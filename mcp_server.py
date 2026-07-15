"""
MCP Server for Job Search Agent
================================
Provides interactive job search, scoring, tracking, and resume parsing
via the Model Context Protocol (MCP).

Run with:   python mcp_server.py
Or connect from any MCP host (Claude Desktop, Cursor, etc.)
"""

import sys
import os
import json
import re
import smtplib
import shutil
from glob import glob
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Load environment
from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Imports from the existing codebase
# ---------------------------------------------------------------------------
from daily_scan import (
    PROFILE,
    JOB_SOURCES,
    VISA_RELOCATION_KEYWORDS,
    RELOCATION_FRIENDLY,
    NO_RELOCATION_FLAGS,
    RESUME_VERSIONS,
    COMPANY_RESUME_MAP,
    ROLE_DOMAINS,
    UNIVERSAL_RED_FLAGS,
    JobTracker,
    score_job,
    pick_resume,
    company_url,
    tailoring_suggestion,
    fetch_jobs_from_source,
    search_linkedin,
    search_indeed,
    search_naukri,
    search_instahyre,
    search_glassdoor,
    search_simplyhired,
    search_weworkremotely,
    search_womenintech,
    search_remoteok,
    search_remotive,

    search_foundit,
    search_timesjobs,
    search_arcdev,
    search_arbeitnow,
    search_seek,
    search_jora,
    search_xing,
    search_jobsch,
    search_jobsingermany,
    search_skipthedrive,
    search_stepstone,
    search_monsterde,
    search_workingnomads,
    search_jobspresso,
    search_englishjobsearch,
    search_bulldogjob,
    search_workatstartup,
    search_visasponsor,
    search_incluso,
    search_adzuna,
    search_reed,
    search_jobsite,
    search_intermediair,
    search_nationalevacaturebank,
    parse_resume_pdf,
    auto_detect_title_red_flags,
    sync_tracker_to_gsheet,
    get_salary_info,
    build_domain_queries,
    build_email_html,
    send_email,
    _format_salary,
    _rebuild_precompiled_patterns,
)
from eu_companies import EU_JOB_SOURCES
from global_companies import GLOBAL_JOB_SOURCES
from apac_companies import APAC_JOB_SOURCES
from us_canada_companies import US_CANADA_JOB_SOURCES
from middle_east_companies import MIDDLE_EAST_JOB_SOURCES
from remote_companies import REMOTE_JOB_SOURCES

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = Server("job-search-agent")

# ---------------------------------------------------------------------------
# Exception tracking & notification
# ---------------------------------------------------------------------------
_EXCEPTION_NOTIFY_EMAIL = "kamneemaran45@gmail.com"
_skipped_sources: list[dict] = []  # Collects exceptions during a search run


def _send_exception_email(skipped: list[dict], batch_label: str = "MCP Search"):
    """Send an email with details of skipped sources/boards due to exceptions."""
    if not skipped:
        return
    gmail_address = os.environ.get("GMAIL_ADDRESS") or "kminterviewer@gmail.com"
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_app_password:
        print("Exception email not sent - GMAIL_APP_PASSWORD not set.")
        return

    rows = []
    for entry in skipped:
        rows.append(f"""
        <tr>
            <td style="padding:6px;border:1px solid #ddd;">{entry.get('source', 'N/A')}</td>
            <td style="padding:6px;border:1px solid #ddd;">{entry.get('url', 'N/A')}</td>
            <td style="padding:6px;border:1px solid #ddd;">{entry.get('resume', 'N/A')}</td>
            <td style="padding:6px;border:1px solid #ddd;color:red;">{entry.get('error', 'Unknown')}</td>
        </tr>""")

    html = f"""
    <html><body>
    <h2>⚠️ Skipped Sources During: {batch_label}</h2>
    <p>{len(skipped)} source(s) were skipped due to exceptions at {datetime.now().strftime('%Y-%m-%d %H:%M')}.</p>
    <table style="border-collapse:collapse;width:100%;font-family:monospace;font-size:13px;">
        <tr style="background:#f44336;color:white;">
            <th style="padding:8px;border:1px solid #ddd;">Source / Board</th>
            <th style="padding:8px;border:1px solid #ddd;">URL / Link</th>
            <th style="padding:8px;border:1px solid #ddd;">Resume / Profile</th>
            <th style="padding:8px;border:1px solid #ddd;">Exception</th>
        </tr>
        {''.join(rows)}
    </table>
    <p style="color:#666;font-size:12px;">Automated alert from Job Search Agent MCP Server.</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Job Agent] {len(skipped)} source(s) skipped — {batch_label}"
    msg["From"] = gmail_address
    msg["To"] = _EXCEPTION_NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(gmail_address, gmail_app_password)
            srv.sendmail(gmail_address, _EXCEPTION_NOTIFY_EMAIL, msg.as_string())
        print(f"Exception notification sent to {_EXCEPTION_NOTIFY_EMAIL}")
    except Exception as e:
        print(f"Failed to send exception email: {e}")

tracker = JobTracker()

# Cache for company career page visa checks: {company_lower: True/False/None}
_visa_cache: dict[str, bool | None] = {}
# Fill cache from known RELOCATION_FRIENDLY / NO_RELOCATION_FLAGS
for co in RELOCATION_FRIENDLY:
    _visa_cache[co.lower()] = True
for co in NO_RELOCATION_FLAGS:
    _visa_cache[co.lower()] = False

def _check_career_page_visa(company: str, career_url: str | None = None) -> bool | None:
    """Check if a company's career page mentions visa/relocation support.
    Returns True/False, or None if unable to determine."""
    co_key = company.lower().strip()
    if co_key in _visa_cache:
        return _visa_cache[co_key]

    # Try to find a career page URL
    urls_to_try = []
    if career_url:
        urls_to_try.append(career_url)
    # Try known career page patterns
    slug = re.sub(r'[^a-zA-Z0-9]', '', company.lower().replace(' ', ''))
    for pattern in [
        f"https://{slug}.com/careers",
        f"https://www.{slug}.com/careers",
        f"https://careers.{slug}.com",
        f"https://{slug}.com/jobs",
        f"https://www.{slug}.com/jobs",
    ]:
        urls_to_try.append(pattern)

    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    visa_kw = ["visa sponsorship", "work visa", "sponsorship", "relocation support",
               "relocation assistance", "work authorization", "immigration support",
               "visa provided", "we sponsor", "global mobility"]

    for url in urls_to_try[:3]:  # Limit to 3 URLs to avoid long blocking
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                text = resp.text.lower()
                if any(kw in text for kw in visa_kw):
                    _visa_cache[co_key] = True
                    return True
        except Exception:
            continue

    _visa_cache[co_key] = None
    return None

# Schedule file for email digest preferences
DIGEST_SCHEDULE_FILE = "digest_schedule.json"


def _load_digest_schedule() -> dict:
    try:
        with open(DIGEST_SCHEDULE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"schedule": "never", "email": "", "last_sent": "", "scheduled_date": ""}


def _save_digest_schedule(data: dict):
    with open(DIGEST_SCHEDULE_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="about",
            description="Learn what this job search engine does, how it works, and where it gets jobs",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Optional: 'sources', 'scoring', 'how-it-works', or leave empty for overview",
                    }
                },
            },
        ),
        types.Tool(
            name="search_jobs",
            description="Search for jobs across company ATS APIs + 15+ job boards. Automatically expands to relevant title variants (senior/staff/principal + domain). Set preferences (threshold, exclusions, focus) each time, or leave blank for defaults. Use 'update_tracker' afterwards to track jobs — they'll be organized by resume in separate Google Sheet tabs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query e.g. 'backend engineer', 'senior java developer'",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location filter (default: 'Remote')",
                        "default": "Remote",
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Minimum match score 0-100 (default: 65). Only jobs scoring above this are returned.",
                        "default": 65,
                    },
                    "exclude_companies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: company names to exclude, e.g. ['mollie', 'acme corp']",
                    },
                     "require_visa": {
                        "type": "boolean",
                        "description": "Optional: require visa sponsorship/relocation support (default: false). When true, jobs outside India without explicit visa/relocation signals in the JD, known-sponsor lists, or career page are filtered out (score=0). Set to false for exploratory searches — this injects synthetic visa keywords so all jobs score without the visa penalty, but does NOT guarantee the company actually sponsors.",
                        "default": False,
                    },
                    "focus_role": {
                        "type": "string",
                        "description": "Optional: role keywords to prioritize, e.g. 'senior staff backend'",
                    },
                    "max_results": {
                        "type": "number",
                        "description": "Max results per source (default: 10)",
                        "default": 10,
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: specific sources to search e.g. ['linkedin', 'greenhouse', 'indeed']. Leave empty for all.",
                    },
                    "locations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Multi-select locations (OR logic). Only jobs matching ANY of these locations pass. Overrides 'location' if provided. Example: ['Remote', 'Amsterdam', 'Berlin']",
                    },
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional skills to filter by (OR logic). Only jobs whose title or description mentions ANY of these skills pass, in addition to profile-based scoring. Example: ['rust', 'react', 'typescript']",
                    },
                    "job_type": {
                        "type": "string",
                        "enum": ["", "full-time", "contract"],
                        "description": "Employment type filter: 'full-time', 'contract', or empty string for both",
                        "default": "",
                    },
                    "work_mode": {
                        "type": "string",
                        "enum": ["", "remote", "on-site", "hybrid"],
                        "description": "Work mode filter: 'remote', 'on-site', 'hybrid', or empty string for all",
                        "default": "",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="score_job",
            description="Score any job title + description against your resume profile (0-100). Shows why it scored that way.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Job title"},
                    "description": {"type": "string", "description": "Job description text"},
                    "company": {"type": "string", "description": "Company name"},
                    "location": {
                        "type": "string",
                        "description": "Job location (default: 'Remote')",
                        "default": "Remote",
                    },
                },
                "required": ["title", "description", "company"],
            },
        ),
        types.Tool(
            name="tracker_status",
            description="View all tracked jobs, their statuses (new/applied/rejected/offer), and recent updates",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: 'new', 'applied', 'rejected', 'offer', or empty for all",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Max results (default: 20)",
                        "default": 20,
                    },
                },
            },
        ),
        types.Tool(
            name="update_tracker",
            description="Update the status of a tracked job (e.g. mark as applied, rejected, offer). Jobs are organized by resume version in Google Sheets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Job title"},
                    "company": {"type": "string", "description": "Company name"},
                    "status": {
                        "type": "string",
                        "description": "New status: 'applied', 'rejected', 'offer'",
                        "enum": ["applied", "rejected", "offer"],
                    },
                    "notes": {"type": "string", "description": "Optional notes"},
                    "resume": {"type": "string", "description": "Optional resume version used (e.g. 'Kamnee_Maran_Resume_FAANG.pdf'). Creates a separate sheet tab per resume."},
                },
                "required": ["title", "company", "status"],
            },
        ),
        types.Tool(
            name="parse_resume",
            description="Extract name, email, current role, skills, and experience from a PDF resume. Auto-configures title filters. Optionally register the resume as a new version with a key name (e.g. 'faang', 'general', 'startup').",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the PDF resume file",
                    },
                    "key": {
                        "type": "string",
                        "description": "Optional: version name to register this resume as (e.g. 'faang', 'general', 'startup'). Overwrites if key already exists.",
                    },
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="get_profile",
            description="View the current profile configuration: name, experience, core skills, filter settings, and resume versions",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="list_resumes",
            description="List all registered resume versions and discover available PDF files in the project directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "scan": {
                        "type": "boolean",
                        "description": "Scan for unregistered PDF files in the project directory (default: true)",
                        "default": True,
                    },
                },
            },
        ),
        types.Tool(
            name="search_board_jobs",
            description="Search for jobs across job boards (LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter) using JobSpy. Finds jobs from companies not in your personal database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Job search query e.g. 'software engineer', 'backend developer'",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location filter (default: 'Remote')",
                        "default": "Remote",
                    },
                    "site_names": {
                        "type": "string",
                        "description": "Comma-separated job sites (linkedin, indeed, glassdoor, google, zip_recruiter). Default: linkedin,indeed,glassdoor",
                        "default": "linkedin,indeed,glassdoor",
                    },
                    "results_wanted": {
                        "type": "number",
                        "description": "Number of results wanted per site (default: 15)",
                        "default": 15,
                    },
                    "hours_old": {
                        "type": "number",
                        "description": "Only jobs posted within this many hours (default: 168 = 1 week)",
                        "default": 168,
                    },
                    "is_remote": {
                        "type": "boolean",
                        "description": "Remote jobs only (default: true)",
                        "default": True,
                    },
                },
                "required": ["search_term"],
            },
        ),
        types.Tool(
            name="prepare_application",
            description="Prepare application materials for a matched job. Returns profile context, match analysis, skill gaps, and salary info so the LLM can generate a cover letter draft, STAR+R stories, and a gap mitigation plan. Run AFTER scoring a job to get the application materials.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Job title"},
                    "company": {"type": "string", "description": "Company name"},
                    "description": {"type": "string", "description": "Full job description text"},
                    "location": {"type": "string", "description": "Job location (default: 'Remote')", "default": "Remote"},
                    "url": {"type": "string", "description": "Optional URL to the job posting"},
                    "resume": {"type": "string", "description": "Optional resume version override (e.g. 'Kamnee_Maran_Resume_FAANG.pdf')"},
                },
                "required": ["title", "company", "description"],
            },
        ),
        types.Tool(
            name="email_digest",
            description="Trigger or schedule the email digest with your latest job matches. Send immediately ('now'), schedule for tomorrow, or set a recurring schedule (weekly/monthly). Use 'never' to disable.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schedule": {
                        "type": "string",
                        "enum": ["now", "tomorrow", "weekly", "monthly", "never"],
                        "description": "'now' — send immediately | 'tomorrow' — send once tomorrow | 'weekly'/'monthly' — recurring digest | 'never' — disable scheduled digest",
                    },
                    "email": {
                        "type": "string",
                        "description": "Optional: recipient email override (defaults to GMAIL_ADDRESS or EMAIL_TO from env)",
                    },
                },
                "required": ["schedule"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if not arguments:
        arguments = {}

    if name == "about":
        return [types.TextContent(type="text", text=_about(arguments.get("topic", "")))]

    if name == "search_jobs":
        return [types.TextContent(type="text", text=_search_jobs(**arguments))]

    if name == "score_job":
        return [types.TextContent(type="text", text=_score_job(**arguments))]

    if name == "tracker_status":
        return [types.TextContent(type="text", text=_tracker_status(**arguments))]

    if name == "update_tracker":
        return [types.TextContent(type="text", text=_update_tracker(**arguments))]

    if name == "parse_resume":
        return [types.TextContent(type="text", text=_parse_resume(**arguments))]

    if name == "get_profile":
        return [types.TextContent(type="text", text=_get_profile())]

    if name == "list_resumes":
        return [types.TextContent(type="text", text=_list_resumes(**arguments))]

    if name == "search_board_jobs":
        return [types.TextContent(type="text", text=_search_board_jobs(**arguments))]

    if name == "email_digest":
        return [types.TextContent(type="text", text=_email_digest(**arguments))]

    if name == "prepare_application":
        return [types.TextContent(type="text", text=_prepare_application(**arguments))]

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _about(topic: str = "") -> str:
    overview = """## Job Search Agent

A smart job search engine that automatically discovers, scores, and tracks job opportunities tailored to your profile.

### What it does
- Scans 250+ job sources daily for matching roles
- Scores each job against your resume profile (skills, seniority, location, visa support)
- Tracks application statuses (new → applied → rejected → offer)
- Emails a daily digest of top matches
- Syncs results to Google Sheets

### Where it gets jobs

**Company ATS APIs** (direct, no scraping):
- Greenhouse (GitLab, Stripe, Airbnb, Dropbox, Datadog, Coinbase, Reddit, etc.)
- Lever (companies using Lever's hosted postings)
- Ashby (companies using Ashby's job board)
- BambooHR, Workable, Recruitee, Breezy, Personio, Teamtailor, Freshteam, SmartRecruiters

**Job boards** (web scraping):
- LinkedIn, Indeed, Naukri, Instahyre, Glassdoor, SimplyHired
- WeWorkRemotely, WomenInTech UK, SkipTheDrive
- VisaSponsor.Jobs, Incluso

**Remote-focused boards** (Playwright headless browser):
- RemoteOK, WorkingNomads, Jobspresso, EnglishJobSearch.ch, BulldogJob.pl
- WorkAtAStartup (Y Combinator startups)

**Regional company databases:**
- **EU** — 800+ company career pages (Germany, Netherlands, France, Nordics, etc.)
- **Global** — 30+ international companies and recruitment agencies
- **APAC** — Singapore, Japan, Australia, and Southeast Asia companies
- **US/Canada** — North American tech companies
- **Middle East** — UAE, Saudi Arabia, and Gulf region companies

**Recruiter agencies** (manual check reminders):
- Hays, Spring Professional, Michael Page, Randstad, Robert Half, Darwin Recruitment

### How it searches
1. Fetches live jobs from ATS APIs (Greenhouse/Lever/Ashby endpoints, no auth needed)
2. Scrapes job boards using requests + BeautifulSoup or cloudscraper
3. Uses Playwright headless browser for JavaScript-rendered sites
4. Filters out: mobile, frontend, QA, network/SRE roles, and non-relevant tracks
5. Scores each job on skills match + seniority fit + relocation/visa support
6. Deduplicates via a JSON tracker so you never see the same job twice
7. Auto-detects rejections from Gmail inbox

### Key filters (from AGENTS.md)
- **Role exclusions:** mobile (android/ios/swift/kotlin), frontend, QA, network/SRE/devops
- **Track statuses:** new, applied, rejected, offer
- **Data source:** Google Sheet at the configured spreadsheet ID
"""

    details = {
        "sources": """### Job Sources
The engine pulls from 250+ sources across four tiers:

**Tier 1 — ATS APIs (live, structured data)**
Greenhouse, Lever, Ashby, BambooHR, Workable, Recruitee, Breezy, Personio, Teamtailor, Freshteam, SmartRecruiters. These return JSON with title, company, location, description, and posting date. No authentication required.

**Tier 2 — Web scraping (HTML parsing)**
LinkedIn Guest API, Indeed, Naukri, Instahyre, Glassdoor, SimplyHired, WeWorkRemotely, WomenInTech UK. Uses requests + cloudscraper to bypass basic anti-bot measures.

**Tier 3 — Headless browser (JavaScript-rendered)**
RemoteOK, WorkingNomads, Jobspresso, EnglishJobSearch, BulldogJob, WorkAtAStartup. Uses Playwright to render JS-heavy pages.

**Tier 4 — Regional company databases**
- EU: 800+ company career pages across Germany, Netherlands, France, Nordics, Spain, Italy, and more
- Global: 30+ international companies and recruitment agencies
- APAC: Singapore, Japan, Australia, India, and Southeast Asia
- US/Canada: North American tech companies
- Middle East: UAE, Saudi Arabia, Qatar, and Gulf region

**Specialized boards**: VisaSponsor.Jobs (visa-sponsored roles), Incluso (diversity-focused)

**Manual check reminders** — Companies without public APIs (like Booking.com, Picnic) print reminders to check manually.""",
        "scoring": """### How scoring works (0-100)

1. **Red flag check** (immediate reject) — junior roles, non-relevant titles (mobile/frontend/QA/etc.), roles requiring travel
2. **Seniority filter** — rejects roles too senior for your experience (VP at 10yr, Director at 8yr, Principal at 5yr, Senior at 3yr)
3. **Experience range** — matches JD's explicit experience requirements against your profile
4. **Visa/relocation check** — for roles outside India, requires visa sponsorship or relocation support keywords
5. **Language filter** — rejects roles requiring non-English fluency
6. **Skill scoring** — up to 60 points based on keyword overlap with your core skills
7. **Seniority bonus** — 25pt if title matches seniority keywords, 10pt otherwise
8. **Relocation bonus** — 15pt if company is known relocation-friendly""",
        "how-it-works": """### How it works end-to-end

1. **Configuration** — your skills, experience, target regions, and red flags are in `PROFILE` in `daily_scan.py`
2. **Scheduled scan** — runs daily via cron/GitHub Actions (or manually with `python daily_scan.py`)
3. **Fetch** — iterates all configured job sources, fetches live postings
4. **Score** — each job is scored 0-100; only jobs above threshold (default 70) proceed
5. **Track** — new matches are saved to `job_tracker.json` with status "new"
6. **Email** — a daily HTML digest is sent with match details, scores, and resume tailoring tips
7. **Sheets** — results sync to Google Sheets
8. **Gmail scan** — auto-detects rejection emails and marks jobs "rejected"

You're now talking to the interactive MCP interface, which lets you search, score, and track jobs on demand.""",
    }

    if topic in details:
        return overview + "\n\n" + details[topic]
    return overview


# Keywords for job type and work mode filtering
_CONTRACT_KW = ["contract", "freelance", "temporary", "temp ", "fixed-term", "consultant", "12-month", "6-month"]
_FULLTIME_KW = ["full-time", "full time", "permanent", "fte", "regular", "permanent employee"]
_REMOTE_KW = ["remote", "work from home", "wfh", "virtual", "100% remote", "fully remote"]
_ONSITE_KW = ["on-site", "on site", "in-office", "office based", "office-based"]
_HYBRID_KW = ["hybrid"]


def _search_jobs(
    query: str,
    location: str = "Remote",
    threshold: int = 65,
    require_visa: bool = False,
    exclude_companies: list[str] | None = None,
    focus_role: str = "",
    max_results: int = 10,
    sources: list[str] | None = None,
    locations: list[str] | None = None,
    skills: list[str] | None = None,
    job_type: str = "",
    work_mode: str = "",
) -> str:
    if max_results > 50:
        max_results = 50

    board_scrapers = [
        ("LinkedIn", search_linkedin),
        ("Indeed", search_indeed),
        ("Naukri", search_naukri),
        ("Glassdoor", search_glassdoor),
        ("SimplyHired", search_simplyhired),
        ("WeWorkRemotely", search_weworkremotely),
        ("WomenInTech", search_womenintech),
        ("Instahyre", search_instahyre),
        ("Remotive", search_remotive),
        ("Foundit", search_foundit),
        ("TimesJobs", search_timesjobs),
        ("ArcDev", search_arcdev),
        ("Arbeitnow", search_arbeitnow),
        ("Seek", search_seek),
        ("Jora", search_jora),
        ("Xing", search_xing),
        ("JobsCh", search_jobsch),
        ("JobsinGermany", search_jobsingermany),
        ("VisaSponsor", search_visasponsor),
        ("Incluso", search_incluso),
    ]
    pw_scrapers = [
        ("RemoteOK", search_remoteok),
        ("SkipTheDrive", search_skipthedrive),
        ("WorkingNomads", search_workingnomads),
        ("Jobspresso", search_jobspresso),
        ("EnglishJobSearch", search_englishjobsearch),
        ("BulldogJob", search_bulldogjob),
        ("WorkAtAStartup", search_workatstartup),
        ("StepStone", search_stepstone),
        ("MonsterDE", search_monsterde),
        ("Adzuna", search_adzuna),
        ("Reed", search_reed),
        ("Jobsite", search_jobsite),
        ("Intermediair", search_intermediair),
        ("NationaleVacaturebank", search_nationalevacaturebank),
    ]

    sources_lower = [s.lower() for s in sources] if sources else []
    exclude_lower = [c.lower().strip() for c in exclude_companies] if exclude_companies else []
    focus_words = focus_role.lower().split() if focus_role else []

    # Build expanded queries from profile + user input
    expanded_queries = build_domain_queries(prefer_role=query or focus_role or None)
    if query and query not in expanded_queries:
        expanded_queries.insert(0, query)
    all_jobs = []
    skipped = []

    # Determine effective location for board scrapers (use first from multi-select if provided)
    effective_location = locations[0] if locations else location
    locations_lower = [l.lower() for l in locations] if locations else None
    skills_lower = [s.lower() for s in skills] if skills else None

    def _passes_filters(job):
        """Check job against additional filters: locations, skills, job_type, work_mode (OR logic).
        
        For job_type and work_mode, checks dedicated job fields first (varies by source),
        then falls back to text matching in title + description + location.
        """
        combined = (job.get("title", "") + " " + job.get("description", "") + " " + job.get("location", "")).lower()
        loc = job.get("location", "").lower()

        if locations_lower:
            if not any(l in loc for l in locations_lower):
                return False

        if skills_lower:
            if not any(s in combined for s in skills_lower):
                return False

        if job_type:
            # Try dedicated employment type field first (varies by source/ATS)
            emp = None
            for f in ("employment_type", "employmentType", "commitment", "job_type", "jobType", "type"):
                v = job.get(f)
                if v is not None and v != "":
                    emp = str(v).lower().replace(" ", "_").replace("-", "_")
                    break
            if emp:
                if job_type == "contract":
                    if not any(t in emp for t in ("contract", "temporary", "temp", "freelance", "fixed_term")):
                        return False
                elif job_type == "full-time":
                    if not any(t in emp for t in ("full_time", "fulltime", "permanent", "fte", "regular")):
                        return False
            else:
                # Fall back to text matching
                if job_type == "contract":
                    if not any(kw in combined for kw in _CONTRACT_KW):
                        return False
                elif job_type == "full-time":
                    if not any(kw in combined for kw in _FULLTIME_KW):
                        return False

        if work_mode:
            # Try dedicated workplace type field first
            wfm = None
            for f in ("workplace_type", "workplaceType", "workplace", "locationType"):
                v = job.get(f)
                if v is not None and v != "":
                    wfm = str(v).lower().replace(" ", "_").replace("-", "_")
                    break
            # Also check boolean 'remote' field
            remote_bool = job.get("remote")
            if wfm or remote_bool is not None:
                if work_mode == "remote":
                    is_remote = False
                    if wfm:
                        is_remote = any(t in wfm for t in ("remote", "fully_remote"))
                    if remote_bool is True:
                        is_remote = True
                    if not is_remote:
                        return False
                elif work_mode == "on-site":
                    if wfm:
                        if any(t in wfm for t in ("remote", "fully_remote", "hybrid")):
                            return False
                    elif remote_bool is True:
                        return False
                elif work_mode == "hybrid":
                    is_hybrid = False
                    if wfm:
                        is_hybrid = "hybrid" in wfm
                    if not is_hybrid and remote_bool is True:
                        return False  # purely remote, not hybrid
                    if not is_hybrid and not any(kw in combined for kw in _HYBRID_KW):
                        return False
            else:
                # Fall back to text matching
                if work_mode == "remote":
                    if not any(kw in combined for kw in _REMOTE_KW):
                        return False
                elif work_mode == "on-site":
                    if not any(kw in combined for kw in _ONSITE_KW):
                        return False
                elif work_mode == "hybrid":
                    if not any(kw in combined for kw in _HYBRID_KW):
                        return False

        return True

    def _score(job):
        """Score job, with career page fallback for visa check."""
        desc = job.get("description", "")
        if desc.startswith(("LinkedIn job:", "Indeed job:", "Naukri job:", "Instahyre job:",
                            "Glassdoor job:", "SimplyHired:", "WomenInTech UK job:",
                            "WeWorkRemotely:", "RemoteOK:", "SkipTheDrive:", "WorkingNomads:",
                            "Jobspresso:", "EnglishJobSearch:", "BulldogJob:", "WorkAtAStartup:",
                            "Adzuna:", "Reed:", "Jobsite:", "Intermediair:", "NationaleVacaturebank:")):
            desc = job["title"]
        if not require_visa:
            desc += " visa sponsorship relocation support"
        score, note = score_job(job["title"], desc, job["company"], job.get("location", ""))
        # If score is low and visa info is missing, try career page fallback
        # to see if the company sponsors visas (can boost score via visa/relo bonus)
        if score > 0 and "Visa sponsorship details not mentioned" in note:
            # Check if job is actually outside India
            loc_lower = job.get("location", "").lower()
            text_lower = (job["title"] + " " + job.get("description", "")).lower()
            _INDIA_MARKERS = ["india", "pune", "mumbai", "bangalore", "bengaluru", "hyderabad",
                              "chennai", "delhi", "gurgaon", "gurugram", "noida", "kolkata",
                              "ahmedabad", "jaipur", "thiruvananthapuram", "kochi", "coimbatore"]
            is_outside_india = not any(m in loc_lower or m in text_lower for m in _INDIA_MARKERS)
            is_remote_job = "remote" in loc_lower or "remote" in text_lower
            
            if is_outside_india and not is_remote_job:
                career_url = job.get("url", "") or None
                has_visa = _check_career_page_visa(job["company"], career_url)
                if has_visa:
                    desc += " visa sponsorship relocation support"
                    score, note = score_job(job["title"], desc, job["company"], job.get("location", ""))
                    note = (note + " | visa confirmed from career page").strip(" |")
                elif require_visa:
                    return 0, "Filtered: no visa/relocation signal found (require_visa=True)"
        return score, note

    # Company ATS sources (not query-dependent - fetch all)
    all_sources = JOB_SOURCES + EU_JOB_SOURCES + GLOBAL_JOB_SOURCES + APAC_JOB_SOURCES + US_CANADA_JOB_SOURCES + MIDDLE_EAST_JOB_SOURCES
    for source in all_sources:
        sname = source["name"].lower()
        ats_type = source.get("ats", "").lower()
        if sources_lower and not any(s in sname or s in ats_type for s in sources_lower):
            continue
        try:
            jobs = fetch_jobs_from_source(source)
        except Exception as e:
            skipped.append({
                "source": source["name"],
                "url": source.get("url", "N/A"),
                "resume": PROFILE.get("name", "N/A"),
                "error": str(e)[:200],
            })
            continue
        for job in jobs:
            company_lower = job["company"].lower().strip()
            if exclude_lower and any(c in company_lower for c in exclude_lower):
                continue
            if not _passes_filters(job):
                continue
            score, note = _score(job)
            if score >= threshold:
                salary_info = get_salary_info(job["company"], job["title"], job.get("description", ""))
                resume = pick_resume(job["company"])
                all_jobs.append({**job, "score": score, "relocation_note": note, "salary_info": salary_info, "resume": resume})

    # Job board scrapers — run all expanded queries, deduplicate
    for board_name, board_fn in board_scrapers:
        if sources_lower and not any(s in board_name.lower() for s in sources_lower):
            continue
        for q in expanded_queries:
            try:
                jobs = board_fn(q, location=effective_location, max_results=max_results)
                for job in jobs:
                    company_lower = job["company"].lower().strip()
                    if exclude_lower and any(c in company_lower for c in exclude_lower):
                        continue
                    if not _passes_filters(job):
                        continue
                    score, note = _score(job)
                    if score >= threshold:
                        salary_info = get_salary_info(job["company"], job["title"], job.get("description", ""))
                        resume = pick_resume(job["company"])
                        all_jobs.append({**job, "score": score, "relocation_note": note, "salary_info": salary_info, "resume": resume})
            except Exception as e:
                skipped.append({
                    "source": f"{board_name} (query: {q})",
                    "url": "N/A",
                    "resume": PROFILE.get("name", "N/A"),
                    "error": str(e)[:200],
                })

    # Playwright scrapers
    for pw_name, pw_fn in pw_scrapers:
        if sources_lower and not any(s in pw_name.lower() for s in sources_lower):
            continue
        for q in expanded_queries:
            try:
                jobs = pw_fn(q, location=effective_location, max_results=max_results)
                for job in jobs:
                    company_lower = job["company"].lower().strip()
                    if exclude_lower and any(c in company_lower for c in exclude_lower):
                        continue
                    if not _passes_filters(job):
                        continue
                    score, note = _score(job)
                    if score >= threshold:
                        salary_info = get_salary_info(job["company"], job["title"], job.get("description", ""))
                        resume = pick_resume(job["company"])
                        all_jobs.append({**job, "score": score, "relocation_note": note, "salary_info": salary_info, "resume": resume})
            except Exception as e:
                skipped.append({
                    "source": f"{pw_name} (query: {q})",
                    "url": "N/A",
                    "resume": PROFILE.get("name", "N/A"),
                    "error": str(e)[:200],
                })

    # Send exception notification email if any sources were skipped
    if skipped:
        _send_exception_email(skipped, batch_label=f"search_jobs({query})")

    # Deduplicate by (title, company)
    seen = set()
    unique = []
    for j in sorted(all_jobs, key=lambda x: x.get("score", 0), reverse=True):
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in seen and j["company"]:
            seen.add(key)
            unique.append(j)
            if len(unique) >= max_results * 2:
                break

    if not unique:
        qs = ", ".join(expanded_queries[:5])
        parts = [f"# No matching jobs found for your profile"]
        parts.append(f"Searched queries: {qs}{'...' if len(expanded_queries) > 5 else ''}")
        parts.append(f"\nYour settings: threshold={threshold}% | location={effective_location}")
        if locations:
            parts.append(f"Locations filter: {', '.join(locations)}")
        if skills:
            parts.append(f"Skills filter: {', '.join(skills)}")
        if job_type:
            parts.append(f"Job type: {job_type}")
        if work_mode:
            parts.append(f"Work mode: {work_mode}")
        if exclude_companies:
            parts.append(f"Excluded companies: {', '.join(exclude_companies)}")
        parts.append("\nTry lowering the threshold or removing exclusions.")
        return "\n".join(parts)

    q_summary = ", ".join(expanded_queries[:5])
    lines = [f"# Job Search Results ({len(unique)} matches)"]
    lines.append(f"Queries: {q_summary}{' ...' if len(expanded_queries) > 5 else ''}")
    filter_parts = [f"threshold={threshold}%", f"require_visa={'yes' if require_visa else 'no'}", f"location={effective_location}"]
    if locations:
        filter_parts.append(f"locations={','.join(locations)}")
    if skills:
        filter_parts.append(f"skills={','.join(skills)}")
    if job_type:
        filter_parts.append(f"job_type={job_type}")
    if work_mode:
        filter_parts.append(f"work_mode={work_mode}")
    lines.append(f"Settings: {' | '.join(filter_parts)}")
    if exclude_companies:
        lines.append(f"Excluded: {', '.join(exclude_companies)}")
    if focus_role:
        lines.append(f"Focus role: {focus_role}")
    lines.append("")

    for j in unique[:max_results]:
        score = j.get("score", 0)
        relo = f" — {j['relocation_note']}" if j.get("relocation_note") else ""
        match_tag = " ★" if focus_words and any(w in j["title"].lower() for w in focus_words) else ""

        resume = pick_resume(j.get("company", ""))
        salary_str = ""
        si = j.get("salary_info")
        if si:
            if si["source"] == "jd":
                salary_str = f" | Salary: {_format_salary(si)} (from JD)"
            elif si["source"] == "levels.fyi" and si.get("median_tc"):
                salary_str = f" | Median: {si['median_tc']} (Levels.fyi)"

        lines.append(f"**{j['title']}** @ {j['company']}{match_tag}")
        lines.append(f"   Score: {score}%  |  Location: {j.get('location', 'N/A')}{salary_str}")
        lines.append(f"   Resume: {resume}")
        lines.append(f"   URL: {j.get('url', 'N/A')}{relo}")
        lines.append("")

    lines.append("---")
    lines.append("**To track a job:** use `update_tracker` with title, company, status (applied/rejected/offer), and optional resume.")
    lines.append("Your Google Sheet will auto-organize jobs into tabs by resume version.")

    if len(unique) > max_results:
        lines.append(f"*... and {len(unique) - max_results} more.*")
    return "\n".join(lines)


def _score_job(title: str, description: str, company: str, location: str = "Remote") -> str:
    score, note = score_job(title, description, company, location)
    resume = pick_resume(company)
    suggestions = tailoring_suggestion(title, description, company)
    c_url = company_url(company)
    has_visa = any(kw in (title + " " + description).lower() for kw in VISA_RELOCATION_KEYWORDS)
    in_friendly = any(co in company.lower() for co in RELOCATION_FRIENDLY)
    salary_info = get_salary_info(company, title, description)

    parts = [
        f"## Score: {score}% — {title} @ {company}",
        f"**Location:** {location}",
        f"**Recommended resume:** {resume}",
        f"**Company link:** {c_url}",
        f"**Visa/relocation mentioned:** {'Yes' if has_visa else 'No'}",
        f"**Relocation-friendly company:** {'Yes' if in_friendly else 'No'}",
    ]
    if salary_info:
        if salary_info["source"] == "jd":
            parts.append(f"**Salary (from JD):** {_format_salary(salary_info)}")
        elif salary_info["source"] == "levels.fyi" and salary_info.get("median_tc"):
            parts.append(f"**Median comp (Levels.fyi):** {salary_info['median_tc']}")
            if salary_info.get("levels"):
                level_lines = []
                for lv in salary_info["levels"][:5]:
                    level_lines.append(f"  - {lv['level']}: {lv['total']}")
                parts.append(f"**Levels breakdown:**\n" + "\n".join(level_lines))
    if note:
        parts.append(f"**Note:** {note}")
    if suggestions:
        parts.append(f"**Tailoring suggestions:**")
        for s in suggestions:
            parts.append(f"  - {s}")
    return "\n".join(parts)


def _tracker_status(status: str = "", limit: int = 20) -> str:
    if limit > 100:
        limit = 100

    jobs = tracker.data.get("jobs", {})
    if not jobs:
        return "No jobs tracked yet. Run a search first."

    filtered = []
    for key, entry in jobs.items():
        if status and entry.get("status", "new") != status:
            continue
        filtered.append(entry)

    filtered.sort(key=lambda x: x.get("date_updated", ""), reverse=True)
    filtered = filtered[:limit]

    counts = {}
    for e in tracker.data["jobs"].values():
        s = e.get("status", "new")
        counts[s] = counts.get(s, 0) + 1

    summary = " | ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    lines = [f"## Job Tracker — {summary}", f"Showing {len(filtered)} of {len(jobs)} tracked jobs.\n"]

    for j in filtered:
        status_icon = {"new": "🆕", "applied": "✅", "rejected": "❌", "offer": "🎉"}
        icon = status_icon.get(j.get("status", "new"), "❓")
        lines.append(
            f"{icon} **{j['title']}** @ {j['company']} "
            f"— Score: {j.get('score', '?')}% — Status: {j.get('status', 'new')}"
        )
        lines.append(f"   URL: {j.get('url', 'N/A')}")
        if j.get("notes"):
            lines.append(f"   Notes: {j['notes']}")
        lines.append("")

    return "\n".join(lines)


def _update_tracker(title: str, company: str, status: str, notes: str = "", resume: str = "") -> str:
    key = tracker.job_key(title, company)
    if key not in tracker.data["jobs"]:
        tracker.add_job(title, company, status=status, resume=resume)
    else:
        if resume:
            tracker.data["jobs"][key]["resume"] = resume
    ok = tracker.update_status(title, company, status, notes)
    if ok:
        resume_info = f" (resume: {resume})" if resume else ""
        gsheet_ok = sync_tracker_to_gsheet(tracker)
        gsheet_msg = " + Google Sheet synced" if gsheet_ok else ""
        return f"✅ Updated **{title}** @ {company} → **{status}**{resume_info}{gsheet_msg}. Jobs are now organized by resume in separate sheet tabs."
    else:
        return f"⚠️ Could not find '{title}' @ {company} in tracker. Use a search first so it gets tracked."


_REQUIRED_RESUME_FIELDS = {
    "current_role": "Most recent job title (e.g. 'Senior Backend Engineer')",
    "years_experience": "Years of professional experience (e.g. 10)",
    "core_skills": "Technical skills list (e.g. Java, Python, AWS, Kubernetes)",
}


def _parse_resume(path: str, key: str = "") -> str:
    if not os.path.exists(path):
        return f"Error: File not found at {path}"
    try:
        profile, missing = parse_resume_pdf(path)
        if missing:
            parts = ["## Resume Parsing Failed — Required Parameters Missing"]
            for field in missing:
                parts.append(f"\n**{field}** is missing from your resume")
                parts.append(f"  Expected: {_REQUIRED_RESUME_FIELDS.get(field, '')}")
            parts.append("\nTo continue, update your resume to include the missing fields and try again.")
            return "\n".join(parts)

        # Auto-configure title filters based on detected role
        PROFILE["title_red_flags"] = auto_detect_title_red_flags(profile["core_skills"])
        PROFILE["name"] = profile.get("name", PROFILE["name"])
        PROFILE["current_role"] = profile.get("current_role", "")
        PROFILE["years_experience"] = profile.get("years_experience", PROFILE["years_experience"])
        if profile.get("core_skills"):
            PROFILE["core_skills"] = profile["core_skills"]

        # Detect domain(s) for display
        skill_set = set(s.lower() for s in PROFILE["core_skills"])
        detected_domains = [
            d for d, cfg in ROLE_DOMAINS.items()
            if len(skill_set & cfg["skills"]) >= 2
        ]
        domain_label = ", ".join(detected_domains) if detected_domains else "auto-detected"

        parts = [
            f"## Resume: {profile.get('name', 'Unknown')}",
            f"**Current Role:** {profile.get('current_role', 'N/A')}",
            f"**Email:** {profile.get('email', 'N/A')}",
            f"**Experience:** {profile['years_experience']} years",
            f"**Detected Domain:** {domain_label}",
            f"**Skills ({len(profile.get('core_skills', []))}):**",
        ]
        skills = profile.get("core_skills", [])
        for i in range(0, len(skills), 10):
            parts.append("  " + ", ".join(skills[i:i + 10]))
        parts.append("")

        # --- Register/Copy resume if key is provided ---
        resume_registered = False
        if key:
            key = key.strip().lower().replace(" ", "_")
            filename = os.path.basename(path)
            dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

            # Copy file to project directory if it's not already there
            if os.path.abspath(path) != os.path.abspath(dest):
                shutil.copy2(path, dest)
                parts.append(f"📄 Copied to: {filename}")

            # Register in RESUME_VERSIONS
            old_filename = RESUME_VERSIONS.get(key, "")
            RESUME_VERSIONS[key] = filename
            resume_registered = True

            if old_filename:
                parts.append(f"🔄 Replaced resume **{key}** (was: {old_filename} → now: {filename})")
            else:
                parts.append(f"✅ Registered new resume version **{key}** → {filename}")
                # Auto-map common company patterns to the new key
                if key == "faang":
                    parts.append("ℹ️ This is the default resume — will be used for most companies.")
                elif key:
                    known_domains = {"general", "indian_tech", "startup", "eu", "us", "asia"}
                    if key in known_domains:
                        parts.append(f"ℹ️ Mapped as **{key}** version. Use `update_tracker` with resume={filename} to assign it to specific jobs.")

        # Show all current resume versions
        parts.append("")
        parts.append(f"### Current Resume Versions ({len(RESUME_VERSIONS)})")
        for rk, rfn in RESUME_VERSIONS.items():
            exists = "✅" if os.path.exists(rfn) else "❌"
            is_default = " (default)" if rk == "faang" else ""
            parts.append(f"  {exists} **{rk}** → {rfn}{is_default}")

        parts.append("")
        parts.append(f"Profile updated with {len(PROFILE['title_red_flags'])} title filters "
                     f"(universal + domain-specific).")
        parts.append("Run `get_profile` to see the active configuration.")
        return "\n".join(parts)
    except Exception as e:
        return f"Error parsing resume: {e}"


def _get_profile() -> str:
    skill_set = set(s.lower() for s in PROFILE["core_skills"])
    detected_domains = [
        d for d, cfg in ROLE_DOMAINS.items()
        if len(skill_set & cfg["skills"]) >= 2
    ]
    domain_label = ", ".join(detected_domains) if detected_domains else "general (no dominant domain detected)"
    current_role = PROFILE.get("current_role", "")

    parts = [
        f"## Active Profile — {PROFILE['name']}",
        f"**Current Role:** {current_role or 'Not set (use parse_resume)'}",
        f"**Experience:** {PROFILE['years_experience']} years",
        f"**Detected Domain(s):** {domain_label}",
        f"**Core skills ({len(PROFILE['core_skills'])}):**",
    ]
    skills = PROFILE["core_skills"]
    for i in range(0, len(skills), 10):
        parts.append("  " + ", ".join(skills[i:i + 10]))
    parts.append(f"\n**Title red flags ({len(PROFILE['title_red_flags'])} patterns):**")
    for rf in PROFILE["title_red_flags"][:10]:
        parts.append(f"  - {rf}")
    if len(PROFILE["title_red_flags"]) > 10:
        parts.append(f"  ... and {len(PROFILE['title_red_flags']) - 10} more")
    parts.append(
        f"\n**Job sources configured:** {len(JOB_SOURCES)} company ATS feeds "
        f"+ 15+ job board scrapers"
    )

    # Resume section
    default_resume = RESUME_VERSIONS.get("faang", "N/A")
    parts.append(f"\n### Resumes ({len(RESUME_VERSIONS)} registered)")
    for key, filename in RESUME_VERSIONS.items():
        exists = "✅" if os.path.exists(filename) else "❌"
        is_default = " (default)" if key == "faang" else ""
        parts.append(f"  {exists} **{key}** → {filename}{is_default}")
    parts.append(f"\nUse `parse_resume <path>` to upload a new resume.")
    parts.append(f"Use `list_resumes` to scan for available PDFs.")

    return "\n".join(parts)


def _list_resumes(scan: bool = True) -> str:
    """List registered resume versions and optionally discover new PDFs."""
    parts = [f"## Resume Versions ({len(RESUME_VERSIONS)} registered)"]
    parts.append("")
    default_key = "faang"

    for key, filename in RESUME_VERSIONS.items():
        exists = os.path.exists(filename)
        status = "✅ exists" if exists else "❌ not found"
        is_default = " ← default" if key == default_key else ""
        parts.append(f"  **{key}** → {filename}  ({status}){is_default}")

    parts.append("")
    parts.append("### Company → Resume Mapping")
    parts.append(f"  {len(COMPANY_RESUME_MAP)} companies mapped to resume versions")
    parts.append(f"  Default resume: {RESUME_VERSIONS.get(default_key, 'N/A')}")
    parts.append("")

    if scan:
        pdfs = glob("*.pdf") or []
        registered_names = set(RESUME_VERSIONS.values())
        unregistered = [p for p in pdfs if os.path.basename(p) not in registered_names]
        if unregistered:
            parts.append(f"### Unregistered PDFs Found ({len(unregistered)})")
            for p in unregistered:
                fsize = os.path.getsize(p) // 1024
                parts.append(f"  📄 {p}  ({fsize} KB)")
            parts.append("")
            parts.append("Use `parse_resume <path> [key=<name>]` to register a new resume version.")
        else:
            parts.append("No unregistered PDFs found in the project directory.")
            parts.append("Place a PDF in the project folder and run `list_resumes` to discover it.")

    parts.append("")
    parts.append("---")
    parts.append("**To register a new resume:**")
    parts.append("  1. Place the PDF in the project directory")
    parts.append("  2. Run `parse_resume /path/to/file.pdf` with optional `key=<version_name>`")
    parts.append("  3. The resume is auto-copied and registered for future searches")

    return "\n".join(parts)


def _search_board_jobs(
    search_term: str,
    location: str = "Remote",
    site_names: str = "linkedin,indeed,glassdoor",
    results_wanted: int = 15,
    hours_old: int = 168,
    is_remote: bool = True,
) -> str:
    try:
        from jobspy import scrape_jobs

        sites = [s.strip() for s in site_names.split(",")]
        results_wanted = min(results_wanted, 50)
        hours_old = min(hours_old, 720) if hours_old else None

        df = scrape_jobs(
            site_name=sites,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            is_remote=is_remote,
            country_indeed="USA",
            description_format="markdown",
        )

        if df is None or df.empty:
            return f"# No jobs found\nSearched {site_names} for '{search_term}' in {location}"

        imported = 0
        lines = [f"# Board Search: {search_term} ({len(df)} results)"]
        lines.append(f"Sites: {site_names} | Location: {location}\n")

        for _, row in df.iterrows():
            title = row.get("title", "")
            company = row.get("company", "")
            loc = row.get("location", "") or location
            url = row.get("job_url", "") or ""
            site = row.get("site", "")
            date = row.get("date_posted", "")
            desc = str(row.get("description", "") or "")
            desc_short = desc[:200].replace("\n", " ") + "..." if len(desc) > 200 else desc.replace("\n", " ")

            lines.append(f"**{title}** @ {company}")
            lines.append(f"   Location: {loc} | Source: {site}")
            if date:
                lines.append(f"   Posted: {str(date)[:10]}")
            lines.append(f"   {desc_short}")
            lines.append(f"   URL: {url}")
            lines.append("")
            imported += 1
            if imported >= results_wanted:
                break

        lines.append(f"\nFound {imported} jobs from {site_names}")
        lines.append("Use `search_jobs` with threshold scoring for your profile, or `update_tracker` to track a match.")

        return "\n".join(lines)

    except ImportError:
        return "Error: JobSpy not installed. Run: pip install python-jobspy"
    except Exception as e:
        return f"Error searching boards: {e}"

# Company descriptions from career-ops integration
_COMPANY_CONTEXT = {
    "geberit": "Swiss sanitary products manufacturer with a large IT and engineering division for building systems, IoT plumbing, and factory automation.",
    # US/Canada (28)
    "anthropic": "AI safety research lab developing Claude, a helpful and harmless AI assistant.",
    "cohere": "AI/LLM provider building enterprise-focused language models. Toronto + remote.",
    "perplexity": "AI-native search and enterprise AI platform with real-time web answers.",
    "weights & biases (coreweave)": "ML experiment tracking platform acquired by CoreWeave (GPU cloud).",
    "hume ai": "Empathic voice AI platform based in NYC. Emotion-aware voice interfaces.",
    "sierra": "AI customer agents platform founded by Bret Taylor (ex-CEO Salesforce).",
    "decagon": "AI customer support agent platform. Building autonomous support experiences.",
    "ada": "AI customer service automation platform. Toronto + remote.",
    "airtable": "No-code database and collaboration platform with AI features.",
    "vercel": "Frontend deployment and AI SDK platform creators of Next.js, v0.dev.",
    "temporal": "Workflow orchestration platform for resilient distributed applications.",
    "glean": "Enterprise AI search powered by your company's knowledge graph.",
    "clay labs": "AI-native GTM and workflow automation for go-to-market teams.",
    "langchain": "LangChain/LangSmith framework for LLM application development.",
    "arize ai": "LLMOps and AI observability platform for monitoring ML in production.",
    "pinecone": "Vector database purpose-built for AI similarity search and RAG.",
    "runpod": "GPU cloud platform optimized for AI inference and training workloads.",
    "supabase": "Open-source Firebase alternative: Postgres, Auth, Storage, Realtime.",
    "zep ai": "Context engineering platform for AI agents. YC W24, US-only.",
    "resend": "Email API for developers. Modern email delivery infrastructure.",
    "clerk": "Authentication and user management platform for modern web apps.",
    "inngest": "Durable workflow engine for serverless applications and background jobs.",
    "workos": "Developer tools for enterprise-ready auth and platform APIs.",
    "hightouch": "Data activation platform syncing warehouse data to SaaS tools.",
    "planetscale": "Serverless MySQL platform with branching, deploy requests, and scale.",
    "runway": "Generative AI video creation and creative tooling platform.",
    "safari ai": "Computer vision AI for operations in the physical economy. Vancouver/Miami.",
    "later": "Social media and creator platform based in Vancouver/Toronto.",
    # EU (47)
    "aleph alpha": "Sovereign European LLM provider based in Heidelberg, enterprise & government focus.",
    "amplemarket": "AI-native sales platform based in Lisbon. Automating outbound sales workflows.",
    "attio": "AI-native CRM platform. Remote EU, Series B.",
    "black forest labs": "FLUX image generation models by ex-Stable Diffusion team. Freiburg + SF.",
    "bland ai": "Voice AI phone agents. Series B funded.",
    "boomi": "Integration and automation platform connecting SaaS and on-prem systems.",
    "causaly": "Biomedical knowledge graph and AI platform. London + Athens.",
    "clarity ai": "Sustainability analytics platform powered by AI. Madrid/Remote.",
    "corti": "Medical AI for ambient clinical documentation. Copenhagen.",
    "cradle": "AI-guided protein design for biotech. Zurich + Amsterdam.",
    "deepl": "Translation and language AI. Cologne-based, 60+ open roles.",
    "deepgram": "Speech-to-text and text-to-speech API platform.",
    "dialpad": "Voice AI for business communications and contact centers.",
    "elevenlabs": "Voice AI TTS leader. AI voice synthesis and dubbing.",
    "factorial": "HR SaaS unicorn based in Barcelona.",
    "faculty": "Applied AI consultancy based in London. 80+ roles across AI delivery.",
    "genesys": "Cloud contact center platform with AI-powered customer experience.",
    "gong": "Revenue intelligence platform analyzing customer calls with AI.",
    "helsing": "Defence AI unicorn. Munich, Berlin, London, Paris. 100+ ML and FDE roles.",
    "hugging face": "Open-source ML hub and model library. Paris + NYC + remote.",
    "intercom": "Customer communication platform with Fin AI agent. Dublin EMEA.",
    "isomorphic labs": "DeepMind spin-off for AI-driven drug discovery. London + Lausanne.",
    "lakera": "AI security and guardrails platform. Zurich + SF.",
    "langfuse": "LLMOps and observability platform. Berlin-based open-core company.",
    "legora": "AI-native legal workspace platform. Stockholm + NYC + London.",
    "lindy": "AI agent management platform for automating business workflows.",
    "liveperson": "Conversational AI enterprise platform. Remote EMEA-friendly.",
    "lovable": "AI app builder (text-to-app). Stockholm-based, 80+ open roles.",
    "make.com (celonis)": "Automation platform (visual workflow builder). Part of Celonis.",
    "parloa": "Voice AI for enterprise contact centers. Berlin EMEA.",
    "photoroom": "AI photo editor. Paris-based, Head of CV and ML roles.",
    "physicsx": "Physics-informed ML for engineering simulations. London UK.",
    "pigment": "AI-powered FP&A planning platform. Paris + NYC + London.",
    "pleo": "Spend-management fintech. Copenhagen-based, ML and platform roles.",
    "polyai": "Voice AI for enterprise contact centers. UK-based.",
    "retool": "Low-code internal tool builder. London Deployed Engineer roles.",
    "scandit": "Computer vision and smart data capture. Zurich-based, ML roles.",
    "speechmatics": "Speech recognition platform. Cambridge UK.",
    "stability ai": "Generative AI image and video research lab. London + SF.",
    "synthesia": "AI video generation platform for enterprise. London, $4B valuation.",
    "talkdesk": "Contact center AI platform. Lisbon-based, EMEA-friendly.",
    "templafy": "Document generation and content enablement platform. Copenhagen.",
    "tinybird": "Real-time data platform for high-performance analytics. Remote.",
    "travelperk": "Business travel management platform. Barcelona unicorn.",
    "vapi": "Voice AI infrastructure for developers. Building voice-powered applications.",
    "wayve": "Embodied AI for self-driving vehicles. London-based.",
    "zapier": "Automation platform connecting thousands of apps. Remote-first.",
    # APAC (2)
    "glacis ai": "AI agents for supply chain and logistics. Ho Chi Minh City.",
    "maxim ai": "AI evaluation and observability platform. Bangalore-based.",
    # Middle East (15)
    "trendyol": "Turkey's largest e-commerce platform (Alibaba-owned). Istanbul.",
    "hepsiburada": "Major Turkish e-commerce platform listed on NASDAQ. Istanbul.",
    "getir": "Ultra-fast delivery unicorn. Istanbul-based, now Turkey-only.",
    "insider": "B2B SaaS marketing platform unicorn. Istanbul, remote-friendly.",
    "dream games": "Mobile gaming company behind Royal Match. Istanbul.",
    "peak games (zynga)": "Mobile gaming studio acquired by Zynga. Istanbul.",
    "yemeksepeti (delivery hero)": "Food delivery platform, Delivery Hero subsidiary. Istanbul.",
    "sahibinden.com": "Turkey's largest classifieds platform. Istanbul.",
    "garanti bbva technology": "Fintech/banking tech arm of Garanti BBVA. Istanbul.",
    "akbank tech": "Turkish bank with large in-house tech team. Istanbul.",
    "turkcell": "Turkey's largest telecom with digital transformation team. Istanbul.",
    "iyzico (payu)": "Payment infrastructure platform, PayU subsidiary. Istanbul.",
    "papara": "Turkish fintech / digital wallet. Unicorn valuation. Istanbul.",
    "craftgate": "Payment orchestration platform. Istanbul, engineering-first.",
    "n11.com (doğuş)": "E-commerce marketplace, Doğuş Group. Istanbul.",

    # Pre-existing companies (before career-ops import)
    "openai": "AI research and deployment company behind GPT and DALL-E.",
    "mistral ai": "European AI lab building open-weight language models. Paris.",
    "palantir": "Data analytics platform for government and enterprise clients.",
    "salesforce": "CRM and enterprise cloud platform with Agentforce AI agent platform.",
    "celonis": "Process intelligence and execution management platform. Munich + NYC.",
    "cognigy": "Conversational AI platform for enterprise contact centers. Dusseldorf.",
    "contentful": "Headless CMS platform with AI content workflows. Berlin + Denver.",
    "forto": "Digital freight forwarder platform. Berlin.",
    "getyourguide": "Travel marketplace for tours and activities. Berlin.",
    "hellofresh": "Meal kit delivery service with large data and ML org. Berlin.",
    "n26": "Mobile-first neobank. Berlin + Barcelona.",
    "qonto": "SMB neobank for European businesses. Paris.",
    "sumup": "Payments fintech for small businesses. Berlin + London.",
    "trade republic": "Neobroker for retail investing. Berlin + London + Paris.",
    "vinted": "C2C marketplace for second-hand fashion. Vilnius + Berlin.",
    "spotify": "Audio streaming platform with large ML/personalization org. Stockholm.",
    "twilio": "Voice, messaging, and email API platform.",

    # European industrial & manufacturing
    "abb": "Swiss-Swedish multinational robotics, power, and automation technology.",
    "bmw group": "German luxury automobile and motorcycle manufacturer. Munich HQ.",
    "asml": "Dutch lithography equipment supplier for semiconductor manufacturing.",
    "sika": "Swiss specialty chemicals company for construction and automotive.",
    "clariant": "Swiss specialty chemical company focused on sustainability and innovation.",
    "holcim": "Swiss global building materials and cement manufacturer.",
}

def _email_digest(schedule: str = "now", email: str = "") -> str:
    """Trigger or schedule the email digest."""
    all_sources = JOB_SOURCES + EU_JOB_SOURCES + GLOBAL_JOB_SOURCES + APAC_JOB_SOURCES + US_CANADA_JOB_SOURCES + MIDDLE_EAST_JOB_SOURCES + REMOTE_JOB_SOURCES
    gmail_address = os.environ.get("GMAIL_ADDRESS") or "kminterviewer@gmail.com"
    recipient = email or os.environ.get("EMAIL_TO") or gmail_address

    if schedule == "now":
        _rebuild_precompiled_patterns()
        matches = []
        seen = set()
        for source in all_sources:
            try:
                jobs = fetch_jobs_from_source(source)
            except Exception:
                continue
            for job in jobs:
                key = (job["title"].lower().strip(), job["company"].lower().strip())
                if key in seen:
                    continue
                seen.add(key)
                score, note = score_job(job["title"], job.get("description", ""), job["company"], job.get("location", ""))
                if score >= 65:
                    salary_info = get_salary_info(job["company"], job["title"], job.get("description", ""))
                    resume = pick_resume(job["company"])
                    matches.append({
                        **job,
                        "score": score,
                        "resume": resume,
                        "relocation_note": note,
                        "salary_info": salary_info,
                        "company_url": company_url(job["company"], job.get("url", "")),
                    })
        matches.sort(key=lambda m: m["score"], reverse=True)

        html = build_email_html(matches)
        ok = send_email(html, subject=f"Job Matches — {len(matches)} opportunities — {datetime.now().strftime('%d %b %Y')}", recipient=recipient)

        if ok:
            _save_digest_schedule({
                "schedule": schedule,
                "email": recipient,
                "last_sent": datetime.now().isoformat(),
                "scheduled_date": "",
            })
            return f"## Email Digest Sent\n- **Recipient:** {recipient}\n- **Matches:** {len(matches)} jobs above 65%\n- **Sent:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n- Top match: {matches[0]['title']} @ {matches[0]['company']} ({matches[0]['score']}%)" if matches else f"## Email Digest Sent\n- **Recipient:** {recipient}\n- **Matches:** 0 (no jobs above threshold)\nCheck back later or adjust your profile."
        else:
            return f"## Email Digest Failed\nCould not send email. Check GMAIL_APP_PASSWORD in your .env."

    elif schedule == "never":
        _save_digest_schedule({
            "schedule": "never",
            "email": recipient,
            "last_sent": "",
            "scheduled_date": "",
        })
        return f"## Digest Disabled\nScheduled email digest has been turned off."

    elif schedule in ("tomorrow", "weekly", "monthly"):
        scheduled_date = ""
        if schedule == "tomorrow":
            scheduled_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        _save_digest_schedule({
            "schedule": schedule,
            "email": recipient,
            "last_sent": "",
            "scheduled_date": scheduled_date,
        })
        freq_label = {"tomorrow": "tomorrow (one-time)", "weekly": "every week", "monthly": "every month"}
        return f"## Digest Scheduled\n- **Frequency:** {freq_label.get(schedule, schedule)}\n- **Recipient:** {recipient}\n- **Next send:** {scheduled_date or 'based on frequency'}\n\nRun `email_digest` with `schedule='now'` any time to send immediately."

    return f"## Unknown schedule: {schedule}\nUse one of: now, tomorrow, weekly, monthly, never"


def _prepare_application(
    title: str,
    company: str,
    description: str,
    location: str = "Remote",
    url: str = "",
    resume: str = "",
) -> str:
    """Return structured context for an LLM to generate cover letter, STAR+R stories, and gap mitigation."""
    score, note = score_job(title, description, company, location)
    resume_pdf = resume or pick_resume(company)
    c_url = company_url(company)
    suggestions = tailoring_suggestion(title, description, company)
    salary_info = get_salary_info(company, title, description)
    skills = PROFILE["core_skills"]

    # Gap analysis: extract potential tech/domain keywords from description
    # that aren't in the profile's core skills
    desc_lower = (title + " " + description).lower()
    skill_set = set(s.lower() for s in skills)
    gap_keywords = set()
    tech_patterns = [
        r'\b(?:python|java|javascript|typescript|golang|rust|c\+\+|ruby|php|scala|kotlin|swift)\b',
        r'\b(?:react|angular|vue|svelte|node\.?js|django|flask|spring|rails|laravel)\b',
        r'\b(?:kubernetes|docker|terraform|ansible|jenkins|gitlab\s*ci|github\s*actions|circleci)\b',
        r'\b(?:aws|gcp|azure|cloud|lambda|ec2|s3|rds|dynamodb|kafka|redis|postgresql|mysql|mongodb)\b',
        r'\b(?:machine\s*learning|deep\s*learning|nlp|llm|langchain|pytorch|tensorflow|rag|vector|embedding)\b',
        r'\b(?:sap|salesforce|oracle|servicenow|workday|dynamics)\b',
        r'\b(?:api|graphql|grpc|rest|microservice|event.?driven|streaming)\b',
    ]
    for pat in tech_patterns:
        for m in re.finditer(pat, desc_lower):
            kw = m.group(0).replace('.', '-').replace('_', '')
            if kw not in skill_set and kw not in gap_keywords:
                gap_keywords.add(kw)

    gaps = sorted(gap_keywords)[:20]

    salary_str = ""
    if salary_info:
        if salary_info["source"] == "jd":
            salary_str = f"Salary (from JD): {_format_salary(salary_info)}"
        elif salary_info["source"] == "levels.fyi" and salary_info.get("median_tc"):
            salary_str = f"Median comp (Levels.fyi): {salary_info['median_tc']}"

    co_key = company.lower().strip()
    company_desc = _COMPANY_CONTEXT.get(co_key)
    if not company_desc:
        # Try fuzzy match: first word(s) of company
        for known_key, desc in _COMPANY_CONTEXT.items():
            if known_key in co_key or co_key in known_key:
                company_desc = desc
                break

    parts = [
        f"## Application Context: {title} @ {company}",
        f"",
        f"### Job",
        f"Title: {title}",
        f"Company: {company}",
        f"Company Description: {company_desc}" if company_desc else "",
        f"Location: {location}",
        f"URL: {url or c_url or 'N/A'}",
        f"Score: {score}%",
        f"Salary: {salary_str}" if salary_str else "",
        f"",
        f"### Profile",
        f"Name: {PROFILE['name']}",
        f"Current Role: {PROFILE.get('current_role', 'N/A')}",
        f"Experience: {PROFILE['years_experience']} years",
        f"Core Skills ({len(skills)}): {', '.join(skills)}",
        f"",
        f"### Resume",
        f"Recommended: {resume_pdf}",
        f"",
        f"### Company Link",
        f"{c_url}",
        f"",
        f"### Match Analysis",
        f"Score: {score}%",
        f"Notes: {note}" if note else "",
        f"",
        f"### Tailoring Suggestions",
    ]
    if suggestions:
        for s in suggestions:
            parts.append(f"- {s}")
    else:
        parts.append("(none generated)")

    parts.append(f"")
    parts.append(f"### Skill Gaps (JD vs Profile)")
    if gaps:
        parts.append(f"Keywords in JD not in your core skills ({len(gaps)}):")
        for g in gaps:
            parts.append(f"- {g}")
    else:
        parts.append("No significant gaps detected")
    parts.append(f"")
    parts.append(f"### Full Job Description")
    parts.append(description)
    parts.append(f"")
    parts.append(f"---")
    parts.append(f"Use the context above to generate:")
    parts.append(f"1. **Cover letter draft** — adapted to the role, addressing key JD requirements with concrete achievements from the profile")
    parts.append(f"2. **STAR+R stories** — 4-6 stories mapped to top JD requirements, with Reflection column for seniority signal")
    parts.append(f"3. **Gap mitigation** — for each skill gap, assess if it's a hard blocker vs nice-to-have, adjacent experience, or quick project")
    parts.append(f"Write in native professional English, active voice, no clichés. One page max for cover letter.")

    return "\n".join(parts)


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="job-search-agent",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
