"""Zero-Key Multilingual Indian Neural TTS Endpoint (/api/voice/tts).

Uses Microsoft Edge Neural Indian voices (`edge-tts`) for crystal-clear speech in:
  - English (India): en-IN-NeerjaNeural
  - Hindi:           hi-IN-SwaraNeural
  - Marathi:         mr-IN-AarohiNeural
  - Bengali:         bn-IN-TanishaaNeural
  - Tamil:           ta-IN-PallaviNeural
  - Telugu:          te-IN-ShrutiNeural
Automatically falls back to `gTTS` if Edge Neural TTS is unreachable, and caches MP3 audio in memory.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import re
from collections import OrderedDict

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from backend.gateway.translation_client import detect_language, normalize_lang_code

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice", tags=["Multilingual Voice TTS"])

EDGE_VOICE_MAP: dict[str, str] = {
    "en": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural",
    "hinglish": "hi-IN-SwaraNeural",
    "mr": "mr-IN-AarohiNeural",
    "bn": "bn-IN-TanishaaNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-ShrutiNeural",
}

GTTS_LANG_MAP: dict[str, str] = {
    "en": "en",
    "hi": "hi",
    "hinglish": "hi",
    "mr": "mr",
    "bn": "bn",
    "ta": "ta",
    "te": "te",
}

# Small LRU cache (up to 64 generated MP3 clips) so replay is instantaneous
_AUDIO_CACHE: OrderedDict[str, bytes] = OrderedDict()
_MAX_CACHE_ITEMS = 64


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=3500)
    language: str = Field(default="en")


def _clean_text_for_speech(text: str) -> str:
    s = text or ""
    # Replace markdown links [label](url) with just label
    s = re.sub(r"\[([^\]]+)\]\(https?:\/\/[^\s)]+\)", r"\1", s)
    # Remove raw URLs and inline citation markers [1], [2]
    s = re.sub(r"https?:\/\/\S+", "", s)
    s = re.sub(r"\[\d+\]", "", s)
    # Remove markdown symbols
    s = re.sub(r"[#*`>_~]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:1500]


async def _synth_edge_tts(text: str, lang_code: str) -> bytes:
    import edge_tts

    voice = EDGE_VOICE_MAP.get(lang_code, "en-IN-NeerjaNeural")
    comm = edge_tts.Communicate(text=text, voice=voice, rate="+0%")
    chunks: list[bytes] = []
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    audio = b"".join(chunks)
    if not audio:
        raise RuntimeError("edge-tts returned empty audio stream")
    return audio


def _synth_gtts_sync(text: str, lang_code: str) -> bytes:
    from gtts import gTTS

    g_lang = GTTS_LANG_MAP.get(lang_code, "en")
    tld = "co.in" if g_lang == "en" else "com"
    buf = io.BytesIO()
    tts = gTTS(text=text, lang=g_lang, tld=tld, slow=False)
    tts.write_to_fp(buf)
    audio = buf.getvalue()
    if not audio:
        raise RuntimeError("gTTS returned empty audio")
    return audio


@router.post("/tts")
async def synthesize_speech(req: TTSRequest) -> Response:
    cleaned = _clean_text_for_speech(req.text)
    if not cleaned:
        raise HTTPException(status_code=400, detail="No speakable text provided.")

    # Auto-detect script in the actual answer text (so a Marathi reply speaks Marathi even if UI dropdown says Hindi!)
    detected = detect_language(cleaned, ui_hint=req.language)
    lang_code = normalize_lang_code(detected or req.language)

    cache_key = hashlib.sha256(f"{lang_code}::{cleaned}".encode("utf-8")).hexdigest()
    if cache_key in _AUDIO_CACHE:
        _AUDIO_CACHE.move_to_end(cache_key)
        return Response(
            content=_AUDIO_CACHE[cache_key],
            media_type="audio/mpeg",
            headers={"X-TTS-Provider": "cache", "X-TTS-Lang": lang_code},
        )

    audio_bytes: bytes | None = None
    provider = "gtts"

    try:
        audio_bytes = await asyncio.wait_for(asyncio.to_thread(_synth_gtts_sync, cleaned, lang_code), timeout=18.0)
    except Exception as exc:
        logger.warning("gTTS failed for %s (%s); trying edge-tts fallback.", lang_code, exc)
        provider = "edge-tts"
        try:
            audio_bytes = await asyncio.wait_for(_synth_edge_tts(cleaned, lang_code), timeout=18.0)
        except Exception as exc2:
            logger.error("Both gTTS and edge-tts failed for %s: %s", lang_code, exc2)
            raise HTTPException(
                status_code=503,
                detail=f"Speech synthesis temporarily unavailable for {lang_code}.",
            ) from exc2

    _AUDIO_CACHE[cache_key] = audio_bytes
    if len(_AUDIO_CACHE) > _MAX_CACHE_ITEMS:
        _AUDIO_CACHE.popitem(last=False)

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"X-TTS-Provider": provider, "X-TTS-Lang": lang_code},
    )
