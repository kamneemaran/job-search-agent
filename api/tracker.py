"""Tracker API endpoints — manage job applications in Supabase."""
import csv
import io
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Optional

from api.models import (
    TrackerJob, TrackerUpdateRequest, TrackerResponse,
    TrackerAddRequest,
)
from api.supabase import get_user_client
from api.rate_limit import check_tracker_limit

router = APIRouter(prefix="/api/tracker", tags=["tracker"])


@router.get("", response_model=TrackerResponse)
async def get_tracker(
    status: str = "",
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    sb = get_user_client(authorization)
    query = sb.table("jobs").select("*").eq("user_id", sb.auth.get_user().user.id)

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
            location=r.get("location", "") or "",
            salary=r.get("salary", "") or "",
        )
        for r in result.data
    ]

    count_q = sb.table("jobs").select("id", count="exact").eq("user_id", sb.auth.get_user().user.id)
    if status:
        count_q = count_q.eq("status", status)
    count_result = count_q.execute()

    return TrackerResponse(jobs=jobs, total=count_result.count or len(jobs))


@router.post("/add")
async def add_to_tracker(
    req: TrackerAddRequest,
    authorization: Optional[str] = Header(None),
):
    # Check tracker limit before adding
    check_tracker_limit(authorization)

    sb = get_user_client(authorization)
    user = sb.auth.get_user().user
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
    user = sb.auth.get_user().user
    if not user:
        raise HTTPException(401, "Not authenticated")

    update_data = {
        "status": req.status,
        "notes": req.notes,
        "updated_at": "now()",
    }
    if req.new_title:
        update_data["title"] = req.new_title
    if req.new_company:
        update_data["company"] = req.new_company
    if req.url is not None:
        update_data["url"] = req.url
    if req.salary is not None:
        update_data["salary"] = req.salary
    if req.location is not None:
        update_data["location"] = req.location

    result = (
        sb.table("jobs")
        .update(update_data)
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
    user = sb.auth.get_user().user
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


def _require_user(authorization):
    """Get authenticated user or raise 401."""
    if not authorization:
        raise HTTPException(401, "Authentication required")
    sb = get_user_client(authorization)
    resp = sb.auth.get_user()
    user = resp.user if hasattr(resp, "user") else resp
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    return sb, user


@router.get("/sheet")
async def get_tracker_sheet(authorization: Optional[str] = Header(None)):
    sb, user = _require_user(authorization)
    result = sb.table("profiles").select("tracker_sheet_url").eq("id", user.id).maybe_single().execute()
    url = result.data.get("tracker_sheet_url", "") if result.data else ""
    return {"url": url}


@router.put("/sheet")
async def set_tracker_sheet(
    body: dict,
    authorization: Optional[str] = Header(None),
):
    sb, user = _require_user(authorization)
    url = body.get("url", "")
    sb.table("profiles").update({"tracker_sheet_url": url}).eq("id", user.id).execute()
    return {"status": "saved", "url": url}


@router.post("/sheet/sync")
async def sync_sheet(authorization: Optional[str] = Header(None)):
    sb, user = _require_user(authorization)

    # Get user's sheet URL
    profile = sb.table("profiles").select("tracker_sheet_url, google_sa_json").eq("id", user.id).maybe_single().execute()
    if not profile.data or not profile.data.get("tracker_sheet_url"):
        raise HTTPException(400, "No tracker sheet configured. Save a sheet URL first.")

    sheet_url = profile.data["tracker_sheet_url"]
    sa_json = profile.data.get("google_sa_json", "") or None

    # Get all tracked jobs
    jobs_result = sb.table("jobs").select("*").eq("user_id", user.id).order("updated_at", desc=True).execute()

    from api.gsheet_sync import sync_jobs_to_sheet
    ok = sync_jobs_to_sheet(jobs_result.data, sheet_url, sa_json)

    if not ok:
        raise HTTPException(500, "Failed to sync to sheet. Check the URL and make sure your sheet is shared with the service account.")

    return {"status": "synced", "count": len(jobs_result.data)}


COLUMN_ALIASES = {
    "title": ["title", "job title", "position", "job", "role", "name"],
    "company": ["company", "employer", "organization", "firm", "company name", "employer name"],
    "location": ["location", "loc", "place", "city", "office"],
    "url": ["url", "link", "job url", "job link", "apply url", "application link", "href", "posting url"],
    "status": ["status", "state", "stage", "application status"],
    "notes": ["notes", "note", "comment", "comments", "description"],
}

def _find_column(headers, aliases):
    h_lower = [h.strip().lower() for h in headers]
    for alias in aliases:
        for i, h in enumerate(h_lower):
            if h == alias or h.startswith(alias) or alias in h:
                return i
    return None


@router.post("/import")
async def import_tracker(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    sb, user = _require_user(authorization)

    content = await file.read()
    filename = (file.filename or "").lower()

    rows = []

    if filename.endswith(".csv"):
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        headers = next(reader, [])
        for row in reader:
            rows.append(row)
    else:
        raise HTTPException(400, "Unsupported file format. Please upload a CSV file.")

    cols = {
        key: _find_column(headers, aliases)
        for key, aliases in COLUMN_ALIASES.items()
    }

    title_idx = cols["title"]
    if title_idx is None:
        raise HTTPException(400, "Could not find a 'title' or 'job title' column in the CSV.")

    added = 0
    errors = 0
    for row in rows:
        if not row or len(row) <= max(c for c in cols.values() if c is not None):
            continue
        title = row[title_idx].strip()
        if not title:
            continue

        company = row[cols["company"]].strip() if cols["company"] is not None and cols["company"] < len(row) else "Unknown"
        location = row[cols["location"]].strip() if cols["location"] is not None and cols["location"] < len(row) else ""
        url = row[cols["url"]].strip() if cols["url"] is not None and cols["url"] < len(row) else ""
        status = row[cols["status"]].strip().lower() if cols["status"] is not None and cols["status"] < len(row) else "new"
        notes = row[cols["notes"]].strip() if cols["notes"] is not None and cols["notes"] < len(row) else ""

        if status not in ("new", "applied", "rejected", "offer"):
            status = "new"

        # Check duplicate
        existing = (
            sb.table("jobs")
            .select("id")
            .eq("user_id", user.id)
            .eq("title", title)
            .eq("company", company)
            .maybe_single()
            .execute()
        )
        if existing and existing.data:
            errors += 1
            continue

        check_tracker_limit(authorization)

        sb.table("jobs").insert({
            "user_id": user.id,
            "title": title,
            "company": company,
            "location": location or "Remote",
            "url": url,
            "status": status,
            "notes": notes,
            "score": 0,
        }).execute()
        added += 1

    return {"status": "ok", "added": added, "skipped_duplicates": errors}


@router.get("/export")
async def export_tracker(
    authorization: Optional[str] = Header(None),
):
    sb = get_user_client(authorization)
    user = sb.auth.get_user().user

    jobs_result = sb.table("jobs").select("*").eq("user_id", user.id).order("updated_at", desc=True).execute()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Company", "Location", "Status", "Score", "URL", "Notes", "Date Added", "Date Updated"])

    for j in jobs_result.data:
        writer.writerow([
            j.get("title", ""),
            j.get("company", ""),
            j.get("location", ""),
            j.get("status", "new"),
            j.get("score", 0),
            j.get("url", ""),
            j.get("notes", ""),
            j.get("created_at", ""),
            j.get("updated_at", ""),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=job_tracker_export.csv"},
    )
