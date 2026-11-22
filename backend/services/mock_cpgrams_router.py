"""Embedded CPGRAMS Mock Official API (/mock-cpgrams/v1) with 51-Ministry validation, <=2000-char cap & fault injection."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from backend.db.repositories import Repository, now_ist_iso
from backend.guardrails.pii import mask_pii
from backend.services.grievance_provider import build_assisted_handoff_packet

router = APIRouter(prefix="/mock-cpgrams/v1", tags=["Mock CPGRAMS Official API"])

CPGRAMS_MAX_CHARS = 2000


class MockCPGRAMSSubmitRequest(BaseModel):
    draft_id: str
    session_id: str = ""
    scheme_slug: str = ""
    scheme_name: str = ""
    ministry_code: str
    ministry_name: str
    subject: str = Field(..., min_length=3, max_length=250)
    grievance_text: str = Field(..., min_length=10, max_length=CPGRAMS_MAX_CHARS)
    beneficiary_reference_id: str | None = None
    state: str | None = None
    district: str | None = None
    pending_since: str | None = None


@router.get("/ministries")
async def list_cpgrams_ministries() -> dict[str, Any]:
    repo = Repository()
    ministries = repo.list_ministries()
    return {"count": len(ministries), "ministries": ministries}


@router.post("/grievances")
async def submit_cpgrams_grievance(
    req: MockCPGRAMSSubmitRequest,
    simulate_fault: str | None = Query(default=None, description="Fault injection: 503 | timeout | bad_json"),
) -> Any:
    # Week 3 Fault-Injection Support
    if simulate_fault == "503":
        raise HTTPException(status_code=503, detail="CPGRAMS upstream gateway temporarily unavailable (simulated 503)")
    if simulate_fault == "timeout":
        await asyncio.sleep(10.0)
        raise HTTPException(status_code=504, detail="CPGRAMS upstream gateway timeout")
    if simulate_fault == "bad_json":
        return Response(content="{broken-json-from-cpgrams", media_type="application/json", status_code=200)

    if len(req.grievance_text) > CPGRAMS_MAX_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Grievance text length ({len(req.grievance_text)}) exceeds CPGRAMS 2,000-character limit.",
        )

    repo = Repository()
    # Validate ministry code against canonical 51-ministry table
    resolved = repo.resolve_ministry(req.ministry_code) or repo.resolve_ministry(req.ministry_name)
    if not resolved:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid CPGRAMS ministry_code '{req.ministry_code}'. Must match one of the 51 Central Ministries.",
        )

    # Mask any stray PII before storing
    masked_text = mask_pii(req.grievance_text).masked_text
    masked_subject = mask_pii(req.subject).masked_text

    # Ensure draft exists in SQLite before marking submitted
    existing = repo.get_grievance_by_draft_id(req.draft_id)
    if not existing:
        repo.save_grievance_draft(
            {
                "draft_id": req.draft_id,
                "session_id": req.session_id,
                "scheme_slug": req.scheme_slug,
                "scheme_name": req.scheme_name,
                "ministry_code": resolved["ministry_code"],
                "ministry_name": resolved["ministry_name"],
                "subject": masked_subject,
                "grievance_text": masked_text,
                "char_count": len(masked_text),
                "mode": "sandbox",
                "beneficiary_reference_id": req.beneficiary_reference_id,
                "state": req.state,
                "district": req.district,
                "pending_since": req.pending_since,
            }
        )

    # Idempotency: if already submitted with a registration number, return existing receipt
    existing = repo.get_grievance_by_draft_id(req.draft_id)
    if existing and existing.get("registration_number"):
        reg_no = existing["registration_number"]
        status = existing["status"]
        submitted_at = existing["updated_at"]
    else:
        seq = repo.next_grievance_sequence(resolved["ministry_code"])
        reg_no = f"{resolved['ministry_code']}/E/2026/{seq:06d}"
        status = "SUBMITTED"
        updated = repo.mark_grievance_submitted(
            draft_id=req.draft_id,
            registration_number=reg_no,
            status=status,
            mode="sandbox",
            note="Registered via CPGRAMS Sandbox Official Gateway",
        )
        submitted_at = (updated or {}).get("updated_at") or now_ist_iso()

    draft_for_packet = {
        "ministry_code": resolved["ministry_code"],
        "ministry_name": resolved["ministry_name"],
        "subject": masked_subject,
        "grievance_text": masked_text,
    }
    return {
        "mode": "sandbox",
        "registration_number": reg_no,
        "status": status,
        "ministry_code": resolved["ministry_code"],
        "ministry_name": resolved["ministry_name"],
        "submitted_at": submitted_at,
        "expected_sla_days": 21,
        "assisted_handoff_packet": build_assisted_handoff_packet(draft_for_packet, registration_number=reg_no),
    }


@router.get("/grievances/track")
async def track_cpgrams_grievance_query(
    registration_number: str = Query(..., description="CPGRAMS registration ID e.g. MOAFW/E/2026/000001"),
    simulate_fault: str | None = Query(default=None),
) -> dict[str, Any]:
    if simulate_fault == "503":
        raise HTTPException(status_code=503, detail="CPGRAMS tracking service unavailable (simulated 503)")

    repo = Repository()
    rec = repo.get_grievance_by_reg_no(registration_number)
    if not rec:
        return {
            "found": False,
            "registration_number": registration_number,
            "status": "NOT_FOUND",
            "message": f"Registration number '{registration_number}' was not found.",
        }
    return {
        "found": True,
        "mode": rec["mode"],
        "registration_number": rec["registration_number"],
        "status": rec["status"],
        "ministry_code": rec["ministry_code"],
        "ministry_name": rec["ministry_name"],
        "scheme_name": rec["scheme_name"],
        "subject": rec["subject"],
        "submitted_at": rec["updated_at"],
        "expected_sla_days": 21,
        "status_history": rec.get("status_history", []),
        "assisted_handoff_packet": build_assisted_handoff_packet(rec, registration_number=rec["registration_number"]),
    }


@router.get("/grievances/{registration_number:path}")
async def track_cpgrams_grievance_path(registration_number: str) -> dict[str, Any]:
    return await track_cpgrams_grievance_query(registration_number=registration_number)
