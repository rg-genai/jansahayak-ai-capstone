"""Persona-based Authentication & Role-Based Access Control (RBAC) for JanSahayak AI.

Provides 1 Admin persona (full access including Langfuse-style Trace & Eval Dashboard)
and 4 realistic Indian Citizen personas (scoped to Citizen Copilot, Scheme Explorer & My Grievances).
Uses stdlib HMAC-SHA256 signed tokens with zero extra external dependencies.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import get_settings

TOKEN_TTL_SECONDS = 24 * 3600
_BEARER_SCHEME = HTTPBearer(auto_error=False)


def _signing_secret() -> bytes:
    # Derive deterministic signing key from app env (falls back to local dev salt)
    settings = get_settings()
    raw = (
        os.environ.get("AUTH_SECRET_KEY")
        or settings.llm_api_key.get_secret_value()
        or "jansahayak-local-dev-rbac-secret-2026"
    )
    return hashlib.sha256(f"jansahayak-rbac::{raw}".encode("utf-8")).digest()


DEMO_PERSONAS: dict[str, dict[str, Any]] = {
    "admin": {
        "user_id": "usr-admin-01",
        "username": "admin",
        "password": "admin123",
        "display_name": "Rajesh Verma",
        "title": "System Admin & Track B Evaluator",
        "role": "admin",
        "session_id": "admin-session-01",
        "preferred_language": "en",
        "description": "Full access: Citizen Copilot, 649 Schemes, All Grievances, Langfuse Trace Debugger & Eval Exports.",
        "default_profile": {
            "preferred_language": "en",
        },
    },
    "ramesh": {
        "user_id": "usr-citizen-01",
        "username": "ramesh",
        "password": "citizen123",
        "display_name": "Ramesh Kumar",
        "title": "Rural Farmer (Uttar Pradesh)",
        "role": "citizen",
        "session_id": "citizen-ramesh-01",
        "preferred_language": "hi",
        "description": "46 yrs, OBC, Smallholder Farmer, ₹1.2L income, BPL — Hindi/Hinglish PM-KISAN & DBT persona.",
        "default_profile": {
            "age": 46,
            "gender": "Male",
            "state": "Uttar Pradesh",
            "annual_income_inr": 120000,
            "social_category": "OBC",
            "occupation": "Farmer",
            "is_bpl": True,
            "is_pwd": False,
            "preferred_language": "hi",
        },
    },
    "priya": {
        "user_id": "usr-citizen-02",
        "username": "priya",
        "password": "citizen123",
        "display_name": "Priya Sharma",
        "title": "B.Tech College Student (Maharashtra)",
        "role": "citizen",
        "session_id": "citizen-priya-02",
        "preferred_language": "en",
        "description": "19 yrs, OBC, First-gen B.Tech student, ₹1.8L family income — Central Scholarship persona.",
        "default_profile": {
            "age": 19,
            "gender": "Female",
            "state": "Maharashtra",
            "annual_income_inr": 180000,
            "social_category": "OBC",
            "occupation": "Student",
            "education_level": "B.Tech",
            "is_bpl": False,
            "is_pwd": False,
            "preferred_language": "en",
        },
    },
    "abdul": {
        "user_id": "usr-citizen-03",
        "username": "abdul",
        "password": "citizen123",
        "display_name": "Abdul Rahim",
        "title": "Traditional Carpenter Artisan (Gujarat)",
        "role": "citizen",
        "session_id": "citizen-abdul-03",
        "preferred_language": "hi",
        "description": "34 yrs, Minority, Carpenter seeking PM Vishwakarma toolkit & Mudra micro-credit.",
        "default_profile": {
            "age": 34,
            "gender": "Male",
            "state": "Gujarat",
            "annual_income_inr": 150000,
            "social_category": "Minority",
            "occupation": "Artisan",
            "is_bpl": False,
            "is_pwd": False,
            "preferred_language": "hi",
        },
    },
    "lakshmi": {
        "user_id": "usr-citizen-04",
        "username": "lakshmi",
        "password": "citizen123",
        "display_name": "Lakshmi Devi",
        "title": "Senior Citizen & Homemaker (Tamil Nadu)",
        "role": "citizen",
        "session_id": "citizen-lakshmi-04",
        "preferred_language": "ta",
        "description": "62 yrs, SC, BPL, ₹60K income — Pension, Ayushman Bharat & Tamil vernacular persona.",
        "default_profile": {
            "age": 62,
            "gender": "Female",
            "state": "Tamil Nadu",
            "annual_income_inr": 60000,
            "social_category": "SC",
            "occupation": "Senior Citizen",
            "is_bpl": True,
            "is_pwd": False,
            "preferred_language": "ta",
        },
    },
}


def public_user_view(persona: dict[str, Any]) -> dict[str, Any]:
    role = persona["role"]
    return {
        "user_id": persona["user_id"],
        "username": persona["username"],
        "display_name": persona["display_name"],
        "title": persona["title"],
        "role": role,
        "session_id": persona["session_id"],
        "preferred_language": persona["preferred_language"],
        "description": persona["description"],
        "default_profile": persona["default_profile"],
        "permissions": (
            ["copilot", "schemes", "grievances", "traces", "evals", "export_traces", "manage_traces"]
            if role == "admin"
            else ["copilot", "schemes", "grievances"]
        ),
    }


def list_public_personas() -> list[dict[str, Any]]:
    return [public_user_view(p) for p in DEMO_PERSONAS.values()]


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    key = (username or "").strip().lower()
    persona = DEMO_PERSONAS.get(key)
    if not persona:
        return None
    if not hmac.compare_digest(persona["password"], password or ""):
        return None
    return public_user_view(persona)


def create_access_token(user: dict[str, Any]) -> str:
    payload = {
        "sub": user["username"],
        "user_id": user["user_id"],
        "display_name": user["display_name"],
        "role": user["role"],
        "session_id": user["session_id"],
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(_signing_secret(), b64_payload.encode("ascii"), hashlib.sha256).digest()
    b64_sig = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{b64_payload}.{b64_sig}"


def verify_access_token(token: str) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    try:
        b64_payload, b64_sig = token.split(".", 1)
        expected_sig = hmac.new(_signing_secret(), b64_payload.encode("ascii"), hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode("ascii").rstrip("=")
        if not hmac.compare_digest(b64_sig, expected_b64):
            return None
        padded = b64_payload + "=" * ((4 - len(b64_payload) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        persona = DEMO_PERSONAS.get(payload.get("sub", ""))
        if not persona:
            return None
        return public_user_view(persona)
    except Exception:
        return None


def get_optional_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_BEARER_SCHEME),
) -> dict[str, Any] | None:
    token = creds.credentials if creds else request.query_params.get("token")
    if not token:
        return None
    return verify_access_token(token)


def require_user(
    user: dict[str, Any] | None = Depends(get_optional_user),
) -> dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in with a valid persona.")
    return user


def require_admin(
    user: dict[str, Any] | None = Depends(get_optional_user),
) -> dict[str, Any]:
    if not user:
        raise HTTPException(status_code=401, detail="Admin authentication required to view traces and evaluations.")
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin persona required to access Trace Inspector & Eval Dashboard.",
        )
    return user
