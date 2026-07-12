"""Auto-log emailed jobs to the tracker in Supabase."""
import os
import logging
from supabase import create_client

logger = logging.getLogger("jobpilot.tracker")

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TRACKER_USER_EMAIL = os.environ.get("TRACKER_USER_EMAIL", "")


def log_jobs_to_tracker(matches: list[dict], user_email: str = "") -> int:
    """Log a batch of scored job matches to the Supabase jobs table.

    Args:
        matches: List of job dicts with keys: title, company, url, score, etc.
        user_email: Email to look up the user_id. Falls back to TRACKER_USER_EMAIL env.

    Returns:
        Number of jobs successfully inserted (skips duplicates).
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.debug("Supabase not configured, skipping tracker log")
        return 0

    email = user_email or TRACKER_USER_EMAIL
    if not email:
        logger.debug("No user email configured for tracker")
        return 0

    try:
        sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        # Look up user_id by email
        user_result = sb.rpc("get_user_id_by_email", {"user_email": email}).execute()
        if not user_result.data:
            # Try direct query
            profile = sb.table("profiles").select("id").eq("email", email).limit(1).execute()
            if not profile.data:
                logger.warning(f"No user found for email: {email}")
                return 0
            user_id = profile.data[0]["id"]
        else:
            user_id = user_result.data

        logged = 0
        for match in matches:
            title = match.get("title", "")
            company = match.get("company", "")
            if not title or not company:
                continue

            # Skip if already tracked
            existing = (
                sb.table("jobs")
                .select("id")
                .eq("user_id", user_id)
                .eq("title", title)
                .eq("company", company)
                .limit(1)
                .execute()
            )
            if existing.data:
                continue

            sb.table("jobs").insert({
                "user_id": user_id,
                "title": title,
                "company": company,
                "url": match.get("url", ""),
                "score": match.get("score", 0),
                "description": (match.get("description", "") or "")[:2000],
                "salary": match.get("salary", "") or "",
                "location": match.get("location", "") or "",
                "source": match.get("source", "") or "",
                "status": "new",
            }).execute()
            logged += 1

        logger.info(f"Logged {logged} new jobs to tracker for {email}")
        return logged

    except Exception as e:
        logger.error(f"Failed to log jobs to tracker: {e}")
        return 0
