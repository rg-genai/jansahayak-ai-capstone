"""Milestone M2 tests: Hybrid Retrieval (BM25 + Dense + RRF + Cross-Encoder Reranker) & Language Detection."""

from __future__ import annotations

import pytest

from backend.gateway.llm_client import LLMGateway, count_messages_tokens, strip_thinking
from backend.gateway.translation_client import detect_language
from backend.retrieval.hybrid_retriever import get_hybrid_retriever
from backend.retrieval.web_search import is_allowed_gov_url


def test_flagship_schemes_hit_top_3():
    retriever = get_hybrid_retriever()
    queries = [
        ("Pradhan Mantri Kisan Samman Nidhi PM-KISAN farmer Rs 6000 annual income support", "kisan"),
        ("Ayushman Bharat Pradhan Mantri Jan Arogya Yojana health insurance 5 lakh", "ayushman"),
        ("Pradhan Mantri Awas Yojana urban housing subsidy", "awas"),
        ("Pradhan Mantri Mudra Yojana collateral free loan Shishu Kishore Tarun", "mudra"),
        ("PM Vishwakarma traditional artisans carpenter blacksmith toolkit loan", "vishwakarma"),
    ]
    for query, keyword in queries:
        out = retriever.search_sync(query, top_k=5, mode="hybrid_rerank")
        assert len(out.results) >= 3
        top3_names = " | ".join(r.scheme_name.lower() + " " + r.scheme_slug.lower() for r in out.results[:3])
        assert keyword in top3_names, f"Expected '{keyword}' in Top-3 for '{query}', got: {top3_names}"
        # Verify all 4 score dimensions populated
        assert out.results[0].rerank_score > 0.0
        assert out.results[0].source_url.startswith("https://")


def test_retrieval_modes_all_work():
    retriever = get_hybrid_retriever()
    q = "PM-KISAN eligibility for farmers"
    for mode in ("bm25", "dense", "hybrid_rrf", "hybrid_rerank"):
        out = retriever.search_sync(q, top_k=5, mode=mode)
        assert len(out.results) == 5
        assert out.latency_ms >= 0


def test_permissive_metadata_filter():
    retriever = get_hybrid_retriever()
    out = retriever.search_sync(
        "scholarship for OBC college student",
        top_k=5,
        mode="hybrid_rerank",
        filters={"social_category": "OBC", "age": 19, "annual_income_inr": 180000},
    )
    assert len(out.results) >= 3
    assert out.filter_applied is True


def test_language_detection_and_web_allowlist():
    assert detect_language("What are the benefits of PM-KISAN?") == "en"
    assert detect_language("Mera PM-KISAN ka pichle 6 mahine se paisa nahi aaya, kya karun?") == "hinglish"
    assert detect_language("पीएम किसान योजना की पात्रता क्या है?") == "hi"
    assert detect_language("मला शेतकरी योजना साठी काय कागदपत्रे लागतील?") == "mr"
    assert detect_language("প্রধানমন্ত্রী কিষাণ সম্মান নিধি প্রকল্পের সুবিধা কী?") == "bn"
    assert detect_language("விவசாயிகளுக்கான மத்திய அரசு திட்டம் என்ன?") == "ta"
    assert detect_language("రైతులకు కేంద్ర ప్రభుత్వ పథకం వివరాలు చెప్పండి") == "te"

    assert is_allowed_gov_url("https://www.myscheme.gov.in/schemes/pm-kisan") is True
    assert is_allowed_gov_url("https://pgportal.gov.in/") is True
    assert is_allowed_gov_url("https://pmkisan.nic.in/status") is True
    assert is_allowed_gov_url("https://fake-gov-in.com/scam") is False


def test_llm_gateway_budget_and_think_stripper():
    gw = LLMGateway()
    long_text = "word " * 12000
    msgs, max_out = gw.enforce_context_budget(
        [
            {"role": "system", "content": "You are JanSahayak AI."},
            {"role": "user", "content": "old turn 1"},
            {"role": "assistant", "content": "old reply 1"},
            {"role": "user", "content": long_text},
        ],
        max_tokens=2048,
    )
    assert max_out == 1024
    assert count_messages_tokens(msgs) + max_out <= 8192

    stripped = strip_thinking("<think>Internal reasoning here...</think>\n{\"status\": \"ok\"}")
    assert stripped == '{"status": "ok"}'
