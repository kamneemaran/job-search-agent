"""Scan Gmail for Glassdoor & Indeed job digest emails, parse + score jobs.

Output: JSON to stdout (for piping into daily_scan.py) and/or saved to file.

Usage:
    .venv/bin/python3 email_digest_scan.py [--days 7] [--output digest_jobs.json]

Integration:
    Import parse_all_digests() to get list of scored job dicts.
"""
import imaplib, email, re, json, sys, os
from datetime import datetime, timedelta

GMAIL_USER = "kamneemaran45@gmail.com"
GMAIL_PASS = "bttjcludverlbmnr"

# ── Glassdoor HTML parsing helpers ─────────────────────────────────────────

def _extract_gd_company_from_logo(html):
    """Extract company name from Glassdoor company logo URLs."""
    names = set()
    for m in re.finditer(r'media\.glassdoor\.com/sql/\d+/([^/]+?)-squareLogo', html, re.I):
        name = m.group(1).replace("-", " ").strip()
        # Clean up common suffixes
        name = re.sub(r'\s*\.{2,}', '', name)
        if name and len(name) > 1:
            names.add(name.title())
    return list(names)


def _extract_gd_job_ids(html):
    """Extract job listing IDs from Glassdoor URLs."""
    ids = set()
    for m in re.finditer(r'jobListingId=(\d{10,})', html):
        ids.add(m.group(1))
    return list(ids)


def _extract_gd_jobs_from_subject(subject):
    """Parse Glassdoor subject: 'Title at Company and N more jobs in Location'."""
    subject = subject.strip()
    m = re.match(r'^(.+?)\s+at\s+(.+?)\s+and\s+(\d+)\s+more\s+jobs\s+in\s+(.+?)\s+for\s+you', subject, re.I)
    if m:
        title = m.group(1).strip()
        company = m.group(2).strip()
        count = int(m.group(3)) + 1  # +1 for the first job
        location = m.group(4).strip()
        return title, company, count, location
    # Try simpler: 'Title at Company' 
    m = re.match(r'^(.+?)\s+at\s+(.+?)$', subject)
    if m:
        return m.group(1).strip(), m.group(2).strip(), 1, ""
    return None


def parse_glassdoor_email(subject, html_body):
    """Parse Glassdoor digest email for job listings."""
    result = _extract_gd_jobs_from_subject(subject)
    if not result:
        return []
    title, company, count, location = result
    companies_from_logos = _extract_gd_company_from_logo(html_body)
    job_ids = _extract_gd_job_ids(html_body)

    # Build job entries from what we can extract
    if count == 1:
        jobs = [{"title": title, "company": company, "location": location, "source": "glassdoor"}]
    else:
        jobs = [{"title": title, "company": company, "location": location, "source": "glassdoor"}]
        # Add other jobs from companies list (minus the first which is the subject company)
        other_companies = [c for c in companies_from_logos if c.lower() != company.lower()]
        job_ids_other = list(job_ids) if len(job_ids) > 1 else []
        for i in range(min(count - 1, max(len(other_companies), len(job_ids_other), 1))):
            c = other_companies[i] if i < len(other_companies) else f"Unknown ({company})"
            jid = job_ids_other[i] if i < len(job_ids_other) else ""
            jobs.append({
                "title": f"Role at {c}",
                "company": c,
                "location": location,
                "source": "glassdoor",
                "job_id": jid,
            })

    # Apply URL template for Glassdoor
    base = "https://www.glassdoor.co.in/partner/jobListing.htm"
    for j in jobs:
        jid = j.get("job_id", "")
        if jid:
            j["url"] = f"{base}?jobListingId={jid}"
        else:
            j["url"] = ""

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

def fetch_glassdoor_emails(days=7):
    """Fetch Glassdoor digest emails and parse jobs."""
    mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    mail.login(GMAIL_USER, GMAIL_PASS)
    mail.select("INBOX")

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
            parsed = parse_glassdoor_email(subj, html_body)
            jobs.extend(parsed)

    mail.logout()
    return jobs


def fetch_indeed_emails(days=7):
    """Fetch Indeed job recommendation emails and parse jobs."""
    mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    mail.login(GMAIL_USER, GMAIL_PASS)
    mail.select("INBOX")

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

def parse_all_digests(days=7):
    """Fetch and parse all job digest emails. Returns list of job dicts."""
    jobs = []
    try:
        gd = fetch_glassdoor_emails(days)
        jobs.extend(gd)
        print(f"  [glassdoor] parsed {len(gd)} jobs", flush=True)
    except Exception as e:
        print(f"  [glassdoor] ERROR: {e}", flush=True)

    try:
        ind = fetch_indeed_emails(days)
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
    args = parser.parse_args()

    print(f"=== Scanning job digests (past {args.days}d) ===", flush=True)
    jobs = parse_all_digests(args.days)
    print(f"Total: {len(jobs)} jobs parsed", flush=True)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(jobs, f, indent=2)
        print(f"Saved to {args.output}", flush=True)
    else:
        print(json.dumps(jobs, indent=2))
