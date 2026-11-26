"""Suggested follow-up questions shown under an answer.

Built from localized templates, not by the LLM: zero extra calls, zero added latency,
matches the citizen's language/script (EN, HI, Hinglish, MR, BN, TA, TE), and never
suggests a scheme the answer did not mention.
"""

from __future__ import annotations

import re
from typing import Any

MAX_SUGGESTIONS = 3
_SUGGESTING_INTENTS = {"SCHEME_QA", "ELIGIBILITY_CHECK"}
_RULED_OUT_VERDICT = "NOT_ELIGIBLE"
_CORPUS_SOURCE = "myscheme_corpus"

# What the citizen already asked about (checked on English pivot query), so we do not suggest the same thing back.
_ASKED_PATTERNS: dict[str, re.Pattern[str]] = {
    "eligibility": re.compile(r"eligib|qualif|who can|can i get", re.I),
    "documents": re.compile(r"document|certificate|papers|proof", re.I),
    "apply": re.compile(r"\bapply|application|register|enrol", re.I),
    "benefits": re.compile(r"benefit|amount|how much|money|stipend|subsid|assistance", re.I),
}

_TEMPLATES_BY_LANG: dict[str, list[tuple[str, str]]] = {
    "en": [
        ("eligibility", "Am I eligible for {scheme}?"),
        ("documents", "What documents do I need for {scheme}?"),
        ("apply", "How do I apply for {scheme}?"),
        ("benefits", "What benefits does {scheme} give?"),
    ],
    "hi": [
        ("eligibility", "क्या मैं {scheme} के लिए पात्र हूँ?"),
        ("documents", "{scheme} के लिए कौन-कौन से दस्तावेज़ चाहिए?"),
        ("apply", "{scheme} के लिए आवेदन कैसे करें?"),
        ("benefits", "{scheme} के अंतर्गत क्या लाभ मिलते हैं?"),
    ],
    "hinglish": [
        ("eligibility", "Kya main {scheme} ke liye eligible hoon?"),
        ("documents", "{scheme} ke liye kaun-kaun se documents chahiye?"),
        ("apply", "{scheme} ke liye online apply kaise karein?"),
        ("benefits", "{scheme} mein kya benefits milte hain?"),
    ],
    "mr": [
        ("eligibility", "मी {scheme} साठी पात्र आहे का?"),
        ("documents", "{scheme} साठी कोणती कागदपत्रे लागतात?"),
        ("apply", "{scheme} साठी अर्ज कसा करावा?"),
        ("benefits", "{scheme} चे कोणते लाभ मिळतात?"),
    ],
    "bn": [
        ("eligibility", "আমি কি {scheme}-এর জন্য যোগ্য?"),
        ("documents", "{scheme}-এর জন্য কী কী নথি প্রয়োজন?"),
        ("apply", "{scheme}-এর জন্য কীভাবে আবেদন করব?"),
        ("benefits", "{scheme}-এ কী কী সুবিধা পাওয়া যায়?"),
    ],
    "ta": [
        ("eligibility", "{scheme} திட்டத்திற்கு நான் தகுதியுடையவனா?"),
        ("documents", "{scheme} திட்டத்திற்கு என்ன ஆவணங்கள் தேவை?"),
        ("apply", "{scheme} திட்டத்திற்கு எவ்வாறு விண்ணப்பிப்பது?"),
        ("benefits", "{scheme} திட்டத்தின் நன்மைகள் என்ன?"),
    ],
    "te": [
        ("eligibility", "{scheme} పథకానికి నేను అర్హుడినా?"),
        ("documents", "{scheme} పథకానికి ఏ పత్రాలు అవసరం?"),
        ("apply", "{scheme} పథకానికి ఎలా దరఖాస్తు చేయాలి?"),
        ("benefits", "{scheme} పథకం ద్వారా ఏ ప్రయోజనాలు లభిస్తాయి?"),
    ],
}

OTHER_SCHEMES_SUGGESTION = "Which other schemes am I eligible for?"

_OTHER_SCHEMES_BY_LANG: dict[str, str] = {
    "en": OTHER_SCHEMES_SUGGESTION,
    "hi": "मैं और किन केंद्रीय सरकारी योजनाओं के लिए पात्र हूँ?",
    "hinglish": "Main aur kin sarkari yojanaon ke liye eligible hoon?",
    "mr": "मी इतर कोणत्या सरकारी योजनांसाठी पात्र आहे?",
    "bn": "আমি আর কোন সরকারি প্রকল্পের জন্য যোগ্য?",
    "ta": "நான் வேறு எந்த அரசுத் திட்டங்களுக்குத் தகுதியுடையவன்?",
    "te": "నేను ఇతర ఏ ప్రభుత్వ పథకాలకు అర్హుడిని?",
}


def _lead_scheme(eligibility_cards: list[dict[str, Any]], citations: list[dict[str, Any]]) -> str | None:
    """The scheme the answer is about: best eligibility verdict first, else the first cited catalog scheme."""
    for card in eligibility_cards:
        if card.get("verdict") != _RULED_OUT_VERDICT and card.get("scheme_name"):
            return str(card["scheme_name"])
    for cite in citations:
        if cite.get("source_type") == _CORPUS_SOURCE and cite.get("scheme_name"):
            return str(cite["scheme_name"])
    return None


def suggest_followups(
    query_en: str,
    intent: str | None,
    status: str | None,
    eligibility_cards: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    language: str = "en",
) -> list[str]:
    """Up to 3 localized next questions about the answer's lead scheme, skipping what the citizen just asked."""
    if status != "ok" or intent not in _SUGGESTING_INTENTS:
        return []
    scheme = _lead_scheme(eligibility_cards, citations)
    if not scheme:
        return []
    lang_key = (language or "en").lower()
    templates = _TEMPLATES_BY_LANG.get(lang_key, _TEMPLATES_BY_LANG["en"])
    other_q = _OTHER_SCHEMES_BY_LANG.get(lang_key, OTHER_SCHEMES_SUGGESTION)
    asked = {aspect for aspect, pattern in _ASKED_PATTERNS.items() if pattern.search(query_en or "")}
    suggestions = [template.format(scheme=scheme) for aspect, template in templates if aspect not in asked]
    suggestions.append(other_q)
    return suggestions[:MAX_SUGGESTIONS]
