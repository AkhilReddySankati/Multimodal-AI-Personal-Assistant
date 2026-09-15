"""
Console (non-Streamlit) multimodal assistant: face login, then voice chat.

Fixes vs the original src/multimodal.py
---------------------------------------
1. `from agent import ask_agent` failed whenever the script was launched
   directly (python src/multimodal.py), because sys.path[0] was src/ and
   agent.py lives in the project root. The project root is now added to
   sys.path explicitly.
2. The file re-implemented face recognition, speech-to-text and
   text-to-speech that already existed in src/recognize_face.py and
   speech.py - three copies of the same logic with different tolerances and
   different error handling. It now imports them.
3. ENCODINGS_FILE was relative to the working directory; recognize_face.py
   resolves it against the project root. The duplicate is gone.
"""

import os
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")

for path in (BASE_DIR, SRC_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)


from agent import ask_agent
from memory import clear_memory
from speech import speak, speech_to_text

from recognize_face import recognize_from_camera


EXIT_COMMANDS = {"exit", "quit", "stop", "goodbye"}


def start_assistant():

    print("\n" + "=" * 60)
    print("MULTIMODAL AI PERSONAL ASSISTANT")
    print("=" * 60)

    # --------------------------------------------------------
    # STEP 1: FACE AUTHENTICATION
    # --------------------------------------------------------

    try:
        user = recognize_from_camera()
    except FileNotFoundError as error:
        print(f"\n{error}")
        print("Run: python src/register_face.py")
        return
    except Exception as error:
        print(f"\nFace recognition failed: {error}")
        return

    if not user or str(user).strip().lower() == "unknown":
        print("\nUser could not be recognized.")
        speak("Sorry, I could not recognize you.")
        return

    user = str(user).strip()

    print("\n" + "=" * 60)
    print(f"Welcome, {user}!")
    print("=" * 60)

    speak(f"Hello {user}. I am ready to help you.")

    # --------------------------------------------------------
    # STEP 2: VOICE CONVERSATION
    # --------------------------------------------------------

    while True:

        question = speech_to_text()

        if not question:
            continue

        command = question.lower().strip()

        if command in EXIT_COMMANDS:
            speak(f"Goodbye {user}. Have a great day.")
            break

        if command == "clear memory":
            clear_memory()
            speak("Your conversation memory has been cleared.")
            continue

        print("\nSending question to the AI agent...")

        personalized_question = (
            f"The authenticated user is {user}. "
            f"They are speaking through the multimodal voice assistant, "
            f"so keep the answer short and easy to listen to.\n\n"
            f"User question:\n{question}"
        )

        try:
            answer = ask_agent(personalized_question)
            speak(answer)

        except Exception as error:
            print(f"\nAgent error: {error}")
            speak(
                "Sorry, I encountered an error while processing "
                "your request."
            )


if __name__ == "__main__":
    start_assistant()
