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

## Google Sheets
- **Tracker sheet** (`job_matches`): https://docs.google.com/spreadsheets/d/1NO-erkRi_aV7RSY8dMbZkxEZBA9jEN55IfIrK3S8WEg/edit — tracks applied/rejected/offer status
- **Links sheet** (`1mgD6L5e6...`): https://docs.google.com/spreadsheets/d/1mgD6L5e6-5HLiuSYggCYi48LUONnul0lzoqfL2RYWpo/edit — master list of all companies & boards managed in batches
  - "Companies" tab (1260 rows): Name, URL, Region, ATS, Playwright
  - "Job Boards" tab (50 rows): Name, URL, Region, ATS, Playwright
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
  - `search_jobs` — on-demand job search across ATS APIs + 15+ job boards. Auto-expands to relevant title variants (senior/staff/principal + domain) based on profile. Shows salary from JD or Levels.fyi static table (35+ companies). Supports filters: `locations` (multi-select OR), `skills` (multi-select OR), `job_type` (full-time/contract), `work_mode` (remote/on-site/hybrid).
    - `require_visa` (default: true) — when true, jobs outside India without an explicit visa/relocation signal (from JD text, known-sponsor lists, IND register, or career page fallback) are filtered out with score=0. Set to false for exploratory searches; this injects synthetic visa keywords so all jobs score without the visa penalty, but does **not** guarantee the company actually sponsors.
  - `score_job` — score any job title/description against profile (0-100). Includes salary info.
  - `tracker_status` — view tracked jobs and their statuses
  - `update_tracker` — update job status (applied/rejected/offer). Jobs go to separate Google Sheet tabs organized by resume version.
  - `parse_resume` — parse a PDF resume. Optional `key` param registers it as a named version (e.g. `faang`, `general`). Shows all registered versions.
  - `list_resumes` — list registered resume versions and discover unregistered PDFs in the project directory.
  - `get_profile` — show active profile config and all resume versions
  - `email_digest` — trigger or schedule the email digest. `schedule='now'` sends immediately; 'tomorrow' schedules one-time; 'weekly'/'monthly' sets recurring; 'never' disables. Optional `email` to override recipient.
  - `prepare_application` — generates structured context (profile, match analysis, skill gaps, salary, resume) for an LLM to produce a cover letter draft, STAR+R stories, and gap mitigation plan. Run after scoring a job. Pass title, company, description, and optional url/resume.

---

## Multi-MCP Unified Workflow (JobPilot + Rezi + JobGPT)

You can combine the **Job Search Agent (JobPilot)**, **Rezi Resume MCP**, and **JobGPT MCP** into a single, fully-automated job search, resume tailoring, and auto-apply pipeline.

```
┌─────────────────────────────────┐      ┌─────────────────────────────┐      ┌─────────────────────────────┐
│    1. SEARCH & SCORE (JobPilot)  │ ───► │  2. TAILOR RESUME (Rezi)    │ ───► │   3. AUTO-APPLY (JobGPT)    │
│  - Find highly aligned jobs     │      │  - Load & read Rezi resume  │      │  - Import job by URL        │
│  - Profile scoring (0-100)      │      │  - Target skill gap context │      │  - Submit tailored resume   │
│  - Build LLM application context│      │  - Update & save on Rezi    │      │  - Outreach to recruiters   │
└─────────────────────────────────┘      └─────────────────────────────┘      └─────────────────────────────┘
```

### Complete Multi-MCP Client Configurations

#### 1. Cursor Configuration (`.cursor/mcp.json`)
We have pre-configured Cursor in `.cursor/mcp.json`. It will automatically enable all three servers in parallel:
```json
{
  "mcpServers": {
    "job-search-agent": {
      "command": "/Users/kamnee.maran/Downloads/job-search-agent/.venv/bin/python",
      "args": ["/Users/kamnee.maran/Downloads/job-search-agent/mcp_server.py"],
      "env": {}
    },
    "rezi": {
      "type": "http",
      "url": "https://api.rezi.ai/mcp"
    },
    "jobgpt": {
      "type": "http",
      "url": "https://mcp.6figr.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_JOBGPT_API_KEY"
      }
    }
  }
}
```

#### 2. Claude Desktop Configuration (`claude_desktop_config.json`)
To integrate all three servers into Claude Desktop, copy this configuration into your `claude_desktop_config.json` (located at `~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "job-search-agent": {
      "command": "/Users/kamnee.maran/Downloads/job-search-agent/.venv/bin/python",
      "args": [
        "/Users/kamnee.maran/Downloads/job-search-agent/mcp_server.py"
      ],
      "env": {}
    },
    "rezi": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://api.rezi.ai/mcp"
      ],
      "env": {}
    },
    "jobgpt": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://mcp.6figr.com/mcp",
        "--header",
        "Authorization:Bearer YOUR_JOBGPT_API_KEY"
      ],
      "env": {}
    }
  }
}
```

#### 3. Claude Code (CLI) Configuration
Install each server on Claude Code directly using the CLI:
```bash
# Add Job Search Agent (Local python script)
claude mcp add job-search-agent -- /Users/kamnee.maran/Downloads/job-search-agent/.venv/bin/python /Users/kamnee.maran/Downloads/job-search-agent/mcp_server.py

# Add Rezi Resume MCP (Remote Streamable HTTP)
claude mcp add rezi --transport http https://api.rezi.ai/mcp

# Add JobGPT MCP (Remote HTTP with Auth token)
claude mcp add jobgpt -t http -u https://mcp.6figr.com/mcp --header "Authorization: Bearer YOUR_JOBGPT_API_KEY"
```

---

### Step-by-Step Orchestrated Workflow

When talking to your AI assistant (e.g. Cursor or Claude Desktop), you can trigger this end-to-end flow with a single prompt:

1. **Step 1: On-Demand Job Search & Score**
   - **Action:** Ask the assistant to find open roles.
   - **Assistant execution:** Calls `job-search-agent` → `search_jobs` to scour 15+ job boards and 110+ company endpoints, score each match 0-100, and filter out red flags.
   - **Application Context:** Run `prepare_application` on the highest scoring job to extract skill gap insights and tailored resume instructions.

2. **Step 2: Resume Tailoring in Rezi**
   - **Action:** Tell the assistant: *"Tailor my Rezi resume for this role."*
   - **Assistant execution:** 
     1. Calls `rezi` → `list_resumes` and `read_resume` to pull your baseline resume JSON structure.
     2. Analyzes the target job requirements and compares it with your current skills.
     3. Rewrites bullet points, highlights matching skills, and adjusts title focus.
     4. Calls `rezi` → `write_resume` to push the tailored resume version directly into your Rezi dashboard.

3. **Step 3: Auto-Apply & Tracking via JobGPT**
   - **Action:** Tell the assistant: *"Submit the application and start tracking."*
   - **Assistant execution:**
     1. Calls `jobgpt` → `import_job_by_url` to load the job from the company career page.
     2. Calls `jobgpt` → `generate_resume_for_job` (or links your Rezi-tailored PDF).
     3. Calls `jobgpt` → `apply_to_job` to submit the job application on your behalf.
     4. Calls `jobgpt` → `get_job_recruiters` / `get_job_referrers` and drafts referral/recruiter outreach messages.

4. **Step 4: Update JobPilot Tracker**
   - **Action:** Calls `job-search-agent` → `update_tracker` with status `applied` to sync your master Google Sheets and notify you in your next email digest.

