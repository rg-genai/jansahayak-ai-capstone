"""Suggested follow-up questions (deterministic, no LLM)."""

from __future__ import annotations

from backend.agent.followups import OTHER_SCHEMES_SUGGESTION, suggest_followups

KISAN = [{"source_type": "myscheme_corpus", "scheme_name": "PM-KISAN"}]


def test_skips_the_aspect_just_asked_and_caps_at_three():
    out = suggest_followups("What documents are needed for PM-KISAN?", "SCHEME_QA", "ok", [], KISAN)
    assert out == ["Am I eligible for PM-KISAN?", "How do I apply for PM-KISAN?", "What benefits does PM-KISAN give?"]


def test_leads_with_best_eligible_scheme_not_a_ruled_out_one():
    cards = [{"scheme_name": "Ruled Out Scheme", "verdict": "NOT_ELIGIBLE"},
             {"scheme_name": "PM-USP", "verdict": "LIKELY_ELIGIBLE"}]
    out = suggest_followups("Which schemes am I eligible for?", "ELIGIBILITY_CHECK", "ok", cards, KISAN)
    assert out[0] == "What documents do I need for PM-USP?" and "Ruled Out" not in " ".join(out)


def test_everything_asked_falls_back_to_other_schemes():
    query = "Am I eligible, what documents, how to apply and how much money for PM-KISAN?"
    assert suggest_followups(query, "SCHEME_QA", "ok", [], KISAN) == [OTHER_SCHEMES_SUGGESTION]


def test_no_suggestions_without_a_finished_scheme_answer():
    assert suggest_followups("x", "SCHEME_QA", "awaiting_user_input", [], KISAN) == []
    assert suggest_followups("file a complaint", "GRIEVANCE", "ok", [], KISAN) == []
    web_only = [{"source_type": "web", "scheme_name": "Some portal"}]
    assert suggest_followups("x", "SCHEME_QA", "ok", [], web_only) == []


def test_localizes_followups_to_devanagari_hindi_and_marathi():
    hi = suggest_followups("What benefits does PM-KISAN give?", "SCHEME_QA", "ok", [], KISAN, language="hi")
    assert len(hi) == 3 and all("PM-KISAN" in q for q in hi)
    assert any("दस्तावेज़" in q for q in hi) and any("आवेदन" in q for q in hi)
    mr = suggest_followups("Am I eligible for PM-KISAN?", "SCHEME_QA", "ok", [], KISAN, language="mr")
    assert len(mr) == 3 and any("कागदपत्रे" in q for q in mr)

