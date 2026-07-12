"""Tracker API endpoints — manage job applications in Supabase."""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from api.models import (
    TrackerJob, TrackerUpdateRequest, TrackerResponse,
    TrackerAddRequest,
)
from api.supabase import get_user_client

router = APIRouter(prefix="/api/tracker", tags=["tracker"])


@router.get("", response_model=TrackerResponse)
async def get_tracker(
    status: str = "",
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    sb = get_user_client(authorization)
    query = sb.table("jobs").select("*").eq("user_id", sb.auth.get_user().id)

    if status:
        query = query.eq("status", status)

    result = query.order("updated_at", desc=True).limit(limit).execute()
    jobs = [
        TrackerJob(
            title=r["title"],
            company=r["company"],
            url=r.get("url", ""),
            score=r.get("score", 0),
            status=r.get("status", "new"),
            date_found=r.get("found_at", ""),
            date_updated=r.get("updated_at", ""),
            notes=r.get("notes", ""),
        )
        for r in result.data
    ]

    count_q = sb.table("jobs").select("id", count="exact").eq("user_id", sb.auth.get_user().id)
    if status:
        count_q = count_q.eq("status", status)
    count_result = count_q.execute()

    return TrackerResponse(jobs=jobs, total=count_result.count or len(jobs))


@router.post("/add")
async def add_to_tracker(
    req: TrackerAddRequest,
    authorization: Optional[str] = Header(None),
):
    sb = get_user_client(authorization)
    user = sb.auth.get_user()
    if not user:
        raise HTTPException(401, "Not authenticated")

    existing = (
        sb.table("jobs")
        .select("id")
        .eq("user_id", user.id)
        .eq("title", req.title)
        .eq("company", req.company)
        .execute()
    )
    if existing.data:
        raise HTTPException(409, "Job already in tracker")

    result = (
        sb.table("jobs")
        .insert({
            "user_id": user.id,
            "title": req.title,
            "company": req.company,
            "url": req.url,
            "score": req.score,
            "description": req.description,
            "salary": req.salary,
            "location": req.location,
            "status": "new",
        })
        .execute()
    )

    return {"status": "added", "id": result.data[0]["id"] if result.data else None}


@router.post("/update")
async def update_tracker(
    req: TrackerUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    sb = get_user_client(authorization)
    user = sb.auth.get_user()
    if not user:
        raise HTTPException(401, "Not authenticated")

    result = (
        sb.table("jobs")
        .update({
            "status": req.status,
            "notes": req.notes,
            "updated_at": "now()",
        })
        .eq("user_id", user.id)
        .eq("title", req.title)
        .eq("company", req.company)
        .execute()
    )

    if not result.data:
        raise HTTPException(404, "Job not found in tracker")

    return {"status": "updated", "title": req.title, "company": req.company, "new_status": req.status}


@router.delete("/{title}/{company}")
async def remove_from_tracker(
    title: str,
    company: str,
    authorization: Optional[str] = Header(None),
):
    sb = get_user_client(authorization)
    user = sb.auth.get_user()
    if not user:
        raise HTTPException(401, "Not authenticated")

    result = (
        sb.table("jobs")
        .delete()
        .eq("user_id", user.id)
        .eq("title", title)
        .eq("company", company)
        .execute()
    )

    return {"status": "removed"}
