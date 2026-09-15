import os
import hashlib

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURATION
# ============================================================

CHROMA_PATH = "data/chroma_db"
COLLECTION_NAME = "assistant_documents"

SUPPORTED_DOCUMENTS = {
    ".pdf",
    ".txt",
    ".md",
    ".docx",
}


# ============================================================
# CREATE DIRECTORIES
# ============================================================

os.makedirs("data", exist_ok=True)
os.makedirs("data/documents", exist_ok=True)
os.makedirs("data/uploads", exist_ok=True)
os.makedirs(CHROMA_PATH, exist_ok=True)


# ============================================================
# EMBEDDING MODEL
# ============================================================

print("Loading embedding model...")

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# ============================================================
# CHROMA DATABASE
# ============================================================

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME
)


# ============================================================
# READ PDF
# ============================================================

def read_pdf(filepath):
    text = ""

    reader = PdfReader(filepath)

    for page_number, page in enumerate(reader.pages, start=1):

        try:
            page_text = page.extract_text()

            if page_text:
                text += (
                    f"\n[Page {page_number}]\n"
                    f"{page_text}\n"
                )

        except Exception:
            continue

    return text


# ============================================================
# READ DOCX
# ============================================================

def read_docx(filepath):

    try:

        from docx import Document

        document = Document(filepath)

        paragraphs = []

        for paragraph in document.paragraphs:

            text = paragraph.text.strip()

            if text:
                paragraphs.append(text)

        return "\n".join(paragraphs)

    except ImportError:

        return (
            "DOCX support requires python-docx. "
            "Install it using: pip install python-docx"
        )

    except Exception as error:

        return f"Could not read DOCX file: {error}"


# ============================================================
# READ TEXT FILE
# ============================================================

def read_text_file(filepath):

    encodings = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin-1"
    ]

    for encoding in encodings:

        try:

            with open(
                filepath,
                "r",
                encoding=encoding
            ) as file:

                return file.read()

        except UnicodeDecodeError:

            continue

    return ""


# ============================================================
# READ DOCUMENT
# ============================================================

def read_document(filepath):

    extension = os.path.splitext(filepath)[1].lower()

    if extension == ".pdf":

        return read_pdf(filepath)

    if extension == ".docx":

        return read_docx(filepath)

    if extension in [".txt", ".md"]:

        return read_text_file(filepath)

    return ""


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):

    if not text:
        return ""

    lines = []

    for line in text.splitlines():

        line = line.strip()

        if line:

            lines.append(line)

    return "\n".join(lines)


# ============================================================
# TEXT CHUNKING
# ============================================================

def split_text(
    text,
    chunk_size=500,
    overlap=100
):

    words = text.split()

    if not words:
        return []

    chunks = []

    start = 0

    while start < len(words):

        end = start + chunk_size

        chunk = " ".join(
            words[start:end]
        )

        if chunk.strip():

            chunks.append(chunk)

        if end >= len(words):

            break

        start = end - overlap

    return chunks


# ============================================================
# FILE HASH
# ============================================================

def get_file_hash(filepath):

    sha256 = hashlib.sha256()

    with open(filepath, "rb") as file:

        while True:

            data = file.read(1024 * 1024)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()


# ============================================================
# DOCUMENT ID
# ============================================================

def make_chunk_id(
    file_hash,
    chunk_number
):

    return (
        f"{file_hash}_chunk_{chunk_number}"
    )


# ============================================================
# INDEX ONE DOCUMENT
# ============================================================

def index_document(filepath):

    if not os.path.exists(filepath):

        return {
            "success": False,
            "message": "File does not exist."
        }

    extension = os.path.splitext(filepath)[1].lower()

    if extension not in SUPPORTED_DOCUMENTS:

        return {
            "success": False,
            "message": (
                f"Unsupported RAG document type: "
                f"{extension}"
            )
        }

    filename = os.path.basename(filepath)

    print(
        f"\n📄 Indexing document: {filename}"
    )

    try:

        text = read_document(filepath)

        text = clean_text(text)

        if not text:

            return {
                "success": False,
                "message": (
                    f"No readable text found in "
                    f"{filename}"
                )
            }

        chunks = split_text(text)

        if not chunks:

            return {
                "success": False,
                "message": (
                    f"No chunks created for "
                    f"{filename}"
                )
            }

        file_hash = get_file_hash(filepath)

        ids = []

        metadata = []

        for index, chunk in enumerate(chunks):

            ids.append(
                make_chunk_id(
                    file_hash,
                    index
                )
            )

            metadata.append(
                {
                    "source": filename,
                    "filepath": os.path.abspath(filepath),
                    "file_hash": file_hash,
                    "chunk_id": index
                }
            )

        embeddings = embedding_model.encode(
            chunks,
            show_progress_bar=False
        ).tolist()

        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadata
        )

        print(
            f"✅ Indexed {len(chunks)} chunks "
            f"from {filename}"
        )

        return {
            "success": True,
            "filename": filename,
            "chunks": len(chunks),
            "message": (
                f"Successfully indexed "
                f"{filename}"
            )
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                f"Could not index {filename}: "
                f"{error}"
            )
        }


# ============================================================
# INDEX MULTIPLE DOCUMENTS
# ============================================================

def index_documents(filepaths):

    results = []

    for filepath in filepaths:

        result = index_document(filepath)

        results.append(result)

    return results


# ============================================================
# SEARCH DOCUMENTS
# ============================================================

def search_documents(
    query,
    top_k=5,
    filepaths=None
):

    if not query:

        return {
            "documents": [],
            "metadatas": [],
            "distances": []
        }

    try:

        total_documents = collection.count()

        if total_documents == 0:

            return {
                "documents": [],
                "metadatas": [],
                "distances": []
            }

        query_embedding = embedding_model.encode(
            [query]
        ).tolist()

        query_arguments = {
            "query_embeddings": query_embedding,
            "n_results": min(
                top_k,
                total_documents
            )
        }

        # ----------------------------------------------------
        # OPTIONAL FILE FILTER
        # ----------------------------------------------------

        if filepaths:

            filenames = [
                os.path.basename(path)
                for path in filepaths
            ]

            if len(filenames) == 1:

                query_arguments["where"] = {
                    "source": filenames[0]
                }

            else:

                query_arguments["where"] = {
                    "$or": [
                        {
                            "source": filename
                        }
                        for filename in filenames
                    ]
                }

        results = collection.query(
            **query_arguments
        )

        documents = results.get(
            "documents",
            [[]]
        )

        metadatas = results.get(
            "metadatas",
            [[]]
        )

        distances = results.get(
            "distances",
            [[]]
        )

        return {
            "documents": (
                documents[0]
                if documents
                else []
            ),
            "metadatas": (
                metadatas[0]
                if metadatas
                else []
            ),
            "distances": (
                distances[0]
                if distances
                else []
            )
        }

    except Exception as error:

        print(
            f"RAG search error: {error}"
        )

        return {
            "documents": [],
            "metadatas": [],
            "distances": [],
            "error": str(error)
        }


# ============================================================
# GENERAL DOCUMENT SEARCH
# ============================================================

def search_documents_text(
    query,
    top_k=5,
    filepaths=None
):

    results = search_documents(
        query=query,
        top_k=top_k,
        filepaths=filepaths
    )

    documents = results.get(
        "documents",
        []
    )

    metadatas = results.get(
        "metadatas",
        []
    )

    if not documents:

        return (
            "No relevant information was found "
            "in the provided documents."
        )

    output = []

    for index, document in enumerate(
        documents
    ):

        source = "Unknown document"

        if index < len(metadatas):

            source = metadatas[index].get(
                "source",
                "Unknown document"
            )

        output.append(
            f"--- Source: {source} ---\n"
            f"{document}"
        )

    return "\n\n".join(output)


# ============================================================
# GET INDEXED DOCUMENTS
# ============================================================

def get_indexed_documents():

    try:

        result = collection.get(
            include=["metadatas"]
        )

        metadatas = result.get(
            "metadatas",
            []
        )

        documents = sorted(
            set(
                metadata.get(
                    "source"
                )
                for metadata in metadatas
                if metadata
            )
        )

        return documents

    except Exception:

        return []


# ============================================================
# REMOVE DOCUMENT
# ============================================================

def remove_document(filename):

    try:

        results = collection.get(
            where={
                "source": filename
            }
        )

        ids = results.get(
            "ids",
            []
        )

        if ids:

            collection.delete(
                ids=ids
            )

        return True

    except Exception as error:

        print(
            f"Could not remove document: {error}"
        )

        return False


# ============================================================
# GENERAL RAG SEARCH
# ============================================================

def ask_rag(
    question,
    filepaths=None
):

    results = search_documents(
        question,
        top_k=5,
        filepaths=filepaths
    )

    documents = results.get(
        "documents",
        []
    )

    if not documents:

        return (
            "No relevant information was found "
            "in the provided documents."
        )

    context_parts = []

    metadatas = results.get(
        "metadatas",
        []
    )

    for index, document in enumerate(
        documents
    ):

        source = "Unknown"

        if index < len(metadatas):

            source = metadatas[index].get(
                "source",
                "Unknown"
            )

        context_parts.append(
            f"[Source: {source}]\n"
            f"{document}"
        )

    return "\n\n".join(
        context_parts
    )


# ============================================================
# COMMAND LINE TEST
# ============================================================

if __name__ == "__main__":

    print(
        "\n" + "=" * 60
    )

    print(
        "📚 GENERAL DOCUMENT RAG"
    )

    print(
        "=" * 60
    )

    print(
        "\nIndexed documents:"
    )

    for document in get_indexed_documents():

        print(
            f"  • {document}"
        )

    question = input(
        "\nAsk a question: "
    ).strip()

    if question:

        answer = ask_rag(
            question
        )

        print(
            "\n🔎 Retrieved context:\n"
        )

        print(answer)