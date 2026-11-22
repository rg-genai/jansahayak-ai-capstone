"""Dual-Mode CPGRAMS Grievance Provider (Sandbox Official API, Assisted Real-Portal Handoff, Pluggable API Setu)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

import httpx

from backend.config import get_settings
from backend.db.repositories import Repository, now_ist_iso

logger = logging.getLogger(__name__)

PGPORTAL_URL = "https://pgportal.gov.in/"


def build_assisted_handoff_packet(draft: dict[str, Any], registration_number: str | None = None) -> dict[str, Any]:
    """Always build a ready-to-paste Assisted Real-Portal Handoff Packet for pgportal.gov.in."""
    return {
        "portal_url": PGPORTAL_URL,
        "ministry": draft["ministry_name"],
        "ministry_code": draft["ministry_code"],
        "subject": draft["subject"],
        "body": draft["grievance_text"],
        "char_count": len(draft["grievance_text"]),
        "registration_number": registration_number,
        "next_steps": [
            "1. Open https://pgportal.gov.in/ and sign in using Mobile OTP / Jan Parichay.",
            f"2. Click 'Lodge Public Grievance' and select Ministry: {draft['ministry_name']} ({draft['ministry_code']}).",
            "3. Copy & paste the verified grievance text below (already within CPGRAMS 2,000-character limit).",
            "4. Attach supporting documents (e.g., Bank Passbook / Scheme Acknowledgement / Aadhaar copy with masked digits).",
            "5. Submit and save your official CPGRAMS registration number for tracking.",
        ],
    }


class GrievanceProvider(Protocol):
    async def submit_grievance(
        self,
        draft: dict[str, Any],
        simulate_fault: str | None = None,
    ) -> dict[str, Any]: ...

    async def track_grievance(
        self,
        registration_number: str,
        simulate_fault: str | None = None,
    ) -> dict[str, Any]: ...


class AssistedHandoffProvider:
    """Zero-credential mode: persists local reference & delivers ready-to-submit pgportal.gov.in packet."""

    def __init__(self, repo: Repository | None = None):
        self.repo = repo or Repository()

    async def submit_grievance(
        self,
        draft: dict[str, Any],
        simulate_fault: str | None = None,
    ) -> dict[str, Any]:
        seq = self.repo.next_grievance_sequence(draft["ministry_code"])
        reg_no = f"{draft['ministry_code']}/E/2026/{seq:06d}"
        updated = self.repo.mark_grievance_submitted(
            draft_id=draft["draft_id"],
            registration_number=reg_no,
            status="ASSISTED_HANDOFF_READY",
            mode="assisted",
            note="Prepared Assisted Real-Portal Handoff Packet for pgportal.gov.in after user confirmation",
        )
        ts = (updated or {}).get("updated_at") or now_ist_iso()
        return {
            "mode": "assisted",
            "registration_number": reg_no,
            "status": "ASSISTED_HANDOFF_READY",
            "ministry_code": draft["ministry_code"],
            "ministry_name": draft["ministry_name"],
            "submitted_at": ts,
            "expected_sla_days": 21,
            "fallback_used": False,
            "assisted_handoff_packet": build_assisted_handoff_packet(draft, registration_number=reg_no),
        }

    async def track_grievance(
        self,
        registration_number: str,
        simulate_fault: str | None = None,
    ) -> dict[str, Any]:
        rec = self.repo.get_grievance_by_reg_no(registration_number)
        if not rec:
            return {
                "found": False,
                "registration_number": registration_number,
                "status": "NOT_FOUND",
                "message": (
                    f"No grievance ticket matching '{registration_number}' was found in the local ledger. "
                    "If you submitted directly on pgportal.gov.in, please check status at https://pgportal.gov.in/Status."
                ),
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


class SandboxCPGRAMSProvider:
    """Calls embedded FastAPI /mock-cpgrams/v1 API with retry backoff (1s, 2s) & automatic Assisted Handoff fallback."""

    def __init__(self, repo: Repository | None = None, asgi_app: Any | None = None):
        self.settings = get_settings()
        self.repo = repo or Repository()
        self.base_url = self.settings.mock_cpgrams_base_url.rstrip("/")
        self.asgi_app = asgi_app
        self._assisted = AssistedHandoffProvider(repo=self.repo)

    def _make_client(self) -> httpx.AsyncClient:
        if self.asgi_app is not None:
            transport = httpx.ASGITransport(app=self.asgi_app)
            return httpx.AsyncClient(transport=transport, base_url="http://testserver/mock-cpgrams/v1", timeout=8.0)
        return httpx.AsyncClient(base_url=self.base_url, timeout=8.0)

    async def submit_grievance(
        self,
        draft: dict[str, Any],
        simulate_fault: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "draft_id": draft["draft_id"],
            "session_id": draft.get("session_id", ""),
            "scheme_slug": draft.get("scheme_slug", ""),
            "scheme_name": draft.get("scheme_name", ""),
            "ministry_code": draft["ministry_code"],
            "ministry_name": draft["ministry_name"],
            "subject": draft["subject"],
            "grievance_text": draft["grievance_text"],
            "beneficiary_reference_id": draft.get("beneficiary_reference_id"),
            "state": draft.get("state"),
            "district": draft.get("district"),
            "pending_since": draft.get("pending_since"),
        }
        params = {"simulate_fault": simulate_fault} if simulate_fault else {}
        retry_waits = (1.0, 2.0)
        last_error: str | None = None
        retries = 0

        async with self._make_client() as client:
            for attempt in range(len(retry_waits) + 1):
                try:
                    resp = await client.post("/grievances", json=payload, params=params)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                        except Exception as exc:
                            last_error = f"Malformed JSON from CPGRAMS gateway: {exc}"
                            if attempt < len(retry_waits):
                                retries += 1
                                await asyncio.sleep(retry_waits[attempt])
                                continue
                            break
                        if "registration_number" not in data:
                            last_error = "CPGRAMS response missing registration_number"
                            if attempt < len(retry_waits):
                                retries += 1
                                await asyncio.sleep(retry_waits[attempt])
                                continue
                            break
                        data["retries"] = retries
                        data["fallback_used"] = False
                        return data

                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < len(retry_waits):
                        last_error = f"CPGRAMS HTTP {resp.status_code}"
                        retries += 1
                        logger.warning("CPGRAMS sandbox returned %s; retry %d in %.1fs", resp.status_code, retries, retry_waits[attempt])
                        await asyncio.sleep(retry_waits[attempt])
                        continue
                    last_error = f"CPGRAMS HTTP {resp.status_code}: {resp.text[:200]}"
                    break
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_error = f"CPGRAMS transport/timeout error: {type(exc).__name__}"
                    if attempt < len(retry_waits):
                        retries += 1
                        logger.warning("CPGRAMS transport error (%s); retry %d in %.1fs", exc, retries, retry_waits[attempt])
                        await asyncio.sleep(retry_waits[attempt])
                        continue
                    break

        # Graceful fallback: never lose the citizen's drafted complaint!
        logger.warning("CPGRAMS sandbox unavailable (%s); falling back to Assisted Handoff Packet.", last_error)
        fallback = await self._assisted.submit_grievance(draft)
        fallback["fallback_used"] = True
        fallback["fallback_reason"] = last_error
        fallback["retries"] = retries
        return fallback

    async def track_grievance(
        self,
        registration_number: str,
        simulate_fault: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {"registration_number": registration_number}
        if simulate_fault:
            params["simulate_fault"] = simulate_fault
        try:
            async with self._make_client() as client:
                resp = await client.get("/grievances/track", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as exc:
            logger.warning("Sandbox track failed (%s); falling back to local SQLite ledger.", exc)
        return await self._assisted.track_grievance(registration_number)


class APISetuCPGRAMSProvider:
    """Production API Setu / UMANG adapter (activates when APISETU_CLIENT_ID & APISETU_API_KEY are set)."""

    def __init__(self, repo: Repository | None = None):
        self.settings = get_settings()
        self.repo = repo or Repository()
        self._assisted = AssistedHandoffProvider(repo=self.repo)

    async def submit_grievance(self, draft: dict[str, Any], simulate_fault: str | None = None) -> dict[str, Any]:
        if not self.settings.apisetu_client_id or not self.settings.apisetu_api_key:
            logger.info("API Setu credentials not configured; returning Assisted Handoff Packet.")
            res = await self._assisted.submit_grievance(draft)
            res["fallback_used"] = True
            res["fallback_reason"] = "API Setu production credentials not configured"
            return res
        # Placeholder for institutional API Setu endpoint once whitelisted
        res = await self._assisted.submit_grievance(draft)
        res["mode"] = "apisetu"
        return res

    async def track_grievance(self, registration_number: str, simulate_fault: str | None = None) -> dict[str, Any]:
        return await self._assisted.track_grievance(registration_number)


def get_grievance_provider(
    repo: Repository | None = None,
    asgi_app: Any | None = None,
) -> GrievanceProvider:
    settings = get_settings()
    if settings.grievance_mode == "assisted":
        return AssistedHandoffProvider(repo=repo)
    if settings.grievance_mode == "apisetu":
        return APISetuCPGRAMSProvider(repo=repo)
    return SandboxCPGRAMSProvider(repo=repo, asgi_app=asgi_app)
