"""FastAPI Observability Routes: /api/health, Admin-only Langfuse-Style /api/traces, Exports & /api/evals."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.config import PROJECT_ROOT, get_settings
from backend.db.database import get_connection
from backend.db.repositories import Repository
from backend.services.auth import require_admin

router = APIRouter(prefix="/api", tags=["Observability & Evals"])

EVAL_REPORT_REGISTRY: dict[str, dict[str, str]] = {
    "retrieval_ablation": {
        "eval_trace_id": "EVAL-RET-R1R4",
        "title": "4-Way Retrieval Ablation (R1-R4)",
        "json_file": "retrieval_ablation.json",
        "md_file": "retrieval_ablation.md",
    },
    "prompt_comparison": {
        "eval_trace_id": "EVAL-PRM-P1P3",
        "title": "3-Way Prompting Strategy Comparison (P1-P3)",
        "json_file": "prompt_comparison.json",
        "md_file": "prompt_comparison.md",
    },
    "agent_reliability": {
        "eval_trace_id": "EVAL-AGT-FI15",
        "title": "Agent Fault-Injection Reliability (15 Scenarios)",
        "json_file": "agent_reliability.json",
        "md_file": "agent_reliability.md",
    },
    "red_team_report": {
        "eval_trace_id": "EVAL-RTM-20",
        "title": "Red-Team Adversarial Safety & Failure Taxonomy (20 Tests)",
        "json_file": "red_team_report.json",
        "md_file": "red_team_report.md",
    },
    "gold60_comprehensive_eval": {
        "eval_trace_id": "EVAL-GOLD60-GEMINI",
        "title": "60-Pair Zero-Leakage Gold QA (Vanilla vs RAG, ROUGE/BLEU/BERTScore & Unbiased Gemini Judge)",
        "json_file": "gold60_comprehensive_eval.json",
        "md_file": "gold60_comprehensive_eval.md",
    },
    "gold_eval": {
        "eval_trace_id": "EVAL-GOLD-LOOP",
        "title": "60-Pair Gold QA Full-Agent Ablation (FAQ Excluded, Top-k 1/3/5 & Gemini 3.5 Flash-Lite Judge)",
        "json_file": "gold_eval.json",
        "md_file": "gold_eval.md",
    },
    "task_eval": {
        "eval_trace_id": "EVAL-TASK-80",
        "title": "80-Task End-to-End Agent Suite (Reflector Loop vs Single Pass)",
        "json_file": "task_eval.json",
        "md_file": "task_eval.md",
    },
    "chunking_eval": {
        "eval_trace_id": "EVAL-CHUNK-5WAY",
        "title": "5-Way Chunking Ablation (440/256/128-tok & Fixed Windows)",
        "json_file": "chunking_eval.json",
        "md_file": "chunking_eval.md",
    },
    "failure_taxonomy": {
        "eval_trace_id": "EVAL-FAIL-TAX",
        "title": "Root-Cause Failure Taxonomy (Human Audited, Cohen's kappa 0.92)",
        "json_file": "failure_taxonomy.json",
        "md_file": "failure_taxonomy.md",
    },
}


def _format_trace_markdown(trace: dict[str, Any]) -> str:
    lines = [
        f"# JanSahayak AI — Execution Trace Debug Report (`{trace['trace_id']}`)",
        "",
        "## Trace Metadata",
        f"- **Trace ID:** `{trace['trace_id']}`",
        f"- **Timestamp:** `{trace.get('timestamp')}`",
        f"- **User Persona:** `{trace.get('user_id', 'anonymous')}` (`{trace.get('user_role', 'citizen')}`)",
        f"- **Session ID:** `{trace.get('session_id')}`",
        f"- **Model:** `{trace.get('model_name', 'Qwen/Qwen3-8B')}`",
        f"- **Language:** `{trace.get('detected_lang')}` | **Cache:** `{trace.get('cache_hit')}` | **Status:** `{trace.get('status')}`",
        f"- **Total Latency:** `{trace.get('total_latency_ms', 0):.1f} ms`",
        f"- **Tokens:** `{trace.get('prompt_tokens', 0)}` prompt + `{trace.get('completion_tokens', 0)}` completion = `{int(trace.get('prompt_tokens', 0)) + int(trace.get('completion_tokens', 0))}` total",
        "",
        "## User Input (PII-Masked)",
        "```text",
        str(trace.get("user_query_masked") or ""),
        "```",
        "",
        "## Final Assistant Output",
        "```markdown",
        str(trace.get("final_answer") or "(No output captured — check earlier trace before v1.1 upgrade)"),
        "```",
        "",
        "## Guardrail Flags",
        f"- {', '.join(trace.get('guardrail_flags') or ['None'])}",
        "",
        "## Step Latency Waterfall",
        "| Step | Duration (ms) |",
        "| :--- | ---: |",
    ]
    for step, ms in (trace.get("step_latencies") or {}).items():
        lines.append(f"| `{step}` | {float(ms):.1f} |")

    spans = trace.get("spans") or []
    if spans:
        lines.extend([
            "",
            "## Structured Observation Spans (Langfuse-style)",
            "| Span ID | Name | Type | Start (+ms) | Duration (ms) | Tokens | Status | Error |",
            "| :--- | :--- | :--- | ---: | ---: | ---: | :---: | :--- |",
        ])
        for sp in spans:
            toks = (sp.get("tokens") or {}).get("total", 0)
            lines.append(
                f"| `{sp.get('span_id')}` | {sp.get('name')} | `{sp.get('type')}` | "
                f"{sp.get('start_offset_ms', 0)} | {sp.get('duration_ms', 0)} | {toks} | "
                f"`{sp.get('status')}` | {sp.get('error') or '-'} |"
            )

    chunks = trace.get("retrieved_chunks") or []
    if chunks:
        lines.extend([
            "",
            "## Hybrid Retrieval & Cross-Encoder Scores",
            "| # | Scheme | Section | BM25 | Dense | RRF | Rerank | URL |",
            "| :---: | :--- | :--- | ---: | ---: | ---: | ---: | :--- |",
        ])
        for i, c in enumerate(chunks, start=1):
            sc = c.get("scores") or {}
            lines.append(
                f"| {i} | {c.get('scheme_name')} | `{c.get('section')}` | "
                f"{sc.get('bm25', 0)} | {sc.get('dense', 0)} | {sc.get('rrf', 0)} | "
                f"{sc.get('rerank', 0)} | {c.get('source_url', '')} |"
            )

    lines.extend([
        "",
        "## Planner JSON",
        "```json",
        json.dumps(trace.get("planner") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Tool Calls JSON",
        "```json",
        json.dumps(trace.get("tool_calls") or [], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Critic Audit JSON",
        "```json",
        json.dumps(trace.get("critic") or {}, indent=2, ensure_ascii=False),
        "```",
    ])
    return "\n".join(lines) + "\n"


@router.get("/health")
async def health_check() -> dict[str, Any]:
    settings = get_settings()
    repo = Repository()
    counts = repo.get_counts()

    emb_path = settings.index_abs_dir / "embeddings.npy"
    bm25_path = settings.index_abs_dir / "bm25.pkl"
    manifest_path = settings.index_abs_dir / "index_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    return {
        "status": "ok",
        "service": "JanSahayak AI",
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "reranker_model": settings.reranker_model,
        "grievance_mode": settings.grievance_mode,
        "certs": {
            "llm_ca_exists": settings.llm_ca_cert_abs.exists(),
            "embedding_ca_exists": settings.embedding_ca_cert_abs.exists(),
        },
        "index_ready": emb_path.exists() and bm25_path.exists() and counts["chunks"] > 0,
        "counts": counts,
        "manifest": manifest,
    }


@router.get("/traces")
async def list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    hide_erased: bool = Query(default=False),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    repo = Repository()
    items, total = repo.list_traces(
        limit=limit,
        offset=offset,
        search=search,
        status=status,
        user_id=user_id,
        hide_erased=hide_erased,
    )

    with get_connection(repo.db_path) as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total_traces,
                AVG(total_latency_ms) as avg_latency_ms,
                SUM(CASE WHEN cache_hit != 'miss' THEN 1 ELSE 0 END) as cache_hits,
                SUM(CASE WHEN status = 'blocked_by_guardrail' THEN 1 ELSE 0 END) as guardrail_blocks,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens
            FROM traces
            WHERE (? = 0 OR user_query_masked != '[ERASED_BY_USER]')
            """,
            (1 if hide_erased else 0,),
        ).fetchone()

    total_t = int(row["total_traces"] or 0)
    cache_hits = int(row["cache_hits"] or 0)
    summary = {
        "total_traces": total_t,
        "avg_latency_ms": round(float(row["avg_latency_ms"] or 0.0), 1),
        "cache_hits": cache_hits,
        "cache_hit_rate": round((cache_hits / total_t) * 100.0, 1) if total_t else 0.0,
        "guardrail_blocks": int(row["guardrail_blocks"] or 0),
        "total_prompt_tokens": int(row["total_prompt_tokens"] or 0),
        "total_completion_tokens": int(row["total_completion_tokens"] or 0),
    }
    return {"total": total, "limit": limit, "offset": offset, "summary": summary, "items": items}


@router.delete("/traces/cleanup")
async def cleanup_erased_traces(
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Remove anonymized [ERASED_BY_USER] test traces for a clean admin console."""
    repo = Repository()
    removed = repo.delete_erased_traces()
    return {"status": "ok", "removed_traces": removed}


@router.get("/traces/export/all")
async def export_all_traces(
    format: Literal["json", "csv"] = Query(default="json"),
    hide_erased: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=1000),
    _admin: dict[str, Any] = Depends(require_admin),
) -> Response:
    repo = Repository()
    items, _ = repo.list_traces(limit=limit, offset=0, hide_erased=hide_erased)
    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "trace_id", "timestamp", "user_id", "user_role", "session_id", "detected_lang",
            "cache_hit", "status", "total_latency_ms", "prompt_tokens", "completion_tokens",
            "guardrail_flags", "user_query_masked",
        ])
        for t in items:
            writer.writerow([
                t["trace_id"], t["timestamp"], t.get("user_id", ""), t.get("user_role", ""),
                t["session_id"], t["detected_lang"], t["cache_hit"], t["status"],
                t["total_latency_ms"], t["prompt_tokens"], t["completion_tokens"],
                ";".join(t.get("guardrail_flags") or []), t["user_query_masked"],
            ])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="jansahayak_traces_export.csv"'},
        )
    return Response(
        content=json.dumps({"count": len(items), "traces": items}, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="jansahayak_traces_export.json"'},
    )


@router.get("/traces/{trace_id}/export")
async def export_single_trace(
    trace_id: str,
    format: Literal["json", "md"] = Query(default="json"),
    _admin: dict[str, Any] = Depends(require_admin),
) -> Response:
    repo = Repository()
    trace = repo.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")
    if format == "md":
        md = _format_trace_markdown(trace)
        return Response(
            content=md,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="trace_{trace_id}.md"'},
        )
    return Response(
        content=json.dumps(trace, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="trace_{trace_id}.json"'},
    )


@router.get("/traces/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    repo = Repository()
    trace = repo.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")
    return {"trace": trace}


@router.get("/evals/summary")
async def get_evals_summary(
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    reports_dir: Path = PROJECT_ROOT / "eval" / "reports"
    reports: dict[str, Any] = {}
    available_count = 0
    for key, meta in EVAL_REPORT_REGISTRY.items():
        path = reports_dir / meta["json_file"]
        if path.exists():
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
                parsed["eval_trace_id"] = meta["eval_trace_id"]
                parsed["report_key"] = key
                reports[key] = parsed
                available_count += 1
            except Exception as exc:
                reports[key] = {"error": f"Failed to parse {path.name}: {exc}"}
        else:
            reports[key] = None

    return {
        "available_reports": available_count,
        "total_expected": len(EVAL_REPORT_REGISTRY),
        "reports": reports,
    }


@router.get("/evals/export/{report_key}")
async def export_eval_report(
    report_key: str,
    format: Literal["json", "md"] = Query(default="json"),
    _admin: dict[str, Any] = Depends(require_admin),
) -> Response:
    meta = EVAL_REPORT_REGISTRY.get(report_key)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown eval report '{report_key}'.")
    reports_dir: Path = PROJECT_ROOT / "eval" / "reports"
    fname = meta["md_file"] if format == "md" else meta["json_file"]
    path = reports_dir / fname
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Report file '{fname}' not generated yet.")
    media = "text/markdown; charset=utf-8" if format == "md" else "application/json"
    return Response(
        content=path.read_text(encoding="utf-8"),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{meta["eval_trace_id"]}_{fname}"'},
    )
