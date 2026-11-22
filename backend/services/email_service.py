"""CPGRAMS Sandbox Confirmation Email Service (Real SMTP when configured + Built-in Sandbox Outbox Preview)."""

from __future__ import annotations

import asyncio
import html
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from backend.config import get_settings
from backend.db.repositories import Repository, now_ist_iso

logger = logging.getLogger(__name__)


def build_grievance_confirmation_email(
    receipt: dict[str, Any],
    draft: dict[str, Any],
    recipient_email: str,
    applicant_name: str = "Citizen Applicant",
) -> tuple[str, str, str]:
    """Return (subject, body_text, body_html) styled like an official CPGRAMS acknowledgement."""
    reg_no = receipt["registration_number"]
    ministry_name = receipt["ministry_name"]
    ministry_code = receipt["ministry_code"]
    scheme_name = draft.get("scheme_name") or "Central Government Scheme"
    submitted_at = receipt.get("submitted_at") or now_ist_iso()
    sla_days = receipt.get("expected_sla_days", 21)
    grievance_text = draft.get("grievance_text") or ""

    subject = f"[JanSahayak CPGRAMS Sandbox] Grievance Registered — {reg_no}"

    body_text = (
        f"Dear {applicant_name},\n\n"
        f"Your public grievance has been registered in the JanSahayak CPGRAMS Sandbox Gateway "
        f"(pending production API Setu onboarding).\n\n"
        f"REGISTRATION DETAILS\n"
        f"--------------------\n"
        f"Registration Number : {reg_no}\n"
        f"Status              : {receipt.get('status', 'SUBMITTED')} ({receipt.get('mode', 'sandbox').upper()})\n"
        f"Scheme              : {scheme_name}\n"
        f"Target Ministry     : {ministry_name} ({ministry_code})\n"
        f"Registered On       : {submitted_at}\n"
        f"Expected SLA        : {sla_days} Days\n\n"
        f"SUBMITTED GRIEVANCE TEXT\n"
        f"------------------------\n"
        f"{grievance_text}\n\n"
        f"NEXT STEPS FOR OFFICIAL PORTAL SUBMISSION\n"
        f"-----------------------------------------\n"
        f"Until institutional API Setu access is enabled, you may also paste the above verified text "
        f"directly on the official Government of India CPGRAMS portal: https://pgportal.gov.in/\n\n"
        f"Regards,\n"
        f"JanSahayak Citizen Welfare & Public Grievance Portal\n"
    )

    body_html = f"""<!doctype html>
<html>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#f7f6f2;padding:20px;color:#1e293b;">
  <div style="max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #cbd5e1;border-radius:12px;overflow:hidden;">
    <div style="height:5px;background:linear-gradient(90deg,#ff9933 33%,#ffffff 33% 66%,#138808 66%);"></div>
    <div style="background:#0f2942;color:#ffffff;padding:18px 24px;">
      <div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#fde68a;">JanSahayak • CPGRAMS Sandbox Gateway</div>
      <h2 style="margin:6px 0 0;font-size:20px;">Public Grievance Acknowledgement Receipt</h2>
    </div>
    <div style="padding:22px 24px;font-size:14px;line-height:1.6;">
      <p style="margin-top:0;">Dear <strong>{html.escape(applicant_name)}</strong>,</p>
      <p>Your public grievance has been successfully logged in the <strong>JanSahayak CPGRAMS Sandbox</strong> after your explicit confirmation. Below is your official tracking reference and complete complaint copy.</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:13px;">
        <tr style="background:#f0fdf4;"><td style="padding:8px 12px;border:1px solid #bbf7d0;font-weight:600;">Registration Number</td><td style="padding:8px 12px;border:1px solid #bbf7d0;font-family:monospace;font-size:15px;font-weight:700;color:#166534;">{html.escape(reg_no)}</td></tr>
        <tr><td style="padding:8px 12px;border:1px solid #e2e8f0;font-weight:600;">Status</td><td style="padding:8px 12px;border:1px solid #e2e8f0;">{html.escape(str(receipt.get('status', 'SUBMITTED')))} (SANDBOX)</td></tr>
        <tr><td style="padding:8px 12px;border:1px solid #e2e8f0;font-weight:600;">Target Central Ministry</td><td style="padding:8px 12px;border:1px solid #e2e8f0;">{html.escape(ministry_name)} ({html.escape(ministry_code)})</td></tr>
        <tr><td style="padding:8px 12px;border:1px solid #e2e8f0;font-weight:600;">Scheme</td><td style="padding:8px 12px;border:1px solid #e2e8f0;">{html.escape(scheme_name)}</td></tr>
        <tr><td style="padding:8px 12px;border:1px solid #e2e8f0;font-weight:600;">Registered On</td><td style="padding:8px 12px;border:1px solid #e2e8f0;">{html.escape(submitted_at)}</td></tr>
        <tr><td style="padding:8px 12px;border:1px solid #e2e8f0;font-weight:600;">Expected Disposal SLA</td><td style="padding:8px 12px;border:1px solid #e2e8f0;">{sla_days} Days</td></tr>
      </table>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin:14px 0;">
        <div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;margin-bottom:6px;">Submitted Complaint Text ({len(grievance_text)} / 2000 chars)</div>
        <pre style="white-space:pre-wrap;font-family:Consolas,monospace;font-size:12px;margin:0;color:#0f172a;">{html.escape(grievance_text)}</pre>
      </div>
      <p style="font-size:12px;color:#475569;">
        <strong>Official Portal Handoff:</strong> While institutional API Setu production credentials are pending, you can also lodge this exact verified text on
        <a href="https://pgportal.gov.in/" style="color:#0f2942;font-weight:600;">https://pgportal.gov.in/</a>.
      </p>
    </div>
  </div>
</body>
</html>"""
    return subject, body_text, body_html


def _send_smtp_sync(
    host: str,
    port: int,
    user: str,
    password: str,
    from_email: str,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str,
    use_tls: bool,
) -> None:
    msg = EmailMessage()
    clean_from = from_email if "<" in from_email else f"JanSahayak CPGRAMS Sandbox <{from_email}>"
    msg["From"] = clean_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype="html")

    clean_pass = password.replace(" ", "") if host.endswith("gmail.com") else password
    with smtplib.SMTP(host, port, timeout=12) as server:
        if use_tls:
            server.starttls()
        if user and clean_pass:
            server.login(user, clean_pass)
        server.send_message(msg)


async def dispatch_grievance_confirmation_email(
    receipt: dict[str, Any],
    draft: dict[str, Any],
    recipient_email: str | None,
    applicant_name: str | None = None,
    repo: Repository | None = None,
) -> dict[str, Any]:
    """Send real SMTP email if configured in .env, AND always store full preview in Sandbox Outbox."""
    settings = get_settings()
    repo = repo or Repository()

    clean_email = (recipient_email or "").strip() or "citizen-sandbox@jansahayak.local"
    clean_name = (applicant_name or "").strip() or "Citizen Applicant"

    subject, body_text, body_html = build_grievance_confirmation_email(
        receipt=receipt,
        draft=draft,
        recipient_email=clean_email,
        applicant_name=clean_name,
    )

    delivery_status = "SANDBOX_OUTBOX"
    delivery_detail = (
        "Stored in JanSahayak Sandbox Email Outbox (add SMTP_HOST/SMTP_USER/SMTP_PASSWORD in .env "
        "to deliver live emails to external inboxes)."
    )

    smtp_host = settings.smtp_host.strip()
    smtp_user = settings.smtp_user.strip()
    smtp_pass = settings.smtp_password.get_secret_value().strip()

    if smtp_host and "@" in clean_email and not clean_email.endswith(".local"):
        try:
            await asyncio.to_thread(
                _send_smtp_sync,
                smtp_host,
                settings.smtp_port,
                smtp_user,
                smtp_pass,
                settings.smtp_from_email or smtp_user or "noreply@jansahayak.local",
                clean_email,
                subject,
                body_text,
                body_html,
                settings.smtp_use_tls,
            )
            delivery_status = "SENT_SMTP"
            delivery_detail = f"Live confirmation email delivered to {clean_email} via {smtp_host}."
        except Exception as exc:
            logger.warning("SMTP email delivery failed (%s); preserved in Sandbox Outbox.", exc)
            delivery_status = "SANDBOX_OUTBOX_SMTP_FALLBACK"
            delivery_detail = f"SMTP error ({type(exc).__name__}); confirmation email saved in Sandbox Outbox."

    saved = repo.save_email_notification(
        {
            "registration_number": receipt["registration_number"],
            "draft_id": draft.get("draft_id", ""),
            "recipient_email": clean_email,
            "applicant_name": clean_name,
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
            "delivery_status": delivery_status,
            "delivery_detail": delivery_detail,
            "sent_at": now_ist_iso(),
        }
    )
    return saved
