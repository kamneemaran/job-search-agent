"""Job Search Agent API — wraps existing daily_scan.py logic into REST endpoints."""
import os
import sys
import json
import tempfile
import logging
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("jobpilot")

# Add parent dir so we can import daily_scan
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.models import (
    ScoreRequest, ScoreResponse,
    SearchRequest, SearchResponse, JobResult,
    ResumeUploadResponse, ProfileResponse,
    TrackerJob, TrackerUpdateRequest, TrackerResponse,
    ProfileUpdateRequest,
)
from api.tracker import router as tracker_router
from api.digest import router as digest_router
from api.supabase import get_user_client
from api.rate_limit import check_search_limit, increment_search_count, check_tracker_limit, get_max_results

_ds = None
_profile_lock = threading.Lock()


def _get_ds():
    global _ds
    if _ds is None:
        import daily_scan as ds
        try:
            ds._rebuild_precompiled_patterns()
        except Exception:
            pass
        _ds = ds
    return _ds


def _get_user_profile(authorization: Optional[str]) -> dict:
    """Fetch user profile from Supabase, fall back to hardcoded PROFILE."""
    ds = _get_ds()
    fallback = {
        "name": ds.PROFILE.get("name", ""),
        "current_role": ds.PROFILE.get("current_role", ""),
        "core_skills": ds.PROFILE.get("core_skills", []),
        "years_experience": ds.PROFILE.get("years_experience", 0),
    }

    if not authorization:
        return fallback

    try:
        sb = get_user_client(authorization)
        user = sb.auth.get_user()
        result = sb.table("profiles").select("*").eq("id", user.id).maybe_single().execute()
        if not result.data:
            return fallback

        row = result.data
        core_skills = row.get("core_skills")
        if not core_skills:
            return fallback

        return {
            "name": row.get("full_name", "") or fallback["name"],
            "current_role": row.get("current_role", "") or fallback["current_role"],
            "core_skills": core_skills,
            "years_experience": row.get("years_experience") or fallback["years_experience"],
        }
    except Exception:
        return fallback


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="JobPilot API",
    description="AI-powered job search for tech roles — scoring, matching, and tracking.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(tracker_router)
app.include_router(digest_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/subscription")
def get_subscription(authorization: Optional[str] = Header(None)):
    from api.rate_limit import get_user_plan
    info = get_user_plan(authorization)
    return {
        "plan": info["plan"],
        "searches_today": info["searches_today"],
        "tracker_count": info["tracker_count"],
        "limits": info["limits"],
    }

@app.get("/api/profile", response_model=ProfileResponse)
def get_profile(authorization: Optional[str] = Header(None)):
    ds = _get_ds()
    profile = _get_user_profile(authorization)
    p = ds.PROFILE
    return ProfileResponse(
        name=profile["name"],
        current_role=profile["current_role"],
        core_skills=profile["core_skills"],
        years_experience=profile["years_experience"],
        seniority_keywords=p.get("seniority_keywords", []),
    )


@app.put("/api/profile", response_model=ProfileResponse)
def update_profile(
    req: ProfileUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    if not authorization:
        raise HTTPException(401, "Authorization required")

    sb = get_user_client(authorization)
    user = sb.auth.get_user()

    data = {
        "id": user.id,
        "full_name": req.full_name,
        "current_role": req.current_role,
        "years_experience": req.years_experience,
        "core_skills": req.core_skills,
    }
    sb.table("profiles").upsert(data, on_conflict="id").execute()

    ds = _get_ds()
    return ProfileResponse(
        name=req.full_name,
        current_role=req.current_role,
        core_skills=req.core_skills,
        years_experience=req.years_experience,
        seniority_keywords=ds.PROFILE.get("seniority_keywords", []),
    )


@app.post("/api/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files supported")

    ds = _get_ds()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        profile, missing = ds.parse_resume_pdf(tmp_path)

        # Save to Supabase if authenticated
        if authorization:
            try:
                sb = get_user_client(authorization)
                user = sb.auth.get_user()
                user_id = user.id
                filename = file.filename
                storage_path = f"{user_id}/{filename}"

                # Upload file to storage
                sb.storage.from_("resumes").upload(storage_path, content, {"content-type": "application/pdf", "upsert": "true"})

                # Deactivate other resumes
                sb.table("resumes").update({"is_active": False}).eq("user_id", user_id).eq("is_active", True).execute()

                # Insert new resume record
                sb.table("resumes").insert({
                    "user_id": user_id,
                    "filename": filename,
                    "storage_path": storage_path,
                    "parsed_name": profile.get("name", ""),
                    "parsed_role": profile.get("current_role", ""),
                    "parsed_skills": profile.get("core_skills", []),
                    "parsed_experience": profile.get("years_experience", 0),
                    "is_active": True,
                }).execute()

                # Update profiles table
                sb.table("profiles").upsert({
                    "id": user_id,
                    "core_skills": profile.get("core_skills", []),
                    "current_role": profile.get("current_role", ""),
                    "years_experience": profile.get("years_experience", 0),
                }, on_conflict="id").execute()
            except Exception:
                pass

        return ResumeUploadResponse(
            name=profile.get("name", ""),
            email=profile.get("email", ""),
            current_role=profile.get("current_role", ""),
            core_skills=profile.get("core_skills", []),
            years_experience=profile.get("years_experience", 0),
            missing_fields=missing,
        )
    finally:
        os.unlink(tmp_path)


@app.post("/api/score", response_model=ScoreResponse)
def score_job(req: ScoreRequest, authorization: Optional[str] = Header(None)):
    ds = _get_ds()
    profile = _get_user_profile(authorization)

    with _profile_lock:
        orig_skills = ds.PROFILE.get("core_skills")
        orig_years = ds.PROFILE.get("years_experience")
        try:
            ds.PROFILE["core_skills"] = profile["core_skills"]
            ds.PROFILE["years_experience"] = profile["years_experience"]
            score, note = ds.score_job(req.title, req.description, req.company, req.location)
        finally:
            ds.PROFILE["core_skills"] = orig_skills
            ds.PROFILE["years_experience"] = orig_years

    return ScoreResponse(score=score, note=note, title=req.title, company=req.company)


@app.post("/api/search", response_model=SearchResponse)
def search_jobs(req: SearchRequest, authorization: Optional[str] = Header(None)):
    # Rate limit check
    check_search_limit(authorization)
    max_results = min(req.max_results, get_max_results(authorization))

    ds = _get_ds()
    profile = _get_user_profile(authorization)

    queries = ds.build_domain_queries(
        skills=profile["core_skills"],
        exp_years=profile["years_experience"],
        prefer_role=req.query,
    )

    all_jobs = []
    seen = set()

    all_sources = (
        ds.JOB_SOURCES
        + ds.EU_JOB_SOURCES
        + ds.GLOBAL_JOB_SOURCES
        + ds.APAC_JOB_SOURCES
        + ds.US_CANADA_JOB_SOURCES
        + ds.MIDDLE_EAST_JOB_SOURCES
        + ds.REMOTE_JOB_SOURCES
    )

    for source in all_sources:
        try:
            jobs = ds.fetch_jobs_from_source(source)
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
                            job.get("title", ""),
                            job.get("description", ""),
                            job.get("company", ""),
                            job.get("location", req.location),
                        )
                    finally:
                        ds.PROFILE["core_skills"] = orig_skills
                        ds.PROFILE["years_experience"] = orig_years

                if score < req.threshold:
                    continue

                if req.exclude_companies:
                    if job.get("company", "").lower() in [c.lower() for c in req.exclude_companies]:
                        continue

                salary_info = ds.get_salary_info(
                    job.get("company", ""), job.get("title", ""), job.get("description", "")
                )
                salary_str = ds._format_salary(salary_info) if salary_info else None

                all_jobs.append(JobResult(
                    title=job.get("title", ""),
                    company=job.get("company", ""),
                    location=job.get("location", ""),
                    url=job.get("url", ""),
                    score=score,
                    note=note,
                    salary=salary_str,
                    description=job.get("description", "")[:500],
                    source=source.get("name", ""),
                ))
        except Exception:
            continue

    all_jobs.sort(key=lambda j: j.score, reverse=True)
    all_jobs = all_jobs[:max_results * 2]

    # Increment search count after successful search
    increment_search_count(authorization)

    # Log search to searches table for rate limiting
    if authorization:
        try:
            sb = get_user_client(authorization)
            user = sb.auth.get_user()
            sb.table("searches").insert({
                "user_id": user.id,
                "query": req.query,
                "location": req.location,
                "results_count": len(all_jobs),
            }).execute()
        except Exception:
            pass

    return SearchResponse(jobs=all_jobs, total=len(all_jobs), query=req.query)
