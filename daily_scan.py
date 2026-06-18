"""
Daily Job Matching Agent for Kamnee Maran
==========================================
Scans configured job sources, scores each posting against the resume profile,
picks the right resume version, and emails a daily digest.

Run manually:   python daily_scan.py
Run on schedule: see .github/workflows/daily_scan.yml (GitHub Actions, free tier)

Required environment variables (set as GitHub Secrets or local .env):
  GMAIL_ADDRESS        - kamneemaran45@gmail.com
  GMAIL_APP_PASSWORD   - Gmail App Password (NOT your normal password - see setup notes)
  WHATSAPP_TO          - optional, +91XXXXXXXXXX (only if Twilio is configured)
  TWILIO_SID           - optional
  TWILIO_AUTH_TOKEN    - optional
  TWILIO_WHATSAPP_FROM - optional, e.g. whatsapp:+14155238886
"""

import os
import json
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ---------------------------------------------------------------------------
# 1. CONFIGURATION - your sources, profile, and scoring rules
# ---------------------------------------------------------------------------

PROFILE = {
    "name": "Kamnee Maran",
    "years_experience": 10,
    "core_skills": [
        "java", "python", "node.js", "microservices", "distributed systems",
        "event-driven", "kafka", "rabbitmq", "redis", "mysql", "mongodb",
        "elasticsearch", "aws", "docker", "kubernetes", "rest api",
        "system design", "high availability", "fault tolerance",
        "circuit breaker", "hystrix", "spring boot", "dropwizard",
        "fintech", "payments", "compliance", "rca", "incident management",
    ],
    "seniority_keywords": ["senior", "staff", "lead", "principal", "sde-3", "sde 3"],
    "junior_red_flags": ["junior", "intern", "entry level", "graduate", "0-2 years"],
}

# Companies known to NOT support relocation from outside the EU / no India hiring
# (update this list as you learn more - e.g. after Mollie's rejection)
NO_RELOCATION_FLAGS = {
    "mollie": "No relocation support outside Europe (confirmed - application rejected screening)",
}

# Companies confirmed to support relocation / sponsor visas / have India presence
RELOCATION_FRIENDLY = {
    "guerrilla games": "Explicit relocation + immigration support",
    "backbase": "Hyderabad office - no relocation needed",
    "booking.com": "Historically strong visa sponsorship",
    "xero": "NZ visa sponsorship available",
    "halter": "NZ visa sponsorship + relocation support",
    "canonical": "100% remote - no visa needed",
    "gitlab": "100% remote - no visa needed",
}

# Job sources to scan. Each entry: name, url, region, type (board/company/agency)
JOB_SOURCES = [
    {"name": "Picnic (Lever)", "url": "https://jobs.eu.lever.co/picnic", "region": "NL", "type": "company"},
    {"name": "Booking.com Careers", "url": "https://careers.booking.com", "region": "NL", "type": "company"},
    {"name": "bol.com Careers", "url": "https://careers.bol.com/en/jobs/", "region": "NL", "type": "company"},
    {"name": "Guerrilla Games", "url": "https://www.guerrilla-games.com/join", "region": "NL", "type": "company"},
    {"name": "Mollie Jobs", "url": "https://jobs.mollie.com/vacancies", "region": "NL", "type": "company"},
    {"name": "Just Eat Takeaway", "url": "https://careers.justeattakeaway.com/global/en/c/tech-product-jobs", "region": "NL", "type": "company"},
    {"name": "Backbase Careers", "url": "https://www.backbase.com/careers/jobs", "region": "IN", "type": "company"},
    {"name": "Raisin Jobs", "url": "https://jobs.raisin.com", "region": "DE", "type": "company"},
    {"name": "Solaris Careers", "url": "https://www.solarisbank.com/en/careers/", "region": "DE", "type": "company"},
    {"name": "SumUp Careers", "url": "https://www.sumup.com/en-us/careers/", "region": "DE", "type": "company"},
    {"name": "Celonis Jobs", "url": "https://www.celonis.com/careers/jobs/", "region": "DE", "type": "company"},
    {"name": "Personio Careers", "url": "https://www.personio.com/career/", "region": "DE", "type": "company"},
    {"name": "GitLab Jobs", "url": "https://about.gitlab.com/jobs/all-jobs/", "region": "Remote", "type": "company"},
    {"name": "Elastic Careers", "url": "https://www.elastic.co/about/careers/", "region": "Remote", "type": "company"},
    {"name": "HashiCorp Careers", "url": "https://www.hashicorp.com/en/careers", "region": "Remote", "type": "company"},
    {"name": "Canonical Careers", "url": "https://canonical.com/careers", "region": "Remote", "type": "company"},
    {"name": "Atlassian Careers", "url": "https://www.atlassian.com/company/careers", "region": "AU", "type": "company"},
    {"name": "Xero Careers", "url": "https://www.xero.com/about/careers/", "region": "NZ", "type": "company"},
    {"name": "Halter Careers", "url": "https://halter.io/careers", "region": "NZ", "type": "company"},
    {"name": "Arbeitnow Visa Sponsorship", "url": "https://www.arbeitnow.com/visa-sponsorship-jobs", "region": "DE", "type": "board"},
    {"name": "EuroTechJobs", "url": "https://www.eurotechjobs.com/job_search", "region": "EU", "type": "board"},
    {"name": "relocate.me", "url": "https://relocate.me/international-jobs", "region": "EU", "type": "board"},
]

RECRUITER_AGENCIES = [
    {"name": "Hays Europe", "url": "https://www.hays.nl"},
    {"name": "Spring Professional", "url": "https://www.springprofessional.nl"},
    {"name": "Michael Page", "url": "https://www.michaelpage.nl"},
    {"name": "Randstad", "url": "https://www.randstad.nl"},
    {"name": "Robert Half", "url": "https://www.roberthalf.nl"},
    {"name": "Darwin Recruitment", "url": "https://www.darwinrecruitment.com"},
]

RESUME_VERSIONS = {
    "faang": "Kamnee_Maran_Resume_FAANG.pdf",
    "indian_tech": "Kamnee_Maran_Resume_IndianTech.pdf",
    "general": "Kamnee_Maran_Resume_v2.pdf",
}

# Map companies to resume version (extend this as you add companies)
COMPANY_RESUME_MAP = {
    "picnic": "faang", "booking.com": "faang", "bol.com": "faang",
    "guerrilla games": "faang", "mollie": "faang", "just eat takeaway": "faang",
    "raisin": "faang", "solaris": "faang", "sumup": "faang", "celonis": "faang",
    "personio": "faang", "gitlab": "faang", "elastic": "faang",
    "hashicorp": "faang", "canonical": "faang", "atlassian": "faang",
    "xero": "faang", "halter": "faang",
    "backbase": "faang",
}


# ---------------------------------------------------------------------------
# 2. FIT SCORING
# ---------------------------------------------------------------------------

def score_job(title, description, company):
    """Returns a fit score 0-100 based on keyword overlap with PROFILE."""
    text = (title + " " + description).lower()

    if any(flag in text for flag in PROFILE["junior_red_flags"]):
        return 0, "Filtered: junior/entry-level role detected"  # auto-reject junior/intern roles

    skill_hits = sum(1 for skill in PROFILE["core_skills"] if skill in text)
    skill_score = min(skill_hits / 8, 1.0) * 60  # up to 60 points for skill overlap

    seniority_score = 25 if any(k in text for k in PROFILE["seniority_keywords"]) else 10

    relocation_bonus = 0
    relocation_note = ""
    company_lower = company.lower()
    for flagged_co, note in NO_RELOCATION_FLAGS.items():
        if flagged_co in company_lower:
            relocation_bonus = -20
            relocation_note = f"WARNING: {note}"
    for friendly_co, note in RELOCATION_FRIENDLY.items():
        if friendly_co in company_lower:
            relocation_bonus = 15
            relocation_note = note

    score = round(skill_score + seniority_score + relocation_bonus)
    score = max(0, min(100, score))
    return score, relocation_note


def pick_resume(company):
    company_lower = company.lower()
    for key, resume in COMPANY_RESUME_MAP.items():
        if key in company_lower:
            return RESUME_VERSIONS[resume]
    return RESUME_VERSIONS["faang"]  # default for unknown EU/global companies


def tailoring_suggestion(title, description, company):
    """Lightweight rule-based suggestion. For deeper tailoring, paste the JD into
    a Claude chat alongside the resume - this just flags what to check."""
    text = (title + " " + description).lower()
    suggestions = []

    keyword_checks = {
        "kafka": "Mention Kafka explicitly if not already prominent in the summary.",
        "kotlin": "Flag Kotlin as 'learnable, strong Java foundation' if not already on resume.",
        "kubernetes": "Confirm Kubernetes is visible in the skills section.",
        "go": "No Go experience on resume - consider whether to apply or note willingness to learn.",
        "compliance": "Surface the RENT/EDU compliance (PAN/FRA) bullet higher in the experience section.",
        "payments": "Lead with PhonePe payments-scale experience in the summary.",
        "kafka streams": "Specifically mention stream processing experience if applicable.",
    }
    for kw, note in keyword_checks.items():
        if kw in text:
            suggestions.append(note)

    if not suggestions:
        suggestions.append("No specific gaps detected - standard tailoring pass recommended before applying.")
    return suggestions


# ---------------------------------------------------------------------------
# 3. SCANNING (placeholder - wire up real scraping/APIs here)
# ---------------------------------------------------------------------------

def fetch_jobs_from_source(source):
    """
    Pulls live job postings from public ATS APIs where available.
    Confirmed working, no-auth-required APIs (as of mid-2026):
      - Lever:      https://api.lever.co/v0/postings/{company}?mode=json
                    (EU-hosted Lever accounts use the same endpoint format)
      - Greenhouse: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
      - Ashby:      https://api.ashbyhq.com/posting-api/job-board/{company}

    For sites without a public ATS feed (most custom company career pages),
    this prints a manual-check reminder rather than attempting fragile HTML
    scraping, which breaks every time a site redesigns.
    """
    jobs = []
    try:
        if "lever.co" in source["url"]:
            company_slug = source["url"].rstrip("/").split("/")[-1]
            api_url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                for posting in resp.json():
                    jobs.append({
                        "title": posting.get("text", ""),
                        "company": source["name"],
                        "location": posting.get("categories", {}).get("location", "Unknown"),
                        "url": posting.get("hostedUrl", source["url"]),
                        "description": posting.get("descriptionPlain", "")[:2000],
                    })
            else:
                print(f"  [warn] Lever API returned {resp.status_code} for {source['name']}")

        elif "greenhouse.io" in source["url"] or source.get("ats") == "greenhouse":
            company_slug = source.get("ats_slug") or source["url"].rstrip("/").split("/")[-1]
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                for posting in resp.json().get("jobs", []):
                    jobs.append({
                        "title": posting.get("title", ""),
                        "company": source["name"],
                        "location": posting.get("location", {}).get("name", "Unknown"),
                        "url": posting.get("absolute_url", source["url"]),
                        "description": posting.get("content", "")[:2000],
                    })
            else:
                print(f"  [warn] Greenhouse API returned {resp.status_code} for {source['name']}")

        elif "ashbyhq.com" in source["url"] or source.get("ats") == "ashby":
            company_slug = source.get("ats_slug") or source["url"].rstrip("/").split("/")[-1]
            api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                for posting in resp.json().get("jobs", []):
                    jobs.append({
                        "title": posting.get("title", ""),
                        "company": source["name"],
                        "location": posting.get("location", "Unknown"),
                        "url": posting.get("jobUrl", source["url"]),
                        "description": posting.get("descriptionPlain", "")[:2000],
                    })
            else:
                print(f"  [warn] Ashby API returned {resp.status_code} for {source['name']}")

        else:
            print(f"  [skip] {source['name']} - no public ATS API detected. "
                  f"Check manually: {source['url']}")
    except Exception as e:
        print(f"  [error] Failed to fetch {source['name']}: {e}")
    return jobs


# ---------------------------------------------------------------------------
# 4. EMAIL DIGEST
# ---------------------------------------------------------------------------

def build_email_html(matches):
    if not matches:
        return "<p>No new matches above threshold today. Sources checked, all clear.</p>"

    rows = ""
    for m in matches:
        rows += f"""
        <div style="border:1px solid #ddd;border-radius:8px;padding:16px;margin-bottom:12px;">
          <h3 style="margin:0 0 4px;font-size:16px;">{m['title']}</h3>
          <p style="margin:0 0 8px;color:#666;font-size:13px;">{m['company']} &middot; {m['location']}</p>
          <p style="margin:0 0 8px;font-size:14px;"><b>Fit score: {m['score']}%</b> &middot; Use: {m['resume']}</p>
          <p style="margin:0 0 8px;font-size:13px;color:#444;">{m['relocation_note']}</p>
          <ul style="margin:0 0 8px;font-size:13px;color:#444;">
            {''.join(f'<li>{s}</li>' for s in m['suggestions'])}
          </ul>
          <a href="{m['url']}" style="font-size:13px;">Open job posting &rarr;</a>
        </div>
        """
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;">
      <h2>Daily job matches - {datetime.now().strftime('%d %b %Y')}</h2>
      <p>{len(matches)} role(s) scored above threshold.</p>
      {rows}
    </body></html>
    """


def send_email(html_body, subject="Daily Job Matches"):
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_app_password:
        print("Email not sent - GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set.")
        print("See setup notes in README for how to create a Gmail App Password.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, gmail_address, msg.as_string())
        print(f"Email sent to {gmail_address}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def send_whatsapp(message):
    """Optional - requires Twilio account with WhatsApp sandbox or approved number."""
    sid = os.environ.get("TWILIO_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM")
    to_number = os.environ.get("WHATSAPP_TO")

    if not all([sid, token, from_number, to_number]):
        print("WhatsApp not sent - Twilio environment variables not fully set.")
        return False

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        resp = requests.post(
            url,
            auth=(sid, token),
            data={"From": from_number, "To": to_number, "Body": message},
            timeout=10,
        )
        if resp.status_code == 201:
            print("WhatsApp message sent.")
            return True
        else:
            print(f"WhatsApp send failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"WhatsApp error: {e}")
        return False


# ---------------------------------------------------------------------------
# 5. MAIN
# ---------------------------------------------------------------------------

def main():
    print(f"=== Daily job scan started: {datetime.now().isoformat()} ===")
    all_matches = []

    for source in JOB_SOURCES:
        print(f"Scanning: {source['name']} ({source['region']})")
        jobs = fetch_jobs_from_source(source)
        for job in jobs:
            score, relocation_note = score_job(job["title"], job["description"], job["company"])
            if score >= 70:
                resume = pick_resume(job["company"])
                suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                all_matches.append({
                    **job,
                    "score": score,
                    "resume": resume,
                    "relocation_note": relocation_note,
                    "suggestions": suggestions,
                })

    all_matches.sort(key=lambda m: m["score"], reverse=True)

    print(f"Found {len(all_matches)} matches above 70% threshold.")

    html = build_email_html(all_matches)
    send_email(html, subject=f"Daily Job Matches - {len(all_matches)} new roles")

    if all_matches:
        top = all_matches[0]
        send_whatsapp(
            f"Job match: {top['title']} at {top['company']} ({top['score']}%). "
            f"Check your email for full details."
        )

    with open("last_scan_results.json", "w") as f:
        json.dump(all_matches, f, indent=2)

    print("=== Scan complete ===")


if __name__ == "__main__":
    main()
