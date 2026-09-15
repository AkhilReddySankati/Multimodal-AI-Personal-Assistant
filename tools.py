"""
Tool layer between the agent and the individual feature modules.

Fixes vs the original tools.py
------------------------------
1. calculator() no longer uses eval(). A character whitelist does not make
   eval() safe: "9**9**9" passes the whitelist and hangs the process. It is
   now an AST evaluator with an exponent guard.
2. `ast` and `math` were imported but never used; they are now used / removed.
3. Import paths are resolved consistently whether the project is run from the
   project root or from inside src/.
"""

import ast
import operator
import os
import sys


# ------------------------------------------------------------
# Make imports work from the project root and from src/
# ------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")

for path in (BASE_DIR, SRC_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)


from rag import (
    search_documents_text,
    index_documents,
    get_indexed_documents,
)

from src.file_processor import inspect_file
from src.data_analysis import analyze_dataset
from src.code_generator import generate_python_code, generate_sql_code
from src.dashboard import create_dashboard
from src.er_diagram import generate_er_diagram


# ============================================================
# CALCULATOR
# ============================================================

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

MAX_EXPONENT = 100


def _evaluate(node):

    if isinstance(node, ast.Expression):
        return _evaluate(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(
            node.value, (int, float)
        ):
            raise ValueError("Only numbers are allowed.")
        return node.value

    if isinstance(node, ast.UnaryOp):
        handler = _OPERATORS.get(type(node.op))
        if handler is None:
            raise ValueError("Unsupported operator.")
        return handler(_evaluate(node.operand))

    if isinstance(node, ast.BinOp):

        handler = _OPERATORS.get(type(node.op))

        if handler is None:
            raise ValueError("Unsupported operator.")

        left = _evaluate(node.left)
        right = _evaluate(node.right)

        # Guard against 9**9**9 style denial of service.
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ValueError("Exponent too large.")

        return handler(left, right)

    raise ValueError("Unsupported expression.")


def calculator(expression):
    """Safely evaluate a basic arithmetic expression."""

    if not expression or not str(expression).strip():
        return "No mathematical expression provided."

    try:
        tree = ast.parse(str(expression).strip(), mode="eval")
        result = _evaluate(tree)
    except ZeroDivisionError:
        return "Division by zero."
    except Exception:
        return "Could not calculate the expression."

    return str(result)


# ============================================================
# DOCUMENT SEARCH (RAG)
# ============================================================

def search_documents(question, filepaths=None):
    """Search uploaded documents using RAG."""

    if not question:
        return "Please provide a question."

    return search_documents_text(
        query=question,
        top_k=5,
        filepaths=filepaths,
    )


def index_uploaded_documents(filepaths):
    """Index PDF, TXT, MD and DOCX files."""

    if not filepaths:
        return "No documents were provided."

    if isinstance(filepaths, str):
        filepaths = [filepaths]

    output = []

    for result in index_documents(filepaths):

        if result.get("success"):
            output.append(
                f"OK  {result.get('filename')} -> "
                f"{result.get('chunks')} chunks"
            )
        else:
            output.append(f"FAIL {result.get('message')}")

    return "\n".join(output)


def list_indexed_documents():

    documents = get_indexed_documents()

    if not documents:
        return "No documents are currently indexed."

    return "\n".join(f"- {document}" for document in documents)


# ============================================================
# FILE INSPECTION
# ============================================================

def inspect_uploaded_file(filepath):
    """Inspect CSV, Excel, SQL, Python, PDF, TXT, MD and DOCX files."""

    if not filepath:
        return "No file path provided."

    if not os.path.exists(filepath):
        return f"File not found: {filepath}"

    try:
        return inspect_file(filepath)
    except Exception as error:
        return f"File inspection error: {error}"


# ============================================================
# DATASET ANALYSIS
# ============================================================

def analyze_uploaded_dataset(filepath):
    """Analyze a CSV or Excel dataset."""

    if not filepath:
        return "No dataset path provided."

    if not os.path.exists(filepath):
        return f"Dataset not found: {filepath}"

    try:
        return analyze_dataset(filepath)
    except Exception as error:
        return f"Dataset analysis error: {error}"


# ============================================================
# CODE GENERATION
# ============================================================

def generate_python(requirement):

    if not requirement:
        return "Please provide a Python requirement."

    try:
        return generate_python_code(requirement)
    except Exception as error:
        return f"Python generation error: {error}"


def generate_sql(requirement):

    if not requirement:
        return "Please provide an SQL requirement."

    try:
        return generate_sql_code(requirement)
    except Exception as error:
        return f"SQL generation error: {error}"


# ============================================================
# DASHBOARD
# ============================================================

def generate_dashboard(
    filepath,
    chart_type="auto",
    x_column="",
    y_column="",
):
    """
    Build a Plotly chart.

    Returns a dict on success (figure, dataframe, chart_type, x_column,
    y_column) or an error string. The caller is responsible for rendering
    the figure - it must never be sent to the LLM directly.
    """

    if not filepath:
        return "No dataset path provided."

    if not os.path.exists(filepath):
        return f"Dataset not found: {filepath}"

    try:
        return create_dashboard(
            filepath=filepath,
            chart_type=chart_type,
            x_column=x_column,
            y_column=y_column,
        )
    except Exception as error:
        return f"Dashboard generation error: {error}"


# ============================================================
# ER DIAGRAM
# ============================================================

def create_er_diagram(filepath):
    """Return {'filename': ..., 'mermaid': ...} or an error string."""

    if not filepath:
        return "No SQL file path provided."

    if not os.path.exists(filepath):
        return f"SQL file not found: {filepath}"

    try:
        return generate_er_diagram(filepath)
    except Exception as error:
        return f"ER diagram generation error: {error}"
