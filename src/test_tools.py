"""
Tests for tools.py.

Fix vs the original test_tools.py: it imported `search_resume`, which has
never existed in tools.py (the RAG function is `search_documents`). The file
crashed with ImportError before running a single assertion.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from tools import calculator, list_indexed_documents, search_documents


def test_calculator():

    cases = {
        "25*48": "1200",
        "(100+50)/2": "75.0",
        "2**10": "1024",
        "7 % 3": "1",
    }

    for expression, expected in cases.items():
        actual = calculator(expression)
        status = "PASS" if actual == expected else "FAIL"
        print(f"  [{status}] {expression} -> {actual} (expected {expected})")

    # Rejected inputs
    for bad in ["__import__('os').system('ls')", "9**9**9", "1/0", ""]:
        print(f"  [INFO] {bad!r} -> {calculator(bad)}")


def test_documents():

    print("\nIndexed documents:")
    print(list_indexed_documents())

    print("\nSample RAG query:")
    print(search_documents("What is this document about?")[:500])


if __name__ == "__main__":

    print("Testing calculator")
    print("-" * 40)
    test_calculator()

    print("\nTesting document search")
    print("-" * 40)
    test_documents()
