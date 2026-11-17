"""DocAnswer web app.

    streamlit run app.py

Works without an API key (offline demo mode). With GOOGLE_API_KEY set in .env,
in .streamlit/secrets.toml or in Streamlit Cloud secrets, it uses Gemini.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import streamlit as st

from docanswer import OPTIMIZED, RagEngine, load_bytes, make_providers
from docanswer.loaders import SUPPORTED_EXTENSIONS
from docanswer.providers import DEFAULT_CHAT_MODEL

ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = ROOT / "sample_docs"
CACHE_PATH = ROOT / ".cache" / "embeddings.json"

SAMPLE_BUSINESS = "Saffron & Thread"
EXAMPLE_QUESTIONS = [
    "Can I get my money back on a Final Sale item?",
    "What size is SNT-BD-114?",
    "Do you ship to the USA, and who pays customs?",
    "Do you sell wooden furniture?",  # not in the documents: shows the refusal
]

# Limits that keep a public demo inside Gemini's free tier.
MAX_QUESTIONS_PER_SESSION = 15
MAX_QUESTION_CHARS = 500
MAX_FILES = 5
MAX_FILE_MB = 5
MAX_TOTAL_CHARS = 250_000

CONTRA_URL = "https://contra.com/bharti_shrivastava_zu3hypce"


# ------------------------------------------------------------------ settings
def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def setting(name: str) -> str | None:
    """Environment first (Streamlit Cloud exposes root-level secrets as env
    vars), then a local secrets.toml if one exists."""
    value = os.getenv(name)
    if value:
        return value
    secrets_files = [ROOT / ".streamlit" / "secrets.toml", Path.home() / ".streamlit" / "secrets.toml"]
    if any(p.exists() for p in secrets_files):
        try:
            return st.secrets.get(name)
        except Exception:  # noqa: BLE001 - a broken secrets file should not crash the demo
            return None
    return None


# ------------------------------------------------------------------ caching
@st.cache_resource(show_spinner=False)
def get_providers(api_key: str | None):
    return make_providers(api_key)


@st.cache_data(show_spinner=False, max_entries=64)
def parse_file(name: str, data: bytes):
    """Returns (pages, error message or None)."""
    try:
        pages = load_bytes(data, name)
    except Exception as error:  # noqa: BLE001 - corrupt or protected files
        return [], f"Couldn't read {name} ({type(error).__name__})."
    if not any(p.text.strip() for p in pages):
        hint = " Scanned PDFs need OCR first." if name.lower().endswith(".pdf") else ""
        return [], f"No text found in {name}.{hint}"
    return pages, None


@st.cache_resource(show_spinner=False, max_entries=12, ttl=6 * 3600)
def build_engine(fingerprint: str, business: str, api_key: str | None, _pages: list) -> RagEngine:
    # `fingerprint` identifies the documents; `_pages` (leading underscore) is
    # not hashed by Streamlit.
    embedder, model, _ = get_providers(api_key)
    return RagEngine(embedder, model, OPTIMIZED, business=business, cache_path=CACHE_PATH).build(_pages)


def fingerprint_of(files: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for name, data in sorted(files):
        digest.update(name.encode())
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def trim_to_limit(pages: list) -> tuple[list, bool]:
    kept, total = [], 0
    for page in pages:
        if total + len(page.text) > MAX_TOTAL_CHARS:
            return kept, True
        kept.append(page)
        total += len(page.text)
    return kept, False


def is_rate_limit(error: Exception) -> bool:
    text = f"{type(error).__name__} {error}".lower()
    return any(s in text for s in ("429", "resource_exhausted", "resourceexhausted", "quota", "rate limit"))


# ------------------------------------------------------------------ UI pieces
def render_answer(message: dict) -> None:
    st.markdown(message["text"])
    citations = message.get("citations") or []
    if citations:
        st.caption("Sources: " + " · ".join(f"[{c['number']}] {c['source']}, {c['location']}" for c in citations))
        with st.expander("Show the source text"):
            for c in citations:
                st.markdown(f"**[{c['number']}] {c['source']} — {c['location']}**")
                st.caption(c["snippet"])
    elif message.get("refused"):
        st.caption("No supporting passage was found, so the bot did not guess.")


def answer_to_message(answer) -> dict:
    def passage(c) -> str:
        # Show the whole cited passage, not just its first line.
        if 0 < c.number <= len(answer.retrieved):
            return answer.retrieved[c.number - 1].chunk.text
        return c.snippet

    return {
        "role": "assistant",
        "text": answer.text,
        "refused": answer.refused,
        "citations": [
            {"number": c.number, "source": c.source, "location": c.location, "snippet": passage(c)}
            for c in answer.citations
        ],
    }


# ------------------------------------------------------------------ page
def main() -> None:
    st.set_page_config(page_title="DocAnswer: answers from your documents", page_icon="📄", layout="centered")
    _load_dotenv()

    api_key = setting("GOOGLE_API_KEY") or setting("GEMINI_API_KEY")
    for name in ("GEMINI_CHAT_MODEL", "GEMINI_EMBED_MODEL"):
        value = setting(name)
        if value:
            os.environ[name] = value
    source_url = setting("SOURCE_URL")

    try:
        _, _, live = get_providers(api_key)
    except Exception as error:  # noqa: BLE001 - e.g. missing packages
        st.error(f"Couldn't start the Gemini models ({type(error).__name__}: {error}). Running offline instead.")
        api_key, live = None, False

    state = st.session_state
    state.setdefault("messages", [])
    state.setdefault("asked", 0)
    state.setdefault("docs_id", None)

    # ---------------------------------------------------------- sidebar
    with st.sidebar:
        st.header("Documents")
        choice = st.radio("Answer from", ["Sample shop documents", "Upload your own"], label_visibility="collapsed")

        files: list[tuple[str, bytes]] = []
        if choice == "Sample shop documents":
            business = SAMPLE_BUSINESS
            st.caption("Policies of *Saffron & Thread*, a **fictional** handloom shop made up for this demo. "
                       "Download them to check the answers yourself.")
            for path in sorted(SAMPLE_DIR.iterdir()):
                if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    data = path.read_bytes()
                    files.append((path.name, data))
                    st.download_button(f"⬇ {path.name}", data, file_name=path.name, key=f"dl-{path.name}")
        else:
            business = st.text_input("Business name", value="our business", max_chars=60).strip() or "our business"
            uploads = st.file_uploader(
                f"PDF, Word, TXT or Markdown · up to {MAX_FILES} files, {MAX_FILE_MB} MB each",
                type=[ext.lstrip(".") for ext in sorted(SUPPORTED_EXTENSIONS)],
                accept_multiple_files=True,
            ) or []
            if len(uploads) > MAX_FILES:
                st.warning(f"Only the first {MAX_FILES} files are used.")
            for upload in uploads[:MAX_FILES]:
                if upload.size > MAX_FILE_MB * 1024 * 1024:
                    st.warning(f"{upload.name} is larger than {MAX_FILE_MB} MB and was skipped.")
                    continue
                files.append((upload.name, upload.getvalue()))
            st.caption("Files are processed in memory for this session and are not stored.")

        st.divider()
        if live:
            st.success(f"Live: Gemini ({os.getenv('GEMINI_CHAT_MODEL', DEFAULT_CHAT_MODEL)})")
            counter = st.empty()
            counter.caption(f"Questions left this session: {max(0, MAX_QUESTIONS_PER_SESSION - state.asked)}")
        else:
            st.info("Offline demo mode: no API key, so answers are the best-matching sentence, "
                    "copied word for word. Add GOOGLE_API_KEY for real Gemini answers.")
        if st.button("Clear chat"):
            state.messages = []
            st.rerun()

        with st.expander("How it works"):
            st.markdown(
                "- Documents are split into passages that keep their page or section.\n"
                "- Each question searches by meaning **and** by exact words (product codes, prices), "
                "and the two result lists are merged.\n"
                "- The model may only use those passages and must cite them as [1], [2].\n"
                "- An answer with no valid citation is never shown: the bot says it doesn't know."
            )
        links = [f"[Hire me on Contra]({CONTRA_URL})"]
        if source_url:
            links.append(f"[Source code]({source_url})")
        st.caption("Built by Bharti Shrivastava · " + " · ".join(links))

    # ---------------------------------------------------------- documents -> engine
    pages, problems = [], []
    for name, data in files:
        file_pages, problem = parse_file(name, data)
        pages.extend(file_pages)
        if problem:
            problems.append(problem)
    pages, trimmed = trim_to_limit(pages)

    docs_id = fingerprint_of(files) + business
    if docs_id != state.docs_id:  # new documents: start a fresh conversation
        state.docs_id = docs_id
        state.messages = []

    # ---------------------------------------------------------- main area
    st.title("DocAnswer")
    st.markdown("**A customer-help chatbot that answers only from your documents, "
                "and shows the page each answer came from.**")

    for problem in problems:
        st.warning(problem)
    if trimmed:
        st.warning(f"The documents are long, so only the first {MAX_TOTAL_CHARS:,} characters are used in this demo.")
    if not pages:
        st.info("Upload a PDF, Word, TXT or Markdown file in the sidebar to start.")
        return

    try:
        with st.spinner("Reading the documents…"):
            engine = build_engine(docs_id, business, api_key, pages)
    except Exception as error:  # noqa: BLE001
        if is_rate_limit(error):
            st.error("The demo has reached its free daily limit for reading documents. Please try again tomorrow.")
        else:
            st.error(f"Couldn't index the documents ({type(error).__name__}).")
        return

    for message in state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["text"])
            else:
                render_answer(message)

    clicked = None
    examples_box = st.empty()
    if not state.messages and choice == "Sample shop documents":
        with examples_box.container():
            st.caption("Try one:")
            columns = st.columns(2)
            for i, example in enumerate(EXAMPLE_QUESTIONS):
                if columns[i % 2].button(example, key=f"example-{i}"):
                    clicked = example

    question = st.chat_input("Ask a question about the documents…", max_chars=MAX_QUESTION_CHARS) or clicked
    if not question:
        return
    examples_box.empty()

    with st.chat_message("user"):
        st.markdown(question)
    state.messages.append({"role": "user", "text": question})

    with st.chat_message("assistant"):
        if live and state.asked >= MAX_QUESTIONS_PER_SESSION:
            message = {"role": "assistant", "refused": True, "citations": [],
                       "text": f"This demo allows {MAX_QUESTIONS_PER_SESSION} questions per visit to stay within "
                               "its free API limit. Refresh the page later, or run it yourself with your own key."}
        else:
            try:
                with st.spinner("Searching the documents…"):
                    answer = engine.ask(question)
                message = answer_to_message(answer)
                if live:
                    state.asked += 1
                    counter.caption(f"Questions left this session: {max(0, MAX_QUESTIONS_PER_SESSION - state.asked)}")
            except Exception as error:  # noqa: BLE001
                text = ("The demo has hit its free API limit for now. Please try again in a few minutes."
                        if is_rate_limit(error) else
                        f"Something went wrong while answering ({type(error).__name__}). Please try again.")
                message = {"role": "assistant", "text": text, "refused": True, "citations": []}
        render_answer(message)
    state.messages.append(message)


main()
