<div align="center">

# 🤖 Multimodal AI Personal Assistant

**A face-authenticated agentic AI system with voice input, document RAG, and nine-tool LLM function calling.**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.63-FF4B4B?logo=streamlit&logoColor=white)
![Gemini](https://img.shields.io/badge/Google%20Gemini-API-4285F4?logo=google&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Store-FFB000)
![dlib](https://img.shields.io/badge/dlib-Face%20Recognition-008080)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## 📌 Overview

Most AI chat apps accept a question and return text. This one authenticates you
with your face first, listens if you'd rather speak than type, and then decides
for itself which of nine tools it needs to answer you — semantic search across
your documents, statistical profiling of a spreadsheet, a generated dashboard,
an ER diagram from a SQL schema, or nothing at all if it already knows.

It is roughly **5,400 lines across 18 modules**, built as a single Streamlit
application.

| | |
|---|---|
| **Problem** | Analysts juggle separate tools for document search, data profiling, charting and schema inspection, with no shared context between them. |
| **Approach** | One conversational interface backed by an LLM agent that routes each question to the right tool and keeps the results in context. |
| **Access control** | Biometric. Unknown faces reach nothing — not the chat, not the uploader. |

---

## 📑 Table of Contents

- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Request Lifecycle](#-request-lifecycle)
- [The Agent Tool Loop](#-the-agent-tool-loop)
- [The Nine Tools](#-the-nine-tools)
- [RAG Pipeline](#-rag-pipeline)
- [Face Authentication](#-face-authentication)
- [Design Deep Dive](#-design-deep-dive)
- [Project Structure](#-project-structure)
- [Tech Stack](#-tech-stack)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Cost and Performance](#-cost-and-performance)
- [Troubleshooting](#-troubleshooting)
- [Known Limitations](#-known-limitations)
- [Roadmap](#-roadmap)
- [Security](#-security)

---

## ✨ Features

| Capability | Implementation |
|---|---|
| 🔐 **Face login** | 128-dimension dlib encodings, matched at a 0.45 distance threshold against a registered gallery |
| 🎤 **Voice input** | Browser audio capture, transcribed via Google Speech Recognition |
| 📚 **Document RAG** | PDF / DOCX / TXT / MD chunked, embedded with `all-MiniLM-L6-v2`, stored in persistent ChromaDB |
| 📊 **Dataset profiling** | Shape, dtypes, missing values, duplicates, descriptive statistics, correlations |
| 📈 **Auto dashboards** | KPI cards, multi-chart Plotly layouts, generated insights — from any CSV or Excel file |
| 🗂️ **ER diagrams** | SQL schema parsed to Mermaid with balanced-parenthesis tokenisation |
| 💻 **Code generation** | Python and SQL from a plain-English requirement |
| 🧠 **Conversation memory** | Rolling history persisted to disk and injected into every prompt |
| 🔁 **Multi-step reasoning** | The agent can chain tools across turns before answering |

---

## 🏗 System Architecture

```mermaid
flowchart TD
    User(["👤 User"]) --> UI["app.py<br/>Streamlit Interface"]

    UI --> Auth{"Face<br/>Authenticated?"}
    Auth -- "No" --> Block["🚫 Access Blocked<br/>st.stop()"]
    Auth -- "Yes" --> Input["Text or Voice Input"]

    Input --> Agent["agent.py<br/>Gemini Function-Calling Agent"]

    Agent --> Memory["memory.py<br/>Conversation History"]
    Agent --> Tools["tools.py<br/>Tool Dispatch Layer"]

    Tools --> RAG["rag.py<br/>Semantic Search"]
    Tools --> Data["src/data_analysis.py<br/>Profiling"]
    Tools --> Dash["src/dashboard.py<br/>KPIs and Charts"]
    Tools --> ER["src/er_diagram.py<br/>SQL to Mermaid"]
    Tools --> Files["src/file_processor.py<br/>Inspection"]
    Tools --> Code["src/code_generator.py<br/>Python and SQL"]

    RAG --> Chroma[("ChromaDB<br/>Vector Store")]
    Dash --> Artifacts["Artifacts List"]
    ER --> Artifacts

    Agent --> Answer["Text Answer"]
    Answer --> UI
    Artifacts --> UI

    Auth -.-> Face["face_agent.py"]
    Face -.-> Recog["src/recognize_face.py"]
    Recog -.-> Pickle[("encodings.pkl")]

    style Agent fill:#4285F4,color:#fff
    style Chroma fill:#FFB000,color:#000
    style Block fill:#d32f2f,color:#fff
    style Artifacts fill:#7b1fa2,color:#fff
```

---

## 🔄 Request Lifecycle

What happens between pressing Send and seeing an answer.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant A as app.py
    participant G as agent.py
    participant M as Gemini API
    participant T as Tools

    U->>A: Question (text or voice)
    A->>G: ask_agent(question, files, artifacts)
    G->>G: Load memory + file context
    G->>M: Prompt + 9 tool declarations

    alt Tool needed
        M-->>G: function_call(name, args)
        G->>T: Execute tool locally
        T-->>G: Result
        G->>G: Rich objects to artifacts<br/>Text summary to model
        G->>M: function_response(safe text)
        M-->>G: Final answer
    else Answered directly
        M-->>G: Final answer
    end

    G->>G: save_memory(question, answer)
    G-->>A: Answer string + artifacts
    A->>U: Rendered text, charts, diagrams
```

---

## ⚙️ The Agent Tool Loop

```mermaid
flowchart LR
    Start(["Question"]) --> Build["Build Prompt<br/>memory + files + question"]
    Build --> Call["Gemini Call<br/>9 tools declared"]
    Call --> Check{"Tool<br/>requested?"}

    Check -- "No" --> Final["Final Answer"]
    Final --> Save["Save to Memory"]
    Save --> Done(["Return"])

    Check -- "Yes" --> Run["Execute Tool"]
    Run --> Split{"Result<br/>type?"}

    Split -- "Text" --> Feed["JSON-safe text<br/>back to model"]
    Split -- "Figure or Mermaid" --> Art["Append to artifacts<br/>for the UI"]

    Art --> Feed
    Feed --> Budget{"Steps<br/>remaining?"}
    Budget -- "Yes" --> Call
    Budget -- "No" --> Exit["Return best available answer"]
    Exit --> Done

    style Call fill:#4285F4,color:#fff
    style Art fill:#7b1fa2,color:#fff
    style Split fill:#f57c00,color:#fff
```

The loop is capped at `MAX_TOOL_STEPS` so a model that keeps requesting tools
cannot spin indefinitely.

---

## 🧰 The Nine Tools

| Tool | Triggered by | Returns |
|---|---|---|
| `calculator` | Arithmetic in a question | Result via a safe AST evaluator, no `eval` |
| `search_documents` | Questions about uploaded PDFs, DOCX, TXT, MD | Top-k semantic matches with sources |
| `list_indexed_documents` | "What documents do you have?" | Names in the vector store |
| `index_uploaded_documents` | A document that skipped auto-indexing | Chunk counts per file |
| `inspect_uploaded_file` | "What's in this file?" | Structure summary for any supported type |
| `analyze_uploaded_dataset` | "Analyse this CSV" | Rows, dtypes, missing values, stats, correlations |
| `generate_dashboard` | "Build a dashboard" | KPI cards, charts, insights — rendered, plus a text summary |
| `create_er_diagram` | A `.sql` schema file | Mermaid ER diagram, rendered |
| `generate_python` / `generate_sql` | "Write code that..." | Generated source, never executed |

### Routing rules

```mermaid
flowchart TD
    Q["Uploaded file"] --> Type{"Extension"}
    Type -- ".pdf .docx .txt .md" --> R["RAG semantic search"]
    Type -- ".csv .xlsx .xls" --> D["Dataset analysis<br/>or dashboard"]
    Type -- ".sql" --> S["Inspection<br/>or ER diagram"]
    Type -- ".py" --> P["Python inspection"]

    style R fill:#2e7d32,color:#fff
    style D fill:#1565c0,color:#fff
    style S fill:#6a1b9a,color:#fff
    style P fill:#ef6c00,color:#fff
```

Spreadsheets deliberately never go through RAG. Semantic search over tabular
rows returns fragments without the aggregate context a statistical summary
provides.

---

## 📚 RAG Pipeline

```mermaid
flowchart LR
    Doc["📄 Document<br/>PDF DOCX TXT MD"] --> Extract["Extract text"]
    Extract --> Chunk["Chunk<br/>500 tokens / 100 overlap"]
    Chunk --> Hash["SHA-256 content hash<br/>per chunk ID"]
    Hash --> Embed["all-MiniLM-L6-v2<br/>384-d embeddings"]
    Embed --> Store[("ChromaDB<br/>persistent collection")]

    Query["❓ Question"] --> QEmbed["Embed query"]
    QEmbed --> Search["Cosine similarity<br/>top-k = 5"]
    Store --> Search
    Search --> Context["Ranked chunks<br/>with source metadata"]

    style Store fill:#FFB000,color:#000
    style Embed fill:#2e7d32,color:#fff
```

**Why content hashing.** Chunk IDs derive from a SHA-256 of the content, so
re-uploading the same document overwrites existing chunks rather than
duplicating them. Without it, uploading a file three times would triple its
weight in every retrieval.

**Why 500/100.** 500 tokens is large enough to hold a complete idea, and the
100-token overlap prevents an answer that straddles a boundary from being cut
in half.

---

## 🔐 Face Authentication

```mermaid
flowchart TD
    subgraph Enrolment ["Enrolment — run once"]
        Photos["data/faces/&lt;name&gt;/*.jpg"] --> Detect1["Detect face"]
        Detect1 --> Encode1["128-d encoding"]
        Encode1 --> Save[("encodings.pkl")]
    end

    subgraph Login ["Login — every session"]
        Cam["📷 Camera capture"] --> Detect2["Detect face"]
        Detect2 --> Encode2["128-d encoding"]
        Encode2 --> Compare["Euclidean distance<br/>to every registered face"]
        Save --> Compare
        Compare --> Thresh{"distance &lt; 0.45?"}
        Thresh -- "Yes" --> Grant["✅ Grant access"]
        Thresh -- "No" --> Deny["🚫 Block entire app"]
    end

    style Grant fill:#2e7d32,color:#fff
    style Deny fill:#d32f2f,color:#fff
```

The gate calls `st.stop()`, so an unrecognised user never renders the chat
interface or the file uploader — it is not a cosmetic check.

Enrolment images that contain no face, or more than one, are skipped with a
reported count rather than silently corrupting the gallery.

---

## 🔬 Design Deep Dive

### The dual-channel tool result

This is the central architectural decision in the project.

Gemini function responses must be **strictly JSON-serialisable**. A Plotly
figure is not. Neither is a pandas DataFrame, nor the `NaN` that `describe()`
produces for a column with a single non-null value. Sending any of them back
raises `ValueError: Out of range float values are not JSON compliant`.

So every rich tool returns two things to two different destinations:

```mermaid
flowchart TD
    Tool["generate_dashboard()"] --> Result["Dashboard result<br/>kpis, figures, insights, dataframe"]

    Result --> Text["📝 Text summary<br/>KPI values, chart titles, insights"]
    Result --> Object["📊 Figure objects"]

    Text --> LLM["Gemini<br/>function_response"]
    Object --> UI["Streamlit<br/>st.plotly_chart"]

    LLM --> Answer["Written analysis"]
    UI --> Visual["Rendered charts"]

    Answer --> Screen["🖥️ User sees both"]
    Visual --> Screen

    style Text fill:#1565c0,color:#fff
    style Object fill:#7b1fa2,color:#fff
    style Screen fill:#2e7d32,color:#fff
```

Two consequences worth noting:

1. **The model can describe a chart it never received.** The summary carries
   the real KPI values and chart titles, so "explain this dashboard" produces
   genuine analysis rather than a hedge.
2. **Follow-ups cost nothing extra.** "Write a report on it" is answered from
   the summary already in context — no rebuild, no second dashboard.

### Why keyword routing was removed

An earlier version short-circuited any question containing the word
"dashboard" straight to the chart builder. It could not distinguish
*"create a dashboard"* from *"explain the dashboard"*, so both returned the
same hardcoded confirmation string and the LLM was never called.

Routing is now the model's job. It has the tool descriptions and the
conversation context, which is exactly the information a keyword match lacks.

### Safe arithmetic

The calculator uses an AST evaluator with a whitelist of operators, not
`eval`. A character whitelist is not sufficient protection: `9**9**9` contains
only digits and asterisks, passes any such filter, and hangs the process.

---

## 📂 Project Structure

```
multimodal-ai-assistant/
│
├── app.py                      # Streamlit UI, face gate, uploads, rendering
├── agent.py                    # Gemini agent, tool declarations, tool loop
├── tools.py                    # Tool dispatch + safe AST calculator
├── rag.py                      # Chunking, embedding, vector search
├── memory.py                   # Conversation persistence
├── llm.py                      # Shared stateless text generation
├── speech.py                   # Microphone STT / TTS for console use
├── face_agent.py               # Authentication wrapper
├── requirements.txt
├── .env                        # GEMINI_API_KEY — never commit
│
├── src/
│   ├── recognize_face.py       # Image and webcam recognition
│   ├── register_face.py        # Builds encodings.pkl
│   ├── data_analysis.py        # CSV / Excel profiling, JSON-safe output
│   ├── dashboard.py            # KPI + chart + insight generation
│   ├── er_diagram.py           # SQL schema to Mermaid
│   ├── file_processor.py       # Multi-format file inspection
│   ├── code_generator.py       # LLM-backed Python / SQL generation
│   └── multimodal.py           # Console version of the assistant
│
├── tests/
│   ├── test_agent.py
│   └── test_tools.py
│
├── docs/
│   └── screenshots/            # UI captures referenced below
│
└── data/
    ├── faces/<person>/         # Enrolment photos
    ├── uploads/                # Saved uploads
    ├── chroma_db/              # Vector store
    └── memory.json             # Conversation history
```

---

## 🛠 Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Interface | Streamlit | Chat UI, camera, uploads, chart rendering |
| LLM | Google Gemini | Reasoning and function calling |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` | 384-d semantic vectors |
| Vector store | ChromaDB | Persistent similarity search |
| Vision | dlib + face_recognition + OpenCV | 128-d face encodings |
| Speech | SpeechRecognition + pyttsx3 | STT and TTS |
| Data | pandas + NumPy | Profiling and transformation |
| Charts | Plotly Express | Interactive figures |
| Diagrams | Mermaid | ER diagrams rendered in-browser |

---
 

## 🚀 Installation

**Requires Python 3.11.**

```bash
git clone https://github.com/<your-username>/multimodal-ai-assistant.git
cd multimodal-ai-assistant

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install dlib-bin            # prebuilt wheel — see note below
pip install -r requirements.txt
pip install face_recognition --no-deps
```

> ### ⚠️ About `dlib-bin`
>
> Installing `face_recognition` the normal way pulls the source-only `dlib`
> package, which compiles C++ and needs Visual Studio with the C++ workload
> plus CMake. Without them the install dies with:
>
> ```
> ERROR: Failed building wheel for dlib
> You must use Visual Studio to build a python extension on windows.
> ```
>
> `dlib-bin` ships prebuilt wheels for CPython 3.11 on Windows, macOS and
> Linux and provides the identical `dlib` module. No toolchain required.

Create `.env` in the project root:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash
```

Register at least one face and verify recognition **before** launching the UI —
debugging a camera through a browser widget is far harder than through a plain
OpenCV window:

```bash
mkdir -p data/faces/YourName    # add 5-10 clear, single-face photos
python src/register_face.py     # builds encodings.pkl
python src/recognize_face.py    # webcam test, should print your name
```

Launch:

```bash
streamlit run app.py
```

First launch takes 10–30 seconds while the embedding model downloads.

---

## ⚙️ Configuration

**`agent.py`**

| Setting | Default | Effect |
|---|---|---|
| `MODEL_NAME` | `gemini-3.8-flash` | Read from `GEMINI_MODEL`. Rate limits are per model. |
| `MAX_TOOL_STEPS` | `2` | Tool rounds per question. Each round is an API call. |
| `MAX_TOOL_TEXT` | `4000` | Character cap on a tool result sent to the model |
| `MEMORY_LIMIT` | `2` | Past exchanges injected into each prompt |

**`src/recognize_face.py`**

| Setting | Default | Effect |
|---|---|---|
| `TOLERANCE` | `0.45` | Face-match distance. Lower is stricter. |

**`rag.py`**

| Setting | Default | Effect |
|---|---|---|
| chunk size | `500` | Tokens per chunk |
| overlap | `100` | Token overlap between chunks |
| `top_k` | `5` | Chunks retrieved per query |

---

## 💡 Usage

Prompts that exercise each path:

| Intent | Example |
|---|---|
| General knowledge | "Explain what a foreign key is" |
| Arithmetic | "What is 17 × 23?" |
| Document RAG | "What does the contract say about termination?" |
| Dataset profiling | "Analyse sales.csv and tell me about missing values" |
| Dashboard | "Build a dashboard from this Excel file" |
| Dashboard follow-up | "Write a report on the dashboard above" |
| ER diagram | "Generate an ER diagram from schema.sql" |
| Code generation | "Write Python to deduplicate a CSV by email" |

Say **"clear memory"** to wipe conversation history mid-session.

---

## 💰 Cost and Performance

Each question costs **at least two API calls** — one to select the tool, one to
interpret the result. Chained tools cost more.

| Lever | Impact |
|---|---|
| `MAX_TOOL_TEXT` | Largest single lever. Tool results are resent on every subsequent round, so a 20,000-character result is charged repeatedly. |
| `MAX_TOOL_STEPS` | Caps worst-case calls per question |
| `MEMORY_LIMIT` | Cuts prompt tokens; a generated code block in history is expensive |
| Model choice | Limits are per model, so switching gives a separate quota bucket |

| Operation | Typical time |
|---|---|
| Cold start (model download) | 10–30 s |
| Warm start | 2–5 s |
| Face recognition | < 1 s |
| Document indexing | 1–3 s per document |
| Simple question | 2–4 s |
| Dashboard generation | 5–10 s |

---

## 🧯 Troubleshooting

<details>
<summary><b>Failed building wheel for dlib</b></summary>

The source `dlib` package needs a C++ toolchain. Install `dlib-bin` instead:

```bash
pip install dlib-bin
python -c "import dlib, face_recognition; print(dlib.__version__)"
```
</details>

<details>
<summary><b>Encoding file not found</b></summary>

`encodings.pkl` has not been built, or was built from the wrong directory.
Run from the project root:

```bash
python src/register_face.py
```
</details>

<details>
<summary><b>Gemini quota exceeded</b></summary>

The full 429 response is printed in the chat. Read the `quota_id`:

- contains `PerMinute` → wait 60 seconds
- contains `PerDay` → wait for the reset at midnight Pacific

Quota is counted **per project**, not per key — a new key in the same project
changes nothing. Check your real limits at `aistudio.google.com/rate-limit`.
</details>

<details>
<summary><b>ModuleNotFoundError: No module named 'src'</b></summary>

Run from the project root. `tools.py` resolves `src/` relative to its own
location, but Python still needs the root on `sys.path`.
</details>

<details>
<summary><b>Startup takes 30 seconds</b></summary>

`rag.py` loads the sentence-transformer at import time and ChromaDB opens its
persistent collection. Once per process, not per request.
</details>

<details>
<summary><b>pkg_resources deprecation warning</b></summary>

Emitted by `face_recognition_models`. Harmless. Suppress with:

```python
import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
```
</details>

---

## ⚠️ Known Limitations

- **Memory and RAG are not scoped per user.** All conversations share one
  `data/memory.json` and all documents share one Chroma collection. After a
  different face logs in, the previous user's history is still in context —
  which partly undermines the point of biometric login.
- **No liveness detection.** A photograph of a registered face will
  authenticate.
- **Concurrent tabs clobber each other.** Memory saves rewrite the whole file,
  so the last write wins.
- **Speech-to-text requires internet.** It calls Google's API.
- **Datasets are held fully in memory.** Very large files will struggle.
- **English only**, for both transcription and prompting.

---

## 🗺 Roadmap

- [ ] Scope memory and the vector collection per authenticated user
- [ ] Liveness detection (blink or head-movement challenge)
- [ ] Per-user rate limiting and usage tracking
- [ ] Offline speech-to-text via Whisper
- [ ] Session-level tool-call audit log
- [ ] Docker packaging
- [ ] Model comparison for the code-generation tools

---

## 🔒 Security

`.env` holds a live API key, and `encodings.pkl` holds **biometric data**.
Neither belongs in version control.

```gitignore
.env
.venv/
encodings.pkl
data/uploads/
data/faces/
data/chroma_db/
data/memory.json
__pycache__/
*.pyc
 

<div align="center">

**Built by [Akhil Reddy Sankati](https://github.com/akhil2203031050881)**

[LinkedIn](https://linkedin.com/in/akhil-reddy-sankati-ba5212320) · akhilreddysankati1328@gmail.com

</div>
