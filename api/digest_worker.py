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

# Remove current directory (api/) from sys.path to prevent namespace shadowing of 'supabase' package
sys.path = [p for p in sys.path if p and p != "" and Path(p).resolve() != Path(__file__).resolve().parent]

from supabase import create_client

class ScanCancelledException(Exception):
    pass

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


def search_jobs_for_user(profile: dict, sb=None, user_id=None, scan_id=None) -> list[dict]:
    """Run job search using user's profile and return scored results."""
    import daily_scan as ds

    try:
        ds._rebuild_precompiled_patterns()
    except Exception:
        pass

    batches_list = profile.get("batches") or ["all"]
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
            ds.JOB_SOURCES
            + ds.EU_JOB_SOURCES
            + ds.GLOBAL_JOB_SOURCES
            + ds.APAC_JOB_SOURCES
            + ds.US_CANADA_JOB_SOURCES
            + ds.MIDDLE_EAST_JOB_SOURCES
            + ds.REMOTE_JOB_SOURCES
        )
    else:
        if "india" in batches_list:
            all_sources += ds.JOB_SOURCES
        if "europe_companies" in batches_list:
            all_sources += ds.EU_JOB_SOURCES
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

    for idx, source in enumerate(all_sources, 1):
        if sb and user_id and scan_id and idx % 2 == 0:  # Check database every 2 sources
            try:
                pref_result = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
                if pref_result and pref_result.data:
                    curr_history = pref_result.data.get("sent_history") or []
                    has_running = any(isinstance(x, str) and x.startswith("RUNNING:") and f"scan_id:{scan_id}" in x for x in curr_history)
                    if not has_running:
                        logger.info(f"Target scan_id {scan_id} was cancelled by user. Terminating search.")
                        raise ScanCancelledException("Scan was cancelled by user")
            except ScanCancelledException:
                raise
            except Exception as e:
                logger.warning(f"Error checking cancel status in runner loop: {e}")

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

    # 2. Run Europe Job Boards directly if "europe_boards" is requested!
    if "europe_boards" in batches_list:
        logger.info("[DIGEST-BG-WORKER] Triggering direct Europe Job Boards scrapers (Arbeitnow, IamExpat, TogetherAbroad)...")
        
        # Build queries based on core skills
        queries = [s.strip() for s in profile.get("core_skills", [])[:3] if s.strip()]
        if not queries:
            queries = ["Python"]
            
        board_mapping = [
            ("Arbeitnow", ds.search_arbeitnow, ["Remote"]),
            ("IamExpat", ds.search_iamexpat, ["Netherlands"]),
            ("TogetherAbroad", ds.search_togetherabroad, ["Netherlands"])
        ]
        
        for board_name, board_fn, locations in board_mapping:
            logger.info(f"[DIGEST-BG-WORKER] Scraping Europe Board: '{board_name}'...")
            for query in queries:
                for loc in locations:
                    try:
                        logger.info(f"[DIGEST-BG-WORKER] Calling {board_name} for query='{query}' @ location='{loc}'...")
                        board_jobs = board_fn(query, location=loc)
                        logger.info(f"[DIGEST-BG-WORKER] {board_name} returned {len(board_jobs) if board_jobs else 0} jobs.")
                        if not board_jobs:
                            continue
                            
                        for job in board_jobs:
                            key = (job.get("title", "").lower().strip(), job.get("company", "").lower().strip())
                            if key in seen:
                                continue
                            seen.add(key)
                            
                            # Score job
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
                                logger.info(f"[DIGEST-BG-WORKER] Match verified on Board {board_name}! '{job.get('title')}' at '{job.get('company')}' -> Score: {score}")
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
                    except Exception as be:
                        logger.error(f"[DIGEST-BG-WORKER] Board {board_name} failed for query='{query}': {be}")

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
        if isinstance(core_skills, str):
            try:
                import json
                core_skills = json.loads(core_skills)
            except Exception:
                core_skills = []

        if not core_skills or not isinstance(core_skills, list):
            logger.warning(f"User {user_id} has no core_skills, skipping")
            continue

        profile = {
            "core_skills": core_skills,
            "years_experience": row.get("years_experience", 0),
            "current_role": row.get("current_role", ""),
            "batches": pref.get("batches") or ["all"]
        }

        logger.info(f"Searching jobs for user {user_id} ({to_email})")
        import time
        try:
            jobs = search_jobs_for_user(profile)
        except Exception as e:
            logger.error(f"Error searching for user {user_id}: {e}")
            try:
                pref_res = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
                curr_history = pref_res.data.get("sent_history") or [] if pref_res and pref_res.data else []
                new_history = list(curr_history)
                new_history.append(f"FAILED_DAILY:{int(time.time())}|error:{str(e)}")
                sb.table("email_preferences").update({"sent_history": new_history}).eq("user_id", user_id).execute()
            except Exception as he:
                logger.error(f"Failed to update scheduled failure history: {he}")
            continue

        if not jobs:
            logger.info(f"No matches above {SCORE_THRESHOLD} for user {user_id}")
            try:
                pref_res = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
                curr_history = pref_res.data.get("sent_history") or [] if pref_res and pref_res.data else []
                new_history = list(curr_history)
                new_history.append(f"COMPLETED_DAILY:{int(time.time())}|jobs:0")
                sb.table("email_preferences").update({
                    "last_sent_at": datetime.now(timezone.utc).isoformat(),
                    "sent_history": new_history
                }).eq("user_id", user_id).execute()
            except Exception as he:
                logger.error(f"Failed to update scheduled zero-match success history: {he}")
            continue

        try:
            send_email(to_email, jobs)
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            try:
                pref_res = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
                curr_history = pref_res.data.get("sent_history") or [] if pref_res and pref_res.data else []
                new_history = list(curr_history)
                new_history.append(f"FAILED_DAILY:{int(time.time())}|error:Email dispatch failed - {str(e)}")
                sb.table("email_preferences").update({"sent_history": new_history}).eq("user_id", user_id).execute()
            except Exception as he:
                logger.error(f"Failed to update scheduled email failure history: {he}")
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

        # Update last_sent_at and save success history
        try:
            pref_res = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
            curr_history = pref_res.data.get("sent_history") or [] if pref_res and pref_res.data else []
            new_history = list(curr_history)
            new_history.append(f"COMPLETED_DAILY:{int(time.time())}|jobs:{len(jobs)}")
            sb.table("email_preferences").update({
                "last_sent_at": datetime.now(timezone.utc).isoformat(),
                "sent_history": new_history,
            }).eq("user_id", user_id).execute()
        except Exception as e:
            logger.error(f"Failed to update scheduled success history: {e}")


def run_one_user(user_id: str, scan_id: str = None):
    logger.info(f"Forcing immediate manual digest run for user_id: {user_id}, scan_id: {scan_id}")
    sb = get_service_client()
    
    pref_result = sb.table("email_preferences").select("*").eq("user_id", user_id).maybe_single().execute()
    if not pref_result.data:
        logger.error(f"No email preferences found for user_id {user_id}")
        return
    pref = pref_result.data
    to_email = pref.get("email") or ""
    if not to_email:
        logger.error(f"No email address configured for user_id {user_id}")
        return

    profile_result = sb.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
    if not profile_result.data:
        logger.error(f"No profile found for user_id {user_id}")
        return
        
    row = profile_result.data
    core_skills = row.get("core_skills") or []
    if isinstance(core_skills, str):
        try:
            import json
            core_skills = json.loads(core_skills)
        except Exception:
            core_skills = []

    if not core_skills or not isinstance(core_skills, list):
        logger.error(f"User {user_id} has no core_skills")
        return

    batches_list = ["all"]
    # Look for the target RUNNING token in sent_history to extract batches
    curr_history = pref.get("sent_history") or []
    target_token = None
    for x in curr_history:
        if isinstance(x, str) and x.startswith("RUNNING:"):
            if scan_id and f"scan_id:{scan_id}" in x:
                target_token = x
                break
            elif not scan_id:
                target_token = x
                break

    if target_token:
        # Extract batches from token e.g. "batches:india,europe"
        parts = target_token.split("|")
        for part in parts:
            if part.startswith("batches:"):
                batches_list = part.replace("batches:", "").split(",")
                break
    else:
        batches_list = pref.get("batches") or ["all"]

    profile = {
        "core_skills": core_skills,
        "years_experience": row.get("years_experience", 0),
        "current_role": row.get("current_role", ""),
        "batches": batches_list
    }

    # Check if this scan has already been cancelled by the user before execution starts
    if scan_id:
        try:
            pref_result = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
            if pref_result and pref_result.data:
                curr_history = pref_result.data.get("sent_history") or []
                has_running = any(isinstance(x, str) and x.startswith("RUNNING:") and f"scan_id:{scan_id}" in x for x in curr_history)
                if not has_running:
                    logger.info(f"Target scan_id {scan_id} was cancelled before starting. Terminating runner.")
                    return
        except Exception as e:
            logger.warning(f"Error checking initial cancel: {e}")

    # Write RUNNING:Scraping to sent_history in database
    github_run_id = os.environ.get("GITHUB_RUN_ID") or "pending"
    batches_str = ",".join(batches_list)
    running_token = f"RUNNING:Scraping in GitHub Actions...|batches:{batches_str}|scan_id:{scan_id or 'unknown'}|run_id:{github_run_id}|{int(datetime.now().timestamp())}"
    
    try:
        new_history = []
        replaced = False
        for x in curr_history:
            if isinstance(x, str) and x.startswith("RUNNING:"):
                if scan_id and f"scan_id:{scan_id}" in x:
                    new_history.append(running_token)
                    replaced = True
                elif not scan_id and not replaced:
                    new_history.append(running_token)
                    replaced = True
                else:
                    new_history.append(x)
            else:
                new_history.append(x)
                
        if not replaced:
            new_history.append(running_token)
            
        sb.table("email_preferences").update({
            "sent_history": new_history,
        }).eq("user_id", user_id).execute()
        logger.info(f"Registered/updated RUNNING token in sent_history with GITHUB_RUN_ID={github_run_id}")
    except Exception as e:
        logger.error(f"Failed to set running token: {e}")

    logger.info(f"Searching jobs for user {user_id} ({to_email}) in batches: {batches_list}")
    try:
        jobs = search_jobs_for_user(profile, sb=sb, user_id=user_id, scan_id=scan_id)
    except ScanCancelledException:
        logger.info(f"Scan {scan_id} was cancelled by user. Exiting runner silently.")
        return
    except Exception as e:
        logger.error(f"Error searching for user {user_id}: {e}")
        try:
            pref_result = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
            if pref_result and pref_result.data:
                curr_history = pref_result.data.get("sent_history") or []
                filtered = []
                for x in curr_history:
                    if isinstance(x, str) and x.startswith("RUNNING:"):
                        if scan_id and f"scan_id:{scan_id}" in x:
                            continue
                        elif not scan_id:
                            continue
                    filtered.append(x)
                import time
                filtered.append(f"FAILED_INSTANT:{int(time.time())}|error:{str(e)}")
                sb.table("email_preferences").update({"sent_history": filtered}).eq("user_id", user_id).execute()
        except Exception as he:
            logger.error(f"Failed to update instant failure history: {he}")
        return

    try:
        # Load final history
        pref_result = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
        curr_history = pref_result.data.get("sent_history") or [] if pref_result and pref_result.data else []
        
        # Remove only the specific running token
        clean_history = []
        for x in curr_history:
            if isinstance(x, str) and x.startswith("RUNNING:"):
                if scan_id and f"scan_id:{scan_id}" in x:
                    continue
                elif not scan_id:
                    continue
            clean_history.append(x)
            
        import time
        clean_history.append(f"COMPLETED_INSTANT:{int(time.time())}|jobs:{len(jobs)}")
        
        sb.table("email_preferences").update({
            "sent_history": clean_history,
            "last_sent_at": datetime.now(timezone.utc).isoformat(),
        }).eq("user_id", user_id).execute()
    except Exception as e:
        logger.error(f"Failed to update final history: {e}")

    if not jobs:
        logger.info(f"No matches above {SCORE_THRESHOLD} for user {user_id}")
        return

    try:
        send_email(to_email, jobs)
        logger.info(f"Successfully emailed {len(jobs)} matches to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")

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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run digest worker")
    parser.add_argument("--user-id", type=str, help="Run immediately for a specific user ID")
    parser.add_argument("--scan-id", type=str, help="Specify scan ID to track")
    args = parser.parse_args()
    
    if args.user_id:
        run_one_user(args.user_id, scan_id=args.scan_id)
    else:
        run()
