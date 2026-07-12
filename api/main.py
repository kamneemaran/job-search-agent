"""Job Search Agent API — wraps existing daily_scan.py logic into REST endpoints."""
import os
import sys
import json
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

# Add parent dir so we can import daily_scan
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.models import (
    ScoreRequest, ScoreResponse,
    SearchRequest, SearchResponse, JobResult,
    ResumeUploadResponse, ProfileResponse,
    TrackerJob, TrackerUpdateRequest, TrackerResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load profile and precompile patterns on startup."""
    import daily_scan as ds
    ds._rebuild_precompiled_patterns()
    yield


app = FastAPI(
    title="Job Search Agent",
    description="AI-powered job search for tech roles — scoring, matching, and tracking.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── Profile ─────────────────────────────────────────────────────────────────

@app.get("/api/profile", response_model=ProfileResponse)
def get_profile():
    import daily_scan as ds
    p = ds.PROFILE
    return ProfileResponse(
        name=p.get("name", ""),
        current_role=p.get("current_role", ""),
        core_skills=p.get("core_skills", []),
        years_experience=p.get("years_experience", 0),
        seniority_keywords=p.get("seniority_keywords", []),
    )


# ── Resume Upload ───────────────────────────────────────────────────────────

@app.post("/api/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files supported")

    import daily_scan as ds
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        profile, missing = ds.parse_resume_pdf(tmp_path)
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


# ── Score a Job ─────────────────────────────────────────────────────────────

@app.post("/api/score", response_model=ScoreResponse)
def score_job(req: ScoreRequest):
    import daily_scan as ds
    score, note = ds.score_job(req.title, req.description, req.company, req.location)
    return ScoreResponse(score=score, note=note, title=req.title, company=req.company)


# ── Search Jobs ─────────────────────────────────────────────────────────────

@app.post("/api/search", response_model=SearchResponse)
def search_jobs(req: SearchRequest):
    import daily_scan as ds

    # Build search queries from the input
    queries = ds.build_domain_queries(
        skills=req.query.split(","),
        exp_years=ds.PROFILE.get("years_experience", 5),
        prefer_role=req.query,
    )

    all_jobs = []
    seen = set()

    # Search company ATS sources
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

                score, note = ds.score_job(
                    job.get("title", ""),
                    job.get("description", ""),
                    job.get("company", ""),
                    job.get("location", req.location),
                )

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

    # Sort by score descending, cap results
    all_jobs.sort(key=lambda j: j.score, reverse=True)
    all_jobs = all_jobs[:req.max_results * 2]

    return SearchResponse(jobs=all_jobs, total=len(all_jobs), query=req.query)


# ── Tracker ─────────────────────────────────────────────────────────────────

@app.get("/api/tracker", response_model=TrackerResponse)
def get_tracker(status: str = "", limit: int = 50):
    import daily_scan as ds
    tracker = ds.JobTracker()
    jobs = []
    for key, info in tracker.data.get("jobs", {}).items():
        if status and info.get("status", "new") != status:
            continue
        jobs.append(TrackerJob(
            title=info.get("title", ""),
            company=info.get("company", ""),
            url=info.get("url", ""),
            score=info.get("score", 0),
            status=info.get("status", "new"),
            date_found=info.get("date_found", ""),
            date_updated=info.get("date_updated", ""),
            notes=info.get("notes", ""),
        ))
    jobs.sort(key=lambda j: j.date_updated or j.date_found or "", reverse=True)
    return TrackerResponse(jobs=jobs[:limit], total=len(jobs))


@app.post("/api/tracker/update")
def update_tracker(req: TrackerUpdateRequest):
    import daily_scan as ds
    tracker = ds.JobTracker()
    success = tracker.update_status(req.title, req.company, req.status, req.notes)
    if not success:
        raise HTTPException(404, "Job not found in tracker")
    return {"status": "updated", "title": req.title, "company": req.company, "new_status": req.status}


@app.post("/api/tracker/add")
def add_to_tracker(req: TrackerJob):
    import daily_scan as ds
    tracker = ds.JobTracker()
    tracker.add_job(req.title, req.company, req.url, req.score, req.status)
    return {"status": "added", "title": req.title, "company": req.company}
