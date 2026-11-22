"""Milestone M3 tests: All 5 Pydantic tools, HITL enforcement, JSON repair, Mock CPGRAMS 503/bad_json fault recovery."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

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
from backend.services.grievance_provider import SandboxCPGRAMSProvider
from backend.services.mock_cpgrams_router import router as mock_cpgrams_router


def _make_mock_cpgrams_app() -> FastAPI:
    app = FastAPI()
    app.include_router(mock_cpgrams_router)
    return app


@pytest.mark.asyncio
async def test_grievance_draft_hitl_block_confirm_and_track():
    repo = Repository()
    app = _make_mock_cpgrams_app()
    provider = SandboxCPGRAMSProvider(repo=repo, asgi_app=app)
    toolbox = AgentToolbox(repo=repo, grievance_provider=provider)

    # 1. Draft grievance with Aadhaar embedded -> must mask Aadhaar & enforce <= 2000 chars
    draft = await toolbox.draft_grievance(
        DraftGrievanceInput(
            scheme_name="Pradhan Mantri Kisan Samman Nidhi",
            ministry="Ministry Of Agriculture and Farmers Welfare",
            issue_summary="My PM-KISAN installment has been delayed for 6 months. Aadhaar 4512 8891 3342.",
            state="Uttar Pradesh",
            district="Lucknow",
            pending_since="May 2026",
            session_id="test-hitl-sess",
        )
    )
    assert draft["ministry_code"] == "MOAFW"
    assert draft["within_cpgrams_limit"] is True
    assert draft["char_count"] <= 2000
    assert draft["requires_user_confirmation"] is True
    assert "4512 8891 3342" not in draft["grievance_text"]
    assert "[AADHAAR_MASKED:XXXX-XXXX-3342]" in draft["grievance_text"]

    # 2. Unconfirmed submit MUST be blocked by HITL gate
    blocked = await toolbox.submit_or_track_grievance(
        SubmitOrTrackGrievanceInput(
            action="submit",
            draft_id=draft["draft_id"],
            user_confirmed=False,
        )
    )
    assert blocked.get("blocked") is True
    assert "HITL_CONFIRMATION_REQUIRED" in blocked.get("error", "")

    # 3. Confirmed submit succeeds via Mock CPGRAMS and returns ticket ID + Assisted Handoff Packet
    receipt = await toolbox.submit_or_track_grievance(
        SubmitOrTrackGrievanceInput(
            action="submit",
            draft_id=draft["draft_id"],
            user_confirmed=True,
        )
    )
    assert receipt["mode"] == "sandbox"
    assert receipt["registration_number"].startswith("MOAFW/E/2026/")
    assert receipt["status"] == "SUBMITTED"
    assert receipt["assisted_handoff_packet"]["portal_url"] == "https://pgportal.gov.in/"

    # 4. Track submitted ticket
    tracked = await toolbox.submit_or_track_grievance(
        SubmitOrTrackGrievanceInput(
            action="track",
            registration_number=receipt["registration_number"],
        )
    )
    assert tracked["found"] is True
    assert tracked["registration_number"] == receipt["registration_number"]
    assert tracked["ministry_code"] == "MOAFW"


@pytest.mark.asyncio
async def test_cpgrams_503_and_bad_json_graceful_fallback():
    repo = Repository()
    app = _make_mock_cpgrams_app()
    provider = SandboxCPGRAMSProvider(repo=repo, asgi_app=app)
    toolbox = AgentToolbox(repo=repo, grievance_provider=provider)

    for fault in ("503", "bad_json"):
        draft = await toolbox.draft_grievance(
            DraftGrievanceInput(
                scheme_name="Pradhan Mantri Kisan Samman Nidhi",
                ministry="MOAFW",
                issue_summary=f"Testing fault recovery for {fault}",
                session_id=f"fault-{fault}",
            )
        )
        res = await toolbox.submit_or_track_grievance(
            SubmitOrTrackGrievanceInput(
                action="submit",
                draft_id=draft["draft_id"],
                user_confirmed=True,
                simulate_fault=fault,
            )
        )
        # Must gracefully fall back to Assisted Handoff Packet without losing the complaint!
        assert res["fallback_used"] is True
        assert res["mode"] == "assisted"
        assert res["assisted_handoff_packet"]["portal_url"] == "https://pgportal.gov.in/"
        assert res["assisted_handoff_packet"]["body"] == draft["grievance_text"]


@pytest.mark.asyncio
async def test_json_extraction_and_deterministic_repair():
    # Think block + markdown fence + trailing comma
    messy = """<think>Let me plan this carefully...</think>
```json
{
  "intent": "SCHEME_QA",
  "profile_updates": {"age": 46,},
  "tool_calls": [{"tool_name": "search_schemes", "arguments": {"query": "PM-KISAN"}}],
  "reasoning": "Search PM-KISAN details.",
}
```"""
    parsed, diag = await parse_and_repair_json(messy, PlannerOutput, allow_llm_repair=False)
    assert parsed is not None
    assert parsed.intent == "SCHEME_QA"
    assert parsed.profile_updates["age"] == 46
    assert diag["repaired"] is True
    assert diag["repair_method"] == "deterministic_regex"


@pytest.mark.asyncio
async def test_check_eligibility_tool_and_search_schemes():
    toolbox = AgentToolbox()
    search_res = await toolbox.search_schemes(
        SearchSchemesInput(query="PM-KISAN Pradhan Mantri Kisan Samman Nidhi farmer", top_k=5)
    )
    assert len(search_res["results"]) >= 3
    top_slug = search_res["results"][0]["scheme_slug"]

    elig = await toolbox.check_eligibility(
        CheckEligibilityInput(
            scheme_slug=top_slug,
            citizen_profile=CitizenProfile(age=46, occupation="Farmer", state="Uttar Pradesh", annual_income_inr=120000),
        )
    )
    assert elig["verdict"] in ("ELIGIBLE", "PARTIALLY_ELIGIBLE", "NOT_ELIGIBLE", "NEEDS_MORE_INFO")
    assert elig["source_url"].startswith("https://")
    assert isinstance(elig["documents_required"], list)
