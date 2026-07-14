"""Sync tracked jobs to user's Google Sheet."""
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("jobpilot.gsheet")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_gsheet_service(sa_json: str | None = None):
    """Get a Google Sheets service instance.

    Uses user-provided service account JSON, or falls back to gsheet_service_account.json.
    """
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    if sa_json:
        creds = Credentials.from_service_account_info(json.loads(sa_json), scopes=SCOPES)
    else:
        sa_path = os.environ.get("GSHEET_SERVICE_ACCOUNT") or "gsheet_service_account.json"
        if not os.path.exists(sa_path):
            raise FileNotFoundError(f"Service account file not found: {sa_path}")
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

    Creates a 'Job Tracker' tab with columns:
    Title, Company, Location, Score, Status, URL, Notes, Last Updated
    """
    sheet_id = parse_sheet_url(sheet_url)
    if not sheet_id:
        logger.error(f"Invalid sheet URL: {sheet_url}")
        return False

    try:
        service = _get_gsheet_service(sa_json)
        sheets_api = service.spreadsheets()

        # Ensure "Job Tracker" tab exists
        spreadsheet = sheets_api.get(spreadsheetId=sheet_id).execute()
        tab_name = "Job Tracker"
        existing_tabs = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

        if tab_name not in existing_tabs:
            sheets_api.batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
            ).execute()

        # Build rows
        headers = ["Title", "Company", "Location", "Score", "Status", "URL", "Notes", "Last Updated"]
        rows = [headers]
        for j in jobs:
            rows.append([
                j.get("title", ""),
                j.get("company", ""),
                j.get("location", ""),
                str(j.get("score", 0)),
                j.get("status", "new"),
                j.get("url", ""),
                j.get("notes", ""),
                j.get("updated_at", "") or j.get("date_updated", ""),
            ])

        # Write to sheet (clear first, then write)
        range_str = f"{tab_name}!A1:H{len(rows)}"
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

    Expects: Title, Company, Location, Score, Status, URL, Notes, Last Updated
    """
    sheet_id = parse_sheet_url(sheet_url)
    if not sheet_id:
        return []

    try:
        service = _get_gsheet_service(sa_json)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Job Tracker!A:H",
        ).execute()

        values = result.get("values", [])
        if len(values) < 2:
            return []

        headers = values[0]
        jobs = []
        for row in values[1:]:
            if len(row) < 2:
                continue
            jobs.append({
                "title": row[0] if len(row) > 0 else "",
                "company": row[1] if len(row) > 1 else "",
                "location": row[2] if len(row) > 2 else "",
                "score": int(row[3]) if len(row) > 3 and row[3].isdigit() else 0,
                "status": row[4] if len(row) > 4 else "new",
                "url": row[5] if len(row) > 5 else "",
                "notes": row[6] if len(row) > 6 else "",
                "date_updated": row[7] if len(row) > 7 else "",
            })
        return jobs
    except Exception as e:
        logger.error(f"Failed to read from sheet: {e}")
        return []
