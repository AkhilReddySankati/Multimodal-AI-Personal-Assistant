"""
SQL schema -> Mermaid ER diagram.

Fixes vs the original er_diagram.py
-----------------------------------
1. The body was split with body.split(","), which breaks any type containing
   a comma: DECIMAL(10,2) became the two fragments "amount DECIMAL(10" and
   "2)". Splitting is now done on top-level commas only.
2. Foreign keys were matched to their owning table with
   `if local_column in table_body`, taking the first table that merely
   contained that substring. Every table with an "id" column matched the
   same table, so relationships pointed at the wrong entity. Foreign keys
   are now parsed per table body.
3. Inline REFERENCES (column-level foreign keys) are now detected too.
4. Mermaid forbids some characters in type names, so types are sanitised.
"""

import os
import re


# ============================================================
# READ SQL
# ============================================================

def read_sql(filepath):

    with open(filepath, "r", encoding="utf-8", errors="ignore") as file:
        return file.read()


# ============================================================
# PARSING HELPERS
# ============================================================

TABLE_PATTERN = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"[`\"\[]?(\w+)[`\"\]]?\s*\(",
    flags=re.IGNORECASE,
)

FK_PATTERN = re.compile(
    r"FOREIGN\s+KEY\s*\(\s*[`\"\[]?(\w+)[`\"\]]?\s*\)\s*"
    r"REFERENCES\s+[`\"\[]?(\w+)[`\"\]]?\s*\(\s*[`\"\[]?(\w+)",
    flags=re.IGNORECASE,
)

INLINE_FK_PATTERN = re.compile(
    r"^[`\"\[]?(\w+)[`\"\]]?\s+[\w()\s,]*?"
    r"REFERENCES\s+[`\"\[]?(\w+)[`\"\]]?\s*\(\s*[`\"\[]?(\w+)",
    flags=re.IGNORECASE,
)

COLUMN_PATTERN = re.compile(r"^[`\"\[]?(\w+)[`\"\]]?\s+([A-Za-z]\w*)")

CONSTRAINT_KEYWORDS = (
    "PRIMARY KEY",
    "FOREIGN KEY",
    "UNIQUE",
    "CHECK",
    "CONSTRAINT",
    "INDEX",
    "KEY ",
)


def extract_tables(sql):
    """Return [(table_name, body)] using balanced-parenthesis matching."""

    tables = []

    for match in TABLE_PATTERN.finditer(sql):

        name = match.group(1)
        start = match.end()
        depth = 1
        index = start

        while index < len(sql) and depth > 0:
            character = sql[index]
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            index += 1

        if depth == 0:
            tables.append((name, sql[start:index - 1]))

    return tables


def split_top_level(body):
    """Split a CREATE TABLE body on commas that are not inside brackets."""

    parts = []
    depth = 0
    current = []

    for character in body:

        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1

        if character == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(character)

    if current:
        parts.append("".join(current).strip())

    return [part for part in parts if part]


def is_constraint(row):

    upper = row.upper().strip()

    return any(upper.startswith(word) for word in CONSTRAINT_KEYWORDS)


def sanitise_type(data_type):
    """Mermaid only accepts simple identifiers as attribute types."""

    return re.sub(r"\W", "_", data_type) or "unknown"


# ============================================================
# GENERATE MERMAID ER DIAGRAM
# ============================================================

def generate_er_diagram(filepath):

    sql = read_sql(filepath)

    tables = extract_tables(sql)

    lines = ["erDiagram"]
    relationships = []

    for table_name, body in tables:

        lines.append(f"    {table_name} {{")

        for row in split_top_level(body):

            # ------------------------------------------------
            # Table-level foreign key
            # ------------------------------------------------

            fk_match = FK_PATTERN.search(row)

            if fk_match:
                relationships.append(
                    (fk_match.group(2), table_name, fk_match.group(1))
                )
                continue

            if is_constraint(row):
                continue

            # ------------------------------------------------
            # Column-level foreign key
            # ------------------------------------------------

            inline_match = INLINE_FK_PATTERN.match(row)

            if inline_match:
                relationships.append(
                    (
                        inline_match.group(2),
                        table_name,
                        inline_match.group(1),
                    )
                )

            # ------------------------------------------------
            # Ordinary column
            # ------------------------------------------------

            column_match = COLUMN_PATTERN.match(row)

            if column_match:
                lines.append(
                    f"        {sanitise_type(column_match.group(2))} "
                    f"{column_match.group(1)}"
                )

        lines.append("    }")

    seen = set()

    for parent, child, column in relationships:

        key = (parent, child, column)

        if key in seen:
            continue

        seen.add(key)

        lines.append(f"    {parent} ||--o{{ {child} : \"{column}\"")

    return {
        "filename": os.path.basename(filepath),
        "tables": [name for name, _ in tables],
        "mermaid": "\n".join(lines),
    }


if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:
        print("Usage: python src/er_diagram.py schema.sql")
    else:
        print(generate_er_diagram(sys.argv[1])["mermaid"])
