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
from datetime import datetime
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
    parse_resume_pdf,
    auto_detect_title_red_flags,
    sync_tracker_to_gsheet,
    get_salary_info,
    build_domain_queries,
    _format_salary,
)
from eu_companies import EU_JOB_SOURCES
from global_companies import GLOBAL_JOB_SOURCES
from apac_companies import APAC_JOB_SOURCES
from us_canada_companies import US_CANADA_JOB_SOURCES
from middle_east_companies import MIDDLE_EAST_JOB_SOURCES

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = Server("job-search-agent")

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

    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                text = resp.text.lower()
                if any(kw in text for kw in visa_kw):
                    _visa_cache[co_key] = True
                    return True
        except Exception:
            continue

    _visa_cache[co_key] = None
    return None

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
                        "description": "Optional: require visa sponsorship/relocation support (default: true). Set to false for exploratory searches.",
                        "default": True,
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
            description="Extract name, email, current role, skills, and experience from a PDF resume. Validates that current_role, years_experience, and core_skills are present. Auto-configures title filters based on detected role domain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the PDF resume file",
                    },
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="get_profile",
            description="View the current profile configuration: name, experience, core skills, and filter settings",
            inputSchema={
                "type": "object",
                "properties": {},
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

**Manual check reminders** — Companies without public APIs (like Booking.com, Mollie, Personio) print reminders to check manually.""",
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


def _search_jobs(
    query: str,
    location: str = "Remote",
    threshold: int = 70,
    require_visa: bool = True,
    exclude_companies: list[str] | None = None,
    focus_role: str = "",
    max_results: int = 10,
    sources: list[str] | None = None,
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
    ]

    sources_lower = [s.lower() for s in sources] if sources else []
    exclude_lower = [c.lower().strip() for c in exclude_companies] if exclude_companies else []
    focus_words = focus_role.lower().split() if focus_role else []

    # Build expanded queries from profile + user input
    expanded_queries = build_domain_queries(prefer_role=query or focus_role or None)
    if query and query not in expanded_queries:
        expanded_queries.insert(0, query)
    all_jobs = []

    def _score(job):
        """Score job, with career page fallback for visa check."""
        desc = job.get("description", "")
        if desc.startswith(("LinkedIn job:", "Indeed job:", "Naukri job:", "Instahyre job:",
                            "Glassdoor job:", "SimplyHired:", "WomenInTech UK job:",
                            "WeWorkRemotely:", "RemoteOK:", "SkipTheDrive:", "WorkingNomads:",
                            "Jobspresso:", "EnglishJobSearch:", "BulldogJob:", "WorkAtAStartup:")):
            desc = job["title"]
        if not require_visa:
            desc += " visa sponsorship relocation support"
        score, note = score_job(job["title"], desc, job["company"], job.get("location", ""))
        # If score is 0 because of visa check, try career page fallback
        if score == 0 and "no mention of visa sponsorship" in note:
            career_url = job.get("url", "") or None
            has_visa = _check_career_page_visa(job["company"], career_url)
            if has_visa:
                desc += " visa sponsorship relocation support"
                score, note = score_job(job["title"], desc, job["company"], job.get("location", ""))
                note = (note + " | visa confirmed from career page").strip(" |")
        return score, note

    # Company ATS sources (not query-dependent - fetch all)
    all_sources = JOB_SOURCES + EU_JOB_SOURCES + GLOBAL_JOB_SOURCES + APAC_JOB_SOURCES + US_CANADA_JOB_SOURCES + MIDDLE_EAST_JOB_SOURCES
    for source in all_sources:
        sname = source["name"].lower()
        if sources_lower and not any(s in sname for s in sources_lower):
            continue
        if sources_lower and not any(s in source.get("ats", "").lower() for s in sources_lower):
            if not any(s in sname for s in sources_lower):
                continue
        jobs = fetch_jobs_from_source(source)
        for job in jobs:
            company_lower = job["company"].lower().strip()
            if exclude_lower and any(c in company_lower for c in exclude_lower):
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
                jobs = board_fn(q, location=location, max_results=max_results)
                for job in jobs:
                    company_lower = job["company"].lower().strip()
                    if exclude_lower and any(c in company_lower for c in exclude_lower):
                        continue
                    score, note = _score(job)
                    if score >= threshold:
                        salary_info = get_salary_info(job["company"], job["title"], job.get("description", ""))
                        resume = pick_resume(job["company"])
                        all_jobs.append({**job, "score": score, "relocation_note": note, "salary_info": salary_info, "resume": resume})
            except Exception:
                pass

    # Playwright scrapers
    for pw_name, pw_fn in pw_scrapers:
        if sources_lower and not any(s in pw_name.lower() for s in sources_lower):
            continue
        for q in expanded_queries:
            try:
                jobs = pw_fn(q, location=location, max_results=max_results)
                for job in jobs:
                    company_lower = job["company"].lower().strip()
                    if exclude_lower and any(c in company_lower for c in exclude_lower):
                        continue
                    score, note = _score(job)
                    if score >= threshold:
                        salary_info = get_salary_info(job["company"], job["title"], job.get("description", ""))
                        resume = pick_resume(job["company"])
                        all_jobs.append({**job, "score": score, "relocation_note": note, "salary_info": salary_info, "resume": resume})
            except Exception:
                pass

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
        parts.append(f"\nYour settings: threshold={threshold}% | location={location}")
        if exclude_companies:
            parts.append(f"Excluded companies: {', '.join(exclude_companies)}")
        parts.append("\nTry lowering the threshold or removing exclusions.")
        return "\n".join(parts)

    q_summary = ", ".join(expanded_queries[:5])
    lines = [f"# Job Search Results ({len(unique)} matches)"]
    lines.append(f"Queries: {q_summary}{' ...' if len(expanded_queries) > 5 else ''}")
    lines.append(f"Settings: threshold={threshold}% | require_visa={'yes' if require_visa else 'no'} | location={location}")
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


def _parse_resume(path: str) -> str:
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
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

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
