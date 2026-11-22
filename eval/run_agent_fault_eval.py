"""Track B Week 3 Evaluation: Agentic Fault-Injection & Tool Reliability Benchmark (15 Scenarios)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.state import CitizenProfile, PlannerOutput
from backend.agent.tools import (
    AgentToolbox,
    CheckEligibilityInput,
    DraftGrievanceInput,
    SearchSchemesInput,
    SubmitOrTrackGrievanceInput,
    parse_and_repair_json,
)
from backend.db.repositories import Repository
from backend.gateway.llm_client import get_llm_gateway
from backend.services.grievance_provider import SandboxCPGRAMSProvider
from backend.services.mock_cpgrams_router import router as mock_cpgrams_router

REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"


async def run_agent_fault_eval() -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    app = FastAPI()
    app.include_router(mock_cpgrams_router)
    repo = Repository()
    provider = SandboxCPGRAMSProvider(repo=repo, asgi_app=app)
    toolbox = AgentToolbox(repo=repo, grievance_provider=provider)
    llm = get_llm_gateway()

    scenarios: list[dict[str, Any]] = []

    # ---- Group A (5 scenarios): Malformed LLM JSON Repair ----
    broken_json_cases = [
        ("FI-01", "Think tag + markdown fence + trailing comma",
         '<think>thinking...</think>\n```json\n{"intent":"SCHEME_QA","profile_updates":{"age":42,},"tool_calls":[{"tool_name":"search_schemes","arguments":{"query":"PM-KISAN"}}],"reasoning":"ok",}\n```'),
        ("FI-02", "Prose preamble + valid JSON object",
         'Sure! Here is your plan: {"intent": "ELIGIBILITY_CHECK", "profile_updates": {"social_category": "OBC"}, "tool_calls": [{"tool_name": "search_schemes", "arguments": {"query": "OBC scholarship"}}], "reasoning": "check"} Hope that helps!'),
        ("FI-03", "Invalid intent enum requiring 1-shot LLM repair",
         '{"intent": "FIND_SCHEME_NOW", "profile_updates": {}, "tool_calls": [{"tool_name": "search_schemes", "arguments": {"query": "Ayushman Bharat"}}], "reasoning": "lookup"}'),
        ("FI-04", "Missing closing brace requiring 1-shot LLM repair",
         '{"intent": "GRIEVANCE_DRAFT", "profile_updates": {"state": "Bihar"}, "tool_calls": [{"tool_name": "draft_grievance", "arguments": {"scheme_name": "PM-KISAN", "issue_summary": "delayed payment"}}], "reasoning": "draft"'),
        ("FI-05", "Unquoted key / malformed tool_name requiring 1-shot LLM repair",
         '{intent: "SCHEME_QA", tool_calls: [{"tool_name": "search_schemes", "arguments": {"query": "Mudra loan"}}], reasoning: "loan"}'),
    ]
    json_recovered = 0
    for sid, desc, raw in broken_json_cases:
        parsed, diag = await parse_and_repair_json(raw, PlannerOutput, llm=llm, allow_llm_repair=True)
        ok = parsed is not None
        if ok:
            json_recovered += 1
        scenarios.append({
            "id": sid,
            "type": "json_repair",
            "description": desc,
            "passed": ok,
            "repair_method": diag.get("repair_method") or ("initial" if diag.get("initial_valid") else "failed"),
        })

    # ---- Group B (4 scenarios): HITL Gate Enforcement (MUST BE 100%) ----
    hitl_total = 0
    hitl_enforced = 0
    for idx, (scheme_name, ministry, issue) in enumerate([
        ("Pradhan Mantri Kisan Samman Nidhi", "MOAFW", "Delayed PM-KISAN installment for 2 cycles."),
        ("Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana", "MOHFW", "Hospital empanelment claim rejected unfairly."),
        ("PM Vishwakarma", "MSMEI", "Artisan toolkit voucher not credited after training."),
        ("Pradhan Mantri Mudra Yojana", "MOFIN", "Shishu loan application pending at bank branch for 60 days."),
    ], start=1):
        hitl_total += 1
        draft = await toolbox.draft_grievance(
            DraftGrievanceInput(
                scheme_name=scheme_name,
                ministry=ministry,
                issue_summary=issue,
                session_id=f"eval-hitl-{idx}",
            )
        )
        # Attempt unauthorized submit (user_confirmed=False)
        blocked = await toolbox.submit_or_track_grievance(
            SubmitOrTrackGrievanceInput(action="submit", draft_id=draft["draft_id"], user_confirmed=False)
        )
        enforced = bool(blocked.get("blocked")) and draft["char_count"] <= 2000
        if enforced:
            hitl_enforced += 1
        scenarios.append({
            "id": f"FI-0{5 + idx}",
            "type": "hitl_enforcement",
            "description": f"Block unconfirmed submit for {ministry} ({scheme_name[:32]})",
            "passed": enforced,
            "char_count": draft["char_count"],
        })

    # ---- Group C (3 scenarios): External Tool Fault Injection (503 / bad_json / missing ticket) ----
    fallback_total = 0
    fallback_ok = 0
    for idx, fault in enumerate(["503", "bad_json", "missing_ticket"], start=1):
        fallback_total += 1
        if fault == "missing_ticket":
            res = await toolbox.submit_or_track_grievance(
                SubmitOrTrackGrievanceInput(action="track", registration_number="MOAFW/E/2026/999999")
            )
            ok = (res.get("found") is False) and ("pgportal" in (res.get("message") or "").lower() or "not found" in (res.get("message") or "").lower())
        else:
            d = await toolbox.draft_grievance(
                DraftGrievanceInput(
                    scheme_name="Pradhan Mantri Kisan Samman Nidhi",
                    ministry="MOAFW",
                    issue_summary=f"Fault injection test {fault}",
                    session_id=f"eval-fault-{fault}",
                )
            )
            res = await toolbox.submit_or_track_grievance(
                SubmitOrTrackGrievanceInput(
                    action="submit",
                    draft_id=d["draft_id"],
                    user_confirmed=True,
                    simulate_fault=fault,
                )
            )
            ok = bool(res.get("fallback_used")) and bool(res.get("assisted_handoff_packet", {}).get("portal_url"))
        if ok:
            fallback_ok += 1
        scenarios.append({
            "id": f"FI-{9 + idx}",
            "type": "tool_fault_fallback",
            "description": f"CPGRAMS gateway fault injection: {fault}",
            "passed": ok,
        })

    # ---- Group D (3 scenarios): End-to-End Tool Selection & Execution Accuracy ----
    tool_total = 3
    tool_ok = 0
    # FI-13: search_schemes + check_eligibility
    s_res = await toolbox.search_schemes(SearchSchemesInput(query="PM-KISAN farmer Rs 6000", top_k=5))
    ok13 = bool(s_res["results"]) and "kisan" in s_res["results"][0]["scheme_name"].lower()
    if ok13:
        tool_ok += 1
    scenarios.append({"id": "FI-13", "type": "tool_accuracy", "description": "search_schemes returns PM-KISAN #1", "passed": ok13})

    # FI-14: check_eligibility structured verdict + documents
    e_res = await toolbox.check_eligibility(
        CheckEligibilityInput(
            scheme_slug=s_res["results"][0]["scheme_slug"],
            citizen_profile=CitizenProfile(age=46, occupation="Farmer", state="Uttar Pradesh"),
        )
    )
    ok14 = e_res["verdict"] in ("ELIGIBLE", "PARTIALLY_ELIGIBLE", "NEEDS_MORE_INFO", "NOT_ELIGIBLE") and bool(e_res["source_url"])
    if ok14:
        tool_ok += 1
    scenarios.append({"id": "FI-14", "type": "tool_accuracy", "description": "check_eligibility produces structured verdict & checklist", "passed": ok14})

    # FI-15: Confirmed CPGRAMS submit -> ticket ID -> live track round-trip
    d15 = await toolbox.draft_grievance(
        DraftGrievanceInput(
            scheme_name="PM Vishwakarma",
            ministry="MSMEI",
            issue_summary="Toolkit voucher delayed after skill training completion.",
            session_id="eval-fi-15",
        )
    )
    sub15 = await toolbox.submit_or_track_grievance(
        SubmitOrTrackGrievanceInput(action="submit", draft_id=d15["draft_id"], user_confirmed=True)
    )
    trk15 = await toolbox.submit_or_track_grievance(
        SubmitOrTrackGrievanceInput(action="track", registration_number=sub15.get("registration_number", ""))
    )
    ok15 = bool(sub15.get("registration_number", "").startswith("MSMEI/E/2026/")) and bool(trk15.get("found"))
    if ok15:
        tool_ok += 1
    scenarios.append({"id": "FI-15", "type": "tool_accuracy", "description": "Confirmed CPGRAMS submit -> track round-trip", "passed": ok15})

    metrics = {
        "tool_selection_accuracy": round(tool_ok / tool_total, 4),
        "json_repair_recovery_rate": round(json_recovered / len(broken_json_cases), 4),
        "graceful_fallback_rate": round(fallback_ok / fallback_total, 4),
        "hitl_enforcement_rate": round(hitl_enforced / hitl_total, 4),
        "overall_scenario_pass_rate": round(sum(1 for s in scenarios if s["passed"]) / len(scenarios), 4),
    }
    report = {
        "num_scenarios": len(scenarios),
        "metrics": metrics,
        "scenarios": scenarios,
    }
    (REPORTS_DIR / "agent_reliability.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# Agentic Reliability & Fault-Injection Benchmark (15 Scenarios)",
        "",
        "| Reliability Metric | Score | Target |",
        "| :--- | :---: | :---: |",
        f"| Tool Selection & Execution Accuracy | **{metrics['tool_selection_accuracy']*100:.1f}%** | >= 95% |",
        f"| Malformed JSON Repair Recovery Rate | **{metrics['json_repair_recovery_rate']*100:.1f}%** | >= 95% |",
        f"| External 503 / Bad JSON Graceful Fallback Rate | **{metrics['graceful_fallback_rate']*100:.1f}%** | >= 95% |",
        f"| Human-in-the-Loop (HITL) Gate Enforcement | **{metrics['hitl_enforcement_rate']*100:.1f}%** | **100%** |",
        f"| Overall Scenario Pass Rate | **{metrics['overall_scenario_pass_rate']*100:.1f}%** ({sum(1 for s in scenarios if s['passed'])}/{len(scenarios)}) | >= 95% |",
        "",
        "## Scenario Details",
        "| ID | Category | Description | Result |",
        "| :--- | :--- | :--- | :---: |",
    ]
    for s in scenarios:
        md_lines.append(f"| `{s['id']}` | `{s['type']}` | {s['description']} | {'PASS' if s['passed'] else 'FAIL'} |")
    (REPORTS_DIR / "agent_reliability.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print("[PASS] Agent reliability report saved to eval/reports/agent_reliability.json/.md")
    return report


if __name__ == "__main__":
    asyncio.run(run_agent_fault_eval())
