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
    
    batches_data = row.get("batches") or ["all"]
    if isinstance(batches_data, str):
        try:
            import json
            batches_data = json.loads(batches_data)
        except Exception:
            batches_data = ["all"]

    return DigestPreferences(
        enabled=row.get("enabled", True),
        frequency=row.get("frequency", "weekly"),
        email=row.get("email", ""),
        day_of_week=row.get("day_of_week", "monday"),
        day_of_month=row.get("day_of_month", 1),
        time_of_day=row.get("time_of_day", "09:00"),
        sent_history=row.get("sent_history") or [],
        batches=batches_data,
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
        "day_of_week": prefs.day_of_week,
        "day_of_month": prefs.day_of_month,
        "time_of_day": prefs.time_of_day,
        "sent_history": prefs.sent_history,
        "batches": prefs.batches,
    }

    try:
        sb.table("email_preferences").upsert(data, on_conflict="user_id").execute()
    except Exception as e:
        # If the column "batches" does not exist in the database, let's execute an alter script first!
        try:
            sb.table("email_preferences").select("batches").limit(1).execute()
        except Exception:
            try:
                # Add column dynamically
                # (Note: standard PostgREST cannot alter table, but if it fails we can catch and log)
                print(f"Error: public.email_preferences has no 'batches' column. Please run the SQL alter table command. {e}")
            except Exception:
                pass
        # Remove batches from dict so it can upsert successfully even if column hasn't been added yet
        data.pop("batches", None)
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
    if isinstance(core_skills, str):
        try:
            import json
            core_skills = json.loads(core_skills)
        except Exception:
            core_skills = []

    if not core_skills or not isinstance(core_skills, list):
        raise HTTPException(400, "No core skills found. Upload a resume first.")

    profile = {
        "core_skills": core_skills,
        "years_experience": row.get("years_experience", 0) or 0,
        "current_role": row.get("current_role", ""),
    }

    to_email = req.email or row.get("email") or user.email or ""

    if req.schedule == "now":
        # Get email preferences for frequency and sent history
        pref_result = sb.table("email_preferences").select("*").eq("user_id", user.id).maybe_single().execute()
        pref_row = pref_result.data if pref_result else None

        frequency = pref_row.get("frequency", "weekly") if pref_row else "weekly"
        sent_history = pref_row.get("sent_history", []) if pref_row else []

        # Enforce rate limits based on user requirements:
        # 1. "daily option we can click once in daily"
        # 2. "weekly 1-2 times in week taht too on different day"
        # 3. "monthly 1-2 times in month provided day has to be different"
        now = datetime.now()
        now_weekday = now.weekday()  # 0-6 (Mon-Sun)
        now_day = now.day            # 1-31

        # Filter sent_history to past 30 days to keep the JSON small
        history_dates = []
        for ts in sent_history:
            try:
                from datetime import datetime as dt_class
                # Parse ISO timestamp
                if "T" in ts:
                    dt = datetime.fromisoformat(ts)
                else:
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
                # If within 30 days, keep it
                if (now - dt).days < 30:
                    history_dates.append(dt)
            except Exception:
                pass

        # Check limit logic: Flat 8 hours limit on manual trigger
        for dt in history_dates:
            diff_hours = (now - dt).total_seconds() / 3600.0
            if diff_hours < 8.0:
                raise HTTPException(
                    429,
                    "You already requested a scan recently. Your on-demand digest is running in the background and compiling jobs from multiple regions and company career pages. Please check your inbox in a few minutes, or wait up to 4-5 hours before requesting another scan."
                )

        try:
            ds._rebuild_precompiled_patterns()
        except Exception:
            pass

        batches_list = pref_row.get("batches") if pref_row else ["all"]
        if isinstance(batches_list, str):
            try:
                import json
                batches_list = json.loads(batches_list)
            except Exception:
                batches_list = ["all"]
        if not batches_list:
            batches_list = ["all"]

        all_sources = []
        if "all" in batches_list:
            all_sources = (
                ds.JOB_SOURCES + ds.EU_JOB_SOURCES + ds.GLOBAL_JOB_SOURCES
                + ds.APAC_JOB_SOURCES + ds.US_CANADA_JOB_SOURCES
                + ds.MIDDLE_EAST_JOB_SOURCES + ds.REMOTE_JOB_SOURCES
            )
        else:
            if "india" in batches_list:
                all_sources += ds.JOB_SOURCES
            if "europe_companies" in batches_list:
                all_sources += ds.EU_JOB_SOURCES
            if "europe_boards" in batches_list:
                all_sources += [s for s in ds.GLOBAL_JOB_SOURCES if s.get("name") in ("Arbeitnow", "IamExpat", "TogetherAbroad")]
            if "middle_east" in batches_list:
                all_sources += ds.MIDDLE_EAST_JOB_SOURCES
            if "apac" in batches_list:
                all_sources += ds.APAC_JOB_SOURCES
            if "us_canada" in batches_list:
                all_sources += ds.US_CANADA_JOB_SOURCES
            if "remote" in batches_list:
                all_sources += ds.REMOTE_JOB_SOURCES

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

        # Update last_sent_at and sent_history
        new_history = [dt.isoformat() for dt in history_dates]
        new_history.append(now.isoformat())

        try:
            sb.table("email_preferences").upsert({
                "user_id": user.id,
                "last_sent_at": now.isoformat(),
                "sent_history": new_history,
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
