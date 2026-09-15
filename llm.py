"""
Shared Gemini text-generation helper.

Fixes vs the original llm.py
----------------------------
1. The original created one module-level `chat` session at import time. In a
   Streamlit app that session is shared by every user and grows without
   bound. Generation is now stateless by default; a chat session is opt-in.
2. The original was never imported by anything - dead code. It is now the
   backend used by src/code_generator.py.
3. The model name is read from the environment so it can be changed without
   editing code.
"""

import os
import time

from dotenv import load_dotenv
from google import genai


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not set.")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

client = genai.Client(api_key=API_KEY)


# ============================================================
# STATELESS GENERATION
# ============================================================

def generate_response(prompt, max_retries=3):
    """Send a single prompt to Gemini and return the text response."""

    if not prompt:
        return ""

    for attempt in range(max_retries):

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )

            return response.text or ""

        except Exception as error:

            message = str(error)

            if any(code in message for code in ["500", "502", "503", "504"]):

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(
                        f"\nGemini is temporarily busy. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    continue

                return (
                    "Gemini is temporarily unavailable. "
                    "Please try again later."
                )

            if "429" in message or "RESOURCE_EXHAUSTED" in message:
                return (
                    "Gemini API quota has been exceeded. Please wait for "
                    "the quota to reset or use a different project/model."
                )

            raise

    return ""


# ============================================================
# OPTIONAL CHAT SESSION
# ============================================================

def new_chat():
    """Create an isolated chat session (one per user/conversation)."""

    return client.chats.create(model=MODEL_NAME)


if __name__ == "__main__":
    print(generate_response("Say hello in one short sentence."))
