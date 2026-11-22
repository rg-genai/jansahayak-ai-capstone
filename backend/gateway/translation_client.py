"""Multilingual Language Detector & English-Pivot Translation Client.

Supports English (en), Hindi (hi), Hinglish (hinglish), Marathi (mr), Bengali (bn), Tamil (ta), Telugu (te).
Uses deterministic script detection + Qwen3-8B English pivot with ultra-clean, zero-echo prompts.
"""

from __future__ import annotations

import logging
import re

from backend.gateway.llm_client import LLMGateway, get_llm_gateway

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "hinglish": "Hindi",
    "mr": "Marathi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
}

# Unicode ranges for Indian scripts
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_BENGALI_RE = re.compile(r"[\u0980-\u09FF]")
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
_TELUGU_RE = re.compile(r"[\u0C00-\u0C7F]")

_MARATHI_HINTS = ("आहे", "नाही", "मला", "माझे", "काय", "कसे", "शेतकरी", "योजना", "मिळेल", "पात्र", "तक्रार", "साठी", "करावे", "तुम्ही")

_HINGLISH_WORDS = {
    "mera", "meri", "mere", "kya", "kaise", "karun", "karu", "kare", "nahi", "nhi",
    "paisa", "paise", "aaya", "aaye", "aayega", "milega", "milegi", "milta", "yojana",
    "shikayat", "darj", "kisan", "batao", "bataiye", "mujhe", "humko", "chahiye",
    "pichle", "mahine", "saal", "kaun", "kaunsi", "kiske", "liye", "hain", "hai",
    "hoga", "sakta", "sakti", "hoon", "hu", "aap", "tum", "kahan", "kab", "kitna",
    "kitne", "sarkari", "madad", "bima", "chhatravritti", "patr", "patrata",
}


def detect_language(text: str, ui_hint: str | None = None) -> str:
    """Detect user query language deterministically."""
    if not text or not text.strip():
        return normalize_lang_code(ui_hint or "en")

    if _BENGALI_RE.search(text):
        return "bn"
    if _TAMIL_RE.search(text):
        return "ta"
    if _TELUGU_RE.search(text):
        return "te"
    if _DEVANAGARI_RE.search(text):
        if ui_hint and normalize_lang_code(ui_hint) == "mr":
            return "mr"
        if any(w in text for w in _MARATHI_HINTS) and ("आहे" in text or "मला" in text or "साठी" in text or "नाही" in text):
            return "mr"
        return "hi"

    tokens = set(re.findall(r"[a-z]+", text.lower()))
    hinglish_hits = tokens & _HINGLISH_WORDS
    if len(hinglish_hits) >= 2:
        return "hinglish"

    if ui_hint:
        norm = normalize_lang_code(ui_hint)
        if norm != "en":
            return norm
    return "en"


def normalize_lang_code(lang: str | None) -> str:
    if not lang:
        return "en"
    low = lang.strip().lower()
    if low.startswith("hi"):
        return "hi"
    if low.startswith("mr"):
        return "mr"
    if low.startswith("bn"):
        return "bn"
    if low.startswith("ta"):
        return "ta"
    if low.startswith("te"):
        return "te"
    if low == "hinglish":
        return "hinglish"
    return "en"


def _clean_translation_output(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"</?(?:TEXT|TRANSLATION|SOURCE)[^>]*>", "", text, flags=re.IGNORECASE).strip()
    return text


class TranslationClient:
    """Translates Indic/Hinglish queries to English for bge-small-en-v1.5 retrieval, and localizes replies."""

    def __init__(self, llm: LLMGateway | None = None):
        self._llm = llm

    @property
    def llm(self) -> LLMGateway:
        if self._llm is None:
            self._llm = get_llm_gateway()
        return self._llm

    async def to_english(self, text: str, source_lang: str) -> tuple[str, int, int]:
        """Translate non-English query into faithful, concise English preserving all numbers, categories & scheme names."""
        lang = normalize_lang_code(source_lang)
        if lang == "en" or not text.strip():
            return text, 0, 0

        lang_label = SUPPORTED_LANGUAGES.get(lang, lang)
        messages = [
            {
                "role": "system",
                "content": (
                    f"Translate the user's {lang_label} text into faithful, natural English. "
                    "Preserve all scheme names (PM-KISAN, PM Vishwakarma, Ayushman Bharat, PMAY, Mudra), "
                    "social categories (SC, ST, OBC, EWS), degrees (B.Tech, M.Tech), rupee amounts, ages, "
                    "ticket IDs, and masked tags exactly. Reply with ONLY the English translation."
                ),
            },
            {"role": "user", "content": text},
        ]
        try:
            resp = await self.llm.chat_completion(
                messages=messages,
                max_tokens=220,
                temperature=0.0,
                disable_thinking=True,
            )
            translated = _clean_translation_output(resp.content).strip('"')
            return (translated or text), resp.prompt_tokens, resp.completion_tokens
        except Exception as exc:
            logger.warning("Translation to English failed (%s); using original text.", exc)
            return text, 0, 0

    async def from_english(self, text: str, target_lang: str) -> tuple[str, int, int]:
        """Translate final English assistant reply to user's language with a minimal zero-echo prompt."""
        lang = normalize_lang_code(target_lang)
        if lang == "en" or not text.strip():
            return text, 0, 0

        target_name = SUPPORTED_LANGUAGES.get(lang, "Hindi")
        # Keep system prompt ultra-short with NO numbered rules so Qwen3-8B NEVER echoes instructions into Indic output!
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator. Translate the user's English text into clear, polite {target_name}. "
                    "Keep [1], [2] citations, URLs, official English scheme names, rupee numbers, and ticket IDs unchanged. "
                    f"Output ONLY the {target_name} translation."
                ),
            },
            {"role": "user", "content": text},
        ]
        try:
            resp = await self.llm.chat_completion(
                messages=messages,
                max_tokens=1024,
                temperature=0.05,
                disable_thinking=True,
            )
            cleaned = _clean_translation_output(resp.content)
            return (cleaned or text), resp.prompt_tokens, resp.completion_tokens
        except Exception as exc:
            logger.warning("Localization to %s failed (%s); returning English.", lang, exc)
            return text, 0, 0
