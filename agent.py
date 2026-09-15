"""
Gemini function-calling agent.

Changes in this revision
-----------------------
1. generate_dashboard now pushes the FULL dashboard dict (kpis, figures,
   insights, dataframe) into `artifacts` as type "dashboard", and returns a
   detailed text summary to the model. This is what lets the model answer
   follow-up questions like "explain this dashboard" or "write a report on
   it" without rebuilding anything.
2. Quota-friendly defaults: fewer tool steps, smaller tool payloads, shorter
   memory window. Each directly reduces tokens per request.
3. The full 429 / quota error text is kept in LAST_ERROR and surfaced to the
   user, so a per-minute limit can be told apart from a per-day limit.
"""

import json
import os
import time

from dotenv import load_dotenv

from google import genai
from google.genai import types

from tools import (
    calculator,
    search_documents,
    index_uploaded_documents,
    list_indexed_documents,
    inspect_uploaded_file,
    analyze_uploaded_dataset,
    generate_python,
    generate_sql,
    generate_dashboard,
    create_er_diagram,
)

from memory import (
    get_memory_context,
    save_memory,
    clear_memory,
)


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in .env")

client = genai.Client(api_key=API_KEY)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Quota controls. Lower = fewer tokens per question.
MAX_TOOL_STEPS = 2
MAX_TOOL_TEXT = 4000
MEMORY_LIMIT = 2

# Full text of the last quota / rate-limit error, for display in the UI.
LAST_ERROR = ""


# ============================================================
# TOOL DECLARATIONS
# ============================================================

STRING = types.Type.STRING


def _string(description):
    return types.Schema(type=STRING, description=description)


TOOL_SPECS = [
    {
        "name": "calculator",
        "description": (
            "Calculate a mathematical expression. "
            "Use this for arithmetic calculations."
        ),
        "properties": {
            "expression": _string(
                "Mathematical expression, for example 12*4 or (100/5)+20."
            )
        },
        "required": ["expression"],
    },
    {
        "name": "search_documents",
        "description": (
            "Search the currently uploaded/indexed documents using semantic "
            "RAG. Use this when the user asks about information contained in "
            "their uploaded PDF, TXT, MD or DOCX documents."
        ),
        "properties": {
            "question": _string("Question to search inside the documents.")
        },
        "required": ["question"],
    },
    {
        "name": "list_indexed_documents",
        "description": (
            "List all documents currently indexed in the RAG vector database."
        ),
        "properties": {},
        "required": [],
    },
    {
        "name": "inspect_uploaded_file",
        "description": (
            "Inspect an uploaded file such as CSV, Excel, SQL, Python, PDF, "
            "TXT, Markdown or DOCX."
        ),
        "properties": {
            "filepath": _string("Path or filename of the uploaded file.")
        },
        "required": ["filepath"],
    },
    {
        "name": "analyze_uploaded_dataset",
        "description": (
            "Analyze a CSV or Excel dataset: rows, columns, missing values, "
            "statistics, correlations and categorical analysis. Returns "
            "numbers only, no charts."
        ),
        "properties": {
            "filepath": _string("CSV or Excel file path or filename.")
        },
        "required": ["filepath"],
    },
    {
        "name": "generate_python",
        "description": (
            "Generate Python code for a user requirement. "
            "Do not execute the generated code."
        ),
        "properties": {
            "requirement": _string(
                "Description of the Python code the user wants."
            )
        },
        "required": ["requirement"],
    },
    {
        "name": "generate_sql",
        "description": (
            "Generate SQL for a user requirement. Do not execute the SQL."
        ),
        "properties": {
            "requirement": _string(
                "Description of the SQL query the user wants."
            )
        },
        "required": ["requirement"],
    },
    {
        "name": "generate_dashboard",
        "description": (
            "Build a full analytics dashboard from an uploaded CSV or Excel "
            "dataset: KPI cards, several charts and written insights. The "
            "dashboard is rendered for the user automatically and the tool "
            "returns its KPIs, chart titles and insights as text. "
            "Call this ONLY to build a NEW dashboard. If a dashboard has "
            "already been built and the user asks you to explain, summarise "
            "or write a report about it, answer from the dashboard summary "
            "already in the conversation instead of calling this again."
        ),
        "properties": {
            "filepath": _string("CSV or Excel file path or filename."),
        },
        "required": ["filepath"],
    },
    {
        "name": "create_er_diagram",
        "description": (
            "Create a Mermaid ER diagram from an uploaded SQL schema file. "
            "The diagram is rendered for the user automatically."
        ),
        "properties": {
            "filepath": _string("SQL file path or filename."),
        },
        "required": ["filepath"],
    },
    {
        "name": "index_uploaded_documents",
        "description": (
            "Index PDF, TXT, MD or DOCX files into the RAG vector database "
            "so they can be searched. Only needed if a document was not "
            "indexed automatically."
        ),
        "properties": {
            "filepath": _string("Document path or filename to index."),
        },
        "required": ["filepath"],
    },
]


def _build_tool():
    declarations = []

    for spec in TOOL_SPECS:
        declarations.append(
            types.FunctionDeclaration(
                name=spec["name"],
                description=spec["description"],
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties=spec["properties"],
                    required=spec["required"],
                ),
            )
        )

    return types.Tool(function_declarations=declarations)


AGENT_TOOL = _build_tool()


# ============================================================
# GEMINI CALL WITH RETRY
# ============================================================

def generate_with_retry(contents, max_retries=3):
    """Call Gemini, retrying on transient 5xx errors."""

    global LAST_ERROR

    for attempt in range(max_retries):

        try:
            return client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=types.GenerateContentConfig(tools=[AGENT_TOOL]),
            )

        except Exception as error:

            message = str(error)

            if any(code in message for code in ["500", "502", "503", "504"]):

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(
                        f"\nGemini temporarily busy. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue

                LAST_ERROR = message
                return None

            if "429" in message or "RESOURCE_EXHAUSTED" in message:
                LAST_ERROR = message
                print("\nGemini quota exceeded. Full error:")
                print(message)
                return None

            raise

    return None


# ============================================================
# HELPERS
# ============================================================

def build_file_context(uploaded_files):

    if not uploaded_files:
        return "No files are currently uploaded."

    lines = ["CURRENT UPLOADED FILES:"]

    for filepath in uploaded_files:
        lines.append(f"- {filepath}")

    lines.append(
        "\nUse the appropriate tool when information from these files "
        "is needed. Pass the full path exactly as listed above."
    )

    return "\n".join(lines)


def _resolve_path(filepath, uploaded_files):
    """Gemini often returns only a filename. Map it back to a real path."""

    if not filepath:
        for candidate in uploaded_files or []:
            if candidate.lower().endswith((".csv", ".xlsx", ".xls")):
                return candidate
        return filepath

    if os.path.exists(filepath):
        return filepath

    wanted = os.path.basename(filepath).lower()

    for candidate in uploaded_files or []:
        if os.path.basename(candidate).lower() == wanted:
            return candidate

    return filepath


def _extract_text(response):
    """response.text can be None or raise when only function calls exist."""

    try:
        text = response.text
    except Exception:
        text = None

    if text:
        return text

    parts_text = []

    for candidate in response.candidates or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "text", None):
                parts_text.append(part.text)

    return "\n".join(parts_text)


def _function_calls(candidate):
    calls = []

    content = getattr(candidate, "content", None)

    for part in getattr(content, "parts", None) or []:
        if getattr(part, "function_call", None):
            calls.append(part.function_call)

    return calls


def _to_tool_text(result):
    """Convert any tool return value into a JSON-safe string."""

    if result is None:
        return "No result."

    if isinstance(result, str):
        return result[:MAX_TOOL_TEXT]

    try:
        text = json.dumps(result, indent=2, default=str, ensure_ascii=False)
    except Exception:
        text = str(result)

    return text[:MAX_TOOL_TEXT]


def _chart_title(figure):
    try:
        return figure.layout.title.text or "chart"
    except Exception:
        return "chart"


def describe_dashboard(result, filename):
    """
    Turn a dashboard dict into text the model can reason about.

    This is what makes follow-up questions work: the model never sees the
    Plotly figures, only this description, so it must carry the real numbers.
    """

    lines = [f"Dashboard built from {filename} and displayed to the user."]

    dataframe = result.get("dataframe")

    if dataframe is not None:
        lines.append(
            f"Rows: {len(dataframe)}, Columns: {len(dataframe.columns)}"
        )

    kpis = result.get("kpis") or []

    if kpis:
        lines.append("\nKPI cards shown:")
        for item in kpis:
            try:
                title, value, note = item
                lines.append(f"- {title}: {value} ({note})")
            except Exception:
                lines.append(f"- {item}")

    figures = result.get("figures") or []

    if figures:
        lines.append("\nCharts shown:")
        for figure in figures:
            lines.append(f"- {_chart_title(figure)}")

    insights = result.get("insights") or []

    if insights:
        lines.append("\nInsights computed:")
        for insight in insights:
            lines.append(f"- {insight}")

    lines.append(
        "\nThe charts are already visible to the user. Describe and "
        "interpret them in words. Do not claim to be unable to see them."
    )

    return "\n".join(lines)


# ============================================================
# TOOL EXECUTION
# ============================================================

def _run_tool(tool_name, args, question, uploaded_files, artifacts):
    """
    Execute one tool call.

    Returns the text sent back to Gemini. Rich objects (dashboards, Mermaid
    source) are appended to `artifacts` for the UI to render.
    """

    if tool_name == "calculator":
        return calculator(args.get("expression", ""))

    if tool_name == "search_documents":
        return search_documents(
            args.get("question", question),
            uploaded_files,
        )

    if tool_name == "list_indexed_documents":
        return list_indexed_documents()

    if tool_name == "index_uploaded_documents":
        path = _resolve_path(args.get("filepath", ""), uploaded_files)
        return index_uploaded_documents([path])

    if tool_name == "inspect_uploaded_file":
        path = _resolve_path(args.get("filepath", ""), uploaded_files)
        return inspect_uploaded_file(path)

    if tool_name == "analyze_uploaded_dataset":
        path = _resolve_path(args.get("filepath", ""), uploaded_files)
        return _to_tool_text(analyze_uploaded_dataset(path))

    if tool_name == "generate_dashboard":

        path = _resolve_path(args.get("filepath", ""), uploaded_files)

        result = generate_dashboard(filepath=path)

        if isinstance(result, str):
            return result

        filename = os.path.basename(path)

        summary = describe_dashboard(result, filename)

        artifacts.append(
            {
                "type": "dashboard",
                "dashboard": result,
                "filename": filename,
                "summary": summary,
            }
        )

        return summary

    if tool_name == "generate_python":
        return generate_python(args.get("requirement", question))

    if tool_name == "generate_sql":
        return generate_sql(args.get("requirement", question))

    if tool_name == "create_er_diagram":

        path = _resolve_path(args.get("filepath", ""), uploaded_files)

        result = create_er_diagram(path)

        if isinstance(result, str):
            return result

        mermaid = result.get("mermaid", "")

        artifacts.append(
            {
                "type": "mermaid",
                "mermaid": mermaid,
                "title": f"ER diagram of {result.get('filename')}",
            }
        )

        return (
            "ER diagram created and displayed to the user.\n\n"
            f"Mermaid source:\n{mermaid}"
        )

    return f"Unknown tool: {tool_name}"


# ============================================================
# SYSTEM PROMPT
# ============================================================

def _build_prompt(question, file_context, memory_context):

    return f"""
You are an intelligent personal AI assistant.

You are a GENERAL assistant, NOT a resume-only assistant.
You can answer general questions using your own knowledge.
You also have tools for uploaded files and documents.

TOOL RULES:

- If no files are uploaded, answer general questions normally.
- PDF, TXT, MD and DOCX are searched through RAG.
- CSV and Excel use dataset analysis or the dashboard tool, never RAG.
- SQL files use file inspection or the ER diagram tool.
- Use the calculator for arithmetic.
- Never execute generated Python or SQL.
- Never invent information from uploaded documents. If an answer is not
  present in a document, say so clearly.

DASHBOARD RULES:

- Build a dashboard only when the user asks for a NEW one.
- If a dashboard summary already appears in this prompt or earlier in the
  conversation, the charts are already on screen. Answer questions about
  them ("explain it", "write a report", "summarise in 10 lines") directly
  from that summary. Do NOT call the dashboard tool again.
- Quote the real KPI values and chart names when describing a dashboard.
- Write what the user asked for. A request for a report should read like a
  report, not like a confirmation message.

ANSWER FORMAT:

- Match the format the user asked for: a report reads as a report, an
  explanation in 10 lines is 10 lines, a summary is short.
- For technical questions: explain simply, give syntax, give one example,
  explain the example.

CURRENT FILES:

{file_context}

CONVERSATION MEMORY:

{memory_context}

CURRENT USER QUESTION:

{question}
"""


# ============================================================
# ASK AGENT
# ============================================================

def ask_agent(question, uploaded_files=None, artifacts=None):
    """
    Answer a question, using tools when needed.

    Parameters
    ----------
    question : str
    uploaded_files : list[str] | None
    artifacts : list | None
        Optional list. Dashboards and Mermaid diagrams produced during the
        run are appended to it so the UI can render them.

    Returns
    -------
    str
    """

    uploaded_files = uploaded_files or []

    if artifacts is None:
        artifacts = []

    prompt = _build_prompt(
        question=question,
        file_context=build_file_context(uploaded_files),
        memory_context=get_memory_context(limit=MEMORY_LIMIT),
    )

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
    ]

    for _ in range(MAX_TOOL_STEPS):

        response = generate_with_retry(contents)

        if response is None:
            return _unavailable_message()

        if not response.candidates:
            return "Gemini did not return a response."

        candidate = response.candidates[0]

        calls = _function_calls(candidate)

        # ----------------------------------------------------
        # No tool requested -> final answer
        # ----------------------------------------------------

        if not calls:

            answer = _extract_text(response) or (
                "I could not generate a final answer."
            )

            save_memory(question, answer)

            return answer

        # ----------------------------------------------------
        # Run every requested tool
        # ----------------------------------------------------

        tool_response_parts = []

        for call in calls:

            tool_name = call.name
            args = dict(call.args or {})

            print(f"\nTool selected: {tool_name}")

            try:
                result = _run_tool(
                    tool_name,
                    args,
                    question,
                    uploaded_files,
                    artifacts,
                )
            except Exception as error:
                result = f"Tool '{tool_name}' failed: {error}"

            tool_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response={"result": _to_tool_text(result)},
                )
            )

        contents.append(candidate.content)

        contents.append(
            types.Content(role="user", parts=tool_response_parts)
        )

    # --------------------------------------------------------
    # Step budget exhausted. If a dashboard was built, say so
    # rather than returning a useless message.
    # --------------------------------------------------------

    for artifact in artifacts:
        if artifact.get("type") == "dashboard":
            answer = (
                f"I built the dashboard for "
                f"**{artifact.get('filename')}**. The KPI cards, charts and "
                f"insights are shown below."
            )
            save_memory(question, answer)
            return answer

    answer = (
        "I used several tools but could not finish the answer. "
        "Please try asking a narrower question."
    )

    save_memory(question, answer)

    return answer


def _unavailable_message():
    """Include the real quota error so RPM and RPD can be told apart."""

    base = "Gemini is unavailable or the API quota has been exceeded."

    if not LAST_ERROR:
        return base

    return f"{base}\n\n```\n{LAST_ERROR[:800]}\n```"


# Backwards compatibility.
agent = ask_agent


# ============================================================
# COMMAND LINE TEST
# ============================================================

if __name__ == "__main__":

    print("\n" + "=" * 60)
    print("GENERAL AI AGENT")
    print("=" * 60)
    print("\nType 'exit' to quit, 'clear memory' to wipe history.\n")

    while True:

        try:
            user_question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_question:
            continue

        if user_question.lower() in ["exit", "quit", "stop", "goodbye"]:
            print("\nGoodbye!")
            break

        if user_question.lower() == "clear memory":
            clear_memory()
            continue

        try:
            print("\nAI:\n")
            print(ask_agent(user_question))
        except Exception as error:
            print(f"\nError: {error}")