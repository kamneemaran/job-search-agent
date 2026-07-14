"""Digest preference endpoints."""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from api.models import DigestPreferences
from api.supabase import get_user_client

router = APIRouter(prefix="/api/digest", tags=["digest"])


@router.get("/preferences", response_model=DigestPreferences)
async def get_digest_preferences(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(401, "Authorization required")

    sb = get_user_client(authorization)
    user = sb.auth.get_user().user
    result = sb.table("email_preferences").select("*").eq("user_id", user.id).maybe_single().execute()

    if not result.data:
        return DigestPreferences()

    row = result.data
    return DigestPreferences(
        enabled=row.get("enabled", True),
        frequency=row.get("frequency", "weekly"),
        email=row.get("email", ""),
    )


@router.put("/preferences", response_model=DigestPreferences)
async def update_digest_preferences(
    prefs: DigestPreferences,
    authorization: Optional[str] = Header(None),
):
    if not authorization:
        raise HTTPException(401, "Authorization required")

    sb = get_user_client(authorization)
    user = sb.auth.get_user().user

    data = {
        "user_id": user.id,
        "enabled": prefs.enabled,
        "frequency": prefs.frequency,
        "email": prefs.email,
    }

    sb.table("email_preferences").upsert(data, on_conflict="user_id").execute()

    return prefs
