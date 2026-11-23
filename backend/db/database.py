"""SQLite database initialization and connection management (WAL mode)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.config import get_settings


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS ministries (
    ministry_code TEXT PRIMARY KEY,
    ministry_name TEXT NOT NULL UNIQUE,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    scheme_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS schemes_catalog (
    slug TEXT PRIMARY KEY,
    scheme_name TEXT NOT NULL,
    short_title TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL,
    state TEXT DEFAULT '',
    ministry TEXT NOT NULL DEFAULT '',
    ministry_code TEXT NOT NULL DEFAULT '',
    department TEXT DEFAULT '',
    categories TEXT DEFAULT '',
    sub_categories TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    benefit_type TEXT DEFAULT '',
    dbt_scheme INTEGER NOT NULL DEFAULT 0,
    application_mode TEXT DEFAULT '',
    age_min INTEGER,
    age_max INTEGER,
    income_cap_inr INTEGER,
    social_categories_json TEXT NOT NULL DEFAULT '[]',
    beneficiary_groups_json TEXT NOT NULL DEFAULT '[]',
    brief_description TEXT DEFAULT '',
    detailed_description TEXT DEFAULT '',
    benefits TEXT DEFAULT '',
    eligibility TEXT DEFAULT '',
    exclusions TEXT DEFAULT '',
    application_process TEXT DEFAULT '',
    documents_required TEXT DEFAULT '',
    references_text TEXT DEFAULT '',
    source_url TEXT NOT NULL,
    faq_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_schemes_level ON schemes_catalog(level);
CREATE INDEX IF NOT EXISTS idx_schemes_ministry ON schemes_catalog(ministry);
CREATE INDEX IF NOT EXISTS idx_schemes_ministry_code ON schemes_catalog(ministry_code);

CREATE TABLE IF NOT EXISTS scheme_faqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_slug TEXT NOT NULL,
    faq_number INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    FOREIGN KEY (scheme_slug) REFERENCES schemes_catalog(slug) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_faqs_slug ON scheme_faqs(scheme_slug);

CREATE TABLE IF NOT EXISTS chunks_meta (
    chunk_id TEXT PRIMARY KEY,
    vector_idx INTEGER NOT NULL UNIQUE,
    scheme_slug TEXT NOT NULL,
    scheme_name TEXT NOT NULL,
    ministry TEXT NOT NULL DEFAULT '',
    section TEXT NOT NULL,
    faq_numbers_json TEXT NOT NULL DEFAULT '[]',
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_chunks_slug ON chunks_meta(scheme_slug);
CREATE INDEX IF NOT EXISTS idx_chunks_section ON chunks_meta(section);
CREATE INDEX IF NOT EXISTS idx_chunks_vecidx ON chunks_meta(vector_idx);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    preferred_language TEXT NOT NULL DEFAULT 'en',
    profile_json TEXT NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    eligibility_json TEXT DEFAULT NULL,
    grievance_json TEXT DEFAULT NULL,
    trace_id TEXT DEFAULT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

CREATE TABLE IF NOT EXISTS grievances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id TEXT NOT NULL UNIQUE,
    registration_number TEXT UNIQUE,
    session_id TEXT NOT NULL DEFAULT '',
    scheme_slug TEXT NOT NULL DEFAULT '',
    scheme_name TEXT NOT NULL DEFAULT '',
    ministry_code TEXT NOT NULL,
    ministry_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    grievance_text TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'AWAITING_CONFIRMATION',
    mode TEXT NOT NULL DEFAULT 'sandbox',
    user_confirmed INTEGER NOT NULL DEFAULT 0,
    beneficiary_reference_id TEXT DEFAULT NULL,
    state TEXT DEFAULT NULL,
    district TEXT DEFAULT NULL,
    pending_since TEXT DEFAULT NULL,
    status_history_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_grievances_reg ON grievances(registration_number);
CREATE INDEX IF NOT EXISTS idx_grievances_session ON grievances(session_id);

CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT 'anonymous',
    user_role TEXT NOT NULL DEFAULT 'citizen',
    timestamp TEXT NOT NULL,
    user_query_masked TEXT NOT NULL DEFAULT '',
    final_answer TEXT NOT NULL DEFAULT '',
    detected_lang TEXT NOT NULL DEFAULT 'en',
    cache_hit TEXT NOT NULL DEFAULT 'miss',
    model_name TEXT NOT NULL DEFAULT 'Qwen/Qwen3-8B',
    planner_json TEXT NOT NULL DEFAULT '{}',
    retrieved_chunks_json TEXT NOT NULL DEFAULT '[]',
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    critic_json TEXT NOT NULL DEFAULT '{}',
    guardrail_flags_json TEXT NOT NULL DEFAULT '[]',
    spans_json TEXT NOT NULL DEFAULT '[]',
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_latency_ms REAL NOT NULL DEFAULT 0.0,
    step_latencies_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'ok',
    error_message TEXT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_traces_ts ON traces(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_traces_session ON traces(session_id);

CREATE TABLE IF NOT EXISTS response_cache (
    cache_key TEXT PRIMARY KEY,
    query_en TEXT NOT NULL,
    lang TEXT NOT NULL,
    profile_hash TEXT NOT NULL,
    embedding_blob BLOB,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_respcache_lang ON response_cache(lang, profile_hash);

CREATE TABLE IF NOT EXISTS embedding_cache (
    text_hash TEXT PRIMARY KEY,
    embedding_blob BLOB NOT NULL,
    created_at TEXT NOT NULL
);

-- LLM-extracted, code-grounded eligibility checklist per scheme (scripts/extract_eligibility_criteria.py)
CREATE TABLE IF NOT EXISTS scheme_criteria (
    scheme_slug TEXT PRIMARY KEY REFERENCES schemes_catalog(slug),
    criteria_json TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL DEFAULT '{}',
    prompt_version TEXT NOT NULL,
    model_name TEXT NOT NULL,
    extracted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_number TEXT NOT NULL,
    draft_id TEXT NOT NULL DEFAULT '',
    recipient_email TEXT NOT NULL,
    applicant_name TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT NOT NULL,
    delivery_status TEXT NOT NULL DEFAULT 'SANDBOX_OUTBOX',
    delivery_detail TEXT NOT NULL DEFAULT '',
    sent_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_emails_reg ON email_notifications(registration_number);
"""


def get_db_path(db_path: Path | None = None) -> Path:
    path = db_path or get_settings().db_abs_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def create_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = get_db_path(db_path)
    conn = sqlite3.connect(str(path), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = create_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_TRACE_MIGRATION_COLUMNS: list[tuple[str, str]] = [
    ("user_id", "TEXT NOT NULL DEFAULT 'anonymous'"),
    ("user_role", "TEXT NOT NULL DEFAULT 'citizen'"),
    ("final_answer", "TEXT NOT NULL DEFAULT ''"),
    ("model_name", "TEXT NOT NULL DEFAULT 'Qwen/Qwen3-8B'"),
    ("spans_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("error_message", "TEXT DEFAULT NULL"),
]


_GRIEVANCE_MIGRATION_COLUMNS: list[tuple[str, str]] = [
    ("applicant_name", "TEXT DEFAULT NULL"),
    ("applicant_email", "TEXT DEFAULT NULL"),
]


def init_db(db_path: Path | None = None) -> Path:
    path = get_db_path(db_path)
    with get_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
        existing_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(traces)").fetchall()
        }
        for col_name, col_def in _TRACE_MIGRATION_COLUMNS:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE traces ADD COLUMN {col_name} {col_def}")

        griev_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(grievances)").fetchall()
        }
        for col_name, col_def in _GRIEVANCE_MIGRATION_COLUMNS:
            if col_name not in griev_cols:
                conn.execute(f"ALTER TABLE grievances ADD COLUMN {col_name} {col_def}")
    return path
