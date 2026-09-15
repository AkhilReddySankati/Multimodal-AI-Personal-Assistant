"""
Python / SQL code generation.

Fix vs the original src/code_generator.py: it did not generate anything. It
returned a fixed template containing `pass` and `SELECT * FROM your_table`
regardless of the requirement, while the agent advertised "Python code
generation" and "SQL code generation" as real capabilities. It now calls the
LLM and falls back to the template only if the call fails.
"""

import os
import re
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def _strip_fences(text):
    """Remove ```python ... ``` wrappers the model sometimes adds."""

    if not text:
        return ""

    match = re.search(
        r"```[a-zA-Z]*\s*\n(.*?)```",
        text,
        flags=re.DOTALL,
    )

    return match.group(1).strip() if match else text.strip()


def _fallback_python(requirement, reason):

    return f"""# Code generation is unavailable ({reason}).
# Requirement:
# {requirement}


def main():
    # Implement the requirement here.
    pass


if __name__ == "__main__":
    main()
"""


def _fallback_sql(requirement, reason):

    return f"""-- Code generation is unavailable ({reason}).
-- Requirement:
-- {requirement}

SELECT *
FROM your_table
LIMIT 10;
"""


# ============================================================
# PYTHON
# ============================================================

def generate_python_code(requirement):

    if not requirement:
        return "Please describe what the Python code should do."

    prompt = f"""Write Python code for this requirement.

Requirement:
{requirement}

Rules:
- Return only the code, inside a single ```python block.
- Include short comments for non-obvious steps.
- Use the standard library unless another library is clearly required.
- Add a simple usage example under `if __name__ == "__main__":`.
- Do not include explanations outside the code block.
"""

    try:
        from llm import generate_response

        code = _strip_fences(generate_response(prompt))

    except Exception as error:
        return _fallback_python(requirement, error)

    if not code:
        return _fallback_python(requirement, "empty model response")

    header = (
        "# ============================================================\n"
        "# Generated Python code - review and test before running.\n"
        f"# Requirement: {requirement}\n"
        "# ============================================================\n\n"
    )

    return header + code


# ============================================================
# SQL
# ============================================================

def generate_sql_code(requirement):

    if not requirement:
        return "Please describe what the SQL should do."

    prompt = f"""Write an SQL query for this requirement.

Requirement:
{requirement}

Rules:
- Return only SQL, inside a single ```sql block.
- Use standard ANSI SQL unless a dialect is specified.
- Use clear table and column aliases.
- Add short -- comments where the logic is not obvious.
- Do not include explanations outside the code block.
"""

    try:
        from llm import generate_response

        sql = _strip_fences(generate_response(prompt))

    except Exception as error:
        return _fallback_sql(requirement, error)

    if not sql:
        return _fallback_sql(requirement, "empty model response")

    header = (
        "-- ============================================================\n"
        "-- Generated SQL - verify table and column names before running.\n"
        f"-- Requirement: {requirement}\n"
        "-- ============================================================\n\n"
    )

    return header + sql
