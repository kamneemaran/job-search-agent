# Job‑Search Automation (MCP)

A lightweight Python “Job‑Search Mini‑Control‑Program” (MCP) that:

*   Loads and parses your resume (text format)
*   Fetches job‑board pages (configurable URLs)
*   Calculates a simple match score between your resume and each posting
*   Suggests which resume version to use
*   Sends optional email / WhatsApp notifications
*   Updates `job_application_tracker.md` with the jobs you apply to
*   Can be scheduled to run daily via **GitHub Actions**

> **Note:** This is a starter kit. Scraping each job board reliably requires custom logic per site. The provided code includes a generic fetcher and mock jobs for demonstration. Extend the fetcher as needed.

---

## Table of Contents

1. [Prerequisites](#prerequisites)  
2. [Repository Structure](#repo-structure)  
3. [Setup – Local Development](#setup--local-development)  
4. [Configuration (`.env`)](#configuration-env)  
5. [Running the App Locally](#running‑locally)  
6. [Adding Your Own Resume (Text/Plain‑Text)](#adding‑your‑resume)  
7. [Extending the Job Fetcher (Scraping)](#extending‑the‑fetcher)  
8. [Notification Options](#notification‑options)  
9. [GitHub Actions – Daily Run](#github‑actions)  
10. [Troubleshooting & FAQ](#troubleshooting)  

---

<a name="prerequisites"></a>
## 1. Prerequisites

* **Python 3.9+** (tested on macOS 13, Linux, Windows)  
* **Git** (to push to a GitHub repo)  
* Ability to install Python packages (`pip`)  
* Optional: **Gmail/App‑Password**, **Twilio** or another WhatsApp API if you want notifications  

---

<a name="repo-structure"></a>
## 2. Repository Structure

```
/Users/admin/Downloads/files/
│
├─ .env                 # configuration (do NOT commit this!)
├─ README.md            # <-- you are reading it
├─ job_application_tracker.md   # markdown table you will fill
│
├─ config.py            # loads .env values
├─ resume_parser.py     # parses resume text (string or file)
├─ job_fetcher.py       # generic webpage fetcher (BeautifulSoup)
├─ job_matcher.py       # simple scoring algorithm
├─ main_app.py          # orchestrator – runs the whole flow
│
└─ (optional) requirements.txt  # you can generate it with `pip freeze > requirements.txt`
```

---

<a name="setup--local-development"></a>
## 3. Setup – Local Development

### 3.1 Create a Python virtual environment (recommended)

```bash
cd /Users/admin/Downloads/files
python3 -m venv venv
source venv/bin/activate    # macOS/Linux
# .\venv\Scripts\activate   # Windows PowerShell
```

### 3.2 Install required packages

```bash
pip install --upgrade pip
pip install requests beautifulsoup4 python-dotenv pandas openai
# If you plan to use WhatsApp via Twilio:
pip install twilio
# If you prefer SendGrid for email:
pip install sendgrid
```

*(You can also create a `requirements.txt` and install with `pip install -r requirements.txt`.)*

---

<a name="configuration-env"></a>
## 4. Configuration (`.env`)

Copy the template below into a new file named `.env` **in the same folder**.

```ini
# -------------------------------------------------
# GENERAL SETTINGS
# -------------------------------------------------
# Comma‑separated list of job‑board URLs you want to scan.
# Add as many as you like; keep them short and use the base page.
TARGET_URLS=https://www.eurotechjobs.com/job_search,https://www.darwinrecruitment.com/,https://englishjobs.de/in/berlin/visa_sponsorship,https://www.personio.com,https://honeypot.io,https://www.levels.fyi/jobs/,https://wellfound.com/jobs,https://www.linkedin.com/jobs,https://www.indeed.com,https://www.glassdoor.com,https://remote.com/careers,https://weworkremotely.com,https://remoteok.com/,https://www.simplyhired.com,https://stackoverflow.com/jobs

# Path to your resume file (plain‑text). If you store the resume as PDF/DOCX,
# either convert it to .txt first or extend resume_parser.py to read those formats.
RESUME_PATH=/Users/admin/Downloads/files/job-search-agent/Kamnee_Maran_Resume_FAANG.txt   # <-- UPDATE THIS!

# Tracker file (already present)
APPLICATION_TRACKER_PATH=job_application_tracker.md

# -------------------------------------------------
# EMAIL NOTIFICATIONS (optional – Gmail example)
# -------------------------------------------------
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your_email@gmail.com
# SMTP_PASSWORD=***   # Use an App‑Password, not your login password
# EMAIL_FROM=your_email@gmail.com
# EMAIL_TO=you@example.com,other@example.com

# -------------------------------------------------
# WHATSAPP NOTIFICATIONS (optional – Twilio example)
# -------------------------------------------------
# TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# TWILIO_AUTH_TOKEN=your_t…oken
# TWILIO_PHONE_NUMBER=whatsapp:+14155238886   # Twilio sandbox number
# WHATSAPP_TO=+1xxxxxxxxxx,+1yyyyyyyyyy

# -------------------------------------------------
# OPENAI (optional – for advanced NLP matching)
# -------------------------------------------------
# OPENAI_API_KEY=sk-xxx…xxxx
```

*After editing, **never commit** `.env` to a public repo – it contains secrets.*

---

<a name="running‑locally"></a>
## 5. Running the App Locally

```bash
# Ensure the virtual environment is active
source venv/bin/activate   # macOS/Linux
# .\venv\Scripts\activate  # Windows

python main_app.py
```

What you should see:

1. **Resume Load & Parse** – prints a JSON view of the extracted data.  
2. **Job Fetching** – attempts to download each URL from `TARGET_URLS`.  
3. **Match Scoring** – runs the mock‑job example (real jobs need site‑specific parsing).  
4. **Notification Stubs** – prints email / WhatsApp “sent” messages if you filled in credentials.  
5. **Tracker Update** – appends rows to `job_application_tracker.md` for high‑score matches.

If everything works, you can start extending the scraper (see Section 7).

---

<a name="adding‑your‑resume"></a>
## 6. Adding Your Own Resume (Text)

The current parser expects **plain‑text**. To use your existing PDF or DOCX:

1. **Quick conversion (one‑off):**  
   ```bash
   # macOS/Linux – using `pandoc`
   pandoc "/Users/admin/Downloads/files/job-search-agent/Kamnee_Maran_Resume_FAANG.pdf" -t plain -o Kamnee_Maran_Resume_FAANG.txt
   ```
2. **Keep the `.txt` file next to the script** and update `RESUME_PATH` in `.env`.  

If you want a fully‑automatic PDF/DOCX parser, replace the stub in `resume_parser.py` with something like:

```python
from PyPDF2 import PdfReader
def load_pdf(path):
    reader = PdfReader(path)
    return "\n".join(page.extract_text() for page in reader.pages)
```

and call it when `RESUME_PATH` ends with `.pdf`.

---

<a name="extending‑the‑fetcher"></a>
## 7. Extending the Job Fetcher (Scraping)

`job_fetcher.py` currently returns **raw page text**. For production you’ll want to:

1. **Identify the HTML structure** of each job board (inspect element → find the job card container, title, description, link, date).  
2. **Write a site‑specific parser** that extracts an array of dictionaries:

```python
def parse_honeypot(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.select(".job-card"):        # <-- replace with real CSS selector
        title = card.select_one(".title").get_text(strip=True)
        url   = card.select_one("a")["href"]
        desc  = card.select_one(".description").get_text(" ", strip=True)
        date  = card.select_one(".date").get_text(strip=True)
        jobs.append({"title": title, "url": url, "description": desc, "date": date})
    return jobs
```

3. **Add a dispatcher** in `main_app.py` that calls the appropriate parser based on the source URL.

You can also use **official APIs** (if any) – many platforms (LinkedIn, Wellfound, Levels.fyi) provide JSON endpoints that are far easier to consume than HTML.

---

<a name="notification-options"></a>
## 8. Notification Options

### Email (Gmail)

*Enable “App passwords”* in your Google account, then fill `SMTP_USERNAME` and `SMTP_PASSWORD` in `.env`.  
Replace the placeholder `send_email_notification` with a real implementation using `smtplib` or a service like **SendGrid**.

### WhatsApp (Twilio)

1. Sign up at https://www.twilio.com/whatsapp  
2. Verify the **sandbox number** (`+14155238886`) and link it to your WhatsApp.  
3. Fill `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, and `WHATSAPP_TO`.  
4. The stub `send_whatsapp_notification` already uses `twilio.rest.Client` – just install the `twilio` package and uncomment the lines.

Both notification functions are currently **print‑only** for safety; swap them with actual send logic once you’re ready.

---

<a name="github-actions"></a>
## 9. GitHub Actions – Daily Run

### 9.1 Create a GitHub Repository

1. Push the entire folder to a new repo (e.g., `username/job-search-mcp`).  
2. **Do NOT commit** your `.env` file – add it to `.gitignore` (the template already includes it).

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/username/job-search-mcp.git
git push -u origin master
```

### 9.2 Add the Workflow file

Create a file at `.github/workflows/job_search.yml` (you can place it directly in the repo or create it locally and push):

```yaml
name: Daily Job Search

on:
  schedule:
    - cron: '0 9 * * *'   # Runs daily at 09:00 UTC (adjust to your preferred time)
  workflow_dispatch:       # Allows manual trigger from the GitHub UI

jobs:
  run-search:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'   # Or any 3.x you need

      - name: Install dependencies
        run: |
          python -m venv venv
          source venv/bin/activate
          pip install --upgrade pip
          pip install -r requirements.txt || pip install requests beautifulsoup4 python-dotenv pandas openai twilio

      - name: Populate .env (secrets)
        env:
          TARGET_URLS: ${{ secrets.TARGET_URLS }}
          RESUME_PATH: ${{ secrets.RESUME_PATH }}
          SMTP_SERVER: ${{ secrets.SMTP_SERVER }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USERNAME: ${{ secrets.SMTP_USERNAME }}
          SMTP_PASSWORD: *** secrets.SMTP_PASSWORD }}
          EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          TWILIO_ACCOUNT_SID: ${{ secrets.TWILIO_ACCOUNT_SID }}
          TWILIO_AUTH_TOKEN: *** secrets.TWILIO_AUTH_TOKEN }}
          TWILIO_PHONE_NUMBER: ${{ secrets.TWILIO_PHONE_NUMBER }}
          WHATSAPP_TO: ${{ secrets.WHATSAPP_TO }}
          OPENAI_API_KEY: *** secrets.OPENAI_API_KEY }}
        run: |
          cat <<EOF > .env
          TARGET_URLS=${TARGET_URLS}
          RESUME_PATH=${RESUME_PATH}
          SMTP_SERVER=${SMTP_SERVER}
          SMTP_PORT=${SMTP_PORT}
          SMTP_USERNAME=${SMTP_USERNAME}
          SMTP_PASSWORD=${SMTP_PASSWORD}
          EMAIL_FROM=${EMAIL_FROM}
          EMAIL_TO=${EMAIL_TO}
          TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
          TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
          TWILIO_PHONE_NUMBER=${TWILIO_PHONE_NUMBER}
          WHATSAPP_TO=${WHATSAPP_TO}
          OPENAI_API_KEY=${OPENAI_API_KEY}
          EOF

      - name: Run job‑search app
        env:
          PYTHONUNBUFFERED: 1
        run: |
          source venv/bin/activate
          python main_app.py
```

### 9.3 Add Repository Secrets

In the GitHub repo → Settings → Secrets → Actions → **New repository secret**, add each variable used above (`TARGET_URLS`, `RESUME_PATH`, `SMTP_SERVER`, etc.).  
*Never store raw passwords in the repo; secrets keep them safe.*

### 9.4 Verify the Run

After pushing the workflow file, you should see a **“Actions”** tab in GitHub. The job will run at the scheduled time, and you can manually trigger it via “Run workflow”.

---

<a name="troubleshooting"></a>
## 10. Troubleshooting & FAQ

| Issue | Quick Fix |
|------|------------|
| **`ModuleNotFoundError: No module named 'twilio'`** | Run `pip install twilio` inside your virtual env or add it to `requirements.txt`. |
| **Resume not loading** | Verify `RESUME_PATH` points to a **readable `.txt`** file. If you used PDF, convert it to text first. |
| **All match scores are 0** | The mock jobs are placeholders. Real scores appear only after you parse actual job postings with appropriate keywords. |
| **Email not sending** | Double‑check Gmail “App password” and that `SMTP_SERVER`/`SMTP_PORT` match the provider. Check spam folder. |
| **GitHub Action fails on `source venv/bin/activate`** | On Windows runners use `.\venv\Scripts\activate`. On Linux/macOS the line shown works. |
| **Too many false positives** | Tune `calculate_match_score` weights or add more restrictive keyword lists. |
| **Job board blocks my scraper** | Add a random `User‑Agent` header, increase `time.sleep` between requests, or use the site’s official API if available. |

---

### 🎉 You’re ready!

1. **Configure `.env`** (step 4)  
2. **Run locally** (`python main_app.py`) – confirm everything prints as expected.  
3. **Push to GitHub** and set up the Action (step 9) for automated daily runs.  

Feel free to ask for help on any of the steps—whether it’s fine‑tuning the scorer, writing a parser for a particular job board, or setting up secret management in GitHub. Good luck with the job hunt! 🚀