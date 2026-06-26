"""Daily email scan: check Interview label for applied/rejected/offer, sync to sheet."""
import imaplib, email, json, re, sys
from datetime import datetime, timedelta

GMAIL_USER = "kamneemaran45@gmail.com"
GMAIL_PASS = "bttjcludverlbmnr"
TRACKER_FILE = "job_tracker.json"
STATE_FILE = "last_email_scan.json"
GSHEET_ID = "1NO-erkRi_aV7RSY8dMbZkxEZBA9jEN55IfIrK3S8WEg"
LABELS = ["Interview"]

KNOWN_COMPANIES = [
    "coinbase", "databricks", "datadog", "elastic", "airbnb", "stripe",
    "google", "microsoft", "amazon", "meta", "apple", "netflix", "spotify",
    "linkedin", "twitter", "uber", "lyft", "pinterest", "reddit", "dropbox",
    "gitlab", "vercel", "webflow", "upwork", "instacart", "discord", "monzo",
    "adyen", "anthropic", "atlassian", "intuit", "wise", "postman",
    "nutanix", "browserstack", "confluent", "snowflake", "canva", "mollie",
    "n26", "bol", "join", "algolia", "bloomreach", "tide", "zscaler", "stream",
    "olo", "signifyd", "workable", "grafana", "canonical", "freetrade",
    "optiver", "coolblue", "kaufland", "airwallex", "headout", "about you",
    "agoda", "re-leased", "privy", "salento", "justeat", "bonial",
]

def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def job_key(title, company):
    return f"{company.lower()}|{title.lower()}"

def extract_company(full_text, tracker_companies):
    """Find which company appears in the email text — check tracker companies first."""
    full_lower = full_text.lower()
    # Check known companies that are in the tracker first
    for c in tracker_companies:
        cl = c.lower()
        if cl in full_lower and len(cl) > 2:
            return c
    # Then check broader known companies
    for c in KNOWN_COMPANIES:
        if c in full_lower and len(c) > 2:
            return c.title() if c.islower() else c
    # Try domain-based extraction as fallback
    m = re.search(r'@([a-zA-Z0-9-]+)\.(com|io|ai|co|de|nl|uk)', full_text[:500])
    if m:
        domain = m.group(1).lower()
        if domain not in ("gmail", "outlook", "yahoo", "hotmail", "icloud", "protonmail"):
            return domain.title()
    return None

def main():
    full_scan = "--full" in sys.argv

    tracker = load_json(TRACKER_FILE, {"jobs": {}})
    state = load_json(STATE_FILE, {"last_scan": None})

    days = 90 if (full_scan or state.get("last_scan") is None) else max(1, (datetime.now() - datetime.fromisoformat(state["last_scan"])).days + 2)
    print(f"=== {'Full' if days >= 90 else 'Incremental'} scan of Interview label ===", flush=True)

    mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    mail.login(GMAIL_USER, GMAIL_PASS)

    results = []
    for label in LABELS:
        try:
            mail.select(label)
        except:
            print(f"  [!] Cannot select '{label}'", flush=True)
            continue
        since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        r, d = mail.search(None, f"(SINCE {since})")
        if r != "OK":
            continue
        emails = d[0].split()
        print(f"  [{label}] {len(emails)} emails", flush=True)
        for num in emails:
            try:
                r2, md = mail.fetch(num, "(RFC822)")
                if r2 != "OK":
                    continue
                msg = email.message_from_bytes(md[0][1])
                subject = msg["subject"] or ""
                sender = msg["from"] or ""
                date = msg["date"] or ""
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = (part.get_payload(decode=True) or b"").decode("utf-8", errors="ignore")
                            break
                else:
                    body = (msg.get_payload(decode=True) or b"").decode("utf-8", errors="ignore")
                results.append((subject, sender, body, date))
            except:
                continue

    mail.logout()
    print(f"  Processing {len(results)} emails...", flush=True)

    # Build list of tracker company names
    tracker_companies = sorted(set(e.get("company", "") for e in tracker["jobs"].values()))

    updated_companies = {}  # company -> status
    for subject, sender, body, date in results:
        full = f"{subject} {sender} {body}".lower()

        if any(kw in full for kw in ["offer", "offer letter", "congratulations", "we are pleased to inform"]):
            status = "offer"
        elif any(kw in full for kw in ["unfortunately", "not moving forward", "regret to inform",
                                        "not selected", "position has been filled",
                                        "update about your application", "status of your application",
                                        "application status", "update on your application"]):
            status = "rejected"
        elif any(kw in full for kw in ["application received", "thank you for applying",
                                        "received your application", "we have received",
                                        "application submitted", "application confirmation",
                                        "thank you for your interest", "your application has been received"]):
            status = "applied"
        else:
            continue

        company = extract_company(full, tracker_companies)
        if company:
            updated_companies[company] = status

    if not updated_companies:
        print("  No companies detected in emails.", flush=True)
    else:
        print(f"  Detected: {updated_companies}", flush=True)

    # Update tracker for matching companies (case-insensitive)
    now = datetime.now().isoformat()
    updated_count = 0
    tracker_company_set = set(c.lower() for c in tracker_companies)
    for entry_key, entry in list(tracker["jobs"].items()):
        c = entry.get("company", "")
        cl = c.lower()
        # Find matching status from updated_companies
        new_status = None
        for uc, us in updated_companies.items():
            if uc.lower() == cl:
                new_status = us
                break
        if not new_status:
            continue

        old_status = entry.get("status", "new")
        if new_status == "applied" and old_status in ("applied", "rejected", "offer"):
            continue
        if new_status == "rejected" and old_status == "rejected":
            continue
        if new_status == "offer" and old_status == "offer":
            continue

        entry["status"] = new_status
        entry["date_updated"] = now
        if new_status == "applied" and "date_applied" not in entry:
            entry["date_applied"] = now
        elif new_status == "rejected":
            entry["date_rejected"] = now
        elif new_status == "offer":
            entry["date_offer"] = now
        entry["notes"] = f"Email scan: {new_status}"
        updated_count += 1

    print(f"  Updated {updated_count} tracker entries", flush=True)

    # Add placeholder entries for companies not in tracker so they appear in sheet
    added = 0
    for c, status in updated_companies.items():
        if c.lower() in tracker_company_set:
            continue
        key = job_key("Unknown Role", c)
        if key in tracker["jobs"]:
            continue
        now = datetime.now().isoformat()
        tracker["jobs"][key] = {
            "title": "Unknown Role",
            "company": c,
            "url": "",
            "score": "",
            "status": status,
            "resume": "",
            "date_found": now,
            "date_updated": now,
        }
        if status == "applied":
            tracker["jobs"][key]["date_applied"] = now
        elif status == "rejected":
            tracker["jobs"][key]["date_rejected"] = now
        elif status == "offer":
            tracker["jobs"][key]["date_offer"] = now
        tracker["jobs"][key]["notes"] = f"Email scan: {status}"
        added += 1

    if added:
        print(f"  Added {added} placeholder entries for untracked companies", flush=True)
        # Recompute tracker company set for the "not in tracker" check below
        tracker_companies = sorted(set(e.get("company", "") for e in tracker["jobs"].values()))
        tracker_company_set = set(c.lower() for c in tracker_companies)

    for c in updated_companies:
        if c.lower() not in tracker_company_set:
            print(f"  [!] '{c}' ({updated_companies[c]}) — not in tracker", flush=True)

    save_json(TRACKER_FILE, tracker)
    state["last_scan"] = datetime.now().isoformat()
    save_json(STATE_FILE, state)

    # Sync to sheet
    print("  Syncing to Google Sheet...", flush=True)
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            "gsheet_service_account.json",
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        try:
            existing = sheet.values().get(spreadsheetId=GSHEET_ID, range="'job_matches'!A:L").execute()
            existing_rows = existing.get("values", [])
            existing_keys = set()
            for row in existing_rows[1:]:
                if len(row) >= 3:
                    existing_keys.add((row[2].strip().lower(), row[1].strip().lower()))
        except:
            existing_rows = []
            existing_keys = set()

        header = ["Score", "Title", "Company", "Location", "URL", "Company Link",
                   "Status", "Date Found", "Applied Date", "Rejection Date", "Offer Date", "Notes"]
        new_rows = []
        seen = set()
        for entry in tracker["jobs"].values():
            s = entry.get("status", "new")
            if s not in ("applied", "rejected", "offer"):
                continue
            dedup = (entry["company"].lower(), entry.get("title", "").lower())
            if dedup in seen or dedup in existing_keys:
                continue
            seen.add(dedup)
            new_rows.append([
                entry.get("score", ""),
                entry.get("title", ""),
                entry.get("company", ""),
                "",
                entry.get("url", ""),
                "",
                s,
                (entry.get("date_found") or "")[:10],
                (entry.get("date_applied") or "")[:10],
                (entry.get("date_rejected") or "")[:10],
                (entry.get("date_offer") or "")[:10],
                (entry.get("notes") or "")[:80],
            ])

        if not existing_rows:
            sheet.values().update(
                spreadsheetId=GSHEET_ID, range="'job_matches'!A1",
                valueInputOption="RAW", body={"values": [header]}
            ).execute()

        if new_rows:
            sheet.values().append(
                spreadsheetId=GSHEET_ID, range="'job_matches'!A:L",
                valueInputOption="RAW", body={"values": new_rows}
            ).execute()
            print(f"  [gsheet] Added {len(new_rows)} rows", flush=True)
        else:
            print(f"  [gsheet] No new rows", flush=True)
    except Exception as e:
        print(f"  [gsheet] Error: {e}", flush=True)

    print("=== Done ===", flush=True)

if __name__ == "__main__":
    main()
