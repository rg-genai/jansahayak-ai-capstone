"""FastAPI Scheme Explorer & HITL Grievance Confirmation, Sandbox Email & Tracking Routes."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.agent.tools import AgentToolbox, DraftGrievanceInput, SubmitOrTrackGrievanceInput
from backend.db.database import get_connection
from backend.db.repositories import Repository
from backend.guardrails.pii import mask_pii
from backend.services.auth import get_optional_user, require_admin
from backend.services.email_service import dispatch_grievance_confirmation_email
from backend.services.grievance_provider import get_grievance_provider

router = APIRouter(prefix="/api", tags=["Schemes & Grievances"])


class ConfirmGrievanceRequest(BaseModel):
    confirmed: bool = False
    grievance_text: str | None = Field(default=None, max_length=2000)
    subject: str | None = Field(default=None, max_length=250)
    applicant_name: str | None = Field(default=None, max_length=120)
    applicant_email: str | None = Field(default=None, max_length=180)
    simulate_fault: str | None = None


class DirectDraftGrievanceRequest(BaseModel):
    scheme_name: str = Field(..., min_length=2)
    ministry: str = ""
    issue_summary: str = Field(..., min_length=5)
    beneficiary_reference_id: str | None = None
    state: str | None = None
    district: str | None = None
    pending_since: str | None = None
    scheme_slug: str | None = None
    session_id: str = ""
    applicant_name: str | None = None
    applicant_email: str | None = None


class UpdateGrievanceStatusRequest(BaseModel):
    registration_number: str = Field(..., min_length=5)
    status: Literal["SUBMITTED", "UNDER_REVIEW", "ACTION_TAKEN", "DISPOSED"]
    note: str = Field(default="", max_length=400)


@router.get("/ministries")
async def list_ministries() -> dict[str, Any]:
    repo = Repository()
    items = repo.list_ministries()
    return {"count": len(items), "ministries": items}


@router.get("/schemes")
async def list_schemes(
    q: str | None = Query(default=None),
    ministry: str | None = Query(default=None),
    category: str | None = Query(default=None),
    dbt_only: bool | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    repo = Repository()
    items, total = repo.list_schemes(
        q=q,
        ministry=ministry,
        category=category,
        dbt_only=dbt_only,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/schemes/{slug}")
async def get_scheme_detail(slug: str) -> dict[str, Any]:
    repo = Repository()
    scheme = repo.get_scheme(slug)
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme '{slug}' not found.")
    faqs = repo.get_scheme_faqs(slug, limit=100)
    return {"scheme": scheme, "faqs": faqs}


@router.post("/grievances/draft")
async def create_grievance_draft(
    req: DirectDraftGrievanceRequest,
    user: dict[str, Any] | None = Depends(get_optional_user),
) -> dict[str, Any]:
    repo = Repository()
    toolbox = AgentToolbox(repo=repo)
    payload = req.model_dump()
    if not payload.get("session_id") and user:
        payload["session_id"] = user.get("session_id", "")
    draft = await toolbox.draft_grievance(DraftGrievanceInput.model_validate(payload))

    # Persist optional applicant name/email on the draft
    if req.applicant_name or req.applicant_email:
        with get_connection(repo.db_path) as conn:
            conn.execute(
                "UPDATE grievances SET applicant_name = ?, applicant_email = ? WHERE draft_id = ?",
                (req.applicant_name, req.applicant_email, draft["draft_id"]),
            )
        draft["applicant_name"] = req.applicant_name
        draft["applicant_email"] = req.applicant_email
    return {"draft": draft}


@router.post("/grievances/{draft_id}/confirm")
async def confirm_and_submit_grievance(
    draft_id: str,
    req: ConfirmGrievanceRequest,
    request: Request,
    user: dict[str, Any] | None = Depends(get_optional_user),
) -> dict[str, Any]:
    """Explicit Human-in-the-Loop (HITL) confirmation gate + CPGRAMS submission + confirmation email."""
    if not req.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Explicit user confirmation (confirmed=true) is mandatory before submitting a CPGRAMS grievance.",
        )

    repo = Repository()
    draft = repo.get_grievance_by_draft_id(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Grievance draft '{draft_id}' not found.")

    new_text = mask_pii(req.grievance_text if req.grievance_text is not None else draft["grievance_text"]).masked_text
    if len(new_text) > 2000:
        raise HTTPException(status_code=422, detail="Edited grievance text exceeds CPGRAMS 2,000-character limit.")
    new_subj = mask_pii(req.subject if req.subject is not None else draft["subject"]).masked_text
    app_name = req.applicant_name or draft.get("applicant_name") or (user or {}).get("display_name") or "Citizen Applicant"
    app_email = req.applicant_email or draft.get("applicant_email") or ""

    with get_connection(repo.db_path) as conn:
        conn.execute(
            """
            UPDATE grievances
            SET grievance_text = ?, char_count = ?, subject = ?, applicant_name = ?, applicant_email = ?
            WHERE draft_id = ?
            """,
            (new_text, len(new_text), new_subj, app_name, app_email, draft_id),
        )

    provider = get_grievance_provider(repo=repo, asgi_app=request.app)
    toolbox = AgentToolbox(repo=repo, grievance_provider=provider)
    receipt = await toolbox.submit_or_track_grievance(
        SubmitOrTrackGrievanceInput(
            action="submit",
            draft_id=draft_id,
            user_confirmed=True,
            simulate_fault=req.simulate_fault,
        )
    )
    if receipt.get("blocked") or receipt.get("error"):
        raise HTTPException(status_code=400, detail=receipt.get("error", "Grievance submission blocked."))

    refreshed_draft = repo.get_grievance_by_draft_id(draft_id) or draft
    email_notif = await dispatch_grievance_confirmation_email(
        receipt=receipt,
        draft=refreshed_draft,
        recipient_email=app_email,
        applicant_name=app_name,
        repo=repo,
    )

    return {"receipt": receipt, "email_notification": email_notif}


@router.get("/grievances")
async def list_grievances(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: dict[str, Any] | None = Depends(get_optional_user),
) -> dict[str, Any]:
    repo = Repository()
    effective_session = session_id
    if user and user.get("role") != "admin":
        effective_session = user.get("session_id")
    items = repo.list_grievances(session_id=effective_session, limit=limit)
    return {"count": len(items), "items": items}


@router.get("/grievances/emails/outbox")
async def list_grievance_emails(
    registration_number: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    repo = Repository()
    items = repo.list_email_notifications(registration_number=registration_number, limit=limit)
    return {"count": len(items), "items": items}


@router.patch("/grievances/status")
async def update_sandbox_grievance_status(
    req: UpdateGrievanceStatusRequest,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Admin Sandbox Portal action: advance ticket status to demonstrate end-to-end CPGRAMS tracking."""
    repo = Repository()
    updated = repo.update_grievance_status(
        registration_number=req.registration_number,
        new_status=req.status,
        note=req.note or f"Sandbox Ministry Nodal Officer updated status to {req.status}",
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Grievance '{req.registration_number}' not found.")
    return {"grievance": updated}


@router.get("/grievances/track")
async def track_grievance_query(
    request: Request,
    registration_number: str = Query(...),
) -> dict[str, Any]:
    repo = Repository()
    provider = get_grievance_provider(repo=repo, asgi_app=request.app)
    res = await provider.track_grievance(registration_number)
    if res.get("found"):
        res["emails"] = repo.list_email_notifications(registration_number=registration_number, limit=5)
    return res


@router.get("/grievances/{reg_no:path}")
async def track_grievance_path(reg_no: str, request: Request) -> dict[str, Any]:
    return await track_grievance_query(request=request, registration_number=reg_no)
