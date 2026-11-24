"""Suggested follow-up questions shown under an answer.

Built from templates, not by the LLM: no extra call, no added latency, and never a suggestion about a scheme the
answer did not mention. The UI decides when to show them (e.g. from the citizen's second message on).
"""

from __future__ import annotations

import re
from typing import Any

MAX_SUGGESTIONS = 3
_SUGGESTING_INTENTS = {"SCHEME_QA", "ELIGIBILITY_CHECK"}
_RULED_OUT_VERDICT = "NOT_ELIGIBLE"
_CORPUS_SOURCE = "myscheme_corpus"

# What the citizen already asked about, so we do not suggest the same thing back.
_ASKED_PATTERNS: dict[str, re.Pattern[str]] = {
    "eligibility": re.compile(r"eligib|qualif|who can|can i get", re.I),
    "documents": re.compile(r"document|certificate|papers|proof", re.I),
    "apply": re.compile(r"\bapply|application|register|enrol", re.I),
    "benefits": re.compile(r"benefit|amount|how much|money|stipend|subsid|assistance", re.I),
}
_TEMPLATES: list[tuple[str, str]] = [
    ("eligibility", "Am I eligible for {scheme}?"),
    ("documents", "What documents do I need for {scheme}?"),
    ("apply", "How do I apply for {scheme}?"),
    ("benefits", "What benefits does {scheme} give?"),
]
OTHER_SCHEMES_SUGGESTION = "Which other schemes am I eligible for?"


def _lead_scheme(eligibility_cards: list[dict[str, Any]], citations: list[dict[str, Any]]) -> str | None:
    """The scheme the answer is about: best eligibility verdict first, else the first cited catalog scheme."""
    for card in eligibility_cards:
        if card.get("verdict") != _RULED_OUT_VERDICT and card.get("scheme_name"):
            return str(card["scheme_name"])
    for cite in citations:
        if cite.get("source_type") == _CORPUS_SOURCE and cite.get("scheme_name"):
            return str(cite["scheme_name"])
    return None


def suggest_followups(query_en: str, intent: str | None, status: str | None,
                      eligibility_cards: list[dict[str, Any]], citations: list[dict[str, Any]]) -> list[str]:
    """Up to 3 next questions about the answer's lead scheme, skipping what the citizen just asked."""
    if status != "ok" or intent not in _SUGGESTING_INTENTS:
        return []
    scheme = _lead_scheme(eligibility_cards, citations)
    if not scheme:
        return []
    asked = {aspect for aspect, pattern in _ASKED_PATTERNS.items() if pattern.search(query_en or "")}
    suggestions = [template.format(scheme=scheme) for aspect, template in _TEMPLATES if aspect not in asked]
    suggestions.append(OTHER_SCHEMES_SUGGESTION)
    return suggestions[:MAX_SUGGESTIONS]
