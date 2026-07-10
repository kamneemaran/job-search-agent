"""Daily email scan: check Interview label for applied/rejected/offer, sync to sheet."""
import imaplib, email, json, re, sys, os
from datetime import datetime, timedelta

GMAIL_USER = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")
GSHEET_ID = os.environ.get("GSHEET_ID", "1NO-erkRi_aV7RSY8dMbZkxEZBA9jEN55IfIrK3S8WEg")
profile_slug = os.environ.get("PROFILE", "kamnee").replace(" ", "_").lower()
TRACKER_FILE = os.environ.get("TRACKER_FILE", f"job_tracker_{profile_slug}.json")
STATE_FILE = os.environ.get("STATE_FILE", f"last_email_scan_{profile_slug}.json")
LABELS = [os.environ.get("GMAIL_LABEL", "Interview")]

KNOWN_COMPANIES = [
    # Major tech
    "google", "microsoft", "amazon", "meta", "apple", "netflix", "spotify",
    "coinbase", "databricks", "datadog", "elastic", "airbnb", "stripe",
    "linkedin", "twitter", "uber", "lyft", "pinterest", "reddit", "dropbox",
    "gitlab", "vercel", "webflow", "upwork", "instacart", "discord",
    "adyen", "anthropic", "atlassian", "intuit", "postman",
    "nutanix", "browserstack", "confluent", "snowflake", "canva",
    # Consulting / enterprise
    "deloitte", "ey", "atos", "ibm", "accenture", "capgemini", "infosys",
    "tcs", "wipro", "cognizant", "genpact",
    # SAP / ERP domain
    "sap", "norsk hydro", "hydro", "avery dennison", "austro control",
    # Other
    "algolia", "bloomreach", "zscaler",
    "signifyd", "workable", "grafana", "canonical", "freetrade",
    "optiver", "coolblue", "kaufland", "airwallex", "headout",
    "agoda", "re-leased", "privy", "justeat", "bonial",
    "gea", "adams",
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

def _parse_display_name(sender):
    """Extract the display name from a From header, e.g. 'Deloitte Netherlands <x@y.com>' -> 'deloitte netherlands'."""
    m = re.match(r'^"?([^"<]*?)"?\s*<', sender)
    if m:
        return m.group(1).strip().lower()
    return sender.split("@")[0].replace(".", " ").strip().lower() if "@" in sender else sender.lower()

def _extract_from_subject(subject, tracker_companies):
    """Try to find company in subject line — e.g. 'at Deloitte', 'Deloitte -', 'Deloitte Netherlands'."""
    s_lower = subject.lower()
    # "at CompanyName" pattern
    m = re.search(r'\bat\s+([a-zA-Z0-9\s&]+?)(?:\s*[–—-]|\s*$|\(|\))', s_lower)
    if m:
        candidate = m.group(1).strip()
        if len(candidate) > 2:
            return candidate.title()
    # "CompanyName -" or "CompanyName |" pattern  
    m = re.search(r'^([a-zA-Z0-9\s&]+?)\s*[–—\-|]', s_lower)
    if m:
        candidate = m.group(1).strip()
        if len(candidate) > 2:
            return candidate.title()
    return None

def _clean_display(raw):
    """Remove common qualifiers from a sender display name."""
    name = raw.lower()
    for q in ["recruiting", "recruitment", "talent acquisition", "talent",
              "noreply", "careers", "notification", "hiring", "nl"]:
        name = name.replace(q, "").strip()
    return name.strip(" ,-–—|")

def extract_company(subject, sender, full_text, tracker_companies):
    """Find which company appears in the email text.
    
    Priority:
      1. Sender display name (e.g. 'Deloitte Netherlands <x@y.com>' -> 'Deloitte')
      2. Subject line (e.g. 'at Deloitte', 'Deloitte -')
      3. KNOWN_COMPANIES (min 4 chars)
      4. Tracker companies
      5. Domain extraction (@company.com -> Company)
    """
    full_lower = full_text.lower()

    # 1. Sender display name
    # Parse: "Display Name <email>" or "<email>" or just "email"
    sm = re.match(r'^"?([^"<]*?)"?\s*<[^>]+@[^>]+>', sender)
    if sm:
        display = _clean_display(sm.group(1))
    elif "@" in sender:
        display = _clean_display(sender.split("@")[0].replace(".", " "))
    else:
        display = _clean_display(sender)
    
    if display:
        display_words = display.split()
        # Check known companies first (word-boundary match in display name)
        for c in KNOWN_COMPANIES:
            if len(c) >= 4:
                if c in display:
                    return c.title() if c.islower() else c
            elif len(c) >= 2:
                # 2-3 char names: exact word match to avoid substring false positives
                if re.search(rf'\b{re.escape(c)}\b', display):
                    return c.title() if c.islower() else c
        # Filter out common person first names and generic roles
        _common_names = {"kalimi", "mohini", "agnes", "monika", "csorba",
                         "pradeep", "kamnee", "maran", "john", "jane",
                         "michael", "david", "sarah", "lisa", "thomas"}
        significant = [w for w in display_words if len(w) >= 4
                       and w not in _common_names
                       and w not in ("human", "resources", "department",
                                     "information", "technology")]
        if significant:
            return max(significant, key=len).title()
        # All display words are known names — fall through to subject/domain
        if not all(w in _common_names or len(w) < 4 for w in display_words):
            # Some non-name word exists (like "ey"), use the longest
            longest = max(display_words, key=len)
            if len(longest) >= 2:
                return longest.title()

    # 2. Subject line — check known companies (word-boundary)
    s_lower = subject.lower()
    for c in KNOWN_COMPANIES:
        if len(c) >= 2 and re.search(rf'\b{re.escape(c)}\b', s_lower):
            return c.title() if c.islower() else c
    # "Thank you for applying to EY" -> skip "thank you for applying" etc
    # Match: "at Deloitte", "with Deloitte", "bei Austro Control"
    m = re.search(r'\b(?:at|with|bei)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)', subject)
    if m:
        return m.group(1).strip()

    # 3. KNOWN_COMPANIES in subject+sender (first 300 chars to avoid footer false matches)
    for c in KNOWN_COMPANIES:
        if len(c) >= 4 and re.search(rf'\b{re.escape(c)}\b', full_lower[:300]):
            return c.title() if c.islower() else c

    # 4. Tracker companies
    for c in tracker_companies:
        cl = c.lower()
        if cl in full_lower and len(cl) > 2:
            return c

    # 5. Domain extraction (@company.com -> Company)
    m = re.search(r'@([a-zA-Z0-9-]+)\.(com|io|ai|co|de|nl|uk)', full_text[:500])
    if m:
        domain = m.group(1).lower()
        if domain not in ("gmail", "outlook", "yahoo", "hotmail", "icloud", "protonmail"):
            return domain.title() if domain.islower() else domain
    return None

def main():
    full_scan = "--full" in sys.argv

    tracker = load_json(TRACKER_FILE, {"jobs": {}})
    state = load_json(STATE_FILE, {"last_scan": None})

    days = 90 if (full_scan or state.get("last_scan") is None) else max(1, (datetime.now() - datetime.fromisoformat(state["last_scan"])).days + 2)
    print(f"=== {'Full' if days >= 90 else 'Incremental'} scan of {LABELS} label(s) ===", flush=True)

    mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    mail.login(GMAIL_USER, GMAIL_PASS)

    results = []
    for label in LABELS:
        try:
            # Quote if containing spaces to satisfy IMAP parser
            imap_label = f'"{label}"' if " " in label else label
            mail.select(imap_label)
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

        # Determine status — check NEW email only (body without quoted reply)
        body_clean = body.split("-----Original Message-----")[0]
        body_clean = body_clean.split("From:")[0]
        body_clean = body_clean.split("Sent:")[0]
        body_clean = body_clean.split("________________________________")[0]
        full_clean = f"{subject} {sender} {body_clean}".lower()

        if any(kw in full_clean for kw in ["offer letter", "congratulations", "we are pleased to inform"]):
            status = "offer"
        elif any(kw in full_clean for kw in ["not moving forward", "regret to inform",
                                              "not selected", "position has been filled"]):
            status = "rejected"
        elif any(kw in full_clean for kw in ["application received", "thank you for applying",
                                              "thank you for your application",
                                              "received your application", "we have received",
                                              "application submitted", "application confirmation",
                                              "thank you for your interest", "your application has been received",
                                              "thank you for submitting", "your application for"]):
            status = "applied"
        else:
            continue

        company = extract_company(subject, sender, full, tracker_companies)
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
