"""Sync tracked jobs to user's Google Sheet."""
import os
import json
import base64
import logging
from datetime import datetime

logger = logging.getLogger("jobpilot.gsheet")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_gsheet_service(sa_json: str | None = None):
    """Get a Google Sheets service instance.

    Tries in order:
    1. User-provided sa_json
    2. GOOGLE_SA_JSON env var (base64 encoded)
    3. GOOGLE_SERVICE_ACCOUNT_JSON env var (raw JSON, fallback)
    4. GSHEET_SERVICE_ACCOUNT env var (file path)
    5. gsheet_service_account.json (local file)
    """
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    if sa_json:
        creds = Credentials.from_service_account_info(json.loads(sa_json), scopes=SCOPES)
        return build("sheets", "v4", credentials=creds)

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
    sa_json: str | None = None,
) -> bool:
    """Write tracked jobs to a Google Sheet.

    Creates a 'Job Tracker' tab with columns matching the official layout:
    Score, Title, Company, Location, URL, Company Link, Status, Date Found
    """
    sheet_id = parse_sheet_url(sheet_url)
    if not sheet_id:
        logger.error(f"Invalid sheet URL: {sheet_url}")
        return False

    try:
        service = _get_gsheet_service(sa_json)
        sheets_api = service.spreadsheets()

        # Ensure "Job Tracker" tab exists (or "All Jobs" if preferred)
        spreadsheet = sheets_api.get(spreadsheetId=sheet_id).execute()
        tab_name = "Job Tracker"
        existing_tabs = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

        if "All Jobs" in existing_tabs:
            tab_name = "All Jobs"

        if tab_name not in existing_tabs:
            sheets_api.batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
            ).execute()

        # Build rows
        headers = ["Score", "Title", "Company", "Location", "URL", "Company Link", "Status", "Date Found"]
        rows = [headers]
        for j in jobs:
            company = j.get("company", "")
            comp_link = j.get("company_link") or j.get("company_url") or ""
            if not comp_link and company:
                comp_link = f"https://www.linkedin.com/company/{company.lower().replace(' ', '')}"
            
            rows.append([
                str(j.get("score", 0)),
                j.get("title", ""),
                company,
                j.get("location", ""),
                j.get("url", ""),
                comp_link,
                j.get("status", "new"),
                (j.get("updated_at") or j.get("date_updated") or j.get("date_found") or "")[:10],
            ])

        # Write to sheet (clear first, then write)
        range_str = f"'{tab_name}'!A1:H{len(rows)}"
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
    sa_json: str | None = None,
) -> list[dict]:
    """Read tracked jobs from a Google Sheet.

    Expects matching columns: Score, Title, Company, Location, URL, Company Link, Status, Date Found
    """
    sheet_id = parse_sheet_url(sheet_url)
    if not sheet_id:
        return []

    try:
        service = _get_gsheet_service(sa_json)
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        existing_tabs = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

        target_tab = "Job Tracker"
        if "All Jobs" in existing_tabs:
            target_tab = "All Jobs"
        elif "Job Tracker" in existing_tabs:
            target_tab = "Job Tracker"
        elif existing_tabs:
            target_tab = existing_tabs[0]

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{target_tab}'!A:H",
        ).execute()

        values = result.get("values", [])
        if len(values) < 2:
            return []

        jobs = []
        for row in values[1:]:
            # Ensure the row is padded to at least 8 elements to prevent any IndexError
            row = list(row) + [""] * (8 - len(row))
            
            title = row[1].strip()
            company = row[2].strip()
            if not title or not company:
                continue

            try:
                score_val = int(float(str(row[0]).strip())) if row[0] else 0
            except ValueError:
                score_val = 0

            jobs.append({
                "score": score_val,
                "title": title,
                "company": company,
                "location": row[3].strip(),
                "url": row[4].strip(),
                "company_link": row[5].strip(),
                "status": row[6].strip().lower() or "new",
                "date_updated": row[7].strip(),
            })
        return jobs
    except Exception as e:
        logger.error(f"Failed to read from sheet: {e}")
        return []
