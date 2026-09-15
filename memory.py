import json
import os

from datetime import datetime


# ============================================================
# MEMORY FILE
# ============================================================

MEMORY_FILE = "data/memory.json"


# ============================================================
# INITIALIZE MEMORY
# ============================================================

def initialize_memory():

    os.makedirs(
        "data",
        exist_ok=True
    )

    if not os.path.exists(
        MEMORY_FILE
    ):

        with open(
            MEMORY_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                [],
                file,
                indent=4
            )


# ============================================================
# LOAD MEMORY
# ============================================================

def load_memory():

    initialize_memory()

    try:

        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(
                file
            )

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        return []


# ============================================================
# SAVE MEMORY
# ============================================================

def save_memory(
    question,
    answer
):

    memory = load_memory()

    conversation = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "answer": answer
    }

    memory.append(
        conversation
    )

    # Keep last 100 conversations
    memory = memory[-100:]

    with open(
        MEMORY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            memory,
            file,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# RECENT MEMORY
# ============================================================

def get_recent_memory(
    limit=5
):

    memory = load_memory()

    return memory[-limit:]


# ============================================================
# MEMORY CONTEXT
# ============================================================

def get_memory_context(
    limit=5
):

    recent_memory = get_recent_memory(
        limit
    )

    if not recent_memory:

        return (
            "No previous conversation memory."
        )

    context = []

    for item in recent_memory:

        context.append(
            f"Previous Question: "
            f"{item.get('question', '')}\n"
            f"Previous Answer: "
            f"{item.get('answer', '')}"
        )

    return "\n\n".join(
        context
    )


# ============================================================
# CLEAR MEMORY
# ============================================================

def clear_memory():

    initialize_memory()

    with open(
        MEMORY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            [],
            file,
            indent=4
        )

    print(
        "\n🗑️ Memory cleared."
    )