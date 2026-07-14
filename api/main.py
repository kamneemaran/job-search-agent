"""Job Search Agent API — wraps existing daily_scan.py logic into REST endpoints."""
import os
import sys
import json
import tempfile
import logging
import threading
import shutil
from glob import glob
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("jobpilot")

# Add parent dir so we can import daily_scan
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.models import (
    ScoreRequest, ScoreResponse,
    SearchRequest, SearchResponse, JobResult,
    ResumeUploadResponse, ResumeInfo, ListResumesResponse, ProfileResponse,
    TrackerJob, TrackerUpdateRequest, TrackerResponse,
    ProfileUpdateRequest, DigestSendRequest,
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
    resp = sb.auth.get_user()
    user = resp.user if hasattr(resp, "user") else resp

    data = {
        "id": user.id,
        "email": user.email or "",
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
async def upload_resume(
    file: UploadFile = File(...),
    key: str = Query("", description="Optional version name to register as (e.g. 'faang', 'general', 'startup')"),
    authorization: Optional[str] = Header(None),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files supported")

    ds = _get_ds()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        try:
            profile, missing = ds.parse_resume_pdf(tmp_path)
        except Exception as e:
            raise HTTPException(400, f"Failed to parse resume: {e}")

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
            except Exception as e:
                print(f"  [resume] Supabase save failed: {e}")

        # Register as a local resume version if key is provided
        if key and not missing:
            key = key.strip().lower().replace(" ", "_")
            filename = file.filename or f"resume_{key}.pdf"
            dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", filename)
            if not os.path.exists(os.path.dirname(os.path.abspath(dest))):
                os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(content)
            ds.RESUME_VERSIONS[key] = filename
            print(f"  [resume] Registered version '{key}' -> {filename}")

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


@app.get("/api/resumes", response_model=ListResumesResponse)
def list_resumes(authorization: Optional[str] = Header(None)):
    ds = _get_ds()
    registered = []
    default_key = "faang"
    for key, filename in ds.RESUME_VERSIONS.items():
        exists = os.path.exists(filename)
        fsize = os.path.getsize(filename) // 1024 if exists else 0
        registered.append(ResumeInfo(
            key=key, filename=filename, exists=exists,
            is_default=(key == default_key), size_kb=fsize,
        ))
    pdfs = glob("*.pdf") or []
    registered_names = set(ds.RESUME_VERSIONS.values())
    unregistered = [p for p in pdfs if os.path.basename(p) not in registered_names]
    return ListResumesResponse(
        registered=registered, unregistered=unregistered, default_key=default_key,
    )


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
            ds._rebuild_precompiled_patterns()
            score, note = ds.score_job(req.title, req.description, req.company, req.location)
        finally:
            ds.PROFILE["core_skills"] = orig_skills
            ds.PROFILE["years_experience"] = orig_years
            ds._rebuild_precompiled_patterns()

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

    # Swap profile once for the whole search
    with _profile_lock:
        orig_skills = ds.PROFILE.get("core_skills")
        orig_years = ds.PROFILE.get("years_experience")
        ds.PROFILE["core_skills"] = profile["core_skills"]
        ds.PROFILE["years_experience"] = profile["years_experience"]
        ds._rebuild_precompiled_patterns()

    try:
        all_jobs = []
        seen = set()
        import time as _time
        _deadline = _time.time() + 25

        # Filter keyword sets (mirrors mcp_server.py)
        _CONTRACT_KW = ["contract", "freelance", "temporary", "temp ", "fixed-term", "consultant", "12-month", "6-month"]
        _FULLTIME_KW = ["full-time", "full time", "permanent", "fte", "regular", "permanent employee"]
        _REMOTE_KW = ["remote", "work from home", "wfh", "virtual", "100% remote", "fully remote"]
        _ONSITE_KW = ["on-site", "on site", "in-office", "office based", "office-based"]
        _HYBRID_KW = ["hybrid"]

        locations_lower = [l.lower() for l in req.locations] if req.locations else None
        skills_lower = [s.lower() for s in req.skills] if req.skills else None

        def _get_job_field(job, *names):
            for n in names:
                v = job.get(n)
                if v is not None and v != "":
                    return str(v).lower().replace(" ", "_").replace("-", "_")
            return None

        def _passes_filters(job):
            """Check job against filters with dedicated field support (varies by ATS/board)."""
            combined = (job.get("title", "") + " " + job.get("description", "") + " " + job.get("location", "")).lower()
            loc = job.get("location", "").lower()
            if locations_lower and not any(l in loc for l in locations_lower):
                return False
            if skills_lower and not any(s in combined for s in skills_lower):
                return False

            if req.job_type:
                emp = _get_job_field(job, "employment_type", "employmentType", "commitment", "job_type", "jobType", "type")
                if emp:
                    if req.job_type == "contract":
                        if not any(t in emp for t in ("contract", "temporary", "temp", "freelance", "fixed_term")):
                            return False
                    elif req.job_type == "full-time":
                        if not any(t in emp for t in ("full_time", "fulltime", "permanent", "fte", "regular")):
                            return False
                else:
                    if req.job_type == "contract" and not any(kw in combined for kw in _CONTRACT_KW):
                        return False
                    if req.job_type == "full-time" and not any(kw in combined for kw in _FULLTIME_KW):
                        return False

            if req.work_mode:
                wfm = _get_job_field(job, "workplace_type", "workplaceType", "workplace", "locationType")
                remote_bool = job.get("remote")
                if wfm or remote_bool is not None:
                    if req.work_mode == "remote":
                        is_remote = bool(remote_bool is True)
                        if wfm and any(t in wfm for t in ("remote", "fully_remote")):
                            is_remote = True
                        if not is_remote:
                            return False
                    elif req.work_mode == "on-site":
                        if wfm and any(t in wfm for t in ("remote", "fully_remote", "hybrid")):
                            return False
                        if remote_bool is True:
                            return False
                    elif req.work_mode == "hybrid":
                        is_hybrid = False
                        if wfm:
                            is_hybrid = "hybrid" in wfm
                        if not is_hybrid:
                            if remote_bool is True:
                                return False
                            if not any(kw in combined for kw in _HYBRID_KW):
                                return False
                else:
                    if req.work_mode == "remote" and not any(kw in combined for kw in _REMOTE_KW):
                        return False
                    if req.work_mode == "on-site" and not any(kw in combined for kw in _ONSITE_KW):
                        return False
                    if req.work_mode == "hybrid" and not any(kw in combined for kw in _HYBRID_KW):
                        return False
            return True

        def _collect(jobs, src_name):
            if _time.time() > _deadline:
                return
            for job in jobs:
                key = (job.get("title", "").lower(), job.get("company", "").lower())
                if key in seen:
                    continue
                seen.add(key)

                if not _passes_filters(job):
                    continue

                score, note = ds.score_job(
                    job.get("title", ""),
                    job.get("description", ""),
                    job.get("company", ""),
                    job.get("location", req.location),
                )

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
    finally:
        with _profile_lock:
            ds.PROFILE["core_skills"] = orig_skills
            ds.PROFILE["years_experience"] = orig_years
            ds._rebuild_precompiled_patterns()
