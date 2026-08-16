"""Sync tracked jobs to user's Google Sheet."""
import os
import json
import base64
import logging
from datetime import datetime

logger = logging.getLogger("jobpilot.gsheet")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_gsheet_service():
    """Get a Google Sheets service instance.

    Tries in order:
    1. GOOGLE_SA_JSON env var (base64 encoded)
    2. GOOGLE_SERVICE_ACCOUNT_JSON env var (raw JSON, fallback)
    3. GSHEET_SERVICE_ACCOUNT env var (file path)
    4. gsheet_service_account.json (local file)
    """
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    # Check base64 env var
    b64_json = os.environ.get("GOOGLE_SA_JSON")
    if b64_json:
        try:
            decoded = base64.b64decode(b64_json).decode("utf-8")
            creds = Credentials.from_service_account_info(json.loads(decoded), scopes=SCOPES)
            return build("sheets", "v4", credentials=creds)
        except Exception:
            pass

    env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_json:
        try:
            creds = Credentials.from_service_account_info(json.loads(env_json), scopes=SCOPES)
            return build("sheets", "v4", credentials=creds)
        except Exception:
            pass

    sa_path = os.environ.get("GSHEET_SERVICE_ACCOUNT") or "gsheet_service_account.json"
    if not os.path.exists(sa_path):
        raise FileNotFoundError(
            f"Service account not found. "
            f"Set GOOGLE_SA_JSON env var (base64) or provide gsheet_service_account.json."
        )
    creds = Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def parse_sheet_url(url: str) -> str | None:
    """Extract spreadsheet ID from a Google Sheets URL.

    Supports: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit...
    """
    import re
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def sync_jobs_to_sheet(
    jobs: list[dict],
    sheet_url: str,
) -> bool:
    """Write tracked jobs to a Google Sheet.

    Creates columns matching user's tracker layout:
    Company, Role, Location, Application Status, Date Applied, Interview/Rej Date, Job URL
    """
    sheet_id = parse_sheet_url(sheet_url)
    if not sheet_id:
        logger.error(f"Invalid sheet URL: {sheet_url}")
        return False

    try:
        service = _get_gsheet_service()
        sheets_api = service.spreadsheets()

        # Ensure "job_matches" tab exists
        spreadsheet = sheets_api.get(spreadsheetId=sheet_id).execute()
        tab_name = "job_matches"
        existing_tabs = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

        if tab_name not in existing_tabs:
            sheets_api.batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
            ).execute()

        # Build rows with columns: Company, Role, Location, Application Status, Date Applied, Interview/Rej Date, Job URL
        headers = ["Company", "Role", "Location", "Application Status", "Date Applied", "Interview/Rej Date", "Job URL"]
        rows = [headers]
        for j in jobs:
            # Map status to Application Status format
            status = j.get("status", "new").lower()
            if status == "applied":
                app_status = "Applied"
            elif status == "rejected":
                app_status = "Rejected"
            elif status == "offer":
                app_status = "Offer"
            else:
                app_status = "New"
            
            rows.append([
                j.get("company", ""),
                j.get("title", ""),
                j.get("location", ""),
                app_status,
                (j.get("date_updated") or j.get("updated_at") or "")[:10],
                "",  # Interview/Rej Date (empty for now)
                j.get("url", ""),
            ])

        # Write to sheet (clear first, then write)
        range_str = f"'{tab_name}'!A1:G{len(rows)}"
        sheets_api.values().clear(
            spreadsheetId=sheet_id,
            range=tab_name,
        ).execute()
        sheets_api.values().update(
            spreadsheetId=sheet_id,
            range=range_str,
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        logger.info(f"Synced {len(jobs)} jobs to sheet {sheet_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to sync to sheet: {e}")
        return False


def read_jobs_from_sheet(
    sheet_url: str,
) -> list[dict]:
    """Read tracked jobs from a Google Sheet.

    Expects columns: Company, Role, Location, Application Status, Date Applied, Interview/Rej Date, Job URL
    """
    sheet_id = parse_sheet_url(sheet_url)
    if not sheet_id:
        return []

    try:
        service = _get_gsheet_service()
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        existing_tabs = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

        target_tab = "job_matches"
        if "job_matches" in existing_tabs:
            target_tab = "job_matches"
        elif "Job Tracker" in existing_tabs:
            target_tab = "Job Tracker"
        elif "All Jobs" in existing_tabs:
            target_tab = "All Jobs"
        elif existing_tabs:
            target_tab = existing_tabs[0]

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{target_tab}'!A:G",
        ).execute()

        values = result.get("values", [])
        if len(values) < 2:
            return []

        jobs = []
        for row in values[1:]:
            # Ensure the row is padded to at least 7 elements to prevent any IndexError
            row = list(row) + [""] * (7 - len(row))
            
            # Map columns: Company, Role, Location, Application Status, Date Applied, Interview/Rej Date, Job URL
            company = row[0].strip()
            title = row[1].strip()
            if not title or not company:
                continue

            # Map Application Status to status (applied, rejected, new, offer)
            app_status = row[3].strip().lower()
            status = "new"
            if "applied" in app_status:
                status = "applied"
            elif "rejected" in app_status or "rej" in app_status:
                status = "rejected"
            elif "offer" in app_status:
                status = "offer"

            jobs.append({
                "score": 0,  # Not in sheet, will be calculated later
                "title": title,
                "company": company,
                "location": row[2].strip(),
                "url": row[6].strip(),
                "company_link": "",
                "status": status,
                "date_updated": row[4].strip(),  # Date Applied
            })
        return jobs
    except Exception as e:
        logger.error(f"Failed to read from sheet: {e}")
        return []
