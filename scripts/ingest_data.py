"""Resumable ingestion pipeline: CSV -> SQLite Catalog + Chunks + VM02 Embeddings + BM25 Index."""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

# Ensure project root is on sys.path when invoked as `python scripts/ingest_data.py`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings
from backend.db.database import get_connection, init_db
from backend.db.repositories import now_ist_iso
from backend.gateway.embedding_client import EMBEDDING_DIM, EmbeddingClient
from backend.retrieval.chunker import HARD_TOKEN_LIMIT, SchemeChunk, chunk_all_schemes
from backend.retrieval.etl import load_and_enrich_schemes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ingest_data")


TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize_for_bm25(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def build_bm25_doc_tokens(chunk: SchemeChunk) -> list[str]:
    """Boost scheme_name, short_title, tags, and ministry tokens for sharper lexical recall."""
    meta = chunk.metadata
    boost_parts = [
        chunk.scheme_name,
        chunk.scheme_name,  # 2x weight for exact scheme title
        meta.get("short_title") or "",
        meta.get("short_title") or "",
        chunk.ministry,
        " ".join(meta.get("tags") or []),
        " ".join(meta.get("categories") or []),
        chunk.text,
    ]
    return tokenize_for_bm25(" ".join(boost_parts))


def run_ingestion(scope: str = "central", force_rebuild: bool = False) -> dict:
    t0 = time.perf_counter()
    settings = get_settings()
    db_path = init_db(settings.db_abs_path)
    index_dir = settings.index_abs_dir
    index_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading and enriching schemes (scope=%s) from %s ...", scope, settings.archive_dir)
    schemes, ministries_map = load_and_enrich_schemes(settings.archive_dir, scope=scope)
    total_faqs = sum(s.faq_count for s in schemes)
    logger.info(
        "Loaded %d schemes, %d FAQs across %d canonical ministries.",
        len(schemes),
        total_faqs,
        len(ministries_map),
    )

    logger.info("Chunking schemes & FAQs (section-aware, <= %d tokens)...", HARD_TOKEN_LIMIT)
    chunks = chunk_all_schemes(schemes)
    max_toks = max((c.token_count for c in chunks), default=0)
    over_limit = [c for c in chunks if c.token_count > HARD_TOKEN_LIMIT]
    logger.info(
        "Generated %d chunks | max_tokens=%d | chunks_over_512=%d",
        len(chunks),
        max_toks,
        len(over_limit),
    )
    if over_limit:
        raise RuntimeError(f"Found {len(over_limit)} chunks exceeding {HARD_TOKEN_LIMIT} tokens!")

    # Persist catalog, ministries, FAQs, and chunk metadata into SQLite
    logger.info("Writing schemes_catalog, scheme_faqs, ministries, and chunks_meta to %s ...", db_path)
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM scheme_faqs")
        conn.execute("DELETE FROM chunks_meta")
        conn.execute("DELETE FROM schemes_catalog")
        conn.execute("DELETE FROM ministries")

        conn.executemany(
            "INSERT INTO ministries(ministry_code, ministry_name, aliases_json, scheme_count) VALUES (?, ?, ?, ?)",
            [
                (
                    m["ministry_code"],
                    m["ministry_name"],
                    json.dumps(m["aliases"], ensure_ascii=False),
                    m["scheme_count"],
                )
                for m in ministries_map.values()
            ],
        )

        conn.executemany(
            """
            INSERT INTO schemes_catalog(
                slug, scheme_name, short_title, level, state, ministry, ministry_code,
                department, categories, sub_categories, tags, benefit_type, dbt_scheme,
                application_mode, age_min, age_max, income_cap_inr,
                social_categories_json, beneficiary_groups_json,
                brief_description, detailed_description, benefits, eligibility, exclusions,
                application_process, documents_required, references_text, source_url, faq_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    s.slug,
                    s.scheme_name,
                    s.short_title,
                    s.level,
                    s.state,
                    s.ministry,
                    s.ministry_code,
                    s.department,
                    s.categories,
                    s.sub_categories,
                    s.tags,
                    s.benefit_type,
                    1 if s.dbt_scheme else 0,
                    s.application_mode,
                    s.age_min,
                    s.age_max,
                    s.income_cap_inr,
                    json.dumps(s.social_categories, ensure_ascii=False),
                    json.dumps(s.beneficiary_groups, ensure_ascii=False),
                    s.brief_description,
                    s.detailed_description,
                    s.benefits,
                    s.eligibility,
                    s.exclusions,
                    s.application_process,
                    s.documents_required,
                    s.references_text,
                    s.source_url,
                    s.faq_count,
                )
                for s in schemes
            ],
        )

        faq_rows = []
        for s in schemes:
            for faq in s.faqs:
                faq_rows.append((s.slug, faq["faq_number"], faq["question"], faq["answer"]))
        conn.executemany(
            "INSERT INTO scheme_faqs(scheme_slug, faq_number, question, answer) VALUES (?, ?, ?, ?)",
            faq_rows,
        )

        conn.executemany(
            """
            INSERT INTO chunks_meta(
                chunk_id, vector_idx, scheme_slug, scheme_name, ministry, section,
                faq_numbers_json, text, token_count, source_url, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    c.chunk_id,
                    idx,
                    c.scheme_slug,
                    c.scheme_name,
                    c.ministry,
                    c.section,
                    json.dumps(c.faq_numbers),
                    c.text,
                    c.token_count,
                    c.source_url,
                    json.dumps(c.metadata, ensure_ascii=False),
                )
                for idx, c in enumerate(chunks)
            ],
        )

    # Embed chunks via VM02 bge-small-en-v1.5 with SQLite embedding_cache checkpointing
    logger.info("Embedding %d chunks via %s (batch=%d, checkpointed in SQLite)...", len(chunks), settings.embedding_model, settings.embedding_batch_size)
    emb_client = EmbeddingClient(db_path=db_path)
    texts = [c.text for c in chunks]
    vectors = emb_client.embed_texts_sync(texts, use_cache=not force_rebuild, progress_every=20)
    if vectors.shape != (len(chunks), EMBEDDING_DIM):
        raise RuntimeError(f"Embedding matrix shape mismatch: {vectors.shape} vs ({len(chunks)}, {EMBEDDING_DIM})")

    emb_path = index_dir / "embeddings.npy"
    np.save(str(emb_path), vectors.astype(np.float32))
    logger.info("Saved dense embeddings to %s | shape=%s | dtype=%s", emb_path, vectors.shape, vectors.dtype)

    # Build BM25 index
    logger.info("Building BM25Okapi lexical index...")
    tokenized_corpus = [build_bm25_doc_tokens(c) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    bm25_path = index_dir / "bm25.pkl"
    with bm25_path.open("wb") as f:
        pickle.dump(
            {
                "bm25": bm25,
                "chunk_ids": [c.chunk_id for c in chunks],
            },
            f,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    logger.info("Saved BM25 index to %s", bm25_path)

    elapsed = round(time.perf_counter() - t0, 2)
    manifest = {
        "scope": scope,
        "built_at": now_ist_iso(),
        "elapsed_seconds": elapsed,
        "scheme_count": len(schemes),
        "faq_count": total_faqs,
        "ministry_count": len(ministries_map),
        "chunk_count": len(chunks),
        "max_chunk_tokens": max_toks,
        "embedding_model": settings.embedding_model,
        "embedding_shape": list(vectors.shape),
    }
    manifest_path = index_dir / "index_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Ingestion complete in %.2fs! Manifest: %s", elapsed, json.dumps(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest myScheme datasets into JanSahayak AI Hybrid Index.")
    parser.add_argument("--scope", choices=["central", "all"], default=None)
    parser.add_argument("--force-rebuild", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    scope = args.scope or settings.ingest_scope
    run_ingestion(scope=scope, force_rebuild=args.force_rebuild)
    return 0


if __name__ == "__main__":
    sys.exit(main())
