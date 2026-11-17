"""End-to-end tests of the engine with offline models (no network)."""
from pathlib import Path

import pytest

from docanswer.engine import BASELINE, OPTIMIZED, RagConfig, RagEngine
from docanswer.evaluation import evaluate, load_questions, normalise, summarise
from docanswer.loaders import load_folder
from docanswer.prompting import REFUSAL
from docanswer.providers import (
    OfflineAnswerModel,
    OfflineEmbedder,
    _message_text,
    make_providers,
    with_backoff,
)
from docanswer.vector_index import EmbeddingCache, VectorIndex

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pages():
    return load_folder(ROOT / "sample_docs")


def engine_for(pages, config=OPTIMIZED, model=None):
    return RagEngine(OfflineEmbedder(), model or OfflineAnswerModel(), config,
                     business="Saffron & Thread", cache_path=None).build(pages)


class ScriptedModel:
    """Returns a fixed reply, to test how the engine treats model output."""

    name = "scripted"

    def __init__(self, reply):
        self.reply = reply

    def answer(self, business, context, question):
        return self.reply


def test_answers_with_a_citation(pages):
    answer = engine_for(pages).ask("What is the COD handling fee?")
    assert not answer.refused
    assert "49" in answer.text
    assert answer.citations and answer.citations[0].source == "shipping_and_delivery.pdf"


def test_refuses_when_documents_do_not_cover_it(pages):
    answer = engine_for(pages).ask("Do you sell wooden furniture?")
    assert answer.refused and answer.text == REFUSAL


def test_uncited_answer_is_not_shown(pages):
    answer = engine_for(pages, model=ScriptedModel("Yes, absolutely, next-day delivery everywhere!")).ask("Next-day delivery?")
    assert answer.refused and answer.text == REFUSAL


def test_hallucinated_source_numbers_are_removed(pages):
    answer = engine_for(pages, model=ScriptedModel("Free above ₹1,999 [1][9].")).ask("free shipping minimum")
    assert answer.text == "Free above ₹1,999 [1]." and [c.number for c in answer.citations] == [1]


def test_partial_answer_with_citation_is_kept(pages):
    reply = "Express costs ₹249 [1]. I couldn't find that in the documents for Sunday delivery."
    answer = engine_for(pages, model=ScriptedModel(reply)).ask("Express price and Sunday delivery?")
    assert not answer.refused and answer.citations


def test_empty_question(pages):
    assert engine_for(pages).ask("   ").refused


@pytest.mark.parametrize("mode", ["dense", "bm25", "hybrid"])
def test_every_retrieval_mode_returns_top_k(pages, mode):
    engine = engine_for(pages, RagConfig(retrieval=mode, top_k=3))
    assert len(engine.retrieve("return window for full-price items")) == 3


def test_hybrid_finds_product_code(pages):
    top = engine_for(pages).retrieve("What size is SNT-BD-114?")[0].chunk
    assert top.location == "Section: Product codes"


def test_evaluation_runs_and_summarises(pages):
    questions = load_questions(ROOT / "eval" / "questions.jsonl")
    rows = evaluate(engine_for(pages), questions)
    summary = summarise(rows)
    assert summary["questions"] == 30
    assert set(summary) >= {"retrieval_hit_rate", "mrr", "answer_accuracy", "refused_when_should"}
    # Even word-overlap embeddings should beat the naive baseline on retrieval.
    baseline = summarise(evaluate(engine_for(pages, BASELINE), questions, answer=False))
    assert summary["retrieval_hit_rate"] >= baseline["retrieval_hit_rate"]


def test_normalise_for_scoring():
    assert normalise("₹1,999 – 5–9 Business  Days") == "1999 - 5-9 business days"


# ------------------------------------------------------------ caching
class CountingEmbedder(OfflineEmbedder):
    def __init__(self):
        super().__init__()
        self.document_calls = 0

    def embed_documents(self, texts):
        self.document_calls += len(texts)
        return super().embed_documents(texts)


def test_embedding_cache_avoids_repeat_calls(tmp_path):
    embedder = CountingEmbedder()
    cache_file = tmp_path / "emb.json"
    VectorIndex(embedder, EmbeddingCache(cache_file)).build(["a b c", "d e f"])
    VectorIndex(embedder, EmbeddingCache(cache_file)).build(["a b c", "d e f", "g h i"])
    assert embedder.document_calls == 3  # 2 first time, only the new one second time
    assert cache_file.exists()


# ---------------------------------------------------------- providers
class FakeMessage:
    def __init__(self, text=None, content=""):
        if text is not None:
            self.text = text
        self.content = content


def test_message_text_handles_all_shapes():
    assert _message_text(FakeMessage(text="hi")) == "hi"
    assert _message_text(FakeMessage(text=lambda: "hey")) == "hey"
    assert _message_text(FakeMessage(content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])) == "ab"
    assert _message_text(FakeMessage(content="plain")) == "plain"


def test_backoff_retries_rate_limits_only(monkeypatch):
    monkeypatch.setattr("docanswer.providers.time.sleep", lambda s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return "ok"

    assert with_backoff(flaky) == "ok" and calls["n"] == 3
    with pytest.raises(ValueError):
        with_backoff(lambda: (_ for _ in ()).throw(ValueError("bad request")))


def test_no_key_means_offline(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _, model, live = make_providers()
    assert live is False and model.name == "offline-extractive"


def test_cache_survives_read_only_disk(tmp_path):
    blocked = tmp_path / "file-not-dir"
    blocked.write_text("x")  # a file where a folder is needed -> write fails
    cache = EmbeddingCache(blocked / "emb.json")
    VectorIndex(OfflineEmbedder(), cache).build(["a b c"])
    assert cache.path is None and len(cache._data) == 1
