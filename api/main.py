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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("jobpilot")

# Add parent dir so we can import daily_scan
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def is_within_date_filter(posted_at, date_filter: str) -> bool:
    if not date_filter or date_filter == "any":
        return True
    if not posted_at:
        return False
    from datetime import datetime, date
    now = datetime.now()
    today = date.today()
    days_cutoff = 365 * 10
    if date_filter == "1d":
        days_cutoff = 1
    elif date_filter == "1w":
        days_cutoff = 7
    elif date_filter == "1m":
        days_cutoff = 30
    elif date_filter == "3m":
        days_cutoff = 90
    if isinstance(posted_at, str):
        try:
            if "T" in posted_at:
                posted_dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                return (now - posted_dt.replace(tzinfo=None)).days <= days_cutoff
            else:
                posted_date = date.fromisoformat(posted_at)
                return (today - posted_date).days <= days_cutoff
        except Exception:
            return False
    if isinstance(posted_at, datetime):
        return (now - posted_at.replace(tzinfo=None)).days <= days_cutoff
    if isinstance(posted_at, date):
        return (today - posted_at).days <= days_cutoff
    return True

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
    """Fetch user profile from Supabase. Raises 401 if unauthorized or expired."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication token missing")

    try:
        sb = get_user_client(authorization)
        resp = sb.auth.get_user()
        user = resp.user if hasattr(resp, "user") else resp
        if not user or not getattr(user, "id", None):
            raise HTTPException(status_code=401, detail="Session expired or invalid")

        result = sb.table("profiles").select("*").eq("id", user.id).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Profile not found. Please upload a resume.")

        row = result.data
        core_skills = row.get("core_skills")
        if isinstance(core_skills, str):
            try:
                import json
                core_skills = json.loads(core_skills)
            except Exception:
                core_skills = []

        if not core_skills or not isinstance(core_skills, list) or len(core_skills) == 0:
            return {
                "name": row.get("full_name", "") or "",
                "current_role": row.get("current_role", "") or "",
                "core_skills": [],
                "years_experience": row.get("years_experience", 0) or 0,
            }

        return {
            "name": row.get("full_name", "") or "",
            "current_role": row.get("current_role", "") or "",
            "core_skills": core_skills,
            "years_experience": row.get("years_experience", 0) or 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in _get_user_profile: {e}")
        raise HTTPException(status_code=401, detail="Session expired or invalid")


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
                    "full_name": profile.get("name", ""),
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

    # Smart query fallback if user left search box empty (as per resume)
    search_query = req.query.strip()
    if not search_query:
        role = profile.get("current_role", "").lower()
        if "backend" in role:
            search_query = "backend engineer"
        elif "frontend" in role:
            search_query = "frontend engineer"
        elif "full stack" in role or "fullstack" in role:
            search_query = "full stack engineer"
        elif "devops" in role:
            search_query = "devops engineer"
        elif "qa" in role or "test" in role:
            search_query = "qa engineer"
        elif "data" in role:
            search_query = "data engineer"
        elif profile.get("current_role"):
            search_query = profile["current_role"]
        elif profile.get("core_skills"):
            search_query = profile["core_skills"][0] + " developer"
        else:
            search_query = "software engineer"

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
            if locations_lower:
                has_loc_match = False
                for l in locations_lower:
                    if l in loc:
                        has_loc_match = True
                        break
                    if l in ("india", "ind"):
                        _INDIA_CITIES = ["india", "pune", "mumbai", "bangalore", "bengaluru", "hyderabad",
                                         "chennai", "delhi", "gurgaon", "gurugram", "noida", "kolkata",
                                         "ahmedabad", "jaipur", "kochi", "coimbatore"]
                        if any(c in loc for c in _INDIA_CITIES):
                            has_loc_match = True
                            break
                if not has_loc_match:
                    print(f"  [filter] SKIP: '{job.get('title')}' @ '{job.get('company')}' - location '{job.get('location')}' not matched in {req.locations}")
                    return False
            if skills_lower and not any(s in combined for s in skills_lower):
                print(f"  [filter] SKIP: '{job.get('title')}' @ '{job.get('company')}' - combined text doesn't match skills {req.skills}")
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

            if req.posted_date_filter and req.posted_date_filter != "any":
                if not is_within_date_filter(job.get("posted_at"), req.posted_date_filter):
                    return False

            return True

        def _collect(jobs, src_name):
            if _time.time() > _deadline:
                print(f"  [collect] WARNING: Search deadline exceeded during source '{src_name}'")
                return
            print(f"  [collect] Processing {len(jobs)} jobs from {src_name}...")
            for job in jobs:
                key = (job.get("title", "").lower(), job.get("company", "").lower())
                if key in seen:
                    continue
                seen.add(key)

                if not _passes_filters(job):
                    continue

                desc = job.get("description", "")
                if not req.require_visa:
                    desc += " visa sponsorship relocation support"

                score, note = ds.score_job(
                    job.get("title", ""),
                    desc,
                    job.get("company", ""),
                    job.get("location", req.location),
                )

                # Filter jobs without visa/relo signals when require_visa is on AND job is outside India AND is NOT remote
                if req.require_visa and score > 0 and "Visa sponsorship details not mentioned" in note:
                    loc_lower = job.get("location", "").lower()
                    text_lower = (job.get("title", "") + " " + job.get("description", "")).lower()
                    is_remote_job = "remote" in loc_lower or "remote" in text_lower
                    if not is_remote_job:
                        _INDIA_MARKERS = ["india", "pune", "mumbai", "bangalore", "bengaluru", "hyderabad",
                                          "chennai", "delhi", "gurgaon", "gurugram", "noida", "kolkata",
                                          "ahmedabad", "jaipur", "thiruvananthapuram", "kochi", "coimbatore"]
                        is_outside_india = not any(m in loc_lower or m in text_lower for m in _INDIA_MARKERS)
                        if is_outside_india:
                            print(f"  [collect] SKIP Visa: '{job.get('title')}' @ '{job.get('company')}' - outside India & not remote & no visa info")
                            continue

                print(f"  [collect] Scored: '{job.get('title')}' @ '{job.get('company')}' in '{job.get('location')}' -> score {score} (note: {note or 'N/A'})")

                if score < req.threshold:
                    print(f"  [collect] SKIP Threshold: '{job.get('title')}' @ '{job.get('company')}' - score {score} < {req.threshold}")
                    continue
                ec = [c.lower() for c in req.exclude_companies]
                if ec and job.get("company", "").lower() in ec:
                    print(f"  [collect] SKIP Excluded: '{job.get('title')}' @ '{job.get('company')}'")
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

        # Select highly-targeted search boards based on location and work mode (reduces latency & boosts relevance)
        loc_lower = req.location.lower()
        is_remote_search = req.work_mode == "remote" or "remote" in loc_lower
        is_india_search = "india" in loc_lower or any(city in loc_lower for city in ["pune", "mumbai", "bangalore", "bengaluru", "hyderabad", "chennai", "delhi", "noida", "gurgaon"])
        is_germany_search = "germany" in loc_lower or "de" in loc_lower or "berlin" in loc_lower or "munich" in loc_lower
        is_netherlands_search = "netherlands" in loc_lower or "nl" in loc_lower or any(city in loc_lower for city in ["amsterdam", "rotterdam", "utrecht", "hague", "eindhoven"])

        target_boards = []
        BOARD_MAP = {
            "LinkedIn": ds.search_linkedin,
            "Indeed": ds.search_indeed,
            "Naukri": ds.search_naukri,
            "Instahyre": ds.search_instahyre,
            "WeWorkRemotely": ds.search_weworkremotely,
            "Remotive": ds.search_remotive,
            "Arbeitnow": ds.search_arbeitnow,
            "IamExpat": ds.search_iamexpat,
            "TogetherAbroad": ds.search_togetherabroad,
            "FoundIt": ds.search_foundit,
            "TimesJobs": ds.search_timesjobs,
            "Glassdoor": ds.search_glassdoor,
        }

        if req.sources:
            target_boards = [
                (name, BOARD_MAP[name])
                for name in req.sources
                if name in BOARD_MAP
            ]
        elif is_remote_search:
            # Remote-specific high-signal job boards
            target_boards = [
                ("WeWorkRemotely", ds.search_weworkremotely),
                ("Remotive", ds.search_remotive),
                ("LinkedIn", ds.search_linkedin),
            ]
        elif is_india_search:
            # India-specific job boards
            target_boards = [
                ("Naukri", ds.search_naukri),
                ("Instahyre", ds.search_instahyre),
                ("LinkedIn", ds.search_linkedin),
                ("FoundIt", ds.search_foundit),
                ("TimesJobs", ds.search_timesjobs),
                ("Indeed", ds.search_indeed),
            ]
        elif is_germany_search:
            # Germany-specific job boards
            target_boards = [
                ("Arbeitnow", ds.search_arbeitnow),
                ("LinkedIn", ds.search_linkedin),
                ("Indeed", ds.search_indeed),
            ]
        elif is_netherlands_search:
            # Netherlands-specific job boards
            target_boards = [
                ("IamExpat", ds.search_iamexpat),
                ("TogetherAbroad", ds.search_togetherabroad),
                ("LinkedIn", ds.search_linkedin),
                ("Indeed", ds.search_indeed),
            ]
        else:
            # Default / Global / Europe boards
            target_boards = [
                ("LinkedIn", ds.search_linkedin),
                ("Indeed", ds.search_indeed),
                ("Glassdoor", ds.search_glassdoor),
            ]

        print(f"=== Starting On-Demand Search ===")
        print(f"Query: {search_query}")
        print(f"Location: {req.location}")
        print(f"Locations filter: {req.locations}")
        print(f"Threshold: {req.threshold}")
        print(f"Profile: {profile['name']} | {profile['years_experience']} yrs exp | {len(profile['core_skills'])} skills")
        print(f"Job boards targeted: {[name for name, _ in target_boards]}")

        # 1. Search targeted job boards in parallel to prevent a slow scraper (like LinkedIn) from blocking others
        from concurrent.futures import ThreadPoolExecutor, as_completed
        scraper_timeout = 12.0

        with ThreadPoolExecutor(max_workers=len(target_boards)) as executor:
            future_to_board = {
                executor.submit(fn, search_query, req.location, max_results // 2): name
                for name, fn in target_boards
            }

            for future in as_completed(future_to_board):
                name = future_to_board[future]
                try:
                    # Collect results concurrently (caps wait time at 12s per board)
                    jobs = future.result(timeout=scraper_timeout)
                    print(f"  [scraper] Board '{name}' completed, returned {len(jobs) if jobs else 0} raw results")
                    if jobs:
                        _collect(jobs, name)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"Scraper {name} failed or timed out: {e}")

        # 2. Search remote company ATS (skip heavy Playwright-based scrapers to ensure sub-5s response times)
        max_companies = get_max_companies(authorization)
        non_pw_sources = [s for s in ds.REMOTE_JOB_SOURCES if not s.get("playwright")]
        for src in non_pw_sources[:max_companies]:
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
                    "query": search_query,
                    "location": req.location,
                    "results_count": len(all_jobs),
                }).execute()
            except Exception:
                pass

        return SearchResponse(jobs=all_jobs[:max_results], total=len(all_jobs), query=search_query)
    finally:
        with _profile_lock:
            ds.PROFILE["core_skills"] = orig_skills
            ds.PROFILE["years_experience"] = orig_years
            ds._rebuild_precompiled_patterns()
