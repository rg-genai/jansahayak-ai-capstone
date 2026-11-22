"""FastAPI Authentication & Persona Routes (/api/auth/*)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.db.repositories import Repository
from backend.services.auth import (
    authenticate_user,
    create_access_token,
    list_public_personas,
    require_user,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication & Personas"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.get("/personas")
async def get_demo_personas() -> dict[str, Any]:
    """Return available demo personas (Admin + 4 Citizens) for the login screen."""
    return {"personas": list_public_personas()}


@router.post("/login")
async def login(req: LoginRequest) -> dict[str, Any]:
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    # Seed the user's SQLite session with their persona's default Citizen Profile if empty
    repo = Repository()
    sess = repo.get_or_create_session(user["session_id"], preferred_language=user["preferred_language"])
    if not sess.get("profile"):
        repo.update_session(
            user["session_id"],
            profile=user["default_profile"],
            preferred_language=user["preferred_language"],
        )

    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me")
async def get_current_user(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {"user": user}
