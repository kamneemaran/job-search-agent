"""Weekly/daily/biweekly email digest worker.

Queries Supabase for users with email digests enabled, runs job search
using their profile, and sends an HTML email with matches scoring > 65.
"""
import os
import sys
import smtplib
import logging
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root so we can import daily_scan
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from supabase import create_client

logger = logging.getLogger("digest_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

SCORE_THRESHOLD = 65
_profile_lock = threading.Lock()


def get_service_client():
    """Create a Supabase client with service role key (bypasses RLS)."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def should_send(frequency: str, last_sent_at: str | None) -> bool:
    """Check if enough time has elapsed since last send based on frequency."""
    if not last_sent_at:
        return True

    try:
        last_sent = datetime.fromisoformat(last_sent_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return True

    now = datetime.now(timezone.utc)
    delta = now - last_sent

    if frequency == "daily":
        return delta >= timedelta(hours=20)
    elif frequency == "weekly":
        return delta >= timedelta(days=6)
    elif frequency == "biweekly":
        return delta >= timedelta(days=13)
    return False


def search_jobs_for_user(profile: dict) -> list[dict]:
    """Run job search using user's profile and return scored results."""
    import daily_scan as ds

    try:
        ds._rebuild_precompiled_patterns()
    except Exception:
        pass

    all_sources = (
        ds.JOB_SOURCES
        + ds.EU_JOB_SOURCES
        + ds.GLOBAL_JOB_SOURCES
        + ds.APAC_JOB_SOURCES
        + ds.US_CANADA_JOB_SOURCES
        + ds.MIDDLE_EAST_JOB_SOURCES
        + ds.REMOTE_JOB_SOURCES
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
                        job.get("title", ""),
                        job.get("description", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                    )
                finally:
                    ds.PROFILE["core_skills"] = orig_skills
                    ds.PROFILE["years_experience"] = orig_years

            if score >= SCORE_THRESHOLD:
                salary_info = ds.get_salary_info(
                    job.get("company", ""),
                    job.get("title", ""),
                    job.get("description", ""),
                )
                salary_str = ds._format_salary(salary_info) if salary_info else ""

                results.append({
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "score": score,
                    "location": job.get("location", ""),
                    "salary": salary_str,
                    "url": job.get("url", ""),
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def build_email_html(jobs: list[dict]) -> str:
    """Build a dark-themed HTML email with job results table."""
    rows = ""
    for job in jobs:
        link = f'<a href="{job["url"]}" style="color:#60a5fa;">Apply</a>' if job["url"] else "—"
        rows += f"""<tr>
            <td style="padding:10px 12px;border-bottom:1px solid #374151;">{job["title"]}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #374151;">{job["company"]}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #374151;text-align:center;">{job["score"]}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #374151;">{job["location"]}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #374151;">{job["salary"] or "—"}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #374151;text-align:center;">{link}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#111827;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:800px;margin:0 auto;padding:32px 16px;">
    <h1 style="color:#f9fafb;font-size:24px;margin-bottom:8px;">Your Job Matches</h1>
    <p style="color:#9ca3af;font-size:14px;margin-bottom:24px;">{len(jobs)} new opportunities scoring above {SCORE_THRESHOLD}</p>
    <table style="width:100%;border-collapse:collapse;background-color:#1f2937;border-radius:8px;overflow:hidden;">
      <thead>
        <tr style="background-color:#374151;">
          <th style="padding:12px;text-align:left;color:#d1d5db;font-size:13px;">Title</th>
          <th style="padding:12px;text-align:left;color:#d1d5db;font-size:13px;">Company</th>
          <th style="padding:12px;text-align:center;color:#d1d5db;font-size:13px;">Score</th>
          <th style="padding:12px;text-align:left;color:#d1d5db;font-size:13px;">Location</th>
          <th style="padding:12px;text-align:left;color:#d1d5db;font-size:13px;">Salary</th>
          <th style="padding:12px;text-align:center;color:#d1d5db;font-size:13px;">Link</th>
        </tr>
      </thead>
      <tbody style="color:#e5e7eb;font-size:13px;">
        {rows}
      </tbody>
    </table>
    <p style="color:#6b7280;font-size:12px;margin-top:24px;">Sent by JobPilot. Manage preferences in your dashboard.</p>
  </div>
</body>
</html>"""


def send_email(to_email: str, jobs: list[dict]):
    """Send the digest email via Gmail SMTP."""
    count = len(jobs)
    subject = f"Your Weekly Job Matches — {count} new opportunities"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email

    html = build_email_html(jobs)
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())

    logger.info(f"Sent digest to {to_email} with {count} jobs")


def run():
    """Main worker loop: process all enabled digest users."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("Missing Supabase config")
        return
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.error("Missing Gmail config")
        return

    sb = get_service_client()

    # Fetch all enabled email preferences
    result = sb.table("email_preferences").select("*").eq("enabled", True).execute()
    users = result.data or []
    logger.info(f"Found {len(users)} users with digest enabled")

    for pref in users:
        user_id = pref["user_id"]
        frequency = pref.get("frequency", "weekly")
        last_sent_at = pref.get("last_sent_at")
        to_email = pref.get("email", "")

        if not to_email:
            logger.warning(f"No email for user {user_id}, skipping")
            continue

        if not should_send(frequency, last_sent_at):
            logger.info(f"Skipping user {user_id} — not due yet (frequency={frequency})")
            continue

        # Load user profile
        profile_result = sb.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
        if not profile_result.data:
            logger.warning(f"No profile for user {user_id}, skipping")
            continue

        row = profile_result.data
        core_skills = row.get("core_skills") or []
        if not core_skills:
            logger.warning(f"User {user_id} has no core_skills, skipping")
            continue

        profile = {
            "core_skills": core_skills,
            "years_experience": row.get("years_experience", 0),
            "current_role": row.get("current_role", ""),
        }

        logger.info(f"Searching jobs for user {user_id} ({to_email})")
        try:
            jobs = search_jobs_for_user(profile)
        except Exception as e:
            logger.error(f"Error searching for user {user_id}: {e}")
            continue

        if not jobs:
            logger.info(f"No matches above {SCORE_THRESHOLD} for user {user_id}")
            continue

        try:
            send_email(to_email, jobs)
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            continue

        # Auto-log emailed jobs to user's tracker
        try:
            logged = 0
            for job in jobs:
                existing = (
                    sb.table("jobs")
                    .select("id")
                    .eq("user_id", user_id)
                    .eq("title", job["title"])
                    .eq("company", job["company"])
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    continue
                sb.table("jobs").insert({
                    "user_id": user_id,
                    "title": job["title"],
                    "company": job["company"],
                    "url": job.get("url", ""),
                    "score": job.get("score", 0),
                    "location": job.get("location", ""),
                    "salary": job.get("salary", ""),
                    "source": "email_digest",
                    "status": "new",
                }).execute()
                logged += 1
            if logged:
                logger.info(f"Auto-logged {logged} jobs to tracker for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to auto-log jobs for user {user_id}: {e}")

        # Update last_sent_at
        sb.table("email_preferences").update({
            "last_sent_at": datetime.now(timezone.utc).isoformat(),
        }).eq("user_id", user_id).execute()


if __name__ == "__main__":
    run()
