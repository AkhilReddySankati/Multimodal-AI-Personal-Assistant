"""
Manual smoke test for the agent.

Fix vs the original test_agent.py: it did `from agent import agent`, but
agent.py defines `ask_agent`, not `agent`. The file failed with ImportError.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from agent import ask_agent


def main():

    print("Testing AI Agent")
    print("-" * 40)

    question = input("\nAsk your assistant: ").strip()

    if not question:
        print("No question provided.")
        return

    artifacts = []

    answer = ask_agent(question, uploaded_files=[], artifacts=artifacts)

    print("\nAI Assistant:")
    print(answer)

    if artifacts:
        print(f"\nArtifacts produced: {len(artifacts)}")
        for artifact in artifacts:
            print(f"  - {artifact.get('type')}: {artifact.get('title')}")


if __name__ == "__main__":
    main()
