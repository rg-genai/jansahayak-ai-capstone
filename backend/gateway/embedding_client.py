"""Hosted VM02 bge-small-en-v1.5 Embedding Client with batch<=16, TLS CA verify, retry backoff & SQLite cache."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import ssl
import time
from pathlib import Path
from typing import Sequence

import httpx
import numpy as np

from backend.config import get_settings
from backend.db.database import get_connection, init_db
from backend.db.repositories import now_ist_iso

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384
BACKOFF_SECONDS = (2.0, 4.0, 8.0)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _l2_normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (vecs / norms).astype(np.float32)


class EmbeddingClient:
    """Client for Track B hosted `bge-small-en-v1.5` embeddings endpoint."""

    def __init__(self, db_path: Path | None = None):
        self.settings = get_settings()
        self.base_url = self.settings.embedding_base_url.rstrip("/")
        self.model = self.settings.embedding_model
        self.api_key = self.settings.embedding_api_key.get_secret_value()
        self.ca_cert = self.settings.embedding_ca_cert_abs
        self.batch_size = min(self.settings.embedding_batch_size, 16)
        self.db_path = init_db(db_path)

        if not self.ca_cert.exists():
            raise FileNotFoundError(f"Embedding CA certificate not found: {self.ca_cert}")

    def _get_cached(self, hashes: Sequence[str]) -> dict[str, np.ndarray]:
        if not hashes:
            return {}
        found: dict[str, np.ndarray] = {}
        with get_connection(self.db_path) as conn:
            # Query in chunks of 500 to stay below SQLite parameter limits
            for i in range(0, len(hashes), 500):
                sub = hashes[i : i + 500]
                placeholders = ",".join("?" for _ in sub)
                rows = conn.execute(
                    f"SELECT text_hash, embedding_blob FROM embedding_cache WHERE text_hash IN ({placeholders})",
                    sub,
                ).fetchall()
                for r in rows:
                    vec = np.frombuffer(r["embedding_blob"], dtype=np.float32)
                    if vec.shape == (EMBEDDING_DIM,):
                        found[r["text_hash"]] = vec.copy()
        return found

    def _put_cached(self, items: list[tuple[str, np.ndarray]]) -> None:
        if not items:
            return
        ts = now_ist_iso()
        with get_connection(self.db_path) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO embedding_cache(text_hash, embedding_blob, created_at) VALUES (?, ?, ?)",
                [(h, vec.astype(np.float32).tobytes(), ts) for h, vec in items],
            )

    def _request_batch_sync(self, client: httpx.Client, texts: list[str]) -> np.ndarray:
        url = f"{self.base_url}/embeddings"
        payload = {"model": self.model, "input": texts}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_err: Exception | None = None
        for attempt in range(len(BACKOFF_SECONDS) + 1):
            try:
                resp = client.post(url, json=payload, headers=headers, timeout=60.0)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    data.sort(key=lambda x: x.get("index", 0))
                    vecs = np.asarray([d["embedding"] for d in data], dtype=np.float32)
                    if vecs.shape != (len(texts), EMBEDDING_DIM):
                        raise ValueError(f"Unexpected embedding shape {vecs.shape}, expected ({len(texts)}, {EMBEDDING_DIM})")
                    return _l2_normalize(vecs)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < len(BACKOFF_SECONDS):
                    wait = BACKOFF_SECONDS[attempt]
                    logger.warning("Embedding API HTTP %s; retrying in %.1fs...", resp.status_code, wait)
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Embedding API HTTP {resp.status_code}: {resp.text[:300]}")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_err = exc
                if attempt < len(BACKOFF_SECONDS):
                    wait = BACKOFF_SECONDS[attempt]
                    logger.warning("Embedding transport error (%s); retrying in %.1fs...", exc, wait)
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Embedding API transport failure: {exc}") from exc
        raise RuntimeError(f"Embedding API failed after retries: {last_err}")

    def embed_texts_sync(
        self,
        texts: Sequence[str],
        use_cache: bool = True,
        progress_every: int = 0,
    ) -> np.ndarray:
        """Embed a sequence of texts synchronously with SQLite cache + batching (<=16)."""
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

        hashes = [_text_hash(t) for t in texts]
        cached = self._get_cached(hashes) if use_cache else {}

        # Deduplicate uncached texts while preserving order
        missing_indices: list[int] = []
        unique_missing_texts: list[str] = []
        unique_missing_hashes: list[str] = []
        seen_missing: set[str] = set()

        for idx, (t, h) in enumerate(zip(texts, hashes)):
            if h not in cached:
                missing_indices.append(idx)
                if h not in seen_missing:
                    seen_missing.add(h)
                    unique_missing_texts.append(t)
                    unique_missing_hashes.append(h)

        if unique_missing_texts:
            total_batches = (len(unique_missing_texts) + self.batch_size - 1) // self.batch_size
            ssl_ctx = ssl.create_default_context(cafile=str(self.ca_cert))
            with httpx.Client(verify=ssl_ctx) as client:
                for b_idx in range(0, len(unique_missing_texts), self.batch_size):
                    batch_texts = unique_missing_texts[b_idx : b_idx + self.batch_size]
                    batch_hashes = unique_missing_hashes[b_idx : b_idx + self.batch_size]
                    vecs = self._request_batch_sync(client, batch_texts)
                    to_store: list[tuple[str, np.ndarray]] = []
                    for h, v in zip(batch_hashes, vecs):
                        cached[h] = v
                        to_store.append((h, v))
                    if use_cache:
                        self._put_cached(to_store)
                    batch_num = (b_idx // self.batch_size) + 1
                    if progress_every and (batch_num % progress_every == 0 or batch_num == total_batches):
                        logger.info(
                            "Embedded batch %d/%d (%d/%d unique chunks)",
                            batch_num,
                            total_batches,
                            min(b_idx + self.batch_size, len(unique_missing_texts)),
                            len(unique_missing_texts),
                        )

        result = np.vstack([cached[h] for h in hashes]).astype(np.float32)
        return _l2_normalize(result)

    async def embed_texts(self, texts: Sequence[str], use_cache: bool = True) -> np.ndarray:
        """Async wrapper (runs sync httpx batch in worker thread to avoid blocking event loop)."""
        return await asyncio.to_thread(self.embed_texts_sync, list(texts), use_cache, 0)

    async def embed_query(self, query: str) -> np.ndarray:
        vecs = await self.embed_texts([query], use_cache=True)
        return vecs[0]


_SINGLETON_EMBEDDING_CLIENT: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    global _SINGLETON_EMBEDDING_CLIENT
    if _SINGLETON_EMBEDDING_CLIENT is None:
        _SINGLETON_EMBEDDING_CLIENT = EmbeddingClient()
    return _SINGLETON_EMBEDDING_CLIENT
