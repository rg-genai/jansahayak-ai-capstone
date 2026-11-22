"""Two-Tier SQLite Response Cache (Tier 1 Exact Hash + Tier 2 Semantic Similarity >= 0.96)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from backend.config import get_settings
from backend.db.database import get_connection, init_db
from backend.db.repositories import IST, now_ist_iso
from backend.gateway.embedding_client import EMBEDDING_DIM


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip().lower())


def hash_profile(profile: dict[str, Any] | None) -> str:
    cleaned = {k: v for k, v in (profile or {}).items() if v is not None and v != ""}
    raw = json.dumps(cleaned, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_cache_key(query_en: str, lang: str, profile_hash: str) -> str:
    raw = f"{normalize_query(query_en)}||{lang.lower()}||{profile_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TwoTierResponseCache:
    """Exact + Semantic response cache for read-only scheme Q&A turns."""

    def __init__(self, db_path: Path | None = None, ttl_hours: int = 24):
        self.settings = get_settings()
        self.db_path = init_db(db_path)
        self.ttl_hours = ttl_hours
        self.semantic_threshold = self.settings.semantic_cache_threshold

    def lookup(
        self,
        query_en: str,
        lang: str,
        profile: dict[str, Any] | None,
        query_embedding: np.ndarray | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """Return (cached_response, hit_type) where hit_type in {'exact', 'semantic', 'miss'}."""
        now_iso = now_ist_iso()
        p_hash = hash_profile(profile)
        key = make_cache_key(query_en, lang, p_hash)

        with get_connection(self.db_path) as conn:
            # Tier 1: Exact normalized match
            row = conn.execute(
                "SELECT response_json, expires_at FROM response_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row and row["expires_at"] > now_iso:
                return json.loads(row["response_json"]), "exact"

            # Tier 2: Semantic similarity match (>= 0.96) for same lang & profile_hash
            if query_embedding is not None and query_embedding.shape == (EMBEDDING_DIM,):
                rows = conn.execute(
                    """
                    SELECT embedding_blob, response_json
                    FROM response_cache
                    WHERE lang = ? AND profile_hash = ? AND expires_at > ? AND embedding_blob IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 200
                    """,
                    (lang.lower(), p_hash, now_iso),
                ).fetchall()
                if rows:
                    q_vec = query_embedding.astype(np.float32)
                    q_norm = np.linalg.norm(q_vec)
                    if q_norm > 0:
                        q_vec = q_vec / q_norm
                    best_sim = -1.0
                    best_resp = None
                    for r in rows:
                        vec = np.frombuffer(r["embedding_blob"], dtype=np.float32)
                        if vec.shape != (EMBEDDING_DIM,):
                            continue
                        sim = float(np.dot(q_vec, vec))
                        if sim > best_sim:
                            best_sim = sim
                            best_resp = r["response_json"]
                    if best_resp is not None and best_sim >= self.semantic_threshold:
                        return json.loads(best_resp), "semantic"

        return None, "miss"

    def store(
        self,
        query_en: str,
        lang: str,
        profile: dict[str, Any] | None,
        response_payload: dict[str, Any],
        query_embedding: np.ndarray | None = None,
    ) -> None:
        now = datetime.now(IST)
        expires = now + timedelta(hours=self.ttl_hours)
        p_hash = hash_profile(profile)
        key = make_cache_key(query_en, lang, p_hash)

        emb_blob: bytes | None = None
        if query_embedding is not None and query_embedding.shape == (EMBEDDING_DIM,):
            v = query_embedding.astype(np.float32)
            n = np.linalg.norm(v)
            if n > 0:
                v = v / n
            emb_blob = v.tobytes()

        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO response_cache(
                    cache_key, query_en, lang, profile_hash, embedding_blob,
                    response_json, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    normalize_query(query_en),
                    lang.lower(),
                    p_hash,
                    emb_blob,
                    json.dumps(response_payload, ensure_ascii=False),
                    now.isoformat(timespec="seconds"),
                    expires.isoformat(timespec="seconds"),
                ),
            )
