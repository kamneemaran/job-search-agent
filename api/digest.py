"""Digest preference and send endpoints."""
import os
import sys
import logging
import threading
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from typing import Optional

logger = logging.getLogger("jobpilot.digest")

from api.models import DigestPreferences, DigestSendRequest
from api.supabase import get_user_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import daily_scan as ds

router = APIRouter(prefix="/api/digest", tags=["digest"])
_profile_lock = threading.Lock()


@router.get("/preferences", response_model=DigestPreferences)
async def get_digest_preferences(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(401, "Authorization required")

    sb = get_user_client(authorization)
    user = sb.auth.get_user().user
    result = sb.table("email_preferences").select("*").eq("user_id", user.id).maybe_single().execute()

    if not result.data:
        return DigestPreferences()

    row = result.data
    
    batches_data = row.get("batches") or ["all"]
    if isinstance(batches_data, str):
        try:
            import json
            batches_data = json.loads(batches_data)
        except Exception:
            batches_data = ["all"]

    return DigestPreferences(
        enabled=row.get("enabled", True),
        frequency=row.get("frequency", "weekly"),
        email=row.get("email", ""),
        day_of_week=row.get("day_of_week", "monday"),
        day_of_month=row.get("day_of_month", 1),
        time_of_day=row.get("time_of_day", "09:00"),
        sent_history=row.get("sent_history") or [],
        batches=batches_data,
    )


@router.put("/preferences", response_model=DigestPreferences)
async def update_digest_preferences(
    prefs: DigestPreferences,
    authorization: Optional[str] = Header(None),
):
    if not authorization:
        raise HTTPException(401, "Authorization required")

    sb = get_user_client(authorization)
    user = sb.auth.get_user().user

    data = {
        "user_id": user.id,
        "enabled": prefs.enabled,
        "frequency": prefs.frequency,
        "email": prefs.email,
        "day_of_week": prefs.day_of_week,
        "day_of_month": prefs.day_of_month,
        "time_of_day": prefs.time_of_day,
        "sent_history": prefs.sent_history,
        "batches": prefs.batches,
    }

    try:
        sb.table("email_preferences").upsert(data, on_conflict="user_id").execute()
    except Exception as e:
        # If the column "batches" does not exist in the database, let's execute an alter script first!
        try:
            sb.table("email_preferences").select("batches").limit(1).execute()
        except Exception:
            try:
                # Add column dynamically
                # (Note: standard PostgREST cannot alter table, but if it fails we can catch and log)
                print(f"Error: public.email_preferences has no 'batches' column. Please run the SQL alter table command. {e}")
            except Exception:
                pass
        # Remove batches from dict so it can upsert successfully even if column hasn't been added yet
        data.pop("batches", None)
        sb.table("email_preferences").upsert(data, on_conflict="user_id").execute()

    return prefs


def run_background_digest_scan(
    user_id: str,
    to_email: str,
    profile: dict,
    batches_list: list,
    authorization: str,
    history_dates: list,
    now_iso: str,
    running_token: str,
    start_index: int = 1,
    initial_matches: list = None,
):
    logger.info(f"[DIGEST-BG-WORKER] Starting async background job scan for user_id={user_id}, target_email={to_email}, start_index={start_index}, initial_matches_count={len(initial_matches) if initial_matches else 0}")
    sb = get_user_client(authorization)
    try:
        all_sources = []
        if "all" in batches_list:
            all_sources = (
                ds.JOB_SOURCES + ds.EU_JOB_SOURCES + ds.GLOBAL_JOB_SOURCES
                + ds.APAC_JOB_SOURCES + ds.US_CANADA_JOB_SOURCES
                + ds.MIDDLE_EAST_JOB_SOURCES + ds.REMOTE_JOB_SOURCES
            )
        else:
            if "india" in batches_list:
                all_sources += ds.JOB_SOURCES
            if "europe_companies" in batches_list:
                all_sources += ds.EU_JOB_SOURCES
            if "europe_boards" in batches_list:
                all_sources += [s for s in ds.GLOBAL_JOB_SOURCES if s.get("name") in ("Arbeitnow", "IamExpat", "TogetherAbroad")]
            if "middle_east" in batches_list:
                all_sources += ds.MIDDLE_EAST_JOB_SOURCES
            if "apac" in batches_list:
                all_sources += ds.APAC_JOB_SOURCES
            if "us_canada" in batches_list:
                all_sources += ds.US_CANADA_JOB_SOURCES
            if "remote" in batches_list:
                all_sources += ds.REMOTE_JOB_SOURCES

        logger.info(f"[DIGEST-BG-WORKER] Compiled {len(all_sources)} total job sources to fetch.")

        results = list(initial_matches) if initial_matches else []
        seen = {(j.get("title", "").lower().strip(), j.get("company", "").lower().strip()) for j in results}

        aborted = False
        for idx, source in enumerate(all_sources, 1):
            if idx < start_index:
                logger.info(f"[DIGEST-BG-WORKER] [{idx}/{len(all_sources)}] Skipping already completed source: '{source.get('name')}'")
                continue

            source_name = source.get("name", f"Source #{idx}")
            logger.info(f"[DIGEST-BG-WORKER] [{idx}/{len(all_sources)}] Scraping: '{source_name}'...")
            
            # Update database with current progress!
            try:
                import time
                progress_token = f"RUNNING:Scraping {source_name} ({idx}/{len(all_sources)})|{int(time.time())}"
                pref_result = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
                if pref_result and pref_result.data:
                    curr_history = pref_result.data.get("sent_history") or []
                    
                    # Check if there is an active RUNNING: token. If not, it means the user has cleared/reset the scan!
                    has_running = any(isinstance(x, str) and x.startswith("RUNNING:") for x in curr_history)
                    if not has_running:
                        logger.info(f"[DIGEST-BG-WORKER] RUNNING token not found in sent_history (aborted/reset by user). Terminating background scraper loop.")
                        aborted = True
                        break
                    
                    new_history = []
                    for item in curr_history:
                        if isinstance(item, str) and item.startswith("RUNNING:"):
                            continue
                        new_history.append(item)
                    new_history.append(progress_token)
                    sb.table("email_preferences").update({
                        "sent_history": new_history,
                    }).eq("user_id", user_id).execute()
            except Exception as e:
                logger.error(f"[DIGEST-BG-WORKER] Failed to update progress token: {e}")

            try:
                jobs = ds.fetch_jobs_from_source(source)
                logger.info(f"[DIGEST-BG-WORKER] [{idx}/{len(all_sources)}] Successfully parsed '{source_name}': fetched {len(jobs) if jobs else 0} raw jobs")
            except Exception as e:
                logger.error(f"[DIGEST-BG-WORKER] [{idx}/{len(all_sources)}] Scraper '{source_name}' failed: {e}", exc_info=True)
                continue

            for job in jobs:
                key = (job.get("title", "").lower().strip(), job.get("company", "").lower().strip())
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
                            job.get("title", ""), job.get("description", ""),
                            job.get("company", ""), job.get("location", ""),
                        )
                    finally:
                        ds.PROFILE["core_skills"] = orig_skills
                        ds.PROFILE["years_experience"] = orig_years

                if score >= 65:
                    logger.info(f"[DIGEST-BG-WORKER] Match verified! '{job.get('title')}' at '{job.get('company')}' -> Score: {score}")
                    salary_info = ds.get_salary_info(
                        job.get("company", ""), job.get("title", ""), job.get("description", ""),
                    )
                    job_match = {
                        "title": job.get("title", ""),
                        "company": job.get("company", ""),
                        "score": score,
                        "location": job.get("location", ""),
                        "salary": ds._format_salary(salary_info) if salary_info else "",
                        "url": job.get("url", ""),
                    }
                    results.append(job_match)

                    # Persist match in real-time inside database to safeguard progress
                    try:
                        import json
                        match_token = f"MATCH:{json.dumps(job_match)}"
                        pref_result = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
                        if pref_result and pref_result.data:
                            curr_history = pref_result.data.get("sent_history") or []
                            new_history = list(curr_history)
                            new_history.append(match_token)
                            sb.table("email_preferences").update({
                                "sent_history": new_history,
                            }).eq("user_id", user_id).execute()
                            logger.info(f"[DIGEST-BG-WORKER] Real-time saved job match in database sent_history.")
                    except Exception as pe:
                        logger.error(f"[DIGEST-BG-WORKER] Failed to persist job match to sent_history: {pe}")

        if aborted:
            logger.info(f"[DIGEST-BG-WORKER] Background scan was aborted. Skipping email generation and final updates.")
            return

        results.sort(key=lambda x: x["score"], reverse=True)
        logger.info(f"[DIGEST-BG-WORKER] Finished processing. Total unique jobs evaluated: {len(seen)}. Matches above threshold: {len(results)}.")

        # Clean sent_history: keep only non-RUNNING and non-MATCH entries, and append now_iso
        clean_history = [dt.isoformat() for dt in history_dates]
        clean_history.append(now_iso)

        if not results:
            logger.warning(f"[DIGEST-BG-WORKER] No job matches above 65 found for user_id={user_id}. Skipping email dispatch.")
            clean_history.append("FINISHED:0")
            sb.table("email_preferences").upsert({
                "user_id": user_id,
                "last_sent_at": now_iso,
                "sent_history": clean_history,
            }, on_conflict="user_id").execute()
            logger.info(f"[DIGEST-BG-WORKER] Updated sent history for user_id={user_id} (completed with 0 matches)")
            return

        logger.info(f"[DIGEST-BG-WORKER] Constructing email template and sending {len(results)} matches to {to_email}...")
        try:
            from daily_scan import build_email_html, send_email
            html = build_email_html(results)
            ok = send_email(html, subject=f"Your Job Matches — {len(results)} opportunities — {datetime.now().strftime('%d %b %Y')}", recipient=to_email)
            if ok:
                logger.info(f"[DIGEST-BG-WORKER] Email dispatch successful for user_id={user_id} -> {to_email}")
            else:
                logger.error(f"[DIGEST-BG-WORKER] Email delivery failed (send_email returned False) for {to_email}")
        except Exception as e:
            logger.error(f"[DIGEST-BG-WORKER] Exception raised during email compilation/dispatch: {e}", exc_info=True)
            ok = False

        # Clear active status/matches and save clean run history to database
        clean_history.append(f"FINISHED:{len(results)}")
        sb.table("email_preferences").upsert({
            "user_id": user_id,
            "last_sent_at": now_iso,
            "sent_history": clean_history,
        }, on_conflict="user_id").execute()
        logger.info(f"[DIGEST-BG-WORKER] Successfully updated sent history in Supabase (cleared progress tokens) for user_id={user_id}")

    except Exception as e:
        logger.error(f"[DIGEST-BG-WORKER] Unexpected error in background worker: {e}", exc_info=True)
        try:
            pref_result = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
            if pref_result and pref_result.data:
                curr_history = pref_result.data.get("sent_history") or []
                filtered_history = [x for x in curr_history if x != running_token]
                sb.table("email_preferences").update({
                    "sent_history": filtered_history,
                }).eq("user_id", user_id).execute()
        except Exception as cleanup_err:
            logger.error(f"[DIGEST-BG-WORKER] Cleanup token failed: {cleanup_err}")


@router.post("/send")
async def send_digest(
    req: DigestSendRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
):
    if not authorization:
        logger.warning("[DIGEST-TRIGGER] Rejected request: Authorization header missing.")
        raise HTTPException(401, "Authorization required")

    sb = get_user_client(authorization)
    user = sb.auth.get_user().user
    user_id = user.id

    # Get user profile
    profile_row = sb.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
    if not profile_row.data:
        logger.error(f"[DIGEST-TRIGGER] Profile not found for user_id={user_id}. Upload a resume first.")
        raise HTTPException(400, "Profile not found. Upload a resume first.")

    row = profile_row.data
    core_skills = row.get("core_skills") or []
    if isinstance(core_skills, str):
        try:
            import json
            core_skills = json.loads(core_skills)
        except Exception as e:
            logger.error(f"[DIGEST-TRIGGER] Failed to parse core_skills JSON for user_id={user_id}: {e}")
            core_skills = []

    if not core_skills or not isinstance(core_skills, list):
        logger.error(f"[DIGEST-TRIGGER] No core skills array found for user_id={user_id}.")
        raise HTTPException(400, "No core skills found. Upload a resume first.")

    profile = {
        "core_skills": core_skills,
        "years_experience": row.get("years_experience", 0) or 0,
        "current_role": row.get("current_role", ""),
    }

    to_email = req.email or row.get("email") or user.email or ""
    logger.info(f"[DIGEST-TRIGGER] Manual email digest send initiated for user_id={user_id}, target_email={to_email}, schedule={req.schedule}")
    logger.info(f"[DIGEST-TRIGGER] Matching profile: years_experience={profile['years_experience']}, core_skills={profile['core_skills']}")

    if req.schedule in ("now", "resume"):
        # Get email preferences for frequency and sent history
        pref_result = sb.table("email_preferences").select("*").eq("user_id", user_id).maybe_single().execute()
        pref_row = pref_result.data if pref_result else None

        frequency = pref_row.get("frequency", "weekly") if pref_row else "weekly"
        sent_history = pref_row.get("sent_history", []) if pref_row else []

        start_index = 1
        initial_matches = []
        now = datetime.now()

        # If resume is requested
        if req.schedule == "resume":
            import re
            running_item = next((x for x in sent_history if isinstance(x, str) and x.startswith("RUNNING:")), None)
            if running_item:
                # Find (X/Y) progress
                match_idx = re.search(r"\((\d+)/\d+\)", running_item)
                if match_idx:
                    start_index = int(match_idx.group(1))
                    logger.info(f"[DIGEST-TRIGGER] Resuming scan for user_id={user_id} from index {start_index} based on active status.")

            # Load all real-time MATCH: tokens stored previously
            for item in sent_history:
                if isinstance(item, str) and item.startswith("MATCH:"):
                    try:
                        import json
                        match_data = json.loads(item.replace("MATCH:", "", 1))
                        initial_matches.append(match_data)
                    except Exception:
                        pass
            logger.info(f"[DIGEST-TRIGGER] Loaded {len(initial_matches)} pre-saved matches for user_id={user_id} during resume.")

        # If "now" (start over), clear any running or matches entries
        elif req.schedule == "now":
            any_running = any(isinstance(x, str) and x.startswith("RUNNING:") for x in sent_history)
            if any_running:
                logger.warning(f"[DIGEST-TRIGGER] Rejected start-over request for user_id={user_id} — scan already running.")
                raise HTTPException(400, "A background scan is already in progress. Please use force-reset or wait for it.")

            # Clean and filter sent history
            sent_history = [x for x in sent_history if isinstance(x, str) and not x.startswith("MATCH:") and not x.startswith("RUNNING:") and not x.startswith("FINISHED:")]

        logger.info(f"[DIGEST-TRIGGER] Checking rate limit history for user_id={user_id}. Past sent count: {len(sent_history)}")

        # Enforce rate limits based on user requirements:
        history_dates = []
        for ts in sent_history:
            if not isinstance(ts, str):
                continue
            if ts.startswith("RUNNING:") or ts.startswith("MATCH:") or ts.startswith("FINISHED:"):
                continue
            try:
                # Parse ISO timestamp
                if "T" in ts:
                    dt = datetime.fromisoformat(ts)
                else:
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
                # If within 30 days, keep it
                if (now - dt).days < 30:
                    history_dates.append(dt)
            except Exception as e:
                logger.debug(f"[DIGEST-TRIGGER] Skip parsing history timestamp '{ts}': {e}")

        # Check limit logic: Flat 8 hours limit on manual trigger
        for dt in history_dates:
            diff_hours = (now - dt).total_seconds() / 3600.0
            if diff_hours < 8.0:
                logger.warning(f"[DIGEST-TRIGGER] User user_id={user_id} was rate-limited. Last run was {diff_hours:.2f} hours ago (less than 8h threshold).")
                raise HTTPException(
                    429,
                    "You already requested a scan recently. Your on-demand digest is running in the background and compiling jobs from multiple regions and company career pages. Please check your inbox in a few minutes, or wait up to 4-5 hours before requesting another scan."
                )

        try:
            ds._rebuild_precompiled_patterns()
        except Exception as e:
            logger.warning(f"[DIGEST-TRIGGER] Non-fatal: Pattern rebuild exception: {e}")

        batches_list = pref_row.get("batches") if pref_row else ["all"]
        if isinstance(batches_list, str):
            try:
                import json
                batches_list = json.loads(batches_list)
            except Exception as e:
                logger.warning(f"[DIGEST-TRIGGER] Failed to parse batches string {batches_list}: {e}")
                batches_list = ["all"]
        if not batches_list:
            batches_list = ["all"]

        logger.info(f"[DIGEST-TRIGGER] Active target batches list: {batches_list}")

        # Set the running token in sent_history
        import time
        running_token = f"RUNNING:Initializing...|{int(time.time())}"
        # If we are resuming, we keep the existing running item (which will be updated soon)
        if req.schedule == "resume":
            existing_running = next((x for x in sent_history if isinstance(x, str) and x.startswith("RUNNING:")), None)
            if existing_running:
                running_token = existing_running
        else:
            sent_history.append(running_token)

        try:
            sb.table("email_preferences").upsert({
                "user_id": user_id,
                "sent_history": sent_history,
            }, on_conflict="user_id").execute()
            logger.info(f"[DIGEST-TRIGGER] Initialized scan state in database sent_history for user_id={user_id}")
        except Exception as e:
            logger.error(f"[DIGEST-TRIGGER] Failed to initialize scan state: {e}")
            raise HTTPException(500, "Failed to initialize scan state in database.")

        # Check if GitHub Dispatch token is configured.
        # We delegate the scan to GitHub Actions for massive speed, abundant RAM, and 0% Railway CPU/Memory consumption!
        gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
        gh_repo = os.environ.get("GITHUB_REPO") or os.environ.get("GH_REPO")
        
        fallback_warning = None
        
        if not gh_token and not gh_repo:
            fallback_warning = "Neither GITHUB_TOKEN nor GITHUB_REPO are configured in Railway environment variables."
        elif not gh_token:
            fallback_warning = "GITHUB_TOKEN is missing in Railway environment variables."
        elif not gh_repo:
            fallback_warning = "GITHUB_REPO is missing in Railway environment variables."
        else:
            # Clean up repo name (extract owner/repo if full URL was provided)
            repo_clean = gh_repo.strip()
            if "github.com/" in repo_clean:
                repo_clean = repo_clean.split("github.com/")[-1]
            if repo_clean.endswith(".git"):
                repo_clean = repo_clean[:-4]
            repo_clean = repo_clean.strip("/")
            
            logger.info(f"[DIGEST-TRIGGER] GitHub token and repo detected ({repo_clean}). Dispatching scan to GitHub Actions cloud worker...")
            
            # Update database running token to reflect GitHub Actions progress
            import time
            dispatch_token = f"RUNNING:Starting scan in GitHub Actions Cloud...|{int(time.time())}"
            # Replace any old running items
            clean_history = [x for x in sent_history if not (isinstance(x, str) and x.startswith("RUNNING:"))]
            clean_history.append(dispatch_token)
            
            try:
                sb.table("email_preferences").update({
                    "sent_history": clean_history,
                }).eq("user_id", user_id).execute()
            except Exception as se:
                logger.error(f"[DIGEST-TRIGGER] Failed to update sent_history with GitHub token: {se}")

            import requests
            dispatch_url = f"https://api.github.com/repos/{repo_clean}/dispatches"
            headers = {
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "JobPilot-API"
            }
            payload = {
                "event_type": "manual_scan",
                "client_payload": {
                    "user_id": user_id,
                }
            }
            
            try:
                resp = requests.post(dispatch_url, json=payload, headers=headers, timeout=10)
                if resp.status_code == 204:
                    logger.info(f"[DIGEST-TRIGGER] Successfully dispatched repository_dispatch to {repo_clean}!")
                    return {
                        "message": "Scan dispatched to GitHub Actions Cloud. Your master scan is compiling on high-performance cloud servers. Check your inbox soon!",
                        "sent": True,
                        "count": len(initial_matches)
                    }
                else:
                    fallback_warning = f"GitHub API dispatch failed with status {resp.status_code}: {resp.text}"
                    logger.error(f"[DIGEST-TRIGGER] {fallback_warning}. Local scraper fallback is disabled.")
            except Exception as e:
                fallback_warning = f"GitHub API request failed: {str(e)}"
                logger.error(f"[DIGEST-TRIGGER] {fallback_warning}. Local scraper fallback is disabled.", exc_info=True)

        # If we reach here, the dispatch failed. We clean up the RUNNING token from the database
        # and throw an error back to the user, preventing local fallback as requested!
        try:
            clean_history = [x for x in sent_history if not (isinstance(x, str) and x.startswith("RUNNING:"))]
            sb.table("email_preferences").update({
                "sent_history": clean_history,
            }).eq("user_id", user_id).execute()
        except Exception as se:
            logger.error(f"[DIGEST-TRIGGER] Failed to clean up running token after dispatch failure: {se}")

        raise HTTPException(
            status_code=400,
            detail=f"GitHub Cloud scan failed to start: {fallback_warning}"
        )

    elif req.schedule == "never":
        logger.info(f"[DIGEST-TRIGGER] Disabling email digest for user_id={user_id}")
        sb.table("email_preferences").upsert({
            "user_id": user_id, "enabled": False, "frequency": "never",
        }, on_conflict="user_id").execute()
        return {"message": "Digest disabled", "schedule": "never", "sent": False, "count": 0}

    elif req.schedule in ("tomorrow", "weekly", "monthly"):
        logger.info(f"[DIGEST-TRIGGER] Updating email digest preference for user_id={user_id} to schedule={req.schedule}")
        sb.table("email_preferences").upsert({
            "user_id": user_id, "enabled": True, "frequency": req.schedule,
            "email": to_email,
        }, on_conflict="user_id").execute()
        return {"message": f"Digest scheduled {req.schedule}", "schedule": req.schedule, "sent": False, "count": 0}

    logger.warning(f"[DIGEST-TRIGGER] Unknown schedule value received: {req.schedule}")
    return {"message": f"Unknown schedule: {req.schedule}", "sent": False, "count": 0}


@router.post("/reset")
async def reset_digest_status(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(401, "Authorization required")

    sb = get_user_client(authorization)
    user = sb.auth.get_user().user
    user_id = user.id

    # Get current sent history
    pref_result = sb.table("email_preferences").select("sent_history").eq("user_id", user_id).maybe_single().execute()
    if pref_result and pref_result.data:
        curr_history = pref_result.data.get("sent_history") or []
        new_history = [x for x in curr_history if not (isinstance(x, str) and x.startswith("RUNNING:"))]
        
        sb.table("email_preferences").update({
            "sent_history": new_history,
        }).eq("user_id", user_id).execute()
        logger.info(f"[DIGEST-TRIGGER] Force reset running status for user_id={user_id}")

        # Try to automatically cancel any active GitHub Action workflows
        gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
        gh_repo = os.environ.get("GITHUB_REPO") or os.environ.get("GH_REPO")
        gh_cancelled_count = 0
        
        if gh_token and gh_repo:
            repo_clean = gh_repo.strip()
            if "github.com/" in repo_clean:
                repo_clean = repo_clean.split("github.com/")[-1]
            if repo_clean.endswith(".git"):
                repo_clean = repo_clean[:-4]
            repo_clean = repo_clean.strip("/")
            
            import requests
            runs_url = f"https://api.github.com/repos/{repo_clean}/actions/runs"
            headers = {
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "JobPilot-API"
            }
            try:
                # Fetch in-progress runs
                resp = requests.get(runs_url, params={"status": "in_progress"}, headers=headers, timeout=10)
                if resp.status_code == 200:
                    runs_data = resp.json()
                    for run in runs_data.get("workflow_runs", []):
                        run_id = run.get("id")
                        cancel_url = f"https://api.github.com/repos/{repo_clean}/actions/runs/{run_id}/cancel"
                        cancel_resp = requests.post(cancel_url, headers=headers, timeout=10)
                        if cancel_resp.status_code == 202:
                            logger.info(f"[DIGEST-RESET] Successfully cancelled active GitHub Action workflow run_id={run_id}")
                            gh_cancelled_count += 1
                        else:
                            logger.warning(f"[DIGEST-RESET] Failed to cancel run_id={run_id}: {cancel_resp.status_code} {cancel_resp.text}")
            except Exception as ge:
                logger.error(f"[DIGEST-RESET] Error attempting to cancel GitHub Action workflows: {ge}")

        if gh_cancelled_count > 0:
            msg = f"Scan status reset successfully. Aborted {gh_cancelled_count} active Cloud Actions workflow run(s) on GitHub."
        else:
            msg = "Scan status reset successfully. You can now start a new scan."

        return {"status": "success", "message": msg}

    return {"status": "no_changes", "message": "No active scan was found to reset."}
