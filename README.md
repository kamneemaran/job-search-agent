# Job Search Agent

Automated job scanner that discovers, scores, and tracks job opportunities from 25+ sources. Runs as a daily cron job (email digest + Google Sheets) and also exposes interactive tools via an **MCP server** (Model Context Protocol).

---

## Features

- **Scans** company ATS APIs (Greenhouse, Lever, Ashby) + 15+ job boards (LinkedIn, Indeed, Naukri, Glassdoor, Instahyre, WeWorkRemotely, RemoteOK, etc.)
- **Scores** each job 0–100 against your profile (skills, seniority, location, visa/relocation support)
- **Visa Sponsor Discovery**: Scans visa-friendly job sources to build and maintain a sponsor database (~80+ companies). Sources include:
  - **IND register** (`ind.nl`) — official Dutch IND public register of ~12,900 recognised sponsors, scraped at startup; adds base name + full legal name for O(1) lookup
  - **Welcome to NL** (`welcome-to-nl.nl`) — managed by RVO (Netherlands Enterprise Agency); all listed jobs come from IND pre-approved highly skilled migrant sponsors
  - **VisaSponsor.Jobs** (`visasponsor.jobs`) — third-party aggregator of explicitly visa-sponsored roles
  - **Bundesagentur für Arbeit** (`arbeitsagentur.de`) — German Federal Employment Agency; IT roles typically qualify for EU Blue Card
  - **Career page scraping** — on-the-fly checks of company career pages for visa/relocation keywords via MCP server
  - **Manual research** — companies added/removed based on application feedback and research
  Companies in the sponsor database get automatic visa/relocation bonus points even when the JD itself is silent.
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
| `--threshold 70` | Minimum match score (default: 70) |
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

### Workflow Batches & Coverage

| Batch Name | Job Boards / Sources Covered | Approximate Count of Scanned Links/Endpoints | Regions Covered | Approximate Time Taken |
| :--- | :--- | :--- | :--- | :--- |
| **`ats`** | Direct ATS APIs (Greenhouse, Lever, Ashby, Manatal) | ~110+ custom company endpoints | Global / Remote | **1.5 – 3 minutes** (Uses rapid concurrent API requests) |
| **`boards-major`** | LinkedIn, Indeed, Naukri, Glassdoor, SimplyHired, WomenInTech, Instahyre | ~7 global job boards | Global, India, Remote | **4 – 6 minutes** (Runs concurrently where possible) |
| **`boards-AU-NZ`** | Seek, Jora | ~2 regional job boards | Australia, New Zealand | **2 – 3 minutes** |
| **`boards-eu`** | NetEmpregos, SAPOEmprego, Infoempleo, Bundesagentur, IamExpat, WorkInLux, IndeedNL, WelcomeToNL, TogetherAbroad, StepStone, Adzuna, Freelancermap, Intermediair, NationaleVacaturebank, Philips, Liebherr | ~14 European boards + 2 paginated enterprise portals | Germany, Netherlands, Luxembourg, Spain, Portugal, Switzerland, UK, EU | **6 – 10 minutes** *(Optimized)* |
| **`boards-remote`** | WeWorkRemotely, Remotive, ArcDev, RemoteOK, Himalayas, SkipTheDrive, WorkingNomads, Jobspresso, Arbeitnow, EnglishJobSearch, Bulldogjob, VisaSponsor, Incluso, Crossover, NoDesk, Workew, Kelly | ~17 dedicated remote job boards | Remote (Worldwide) | **5 – 8 minutes** *(Optimized)* |
| **`eu`** | Custom career pages for major European enterprises | ~220+ curated companies | UK, Germany, Netherlands, France, Switzerland, Nordics, etc. | **10 – 15 minutes** (Run concurrently in thread pool) |
| **`us-canada`** | Custom career pages for US & Canadian companies | ~150+ curated companies | USA, Canada | **8 – 12 minutes** (Run concurrently in thread pool) |
| **`apac`** | Custom career pages for APAC-based tech companies | ~50+ curated companies | Singapore, Japan, Australia, APAC | **3 – 5 minutes** (Run concurrently in thread pool) |
| **`middle-east`** | Custom career pages for Middle East enterprises | ~20+ curated companies | UAE, Saudi Arabia, Qatar, etc. | **2 – 3 minutes** (Run concurrently in thread pool) |
| **`global`** | Custom career pages for major multinational giants | ~50+ global enterprise portals | Global / Hybrid / Remote | **3 – 5 minutes** (Run concurrently in thread pool) |

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

## Scoring (0–100) — Resume-Adaptive

Scoring is **fully dynamic** based on the active resume. When `--resume` is provided, the system extracts skills, current role, and years of experience from the PDF and uses them for all scoring decisions.

### Hard Filters (instant reject = 0 score)

| Filter | Logic |
|--------|-------|
| Junior/entry-level | Rejects if JD contains "junior", "intern", "entry level", "graduate", "0-2 years" |
| Title red flags | Auto-detected from resume's domain (e.g., backend resume filters out frontend/mobile/QA titles) |
| Seniority too high | If resume has 6yr exp, rejects VP/Director/Principal titles that need 8-12+ years |
| Experience mismatch | Compares JD's explicit "X years required" against candidate's range |
| Travel required | Rejects roles mentioning mandatory travel |
| No visa/relocation | For non-India roles: hard rejects only if JD **explicitly** says no sponsorship (e.g., "cannot sponsor", "must be authorized to work"). Jobs without visa mention are kept with an informational note. |
| Language barrier | Rejects roles requiring non-English fluency |

### Scoring Components (after passing filters)

| Component | Max Points | How It Works |
|-----------|-----------|--------------|
| **Skill Match** | 50 | Counts how many of the resume's skills appear in the JD. Needs 40% of resume skills to match for full 50 points. Denominator scales with resume size (e.g., 14 skills = need 6 matches for max; 35 skills = need 14 matches). |
| **Title Relevance** | 30 | Derived from resume's `current_role`. Strips seniority prefix to get base role, then matches JD title against it + experience-appropriate variants. E.g., "SAP MM Consultant" with 6yr exp matches: "sap mm consultant", "senior sap mm consultant", "lead sap mm consultant". |
| **Seniority Fit** | 15 | Experience-aware: 10+ yr profiles get points for senior/staff/lead/principal. 5-9yr profiles for senior/lead. 3-5yr for mid-level. <3yr profiles get points for NOT requiring seniority. |
| **Relocation Bonus** | 5 | If company is in the known relocation-friendly list (80+ companies with confirmed visa sponsorship). |

**Max possible score: 100** (50 + 30 + 15 + 5)

### Scoring Examples

**Backend Engineer (10yr, current role: "Senior Software Engineer"):**

| Job Title | Skills in JD | Score | Outcome |
|-----------|-------------|-------|---------|
| Senior Backend Engineer | java, kafka, microservices, spring boot, k8s, aws, docker, distributed systems | 85% | Pass |
| Staff Software Engineer | python, golang, system design, redis, postgresql, architecture | 78% | Pass |
| Data Platform Engineer | python, aws, docker, ci/cd | 43% | Reject (below 70) |

**SAP Consultant (6yr, current role: "SAP MM Consultant"):**

| Job Title | Skills in JD | Score | Outcome |
|-----------|-------------|-------|---------|
| SAP Materials Management Consultant | sap, sap mm, procurement, inventory management, sap hana, configuration | 75% | Pass |
| SAP Functional Consultant | sap, configuration, functional consultant, procurement | 65% | Borderline |
| Senior Software Engineer | java, python, microservices, kafka | 15% | Reject |

### How Title Keywords Are Derived

From the resume's `current_role`, the system:
1. Strips seniority prefix ("Senior Software Engineer" -> "software engineer")
2. Generates experience-appropriate variants:
   - **10+ yr:** base, senior X, staff X, lead X, principal X, SDE-3/4/5
   - **5-9 yr:** base, senior X, lead X
   - **3-5 yr:** base, senior X
   - **<3 yr:** base only
3. Adds meaningful domain words (skipping generic "engineer"/"developer")

This means each resume automatically gets relevant title matching without manual configuration.

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

The system builds its scoring profile from the resume PDF (`--resume`). Manual overrides in `daily_scan.py`:

- `PROFILE["core_skills"]` — default tech stack (used when no resume is provided)
- `PROFILE["current_role"]` — default role for title matching
- `PROFILE["years_experience"]` — used for seniority / experience matching
- `PROFILE["seniority_keywords"]` — what counts as senior (used for search query expansion)
- `PROFILE["junior_red_flags"]` — entry-level patterns to reject
- `ROLE_DOMAINS` — domain definitions (backend, frontend, mobile, data_ml, devops_sre, sap_erp, qa, fullstack) with associated skills and red flags

When `--resume` is provided, these are auto-populated from the PDF:
- `core_skills` extracted from resume text (matched against 80+ known tech keywords)
- `current_role` from most recent job title
- `years_experience` from work history dates
- `title_red_flags` auto-configured by detecting the candidate's domain from their skills

See `AGENTS.md` for user preferences and tracker status definitions.
