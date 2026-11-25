"""Hybrid Retriever: BM25 + Dense (bge-small-en-v1.5) + RRF + Local Cross-Encoder Reranker + Permissive Metadata Filters."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import pickle
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np

from backend.config import get_settings
from backend.db.database import get_connection
from backend.gateway.embedding_client import EmbeddingClient, get_embedding_client
from backend.retrieval.chunker import FAQ_SECTION

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[a-z0-9]+")
RetrievalMode = Literal["bm25", "dense", "hybrid_rrf", "hybrid_rerank"]


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass
class RetrievedChunk:
    chunk_id: str
    citation_id: str
    scheme_slug: str
    scheme_name: str
    ministry: str
    section: str
    text: str
    source_url: str
    faq_numbers: list[int] = field(default_factory=list)
    bm25_score: float = 0.0
    dense_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    rerank_logit: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "citation_id": self.citation_id,
            "scheme_slug": self.scheme_slug,
            "scheme_name": self.scheme_name,
            "ministry": self.ministry,
            "section": self.section,
            "faq_numbers": self.faq_numbers,
            "text": self.text,
            "source_url": self.source_url,
            "scores": {
                "bm25": round(self.bm25_score, 4),
                "dense": round(self.dense_score, 4),
                "rrf": round(self.rrf_score, 6),
                "rerank": round(self.rerank_score, 4),
            },
        }


@dataclass
class RetrievalOutput:
    results: list[RetrievedChunk]
    mode: RetrievalMode
    top_rerank_score: float
    low_confidence: bool
    latency_ms: float
    filter_applied: bool = False
    filter_relaxed: bool = False
    query_embedding: np.ndarray | None = None


class HybridRetriever:
    """In-memory NumPy + BM25 + SQLite metadata + local Cross-Encoder retriever."""

    def __init__(
        self,
        db_path: Path | None = None,
        index_dir: Path | None = None,
        embedding_client: EmbeddingClient | None = None,
        load_reranker: bool = True,
        exclude_faq_chunks: bool | None = None,
    ):
        self.settings = get_settings()
        self.db_path = db_path or self.settings.db_abs_path
        self.index_dir = index_dir or self.settings.index_abs_dir
        self._embedding_client = embedding_client
        self._load_reranker_enabled = load_reranker
        self._reranker = None
        # FAQ chunks stay in the index but are never returned (evaluation: the gold set must not be answered by FAQs).
        # BM25 term statistics still include FAQ text; only which chunks can come back changes.
        self.exclude_faq_chunks = (
            self.settings.retrieval_exclude_faq_chunks if exclude_faq_chunks is None else exclude_faq_chunks
        )

        self.chunks: list[dict[str, Any]] = []
        self._searchable_idx: np.ndarray = np.zeros(0, dtype=np.int32)
        self.embeddings: np.ndarray = np.zeros((0, 384), dtype=np.float32)
        self.bm25 = None
        self._loaded = False

    @property
    def embedding_client(self) -> EmbeddingClient:
        if self._embedding_client is None:
            self._embedding_client = get_embedding_client()
        return self._embedding_client

    def load(self) -> None:
        if self._loaded:
            return
        emb_path = self.index_dir / "embeddings.npy"
        bm25_path = self.index_dir / "bm25.pkl"
        if not emb_path.exists() or not bm25_path.exists():
            raise FileNotFoundError(
                f"Hybrid index artifacts missing in {self.index_dir}. Run `python scripts/ingest_data.py` first."
            )

        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, vector_idx, scheme_slug, scheme_name, ministry, section,
                       faq_numbers_json, text, token_count, source_url, metadata_json
                FROM chunks_meta
                ORDER BY vector_idx ASC
                """
            ).fetchall()

        chunks: list[dict[str, Any]] = []
        for r in rows:
            meta = json.loads(r["metadata_json"] or "{}")
            chunks.append(
                {
                    "chunk_id": r["chunk_id"],
                    "vector_idx": r["vector_idx"],
                    "scheme_slug": r["scheme_slug"],
                    "scheme_name": r["scheme_name"],
                    "ministry": r["ministry"],
                    "section": r["section"],
                    "faq_numbers": json.loads(r["faq_numbers_json"] or "[]"),
                    "text": r["text"],
                    "token_count": r["token_count"],
                    "source_url": r["source_url"],
                    "metadata": meta,
                }
            )

        embeddings = np.load(str(emb_path))
        with bm25_path.open("rb") as f:
            bundle = pickle.load(f)
        self.load_from_memory(chunks, embeddings, bundle["bm25"])

    def load_from_memory(self, chunks: list[dict[str, Any]], embeddings: np.ndarray, bm25: Any) -> None:
        """Use an index built in memory (chunk dicts shaped like `chunks_meta` rows, row-aligned embeddings, a
        BM25 model over the same chunks). `load()` uses this for the on-disk index; the chunking experiments use it
        for temporary indexes that never touch `data/index`."""
        if len(chunks) != embeddings.shape[0]:
            raise RuntimeError(
                f"Index mismatch: {len(chunks)} chunks vs {embeddings.shape[0]} embedding rows"
            )
        self.chunks = chunks
        self.embeddings = embeddings.astype(np.float32)
        self.bm25 = bm25
        self._searchable_idx = np.asarray(
            [i for i, ch in enumerate(self.chunks) if not (self.exclude_faq_chunks and ch["section"] == FAQ_SECTION)],
            dtype=np.int32,
        )
        self._loaded = True
        logger.info("HybridRetriever loaded %d chunks (%d searchable, FAQ chunks %s) and %s embeddings.",
                    len(self.chunks), len(self._searchable_idx),
                    "excluded" if self.exclude_faq_chunks else "included", self.embeddings.shape)

    def _get_reranker(self):
        if not self._load_reranker_enabled:
            return None
        if self._reranker is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading local CPU CrossEncoder reranker: %s", self.settings.reranker_model)
            self._reranker = CrossEncoder(self.settings.reranker_model, device="cpu")
        return self._reranker

    def _to_result(self, idx: int, **scores: float) -> RetrievedChunk:
        ch = self.chunks[idx]
        sec_tag = ch["section"]
        if ch["faq_numbers"]:
            sec_tag = f"faq_{','.join(str(n) for n in ch['faq_numbers'])}"
        return RetrievedChunk(
            chunk_id=ch["chunk_id"],
            citation_id=f"SCHEME:{ch['scheme_slug']}#{sec_tag}",
            scheme_slug=ch["scheme_slug"],
            scheme_name=ch["scheme_name"],
            ministry=ch["ministry"],
            section=ch["section"],
            text=ch["text"],
            source_url=ch["source_url"],
            faq_numbers=ch["faq_numbers"],
            metadata=ch["metadata"],
            **scores,
        )

    def scheme_section_chunks(self, scheme_slug: str, query: str) -> list[dict[str, Any]]:
        """One scheme's official text (benefits, eligibility, process/documents; no FAQ chunks), most relevant to
        `query` first by the local cross-encoder (document order if the reranker is disabled)."""
        self.load()
        idxs = [i for i, ch in enumerate(self.chunks) if ch["scheme_slug"] == scheme_slug and ch["section"] != FAQ_SECTION]
        reranker = self._get_reranker()
        if reranker is None or len(idxs) < 2:
            return [self._to_result(i).to_dict() for i in idxs]
        logits = reranker.predict([(query, self.chunks[i]["text"]) for i in idxs])
        ranked = sorted(zip(idxs, logits), key=lambda pair: float(pair[1]), reverse=True)
        return [self._to_result(i, rerank_logit=float(lg)).to_dict() for i, lg in ranked]

    def _filter_indices(self, filters: dict[str, Any] | None) -> tuple[np.ndarray, bool, bool]:
        """Permissive metadata pre-filtering: null/empty fields on a scheme NEVER exclude a citizen."""
        all_idx = self._searchable_idx
        if not filters:
            return all_idx, False, False

        ministry = (filters.get("ministry") or "").strip().lower()
        category = (filters.get("category") or "").strip().lower()
        dbt_only = filters.get("dbt_only")
        beneficiary = (filters.get("beneficiary_group") or "").strip().lower()
        age = filters.get("age")
        income_inr = filters.get("annual_income_inr")
        social_cat = (filters.get("social_category") or "").strip().lower()

        if not any([ministry, category, dbt_only is True, beneficiary, age is not None, income_inr is not None, social_cat]):
            return all_idx, False, False

        matched: list[int] = []
        for idx in all_idx.tolist():
            ch = self.chunks[idx]
            meta = ch["metadata"]
            if ministry and ministry not in ch["ministry"].lower() and ministry != (meta.get("ministry_code") or "").lower():
                continue
            if dbt_only is True and not meta.get("dbt_scheme"):
                continue
            if category:
                cats = " ".join(meta.get("categories") or []).lower()
                tags = " ".join(meta.get("tags") or []).lower()
                if category not in cats and category not in tags:
                    continue
            if beneficiary:
                bgroups = [b.lower() for b in (meta.get("beneficiary_groups") or [])]
                # Permissive: empty beneficiary_groups never excludes
                if bgroups and not any(beneficiary in b or b in beneficiary for b in bgroups):
                    continue
            if age is not None:
                a_min = meta.get("age_min")
                a_max = meta.get("age_max")
                if a_min is not None and age < a_min:
                    continue
                if a_max is not None and age > a_max:
                    continue
            if income_inr is not None:
                cap = meta.get("income_cap_inr")
                if cap is not None and income_inr > cap:
                    continue
            if social_cat and social_cat not in ("general", "all"):
                scats = [s.lower() for s in (meta.get("social_categories") or [])]
                # Permissive: empty or includes general -> allowed
                if scats and "general" not in scats and social_cat not in scats:
                    continue
            matched.append(idx)

        if len(matched) < 5:
            # Relax filter rather than returning empty/poor results
            return all_idx, True, True
        return np.asarray(matched, dtype=np.int32), True, False

    def search_sync(
        self,
        query: str,
        top_k: int = 6,
        mode: RetrievalMode = "hybrid_rerank",
        filters: dict[str, Any] | None = None,
        k_bm25: int = 30,
        k_dense: int = 30,
        k_rrf: int = 20,
        rrf_k: int = 60,
        query_embedding: np.ndarray | None = None,
    ) -> RetrievalOutput:
        self.load()
        t0 = time.perf_counter()

        cand_indices, filter_applied, filter_relaxed = self._filter_indices(filters)
        cand_set = set(int(i) for i in cand_indices)

        bm25_scores_map: dict[int, float] = {}
        dense_scores_map: dict[int, float] = {}
        bm25_ranked: list[int] = []
        dense_ranked: list[int] = []

        # 1. BM25 Sparse Retrieval
        if mode in ("bm25", "hybrid_rrf", "hybrid_rerank"):
            q_tokens = _tokenize(query)
            if q_tokens:
                raw_bm25 = self.bm25.get_scores(q_tokens)
                sub_scores = raw_bm25[cand_indices]
                top_local = np.argsort(sub_scores)[::-1][:k_bm25]
                for loc in top_local:
                    doc_idx = int(cand_indices[loc])
                    sc = float(sub_scores[loc])
                    bm25_scores_map[doc_idx] = sc
                    bm25_ranked.append(doc_idx)

        # 2. Dense Vector Retrieval (bge-small-en-v1.5)
        q_emb = query_embedding
        if mode in ("dense", "hybrid_rrf", "hybrid_rerank"):
            if q_emb is None:
                q_emb = self.embedding_client.embed_texts_sync([query], use_cache=True)[0]
            sub_vecs = self.embeddings[cand_indices]
            sims = sub_vecs @ q_emb
            top_local = np.argsort(sims)[::-1][:k_dense]
            for loc in top_local:
                doc_idx = int(cand_indices[loc])
                sc = float(sims[loc])
                dense_scores_map[doc_idx] = sc
                dense_ranked.append(doc_idx)

        # 3. Candidate Fusion
        rrf_scores_map: dict[int, float] = {}
        if mode == "bm25":
            ordered_indices = bm25_ranked[:top_k]
        elif mode == "dense":
            ordered_indices = dense_ranked[:top_k]
        else:
            for rank, doc_idx in enumerate(bm25_ranked, start=1):
                rrf_scores_map[doc_idx] = rrf_scores_map.get(doc_idx, 0.0) + 1.0 / (rrf_k + rank)
            for rank, doc_idx in enumerate(dense_ranked, start=1):
                rrf_scores_map[doc_idx] = rrf_scores_map.get(doc_idx, 0.0) + 1.0 / (rrf_k + rank)
            ordered_indices = sorted(
                rrf_scores_map.keys(),
                key=lambda idx: rrf_scores_map[idx],
                reverse=True,
            )[: (k_rrf if mode == "hybrid_rerank" else top_k)]

        # Ensure we still compute dense/bm25 scores for chosen candidates for full observability
        if q_emb is not None:
            for idx in ordered_indices:
                if idx not in dense_scores_map:
                    dense_scores_map[idx] = float(np.dot(self.embeddings[idx], q_emb))

        # 4. Local Cross-Encoder Reranker
        rerank_prob_map: dict[int, float] = {}
        rerank_logit_map: dict[int, float] = {}
        if mode == "hybrid_rerank" and ordered_indices:
            reranker = self._get_reranker()
            if reranker is not None:
                pairs = [(query, self.chunks[idx]["text"]) for idx in ordered_indices]
                logits = reranker.predict(pairs)
                for idx, lg in zip(ordered_indices, logits):
                    lg_f = float(lg)
                    rerank_logit_map[idx] = lg_f
                    rerank_prob_map[idx] = _sigmoid(lg_f)
                ordered_indices = sorted(
                    ordered_indices,
                    key=lambda idx: rerank_logit_map[idx],
                    reverse=True,
                )[:top_k]
            else:
                ordered_indices = ordered_indices[:top_k]

        results = [
            self._to_result(
                idx,
                bm25_score=bm25_scores_map.get(idx, 0.0),
                dense_score=dense_scores_map.get(idx, 0.0),
                rrf_score=rrf_scores_map.get(idx, 0.0),
                rerank_score=rerank_prob_map.get(idx, dense_scores_map.get(idx, 0.0)),
                rerank_logit=rerank_logit_map.get(idx, 0.0),
            )
            for idx in ordered_indices
        ]

        top_rerank = max((r.rerank_score for r in results), default=0.0)
        low_conf = top_rerank < self.settings.web_fallback_threshold
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return RetrievalOutput(
            results=results,
            mode=mode,
            top_rerank_score=round(top_rerank, 4),
            low_confidence=low_conf,
            latency_ms=latency_ms,
            filter_applied=filter_applied,
            filter_relaxed=filter_relaxed,
            query_embedding=q_emb,
        )

    async def search(
        self,
        query: str,
        top_k: int = 6,
        mode: RetrievalMode = "hybrid_rerank",
        filters: dict[str, Any] | None = None,
        query_embedding: np.ndarray | None = None,
    ) -> RetrievalOutput:
        return await asyncio.to_thread(
            self.search_sync,
            query,
            top_k,
            mode,
            filters,
            30,
            30,
            20,
            60,
            query_embedding,
        )


_SINGLETON_RETRIEVER: HybridRetriever | None = None


def get_hybrid_retriever() -> HybridRetriever:
    global _SINGLETON_RETRIEVER
    if _SINGLETON_RETRIEVER is None:
        _SINGLETON_RETRIEVER = HybridRetriever()
        _SINGLETON_RETRIEVER.load()
    return _SINGLETON_RETRIEVER
