"""Daily email scan: check Interview label for applied/rejected/offer, sync to sheet."""
import imaplib, email, json, re, sys, os
from datetime import datetime, timedelta

def _normalize_pw(pw: str) -> str:
    return pw.replace("\xa0", " ").replace("\u2009", " ").strip() if pw else pw


GMAIL_USER = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_PASS = _normalize_pw(os.environ.get("GMAIL_APP_PASSWORD", ""))
GSHEET_ID = os.environ.get("GSHEET_ID")
profile_slug = os.environ.get("PROFILE", "kamnee").replace(" ", "_").lower()
TRACKER_FILE = os.environ.get("TRACKER_FILE", f"job_tracker_{profile_slug}.json")
STATE_FILE = os.environ.get("STATE_FILE", f"last_email_scan_{profile_slug}.json")
LABELS = [os.environ.get("GMAIL_LABEL")] if os.environ.get("GMAIL_LABEL") else []

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
    """Extract the display name from a From header."""
    m = re.match(r'^"?([^"<]*?)"?\s*<', sender)
    if m:
        return m.group(1).strip().lower()
    return sender.split("@")[0].replace(".", " ").strip().lower() if "@" in sender else sender.lower()

def _split_subject(subject):
    """Clean and normalize subject line."""
    s = subject.replace("=?UTF-8?Q?", "").replace("?=", "")
    s = re.sub(r'\s+', ' ', s).strip()
    return s

_ROLE_KEYWORDS = [
    "engineer", "developer", "architect", "manager", "consultant",
    "specialist", "analyst", "designer", "director", "lead",
    "staff", "principal", "senior", "intern", "sde", "backend",
    "frontend", "full stack", "data", "software", "platform",
    "infrastructure", "sap", "ewm", "mm", "devops", "sre",
    "product", "program", "project", "technical", "solution",
]

def find_clean_sap_role(text):
    text_lower = text.lower()
    clean_phrases = [
        "sap mm functional consultant", "sap ewm functional consultant",
        "sap mm consultant", "sap ewm consultant", "sap wm consultant",
        "sap mm/wm consultant", "sap mm/ewm consultant", "sap logistics consultant",
        "sap supply chain consultant", "sap sourcing & procurement consultant",
        "sap sourcing and procurement consultant", "sap support analyst",
        "sap functional lead", "sap functional consultant", "sap consultant"
    ]
    for phrase in clean_phrases:
        if phrase in text_lower:
            return phrase.title()
    return None


def extract_location(subject, body):
    text = (subject + " " + body).lower()
    location_map = {
        "melbourne": "Melbourne, Australia",
        "brisbane": "Brisbane, Australia",
        "sydney": "Sydney, Australia",
        "auckland": "Auckland, New Zealand",
        "wellington": "Wellington, New Zealand",
        "mülheim": "Mülheim, Germany",
        "erlangen": "Erlangen, Germany",
        "düsseldorf": "Düsseldorf, Germany",
        "ichtershausen": "Ichtershausen, Germany",
        "frankfurt": "Frankfurt, Germany",
        "munich": "Munich, Germany",
        "münchen": "Munich, Germany",
        "starnberg": "Starnberg, Germany",
        "hannover": "Hannover, Germany",
        "augsburg": "Augsburg, Germany",
        "olpe": "Olpe, Germany",
        "kronberg": "Kronberg, Germany",
        "berlin": "Berlin, Germany",
        "den bosch": "Den Bosch, Netherlands",
        "eindhoven": "Eindhoven, Netherlands",
        "delft": "Delft, Netherlands",
        "amsterdam": "Amsterdam, Netherlands",
        "warsaw": "Warsaw, Poland",
        "stockholm": "Stockholm, Sweden",
        "malmö": "Malmö, Sweden",
        "pune": "Pune, India",
        "bengaluru": "Bengaluru, India",
        "bangalore": "Bengaluru, India",
        "hyderabad": "Hyderabad, India",
        "chennai": "Chennai, India",
        "mumbai": "Mumbai, India",
        "gurugram": "Gurugram, India",
        "gurgaon": "Gurugram, India",
    }
    for city, formatted in location_map.items():
        if city in text:
            return formatted
    country_map = {
        "australia": "Australia",
        "new zealand": "New Zealand",
        "germany": "Germany",
        "netherlands": "Netherlands",
        "poland": "Poland",
        "sweden": "Sweden",
        "switzerland": "Switzerland",
        "india": "India",
    }
    for country, formatted in country_map.items():
        if country in text:
            return formatted
    return ""


def extract_role(subject, body):
    """Extract job title/role from email subject or body.
    
    Priority:
      0. High-precision SAP role phrase matching
      1. Subject patterns: 'Application for Role', 'Your application for Role'
      2. Subject patterns: 'Role at Company', 'Role - Company'
      3. Company-reply patterns: 'Re: Role at Company'
      4. Known role keywords in subject
    """
    clean_sap = find_clean_sap_role(subject + " " + body)
    if clean_sap:
        return clean_sap

    s = _split_subject(subject)
    s_lower = s.lower()
    body_lower = body.lower()

    # Skip auto-reply subjects
    if s_lower.startswith("re:") or s_lower.startswith("fw:") or s_lower.startswith("fwd:"):
        s_lower = re.sub(r'^(re|fw|fwd)\s*:\s*', '', s_lower).strip()
        # Also try to extract role from forwarded subject
        if "application for" in s_lower:
            m = re.search(r'application for\s+([^,;]+)', s_lower)
            if m: return m.group(1).strip().title()

    # "Application for [Role] at [Company]"
    m = re.search(r'(?:your\s+)?application\s+(?:for|regarding|re)\s+(.+?)(?:\s+at\s+|\s*[–—\-|]\s*|$)', s_lower)
    if m:
        role = m.group(1).strip().rstrip(".,;")
        if len(role) > 3:
            return role.title()

    # "Your application to [Company] for [Role]"
    m = re.search(r'your\s+application\s+to\s+\S+\s+for\s+(.+)', s_lower)
    if m:
        role = m.group(1).strip().rstrip(".,;")
        if len(role) > 3:
            return role.title()

    # "Thank you for applying to [Role] at [Company]"
    m = re.search(r'thank\s+you\s+for\s+(?:your\s+)?applying\s+(?:to|for)\s+(.+?)(?:\s+at\s+|\s*[–—\-|]\s*|$)', s_lower)
    if m:
        role = m.group(1).strip().rstrip(".,;")
        if role.startswith("the ") and any(kw in role for kw in _ROLE_KEYWORDS):
            role = re.sub(r'^the\s+', '', role)
        if len(role) > 3:
            return role.title()

    # "Your application for [Role] has been received" / "Thanks for applying for the [Role] role"
    m = re.search(r'(?:thank|thanks)\s+(?:you\s+)?for\s+(?:applying\s+(?:for|to)\s+)?(?:the\s+)?(.+?)(?:\s+role\s+|\s+position\s+|\s+at\s+|\s*[–—\-|]\s*|\s+has\s+|\s+is\s+|\s+and\s+will\s+|$)', s_lower)
    if m:
        role = m.group(1).strip().rstrip(".,;")
        if any(kw in role for kw in _ROLE_KEYWORDS) and len(role) > 3:
            return role.title()

    # "Your application for [Role] has been received"
    m = re.search(r'(?:your\s+)?application\s+for\s+(.+?)\s+(?:has\s+been|is\s+received|at\s+)', s_lower)
    if m:
        role = m.group(1).strip().rstrip(".,;")
        if len(role) > 3:
            return role.title()

    # "[Role] at [Company]" or "[Role] - [Company]" in subject
    m = re.search(r'(.+?)\s+(?:at|with|bei|–|—|-|\|)\s+.+', s_lower)
    if m:
        candidate = m.group(1).strip().rstrip(".,;")
        if any(kw in candidate for kw in _ROLE_KEYWORDS) and len(candidate) > 5:
            return candidate.title()

    # "Application received - [Role]" or "[Role] - Application Received"
    m = re.search(r'application\s+(?:received|submitted|confirmation)\s*[-–—|]\s*(.+)|(.+)\s*[-–—|]\s*application\s+(?:received|submitted|confirmation)', s_lower)
    if m:
        role = m.group(1) or m.group(2)
        if role and len(role.strip()) > 3:
            return role.strip().title()

    # Skip subjects that are just a company name (e.g. "Twilio!", "Databricks", "Agoda", "Servicenow!")
    s_no_punct = re.sub(r'[!.\s]', '', s_lower)
    if len(s_no_punct) < 20 and not any(kw in s_lower for kw in _ROLE_KEYWORDS):
        return None

    # Fallback: pick the longest phrase containing a role keyword
    parts = re.split(r'\s*[–—\-|]\s*', s_lower)
    best = None
    for part in parts:
        if any(kw in part for kw in _ROLE_KEYWORDS) and len(part) > 5:
            if not best or len(part) > len(best):
                best = part
    if best:
        return best.strip().title()

    # Last resort: check body for "applying for [Role]"
    m = re.search(r'(?:applying\s+for|applied\s+for|application\s+for)\s+(.+?)(?:\s+at\s+|\s*[–—\-|]\s*|\s*\.\s*|$)', body_lower[:500])
    if m:
        role = m.group(1).strip().rstrip(".,;")
        if len(role) > 3:
            return role.title()

    return None


def _clean_role(role):
    """Clean up a raw extracted role string."""
    if not role:
        return None
    # Strip common suffixes
    role = re.sub(r'\s+(role|position|opening)!?\s*$', '', role, flags=re.IGNORECASE)
    role = re.sub(r'^the\s+', '', role, flags=re.IGNORECASE)
    # Trim trailing junk after a natural stopping point
    role = re.sub(r'(Soon And Will Get In Touch.*|Our Recruiting Team.*|We Thank You.*|Thank You For.*|A New Job, So.*)$', '', role, flags=re.IGNORECASE)
    # Strip "Thanks For Applying For The" prefix
    role = re.sub(r'^thanks?\s+(you\s+)?for\s+(your\s+)?applying\s+(for|to)\s+(the\s+)?', '', role, flags=re.IGNORECASE)
    role = role.strip()
    # Reject if it's just a company name or too short
    if len(role) < 5:
        return None
    if role.endswith("!") and len(role) < 20:
        return None
    return role


def _clean_display(raw):
    """Remove common qualifiers from a sender display name."""
    name = raw.lower()
    for q in ["recruiting", "recruitment", "talent acquisition", "talent",
              "noreply", "no-reply", "do-not-reply", "donotreply",
              "careers", "notification", "hiring", "nl", "jobs",
              "career", "team", "hr"]:
        name = name.replace(q, "").strip()
    return name.strip(" ,-–—|")

def extract_company(subject, sender, full_text, tracker_companies):
    """Find which company appears in the email text.
    
    Priority:
      1. Non-ATS, non-public sender email domain (e.g. recruit@asml.com -> ASML)
      2. Cleaned sender display name (e.g. "Capgemini Careers" -> Capgemini)
      3. Subject line patterns: 'at Company', 'with Company', 'bei Company'
      4. Known companies in subject (word-boundary)
      5. Known companies in body (first 300 chars)
      6. Tracker companies
    """
    email_addr = ""
    display_name = ""
    
    m_email = re.search(r'<([^>]+)>', sender)
    if m_email:
        email_addr = m_email.group(1).strip().lower()
        display_name = sender.split("<")[0].strip().replace('"', '')
    else:
        if "@" in sender:
            email_addr = sender.strip().lower()
        else:
            display_name = sender.strip().replace('"', '')
            
    domain = ""
    if email_addr and "@" in email_addr:
        domain_part = email_addr.split("@")[-1].lower()
        domain = domain_part.split(".")[0]
        
    _ats_domains = {
        "smartrecruiters", "ashbyhq", "greenhouse", "lever", "bamboohr",
        "workable", "icims", "jobvite", "recruitee", "comeet",
        "personio", "breezy", "teamtailor", "pinpoint", "myworkday",
        "workday", "jobvite"
    }
    _public_domains = {
        "gmail", "outlook", "yahoo", "hotmail", "icloud", "protonmail", 
        "mail", "zoho", "yandex", "gmx", "aol"
    }
    
    # 1. Non-ATS, non-public sender email domain
    if domain and domain not in _ats_domains and domain not in _public_domains:
        for c in KNOWN_COMPANIES + tracker_companies:
            if c.lower() == domain:
                return c
        return domain.title()
        
    # 2. Cleaned sender display name
    if display_name:
        clean_display = _clean_display(display_name)
        if clean_display:
            _common_names = {
                "kalimi", "mohini", "agnes", "monika", "csorba", "pradeep", "kamnee", 
                "maran", "john", "jane", "michael", "david", "sarah", "lisa", "thomas",
                "georgiana", "alina", "luncanu", "denz", "welcome", "noreply", "no-reply", "donotreply"
            }
            words = clean_display.lower().split()
            if not any(w in _common_names for w in words):
                significant_words = [w for w in words if len(w) >= 3 and w not in (
                    "human", "resources", "department", "nl", "information", "technology", "careers", "career", "jobs"
                )]
                if significant_words:
                    for c in KNOWN_COMPANIES + tracker_companies:
                        if c.lower() == clean_display.lower():
                            return c
                    return clean_display.title()

    # 3. Subject patterns: "at Company", "with Company", "bei Company"
    m_subject = re.search(r'\b(?:at|with|bei)\s+([A-Z][a-zA-Z0-9_-]+(?:\s[A-Z][a-zA-Z0-9_-]+)?)', subject)
    if m_subject:
        comp_candidate = m_subject.group(1).strip()
        _not_companies = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "john", "jane", "you"}
        if comp_candidate.lower() not in _not_companies:
            return comp_candidate

    # 4. Known companies in subject (word-boundary)
    s_lower = subject.lower()
    for c in KNOWN_COMPANIES:
        if len(c) >= 2 and re.search(rf'\b{re.escape(c)}\b', s_lower):
            return c.title() if c.islower() else c
            
    # 5. Tracker companies in subject
    for c in tracker_companies:
        if c.lower() in s_lower:
            return c
            
    # 6. Known companies in body (first 300 chars)
    full_lower = full_text.lower()
    for c in KNOWN_COMPANIES:
        if len(c) >= 4 and re.search(rf'\b{re.escape(c)}\b', full_lower[:300]):
            return c.title() if c.islower() else c

    return None

def _resolve_gsheet_id(supabase_user_email: str = "") -> str:
    """Get the user's tracker sheet ID from the DB, falling back to env."""
    if supabase_user_email:
        supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if supabase_url and supabase_key:
            try:
                from supabase import create_client
                sb = create_client(supabase_url, supabase_key)
                user_res = sb.table("profiles").select("id, tracker_sheet_url").eq("email", supabase_user_email).execute()
                if user_res.data and user_res.data[0].get("tracker_sheet_url"):
                    import re
                    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", user_res.data[0]["tracker_sheet_url"])
                    if m:
                        return m.group(1)
            except Exception as e:
                print(f"  [gsheet] Failed to resolve sheet from DB: {e}", flush=True)
    return os.environ.get("GSHEET_ID", "")


def main(label: str = "", supabase_user_email: str = "", last_scan_override: str = ""):
    full_scan = "--full" in sys.argv

    active_labels = [label] if label else LABELS

    tracker = load_json(TRACKER_FILE, {"jobs": {}})
    state = load_json(STATE_FILE, {"last_scan": None, "last_scan_by_label": {}})

    target_label = active_labels[0] if active_labels else "Job Tracker"
    last_scan_by_label = state.get("last_scan_by_label") or {}
    
    # Check last scan for this specific label
    last_scan_date = last_scan_by_label.get(target_label)
    
    # If a new label is being scanned, or last_scan_date is None, force a full scan
    if last_scan_date is None:
        last_scan_override = "" # Ignore global override to force a full scan on new label!

    # last_scan_override lets the dashboard pass the user's last scan date from
    # Supabase (persisted per-user) so incremental scans only check emails after
    # that date, even though the local STATE_FILE may not exist on the server.
    if last_scan_override and not full_scan:
        last_scan_date = last_scan_override
    elif not last_scan_date and state.get("last_scan"):
        # Fallback to general last scan if this is not a new custom label
        last_scan_date = state.get("last_scan")

    days = 90 if (full_scan or last_scan_date is None) else max(1, (datetime.now() - datetime.fromisoformat(last_scan_date)).days + 2)
    print(f"=== {'Full' if days >= 90 else 'Incremental'} scan of {active_labels} label(s) ===", flush=True)

    if not active_labels:
        print("  [!] No GMAIL_LABEL set — skipping label scan", flush=True)
        print("=== Done ===", flush=True)
        return

    if not GMAIL_USER or not GMAIL_PASS:
        print("  [!] No GMAIL_ADDRESS/GMAIL_APP_PASSWORD set — skipping email scan", flush=True)
        print("=== Done ===", flush=True)
        return

    # Normalize the password right before use, in case it was passed un-normalized from another file
    normalized_pass = _normalize_pw(GMAIL_PASS)

    print(f"  [*] Attempting Gmail login for {GMAIL_USER} (Password length: {len(normalized_pass) if normalized_pass else 0})", flush=True)
    if normalized_pass.startswith("enc:"):
        print("  [!] Gmail login failed: The App Password is encrypted but decryption failed.", flush=True)
        print("      Please make sure APP_PASSWORD_ENCRYPTION_KEY is set in your environment with the correct secret, or re-save your Gmail App Password in your settings.", flush=True)
        print("=== Done ===", flush=True)
        return

    mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    try:
        mail.login(GMAIL_USER, normalized_pass)
    except imaplib.IMAP4.error as e:
        print(f"  [!] Gmail login failed for {GMAIL_USER}: {e}", flush=True)
        print("=== Done ===", flush=True)
        return

    results = []
    for label in active_labels:
        try:
            # Quote if containing spaces to satisfy IMAP parser
            imap_label = f'"{label}"' if " " in label else label
            typ, _ = mail.select(imap_label)
            if typ != "OK":
                print(f"  [!] Cannot select '{label}'", flush=True)
                continue
        except Exception as e:
            print(f"  [!] Cannot select '{label}': {e}", flush=True)
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
        elif any(kw in full_clean for kw in ["interview", "phone screen", "technical screen",
                                              "schedule a time", "schedule an interview",
                                              "interview invitation", "invite you to interview",
                                              "next round", "onsite interview", "on-site interview",
                                              "video interview", "coding interview"]):
            status = "interview"
        elif any(kw in full_clean for kw in ["not moving forward", "not to move forward",
                                              "regret to inform", "not selected", "position has been filled"]):
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
        role = _clean_role(extract_role(subject, body))
        location = extract_location(subject, body)
        if company:
            updated_companies[company] = {"status": status, "role": role, "location": location}

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
        new_info = None
        for uc, ui in updated_companies.items():
            if uc.lower() == cl:
                new_info = ui
                break
        if not new_info:
            continue

        new_status = new_info["status"]
        old_status = entry.get("status", "new")
        if new_status == "applied" and old_status in ("applied", "rejected", "offer", "interview"):
            continue
        if new_status == "rejected" and old_status == "rejected":
            continue
        if new_status == "offer" and old_status == "offer":
            continue
        if new_status == "interview" and old_status in ("interview", "rejected", "offer"):
            continue

        entry["status"] = new_status
        entry["date_updated"] = now
        if new_status == "applied" and "date_applied" not in entry:
            entry["date_applied"] = now
        elif new_status == "interview" and "date_interview" not in entry:
            entry["date_interview"] = now
        elif new_status == "rejected":
            entry["date_rejected"] = now
        elif new_status == "offer":
            entry["date_offer"] = now
        entry["notes"] = f"Email scan: {new_status}"
        if new_info["role"] and (entry.get("title", "") == "Unknown Role" or not entry.get("title")):
            entry["title"] = new_info["role"]
        if new_info.get("location") and (entry.get("location", "") == "Unknown" or not entry.get("location") or entry.get("location") == "Remote"):
            entry["location"] = new_info["location"]
        updated_count += 1

    print(f"  Updated {updated_count} tracker entries", flush=True)

    # Add placeholder entries for companies not in tracker so they appear in sheet
    added = 0
    for c, info in updated_companies.items():
        if c.lower() in tracker_company_set:
            continue
        role = info["role"] or "Unknown Role"
        key = job_key(role, c)
        if key in tracker["jobs"]:
            continue
        now = datetime.now().isoformat()
        status = info["status"]
        tracker["jobs"][key] = {
            "title": role,
            "company": c,
            "url": "",
            "score": "",
            "status": status,
            "location": info.get("location", "Remote"),
            "resume": "",
            "date_found": now,
            "date_updated": now,
        }
        if status == "applied":
            tracker["jobs"][key]["date_applied"] = now
        elif status == "interview":
            tracker["jobs"][key]["date_interview"] = now
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

    for c, info in updated_companies.items():
        if c.lower() not in tracker_company_set:
            print(f"  [!] '{c}' ({info['status']}) — not in tracker", flush=True)

    save_json(TRACKER_FILE, tracker)
    now_iso = datetime.now().isoformat()
    if "last_scan_by_label" not in state:
        state["last_scan_by_label"] = {}
    state["last_scan_by_label"][target_label] = now_iso
    state["last_scan"] = now_iso
    save_json(STATE_FILE, state)

    # Sync to sheet
    gsheet_id = _resolve_gsheet_id(supabase_user_email) or GSHEET_ID
    print("  Syncing to Google Sheet...", flush=True)
    if gsheet_id:
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            import base64

            creds = None
            b64_json = os.environ.get("GOOGLE_SA_JSON")
            if b64_json:
                try:
                    decoded = base64.b64decode(b64_json).decode("utf-8")
                    creds = service_account.Credentials.from_service_account_info(
                        json.loads(decoded),
                        scopes=["https://www.googleapis.com/auth/spreadsheets"]
                    )
                except Exception:
                    pass

            if not creds:
                env_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
                if env_json:
                    try:
                        creds = service_account.Credentials.from_service_account_info(
                            json.loads(env_json),
                            scopes=["https://www.googleapis.com/auth/spreadsheets"]
                        )
                    except Exception:
                        pass

            if not creds:
                sa_path = os.environ.get("GSHEET_SERVICE_ACCOUNT") or "gsheet_service_account.json"
                creds = service_account.Credentials.from_service_account_file(
                    sa_path,
                    scopes=["https://www.googleapis.com/auth/spreadsheets"]
                )

            service = build("sheets", "v4", credentials=creds)
            sheet = service.spreadsheets()

            sheet_tab_name = active_labels[0] if active_labels else "Job Tracker"
            # Auto-check and create sheet tab if not exists
            try:
                sheet_metadata = sheet.get(spreadsheetId=gsheet_id).execute()
                sheets = sheet_metadata.get('sheets', [])
                existing_titles = [s.get('properties', {}).get('title') for s in sheets]
                if sheet_tab_name not in existing_titles:
                    body = {
                        'requests': [
                            {
                                'addSheet': {
                                    'properties': {
                                        'title': sheet_tab_name
                                    }
                                }
                            }
                        ]
                    }
                    sheet.batchUpdate(spreadsheetId=gsheet_id, body=body).execute()
                    print(f"  [gsheet] Created new sheet tab '{sheet_tab_name}'", flush=True)
            except Exception as se:
                print(f"  [gsheet] Failed to check/create sheet tab '{sheet_tab_name}': {se}", flush=True)

            try:
                existing = sheet.values().get(spreadsheetId=gsheet_id, range=f"'{sheet_tab_name}'!A:L").execute()
                existing_rows = existing.get("values", [])
                existing_by_key = {}
                for i, row in enumerate(existing_rows[1:], start=2):
                    if len(row) >= 3:
                        key = (row[2].strip().lower(), row[1].strip().lower())
                        existing_by_key[key] = i
            except:
                existing_rows = []
                existing_by_key = {}

            header = ["Score", "Title", "Company", "Location", "URL", "Company Link", "Status", "Date Found"]
            new_rows = []
            updated_count_sheet = 0
            seen = set()
            for entry in tracker["jobs"].values():
                s = entry.get("status", "new")
                if s not in ("applied", "rejected", "offer", "interview"):
                    continue
                dedup = (entry["company"].lower(), entry.get("title", "").lower())
                if dedup in seen:
                    continue
                seen.add(dedup)

                company = entry.get("company", "")
                comp_link = entry.get("company_link") or entry.get("company_url") or ""
                if not comp_link and company:
                    comp_link = f"https://www.linkedin.com/company/{company.lower().replace(' ', '')}"

                row_data = [
                    entry.get("score", ""),
                    entry.get("title", ""),
                    company,
                    entry.get("location", "Remote"),
                    entry.get("url", ""),
                    comp_link,
                    s,
                    (entry.get("date_found") or "")[:10],
                ]

                if dedup in existing_by_key:
                    row_num = existing_by_key[dedup]
                    sheet.values().update(
                        spreadsheetId=gsheet_id,
                        range=f"'{sheet_tab_name}'!A{row_num}:H{row_num}",
                        valueInputOption="RAW",
                        body={"values": [row_data]}
                    ).execute()
                    updated_count_sheet += 1
                else:
                    new_rows.append(row_data)

            if not existing_rows:
                sheet.values().update(
                    spreadsheetId=gsheet_id, range=f"'{sheet_tab_name}'!A1",
                    valueInputOption="RAW", body={"values": [header]}
                ).execute()

            if updated_count_sheet:
                print(f"  [gsheet] Updated {updated_count_sheet} existing rows", flush=True)
            if new_rows:
                sheet.values().append(
                    spreadsheetId=gsheet_id, range=f"'{sheet_tab_name}'!A:H",
                    valueInputOption="RAW", body={"values": new_rows}
                ).execute()
                print(f"  [gsheet] Added {len(new_rows)} new rows", flush=True)
            if not updated_count_sheet and not new_rows:
                print(f"  [gsheet] No changes", flush=True)
        except Exception as e:
            print(f"  [gsheet] Error: {e}", flush=True)
    else:
        print("  [!] No sheet configured — skipping sheet sync", flush=True)

    # Sync to Supabase so results appear in web dashboard's Job Tracker tab
    supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if supabase_url and supabase_key:
        try:
            from supabase import create_client
            sb = create_client(supabase_url, supabase_key)
            lookup_email = supabase_user_email or GMAIL_USER
            # Look up the user by email
            user_res = sb.table("profiles").select("id").eq("email", lookup_email).execute()
            if user_res.data:
                user_id = user_res.data[0]["id"]
                synced = 0
                for entry in tracker["jobs"].values():
                    s = entry.get("status", "new")
                    if s not in ("applied", "rejected", "offer", "interview"):
                        continue
                    # Check if already exists in Supabase
                    existing = sb.table("jobs").select("id").eq("user_id", user_id)\
                        .eq("title", entry.get("title", ""))\
                        .eq("company", entry.get("company", "")).execute()
                    if existing.data:
                        # Update status
                        sb.table("jobs").update({
                            "status": s,
                            "notes": entry.get("notes", ""),
                            "location": entry.get("location", "Remote"),
                            "updated_at": datetime.now().isoformat(),
                         }).eq("id", existing.data[0]["id"]).execute()
                    else:
                        sb.table("jobs").insert({
                            "user_id": user_id,
                            "title": entry.get("title", ""),
                            "company": entry.get("company", ""),
                            "location": entry.get("location", "Remote"),
                            "url": entry.get("url", ""),
                            "description": "",
                            "score": int(entry["score"]) if str(entry.get("score", "")).strip().isdigit() else 0,
                            "score_note": "",
                            "salary": "",
                            "source": "email_scan",
                            "status": s,
                            "notes": entry.get("notes", ""),
                            "found_at": entry.get("date_found", datetime.now().isoformat()),
                            "updated_at": datetime.now().isoformat(),
                            "posted_date": entry.get("date_found", datetime.now().isoformat()),
                        }).execute()
                    synced += 1
                print(f"  [supabase] Synced {synced} entries to tracker", flush=True)
            else:
                print(f"  [supabase] User '{lookup_email}' not found", flush=True)
        except Exception as e:
            err_str = str(e)
            if "jobs_status_check" in err_str or "violates check constraint" in err_str:
                print("  [supabase] Error: Your Supabase 'jobs' table lacks the updated status constraint.", flush=True)
                print("             Please run the SQL statements in 'supabase/migration_007_widen_jobs_status.sql' in your Supabase SQL Editor.", flush=True)
            else:
                print(f"  [supabase] Error: {e}", flush=True)
    else:
        print("  [!] No SUPABASE_SERVICE_ROLE_KEY set — skipping Supabase sync", flush=True)

    print("=== Done ===", flush=True)

if __name__ == "__main__":
    main()
