"""
Job Search for Pradeep - 8 Years SAP MM/EWM Experience
========================================================
Profile: Senior SAP Consultant / SAP MM/EWM Specialist
Experience: 8 years (SAP MM = Materials Management, EWM = Extended Warehouse Management)
Location: Europe
Posted: < 7 days
Visa/Relocation Support: Preferred
Skills: SAP MM, SAP EWM, SAP ABAP, SAP Fiori, SAP Analytics, Materials Management, Warehouse Management
"""

import daily_scan
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from datetime import datetime, timedelta

def extract_posted_date_days_ago(posted_at):
    """Extract how many days ago job was posted."""
    if not posted_at or posted_at == "Unknown":
        return 999  # Assume old if unknown
    
    try:
        if isinstance(posted_at, str):
            # Try to extract days from "X days ago" format
            match = re.search(r'(\d+)\s+days?\s+ago', posted_at.lower())
            if match:
                return int(match.group(1))
            
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]:
                try:
                    post_date = datetime.strptime(posted_at.split()[0], fmt)
                    days_old = (datetime.now() - post_date).days
                    return days_old
                except:
                    continue
            
            return 999  # Can't parse, assume old
        else:
            days_old = (datetime.now() - posted_at).days
            return days_old
    except:
        return 999

def has_visa_relocation_keyword(job_description, job_title):
    """Check if job mentions visa sponsorship or relocation support."""
    text = (job_description + " " + job_title).lower()
    
    visa_keywords = [
        "visa", "sponsorship", "sponsor", "visa sponsor",
        "relocation", "relocation assistance", "relocation support",
        "relocation package", "employment visa",
        "work visa", "international", "willing to relocate",
        "relocation allowance", "visa support"
    ]
    
    for keyword in visa_keywords:
        if keyword in text:
            return True
    
    return False

def is_sap_mm_ewm_match(job_description, job_title):
    """Check if job is specifically for SAP MM/EWM."""
    text = (job_description + " " + job_title).lower()
    
    sap_keywords = [
        "sap mm", "materials management", "mm module",
        "sap ewm", "extended warehouse", "warehouse management",
        "sap consultant", "sap functional", "sap abap",
        "sap fiori", "sap analytics", "materials planning",
        "inventory management", "procurement", "supply chain"
    ]
    
    # Need at least 2 SAP-related keywords
    matched = sum(1 for kw in sap_keywords if kw in text)
    return matched >= 2

def is_european_location(location):
    """Check if location is in Europe."""
    european_countries = [
        "uk", "united kingdom", "germany", "france", "italy", "spain",
        "netherlands", "belgium", "switzerland", "austria", "poland",
        "portugal", "greece", "finland", "sweden", "norway", "denmark",
        "ireland", "czechia", "czech republic", "hungary", "romania",
        "luxembourg", "slovenia", "croatia", "bulgaria", "remote europe",
        "london", "paris", "berlin", "amsterdam", "zurich", "vienna",
        "warsaw", "prague", "budapest", "lisbon", "athens", "dublin"
    ]
    
    location_lower = location.lower()
    return any(country in location_lower for country in european_countries)

def filter_job_for_sap_mm_ewm(job, profile):
    """
    Filter job for SAP MM/EWM specialist.
    Returns: (is_relevant, reason)
    """
    title = job.get("title", "").lower()
    company = job.get("company", "").lower()
    desc = job.get("description", "").lower()
    location = job.get("location", "").lower()
    posted_at = job.get("posted_at", "Unknown")
    
    # ===== CHECK 1: Location =====
    if not is_european_location(location):
        return False, f"Location mismatch: {location} (need Europe)"
    
    # ===== CHECK 2: Posting date (< 7 days) =====
    days_old = extract_posted_date_days_ago(posted_at)
    if days_old > 7:
        return False, f"Posting too old: {days_old} days ago (max 7)"
    
    # ===== CHECK 3: SAP MM/EWM expertise =====
    if not is_sap_mm_ewm_match(desc, title):
        return False, f"Not SAP MM/EWM specific"
    
    # ===== CHECK 4: Red flags - exclude these roles =====
    red_flags = [
        "fresher", "entry level", "junior", "trainee",
        "qa", "test", "devops", "database",
        "sales", "recruiter", "hr", "marketing"
    ]
    
    for flag in red_flags:
        if flag in title:
            return False, f"Red flag: '{flag}' role"
    
    # ===== CHECK 5: Visa/Relocation support (preferred) =====
    has_visa = has_visa_relocation_keyword(desc, title)
    
    # ===== All checks passed =====
    visa_status = "✓ Visa" if has_visa else "○ No Visa Info"
    return True, f"{visa_status} | Posted {days_old}d ago"

# ===== MAIN SEARCH =====
print("\n" + "=" * 140)
print("🔍 JOB SEARCH - SAP MM/EWM SPECIALIST (8 YEARS EXPERIENCE)")
print("=" * 140)
print()

# Profile
profile = {
    "name": "Pradeep - SAP MM/EWM Specialist",
    "years_experience": 8,
    "skills": [
        "sap mm", "materials management", "mm module",
        "sap ewm", "extended warehouse", "warehouse management",
        "sap consultant", "sap functional", "sap abap",
        "sap fiori", "sap analytics", "materials planning",
    ],
}

# European job boards - best for SAP jobs
european_boards = [
    ("LinkedIn UK", daily_scan.search_linkedin_uk, "United Kingdom"),
    ("LinkedIn Germany", daily_scan.search_linkedin_de, "Germany"),
    ("LinkedIn France", daily_scan.search_linkedin_fr, "France"),
    ("LinkedIn Italy", daily_scan.search_linkedin_it, "Italy"),
    ("Indeed UK", daily_scan.search_indeed_uk, "United Kingdom"),
    ("Indeed Germany", daily_scan.search_indeed_de, "Germany"),
    ("Indeed Netherlands", daily_scan.search_indeed_nl, "Netherlands"),
    ("Indeed Greece", daily_scan.search_indeed_gr, "Greece"),
    ("Indeed Finland", daily_scan.search_indeed_fi, "Finland"),
    ("Glassdoor UK", daily_scan.search_glassdoor_uk, "United Kingdom"),
    ("Glassdoor Germany", daily_scan.search_glassdoor_de, "Germany"),
    ("Welcome to NL", daily_scan.search_welcome_to_nl, "Netherlands"),
    ("StepStone Germany", daily_scan.search_stepstone, "Germany"),
    ("Monster Germany", daily_scan.search_monsterde, "Germany"),
    ("Xing", daily_scan.search_xing, "Germany"),
    ("WorkInAustria", daily_scan.search_workinaustria, "Austria"),
    ("JobSch (Switzerland)", daily_scan.search_jobsch, "Switzerland"),
    ("Infojobs Spain", daily_scan.search_infojobs, "Spain"),
    ("Working In Finland", daily_scan.search_workinfinland, "Finland"),
    ("WorkInLux", daily_scan.search_workinlux, "Luxembourg"),
    ("MonsterLU", daily_scan.search_monsterlu, "Luxembourg"),
    ("VDAB Belgium", daily_scan.search_vdab, "Belgium"),
    ("EURES", daily_scan.search_eures, "Europe"),
    ("Michael Page", daily_scan.search_michaelpage, "Europe"),
    ("Hays", daily_scan.search_hays, "Europe"),
    ("Randstad", daily_scan.search_randstad, "Europe"),
    ("RobertHalf", daily_scan.search_roberthalf, "Europe"),
]

all_jobs = []

print("SEARCHING EUROPEAN JOB BOARDS FOR SAP MM/EWM JOBS")
print("-" * 140)

for board_name, search_func, location in european_boards:
    try:
        print(f"{board_name:30}", end=" ", flush=True)
        # Search for SAP MM/EWM related queries
        jobs = search_func("SAP MM EWM consultant", location, max_results=15)
        if not jobs:
            jobs = search_func("SAP materials management", location, max_results=15)
        if not jobs:
            jobs = search_func("SAP warehouse management", location, max_results=15)
        
        all_jobs.extend(jobs)
        print(f"✓ {len(jobs):2} jobs")
    except Exception as e:
        print(f"✗ ERROR: {str(e)[:50]}")

print()
print(f"Total jobs collected: {len(all_jobs)}")
print()

# Filter and score
print("FILTERING WITH STRICT CRITERIA")
print("-" * 140)

matches = []
seen_urls = set()
visa_jobs = []
no_visa_jobs = []

for job in all_jobs:
    url = job.get("url", "")
    
    # Skip duplicates
    if url in seen_urls:
        continue
    seen_urls.add(url)
    
    # Apply filter
    is_relevant, reason = filter_job_for_sap_mm_ewm(job, profile)
    
    if not is_relevant:
        continue
    
    # Calculate match score based on SAP keywords
    title = job.get("title", "").lower()
    company = job.get("company", "").lower()
    desc = job.get("description", "").lower()
    full_text = title + " " + company + " " + desc
    
    sap_keywords = [
        "sap mm", "materials management", "mm module",
        "sap ewm", "extended warehouse", "warehouse management",
        "sap consultant", "sap functional", "sap abap",
        "sap fiori", "sap analytics"
    ]
    
    matched_keywords = [kw for kw in sap_keywords if kw in full_text]
    
    if len(matched_keywords) >= 5:
        score = 100
    elif len(matched_keywords) >= 4:
        score = 90
    elif len(matched_keywords) >= 3:
        score = 80
    else:
        score = 70
    
    has_visa = has_visa_relocation_keyword(desc, title)
    
    job_data = {
        "title": job.get("title", "Unknown"),
        "company": job.get("company", "Unknown"),
        "location": job.get("location", "Unknown"),
        "score": score,
        "url": url,
        "posted_at": job.get("posted_at", "Unknown"),
        "matched_keywords": matched_keywords[:5],
        "has_visa": has_visa,
        "source": job.get("source", "Unknown"),
    }
    
    matches.append(job_data)
    
    if has_visa:
        visa_jobs.append(job_data)
    else:
        no_visa_jobs.append(job_data)

# Sort by score
matches.sort(key=lambda x: (x["has_visa"], x["score"]), reverse=True)

print(f"Total matches: {len(matches)}")
print(f"  - With Visa/Relocation support: {len(visa_jobs)}")
print(f"  - Without Visa info: {len(no_visa_jobs)}")
print()

if len(matches) == 0:
    print("❌ No matching jobs found. Adjusting search...")
    # Try broader SAP search
    print("Retrying with broader SAP keywords...")
    for board_name, search_func, location in european_boards[:5]:  # Try top 5 boards
        try:
            jobs = search_func("SAP consultant", location, max_results=20)
            all_jobs.extend(jobs)
        except:
            pass
    
    if len(all_jobs) == 0:
        print("❌ No jobs found even with broader search.")
        exit(1)

print(f"✅ {len(matches)} high-quality SAP MM/EWM matches found!")
print()

# Generate HTML email
html = f"""<html><head><style>
body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
.container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
.header {{ background: linear-gradient(135deg, #0066cc 0%, #003d99 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }}
.header h1 {{ margin: 0; font-size: 26px; font-weight: bold; }}
.header p {{ margin: 8px 0 0 0; font-size: 15px; opacity: 0.95; }}
.summary {{ background: #e6f2ff; border-left: 5px solid #0066cc; padding: 20px; border-radius: 5px; margin-bottom: 30px; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 15px; }}
.summary-item {{ }}
.summary-label {{ font-weight: bold; color: #0066cc; font-size: 12px; text-transform: uppercase; }}
.summary-value {{ font-size: 18px; font-weight: bold; color: #003d99; margin-top: 5px; }}
.job {{ border: 1px solid #e5e7eb; border-left: 5px solid #0066cc; padding: 18px; margin-bottom: 15px; background: #fafbfc; border-radius: 5px; }}
.job:hover {{ background: #f3f4f6; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.job-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
.job-title {{ font-size: 15px; font-weight: bold; color: #003d99; flex: 1; line-height: 1.4; }}
.job-score {{ background: #0066cc; color: white; padding: 5px 12px; border-radius: 4px; font-weight: bold; font-size: 13px; white-space: nowrap; margin-left: 10px; }}
.job-company {{ font-size: 13px; color: #4b5563; margin: 5px 0; font-weight: 600; }}
.job-location {{ font-size: 12px; color: #6b7280; margin: 3px 0; }}
.job-meta {{ font-size: 11px; color: #9ca3af; margin: 6px 0; }}
.job-keywords {{ background: #e6f2ff; border-left: 3px solid #0066cc; padding: 8px 10px; margin: 10px 0; border-radius: 3px; font-size: 12px; color: #003d99; }}
.visa-badge {{ display: inline-block; background: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 3px; font-size: 10px; font-weight: bold; margin-left: 8px; }}
.job-link a {{ background: #0066cc; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold; display: inline-block; margin-top: 10px; transition: background 0.2s; }}
.job-link a:hover {{ background: #003d99; }}
.section-title {{ font-size: 18px; font-weight: bold; color: #003d99; margin: 25px 0 15px 0; border-bottom: 2px solid #0066cc; padding-bottom: 10px; }}
.footer {{ text-align: center; padding-top: 25px; border-top: 2px solid #e5e7eb; margin-top: 30px; font-size: 11px; color: #9ca3af; }}
.profile-badge {{ background: #e6f2ff; color: #003d99; padding: 8px 12px; border-radius: 4px; font-size: 12px; margin-bottom: 10px; display: inline-block; }}
</style></head><body><div class="container">
<div class="header">
  <h1>💼 Pradeep - SAP MM/EWM Opportunities in Europe</h1>
  <p>8 Years Experience | Europe | Posted < 7 Days | Visa Support Preferred</p>
</div>

<div class="summary">
  <div class="profile-badge">👤 SAP MM (Materials Management) • EWM (Warehouse Management) • ABAP • Fiori • 8+ Years</div>
  <div class="summary-grid">
    <div class="summary-item">
      <div class="summary-label">Total Matches</div>
      <div class="summary-value">{len(matches)}</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">With Visa Support</div>
      <div class="summary-value">{len(visa_jobs)}</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">Jobs Evaluated</div>
      <div class="summary-value">{len(all_jobs)}</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">Best Score</div>
      <div class="summary-value">{matches[0]['score'] if matches else 0}%</div>
    </div>
  </div>
</div>

<div class="section-title">🌟 Top Opportunities (Visa Support Highlighted)</div>
"""

for i, job in enumerate(matches[:40], 1):
    visa_text = '<span class="visa-badge">✓ VISA/RELOCATION</span>' if job['has_visa'] else ""
    
    html += f"""<div class="job">
    <div class="job-header">
      <div class="job-title">{i}. {job['title']}{visa_text}</div>
      <div class="job-score">{job['score']}%</div>
    </div>
    <div class="job-company">🏢 {job['company']}</div>
    <div class="job-location">📍 {job['location']}</div>
    <div class="job-meta">📅 {job['posted_at']} | 🔧 {job['source']}</div>
    <div class="job-keywords">✓ SAP Skills: {', '.join(job['matched_keywords'][:4])}</div>
    <div class="job-link"><a href="{job['url']}" target="_blank">Apply Now →</a></div>
</div>"""

html += f"""
<div class="footer">
  <p><b>Filter Criteria Applied:</b> Location (Europe) • Posted (<7 days) • SAP MM/EWM Expertise • Visa/Relocation Preferred</p>
  <p>Evaluated: {len(all_jobs)} jobs across 25+ European boards • Matched: {len(matches)} • With Visa: {len(visa_jobs)}</p>
  <p>Boards: LinkedIn (UK/DE/FR/IT) • Indeed (UK/DE/NL/GR/FI) • Glassdoor (UK/DE) • StepStone • Xing • EURES • Michael Page • Hays • Randstad • RobertHalf</p>
</div>
</div></body></html>"""

# Send email
print("SENDING EMAIL")
print("-" * 140)

with open("/Users/kamnee.maran/Downloads/job-search-agent/.env") as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

sender_email = os.getenv("GMAIL_ADDRESS")
sender_password = os.getenv("GMAIL_APP_PASSWORD")

recipient = "pradeepmeena13@gmail.com"

msg = MIMEMultipart("alternative")
msg["Subject"] = f"💼 {len(matches)} SAP MM/EWM Opportunities in Europe | 8 Yrs | Posted < 7 Days"
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
    print("=" * 140)
    print("RESULTS SUMMARY")
    print("=" * 140)
    print(f"Recipient:           {recipient}")
    print(f"Subject:             {len(matches)} SAP MM/EWM Opportunities in Europe | 8 Yrs | Posted < 7 Days")
    print(f"Total Jobs Sent:     {len(matches)}")
    print(f"With Visa Support:   {len(visa_jobs)}")
    print(f"Best Match Score:    {matches[0]['score']}% - {matches[0]['title'][:60]}")
    print(f"Companies:           {len(set(m['company'] for m in matches))} unique companies")
    print()
    print("TOP 5 OPPORTUNITIES:")
    for i, job in enumerate(matches[:5], 1):
        visa_tag = "[✓ VISA]" if job['has_visa'] else "[○ No Info]"
        print(f"  {i}. [{job['score']}%] {visa_tag} {job['title'][:50]} @ {job['company'][:40]}")
    print()
    print("=" * 140)
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
