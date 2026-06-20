# User Preferences

## Job Filtering
Filter out these role types in `daily_scan.py` → `PROFILE["title_red_flags"]`:
- **Mobile:** android, ios, swift, kotlin
- **Frontend:** frontend, front-end, front end, ui engineer, web engineer
- **QA:** qa, qa engineer, quality assurance, quality engineer, test engineer, sdet, automation engineer
- **Network/SRE:** network infrastructure, network engineer, network architect, sre, site reliability engineer, devops, devops engineer

## Tracker Statuses
- `new` - not yet applied
- `applied` - application submitted (skipped in future scans)
- `rejected` - not moving forward or not relevant (skipped in future scans)
- `offer` - offer received

## Google Sheet
- Sheet: `job_matches` at https://docs.google.com/spreadsheets/d/1NO-erkRi_aV7RSY8dMbZkxEZBA9jEN55IfIrK3S8WEg/edit
- "Resume" column replaced with "Company Link" (career page or LinkedIn company URL)

## MCP Server
- Server entry: `mcp_server.py` — exposes job search tools via Model Context Protocol (MCP)
- Python venv: `.venv/` (Python 3.12, mcp SDK installed)
- Run with: `.venv/bin/python mcp_server.py`
- Connect from any MCP host (Claude Desktop, Cursor, VS Code etc.) with command:
  ```
  .venv/bin/python /Users/admin/repo/job-search-agent/mcp_server.py
  ```
- **Tools available:**
  - `about` — describes the job search engine (sources, scoring, how it works)
  - `search_jobs` — on-demand job search across ATS APIs + 15+ job boards
  - `score_job` — score any job title/description against profile (0-100)
  - `tracker_status` — view tracked jobs and their statuses
  - `update_tracker` — update job status (applied/rejected/offer)
  - `parse_resume` — parse a PDF resume
  - `get_profile` — show active profile config
