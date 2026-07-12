"""Scan Gmail for Glassdoor & Indeed job digest emails, parse + score jobs.

Output: JSON to stdout (for piping into daily_scan.py) and/or saved to file.

Usage:
    .venv/bin/python3 email_digest_scan.py [--days 7] [--output digest_jobs.json]

Integration:
    Import parse_all_digests() to get list of scored job dicts.
"""
import imaplib, email, re, json, sys, os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

GMAIL_USER = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")

# ── Glassdoor HTML parsing ────────────────────────────────────────────────

def parse_glassdoor_email(html_body):
    """Parse Glassdoor digest email HTML for job listings using BeautifulSoup.

    Returns list of dicts with title, company, location, url, source, easy_apply.
    """
    soup = BeautifulSoup(html_body, "html.parser")
    base = "https://www.glassdoor.co.in/partner/jobListing.htm"
    jobs = []

    for link in soup.find_all("a", href=re.compile(r"jobListingId=\d{10,}")):
        href = link.get("href", "")
        jid = re.search(r"jobListingId=(\d{10,})", href)
        job_id = jid.group(1) if jid else ""

        text = link.parent.get_text(separator=" | ", strip=True) if link.parent else ""
        if not text:
            continue

        parts = [p.strip() for p in text.split(" | ") if p.strip()]

        # Structure detection: skip rating (★★★) and bracket noise
        has_rating = any("★" in p for p in parts)
        offset = 1 if has_rating else 0  # skip rating if present

        # Detect Easy Apply
        easy_apply = any("easy apply" in p.lower() for p in parts)

        # Detect salary and "Est." markers
        salary = next((p for p in parts if re.search(r'[₹$€£NZ]', p) or "Est." in p), "")

        # Detect age (e.g. 3d, 20h)
        ago = next((p for p in parts if re.match(r'\d+[dhm]', p)), "")

        # Company is first part
        company = parts[0] if len(parts) > 0 else ""

        # Title is at index 1+offset (or 1 if no offset but part 1 has a ★ — fallback)
        title_idx = 1 + offset
        title = parts[title_idx] if len(parts) > title_idx else ""

        # Location is at index 2+offset
        loc_idx = 2 + offset
        location = parts[loc_idx] if len(parts) > loc_idx else ""

        # Skip malformed entries where title is actually a location or salary
        if not title or not company:
            continue
        if re.match(r'^[₹$€£NZ]', title) or "," in title:
            continue

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "salary_raw": salary.replace("( ", "").replace(" )", "").strip(),
            "url": f"{base}?jobListingId={job_id}",
            "source": "glassdoor",
            "easy_apply": easy_apply,
            "ago": ago,
            "job_id": job_id,
        })

    return jobs


# ── Indeed plain-text parsing ──────────────────────────────────────────────

def parse_indeed_email(body):
    """Parse Indeed single-job recommendation email (plain text)."""
    lines = body.strip().split("\n")
    # Find the job details block after the intro text
    title, company, location, salary, jt, url = "", "", "", "", "", ""
    idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("View job:") or stripped.startswith("Apply now:"):
            continue
        # Look for the title line (usually after the intro paragraph ends with a blank line)
        # Indeed format: blank line, Title, Company, Location/Remote, Salary?, Job type?
        if not title and not stripped.startswith("Hi") and not stripped.startswith("Your background") and not stripped.startswith("It looks") and not stripped.startswith("If you"):
            title = stripped
            idx = i
            break

    if not title:
        return None

    # Company is next non-empty line after title
    for i in range(idx + 1, min(idx + 10, len(lines))):
        s = lines[i].strip()
        if s and not s.startswith("View job:") and not s.startswith("Apply now:"):
            if not company:
                company = s
            elif not location:
                location = s
            elif not salary and ("$" in s or "₹" in s or "€" in s or "£" in s):
                salary = s
            elif not jt and any(kw in s.lower() for kw in ["job type", "permanent", "contract", "full-time", "part-time", "temporary"]):
                jt = s

    # Extract URLs
    for line in lines:
        if line.startswith("View job:") or line.startswith("Apply now:"):
            url_candidate = line.split(":", 1)[1].strip()
            if not url:
                url = url_candidate
            break

    if not company:
        return None

    return {
        "title": title,
        "company": company,
        "location": location,
        "salary_raw": salary,
        "job_type_raw": jt,
        "url": url,
        "source": "indeed",
    }


# ── Gmail fetching ─────────────────────────────────────────────────────────

DIGEST_LABEL = os.environ.get("GMAIL_DIGEST_LABEL")

def fetch_glassdoor_emails(days=7, label=None):
    """Fetch Glassdoor digest emails and parse jobs."""
    mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    mail.login(GMAIL_USER, GMAIL_PASS)
    mail.select(label or DIGEST_LABEL)

    since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    r, d = mail.search(None, f'(FROM "noreply@glassdoor.com" SINCE {since})')
    jobs = []
    if r == "OK" and d[0]:
        nums = d[0].split()
        print(f"  [glassdoor] {len(nums)} emails to scan", flush=True)
        for num in nums:
            r2, md = mail.fetch(num, "(RFC822)")
            if r2 != "OK":
                continue
            msg = email.message_from_bytes(md[0][1])
            subj = msg["subject"] or ""
            html_body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/html" and part.get_payload(decode=True):
                        html_body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                html_body = (msg.get_payload(decode=True) or b"").decode("utf-8", errors="ignore")
            parsed = parse_glassdoor_email(html_body)
            jobs.extend(parsed)

    mail.logout()
    return jobs


def fetch_indeed_emails(days=7, label=None):
    """Fetch Indeed job recommendation emails and parse jobs."""
    mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    mail.login(GMAIL_USER, GMAIL_PASS)
    mail.select(label or DIGEST_LABEL)

    since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    r, d = mail.search(None, f'(FROM "donotreply@match.indeed.com" SINCE {since})')
    jobs = []
    if r == "OK" and d[0]:
        nums = d[0].split()
        print(f"  [indeed] {len(nums)} emails to scan", flush=True)
        for num in nums:
            r2, md = mail.fetch(num, "(RFC822)")
            if r2 != "OK":
                continue
            msg = email.message_from_bytes(md[0][1])
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain" and part.get_payload(decode=True):
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = (msg.get_payload(decode=True) or b"").decode("utf-8", errors="ignore")
            parsed = parse_indeed_email(body)
            if parsed:
                jobs.append(parsed)

    mail.logout()
    return jobs


# ── Main entry ─────────────────────────────────────────────────────────────

def parse_all_digests(days=7, label=None):
    """Fetch and parse all job digest emails. Returns list of job dicts."""
    jobs = []
    try:
        gd = fetch_glassdoor_emails(days, label)
        jobs.extend(gd)
        print(f"  [glassdoor] parsed {len(gd)} jobs", flush=True)
    except Exception as e:
        print(f"  [glassdoor] ERROR: {e}", flush=True)

    try:
        ind = fetch_indeed_emails(days, label)
        jobs.extend(ind)
        print(f"  [indeed] parsed {len(ind)} jobs", flush=True)
    except Exception as e:
        print(f"  [indeed] ERROR: {e}", flush=True)

    return jobs


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scan Gmail for job digest emails")
    parser.add_argument("--days", type=int, default=7, help="How many days back to scan")
    parser.add_argument("--output", default="", help="Output JSON file path")
    parser.add_argument("--digest-label", default=None, help="Gmail label to scan (default: INBOX or GMAIL_DIGEST_LABEL env)")
    args = parser.parse_args()

    print(f"=== Scanning job digests (past {args.days}d) ===", flush=True)
    jobs = parse_all_digests(args.days, args.digest_label)
    print(f"Total: {len(jobs)} jobs parsed", flush=True)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(jobs, f, indent=2)
        print(f"Saved to {args.output}", flush=True)
    else:
        print(json.dumps(jobs, indent=2))
