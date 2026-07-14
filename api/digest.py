"""Digest preference and send endpoints."""
import os
import sys
import threading
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from api.models import DigestPreferences, DigestSendRequest
from api.supabase import get_user_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import daily_scan as ds

router = APIRouter(prefix="/api/digest", tags=["digest"])
_profile_lock = threading.Lock()


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


@router.post("/send")
async def send_digest(
    req: DigestSendRequest,
    authorization: Optional[str] = Header(None),
):
    if not authorization:
        raise HTTPException(401, "Authorization required")

    sb = get_user_client(authorization)
    user = sb.auth.get_user().user

    # Get user profile
    profile_row = sb.table("profiles").select("*").eq("id", user.id).maybe_single().execute()
    if not profile_row.data:
        raise HTTPException(400, "Profile not found. Upload a resume first.")

    row = profile_row.data
    core_skills = row.get("core_skills") or []
    if not core_skills:
        raise HTTPException(400, "No core skills found. Upload a resume first.")

    profile = {
        "core_skills": core_skills,
        "years_experience": row.get("years_experience", 0) or 0,
        "current_role": row.get("current_role", ""),
    }

    to_email = req.email or row.get("email") or user.email or ""

    if req.schedule == "now":
        try:
            ds._rebuild_precompiled_patterns()
        except Exception:
            pass

        all_sources = (
            ds.JOB_SOURCES + ds.EU_JOB_SOURCES + ds.GLOBAL_JOB_SOURCES
            + ds.APAC_JOB_SOURCES + ds.US_CANADA_JOB_SOURCES
            + ds.MIDDLE_EAST_JOB_SOURCES + ds.REMOTE_JOB_SOURCES
        )

        results = []
        seen = set()

        for source in all_sources:
            try:
                jobs = ds.fetch_jobs_from_source(source)
            except Exception:
                continue
            for job in jobs:
                key = (job.get("title", "").lower(), job.get("company", "").lower())
                if key in seen:
                    continue
                seen.add(key)
                with _profile_lock:
                    orig_skills = ds.PROFILE.get("core_skills")
                    orig_years = ds.PROFILE.get("years_experience")
                    try:
                        ds.PROFILE["core_skills"] = profile["core_skills"]
                        ds.PROFILE["years_experience"] = profile["years_experience"]
                        score, note = ds.score_job(
                            job.get("title", ""), job.get("description", ""),
                            job.get("company", ""), job.get("location", ""),
                        )
                    finally:
                        ds.PROFILE["core_skills"] = orig_skills
                        ds.PROFILE["years_experience"] = orig_years

                if score >= 65:
                    salary_info = ds.get_salary_info(
                        job.get("company", ""), job.get("title", ""), job.get("description", ""),
                    )
                    results.append({
                        "title": job.get("title", ""),
                        "company": job.get("company", ""),
                        "score": score,
                        "location": job.get("location", ""),
                        "salary": ds._format_salary(salary_info) if salary_info else "",
                        "url": job.get("url", ""),
                    })

        results.sort(key=lambda x: x["score"], reverse=True)

        if not results:
            return {"message": "No matches above threshold found. Check back later.", "sent": False, "count": 0}

        from daily_scan import build_email_html, send_email
        html = build_email_html(results)
        ok = send_email(html, subject=f"Your Job Matches — {len(results)} opportunities — {datetime.now().strftime('%d %b %Y')}")

        # Update last_sent_at
        try:
            sb.table("email_preferences").upsert({
                "user_id": user.id,
                "last_sent_at": datetime.now().isoformat(),
            }, on_conflict="user_id").execute()
        except Exception:
            pass

        return {
            "message": f"Sent {len(results)} matches to {to_email}",
            "sent": ok,
            "count": len(results),
        }

    elif req.schedule == "never":
        sb.table("email_preferences").upsert({
            "user_id": user.id, "enabled": False, "frequency": "never",
        }, on_conflict="user_id").execute()
        return {"message": "Digest disabled", "schedule": "never", "sent": False, "count": 0}

    elif req.schedule in ("tomorrow", "weekly", "monthly"):
        sb.table("email_preferences").upsert({
            "user_id": user.id, "enabled": True, "frequency": req.schedule,
            "email": to_email,
        }, on_conflict="user_id").execute()
        return {"message": f"Digest scheduled {req.schedule}", "schedule": req.schedule, "sent": False, "count": 0}

    return {"message": f"Unknown schedule: {req.schedule}", "sent": False, "count": 0}
