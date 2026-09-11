# Quick Start Guide: Running Job Search Scripts

## Fastest Way to Run Searches

### 1️⃣ India Backend Jobs (Quick - 2 mins)
```bash
python3 scripts/search_and_email_kamnee_india.py
```
**Output:** Email with ~15 India-based roles (avg 82% score)

### 2️⃣ Remote & EU Backend Jobs (Quick - 3 mins)
```bash
python3 scripts/search_and_email_kamnee_remote_eu.py
```
**Output:** 3 emails (Remote Boards, EU Boards, Tech-Specialized)

### 3️⃣ Run Both (5 mins total)
```bash
python3 scripts/search_and_email_kamnee_india.py && \
python3 scripts/search_and_email_kamnee_remote_eu.py
```

---

## What You'll Receive (Emails)

### Email 1: 🇮🇳 India Backend Jobs
- 15 roles from LinkedIn India, Indeed India, Instahyre
- Companies: Paytm, Rippling, Toast, JPMorganChase, LearnTube.ai, etc.
- Locations: Bangalore, Mumbai, Gurugram, Chennai
- Scores: 60-95%

### Email 2: 💼 Remote Boards  
- 3 roles from WeWorkRemotely, RemoteOK, Remotive
- Remote-first companies with visa sponsorship
- Scores: 65-75%

### Email 3: 💼 EU Boards
- 4 roles from Welcome to NL, English Job Search
- EU/Netherlands focus, visa-friendly
- Scores: 70-75%

### Email 4: 💼 Tech-Specialized
- 0-5 roles from Crossover (if available)
- Tech-focused platforms

---

## Recipient

All emails go to: **kamneemaran45@gmail.com**

(Modify in `scripts/search_and_email_kamnee_india.py` line with `recipient =` if needed)

---

## Email Contents

Each email includes:
✅ Job title, company, location  
✅ Score % with star rating  
✅ Direct apply link (clickable)  
✅ Board name for tracking  
✅ Avg score & stats  
✅ Metadata (searched boards, filtering criteria)

---

## Prerequisites

1. **Environment file (.env):**
   ```
   GMAIL_ADDRESS=your-email@gmail.com
   GMAIL_APP_PASSWORD=your-16-char-app-password
   ```

2. **Profile file (profiles/kamnee.json):**
   ```json
   {
     "name": "Kamnee Maran",
     "years_experience": 11,
     "current_role": "Staff Software Engineer",
     ...
   }
   ```

3. **Python 3.9+ with dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## Troubleshooting

**"No jobs found?"**
- Boards might be slow or down
- Try re-running in 10 mins
- Check internet connection

**"Email not sending?"**
- Verify Gmail credentials in .env
- Ensure GMAIL_APP_PASSWORD is 16-char app-specific password (not regular Gmail password)
- Check Gmail "Less Secure Apps" settings

**"Script takes 5+ minutes?"**
- LinkedIn can be slow (rate limiting)
- Normal behavior, wait for completion

---

## Next Steps

Once you receive emails:
1. **Check scores** - 75%+ are excellent matches
2. **Apply immediately** - Use the "Apply Now" links in emails
3. **Track applications** - Note company/date in tracker (coming soon)
4. **Follow up** - Recruiters respond 3-5 days later

---

## Schedule Daily Searches (Optional)

### macOS/Linux Cron Job
```bash
crontab -e

# Add these lines to run every day at 7 AM:
0 7 * * * cd /Users/kamnee.maran/Downloads/job-search-agent && python3 scripts/search_and_email_kamnee_india.py >/dev/null 2>&1
0 7 * * * cd /Users/kamnee.maran/Downloads/job-search-agent && python3 scripts/search_and_email_kamnee_remote_eu.py >/dev/null 2>&1
```

### Windows Task Scheduler
1. Create task "Kamnee India Jobs"
2. Trigger: Daily at 7 AM
3. Action: `python3 C:\path\to\scripts\search_and_email_kamnee_india.py`
4. Repeat for Remote/EU script

---

## Support

For issues or new features:
- Check logs in `.log` files
- Modify thresholds in script (e.g., `score_threshold=50` for more results)
- Add new boards by extending `india_boards` or `boards_config` dicts

