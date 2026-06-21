# Job Search Agent

Automated job scanner that discovers, scores, and tracks job opportunities from 25+ sources. Runs as a daily cron job (email digest + Google Sheets) and also exposes interactive tools via an **MCP server** (Model Context Protocol).

---

## Features

- **Scans** company ATS APIs (Greenhouse, Lever, Ashby) + 15+ job boards (LinkedIn, Indeed, Naukri, Glassdoor, Instahyre, WeWorkRemotely, RemoteOK, etc.)
- **Scores** each job 0–100 against your profile (skills, seniority, location, visa/relocation support)
- **Filters** out irrelevant roles (mobile, frontend, QA, SRE, network, non-engineering tracks)
- **Tracks** applications with statuses: `new` → `applied` → `rejected` → `offer`
- **Emails** daily digest of top matches
- **Syncs** to Google Sheets automatically
- **Auto-detects** rejections from Gmail inbox

---

## Quick Start

### Daily scan (scheduled)

```bash
python daily_scan.py
```

Optional flags:

| Flag | Description |
|------|-------------|
| `--resume path/to/resume.pdf` | Auto-detect profile from PDF |
| `--threshold 70` | Minimum match score (default: 60) |
| `--name "Your Name"` | Override profile name |
| `--skills "java, python, aws"` | Override skills |
| `--exp 8` | Override experience years |

### GitHub Actions workflow (CI)

Trigger a scan manually from **Actions > Daily Job Scan > Run workflow**.

Required inputs:

| Input | Description |
|-------|-------------|
| `batch` | Which batch to run: `all`, `1` (company ATS), `2` (job boards), or `3` (Playwright) |
| `resume_url` | Direct download URL to your resume PDF |

**Getting a Google Drive resume URL:**

```
Copied link:  https://drive.google.com/file/d/FILE_ID/view
Correct URL:  https://drive.google.com/uc?export=download&id=FILE_ID
```

The file ID is the string between `/d/` and `/view`. Append `&confirm=t` if the download fails.

**Required secrets** (set in repo **Settings > Secrets and variables > Actions**):

| Secret | Description |
|--------|-------------|
| `GMAIL_ADDRESS` | Gmail address for sending email |
| `GMAIL_APP_PASSWORD` | Gmail App Password |
| `GSHEET_ID` | Google Sheet ID for sync |
| `GSHEET_SERVICE_ACCOUNT_JSON` | Full JSON content of `gsheet_service_account.json` |

The job tracker persists across workflow runs by loading from Google Sheets at startup, so applied/rejected jobs are remembered.

### Interactive MCP server

```bash
.venv/bin/python mcp_server.py
```

Connect from any MCP host (Claude Desktop, Cursor, VS Code etc.) to get tools for on-demand job search, scoring, tracking, and resume parsing.

---

## Project Structure

```
├── daily_scan.py          # Main scanner, scorers, scrapers, email, sheets sync
├── mcp_server.py          # MCP server exposing interactive tools
├── config.py              # Environment variable loader
├── job_fetcher.py         # Generic HTTP fetcher
├── job_matcher.py         # Keyword-based match scoring
├── resume_parser.py       # Resume text parser
├── job_tracker.json       # Persistent application tracker
├── last_scan_results.json # Last scan output cache
├── AGENTS.md              # AI assistant configuration
└── .venv/                 # Python 3.12 virtual environment
```

---

## Job Sources

| Tier | Sources | Method |
|------|---------|--------|
| **ATS APIs** | Greenhouse (GitLab, Stripe, Airbnb, Dropbox, Datadog, Coinbase, etc.), Lever, Ashby | Public JSON endpoints, no auth |
| **Job boards** | LinkedIn, Indeed, Naukri, Instahyre, Glassdoor, SimplyHired, WeWorkRemotely, WomenInTech UK | HTML scraping (requests + cloudscraper) |
| **Remote boards** | RemoteOK, WorkingNomads, Jobspresso, EnglishJobSearch, BulldogJob, WorkAtAStartup (YC) | Playwright headless browser |

---

## Scoring (0–100)

1. **Red-flag check** — junior roles, non-relevant titles, travel requirements → immediate 0
2. **Seniority filter** — rejects if title is too senior for your experience
3. **Experience range** — matches JD's explicit experience requirements
4. **Visa/relocation** — for non-India roles, requires sponsorship keywords or known friendly company
5. **Language filter** — rejects non-English roles
6. **Skill match** — up to 60pts for keyword overlap with your core skills
7. **Seniority bonus** — 25pt (senior/staff/lead/principal) or 10pt
8. **Relocation bonus** — 15pt for relocation-friendly companies

---

## Environment Variables (`.env`)

| Variable | Description |
|----------|-------------|
| `GMAIL_ADDRESS` | Gmail address for sending email |
| `GMAIL_APP_PASSWORD` | Gmail App Password |
| `EMAIL_TO` | Email recipient (defaults to GMAIL_ADDRESS) |
| `GSHEET_ID` | Google Sheet ID for sync |
| `GSHEET_SERVICE_ACCOUNT` | Path to service account JSON |

---

## Configuration

Edit `PROFILE` in `daily_scan.py` to customize:
- `core_skills` — your tech stack keywords
- `years_experience` — used for seniority / experience matching
- `title_red_flags` — role titles to exclude
- `seniority_keywords` — what counts as senior
- `junior_red_flags` — entry-level patterns to reject

See `AGENTS.md` for user preferences and tracker status definitions.
