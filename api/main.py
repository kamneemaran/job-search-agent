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
from api.rate_limit import check_search_limit, increment_search_count, check_tracker_limit, get_max_results, get_max_companies

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
    """Fetch user profile from Supabase. Returns empty profile if not set up."""
    empty = {"name": "", "current_role": "", "core_skills": [], "years_experience": 0}

    if not authorization:
        return empty

    try:
        sb = get_user_client(authorization)
        user = sb.auth.get_user().user
        result = sb.table("profiles").select("*").eq("id", user.id).maybe_single().execute()
        if not result.data:
            return empty

        row = result.data
        core_skills = row.get("core_skills")
        if not core_skills or (isinstance(core_skills, list) and len(core_skills) == 0):
            return empty

        return {
            "name": row.get("full_name", ""),
            "current_role": row.get("current_role", ""),
            "core_skills": core_skills,
            "years_experience": row.get("years_experience", 0) or 0,
        }
    except Exception:
        return empty


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
        core_skills=profile.get("core_skills", []) or [],
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
    user = sb.auth.get_user().user

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
                user = sb.auth.get_user().user
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
    check_search_limit(authorization)
    max_results = min(req.max_results, get_max_results(authorization))

    ds = _get_ds()
    profile = _get_user_profile(authorization)

    all_jobs = []
    seen = set()
    import time as _time
    _deadline = _time.time() + 25

    def _collect(jobs, src_name):
        if _time.time() > _deadline:
            return
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
            ec = [c.lower() for c in req.exclude_companies]
            if ec and job.get("company", "").lower() in ec:
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
                source=src_name,
            ))

    # 1. Search job boards
    for name, fn in [
        ("LinkedIn", ds.search_linkedin),
        ("Indeed", ds.search_indeed),
        ("Naukri", ds.search_naukri),
        ("Glassdoor", ds.search_glassdoor),
        ("SimplyHired", ds.search_simplyhired),
    ]:
        if _time.time() > _deadline:
            break
        try:
            _collect(fn(req.query, req.location, max_results // 2), name)
        except Exception:
            continue

    # 2. Search remote company ATS
    max_companies = get_max_companies(authorization)
    for src in ds.REMOTE_JOB_SOURCES[:max_companies if max_companies > 0 else len(ds.REMOTE_JOB_SOURCES)]:
        if _time.time() > _deadline:
            break
        try:
            _collect(ds.fetch_jobs_from_source(src), src.get("name", ""))
        except Exception:
            continue

    all_jobs.sort(key=lambda j: j.score, reverse=True)

    increment_search_count(authorization)

    if authorization:
        try:
            sb = get_user_client(authorization)
            user = sb.auth.get_user().user
            sb.table("searches").insert({
                "user_id": user.id,
                "query": req.query,
                "location": req.location,
                "results_count": len(all_jobs),
            }).execute()
        except Exception:
            pass

    return SearchResponse(jobs=all_jobs[:max_results], total=len(all_jobs), query=req.query)
