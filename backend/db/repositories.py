"""SQLite repositories for schemes, sessions, messages, grievances, traces, and caches."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from backend.db.database import get_connection, init_db


IST = timezone(timedelta(hours=5, minutes=30))


def now_ist_iso() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


class Repository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = init_db(db_path)

    # ---- Schemes & Ministries ----

    @staticmethod
    def _scheme_from_row(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["social_categories"] = json.loads(item.get("social_categories_json") or "[]")
        item["beneficiary_groups"] = json.loads(item.get("beneficiary_groups_json") or "[]")
        item["dbt_scheme"] = bool(item.get("dbt_scheme"))
        return item

    def get_scheme(self, slug: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM schemes_catalog WHERE slug = ?", (slug,)
            ).fetchone()
            return self._scheme_from_row(row) if row else None

    def list_all_schemes(self) -> list[dict[str, Any]]:
        """Every scheme with all its columns, in one query (for offline scripts that scan the catalog)."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM schemes_catalog ORDER BY slug").fetchall()
        return [self._scheme_from_row(r) for r in rows]

    def list_scheme_titles(self) -> list[dict[str, str]]:
        """Slug, full name and short title of every scheme (for name matching)."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute("SELECT slug, scheme_name, short_title FROM schemes_catalog").fetchall()
        return [dict(r) for r in rows]

    def beneficiary_group_categories(self) -> dict[str, dict[str, int]]:
        """{beneficiary_group: {category: scheme_count}} across the catalog."""
        out: dict[str, dict[str, int]] = {}
        with get_connection(self.db_path) as conn:
            rows = conn.execute("SELECT beneficiary_groups_json, categories FROM schemes_catalog").fetchall()
        for row in rows:
            cats = [c.strip() for c in (row["categories"] or "").split(",") if c.strip()]
            for group in json.loads(row["beneficiary_groups_json"] or "[]"):
                bucket = out.setdefault(group, {})
                for cat in cats:
                    bucket[cat] = bucket.get(cat, 0) + 1
        return out

    def save_scheme_criteria(
        self, slug: str, criteria: dict[str, Any], diagnostics: dict[str, Any], prompt_version: str, model_name: str
    ) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO scheme_criteria(scheme_slug, criteria_json, diagnostics_json, prompt_version, model_name, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(scheme_slug) DO UPDATE SET
                    criteria_json = excluded.criteria_json, diagnostics_json = excluded.diagnostics_json,
                    prompt_version = excluded.prompt_version, model_name = excluded.model_name,
                    extracted_at = excluded.extracted_at
                """,
                (slug, json.dumps(criteria, ensure_ascii=False), json.dumps(diagnostics, ensure_ascii=False),
                 prompt_version, model_name, now_ist_iso()),
            )

    def get_scheme_criteria(self, slug: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM scheme_criteria WHERE scheme_slug = ?", (slug,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["criteria"] = json.loads(item.pop("criteria_json"))
        item["diagnostics"] = json.loads(item.pop("diagnostics_json"))
        return item

    def list_scheme_criteria_versions(self) -> dict[str, str]:
        """{scheme_slug: prompt_version} for every extracted scheme (used to resume a batch run)."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute("SELECT scheme_slug, prompt_version FROM scheme_criteria").fetchall()
        return {r["scheme_slug"]: r["prompt_version"] for r in rows}

    def list_scheme_slugs(self) -> list[str]:
        with get_connection(self.db_path) as conn:
            return [r["slug"] for r in conn.execute("SELECT slug FROM schemes_catalog ORDER BY slug").fetchall()]

    def get_scheme_faqs(self, slug: str, limit: int = 50) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT faq_number, question, answer FROM scheme_faqs WHERE scheme_slug = ? ORDER BY faq_number ASC LIMIT ?",
                (slug, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_schemes(
        self,
        q: str | None = None,
        ministry: str | None = None,
        category: str | None = None,
        dbt_only: bool | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        where: list[str] = []
        params: list[Any] = []

        if q and q.strip():
            like = f"%{q.strip()}%"
            where.append(
                "(scheme_name LIKE ? OR short_title LIKE ? OR brief_description LIKE ? OR tags LIKE ? OR ministry LIKE ?)"
            )
            params.extend([like, like, like, like, like])
        if ministry and ministry.strip():
            where.append("(ministry LIKE ? OR ministry_code = ?)")
            params.extend([f"%{ministry.strip()}%", ministry.strip().upper()])
        if category and category.strip():
            where.append("(categories LIKE ? OR sub_categories LIKE ? OR tags LIKE ?)")
            params.extend([f"%{category.strip()}%"] * 3)
        if dbt_only is True:
            where.append("dbt_scheme = 1")

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        with get_connection(self.db_path) as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM schemes_catalog {where_sql}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT slug, scheme_name, short_title, level, ministry, ministry_code,
                       categories, benefit_type, dbt_scheme, application_mode,
                       age_min, age_max, income_cap_inr, social_categories_json,
                       beneficiary_groups_json, brief_description, source_url, faq_count
                FROM schemes_catalog
                {where_sql}
                ORDER BY faq_count DESC, scheme_name ASC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["dbt_scheme"] = bool(d["dbt_scheme"])
            d["social_categories"] = json.loads(d.pop("social_categories_json") or "[]")
            d["beneficiary_groups"] = json.loads(d.pop("beneficiary_groups_json") or "[]")
            results.append(d)
        return results, int(total)

    def list_ministries(self) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT ministry_code, ministry_name, aliases_json, scheme_count FROM ministries ORDER BY ministry_name ASC"
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["aliases"] = json.loads(d.pop("aliases_json") or "[]")
                out.append(d)
            return out

    def resolve_ministry(self, ministry_or_code: str) -> dict[str, str] | None:
        if not ministry_or_code:
            return None
        needle = ministry_or_code.strip().lower()
        ministries = self.list_ministries()
        for m in ministries:
            if m["ministry_code"].lower() == needle or m["ministry_name"].lower() == needle:
                return {"ministry_code": m["ministry_code"], "ministry_name": m["ministry_name"]}
        # Partial / token overlap fallback
        best: dict[str, Any] | None = None
        best_score = 0
        needle_tokens = {t for t in needle.replace(",", " ").replace("&", " ").split() if len(t) > 2}
        for m in ministries:
            m_name_low = m["ministry_name"].lower()
            if needle in m_name_low or m_name_low in needle:
                return {"ministry_code": m["ministry_code"], "ministry_name": m["ministry_name"]}
            m_tokens = {t for t in m_name_low.replace(",", " ").replace("&", " ").split() if len(t) > 2}
            overlap = len(needle_tokens & m_tokens)
            if overlap > best_score:
                best_score = overlap
                best = m
        if best and best_score >= 1:
            return {"ministry_code": best["ministry_code"], "ministry_name": best["ministry_name"]}
        return None

    def get_counts(self) -> dict[str, int]:
        with get_connection(self.db_path) as conn:
            return {
                "schemes": conn.execute("SELECT COUNT(*) FROM schemes_catalog").fetchone()[0],
                "faqs": conn.execute("SELECT COUNT(*) FROM scheme_faqs").fetchone()[0],
                "chunks": conn.execute("SELECT COUNT(*) FROM chunks_meta").fetchone()[0],
                "ministries": conn.execute("SELECT COUNT(*) FROM ministries").fetchone()[0],
                "traces": conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0],
                "grievances": conn.execute("SELECT COUNT(*) FROM grievances").fetchone()[0],
            }

    # ---- Sessions & Messages ----

    def get_or_create_session(self, session_id: str, preferred_language: str = "en") -> dict[str, Any]:
        ts = now_ist_iso()
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["profile"] = json.loads(d.pop("profile_json") or "{}")
                return d
            conn.execute(
                """
                INSERT INTO sessions(session_id, preferred_language, profile_json, summary, created_at, updated_at)
                VALUES (?, ?, '{}', '', ?, ?)
                """,
                (session_id, preferred_language, ts, ts),
            )
            return {
                "session_id": session_id,
                "preferred_language": preferred_language,
                "profile": {},
                "summary": "",
                "created_at": ts,
                "updated_at": ts,
            }

    def update_session(
        self,
        session_id: str,
        profile: dict[str, Any] | None = None,
        preferred_language: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        sess = self.get_or_create_session(session_id, preferred_language or "en")
        new_profile = sess["profile"] if profile is None else profile
        new_lang = sess["preferred_language"] if preferred_language is None else preferred_language
        new_summary = sess["summary"] if summary is None else summary
        ts = now_ist_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE sessions
                SET preferred_language = ?, profile_json = ?, summary = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (new_lang, json.dumps(new_profile, ensure_ascii=False), new_summary, ts, session_id),
            )
        return self.get_or_create_session(session_id)

    def delete_session(self, session_id: str) -> dict[str, int]:
        """DPDP Act 2023 Right to Erasure: removes session, messages, and unsubmitted drafts."""
        with get_connection(self.db_path) as conn:
            msg_count = conn.execute(
                "DELETE FROM messages WHERE session_id = ?", (session_id,)
            ).rowcount
            sess_count = conn.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session_id,)
            ).rowcount
            draft_count = conn.execute(
                "DELETE FROM grievances WHERE session_id = ? AND user_confirmed = 0",
                (session_id,),
            ).rowcount
            trace_count = conn.execute(
                "UPDATE traces SET session_id = '[ERASED]', user_query_masked = '[ERASED_BY_USER]' WHERE session_id = ?",
                (session_id,),
            ).rowcount
        return {
            "sessions_deleted": sess_count,
            "messages_deleted": msg_count,
            "drafts_deleted": draft_count,
            "traces_anonymized": trace_count,
        }

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        citations: list[dict[str, Any]] | None = None,
        eligibility: dict[str, Any] | None = None,
        grievance: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> int:
        self.get_or_create_session(session_id)
        ts = now_ist_iso()
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO messages(session_id, role, content, citations_json, eligibility_json, grievance_json, trace_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    role,
                    content,
                    json.dumps(citations or [], ensure_ascii=False),
                    json.dumps(eligibility, ensure_ascii=False) if eligibility else None,
                    json.dumps(grievance, ensure_ascii=False) if grievance else None,
                    trace_id,
                    ts,
                ),
            )
            return int(cur.lastrowid)

    def get_messages(self, session_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, citations_json, eligibility_json, grievance_json, trace_id, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        out = []
        for r in reversed(rows):
            d = dict(r)
            d["citations"] = json.loads(d.pop("citations_json") or "[]")
            elig = d.pop("eligibility_json")
            d["eligibility"] = json.loads(elig) if elig else None
            griev = d.pop("grievance_json")
            d["grievance"] = json.loads(griev) if griev else None
            out.append(d)
        return out

    # ---- Grievances ----

    def save_grievance_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        ts = now_ist_iso()
        history = [{"status": "AWAITING_CONFIRMATION", "timestamp": ts, "note": "Draft created; awaiting citizen HITL confirmation"}]
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO grievances(
                    draft_id, registration_number, session_id, scheme_slug, scheme_name,
                    ministry_code, ministry_name, subject, grievance_text, char_count,
                    status, mode, user_confirmed, beneficiary_reference_id, state, district,
                    pending_since, status_history_json, created_at, updated_at
                ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, 'AWAITING_CONFIRMATION', ?, 0, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft["draft_id"],
                    draft.get("session_id", ""),
                    draft.get("scheme_slug", ""),
                    draft.get("scheme_name", ""),
                    draft["ministry_code"],
                    draft["ministry_name"],
                    draft["subject"],
                    draft["grievance_text"],
                    int(draft["char_count"]),
                    draft.get("mode", "sandbox"),
                    draft.get("beneficiary_reference_id"),
                    draft.get("state"),
                    draft.get("district"),
                    draft.get("pending_since"),
                    json.dumps(history, ensure_ascii=False),
                    ts,
                    ts,
                ),
            )
        return self.get_grievance_by_draft_id(draft["draft_id"]) or draft

    def get_grievance_by_draft_id(self, draft_id: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM grievances WHERE draft_id = ?", (draft_id,)
            ).fetchone()
            return self._row_to_grievance(row) if row else None

    def get_grievance_by_reg_no(self, registration_number: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM grievances WHERE UPPER(registration_number) = UPPER(?)",
                (registration_number.strip(),),
            ).fetchone()
            return self._row_to_grievance(row) if row else None

    def list_grievances(self, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM grievances WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM grievances ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._row_to_grievance(r) for r in rows]

    def mark_grievance_submitted(
        self,
        draft_id: str,
        registration_number: str,
        status: str,
        mode: str,
        note: str = "Submitted to CPGRAMS gateway after explicit user confirmation",
    ) -> dict[str, Any] | None:
        existing = self.get_grievance_by_draft_id(draft_id)
        if not existing:
            return None
        ts = now_ist_iso()
        history = existing.get("status_history", [])
        history.append({"status": status, "timestamp": ts, "note": note})
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE grievances
                SET registration_number = ?, status = ?, mode = ?, user_confirmed = 1,
                    status_history_json = ?, updated_at = ?
                WHERE draft_id = ?
                """,
                (registration_number, status, mode, json.dumps(history, ensure_ascii=False), ts, draft_id),
            )
        return self.get_grievance_by_draft_id(draft_id)

    def next_grievance_sequence(self, ministry_code: str) -> int:
        with get_connection(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM grievances WHERE ministry_code = ? AND registration_number IS NOT NULL",
                (ministry_code,),
            ).fetchone()[0]
            return int(count) + 1

    def update_grievance_status(
        self,
        registration_number: str,
        new_status: str,
        note: str = "",
    ) -> dict[str, Any] | None:
        rec = self.get_grievance_by_reg_no(registration_number)
        if not rec:
            return None
        ts = now_ist_iso()
        history = rec.get("status_history", [])
        history.append({"status": new_status, "timestamp": ts, "note": note or f"Status updated to {new_status}"})
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE grievances SET status = ?, status_history_json = ?, updated_at = ? WHERE UPPER(registration_number) = UPPER(?)",
                (new_status, json.dumps(history, ensure_ascii=False), ts, registration_number.strip()),
            )
        return self.get_grievance_by_reg_no(registration_number)

    def save_email_notification(self, notif: dict[str, Any]) -> dict[str, Any]:
        ts = notif.get("sent_at") or now_ist_iso()
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO email_notifications(
                    registration_number, draft_id, recipient_email, applicant_name,
                    subject, body_text, body_html, delivery_status, delivery_detail, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notif["registration_number"],
                    notif.get("draft_id", ""),
                    notif["recipient_email"],
                    notif.get("applicant_name", ""),
                    notif["subject"],
                    notif["body_text"],
                    notif["body_html"],
                    notif.get("delivery_status", "SANDBOX_OUTBOX"),
                    notif.get("delivery_detail", ""),
                    ts,
                ),
            )
            row = conn.execute("SELECT * FROM email_notifications WHERE id = ?", (cur.lastrowid,)).fetchone()
            return dict(row) if row else notif

    def list_email_notifications(self, registration_number: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            if registration_number:
                rows = conn.execute(
                    "SELECT * FROM email_notifications WHERE UPPER(registration_number) = UPPER(?) ORDER BY id DESC LIMIT ?",
                    (registration_number.strip(), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM email_notifications ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    def list_sessions_for_prefix(
        self, prefix: str, extra_session_id: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Sessions with at least one message, most recently active first.

        Persona primary sessions (e.g. citizen-ramesh-01) do not share the username prefix,
        so they are matched explicitly via extra_session_id.
        """
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT s.session_id, s.preferred_language,
                       MAX(m.created_at) as last_message_at,
                       COUNT(m.id) as message_count,
                       (SELECT content FROM messages fq WHERE fq.session_id = s.session_id AND fq.role = 'user' ORDER BY fq.id ASC LIMIT 1) as first_question
                FROM sessions s
                JOIN messages m ON m.session_id = s.session_id
                WHERE s.session_id LIKE ? OR s.session_id = ?
                GROUP BY s.session_id
                ORDER BY MAX(m.id) DESC
                LIMIT ?
                """,
                (f"{prefix}%", extra_session_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _row_to_grievance(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["user_confirmed"] = bool(d.get("user_confirmed"))
        d["status_history"] = json.loads(d.pop("status_history_json") or "[]")
        return d

    # ---- Traces (Langfuse-style structured telemetry) ----

    def save_trace(self, trace: dict[str, Any]) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO traces(
                    trace_id, session_id, user_id, user_role, timestamp,
                    user_query_masked, final_answer, detected_lang, cache_hit, model_name,
                    planner_json, retrieved_chunks_json, tool_calls_json, critic_json,
                    guardrail_flags_json, spans_json, prompt_tokens, completion_tokens,
                    total_latency_ms, step_latencies_json, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace["trace_id"],
                    trace.get("session_id", ""),
                    trace.get("user_id", "anonymous"),
                    trace.get("user_role", "citizen"),
                    trace.get("timestamp") or now_ist_iso(),
                    trace.get("user_query_masked", ""),
                    trace.get("final_answer", ""),
                    trace.get("detected_lang", "en"),
                    trace.get("cache_hit", "miss"),
                    trace.get("model_name", "Qwen/Qwen3-8B"),
                    json.dumps(trace.get("planner") or {}, ensure_ascii=False),
                    json.dumps(trace.get("retrieved_chunks") or [], ensure_ascii=False),
                    json.dumps(trace.get("tool_calls") or [], ensure_ascii=False),
                    json.dumps(trace.get("critic") or {}, ensure_ascii=False),
                    json.dumps(trace.get("guardrail_flags") or [], ensure_ascii=False),
                    json.dumps(trace.get("spans") or [], ensure_ascii=False),
                    int(trace.get("prompt_tokens") or 0),
                    int(trace.get("completion_tokens") or 0),
                    float(trace.get("total_latency_ms") or 0.0),
                    json.dumps(trace.get("step_latencies") or {}, ensure_ascii=False),
                    trace.get("status", "ok"),
                    trace.get("error_message"),
                ),
            )

    def list_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
        hide_erased: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        where: list[str] = []
        params: list[Any] = []
        if search and search.strip():
            like = f"%{search.strip()}%"
            where.append("(trace_id LIKE ? OR user_query_masked LIKE ? OR session_id LIKE ? OR user_id LIKE ?)")
            params.extend([like, like, like, like])
        if status and status.strip():
            where.append("status = ?")
            params.append(status.strip())
        if user_id and user_id.strip():
            where.append("user_id = ?")
            params.append(user_id.strip())
        if hide_erased:
            where.append("user_query_masked != '[ERASED_BY_USER]'")

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        with get_connection(self.db_path) as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM traces {where_sql}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM traces {where_sql} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [self._row_to_trace(r) for r in rows], int(total)

    def delete_erased_traces(self) -> int:
        with get_connection(self.db_path) as conn:
            return conn.execute(
                "DELETE FROM traces WHERE user_query_masked = '[ERASED_BY_USER]' OR session_id = '[ERASED]'"
            ).rowcount

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            return self._row_to_trace(row) if row else None

    @staticmethod
    def _row_to_trace(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["planner"] = json.loads(d.pop("planner_json") or "{}")
        d["retrieved_chunks"] = json.loads(d.pop("retrieved_chunks_json") or "[]")
        d["tool_calls"] = json.loads(d.pop("tool_calls_json") or "[]")
        d["critic"] = json.loads(d.pop("critic_json") or "{}")
        d["guardrail_flags"] = json.loads(d.pop("guardrail_flags_json") or "[]")
        d["spans"] = json.loads(d.pop("spans_json", "[]") or "[]")
        d["step_latencies"] = json.loads(d.pop("step_latencies_json") or "{}")
        return d
