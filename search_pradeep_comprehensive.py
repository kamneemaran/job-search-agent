"""
COMPREHENSIVE SAP JOB SEARCH - ALL EUROPEAN BOARDS
Sends results to Pradeep with board sources
"""
import daily_scan
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from datetime import datetime

def extract_posted_date_days_ago(posted_at):
    if not posted_at or posted_at == "Unknown":
        return 999
    
    try:
        if isinstance(posted_at, str):
            match = re.search(r'(\d+)\s+days?\s+ago', posted_at.lower())
            if match:
                return int(match.group(1))
            
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]:
                try:
                    post_date = datetime.strptime(posted_at.split()[0], fmt)
                    days_old = (datetime.now() - post_date).days
                    return days_old
                except:
                    continue
            return 999
        else:
            days_old = (datetime.now() - posted_at).days
            return days_old
    except:
        return 999

def is_european_location(location):
    european = [
        "uk", "united kingdom", "germany", "france", "italy", "spain",
        "netherlands", "belgium", "switzerland", "austria", "poland",
        "portugal", "greece", "finland", "sweden", "norway", "denmark",
        "ireland", "czechia", "czech republic", "hungary", "romania",
        "luxembourg", "slovenia", "croatia", "bulgaria", "malta", "cypress",
        "london", "paris", "berlin", "amsterdam", "zurich", "vienna",
        "warsaw", "prague", "budapest", "lisbon", "athens", "dublin", "madrid", "barcelona",
        "europe", "remote"
    ]
    location_lower = location.lower()
    return any(country in location_lower for country in european)

def has_visa_keyword(text):
    keywords = ["visa", "sponsorship", "sponsor", "relocation", "international", "work permit"]
    return any(kw in text.lower() for kw in keywords)

print("\n" + "=" * 160)
print("COMPREHENSIVE SAP JOB SEARCH - PRADEEP")
print("=" * 160)
print()

# All reliable European boards
reliable_boards = [
    ("LinkedIn UK", daily_scan.search_linkedin_uk),
    ("LinkedIn Germany", daily_scan.search_linkedin_de),
    ("LinkedIn France", daily_scan.search_linkedin_fr),
    ("LinkedIn Italy", daily_scan.search_linkedin_it),
    ("Indeed UK", daily_scan.search_indeed_uk),
    ("Indeed Germany", daily_scan.search_indeed_de),
    ("Indeed Netherlands", daily_scan.search_indeed_nl),
    ("Indeed Greece", daily_scan.search_indeed_gr),
    ("Indeed Finland", daily_scan.search_indeed_fi),
    ("Glassdoor UK", daily_scan.search_glassdoor_uk),
    ("Glassdoor Germany", daily_scan.search_glassdoor_de),
    ("Welcome to NL", daily_scan.search_welcome_to_nl),
    ("Working In Finland", daily_scan.search_workinfinland),
    ("WorkInLux", daily_scan.search_workinlux),
    ("EURES", daily_scan.search_eures),
]

jobs_by_board = {}
print("SEARCHING 15 EUROPEAN BOARDS")
print("-" * 160)

for board_name, search_func in reliable_boards:
    try:
        print(f"{board_name:30}", end=" ", flush=True)
        jobs = search_func("SAP consultant", "Europe", max_results=15)
        jobs_by_board[board_name] = jobs
        print(f"✓ {len(jobs):2} jobs")
    except Exception as e:
        print(f"✗ TIMEOUT/ERROR")
        jobs_by_board[board_name] = []

print()

# Filter matches
matches = []
seen_urls = set()

for board_name, jobs in jobs_by_board.items():
    for job in jobs:
        url = job.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        
        title = job.get("title", "")
        location = job.get("location", "")
        posted_at = job.get("posted_at", "")
        desc = job.get("description", "")[:300]
        company = job.get("company", "")
        
        loc_ok = is_european_location(location)
        days_old = extract_posted_date_days_ago(posted_at)
        days_ok = days_old <= 14
        has_sap = "sap" in (title + " " + desc).lower()
        
        if not (loc_ok and days_ok and has_sap):
            continue
        
        has_visa = has_visa_keyword(title + " " + desc)
        
        matches.append({
            "title": title,
            "company": company,
            "location": location,
            "posted_at": posted_at,
            "url": url,
            "board": board_name,
            "days_old": days_old,
            "has_visa": has_visa,
        })

# Sort by visa, then by days
matches.sort(key=lambda x: (not x["has_visa"], x["days_old"]))

# Group by board
board_distribution = {}
for match in matches:
    board = match['board']
    if board not in board_distribution:
        board_distribution[board] = []
    board_distribution[board].append(match)

visa_count = sum(1 for m in matches if m['has_visa'])

print(f"Total jobs evaluated: {sum(len(jobs) for jobs in jobs_by_board.values())}")
print(f"Total SAP jobs found: {len(matches)}")
print(f"  - With visa/relocation info: {visa_count}")
print(f"  - From {len(board_distribution)} boards")
print()

# Generate HTML email
html = f"""<html><head><style>
body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
.container {{ max-width: 1300px; margin: 0 auto; background: white; padding: 35px; box-shadow: 0 2px 15px rgba(0,0,0,0.1); }}
.header {{ background: linear-gradient(135deg, #0066cc 0%, #003d99 100%); color: white; padding: 35px; border-radius: 10px; margin-bottom: 30px; }}
.header h1 {{ margin: 0; font-size: 28px; font-weight: bold; letter-spacing: 0.5px; }}
.header p {{ margin: 10px 0 0 0; font-size: 15px; opacity: 0.95; }}
.summary {{ background: #e6f2ff; border-left: 6px solid #0066cc; padding: 25px; border-radius: 8px; margin-bottom: 30px; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 15px; }}
.summary-label {{ font-weight: bold; color: #0066cc; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
.summary-value {{ font-size: 20px; font-weight: bold; color: #003d99; margin-top: 8px; }}
.board-section {{ margin-bottom: 35px; background: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; }}
.board-header {{ background: linear-gradient(90deg, #0066cc 0%, #003d99 100%); color: white; padding: 18px 20px; font-size: 15px; font-weight: bold; }}
.board-jobs {{ padding: 20px; }}
.job {{ border: 1px solid #e5e7eb; border-left: 5px solid #0066cc; padding: 20px; margin-bottom: 15px; background: white; border-radius: 6px; transition: all 0.2s; }}
.job:hover {{ background: #f8f9fa; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.job-num {{ display: inline-block; background: #0066cc; color: white; padding: 3px 9px; border-radius: 4px; font-size: 12px; font-weight: bold; margin-right: 10px; }}
.job-title {{ font-size: 15px; font-weight: bold; color: #003d99; margin-bottom: 8px; }}
.job-company {{ font-size: 13px; color: #4b5563; font-weight: 600; margin: 5px 0; }}
.job-location {{ font-size: 12px; color: #6b7280; margin: 5px 0; }}
.job-posted {{ font-size: 11px; color: #9ca3af; margin: 6px 0; }}
.visa-badge {{ background: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 10px; display: inline-block; }}
.job-link a {{ background: #0066cc; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold; display: inline-block; margin-top: 12px; transition: background 0.2s; }}
.job-link a:hover {{ background: #003d99; }}
.board-summary {{ font-size: 12px; color: #666; padding: 15px 20px; background: white; border-top: 1px solid #e0e0e0; text-align: center; }}
.stats {{ background: #e6f2ff; padding: 15px 20px; border-radius: 6px; margin-bottom: 20px; font-size: 12px; color: #003d99; }}
.footer {{ text-align: center; padding-top: 30px; border-top: 2px solid #e5e7eb; margin-top: 40px; font-size: 11px; color: #9ca3af; }}
.boards-searched {{ background: #f0f0f0; padding: 15px 20px; border-radius: 6px; margin-top: 15px; font-size: 11px; }}
</style></head><body><div class="container">
<div class="header">
  <h1>💼 SAP MM/EWM Opportunities - Comprehensive European Search</h1>
  <p>Pradeep | 8 Years Experience | Europe | Posted < 14 Days | Source Tracking Included</p>
</div>

<div class="summary">
  <div style="margin-bottom: 15px; font-size: 12px; color: #003d99; font-weight: 600;">
    👤 <b>SAP Expertise:</b> Materials Management (MM) • Extended Warehouse Management (EWM) • ABAP • Fiori • S/4HANA
  </div>
  <div class="summary-grid">
    <div>
      <div class="summary-label">Total Jobs</div>
      <div class="summary-value">{len(matches)}</div>
    </div>
    <div>
      <div class="summary-label">Boards Searched</div>
      <div class="summary-value">15</div>
    </div>
    <div>
      <div class="summary-label">Jobs w/ Visa Info</div>
      <div class="summary-value">{visa_count}</div>
    </div>
    <div>
      <div class="summary-label">Posted Within</div>
      <div class="summary-value">14 Days</div>
    </div>
  </div>
  <div class="boards-searched">
    <b>Boards Searched:</b> LinkedIn (UK/DE/FR/IT) • Indeed (UK/DE/NL/GR/FI) • Glassdoor (UK/DE) • Welcome to NL • Working In Finland • WorkInLux • EURES
  </div>
</div>
"""

# Add jobs grouped by board
job_counter = 1
for board_name in sorted(board_distribution.keys()):
    board_jobs = board_distribution[board_name]
    
    html += f"""<div class="board-section">
    <div class="board-header">🔍 {board_name} ({len(board_jobs)} jobs)</div>
    <div class="board-jobs">
"""
    
    for job in board_jobs:
        visa_tag = '<span class="visa-badge">✓ VISA/RELOCATION</span>' if job['has_visa'] else ""
        html += f"""        <div class="job">
            <div><span class="job-num">{job_counter}</span><span class="job-title">{job['title']}{visa_tag}</span></div>
            <div class="job-company">🏢 {job['company']}</div>
            <div class="job-location">📍 {job['location']}</div>
            <div class="job-posted">📅 Posted: {job['posted_at']} ({job['days_old']} days ago)</div>
            <div class="job-link"><a href="{job['url']}" target="_blank">Apply Now →</a></div>
        </div>
"""
        job_counter += 1
    
    html += """    </div>
</div>
"""

html += f"""
<div class="footer">
  <p><b>Search Methodology:</b></p>
  <p>✓ Searched 15 major European job boards • ✓ Filtered by location (Europe) • ✓ Posted within 14 days • ✓ SAP expertise required • ✓ Visa support highlighted</p>
  <p>Total Evaluated: {sum(len(jobs) for jobs in jobs_by_board.values())} jobs | Matched: {len(matches)} | With Visa Info: {visa_count}</p>
  <p style="margin-top: 15px; font-size: 10px;">Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Profile: Pradeep Meena (8 years SAP MM/EWM experience)</p>
</div>
</div></body></html>"""

# Send email
print("SENDING COMPREHENSIVE EMAIL")
print("-" * 160)

with open("/Users/kamnee.maran/Downloads/job-search-agent/.env") as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

sender_email = os.getenv("GMAIL_ADDRESS")
sender_password = os.getenv("GMAIL_APP_PASSWORD")
recipient = "pradeepmeena13@gmail.com"

msg = MIMEMultipart("alternative")
msg["Subject"] = f"💼 {len(matches)} SAP MM/EWM Jobs | Europe | Comprehensive 15-Board Search | < 14 Days"
msg["From"] = sender_email
msg["To"] = recipient
msg.attach(MIMEText(html, "html"))

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, recipient, msg.as_string())
    server.quit()
    
    print(f"✅ COMPREHENSIVE EMAIL SENT TO {recipient}!")
    print()
    print("=" * 160)
    print("FINAL RESULTS SUMMARY")
    print("=" * 160)
    print(f"Recipient:                {recipient}")
    print(f"Total SAP Jobs:           {len(matches)}")
    print(f"Boards Searched:          15")
    print(f"Boards with Matches:      {len(board_distribution)}")
    print(f"With Visa/Relocation:     {visa_count}")
    print()
    print("JOBS BY BOARD:")
    for board_name in sorted(board_distribution.keys()):
        print(f"  • {board_name:30} {len(board_distribution[board_name]):2} jobs")
    print()
    print("TOP 10 OPPORTUNITIES:")
    for i, job in enumerate(matches[:10], 1):
        visa_tag = "[VISA]" if job['has_visa'] else ""
        print(f"  {i:2}. {visa_tag:7} {job['title'][:60]}")
        print(f"       🏢 {job['company'][:50]} | 📍 {job['location'][:40]}")
    print()
    print("=" * 160)
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
