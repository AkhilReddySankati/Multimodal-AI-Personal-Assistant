import os
import ast
import re

import pandas as pd


# ============================================================
# CSV / EXCEL
# ============================================================

def inspect_dataframe(filepath):

    extension = os.path.splitext(
        filepath
    )[1].lower()

    if extension == ".csv":

        df = pd.read_csv(
            filepath
        )

    elif extension in [
        ".xlsx",
        ".xls"
    ]:

        df = pd.read_excel(
            filepath
        )

    else:

        return (
            "This file is not a CSV or Excel file."
        )

    summary = []

    summary.append(
        f"File: {os.path.basename(filepath)}"
    )

    summary.append(
        f"Rows: {df.shape[0]}"
    )

    summary.append(
        f"Columns: {df.shape[1]}"
    )

    summary.append(
        "\nColumn information:"
    )

    for column in df.columns:

        summary.append(
            f"- {column}: "
            f"dtype={df[column].dtype}, "
            f"missing={df[column].isna().sum()}"
        )

    summary.append(
        "\nFirst 5 rows:"
    )

    summary.append(
        df.head().to_string()
    )

    return "\n".join(summary)


# ============================================================
# SQL INSPECTION
# ============================================================

def inspect_sql(filepath):

    with open(
        filepath,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        sql = file.read()

    tables = re.findall(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?",
        sql,
        flags=re.IGNORECASE
    )

    primary_keys = re.findall(
        r"PRIMARY\s+KEY\s*\(([^)]*)\)",
        sql,
        flags=re.IGNORECASE
    )

    foreign_keys = re.findall(
        r"FOREIGN\s+KEY\s*\(([^)]*)\)"
        r"\s*REFERENCES\s+[`\"]?(\w+)[`\"]?"
        r"\s*\(([^)]*)\)",
        sql,
        flags=re.IGNORECASE
    )

    output = []

    output.append(
        f"SQL file: {os.path.basename(filepath)}"
    )

    output.append(
        "\nTables:"
    )

    if tables:

        for table in tables:

            output.append(
                f"- {table}"
            )

    else:

        output.append(
            "- No CREATE TABLE statements found."
        )

    output.append(
        "\nPrimary Keys:"
    )

    if primary_keys:

        for key in primary_keys:

            output.append(
                f"- {key}"
            )

    else:

        output.append(
            "- No explicit primary keys found."
        )

    output.append(
        "\nForeign Keys:"
    )

    if foreign_keys:

        for local_column, table, remote_column in foreign_keys:

            output.append(
                f"- {local_column} → "
                f"{table}.{remote_column}"
            )

    else:

        output.append(
            "- No foreign keys found."
        )

    output.append(
        "\nSQL Preview:"
    )

    output.append(
        sql[:5000]
    )

    return "\n".join(output)


# ============================================================
# PYTHON INSPECTION
# ============================================================

def inspect_python(filepath):

    with open(
        filepath,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        source = file.read()

    output = []

    output.append(
        f"Python file: {os.path.basename(filepath)}"
    )

    output.append(
        f"\nLines: {len(source.splitlines())}"
    )

    try:

        tree = ast.parse(
            source
        )

        functions = []
        classes = []
        imports = []

        for node in ast.walk(tree):

            if isinstance(
                node,
                ast.FunctionDef
            ):

                functions.append(
                    node.name
                )

            elif isinstance(
                node,
                ast.AsyncFunctionDef
            ):

                functions.append(
                    node.name
                )

            elif isinstance(
                node,
                ast.ClassDef
            ):

                classes.append(
                    node.name
                )

            elif isinstance(
                node,
                ast.Import
            ):

                for name in node.names:

                    imports.append(
                        name.name
                    )

            elif isinstance(
                node,
                ast.ImportFrom
            ):

                if node.module:

                    imports.append(
                        node.module
                    )

        output.append(
            "\nFunctions:"
        )

        if functions:

            for function in functions:

                output.append(
                    f"- {function}"
                )

        else:

            output.append(
                "- None"
            )

        output.append(
            "\nClasses:"
        )

        if classes:

            for class_name in classes:

                output.append(
                    f"- {class_name}"
                )

        else:

            output.append(
                "- None"
            )

        output.append(
            "\nImports:"
        )

        if imports:

            for module in sorted(
                set(imports)
            ):

                output.append(
                    f"- {module}"
                )

        else:

            output.append(
                "- None"
            )

        output.append(
            "\nSource Preview:"
        )

        output.append(
            source[:5000]
        )

        return "\n".join(output)

    except SyntaxError as error:

        return (
            f"Python syntax error:\n{error}"
        )


# ============================================================
# TEXT / MARKDOWN
# ============================================================

def inspect_text(filepath):

    with open(
        filepath,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        text = file.read()

    return (
        f"File: {os.path.basename(filepath)}\n\n"
        f"Characters: {len(text)}\n"
        f"Words: {len(text.split())}\n\n"
        f"Content preview:\n{text[:5000]}"
    )


# ============================================================
# MAIN INSPECTOR
# ============================================================

def inspect_file(filepath):

    extension = os.path.splitext(
        filepath
    )[1].lower()

    if extension in [
        ".csv",
        ".xlsx",
        ".xls"
    ]:

        return inspect_dataframe(
            filepath
        )

    if extension in [
        ".sql"
    ]:

        return inspect_sql(
            filepath
        )

    if extension in [
        ".py"
    ]:

        return inspect_python(
            filepath
        )

    if extension in [
        ".txt",
        ".md"
    ]:

        return inspect_text(
            filepath
        )

    if extension == ".pdf":

        from pypdf import PdfReader

        reader = PdfReader(
            filepath
        )

        text = ""

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:

                text += page_text + "\n"

        return (
            f"PDF: {os.path.basename(filepath)}\n"
            f"Pages: {len(reader.pages)}\n\n"
            f"Text preview:\n{text[:5000]}"
        )

    if extension == ".docx":

        from docx import Document

        document = Document(
            filepath
        )

        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        )

        return (
            f"DOCX: {os.path.basename(filepath)}\n\n"
            f"Text preview:\n{text[:5000]}"
        )

    return (
        f"Unsupported file type: {extension}"
    )