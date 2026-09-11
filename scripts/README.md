# Job Search Scripts

Reusable Python scripts for searching and emailing job opportunities.

## Available Scripts

### 1. Search Kamnee India Backend Jobs
**File:** `search_and_email_kamnee_india.py`

Search India-based backend engineer jobs for Kamnee (11-year Staff Backend Engineer) profile and send email with results.

**Usage:**
```bash
python3 scripts/search_and_email_kamnee_india.py
```

**What it does:**
- Searches 3 Indian job boards: LinkedIn India, Indeed India, Instahyre
- Filters for seniority: Senior/Staff/Lead/Principal/Architect roles only
- Applies scoring: 60%+ match threshold
- Sends formatted HTML email to `kamneemaran45@gmail.com`
- Includes: Job title, company, location, score (%), apply link

**Output:**
- Email with all matched roles grouped by board
- Average score, total job count, board breakdown

---

### 2. Search Kamnee Remote & EU Backend Jobs
**File:** `search_and_email_kamnee_remote_eu.py`

Search Remote and EU backend engineer jobs for Kamnee profile across 6 boards (WeWorkRemotely, RemoteOK, Remotive, Welcome to NL, English Job Search, Crossover).

**Usage:**
```bash
python3 scripts/search_and_email_kamnee_remote_eu.py
```

**What it does:**
- Searches 6 global job boards: 3 remote-focused + 3 EU-focused
- Filters for seniority: Senior/Staff/Lead/Principal/Architect roles only
- Applies scoring: 60%+ match threshold
- Sends 3 separate category emails (Remote Boards, EU Boards, Tech-Specialized)
- Each email includes: Job listings with scores, apply links, visa badges

**Output:**
- 3 emails (one per category)
- Remote email: High visa sponsorship signal
- EU email: Europe/Netherlands focus
- Tech email: Tech-specialized boards

---

## Configuration

All scripts use:
- **Profile:** `profiles/kamnee.json` (11-year Staff Backend Engineer)
- **Environment:** `.env` (Gmail credentials)
- **Scoring Engine:** `daily_scan.py` (from root)

### Required Environment Variables (.env)
```
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

---

## Scoring Criteria

All scripts apply the same scoring system (0-100):

| Component | Points | Details |
|-----------|--------|---------|
| **Skill Match** | 0-50 | Core (Java, Python, Kafka, etc.) + Bonus (gRPC, GraphQL, etc.) |
| **Title Relevance** | 0-30 | Full match (30), Partial (10), Skill inference (15-20) |
| **Seniority** | 0-15 | Title keyword (15), Body mention (10), Experience bonus (10) |
| **Visa Support** | 0-10 | Remote/Intl only - Visa (5) + Relocation (5) |
| **TOTAL** | **0-100** | Threshold: 60%+ |

### Hard Filters (Score = 0 if any fail)
- ❌ No seniority keyword (Staff/Senior/Lead/Principal/Architect/Director)
- ❌ Career track mismatch (DevOps, Frontend, Mobile, QA, SAP, Data Science, ML)
- ❌ Experience out of range (9-14 years for 11-year candidate)
- ❌ Travel > 25%
- ❌ Non-English language required
- ❌ Blacklist (PhonePe)

---

## Output Format

### Email Structure
Each email contains:
1. **Header** with category name and profile
2. **Stats** showing total jobs, boards, average score
3. **Job Listings** grouped by board:
   - Job title
   - Company name
   - Location
   - Score with star rating (⭐⭐⭐ = 60-70%, ⭐⭐⭐⭐ = 70-85%, ⭐⭐⭐⭐⭐ = 85%+)
   - Direct "Apply Now" link (clickable)
4. **Footer** with search methodology

### Email Examples

**Remote Boards Email:**
- Contains: 3-10 remote-first backend roles
- Color: Blue (#2563EB)
- Highlight: Visa sponsorship badges

**EU Boards Email:**
- Contains: 2-5 EU/Netherlands backend roles
- Color: Green (#00D084)
- Highlight: IND-registered companies

**India Boards Email:**
- Contains: 8-15 India-based backend roles
- Color: Saffron (#FF9933)
- Highlight: Metro locations (Bangalore, Mumbai, Gurugram, etc.)

---

## Recent Results

### India Search (2024-09-02)
- **Total jobs:** 15
- **Avg score:** 82%
- **Top scorer:** 95% (Paytm - Senior Backend @ Noida)
- **Boards:** LinkedIn India, Indeed India, Instahyre
- **Distribution:** 9 LinkedIn, 4 Indeed, 2 Instahyre

### Remote & EU Search (2024-09-02)
- **Remote:** 3 jobs (Salesforge, A.Team, others)
- **EU:** 4 jobs (Abbott, DataSnipper, others)
- **Tech:** 0 jobs
- **Avg score:** 72%

---

## Troubleshooting

### Issue: "No jobs found"
- Try lowering score threshold from 60% to 50% in script
- Check if boards are experiencing downtime
- Verify profile matches seniority filters

### Issue: Email not sending
- Verify `.env` has `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`
- Ensure Gmail App Password (16 chars) is used, not regular password
- Check Gmail account is not blocking app access

### Issue: Script timeouts
- Some boards (Naukri, Glassdoor) can be slow
- Remove slow boards from `india_boards` dict
- Or increase timeout from 120s to 180s

---

## How to Run Scheduled Searches

### Option 1: Manual (Every morning)
```bash
# Run both India and Remote/EU searches
python3 scripts/search_and_email_kamnee_india.py
python3 scripts/search_and_email_kamnee_remote_eu.py
```

### Option 2: Automated (macOS/Linux with cron)
```bash
# Edit crontab
crontab -e

# Add lines to run every morning at 7 AM
0 7 * * * cd /Users/kamnee.maran/Downloads/job-search-agent && python3 scripts/search_and_email_kamnee_india.py
0 7 * * * cd /Users/kamnee.maran/Downloads/job-search-agent && python3 scripts/search_and_email_kamnee_remote_eu.py
```

### Option 3: GitHub Actions (Automated cloud runs)
Create `.github/workflows/daily-search.yml`:
```yaml
name: Daily Job Search
on:
  schedule:
    - cron: '0 7 * * *'  # 7 AM UTC
jobs:
  search:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Search India Jobs
        run: python3 scripts/search_and_email_kamnee_india.py
      - name: Search Remote/EU Jobs
        run: python3 scripts/search_and_email_kamnee_remote_eu.py
```

---

## Future Scripts to Create

- [ ] `search_and_email_pradeep_sap.py` - SAP MM/EWM jobs for Pradeep
- [ ] `search_and_email_kamnee_combined.py` - All locations in one script
- [ ] `filter_and_apply_jobs.py` - Auto-apply to 60%+ jobs (integration with job board APIs)
- [ ] `email_digest.py` - Weekly combined digest of all searches
- [ ] `track_applications.py` - Sync applied jobs to Google Sheets

---

## Notes

- Scripts inherit all scoring logic from `daily_scan.py`
- Profiles can be extended by modifying `profiles/kamnee.json`
- Each board search includes retry logic for network failures
- Deduplication prevents same job appearing multiple times
- All timestamps are in IST (Indian Standard Time)
