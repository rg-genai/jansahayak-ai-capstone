"""Quick 3-second SMTP verification script for JanSahayak CPGRAMS confirmation emails.

Usage:
    .\.venv\Scripts\python.exe scripts\test_email.py recipient@example.com
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings
from backend.services.email_service import dispatch_grievance_confirmation_email


async def main() -> int:
    if len(sys.argv) < 2 or "@" not in sys.argv[1]:
        print("Usage: python scripts/test_email.py <recipient_email>")
        return 1

    recipient = sys.argv[1].strip()
    settings = get_settings()
    if not settings.smtp_host:
        print("[FAIL] SMTP_HOST is blank in .env. Please fill SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD first.")
        return 1

    print(f"[INFO] Testing SMTP via {settings.smtp_host}:{settings.smtp_port} -> {recipient} ...")
    sample_receipt = {
        "registration_number": "MOAFW/E/2026/000999",
        "status": "SUBMITTED",
        "mode": "sandbox",
        "ministry_code": "MOAFW",
        "ministry_name": "Ministry Of Agriculture and Farmers Welfare",
        "expected_sla_days": 21,
    }
    sample_draft = {
        "draft_id": "DRAFT-TEST01",
        "scheme_name": "Pradhan Mantri Kisan Samman Nidhi",
        "grievance_text": (
            "To,\nThe Public Grievance Officer,\nMinistry Of Agriculture and Farmers Welfare.\n\n"
            "Subject: Test CPGRAMS Sandbox Confirmation Email\n\n"
            "Respected Sir/Madam,\nThis is a live test confirming that JanSahayak AI's CPGRAMS Sandbox "
            "email acknowledgement system is active and delivering confirmation receipts."
        ),
    }

    res = await dispatch_grievance_confirmation_email(
        receipt=sample_receipt,
        draft=sample_draft,
        recipient_email=recipient,
        applicant_name="Test Citizen",
    )
    print(f"[RESULT] Status: {res['delivery_status']} | Detail: {res['delivery_detail']}")
    return 0 if res["delivery_status"] == "SENT_SMTP" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
