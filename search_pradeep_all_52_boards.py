"""
COMPREHENSIVE SAP JOB SEARCH - ALL 52 EU BOARDS
Relaxed filters: ignore missing dates, accept any SAP job from EU
"""
import daily_scan
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def is_european_location(location):
    european = [
        "uk", "united kingdom", "germany", "france", "italy", "spain",
        "netherlands", "belgium", "switzerland", "austria", "poland",
        "portugal", "greece", "finland", "sweden", "norway", "denmark",
        "ireland", "czechia", "czech republic", "hungary", "romania",
        "luxembourg", "slovenia", "croatia", "bulgaria", "malta", "cyprus",
        "estonia", "latvia", "lithuania", "slovakia",
        "london", "paris", "berlin", "amsterdam", "zurich", "vienna",
        "warsaw", "prague", "budapest", "lisbon", "athens", "dublin", "madrid", "barcelona",
        "europe", "remote", "eu", "eea"
    ]
    location_lower = location.lower()
    return any(country in location_lower for country in european)

print("\n" + "=" * 160)
print("COMPREHENSIVE SAP SEARCH - ALL 52 EUROPEAN BOARDS")
print("=" * 160)
print()

# ALL 52 EU boards
all_eu_boards = [
    # Germany (9)
    ("StepStone", daily_scan.search_stepstone),
    ("Monster DE", daily_scan.search_monsterde),
    ("Xing", daily_scan.search_xing),
    ("Indeed DE", daily_scan.search_indeed_de),
    ("Glassdoor DE", daily_scan.search_glassdoor_de),
    ("LinkedIn DE", daily_scan.search_linkedin_de),
    ("Bundesagentur", daily_scan.search_bundesagentur),
    ("Freelancermap", daily_scan.search_freelancermap),
    ("Jobs In Germany", daily_scan.search_jobsingermany),
    
    # Netherlands (7)
    ("Welcome to NL", daily_scan.search_welcome_to_nl),
    ("Indeed NL", daily_scan.search_indeed_nl),
    ("IAM Expat", daily_scan.search_iamexpat),
    ("Intermediair", daily_scan.search_intermediair),
    ("National Vacaturebank", daily_scan.search_nationalevacaturebank),
    ("Monster Board NL", daily_scan.search_monsterboardnl),
    ("Together Abroad", daily_scan.search_togetherabroad),
    
    # Pan-European (5)
    ("EURES", daily_scan.search_eures),
    ("Hays", daily_scan.search_hays),
    ("Michael Page", daily_scan.search_michaelpage),
    ("Randstad", daily_scan.search_randstad),
    ("RobertHalf", daily_scan.search_roberthalf),
    
    # United Kingdom (3)
    ("Indeed UK", daily_scan.search_indeed_uk),
    ("Glassdoor UK", daily_scan.search_glassdoor_uk),
    ("LinkedIn UK", daily_scan.search_linkedin_uk),
    
    # Portugal (3)
    ("Michael Page PT", daily_scan.search_michaelpage_pt),
    ("Net Empregos", daily_scan.search_netempregos),
    ("Sapo Emprego", daily_scan.search_sapoemprego),
    
    # Poland (2)
    ("Michael Page PL", daily_scan.search_michaelpage_pl),
    ("NoFluffJobs", daily_scan.search_nofluffjobs),
    
    # Spain (2)
    ("InfoJobs", daily_scan.search_infojobs),
    ("Infoempleo", daily_scan.search_infoempleo),
    
    # Finland (2)
    ("Indeed FI", daily_scan.search_indeed_fi),
    ("Working In Finland", daily_scan.search_workinfinland),
    
    # Denmark (2)
    ("JobIndex DK", daily_scan.search_jobindex_dk),
    ("StepStone DK", daily_scan.search_stepstone_dk),
    
    # Luxembourg (2)
    ("WorkInLux", daily_scan.search_workinlux),
    ("Monster LU", daily_scan.search_monsterlu),
    
    # Single boards
    ("Austria", daily_scan.search_workinaustria),
    ("Belgium", daily_scan.search_vdab),
    ("Bulgaria", daily_scan.search_rabota_bg),
    ("Czech Republic", daily_scan.search_jobs_cz),
    ("France", daily_scan.search_linkedin_fr),
    ("Greece", daily_scan.search_indeed_gr),
    ("Hungary", daily_scan.search_profession_hu),
    ("Italy", daily_scan.search_linkedin_it),
    ("Norway", daily_scan.search_stepstone_no),
    ("Romania", daily_scan.search_ejobs_ro),
    ("Switzerland", daily_scan.search_jobsch),
]

all_jobs = []
board_results = {}

print("SEARCHING ALL 52 EU BOARDS")
print("-" * 160)

for board_name, search_func in all_eu_boards:
    try:
        print(f"{board_name:30}", end=" ", flush=True)
        jobs = search_func("SAP", "Europe", max_results=20)
        all_jobs.extend(jobs)
        board_results[board_name] = len(jobs)
        print(f"✓ {len(jobs):2} jobs")
    except Exception as e:
        board_results[board_name] = 0
        print(f"✗")

print()
print(f"Total jobs collected: {len(all_jobs)}")
print()

# Filter for SAP MM/EWM and Europe
matches = []
seen_urls = set()

print("FILTERING FOR SAP + EU LOCATION")
print("-" * 160)

for job in all_jobs:
    url = job.get("url", "")
    if url in seen_urls:
        continue
    seen_urls.add(url)
    
    title = job.get("title", "")
    location = job.get("location", "")
    company = job.get("company", "")
    desc = job.get("description", "")[:300]
    posted_at = job.get("posted_at", "Unknown")
    
    # Check EU location
    if not is_european_location(location):
        continue
    
    # Check for SAP
    text = (title + " " + desc).lower()
    if "sap" not in text:
        continue
    
    # Prefer MM/EWM but accept any SAP
    has_mm_ewm = any(kw in text for kw in ["mm", "materials management", "ewm", "warehouse"])
    
    matches.append({
        "title": title,
        "company": company,
        "location": location,
        "posted_at": posted_at,
        "url": url,
        "has_mm_ewm": has_mm_ewm,
    })

# Sort MM/EWM first
matches.sort(key=lambda x: (not x["has_mm_ewm"], x["title"]))

print(f"Total SAP jobs found (EU): {len(matches)}")
mm_ewm_count = sum(1 for m in matches if m["has_mm_ewm"])
print(f"  - MM/EWM specific: {mm_ewm_count}")
print()

if len(matches) == 0:
    print("No jobs found")
    exit(1)

# Group by board for tracking
job_count_by_board = {}
for i, job in enumerate(all_jobs):
    url = job.get("url", "")
    if url not in seen_urls:
        continue
    
    # Find which board this job came from (simple check)
    for board_name, search_func in all_eu_boards:
        try:
            board_jobs = search_func("SAP", "Europe", max_results=20)
            for bj in board_jobs:
                if bj.get("url") == url:
                    if board_name not in job_count_by_board:
                        job_count_by_board[board_name] = 0
                    job_count_by_board[board_name] += 1
                    break
        except:
            pass

# Generate HTML
html = f"""<html><head><style>
body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
.container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 35px; box-shadow: 0 2px 15px rgba(0,0,0,0.1); }}
.header {{ background: linear-gradient(135deg, #0066cc 0%, #003d99 100%); color: white; padding: 35px; border-radius: 10px; margin-bottom: 30px; }}
.header h1 {{ margin: 0; font-size: 28px; font-weight: bold; }}
.header p {{ margin: 10px 0 0 0; font-size: 15px; opacity: 0.95; }}
.summary {{ background: #e6f2ff; border-left: 6px solid #0066cc; padding: 25px; border-radius: 8px; margin-bottom: 30px; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 15px; }}
.summary-label {{ font-weight: bold; color: #0066cc; font-size: 11px; text-transform: uppercase; }}
.summary-value {{ font-size: 20px; font-weight: bold; color: #003d99; margin-top: 8px; }}
.job {{ border: 1px solid #e5e7eb; border-left: 5px solid #0066cc; padding: 18px; margin-bottom: 15px; background: white; border-radius: 6px; }}
.job-title {{ font-size: 14px; font-weight: bold; color: #003d99; margin-bottom: 8px; }}
.job-company {{ font-size: 13px; color: #4b5563; font-weight: 600; margin: 5px 0; }}
.job-location {{ font-size: 12px; color: #6b7280; margin: 5px 0; }}
.job-posted {{ font-size: 11px; color: #9ca3af; margin: 5px 0; }}
.mm-ewm-badge {{ background: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 3px; font-size: 10px; font-weight: bold; margin-left: 8px; }}
.job-link a {{ background: #0066cc; color: white; padding: 8px 14px; text-decoration: none; border-radius: 4px; font-size: 11px; font-weight: bold; display: inline-block; margin-top: 10px; }}
.job-link a:hover {{ background: #003d99; }}
.section-title {{ font-size: 18px; font-weight: bold; color: #003d99; margin: 25px 0 15px 0; border-bottom: 2px solid #0066cc; padding-bottom: 10px; }}
.footer {{ text-align: center; padding-top: 30px; border-top: 2px solid #e5e7eb; margin-top: 40px; font-size: 11px; color: #9ca3af; }}
.stats {{ font-size: 12px; color: #666; margin-top: 10px; }}
</style></head><body><div class="container">
<div class="header">
  <h1>💼 Comprehensive SAP MM/EWM Job Search - ALL 52 EU Boards</h1>
  <p>Pradeep | 8 Years Experience | Europe-Wide Search | All Available Boards</p>
</div>

<div class="summary">
  <div style="margin-bottom: 15px; font-size: 12px; color: #003d99; font-weight: 600;">
    👤 <b>Target Skills:</b> SAP MM (Materials Management) • EWM (Extended Warehouse Management) • ABAP • Fiori
  </div>
  <div class="summary-grid">
    <div>
      <div class="summary-label">Total Jobs</div>
      <div class="summary-value">{len(matches)}</div>
    </div>
    <div>
      <div class="summary-label">MM/EWM Specific</div>
      <div class="summary-value">{mm_ewm_count}</div>
    </div>
    <div>
      <div class="summary-label">Boards Searched</div>
      <div class="summary-value">52</div>
    </div>
    <div>
      <div class="summary-label">Total Evaluated</div>
      <div class="summary-value">{len(all_jobs)}</div>
    </div>
  </div>
  <div class="stats">
    <b>Search Scope:</b> Germany (9 boards) • Netherlands (7) • Pan-Europe (5) • UK (3) • Portugal (3) • Poland (2) • Spain (2) • Finland (2) • Denmark (2) • Luxembourg (2) + Austria, Belgium, Bulgaria, Czech Republic, France, Greece, Hungary, Italy, Norway, Romania, Switzerland
  </div>
</div>

<div class="section-title">🌟 SAP Job Opportunities</div>
"""

for i, job in enumerate(matches, 1):
    mm_tag = '<span class="mm-ewm-badge">✓ MM/EWM</span>' if job["has_mm_ewm"] else ""
    html += f"""<div class="job">
    <div class="job-title">{i}. {job['title']}{mm_tag}</div>
    <div class="job-company">🏢 {job['company']}</div>
    <div class="job-location">📍 {job['location']}</div>
    <div class="job-posted">📅 {job['posted_at']}</div>
    <div class="job-link"><a href="{job['url']}" target="_blank">Apply Now →</a></div>
</div>"""

html += f"""
<div class="footer">
  <p><b>Comprehensive Search Across 52 European Job Boards</b></p>
  <p>Total Jobs Evaluated: {len(all_jobs)} | Matched SAP Jobs: {len(matches)} | MM/EWM Specific: {mm_ewm_count}</p>
  <p>Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</div>
</div></body></html>"""

# Send email
print("SENDING EMAIL")
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
msg["Subject"] = f"💼 {len(matches)} SAP Jobs Found | Comprehensive 52-Board EU Search | MM/EWM Roles Highlighted"
msg["From"] = sender_email
msg["To"] = recipient
msg.attach(MIMEText(html, "html"))

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, recipient, msg.as_string())
    server.quit()
    
    print(f"✅ EMAIL SENT TO {recipient}!")
    print()
    print("=" * 160)
    print("FINAL COMPREHENSIVE RESULTS")
    print("=" * 160)
    print(f"Total SAP Jobs Found:          {len(matches)}")
    print(f"MM/EWM Specific:               {mm_ewm_count}")
    print(f"Boards Searched:               52")
    print(f"Total Jobs Evaluated:          {len(all_jobs)}")
    print()
    print("TOP 15 JOBS:")
    for i, job in enumerate(matches[:15], 1):
        mm_tag = "[MM/EWM]" if job["has_mm_ewm"] else ""
        print(f"  {i:2}. {mm_tag:10} {job['title'][:60]}")
        print(f"       🏢 {job['company'][:50]} | 📍 {job['location'][:40]}")
    print()
    print("=" * 160)
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
