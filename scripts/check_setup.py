"""Check that everything is installed and the Gemini key works.

    python scripts/check_setup.py

Makes two tiny API calls (one embedding, one short answer).
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OK, FAIL = "[ OK ]", "[FAIL]"
problems = 0


def report(ok: bool, message: str, hint: str = "") -> None:
    global problems
    print(f"{OK if ok else FAIL} {message}")
    if not ok:
        problems += 1
        if hint:
            print(f"       -> {hint}")


report(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}", "Install Python 3.10 or newer (3.12 recommended).")

for module, package in [("langchain_core", "langchain-core"), ("langchain_google_genai", "langchain-google-genai"),
                        ("streamlit", "streamlit"), ("pypdf", "pypdf"), ("docx", "python-docx"),
                        ("numpy", "numpy"), ("dotenv", "python-dotenv")]:
    try:
        version = getattr(importlib.import_module(module), "__version__", "")
        report(True, f"{package} {version}".strip())
    except ImportError:
        report(False, f"{package} is not installed", "Run: pip install -r requirements.txt")

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
report(bool(key), f"GOOGLE_API_KEY found (ends in ...{key[-4:]})" if key else "GOOGLE_API_KEY is missing",
       "Copy .env.example to .env and paste your key from https://aistudio.google.com/apikey")

if key and problems == 0:
    from docanswer.providers import GeminiAnswerModel, GeminiEmbedder

    try:
        embedder = GeminiEmbedder()
        vector = embedder.embed_query("test")
        report(len(vector) > 0, f"Embeddings work: {embedder.model}, {len(vector)} numbers per text")
    except Exception as error:  # noqa: BLE001
        report(False, f"Embedding call failed: {type(error).__name__}: {str(error)[:300]}",
               "Check the key. If the model is not found, set GEMINI_EMBED_MODEL in .env.")

    try:
        model = GeminiAnswerModel()
        reply = model.answer("a test shop", "[1] (test.txt, Introduction)\nThe shop opens at 9 am.",
                             "When does the shop open?")
        report(bool(reply), f"Chat model works: {model.model} replied: {reply[:120]!r}")
    except Exception as error:  # noqa: BLE001
        report(False, f"Chat call failed: {type(error).__name__}: {str(error)[:300]}",
               "If the model is not found, set GEMINI_CHAT_MODEL in .env (for example gemini-3.1-flash-lite).")

print()
print("All good. Next: streamlit run app.py" if problems == 0 else f"{problems} problem(s) to fix above.")
sys.exit(1 if problems else 0)
