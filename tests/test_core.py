"""Unit tests for loading, chunking, keyword search, fusion and prompting.

Run with:  pytest -q
No API key or network needed.
"""
from pathlib import Path

import pytest

from docanswer.bm25 import BM25Index, tokenize
from docanswer.chunking import fixed_chunks, make_chunks, sentence_chunks, split_sentences
from docanswer.hybrid import reciprocal_rank_fusion
from docanswer.loaders import load_bytes, load_folder
from docanswer.prompting import (
    REFUSAL,
    build_citations,
    cited_numbers,
    format_context,
    is_refusal,
    strip_invalid_citations,
)
from docanswer.types import Chunk, Page, ScoredChunk

SAMPLES = Path(__file__).resolve().parent.parent / "sample_docs"


# ----------------------------------------------------------------- loaders
def test_pdf_pages_keep_page_numbers():
    pages = [p for p in load_folder(SAMPLES) if p.source == "returns_and_refunds_policy.pdf"]
    assert [p.location for p in pages] == ["p. 1", "p. 2"]
    assert "30 days" in pages[0].text and "₹149" in pages[1].text


def test_docx_sections_and_tables_stay_in_place():
    pages = {p.location: p.text for p in load_folder(SAMPLES) if p.source == "faq.docx"}
    assert "Section: Gift wrapping" in pages
    assert "SNT-BD-114" in pages["Section: Product codes"]
    assert "SNT-BD-114" not in pages["Section: Gift wrapping"]


def test_markdown_split_on_headings():
    pages = load_bytes(b"Intro line.\n# Hours\nOpen 9 to 5.\n## Parking\nFree parking.", "notes.md")
    assert [p.location for p in pages] == ["Introduction", "Section: Hours", "Section: Parking"]


def test_unsupported_file_type():
    with pytest.raises(ValueError):
        load_bytes(b"x", "sheet.xlsx")


# ---------------------------------------------------------------- chunking
def test_split_sentences_handles_lines_and_periods():
    assert split_sentences("One. Two!\nThree") == ["One.", "Two!", "Three"]


def test_sentence_chunks_respect_size_and_overlap():
    text = " ".join(f"Sentence number {i} is here." for i in range(40))
    chunks = sentence_chunks([Page(text, "a.pdf", "p. 1")], max_chars=120, overlap_sentences=1)
    assert len(chunks) > 3
    assert all(len(c.text) <= 120 for c in chunks)
    # Overlap: each chunk starts with the last sentence of the previous one.
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.text.startswith(split_sentences(prev.text)[-1])


def test_chunks_never_cross_pages():
    pages = [Page("Alpha one. Alpha two.", "a.pdf", "p. 1"), Page("Beta one. Beta two.", "a.pdf", "p. 2")]
    for chunk in make_chunks(pages, "sentence", 1000, 1):
        assert ("Alpha" in chunk.text) != ("Beta" in chunk.text)


def test_fixed_chunks_cut_blindly():
    chunks = fixed_chunks([Page("x" * 250, "a.pdf", "p. 1")], size=100)
    assert [len(c.text) for c in chunks] == [100, 100, 50]


@pytest.mark.parametrize("bad", [dict(size=0), dict(size=10, overlap=10)])
def test_fixed_chunks_reject_bad_settings(bad):
    with pytest.raises(ValueError):
        fixed_chunks([Page("text", "a", "p. 1")], **bad)


# -------------------------------------------------------------------- bm25
def test_tokenize_keeps_codes_and_their_parts():
    tokens = tokenize("What size is SNT-BD-114?")
    assert "snt-bd-114" in tokens and "114" in tokens and "is" not in tokens


def test_bm25_finds_exact_product_code():
    docs = ["Gift wrapping costs 99 per item.", "SNT-BD-114 Indigo Dabu king bedsheet 108 x 108 inches.", "Shipping is free."]
    best, _ = BM25Index(docs).top("size of SNT-BD-114", k=1)[0]
    assert best == 1


def test_bm25_skips_zero_score_documents():
    assert BM25Index(["apples", "pears"]).top("bananas", k=5) == []


# ------------------------------------------------------------------ fusion
def test_rrf_rewards_items_ranked_well_by_both():
    fused = reciprocal_rank_fusion([[1, 2, 3], [3, 1, 4]])
    assert fused[0][0] == 1  # top-1 and top-2
    assert {i for i, _ in fused} == {1, 2, 3, 4}


def test_rrf_needs_one_weight_per_ranking():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[1], [2]], weights=[1.0])


# --------------------------------------------------------------- prompting
def _retrieved(n=3):
    return [ScoredChunk(Chunk(f"id{i}", f"Fact number {i}.", "doc.pdf", f"p. {i}"), 1.0) for i in range(1, n + 1)]


def test_cited_numbers_dedupes_and_drops_out_of_range():
    assert cited_numbers("A [2] B [2][1] C [9]", available=3) == [2, 1]


def test_strip_invalid_citations():
    assert strip_invalid_citations("Yes [1] and [7].", available=3) == "Yes [1] and ."


def test_build_citations_maps_numbers_to_sources():
    cites = build_citations("Thing [3].", _retrieved())
    assert len(cites) == 1 and cites[0].location == "p. 3" and cites[0].snippet == "Fact number 3."


def test_refusal_detection():
    assert is_refusal(REFUSAL)
    assert is_refusal("Sorry, I could not find that in the documents.")
    assert not is_refusal("Shipping is free above ₹1,999 [1].")


def test_context_is_numbered_with_locations():
    context = format_context(_retrieved(2))
    assert context.startswith("[1] (doc.pdf, p. 1)\nFact number 1.") and "[2] (doc.pdf, p. 2)" in context
