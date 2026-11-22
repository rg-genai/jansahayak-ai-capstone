"""Milestone M1 verification tests: ETL, enrichment, chunking, embeddings, and BM25 index."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np

from backend.config import get_settings
from backend.db.database import get_connection
from backend.gateway.embedding_client import EMBEDDING_DIM


def test_sqlite_catalog_counts():
    settings = get_settings()
    assert settings.db_abs_path.exists(), "SQLite database data/jansahayak.db not found"

    with get_connection(settings.db_abs_path) as conn:
        schemes_cnt = conn.execute("SELECT COUNT(*) FROM schemes_catalog").fetchone()[0]
        faqs_cnt = conn.execute("SELECT COUNT(*) FROM scheme_faqs").fetchone()[0]
        ministries_cnt = conn.execute("SELECT COUNT(*) FROM ministries").fetchone()[0]
        chunks_cnt = conn.execute("SELECT COUNT(*) FROM chunks_meta").fetchone()[0]
        over_512 = conn.execute("SELECT COUNT(*) FROM chunks_meta WHERE token_count > 512").fetchone()[0]
        bad_urls = conn.execute(
            "SELECT COUNT(*) FROM schemes_catalog WHERE source_url NOT LIKE 'https://%'"
        ).fetchone()[0]
        bad_chunk_urls = conn.execute(
            "SELECT COUNT(*) FROM chunks_meta WHERE source_url NOT LIKE 'https://%'"
        ).fetchone()[0]

    assert schemes_cnt == 649, f"Expected 649 Central schemes, got {schemes_cnt}"
    assert faqs_cnt == 7724, f"Expected 7724 Central FAQs, got {faqs_cnt}"
    assert ministries_cnt == 51, f"Expected 51 canonical ministries, got {ministries_cnt}"
    assert chunks_cnt > 4000, f"Expected >4000 chunks, got {chunks_cnt}"
    assert over_512 == 0, f"Found {over_limit if 'over_limit' in locals() else over_512} chunks > 512 tokens"
    assert bad_urls == 0, f"Found {bad_urls} schemes with invalid source_url"
    assert bad_chunk_urls == 0, f"Found {bad_chunk_urls} chunks with invalid source_url"


def test_embeddings_and_bm25_alignment():
    settings = get_settings()
    emb_path = settings.index_abs_dir / "embeddings.npy"
    bm25_path = settings.index_abs_dir / "bm25.pkl"
    manifest_path = settings.index_abs_dir / "index_manifest.json"

    assert emb_path.exists(), "embeddings.npy missing"
    assert bm25_path.exists(), "bm25.pkl missing"
    assert manifest_path.exists(), "index_manifest.json missing"

    with get_connection(settings.db_abs_path) as conn:
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks_meta").fetchone()[0]

    vecs = np.load(str(emb_path))
    assert vecs.shape == (chunk_count, EMBEDDING_DIM), (
        f"Expected embeddings shape ({chunk_count}, {EMBEDDING_DIM}), got {vecs.shape}"
    )
    assert np.isfinite(vecs).all(), "Embeddings contain NaN or Inf"
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3), "Embeddings are not L2-normalized"

    with bm25_path.open("rb") as f:
        bm25_bundle = pickle.load(f)
    assert len(bm25_bundle["chunk_ids"]) == chunk_count
    assert bm25_bundle["bm25"].corpus_size == chunk_count

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["scheme_count"] == 649
    assert manifest["ministry_count"] == 51
    assert manifest["chunk_count"] == chunk_count
    assert manifest["max_chunk_tokens"] <= 512


def test_enriched_metadata_populated():
    settings = get_settings()
    with get_connection(settings.db_abs_path) as conn:
        with_age = conn.execute(
            "SELECT COUNT(*) FROM schemes_catalog WHERE age_min IS NOT NULL OR age_max IS NOT NULL"
        ).fetchone()[0]
        with_income = conn.execute(
            "SELECT COUNT(*) FROM schemes_catalog WHERE income_cap_inr IS NOT NULL"
        ).fetchone()[0]
        with_social = conn.execute(
            "SELECT COUNT(*) FROM schemes_catalog WHERE social_categories_json != '[]'"
        ).fetchone()[0]
        with_benef = conn.execute(
            "SELECT COUNT(*) FROM schemes_catalog WHERE beneficiary_groups_json != '[]'"
        ).fetchone()[0]
        pmkisan = conn.execute(
            "SELECT slug, ministry_code, dbt_scheme FROM schemes_catalog WHERE slug = 'pm-kisan'"
        ).fetchone()

    assert with_age > 50, f"Expected >50 schemes with extracted age bounds, got {with_age}"
    assert with_income > 30, f"Expected >30 schemes with extracted income cap, got {with_income}"
    assert with_social > 100, f"Expected >100 schemes with extracted social categories, got {with_social}"
    assert with_benef > 400, f"Expected >400 schemes with extracted beneficiary groups, got {with_benef}"
    # Verify at least one PM-KISAN scheme exists in catalog
    with get_connection(settings.db_abs_path) as conn:
        pmk = conn.execute(
            "SELECT slug, ministry_code FROM schemes_catalog WHERE scheme_name LIKE '%Kisan Samman Nidhi%'"
        ).fetchone()
    assert pmk is not None, "Pradhan Mantri Kisan Samman Nidhi not found in catalog"
    assert pmk["ministry_code"] == "MOAFW"
