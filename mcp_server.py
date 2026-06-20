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
    search_skipthedrive,
    search_workingnomads,
    search_jobspresso,
    search_englishjobsearch,
    search_bulldogjob,
    search_workatstartup,
    parse_resume_pdf,
)

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = Server("job-search-agent")

tracker = JobTracker()

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
            description="Search for jobs across company ATS APIs (Greenhouse, Lever, Ashby), job boards (LinkedIn, Indeed, Naukri, Instahyre, Glassdoor, etc.), and remote job boards",
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
            title="Score a job posting against your profile",
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
            title="Check job application tracker status",
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
            title="Update job application status",
            description="Update the status of a tracked job (e.g. mark as applied, rejected, offer)",
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
                },
                "required": ["title", "company", "status"],
            },
        ),
        types.Tool(
            name="parse_resume",
            title="Parse a resume PDF",
            description="Extract name, email, skills, and experience years from a PDF resume file",
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
            title="Show your search profile",
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
- Scans 25+ job sources daily for matching roles
- Scores each job against your resume profile (skills, seniority, location, visa support)
- Tracks application statuses (new → applied → rejected → offer)
- Emails a daily digest of top matches
- Syncs results to Google Sheets

### Where it gets jobs

**Company ATS APIs** (direct, no scraping):
- Greenhouse (GitLab, Stripe, Airbnb, Dropbox, Datadog, Coinbase, Reddit, etc.)
- Lever (companies using Lever's hosted postings)
- Ashby (companies using Ashby's job board)

**Job boards** (web scraping):
- LinkedIn, Indeed, Naukri, Instahyre, Glassdoor, SimplyHired
- WeWorkRemotely, WomenInTech UK, SkipTheDrive

**Remote-focused boards** (Playwright headless browser):
- RemoteOK, WorkingNomads, Jobspresso, EnglishJobSearch.ch, BulldogJob.pl
- WorkAtAStartup (Y Combinator startups)

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
The engine pulls from three tiers:

**Tier 1 — ATS APIs (live, structured data)**
Greenhouse, Lever, Ashby. These return JSON with title, company, location, description, and posting date. No authentication required.

**Tier 2 — Web scraping (HTML parsing)**
LinkedIn Guest API, Indeed, Naukri, Instahyre, Glassdoor, SimplyHired, WeWorkRemotely, WomenInTech UK. Uses requests + cloudscraper to bypass basic anti-bot measures.

**Tier 3 — Headless browser (JavaScript-rendered)**
RemoteOK, WorkingNomads, Jobspresso, EnglishJobSearch, BulldogJob, WorkAtAStartup. Uses Playwright to render JS-heavy pages.

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
4. **Score** — each job is scored 0-100; only jobs above threshold (default 60) proceed
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
    ]
    pw_scrapers = [
        ("RemoteOK", search_remoteok),
        ("SkipTheDrive", search_skipthedrive),
        ("WorkingNomads", search_workingnomads),
        ("Jobspresso", search_jobspresso),
        ("EnglishJobSearch", search_englishjobsearch),
        ("BulldogJob", search_bulldogjob),
        ("WorkAtAStartup", search_workatstartup),
    ]

    sources_lower = [s.lower() for s in sources] if sources else []
    all_jobs = []

    # Company ATS sources
    for source in JOB_SOURCES:
        sname = source["name"].lower()
        if sources_lower and not any(s in sname for s in sources_lower):
            continue
        if sources_lower and not any(s in source.get("ats", "").lower() for s in sources_lower):
            if not any(s in sname for s in sources_lower):
                continue
        jobs = fetch_jobs_from_source(source)
        for job in jobs:
            score, note = score_job(
                job["title"], job["description"], job["company"], job.get("location", "")
            )
            if score > 0:
                all_jobs.append({**job, "score": score, "relocation_note": note})

    # Job board scrapers
    for board_name, board_fn in board_scrapers:
        if sources_lower and not any(s in board_name.lower() for s in sources_lower):
            continue
        try:
            jobs = board_fn(query, location=location, max_results=max_results)
            for job in jobs:
                score, note = score_job(
                    job["title"], job["description"], job["company"], job.get("location", "")
                )
                if score > 0:
                    all_jobs.append({**job, "score": score, "relocation_note": note})
        except Exception as e:
            all_jobs.append({
                "title": f"[error] {board_name}: {e}", "company": "", "location": "",
                "url": "", "description": "", "score": 0, "relocation_note": "",
            })

    # Playwright scrapers
    for pw_name, pw_fn in pw_scrapers:
        if sources_lower and not any(s in pw_name.lower() for s in sources_lower):
            continue
        try:
            jobs = pw_fn(query, location=location, max_results=max_results)
            for job in jobs:
                score, note = score_job(
                    job["title"], job["description"], job["company"], job.get("location", "")
                )
                if score > 0:
                    all_jobs.append({**job, "score": score, "relocation_note": note})
        except Exception as e:
            all_jobs.append({
                "title": f"[error] {pw_name}: {e}", "company": "", "location": "",
                "url": "", "description": "", "score": 0, "relocation_note": "",
            })

    # Deduplicate by (title, company)
    seen = set()
    unique = []
    for j in sorted(all_jobs, key=lambda x: x.get("score", 0), reverse=True):
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in seen and j["company"]:
            seen.add(key)
            unique.append(j)

    if not unique:
        return f"No matching jobs found for '{query}' in {location}."

    lines = [f"# Job Search Results — '{query}' in {location}"]
    lines.append(f"Found {len(unique)} matching jobs.\n")
    for j in unique[:max_results * 2]:
        score = j.get("score", 0)
        relo = f" — {j['relocation_note']}" if j.get("relocation_note") else ""
        lines.append(f"**{j['title']}** @ {j['company']}")
        lines.append(f"   Score: {score}%  |  Location: {j.get('location', 'N/A')}")
        lines.append(f"   URL: {j.get('url', 'N/A')}{relo}")
        lines.append("")
    return "\n".join(lines)


def _score_job(title: str, description: str, company: str, location: str = "Remote") -> str:
    score, note = score_job(title, description, company, location)
    resume = pick_resume(company)
    suggestions = tailoring_suggestion(title, description, company)
    c_url = company_url(company)
    has_visa = any(kw in (title + " " + description).lower() for kw in VISA_RELOCATION_KEYWORDS)
    in_friendly = any(co in company.lower() for co in RELOCATION_FRIENDLY)

    parts = [
        f"## Score: {score}% — {title} @ {company}",
        f"**Location:** {location}",
        f"**Recommended resume:** {resume}",
        f"**Company link:** {c_url}",
        f"**Visa/relocation mentioned:** {'Yes' if has_visa else 'No'}",
        f"**Relocation-friendly company:** {'Yes' if in_friendly else 'No'}",
    ]
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


def _update_tracker(title: str, company: str, status: str, notes: str = "") -> str:
    key = tracker.job_key(title, company)
    if key not in tracker.data["jobs"]:
        # Add it first
        tracker.add_job(title, company, status=status)
    ok = tracker.update_status(title, company, status, notes)
    if ok:
        return f"✅ Updated **{title}** @ {company} → **{status}**"
    else:
        return f"⚠️ Could not find '{title}' @ {company} in tracker. Use a search first so it gets tracked."


def _parse_resume(path: str) -> str:
    if not os.path.exists(path):
        return f"File not found: {path}"
    try:
        profile = parse_resume_pdf(path)
        parts = [
            f"## Resume: {profile.get('name', 'Unknown')}",
            f"**Email:** {profile.get('email', 'N/A')}",
            f"**Experience:** {profile.get('years_experience', 0)} years",
            f"**Skills ({len(profile.get('core_skills', []))}):**",
        ]
        skills = profile.get("core_skills", [])
        for i in range(0, len(skills), 10):
            parts.append("  " + ", ".join(skills[i:i + 10]))
        parts.append("")
        parts.append("*Tip: Use `get_profile` to see the active profile used for scoring.*")
        return "\n".join(parts)
    except Exception as e:
        return f"Error parsing resume: {e}"


def _get_profile() -> str:
    parts = [
        f"## Active Profile — {PROFILE['name']}",
        f"**Experience:** {PROFILE['years_experience']} years",
        f"**Core skills ({len(PROFILE['core_skills'])}):**",
    ]
    skills = PROFILE["core_skills"]
    for i in range(0, len(skills), 10):
        parts.append("  " + ", ".join(skills[i:i + 10]))
    parts.append(f"\n**Red-flag titles ({len(PROFILE['title_red_flags'])} patterns):**")
    for rf in PROFILE["title_red_flags"][:15]:
        parts.append(f"  - {rf}")
    if len(PROFILE["title_red_flags"]) > 15:
        parts.append(f"  ... and {len(PROFILE['title_red_flags']) - 15} more")
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
