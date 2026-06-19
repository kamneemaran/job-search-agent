"""
Daily Job Matching Agent
========================
Scans company ATS APIs (Greenhouse, Lever, Ashby) plus job boards
(LinkedIn, Indeed, Naukri, Instahyre) for matching roles, scores
each posting against the resume profile, and emails a daily digest.

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
import sys
import json
import re
import smtplib
import imaplib
import email
import argparse
import requests
import cloudscraper
import PyPDF2
from dotenv import load_dotenv
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Lazy import for Playwright (headless browser for JS-rendered sites)
_playwright_browser = None
def _get_browser():
    global _playwright_browser
    if _playwright_browser is None:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        _playwright_browser = _pw.chromium.launch(headless=True)
    return _playwright_browser

load_dotenv()


def strip_html(html):
    """Remove HTML tags and decode common entities for keyword matching."""
    text = html.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

# ---------------------------------------------------------------------------
# 1. CONFIGURATION - your sources, profile, and scoring rules
# ---------------------------------------------------------------------------

PROFILE = {
    "name": "Kamnee Maran",
    "years_experience": 10,
    "core_skills": [
        "java", "python", "node.js", "golang", "microservices", "distributed systems",
        "event-driven", "kafka", "redis", "mysql", "postgresql", "mongodb",
        "elasticsearch", "aws", "azure", "gcp", "docker", "kubernetes", "rest api",
        "api development", "system design", "high availability", "scalable",
        "spring boot", "backend", "cloud infrastructure", "devops",
        "fintech", "payments", "compliance", "incident management",
        "ci/cd", "terraform", "architecture", "soa", "data pipelines",
    ],
    "seniority_keywords": ["senior", "staff", "lead", "principal", "sde-3", "sde 3"],
    "junior_red_flags": ["junior", "intern", "entry level", "graduate", "0-2 years"],
    # Job titles that are NOT relevant (different career tracks)
    "title_red_flags": [
        # Infrastructure / network / devops roles outside backend/platform engineering
        "network engineer", "network architect", "network administrator", "network security",
        "devops engineer", "devops", "site reliability engineer", "sre",
        # Sales / account / customer-facing roles
        "account executive", "account manager", "account director",
        "sales engineer", "sales representative", "sales development", "sales ",
        "business development", "business development representative",
        "customer success", "customer support", "customer experience",
        "technical account manager", "solutions engineer", "solutions architect",
        "technical account management", "technical account", "account management",
        # Product / program / project management
        "product manager", "program manager", "project manager", "product owner",
        "engineering manager", "manager, engineering", "director of engineering",
        "manager ii", "manager iii", "engineering - applied", "engineering - ai",
        # People / HR
        "recruiter", "hiring", "talent acquisition", "hr ", "hris", "workday",
        "people technology", "people operations", "people partner", "people team",
        # Marketing / content / brand
        "marketing", "content writer", "content strategist", "social media", "brand ",
        "corporate communications", "communications lead", "communications manager",
        "public relations", "pr ", "media relations",
        # Finance / legal / compliance
        "finance", "accounting", "accountant", "legal", "lawyer",
        "compliance", "mlro", "money laundering", "regulatory",
        "payments risk", "payments compliance", "risk manager", "risk analyst",
        # Data science / analytics / pure AI
        "data scientist", "data analyst", "data engineer",
        "analytics",
        "machine learning engineer", "ml engineer", "deep learning",
        "ai research", "ai/ml", "prompt engineer", "llm engineer",
        # Business operations / strategy / non-eng management
        "process strategy", "process optimization", "process manager",
        "operations manager", "business operations", "strategy manager",
        "operations strategy", "business strategy",
        "strategic intelligence", "protective intelligence",
        "clearing operations", "clearing",
        "partner manager", "partner enablement", "enablement manager",
        "channel partner", "channel manager",
        "market manager", "marketplace manager", "mid market",
        "key account", "accounts executive",
        "gtm ", "go to market", "strategy/operations",
        "workforce management", "workforce",
        "delivery excellence", "delivery manager", "delivery lead",
        "field enablement", "field marketing",
        "business process", "process improvement",
        # Localization / translation
        "localization", "localization manager", "translator",
        # Design / UX
        "designer", "ui ", "ux ", "product design", "visual design",
        # Miscellaneous non-engineering
        "technical writer", "documentation", "analyst",
        "support engineer", "it support", "desktop support",
        "maintenance", "assistant", "associate ",
        "administrative", "admin assistant", "office manager",
        "safety", "safety specialist", "security specialist", "security guard",
        # Incident / escalation / support management
        "incident manager", "incident response", "escalations manager",
        "escalation manager", "escalation engineer", "incident commander",
        # Policy / government / regulatory affairs
        "public policy", "policy manager", "policy director", "policy advisor",
        "policy economist", "government affairs", "regulatory affairs",
        # Administrative / legal / HR
        "executive assistant",
        "stock administrator",
        "corporate counsel", "securities counsel", "legal counsel", "paralegal",
        "hr business partner", "hr coordinator", "payroll",
        # Sales support / non-technical customer roles
        "inside sales", "sales support", "sales operations",
        "customer success manager", "customer support specialist",
        # Finance / accounting (non-SAP specific)
        "accountant", "accounts payable", "accounts receivable",
        "financial analyst", "finance manager", "controller",
    ],
}

# Keywords that indicate visa / relocation support in a job description
VISA_RELOCATION_KEYWORDS = [
    "visa sponsorship", "work visa", "sponsorship available", "employment visa",
    "relocation support", "relocation assistance", "relocation package",
    "relocation provided", "immigration support", "visa provided",
    "we sponsor", "will sponsor", "work authorization",
    "relocation assistance available", "global mobility",
    "visa", "relocation",
]

# Keywords that suggest the role requires a specific non-English language
# (used to auto-reject roles that aren't primarily English-speaking)
NON_ENGLISH_LANGUAGE_KEYWORDS = [
    "fluent in german", "fluent in dutch", "fluent in french", "fluent in japanese",
    "fluent in mandarin", "fluent in spanish", "fluent in italian",
    "german speaking", "dutch speaking", "french speaking", "japanese speaking",
    "must speak german", "must speak dutch", "must speak french",
    "native german", "native dutch", "native french",
    "deutschkenntnisse", "niederländisch", "französisch",
]

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
    "elastic": "100% remote - no visa needed",
    "stripe": "Global remote - visa sponsorship case-by-case",
    "dropbox": "Virtual First - limited sponsorship",
    "datadog": "Global hiring - sponsorship possible",
    "coinbase": "Remote - US/global roles with limited sponsorship",
    "airbnb": "Global - sponsorship for critical roles",
}

# Job sources to scan. Each entry: name, url, region, type (board/company/agency)
# For Greenhouse/Lever/Ashby, set ats and ats_slug for API-based fetching.
JOB_SOURCES = [
    # --- REMOTE / GLOBAL (Greenhouse companies) ---
    {"name": "GitLab", "url": "https://about.gitlab.com/jobs/all-jobs/", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "gitlab"},
    {"name": "Elastic", "url": "https://www.elastic.co/about/careers/", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "elastic"},
    {"name": "Stripe", "url": "https://stripe.com/jobs", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "stripe"},
    {"name": "Airbnb", "url": "https://careers.airbnb.com", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "airbnb"},
    {"name": "Dropbox", "url": "https://www.dropbox.com/jobs", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "dropbox"},
    {"name": "Datadog", "url": "https://www.datadoghq.com/careers/", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "datadog"},
    {"name": "Discord", "url": "https://discord.com/careers", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "discord"},
    {"name": "Coinbase", "url": "https://www.coinbase.com/careers", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "coinbase"},
    {"name": "Reddit", "url": "https://www.redditinc.com/careers", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "reddit"},
    {"name": "Lyft", "url": "https://www.lyft.com/careers", "region": "US", "type": "company", "ats": "greenhouse", "ats_slug": "lyft"},
    {"name": "Pinterest", "url": "https://www.pinterestcareers.com", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "pinterest"},
    {"name": "Instacart", "url": "https://instacart.careers", "region": "US", "type": "company", "ats": "greenhouse", "ats_slug": "instacart"},
    {"name": "Webflow", "url": "https://webflow.com/jobs", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "webflow"},
    {"name": "Upwork", "url": "https://www.upwork.com/careers", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "upwork"},
    {"name": "Betterment", "url": "https://www.betterment.com/careers", "region": "US", "type": "company", "ats": "greenhouse", "ats_slug": "betterment"},
    {"name": "GoDaddy", "url": "https://careers.godaddy.com", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "godaddy"},
    {"name": "Vercel", "url": "https://vercel.com/careers", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "vercel"},
    # --- IT Services / Enterprise (some SAP/ERP relevance) ---
    {"name": "TCS", "url": "https://www.tcs.com/careers", "region": "IN", "type": "company", "ats": "greenhouse", "ats_slug": "tcs"},
    # --- EU / NL / DE ---
    {"name": "Mollie", "url": "https://jobs.mollie.com", "region": "NL", "type": "company"},
    {"name": "Booking.com", "url": "https://careers.booking.com", "region": "NL", "type": "company"},
    {"name": "Picnic", "url": "https://jobs.picnic.app", "region": "NL", "type": "company"},
    {"name": "Personio", "url": "https://www.personio.com/career/", "region": "DE", "type": "company"},
    # --- Job boards (manual check - no public API available) ---
    {"name": "LinkedIn Jobs", "url": "https://www.linkedin.com/jobs", "region": "Global", "type": "board"},
    {"name": "Wellfound", "url": "https://wellfound.com/jobs", "region": "Global", "type": "board"},
    {"name": "Glassdoor", "url": "https://www.glassdoor.com/Jobs", "region": "Global", "type": "board"},
    {"name": "Naukri", "url": "https://www.naukri.com", "region": "IN", "type": "board"},
    {"name": "Instahyre", "url": "https://www.instahyre.com", "region": "IN", "type": "board"},
    {"name": "Hiring.cafe", "url": "https://hiring.cafe", "region": "Global", "type": "board"},
    {"name": "Arbeitnow Visa Sponsorship", "url": "https://www.arbeitnow.com/visa-sponsorship-jobs", "region": "DE", "type": "board"},
    {"name": "EuroTechJobs", "url": "https://www.eurotechjobs.com/job_search", "region": "EU", "type": "board"},
    {"name": "relocate.me", "url": "https://relocate.me/international-jobs", "region": "EU", "type": "board"},
    # --- Job boards from resume portal lists ---
    {"name": "RemoteOK", "url": "https://remoteok.com/remote-jobs", "region": "Global", "type": "board"},
    {"name": "Remotive", "url": "https://remotive.com/remote-jobs", "region": "Global", "type": "board"},
    {"name": "Stack Overflow Jobs", "url": "https://stackoverflow.com/jobs", "region": "Global", "type": "board"},
    {"name": "Jobspresso", "url": "https://jobspresso.co", "region": "Global", "type": "board"},
    {"name": "Working Nomads", "url": "https://www.workingnomads.com/jobs", "region": "Global", "type": "board"},
    {"name": "Europe Remotely", "url": "https://europeremotely.com/jobs", "region": "EU", "type": "board"},
    {"name": "NoDesk", "url": "https://nodesk.co/remote-jobs", "region": "Global", "type": "board"},
    {"name": "Pangian", "url": "https://pangian.com/job-search", "region": "Global", "type": "board"},
    {"name": "Y Combinator Jobs", "url": "https://www.ycombinator.com/jobs", "region": "Global", "type": "board"},
    {"name": "FlexJobs", "url": "https://www.flexjobs.com/search", "region": "Global", "type": "board"},
    {"name": "Virtual Vocations", "url": "https://www.virtualvocations.com", "region": "Global", "type": "board"},
    {"name": "Skip The Drive", "url": "https://skipthedrive.com", "region": "Global", "type": "board"},
    {"name": "RemoteHabits", "url": "https://remotehabits.com", "region": "Global", "type": "board"},
    {"name": "Remote4Me", "url": "https://remote4me.com", "region": "Global", "type": "board"},
    {"name": "We Work Remotely", "url": "https://weworkremotely.com", "region": "Global", "type": "board"},
    {"name": "SimplyHired", "url": "https://www.simplyhired.com", "region": "Global", "type": "board"},
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

def score_job(title, description, company, location=""):
    """
    Returns (score 0-100, note string).
    For roles outside India: visa sponsorship & relocation support are mandatory.
    """
    text = (title + " " + description).lower()
    title_lower = title.lower()
    loc_lower = location.lower()

    if any(flag in text for flag in PROFILE["junior_red_flags"]):
        return 0, "Filtered: junior/entry-level role detected"

    # Reject roles whose titles match red-flag career tracks
    for red_flag in PROFILE["title_red_flags"]:
        if red_flag in title_lower:
            return 0, f"Filtered: title matches non-relevant track ({red_flag})"

    # --- Seniority filter: reject roles too senior for candidate's experience ---
    exp_years = PROFILE["years_experience"]
    senior_patterns = [
        (["vice president", "vp ", " vp,", "vp of", "rvp ", "svp ", "evp ", "chief ", "cfo", "cto", "ceo",
          "head of"], 12),
        (["director", "senior director", "managing director", "associate director"], 8),
        (["principal", "staff", "senior manager"], 5),
        (["senior ", "lead ", "manager ", "head "], 3),
    ]
    for patterns, min_exp in senior_patterns:
        if exp_years < min_exp:
            for pat in patterns:
                if pat in title_lower:
                    return 0, f"Filtered: too senior ({pat}) for {exp_years}yr profile"

    # --- Experience range filter: match JD's explicit experience requirements ---
    max_allowed = exp_years + 3
    min_allowed = max(0, exp_years - 1)
    exp_patterns = [
        (r'(\d+)\+?\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)', 'min'),
        (r'(?:min|minimum|at least|≥)\s*(\d+)\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)', 'min'),
        (r'(?:max|maximum|up to|≤)\s*(\d+)\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)', 'max'),
        (r'(\d+)\s*(?:to|-|–)\s*(\d+)\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)', 'range'),
        (r'(\d+)\s*-\s*(\d+)\s*(?:yrs?|years?)', 'range'),
    ]
    for pattern, ptype in exp_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            if ptype == 'min':
                req = int(m)
                if req > max_allowed:
                    return 0, f"Filtered: requires {req}+yr, candidate max {max_allowed}"
            elif ptype == 'max':
                req = int(m)
                if req < min_allowed:
                    return 0, f"Filtered: max {req}yr, candidate min {min_allowed}"
            elif ptype == 'range':
                lo, hi = int(m[0]), int(m[1])
                if lo > max_allowed or hi < min_allowed:
                    return 0, f"Filtered: requires {lo}-{hi}yr, candidate range {min_allowed}-{max_allowed}"

    # --- For roles outside India / Remote: require visa & relocation support ---
    is_outside_india = "india" not in loc_lower and "india" not in text
    is_remote = "remote" in loc_lower or "remote" in text

    if is_outside_india or is_remote:
        # Check if description mentions visa/relocation keywords
        has_visa_relo = any(kw in text for kw in VISA_RELOCATION_KEYWORDS)
        # Check if company is in the friendly list
        company_lower = company.lower()
        in_friendly_list = any(co in company_lower for co in RELOCATION_FRIENDLY)
        # Check for known blockers
        in_blocked_list = any(co in company_lower for co in NO_RELOCATION_FLAGS)

        if in_blocked_list:
            note = next(NO_RELOCATION_FLAGS[c] for c in NO_RELOCATION_FLAGS if c in company_lower)
            return 0, f"No visa/relocation: {note}"

        if not has_visa_relo and not in_friendly_list:
            return 0, "Filtered: no mention of visa sponsorship or relocation support"

        # Check if role requires a specific non-English language (filter out)
        if any(lang_kw in text for lang_kw in NON_ENGLISH_LANGUAGE_KEYWORDS):
            if "english" not in text:
                return 0, "Filtered: non-English language requirement detected"

    # --- SAP roles: require SAP MM in JD ---
    has_sap_skills = any("sap" in s or "abap" in s for s in PROFILE["core_skills"])
    if has_sap_skills and "sap mm" not in text:
        return 0, "Filtered: SAP role requires SAP MM in JD"

    # --- Skill scoring ---
    skill_hits = sum(1 for skill in PROFILE["core_skills"] if skill in text)
    skill_score = min(skill_hits / 8, 1.0) * 60  # up to 60 points for skill overlap

    seniority_score = 25 if any(k in text for k in PROFILE["seniority_keywords"]) else 10

    # --- Relocation bonus ---
    relocation_bonus = 0
    relocation_note = ""
    company_lower = company.lower()
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
    """
    Compares job description against the candidate's known skills and suggests
    what to highlight or add to the resume.
    """
    text = (title + " " + description).lower()
    resume_skills = set(s.lower() for s in PROFILE["core_skills"])
    suggestions = []

    # Find skills the JD asks for that the candidate already has (should highlight)
    jd_keywords_found = [kw for kw in COMMON_TECH_KEYWORDS if kw in text]
    own_skills_in_jd = [s for s in jd_keywords_found if s in resume_skills]

    if own_skills_in_jd:
        top = own_skills_in_jd[:5]
        suggestions.append(
            f"JD mentions: {', '.join(top)} — ensure these are prominent in your resume summary."
        )

    # Find skills the JD asks for that the candidate DOESN'T have (skill gap)
    missing = [s for s in jd_keywords_found if s not in resume_skills and len(s) > 2]
    if missing:
        suggestions.append(
            f"Skill gap detected: {', '.join(missing[:5])}. Consider noting willingness to learn or relevant adjacent experience."
        )

    if not suggestions:
        suggestions.append("No specific gaps detected — standard tailoring pass recommended before applying.")
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
                    raw_content = posting.get("content", "") or ""
                    jobs.append({
                        "title": posting.get("title", ""),
                        "company": source["name"],
                        "location": posting.get("location", {}).get("name", "Unknown"),
                        "url": posting.get("absolute_url", source["url"]),
                        "description": strip_html(raw_content)[:2000],
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


def search_linkedin(query, location="India", max_results=25):
    """Search LinkedIn Guest API for jobs matching a query."""
    jobs = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    params = {"keywords": query, "location": location, "start": 0}
    try:
        resp = requests.get(
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
            params=params,
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"  [web] LinkedIn HTTP {resp.status_code} for '{query}' in {location}")
            return jobs

        html = resp.text
        # Parse job cards from LinkedIn guest HTML
        # Extract from script tags with JSON or from li/job-card-container elements
        titles = re.findall(r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>\s*([^<]+?)\s*</h3>', html, re.DOTALL)
        companies = re.findall(r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>\s*<a[^>]*>\s*([^<]+?)\s*</a>', html, re.DOTALL)
        locations = re.findall(r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>\s*([^<]+?)\s*</span>', html, re.DOTALL)
        links = re.findall(r'<a[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"', html)

        # Fallback patterns
        if not titles:
            titles = re.findall(r'"title":"([^"]+)"', html)
            companies = re.findall(r'"companyName":"([^"]+)"', html)
            locations = re.findall(r'"formattedLocation":"([^"]+)"', html)
            links = re.findall(r'"jobUrl":"([^"]+)"', html)

        min_len = min(len(titles), len(companies), len(locations))
        for i in range(min(min_len, max_results)):
            url = links[i] if i < len(links) else ""
            # Try to fetch actual job description from the LinkedIn job page
            full_desc = ""
            if url:
                try:
                    jd_resp = requests.get(url, headers=headers, timeout=10)
                    if jd_resp.status_code == 200:
                        jd_html = jd_resp.text
                        # Extract description from LinkedIn job detail page
                        desc_match = re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>', jd_html, re.DOTALL)
                        if desc_match:
                            full_desc = strip_html(desc_match.group(1))[:2000]
                        if not full_desc:
                            desc_match2 = re.search(r'"description":\s*"([^"]+)"', jd_html)
                            if desc_match2:
                                full_desc = desc_match2.group(1)[:2000]
                except Exception:
                    pass
            desc = full_desc or f"LinkedIn job: {titles[i]} at {companies[i]} in {locations[i]}"
            jobs.append({
                "title": titles[i].strip(),
                "company": companies[i].strip(),
                "location": locations[i].strip(),
                "url": url,
                "description": desc,
            })

        if jobs:
            print(f"  [web] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [web] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [web] Error searching '{query}' in {location}: {e}")
    return jobs


def search_indeed(query, location="India", max_results=25):
    """Search Indeed for jobs matching a query using HTML scraping."""
    jobs = []
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    })
    loc_param = location.replace(" ", "+")
    query_param = query.replace(" ", "+")
    url = f"https://www.indeed.com/jobs?q={query_param}&l={loc_param}"
    try:
        resp = scraper.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"  [indeed] Indeed HTTP {resp.status_code} for '{query}'")
            return jobs
        html = resp.text
        titles = re.findall(r'class="jcs-JobTitle[^"]*"[^>]*>\s*<span[^>]*>([^<]+)', html)
        companies = re.findall(r'data-testid="company-name"[^>]*>([^<]+)', html)
        if not companies:
            companies = re.findall(r'[Cc]ompany[Nn]ame[^"]*"[^>]*>\s*([^<]+)', html)
        if not companies:
            companies = re.findall(r'class="[^"]*companyName[^"]*"[^>]*>\s*([^<]+)', html)
        locations = re.findall(r'data-testid="text-location"[^>]*>([^<]+)', html)
        if not locations:
            locations = re.findall(r'class="[^"]*companyLocation[^"]*"[^>]*>\s*([^<]+)', html)
        links = re.findall(r'class="jcs-JobTitle[^"]*"[^>]*href="([^"]+)"', html)
        if not links:
            links = re.findall(r'href="/company/jobs/view/[^"]+"', html)

        min_len = min(len(titles), len(companies), len(locations))
        for i in range(min(min_len, max_results)):
            url = "https://www.indeed.com" + links[i] if i < len(links) and links[i].startswith("/") else (links[i] if i < len(links) else "")
            jobs.append({
                "title": titles[i].strip(),
                "company": companies[i].strip() if i < len(companies) else "Unknown",
                "location": locations[i].strip() if i < len(locations) else location,
                "url": url,
                "description": f"Indeed job: {titles[i]} at {companies[i]} in {locations[i]}",
            })
        if jobs:
            print(f"  [indeed] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [indeed] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [indeed] Error searching '{query}': {e}")
    return jobs


def search_naukri(query, location="India", max_results=25):
    """Search Naukri for jobs matching a query using their API."""
    jobs = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        "appid": "109",
        "clientid": "d3skt0p",
        "systemid": "Naukri",
        "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
        "Referer": "https://www.naukri.com/",
    })
    try:
        session.get("https://www.naukri.com", timeout=15)
        keyword = query.replace(" ", "+")
        api_url = f"https://www.naukri.com/jobapi/v2/search?keyword={keyword}&location={location}"
        session.headers["Referer"] = f"https://www.naukri.com/{keyword.replace('+', '-')}-jobs"
        resp = session.get(api_url, timeout=15)
        if resp.status_code != 200:
            print(f"  [naukri] Naukri HTTP {resp.status_code} for '{query}'")
            return jobs
        data = resp.json()
        listings = data.get("list", [])
        for i, job in enumerate(listings[:max_results]):
            title = job.get("post", "").strip()
            if not title:
                title = job.get("JOB_SPEC", "").strip()
            company = job.get("companyName", "Unknown").strip()
            loc_raw = job.get("cityfield", "")
            loc_clean = re.sub(r'\s{2,}', ', ', loc_raw).strip()
            loc_clean = re.sub(r'\s*\(.*?\)\s*', '', loc_clean)
            loc_clean = ', '.join(dict.fromkeys(loc_clean.split(', ')))
            for tag in ["Metropolitan Cities", "Top", "Popular Locations", "Preferred Jobseeker",
                         "Anywhere in", "South India", "West India", "North India",
                         "Southindia", "westindia", "northindia"]:
                loc_clean = loc_clean.replace(tag, "").strip()
            loc_clean = re.sub(r',\s*,', ',', loc_clean).strip(', ')
            location_str = loc_clean if loc_clean else location
            job_url = job.get("urlStr", "")
            jobs.append({
                "title": title,
                "company": company,
                "location": location_str,
                "url": job_url,
                "description": f"Naukri job: {title} at {company}",
            })
        if jobs:
            print(f"  [naukri] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [naukri] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [naukri] Error searching '{query}': {e}")
    return jobs


def search_instahyre(query, location="India", max_results=25):
    """Search Instahyre for jobs matching a query using their API."""
    jobs = []
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instahyre.com/jobs/",
        "X-Requested-With": "XMLHttpRequest",
    })
    query_param = query.replace(" ", "+")
    api_url = f"https://www.instahyre.com/api/v1/job_search?search={query_param}&location={location}"
    try:
        resp = scraper.get(api_url, timeout=15)
        if resp.status_code != 200:
            print(f"  [instahyre] Instahyre HTTP {resp.status_code} for '{query}'")
            return jobs
        data = resp.json()
        objects = data.get("objects", [])
        query_lower = query.lower()
        query_terms = query_lower.split()
        for obj in objects:
            title = obj.get("candidate_title") or obj.get("title", "").strip()
            company = obj.get("employer", {}).get("company_name", "Unknown").strip()
            loc = obj.get("locations", location).strip()
            keywords = " ".join(obj.get("keywords", []) or []).lower()
            # Client-side filter since API doesn't filter for anonymous users
            text = f"{title.lower()} {company.lower()} {keywords}"
            if not all(term in text for term in query_terms):
                continue
            job_url = obj.get("public_url", "")
            jobs.append({
                "title": title,
                "company": company,
                "location": loc,
                "url": job_url,
                "description": f"Instahyre job: {title} at {company}",
            })
            if len(jobs) >= max_results:
                break
        if jobs:
            print(f"  [instahyre] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [instahyre] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [instahyre] Error searching '{query}': {e}")
    return jobs


def search_womenintech(query, location="UK", max_results=25):
    """Search WomenInTech UK job board."""
    jobs = []
    scraper = cloudscraper.create_scraper()
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"}
    try:
        resp = scraper.get("https://jobs.womenintech.co.uk/jobs", headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  [womenintech] HTTP {resp.status_code} for '{query}'")
            return jobs
        html = resp.text
        links = re.findall(r'href="(/jobs/\d+-[^"]+)"', html)
        seen = set()
        for link in links:
            parts = link.split("/")[-1]
            without_id = re.sub(r'^\d+-', '', parts)
            if "-at-" in without_id:
                title_part, company = without_id.rsplit("-at-", 1)
                title = title_part.replace("-", " ").title()
                company_pretty = company.replace("-", " ").title()
            else:
                title = without_id.replace("-", " ").title()
                company_pretty = "Unknown"
            if title in seen:
                continue
            seen.add(title)
            full_url = f"https://jobs.womenintech.co.uk{link}"
            jobs.append({
                "title": title,
                "company": company_pretty,
                "location": "UK",
                "url": full_url,
                "description": f"WomenInTech UK job: {title} at {company_pretty}",
            })
            if len(jobs) >= max_results:
                break
        if jobs:
            print(f"  [womenintech] {len(jobs)} jobs for '{query}' in UK")
        else:
            print(f"  [womenintech] No jobs parsed")
    except Exception as e:
        print(f"  [womenintech] Error: {e}")
    return jobs


def search_weworkremotely(query, location="Remote", max_results=25):
    """Search We Work Remotely for jobs matching a query."""
    jobs = []
    scraper = cloudscraper.create_scraper()
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    term = query.replace(" ", "+")
    try:
        resp = scraper.get(f"https://weworkremotely.com/remote-jobs/search?term={term}", headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  [weworkremotely] HTTP {resp.status_code}")
            return jobs
        html = resp.text
        titles = re.findall(r'class="title"[^>]*>\s*([^<]+?)\s*</a>', html)
        companies = re.findall(r'class="company"[^>]*>\s*([^<]+)', html)
        links = re.findall(r'href="(/remote-jobs/[^"]+)"', html)
        min_len = min(len(titles), len(companies))
        for i in range(min(min_len, max_results)):
            t = titles[i].strip()
            if t.lower() in ("search remote jobs", "post a job", ""):
                continue
            url = f"https://weworkremotely.com{links[i]}" if i < len(links) else ""
            jobs.append({
                "title": t, "company": companies[i].strip(),
                "location": "Remote", "url": url,
                "description": f"WeWorkRemotely: {t} at {companies[i].strip()}",
            })
        if jobs:
            print(f"  [weworkremotely] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [weworkremotely] Error: {e}")
    return jobs


def search_simplyhired(query, location="India", max_results=25):
    """Search SimplyHired for jobs matching a query."""
    jobs = []
    scraper = cloudscraper.create_scraper()
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    q = query.replace(" ", "+")
    try:
        resp = scraper.get(f"https://www.simplyhired.com/search?q={q}", headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  [simplyhired] HTTP {resp.status_code}")
            return jobs
        html = resp.text
        titles = re.findall(r'<h2[^>]*>\s*<a[^>]*>\s*([^<]+)', html)
        companies = re.findall(r'data-testid="companyName"[^>]*>\s*([^<]+)', html)
        locs = re.findall(r'data-testid="searchSerpJobLocation"[^>]*>\s*([^<]+)', html)
        links = re.findall(r'href="(/job/[^"]+)"', html)
        min_len = min(len(titles), len(companies))
        for i in range(min(min_len, max_results)):
            url = f"https://www.simplyhired.com{links[i]}" if i < len(links) else ""
            l = locs[i].strip() if i < len(locs) else location
            jobs.append({
                "title": titles[i].strip(), "company": companies[i].strip(),
                "location": l, "url": url,
                "description": f"SimplyHired: {titles[i].strip()} at {companies[i].strip()}",
            })
        if jobs:
            print(f"  [simplyhired] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [simplyhired] Error: {e}")
    return jobs


def search_glassdoor(query, location="India", max_results=25):
    """Search Glassdoor for jobs matching a query."""
    jobs = []
    scraper = cloudscraper.create_scraper()
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    loc_map = {"India": "113", "Remote": "0"}
    loc_id = loc_map.get(location, "113")
    query_param = query.replace(" ", "+")
    url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={query_param}&locT=C&locId={loc_id}"
    try:
        resp = scraper.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  [glassdoor] Glassdoor HTTP {resp.status_code} for '{query}'")
            return jobs
        html = resp.text
        titles = re.findall(r'class="[^"]*JobCard_jobTitle[^"]*"[^>]*>\s*([^<]+)', html)
        companies = re.findall(r'class="[^"]*EmployerProfile_compactEmployerName[^"]*"[^>]*>\s*([^<]+)', html)
        if not companies:
            companies = re.findall(r'class="[^"]*EmployerProfile_employerName[^"]*"[^>]*>\s*([^<]+)', html)
        locations = re.findall(r'class="[^"]*JobCard_location[^"]*"[^>]*>\s*([^<]+)', html)
        links = re.findall(r'href="(/partner/jobListing[^"]+)"', html)
        min_len = min(len(titles), len(companies), len(locations))
        for i in range(min(min_len, max_results)):
            url = "https://www.glassdoor.co.in" + links[i] if i < len(links) and links[i].startswith("/") else (links[i] if i < len(links) else "")
            jobs.append({
                "title": titles[i].strip(),
                "company": companies[i].strip() if i < len(companies) else "Unknown",
                "location": locations[i].strip() if i < len(locations) else location,
                "url": url,
                "description": f"Glassdoor job: {titles[i]} at {companies[i]}",
            })
        if jobs:
            print(f"  [glassdoor] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [glassdoor] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [glassdoor] Error searching '{query}': {e}")
    return jobs


def _playwright_scrape(url, selector, extract_fn, wait_selector=None):
    """Generic helper to scrape JS-rendered pages using Playwright."""
    try:
        browser = _get_browser()
        page = browser.new_page()
        page.goto(url, timeout=30000, wait_until="networkidle")
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=10000)
        results = page.eval_on_selector_all(selector, extract_fn)
        page.close()
        return results
    except Exception as e:
        return []


def search_remoteok(query, location="Remote", max_results=25):
    """Search RemoteOK using Playwright headless browser."""
    jobs = []
    term = query.replace(" ", "+").lower()
    url = f"https://remoteok.com/remote-{term}-jobs"
    try:
        titles = _playwright_scrape(
            url,
            "a[href*='/remote-jobs/'] h2, a[href*='/remote-jobs/'] span[itemprop='title']",
            "els => els.map(e => e.innerText.trim()).filter(t => t.length > 3)"
        )
        companies = _playwright_scrape(
            url,
            "span[itemprop='name'], div.company",
            "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)"
        )
        links = _playwright_scrape(
            url,
            "a[href*='/remote-jobs/']",
            "els => els.map(e => e.href).filter(h => h.includes('/remote-jobs/'))"
        )
        min_len = min(len(titles), len(companies), len(links))
        for i in range(min(min_len, max_results)):
            jobs.append({
                "title": titles[i], "company": companies[i] if i < len(companies) else "Unknown",
                "location": "Remote", "url": links[i],
                "description": f"RemoteOK: {titles[i]}",
            })
        if jobs:
            print(f"  [remoteok] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [remoteok] Error: {e}")
    return jobs


def search_workatstartup(query, location="Remote", max_results=25):
    """Search WorkAtAStartup (YC) using Playwright with profile-based filters."""
    jobs = []
    exp = PROFILE["years_experience"]
    min_exp = max(0, exp - 1)
    top_skills = PROFILE["core_skills"][:3]
    is_sap = any("sap" in s.lower() for s in top_skills)
    role = "swe" if is_sap else "eng"
    role_type = "be"  # backend
    url = (
        f"https://www.workatastartup.com/companies?"
        f"demographic=any&hasEquity=any&hasSalary=any&industry=any"
        f"&interviewProcess=any&jobType=fulltime&layout=list-compact"
        f"&role={role}&role_type={role_type}&sortBy=created_desc"
        f"&tab=any&usVisaNotRequired=any&minExperience={min_exp}"
    )
    try:
        titles = _playwright_scrape(
            url,
            "a[href*='/companies/'] div.font-bold, a[href*='/companies/'] h3",
            "els => els.map(e => e.innerText.trim()).filter(t => t.length > 3)"
        )
        links = _playwright_scrape(
            url,
            "a[href*='/companies/']",
            "els => els.map(e => e.href).filter(h => h.includes('/companies/'))"
        )
        for i in range(min(len(titles), max_results)):
            jobs.append({
                "title": titles[i],
                "company": "YC Startup",
                "location": "Remote/US",
                "url": links[i] if i < len(links) else url,
                "description": f"WorkAtAStartup: {titles[i]}",
            })
        if jobs:
            print(f"  [workatstartup] {len(jobs)} jobs")
    except Exception as e:
        print(f"  [workatstartup] Error: {e}")
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
          <p style="margin:0 0 8px;color:#666;font-size:13px;">
            <a href="{m['url']}" style="color:#1a73e8;text-decoration:none;">{m['company']}</a>
            &middot; {m['location']}
          </p>
          <p style="margin:0 0 8px;font-size:14px;"><b>Fit score: {m['score']}%</b></p>
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
    recipient = os.environ.get("EMAIL_TO") or gmail_address

    if not gmail_address or not gmail_app_password:
        print("Email not sent - GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set.")
        print("See setup notes in README for how to create a Gmail App Password.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, recipient, msg.as_string())
        print(f"Email sent to {recipient}")
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
# 5. RESUME PARSER (auto-detect profile from any PDF)
# ---------------------------------------------------------------------------

# Broad tech skills vocabulary used for auto-detection from any resume
# Covers backend, frontend, cloud, DevOps, ERP/SAP, data, and more.
COMMON_TECH_KEYWORDS = [
    # Languages
    "java", "python", "javascript", "typescript", "golang", "go", "rust", "c++", "c#",
    "ruby", "php", "swift", "kotlin", "scala", "perl", "r",
    "node.js", "nodejs", "react", "angular", "vue.js", "vue", "svelte",
    # Backend frameworks
    "spring", "spring boot", "django", "flask", "express", "rails", "asp.net",
    ".net", "fastapi", "laravel",
    # Cloud & infra
    "aws", "azure", "gcp", "cloud", "docker", "kubernetes", "k8s", "terraform",
    "microservices", "distributed systems", "system design", "architecture",
    "kafka", "rabbitmq", "redis", "mysql", "postgresql", "mongodb", "cassandra",
    "elasticsearch", "rest api", "graphql", "grpc", "soap",
    "ci/cd", "jenkins", "github actions", "gitlab ci", "devops", "ansible",
    "puppet", "chef", "helm", "istio",
    # Data & ML
    "machine learning", "deep learning", "ai", "nlp", "tensorflow", "pytorch",
    "pandas", "numpy", "spark", "hadoop", "airflow",
    # Project management
    "agile", "scrum", "leadership", "mentoring", "jira", "confluence",
    # General tech
    "sql", "nosql", "database", "api", "backend", "frontend", "full stack",
    "linux", "unix", "bash", "shell", "git", "github", "gitlab",
    # SAP / ERP
    "sap", "abap", "sap s/4hana", "sap fico", "sap mm", "sap sd", "sap hana",
    "sap basis", "sap bw", "sap pi", "sap po", "sap successfactors",
    "fico", "fi module", "controlling", "cost center accounting",
    "procurement", "inventory management", "material management",
    "sap implementation", "sap support", "idoc", "bapi", "rfc",
    "oracle", "oracle erp", "oracle fusion", "peoplesoft",
    "salesforce", "microsoft dynamics", "erp",
]

def extract_text_from_pdf(path):
    """Extract all text from a PDF file using PyPDF2."""
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

def parse_resume_pdf(path):
    """
    Given a PDF resume path, extract name, email, skills, and experience.
    Returns a dict suitable for PROFILE overrides.
    """
    raw = extract_text_from_pdf(path)
    lines = raw.split("\n")
    non_empty = [l.strip() for l in lines if l.strip()]

    profile = {"name": "", "email": "", "core_skills": [], "years_experience": 0}

    # --- Extract name (first non-title line is the name) ---
    # Skip lines that look like job titles (contain common role keywords)
    title_keywords = ["engineer", "developer", "consultant", "architect", "manager",
                      "analyst", "specialist", "lead", "scientist"]
    for line in non_empty:
        cleaned = line.strip("|").strip().replace(" ", "")
        # Skip if it looks like a job title (common role keyword + no spaces or short)
        is_title = any(kw in cleaned.lower() for kw in title_keywords)
        if not is_title and len(cleaned) > 2:
            profile["name"] = cleaned
            break

    # --- Extract email ---
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", raw)
    if email_match:
        profile["email"] = email_match.group(0)

    # --- Extract skills ---
    # Look for lines near "SKILLS" / "TECHNICAL SKILLS" / "TECHNOLOGIES" section
    skill_section_text = ""
    in_skills = False
    for line in lines:
        stripped = line.strip().lower()
        if any(kw in stripped for kw in ["technical skills", "technologies", "tech stack",
                                           "skills &", "skills:", "core competencies",
                                           "programming languages", "tools &"]):
            in_skills = True
            continue
        if in_skills:
            if any(kw in stripped for kw in ["experience", "education", "projects",
                                              "certifications", "publications"]):
                if len(skill_section_text) > 50:
                    break
            skill_section_text += line + " "

    # If no skills section found, search whole document for tech keywords
    if not skill_section_text:
        skill_section_text = raw

    # Match against known tech keywords
    found_skills = set()
    text_lower = skill_section_text.lower()
    for kw in COMMON_TECH_KEYWORDS:
        if kw in text_lower:
            found_skills.add(kw)
    profile["core_skills"] = sorted(found_skills)

    # --- Extract years of experience ---
    # Patterns: "10+ years", "10 years", "1 Year 10 Months", "5 yrs exp"
    raw_lower = raw.lower()
    # First try "X Year(s) Y Month(s)" format (with or without spaces between)
    year_month = re.findall(r"(\d+)\s*years?\s*(\d+)\s*months?", raw_lower)
    if not year_month:
        year_month = re.findall(r"(\d+)year\s*(\d+)months?", raw_lower)
    if year_month:
        profile["years_experience"] = max(int(y) + round(int(m) / 12) for y, m in year_month)
    else:
        # Simple "X+ years", "X years ..." patterns
        exp_matches = re.findall(r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+of\s+experience|\s+exp|\s+owning|\s+in|\s+working|\s+of)?", raw_lower)
        exp_matches = [int(e) for e in exp_matches if 3 <= int(e) <= 45]
        if exp_matches:
            profile["years_experience"] = max(exp_matches)
        else:
            # Fallback: compute from earliest → latest year in the document
            dates = re.findall(r"\b(?:19|20)\d{2}\b", raw)
            if dates:
                dates = sorted(int(d) for d in dates)
                span = max(dates) - min(dates) + 1
                profile["years_experience"] = max(span, 1)

    print(f"  Parsed resume: {profile['name']}, {profile['email'] or 'no email'}, "
          f"{profile['years_experience']}yr, {len(profile['core_skills'])} skills")
    return profile


# ---------------------------------------------------------------------------
# 6. JOB TRACKER - persistent status tracking + email rejection detection
# ---------------------------------------------------------------------------

TRACKER_FILE = "job_tracker.json"

class JobTracker:
    """Tracks job application status to avoid re-recommending applied/rejected jobs."""

    def __init__(self, path=TRACKER_FILE):
        self.path = path
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"jobs": {}}

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def job_key(self, title, company):
        return f"{company.lower()}|{title.lower()}"

    def is_known(self, title, company):
        key = self.job_key(title, company)
        entry = self.data["jobs"].get(key)
        return entry and entry.get("status") in ("applied", "rejected", "offer")

    def get_status(self, title, company):
        key = self.job_key(title, company)
        entry = self.data["jobs"].get(key, {})
        return entry.get("status", "new")

    def add_job(self, title, company, url="", score=0, status="new"):
        key = self.job_key(title, company)
        if key not in self.data["jobs"]:
            self.data["jobs"][key] = {
                "title": title, "company": company, "url": url,
                "score": score, "status": status,
                "date_found": datetime.now().isoformat(),
                "date_updated": datetime.now().isoformat(),
            }
            self._save()

    def update_status(self, title, company, status, notes=""):
        key = self.job_key(title, company)
        if key in self.data["jobs"]:
            self.data["jobs"][key]["status"] = status
            self.data["jobs"][key]["date_updated"] = datetime.now().isoformat()
            if notes:
                self.data["jobs"][key]["notes"] = notes
            self._save()
            return True
        return False

    def scan_email_for_rejections(self, gmail_user, gmail_pass, days_back=7):
        """
        Scan Gmail inbox for rejection emails and update tracker status.
        Returns list of newly detected rejections.
        """
        rejections = []
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(gmail_user, gmail_pass)
            mail.select("inbox")

            since_date = (datetime.now().isoformat()[:10].replace("-", "-"))
            search_criteria = f'(SINCE {since_date})'

            rejection_keywords = [
                "unfortunately", "not moving forward", "position has been filled",
                "regret to inform", "not selected", "decided to move forward with other candidates",
                "we will not be moving forward", "application status", "update on your application",
                "your application at", "thank you for your interest",
            ]

            result, data = mail.search(None, search_criteria)
            if result != "OK":
                return rejections

            for num in data[0].split():
                try:
                    result, msg_data = mail.fetch(num, "(RFC822)")
                    if result != "OK":
                        continue
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    subject = msg["subject"] or ""
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True) or b""
                                body = body.decode("utf-8", errors="ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True) or b""
                        body = body.decode("utf-8", errors="ignore")

                    full_text = (subject + " " + body).lower()
                    is_rejection = any(kw in full_text for kw in rejection_keywords)

                    if is_rejection:
                        # Try to identify which company
                        for key, entry in self.data["jobs"].items():
                            if entry.get("status") != "applied":
                                continue
                            company = entry["company"].lower()
                            if company in full_text and len(company) > 3:
                                self.update_status(entry["title"], entry["company"], "rejected",
                                                   notes=f"Auto-detected from email: {subject[:80]}")
                                rejections.append((entry["title"], entry["company"], subject))
                                break
                except Exception:
                    continue

            mail.logout()
        except Exception as e:
            print(f"  [tracker] Email scan error: {e}")
        return rejections


# ---------------------------------------------------------------------------
# 7. MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Daily Job Scanner")
    parser.add_argument("--name", help="Your name (overrides PROFILE)")
    parser.add_argument("--skills", help="Comma-separated core skills (overrides PROFILE)")
    parser.add_argument("--exp", type=int, help="Years of experience (overrides PROFILE)")
    parser.add_argument("--resume", help="Path to resume PDF - auto-extracts profile")
    parser.add_argument("--email-to", help="Email recipient (overrides .env EMAIL_TO)")
    parser.add_argument("--gmail-user", help="Gmail address (overrides .env GMAIL_ADDRESS)")
    parser.add_argument("--gmail-pass", help="Gmail App Password (overrides .env)")
    parser.add_argument("--threshold", type=int, default=60, help="Match score threshold (default: 60)")
    parser.add_argument("--save", default="last_scan_results.json", help="Output JSON path")
    args = parser.parse_args()

    # --- If --resume is provided, auto-build profile from PDF ---
    if args.resume:
        if not os.path.exists(args.resume):
            print(f"Error: resume not found at {args.resume}")
            sys.exit(1)
        print(f"Loading resume: {args.resume}")
        parsed = parse_resume_pdf(args.resume)
        PROFILE["name"] = parsed["name"] or args.name or PROFILE["name"]
        if parsed["core_skills"]:
            PROFILE["core_skills"] = parsed["core_skills"]
        if parsed["years_experience"]:
            PROFILE["years_experience"] = parsed["years_experience"]
        os.environ["RESUME_PATH"] = args.resume
        # Auto-set recipient email from resume (sender stays as .env GMAIL_ADDRESS)
        if parsed["email"] and not args.email_to:
            os.environ["EMAIL_TO"] = parsed["email"]
            print(f"  Auto-detected email: {parsed['email']}")

    # Override PROFILE from CLI args (takes priority over resume parse)
    if args.name:
        PROFILE["name"] = args.name
    if args.skills:
        PROFILE["core_skills"] = [s.strip() for s in args.skills.split(",")]
    if args.exp is not None:
        PROFILE["years_experience"] = args.exp

    # Override .env from CLI args
    if args.resume and not args.resume.startswith("---"):  # already handled above
        pass
    if args.email_to:
        os.environ["EMAIL_TO"] = args.email_to
        os.environ["GMAIL_ADDRESS"] = args.email_to
    if args.gmail_user:
        os.environ["GMAIL_ADDRESS"] = args.gmail_user
    if args.gmail_pass:
        os.environ["GMAIL_APP_PASSWORD"] = args.gmail_pass

    print(f"=== Daily job scan started: {datetime.now().isoformat()} ===")
    print(f"Profile: {PROFILE['name']}, {PROFILE['years_experience']}yr, {len(PROFILE['core_skills'])} skills")
    all_matches = []

    # --- Load job tracker ---
    tracker = JobTracker()
    print(f"  [tracker] {len(tracker.data['jobs'])} tracked jobs loaded")
    # Run email rejection scanner
    gmail_user = os.environ.get("GMAIL_ADDRESS", "")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    if gmail_user and gmail_pass:
        rejections = tracker.scan_email_for_rejections(gmail_user, gmail_pass)
        if rejections:
            print(f"  [tracker] Auto-detected {len(rejections)} rejections from email")
            for t, c, s in rejections:
                print(f"    {t} @ {c} - {s[:50]}")

    # Helper to check tracker before adding a match
    def should_include(job):
        return not tracker.is_known(job["title"], job["company"])

    for source in JOB_SOURCES:
        print(f"Scanning: {source['name']} ({source['region']})")
        jobs = fetch_jobs_from_source(source)
        for job in jobs:
            if not should_include(job):
                continue
            score, relocation_note = score_job(job["title"], job["description"], job["company"])
            if score >= args.threshold:
                resume = pick_resume(job["company"])
                suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                all_matches.append({
                    **job,
                    "score": score,
                    "resume": resume,
                    "relocation_note": relocation_note,
                    "suggestions": suggestions,
                })

    # --- Web search: LinkedIn, Indeed, Naukri, Instahyre ---
    board_scrapers = [
        ("LinkedIn", search_linkedin),
        ("Indeed", search_indeed),
        ("Naukri", search_naukri),
        ("Glassdoor", search_glassdoor),
        ("SimplyHired", search_simplyhired),
        ("WeWorkRemotely", search_weworkremotely),
        ("WomenInTech", search_womenintech),
        ("Instahyre", search_instahyre),
    ]
    top_skills = PROFILE["core_skills"][:5]
    is_sap_profile = any("sap" in s.lower() or "erp" in s.lower() for s in top_skills)
    domain_queries = ["SAP FICO", "SAP MM", "SAP consultant", "SAP S/4HANA"] if is_sap_profile \
        else ["+".join(top_skills[:3]), "backend engineer", "software engineer", "staff engineer", "platform engineer"]
    for query in domain_queries:
        for board_name, board_fn in board_scrapers:
            for region in (["India"] if board_name in ("Naukri", "Instahyre") else ["India", "Remote"]):
                jobs = board_fn(query, location=region)
                for job in jobs:
                    if not should_include(job):
                        continue
                    score, relocation_note = score_job(job["title"], job["description"], job["company"])
                    if score >= args.threshold:
                        resume = pick_resume(job["company"])
                        suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                        all_matches.append({**job, "score": score, "resume": resume,
                                            "relocation_note": relocation_note, "suggestions": suggestions})

    # --- Playwright-based scrapers (JS-rendered sites, called once not per query) ---
    is_sap_profile = any("sap" in s.lower() or "erp" in s.lower() for s in PROFILE["core_skills"][:5])
    exp = PROFILE["years_experience"]
    if is_sap_profile:
        pw_scrapers = [("RemoteOK", search_remoteok, None)]
    else:
        pw_scrapers = [
            ("RemoteOK", search_remoteok, None),
            ("WorkAtAStartup", search_workatstartup, None),
        ]
    for pw_name, pw_fn, pw_query in pw_scrapers:
        try:
            jobs = pw_fn(pw_query or "", location="Remote")
            for job in jobs:
                if not should_include(job):
                    continue
                score, relocation_note = score_job(job["title"], job["description"], job["company"])
                if score >= args.threshold:
                    resume = pick_resume(job["company"])
                    suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                    all_matches.append({**job, "score": score, "resume": resume,
                                        "relocation_note": relocation_note, "suggestions": suggestions})
        except Exception as e:
            print(f"  [{pw_name.lower()}] Error: {e}")

    all_matches.sort(key=lambda m: m["score"], reverse=True)

    # --- Save new matches to tracker ---
    for m in all_matches:
        tracker.add_job(m["title"], m["company"], m.get("url", ""), m["score"])

    print(f"Found {len(all_matches)} matches above {args.threshold}% threshold.")
    print(f"  [tracker] {len(tracker.data['jobs'])} total jobs tracked")

    html = build_email_html(all_matches)
    send_email(html, subject=f"Daily Job Matches - {len(all_matches)} new roles")

    # WhatsApp disabled per user request - all results go via email only
    # if all_matches:
    #     top3 = all_matches[:3]
    #     whatsapp_msg = "Top job matches:\n"
    #     for m in top3:
    #         whatsapp_msg += f"- {m['title']} at {m['company']} ({m['score']}%)\n"
    #     whatsapp_msg += "Check your email for full details."
    #     send_whatsapp(whatsapp_msg)

    with open("last_scan_results.json", "w") as f:
        json.dump(all_matches, f, indent=2)

    print("=== Scan complete ===")


if __name__ == "__main__":
    main()
