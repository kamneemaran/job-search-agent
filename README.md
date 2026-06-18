# Daily Job Matching Agent — Setup Guide

This runs a daily scan of your job sources, scores each posting against your
resume profile, picks the right resume version, and emails you a digest —
fully automatically, for free, using GitHub Actions.

## What this does and does NOT do

**Does:**
- Scans job sources daily on a schedule (no laptop needed — runs in GitHub's cloud)
- Scores roles 0–100 based on skill/seniority keyword match
- Flags relocation risk (e.g. the Mollie no-relocation lesson is baked in)
- Picks FAANG vs Indian Tech vs General resume per company
- Emails you a daily digest via Gmail
- Optionally sends a WhatsApp ping for the top match (requires Twilio setup)

**Does NOT do:**
- Auto-apply to jobs (intentionally — see our earlier discussion on why
  targeted manual applications beat bulk auto-apply for senior roles)
- Scrape every site out of the box. Lever-based career pages (like Picnic)
  work immediately via their public API. Other sites need either a Greenhouse
  API hookup (same pattern) or a custom scraper — see `fetch_jobs_from_source()`
  in `daily_scan.py` for where to extend this.

## One-time setup (about 20 minutes)

### Step 1 — Create a GitHub account (if you don't have one)
Free, at github.com.

### Step 2 — Create a new repository
1. Click "New repository" → name it e.g. `job-search-agent`
2. Set it to **Private** (your job search strategy stays private)
3. Upload these three files, keeping the folder structure:
   - `daily_scan.py`
   - `.github/workflows/daily_scan.yml`
   - `README.md` (this file)

### Step 3 — Create a Gmail App Password
Regular Gmail passwords won't work for automated sending. You need an "App Password":
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification if not already on
3. Search "App passwords" → create one named "Job Agent"
4. Copy the 16-character password shown (you won't see it again)

### Step 4 — Add secrets to your GitHub repository
In your repo: Settings → Secrets and variables → Actions → New repository secret

Add these two (required):
| Name | Value |
|---|---|
| `GMAIL_ADDRESS` | kamneemaran45@gmail.com |
| `GMAIL_APP_PASSWORD` | the 16-character app password from Step 3 |

Optional (only if you want WhatsApp pings):
| Name | Value |
|---|---|
| `TWILIO_SID` | from twilio.com console |
| `TWILIO_AUTH_TOKEN` | from twilio.com console |
| `TWILIO_WHATSAPP_FROM` | e.g. `whatsapp:+14155238886` (Twilio sandbox number) |
| `WHATSAPP_TO` | your number, e.g. `whatsapp:+917387233268` |

Twilio's WhatsApp sandbox is free for testing but requires you to send an
opt-in message once. For a permanent production number, Twilio charges a
small monthly fee — Gmail-only is the simpler free path if you'd rather skip this.

### Step 5 — Test it manually
In your repo: Actions tab → "Daily Job Scan" → "Run workflow" button.
Check your Gmail inbox a minute later.

### Step 6 — Let it run automatically
Once the secrets are set, the workflow in `daily_scan.yml` runs every day at
06:30 UTC (~12:00 PM IST) with zero further action from you.

## Extending the scanner to more sites

Right now only Lever-based sources (like Picnic) pull live jobs automatically.
To add a new company:

1. Check if they use Lever: visit `https://jobs.lever.co/{company-name}`
2. Check if they use Greenhouse: visit `https://boards.greenhouse.io/{company-name}`
3. If either works, just add the URL to `JOB_SOURCES` in `daily_scan.py` —
   the existing Lever code path will pick it up automatically. For Greenhouse,
   uncomment and complete the `elif "greenhouse.io"` block.
4. If neither — the company needs a custom scraper, which is more fragile
   and not included here to keep this maintainable.

## Updating the resume-to-company mapping

Edit `COMPANY_RESUME_MAP` in `daily_scan.py` as you target new companies.

## Updating relocation intelligence

Edit `NO_RELOCATION_FLAGS` and `RELOCATION_FRIENDLY` as you learn more —
this is exactly where the Mollie lesson is encoded so it never gets missed again.
