"""Chunking experiments: strategies, no lost text, the evidence-hit measure, and the in-memory index (no API)."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from rank_bm25 import BM25Okapi

from backend.retrieval.chunker import FAQ_SECTION, HARD_TOKEN_LIMIT, chunk_scheme, scheme_sections
from backend.retrieval.etl import EnrichedScheme
from backend.retrieval.hybrid_retriever import HybridRetriever
from eval.run_chunking_eval import (
    BASELINE,
    EMBED_MODEL_MAX_TOKENS,
    FIXED_WINDOW_SECTION,
    STRATEGIES,
    chunk_record,
    chunk_with_strategy,
    evidence_coverage,
    fit_to_model_limit,
)
from scripts.ingest_data import build_bm25_doc_tokens

_SENTENCE = "Applicants must be small and marginal farmers who own cultivable land in their own name."


def _scheme(slug: str = "demo", eligibility_sentences: int = 60) -> EnrichedScheme:
    return EnrichedScheme(
        slug=slug, scheme_name=f"Demo Scheme {slug}", short_title="", level="Central", state="", ministry="Ministry X",
        ministry_code="MOX", department="", categories="Agriculture", sub_categories="", tags="farmer;income",
        benefit_type="Cash", dbt_scheme=True, application_mode="Online", age_min=None, age_max=None,
        income_cap_inr=None, social_categories=[], beneficiary_groups=["Farmer"],
        brief_description="Income support for farmers.", detailed_description="", benefits="Rs 6000 per year.",
        eligibility=" ".join(f"{_SENTENCE} Rule {i}." for i in range(eligibility_sentences)), exclusions="",
        application_process="Apply on the portal.", documents_required="Aadhaar card.", references_text="",
        source_url=f"https://example.gov.in/{slug}", faq_count=1,
        faqs=[{"faq_number": 1, "question": "Who can apply?", "answer": "Farmers."}],
    )


def _words(texts: list[str]) -> set[str]:
    return {w.strip(".,").lower() for t in texts for w in t.split()}


def test_baseline_strategy_is_exactly_the_production_chunker():
    scheme = _scheme()
    assert [(c.chunk_id, c.text) for c in chunk_with_strategy(scheme, BASELINE)] == \
        [(c.chunk_id, c.text) for c in chunk_scheme(scheme)]


def test_smaller_chunks_make_more_chunks_without_losing_text():
    scheme = _scheme()
    body_words = _words([s.body for s in scheme_sections(scheme)])
    counts = {}
    for name, strategy in STRATEGIES.items():
        chunks = [c for c in chunk_with_strategy(scheme, strategy) if c.section != FAQ_SECTION]
        assert body_words <= _words([c.text for c in chunks]), f"{name} dropped text"
        assert all(c.token_count <= HARD_TOKEN_LIMIT for c in chunks), f"{name} exceeds the embedding limit"
        counts[name] = len(chunks)
    assert counts["section_128_ov10"] > counts["section_256_ov20"] > counts["section_440_ov35"]


def test_fixed_windows_ignore_sections_but_keep_faq_chunks_unchanged():
    scheme = _scheme()
    fixed = chunk_with_strategy(scheme, STRATEGIES["fixed_440_ov35"])
    assert {c.section for c in fixed} == {FIXED_WINDOW_SECTION, FAQ_SECTION}
    assert [c.text for c in fixed if c.section == FAQ_SECTION] == \
        [c.text for c in chunk_scheme(scheme) if c.section == FAQ_SECTION]


def test_chunks_over_the_model_limit_are_split_keeping_header_and_every_word():
    """Regression: the no-overlap strategy produced a chunk the estimator put under 440 but the embedding server
    counted at 526 tokens (> 512) and rejected."""
    chunk = chunk_scheme(_scheme(eligibility_sentences=2))[0]
    header = chunk.text.split("\n", 1)[0]
    long_chunk = replace(chunk, text=f"{header}\n" + " ".join(f"word{i}" for i in range(1200)))
    word_count = lambda texts: [len(t.split()) for t in texts]  # stand-in for the exact tokenizer
    parts = fit_to_model_limit([chunk, long_chunk], word_count)
    assert parts[0] is chunk, "chunks within the limit are untouched"
    split = parts[1:]
    assert len(split) == 4 and all(len(p.text.split()) <= EMBED_MODEL_MAX_TOKENS for p in split)
    assert all(p.text.startswith(header + "\n") for p in split)
    body_words = [w for p in split for w in p.text.split("\n", 1)[1].split()]
    assert body_words == [f"word{i}" for i in range(1200)], "no word lost or reordered"
    assert len({p.chunk_id for p in split}) == 4


def test_evidence_coverage_measures_the_contiguous_share_of_the_quote():
    assert evidence_coverage("Rs 6000 per year", "[Scheme] Benefits: Rs 6000 per year, paid in installments.") == 1.0
    assert evidence_coverage("Rs 6000 per year in three installments", "Rs 6000 per year.") == pytest.approx(4 / 7)
    assert evidence_coverage("", "anything") == 0.0


def test_in_memory_index_searches_without_touching_disk_and_checks_alignment():
    chunks = [c for slug in ("alpha", "beta") for c in chunk_scheme(_scheme(slug, eligibility_sentences=2))]
    records = [chunk_record(c, i) for i, c in enumerate(chunks)]
    bm25 = BM25Okapi([build_bm25_doc_tokens(c) for c in chunks])
    retriever = HybridRetriever(embedding_client=object(), exclude_faq_chunks=True, index_dir=None)
    retriever.load_from_memory(records, np.zeros((len(records), 384), dtype=np.float32), bm25)
    out = retriever.search_sync("Demo Scheme beta farmers", top_k=3, mode="bm25")
    assert out.results[0].scheme_slug == "beta"
    assert all(r.section != FAQ_SECTION for r in out.results), "FAQ exclusion still applies"
    with pytest.raises(RuntimeError):
        HybridRetriever(embedding_client=object()).load_from_memory(records, np.zeros((1, 384)), bm25)
