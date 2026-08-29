"""
Send NEW jobs to Gursimran with LENIENT experience matching (±2 years)
========================================================================
Profile: Gursimran - 8 Years Backend Engineer
Experience: 8 years (lenient: ±2 years, so 6-10 years)
Location: India + Remote
Skills: Java, SpringBoot, Hibernate, Python, MySQL, Redis, ElasticSearch, Aerospike, HBase, MariaDB, DynamoDB, Docker, Kubernetes, AOP, Jenkins, OpenTelemetry
Filter: Only send jobs NOT already sent before
"""

import daily_scan
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from datetime import datetime

def extract_experience_range(job_description, job_title):
    """Extract years of experience required from job description/title."""
    text = (job_description + " " + job_title).lower()
    
    patterns = [
        r'(\d+)\s*[-–]\s*(\d+)\s+years?',  # "8-11 years"
        r'(\d+)\+?\s+years?\s+(?:of\s+)?experience',  # "5+ years experience"
        r'(\d+)\s+years?\s+(?:of\s+)?(?:relevant\s+)?experience',  # "5 years experience"
    ]
    
    years_found = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                years_found.extend([int(m) for m in match if m.isdigit()])
            else:
                years_found.append(int(match))
    
    if not years_found:
        return None, None
    
    return min(years_found), max(years_found)

def is_experience_match_lenient(min_req, max_req, candidate_years=8, tolerance=2):
    """
    Lenient experience matching with ±tolerance years.
    
    Candidate has 8 years.
    With tolerance=2:
    - Accept if job requires 6-10 years (candidate falls in range)
    - Accept if job requires 5-9 years (candidate 8 falls in range)
    - Accept if job requires 10-10 years (|8-10| = 2, within tolerance)
    - Reject if job requires 2-5 years (candidate 8 > 5+tolerance)
    """
    if min_req is None or max_req is None:
        return True  # Unknown requirement, assume match
    
    # Check if candidate's years fall within the required range
    if min_req <= candidate_years <= max_req:
        return True
    
    # Check if candidate is within tolerance of range
    distance_to_min = candidate_years - min_req
    distance_to_max = max_req - candidate_years
    
    if distance_to_min >= -tolerance and distance_to_max >= -tolerance:
        return True
    
    return False

def load_tracker(tracker_file):
    """Load previously sent jobs."""
    if os.path.exists(tracker_file):
        with open(tracker_file, 'r') as f:
            return json.load(f)
    return {"sent_urls": set(), "sent_jobs": []}

def save_tracker(tracker_file, tracker):
    """Save sent jobs to tracker."""
    data = {
        "sent_urls": list(tracker["sent_urls"]),
        "sent_jobs": tracker["sent_jobs"],
        "last_updated": datetime.now().isoformat()
    }
    with open(tracker_file, 'w') as f:
        json.dump(data, f, indent=2)

# ===== MAIN =====
print("\n" + "=" * 120)
print("🔍 SENDING NEW JOBS TO GURSIMRAN - LENIENT EXPERIENCE MATCHING (±2 YEARS)")
print("=" * 120)
print()

# Profile
profile = {
    "name": "Gursimran - Senior Backend Engineer",
    "years_experience": 8,
    "core_skills": [
        "java", "springboot", "spring", "hibernate", "python",
        "mysql", "redis", "elasticsearch", "aerospike", "hbase", "mariadb", "dynamodb",
        "docker", "kubernetes", "aop", "jenkins", "opentelemetry",
        "microservices", "backend", "rest api", "distributed systems",
    ],
}

# Load tracker
tracker_file = "/Users/kamnee.maran/Downloads/job-search-agent/gursimran_sent_jobs.json"
tracker = load_tracker(tracker_file)
print(f"Previously sent jobs: {len(tracker['sent_jobs'])}")
print()

# Search LinkedIn
print("SEARCHING LINKEDIN FOR NEW JOBS")
print("-" * 120)

jobs = daily_scan.search_linkedin("senior backend engineer", "India", max_results=20)
print(f"LinkedIn jobs found: {len(jobs)}")
print()

# Filter jobs
print("FILTERING WITH LENIENT EXPERIENCE (±2 YEARS)")
print("-" * 120)

new_jobs = []
seen_urls = set()

for job in jobs:
    url = job.get("url", "")
    
    # Skip if already sent
    if url in tracker["sent_urls"]:
        print(f"⊘ DUPLICATE: {job.get('title', '')[:60]}")
        continue
    
    # Skip if already seen in this batch
    if url in seen_urls:
        continue
    seen_urls.add(url)
    
    # Extract experience requirement
    min_years, max_years = extract_experience_range(
        job.get("description", ""),
        job.get("title", "")
    )
    
    # Check experience match (lenient ±2 years)
    exp_match = is_experience_match_lenient(min_years, max_years, candidate_years=8, tolerance=2)
    
    # Check skills
    text = (job.get("title", "") + " " + job.get("description", "")).lower()
    matched_skills = [s for s in profile["core_skills"] if s.lower() in text]
    
    # Check location
    location = job.get("location", "").lower()
    location_ok = any(city in location for city in ["india", "bangalore", "delhi", "mumbai", "pune", "hyderabad", "gurgaon", "noida", "remote", "bengaluru", "chandigarh"])
    
    # Check red flags
    title_lower = job.get("title", "").lower()
    has_flag = any(flag in title_lower for flag in ["frontend", "qa", "devops", "android", "ios", "mobile", "devops"])
    
    # Determine pass/fail
    passed = exp_match and len(matched_skills) >= 2 and location_ok and not has_flag
    
    status = "✅ NEW" if passed else "⊘ SKIP"
    print(f"{status} | {job.get('title', '')[:50]:<50} | Exp: {min_years}-{max_years} | Skills: {len(matched_skills)}")
    
    if passed:
        new_jobs.append({
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "url": url,
            "posted_at": job.get("posted_at", "Unknown"),
            "matched_skills": matched_skills[:8],
            "exp_required": f"{min_years}-{max_years}" if min_years else "Unknown",
        })

print()
print(f"✅ {len(new_jobs)} NEW jobs to send")
print()

if len(new_jobs) == 0:
    print("❌ No new jobs found. Exiting.")
    exit(0)

# Generate HTML email
html = f"""<html><head><style>
body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
.container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
.header {{ background: linear-gradient(135deg, #059669 0%, #047857 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }}
.header h1 {{ margin: 0; font-size: 26px; font-weight: bold; }}
.header p {{ margin: 8px 0 0 0; font-size: 15px; opacity: 0.95; }}
.summary {{ background: #ecfdf5; border-left: 5px solid #059669; padding: 20px; border-radius: 5px; margin-bottom: 30px; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 15px; }}
.summary-item {{ }}
.summary-label {{ font-weight: bold; color: #059669; font-size: 12px; text-transform: uppercase; }}
.summary-value {{ font-size: 18px; font-weight: bold; color: #047857; margin-top: 5px; }}
.job {{ border: 1px solid #e5e7eb; border-left: 5px solid #059669; padding: 18px; margin-bottom: 15px; background: #fafbfc; border-radius: 5px; }}
.job:hover {{ background: #f3f4f6; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.job-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
.job-title {{ font-size: 15px; font-weight: bold; color: #047857; flex: 1; line-height: 1.4; }}
.job-badge {{ background: #059669; color: white; padding: 5px 12px; border-radius: 4px; font-weight: bold; font-size: 13px; white-space: nowrap; margin-left: 10px; }}
.job-company {{ font-size: 13px; color: #4b5563; margin: 5px 0; font-weight: 600; }}
.job-location {{ font-size: 12px; color: #6b7280; margin: 3px 0; }}
.job-meta {{ font-size: 11px; color: #9ca3af; margin: 6px 0; }}
.job-skills {{ background: #ecfdf5; border-left: 3px solid #059669; padding: 8px 10px; margin: 10px 0; border-radius: 3px; font-size: 12px; color: #047857; }}
.job-link a {{ background: #059669; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold; display: inline-block; margin-top: 10px; transition: background 0.2s; }}
.job-link a:hover {{ background: #047857; }}
.section-title {{ font-size: 18px; font-weight: bold; color: #047857; margin: 25px 0 15px 0; border-bottom: 2px solid #059669; padding-bottom: 10px; }}
.footer {{ text-align: center; padding-top: 25px; border-top: 2px solid #e5e7eb; margin-top: 30px; font-size: 11px; color: #9ca3af; }}
.profile-badge {{ background: #ecfdf5; color: #047857; padding: 8px 12px; border-radius: 4px; font-size: 12px; margin-bottom: 10px; display: inline-block; }}
.new-badge {{ background: #fecaca; color: #991b1b; padding: 3px 8px; border-radius: 3px; font-size: 10px; font-weight: bold; margin-left: 8px; }}
</style></head><body><div class="container">
<div class="header">
  <h1>🎯 Gursimran - NEW Backend Engineer Opportunities</h1>
  <p>8 Years Experience | India | Lenient Match (±2 Years) | NEW Jobs Only</p>
</div>

<div class="summary">
  <div class="profile-badge">👤 8 Years | Java, SpringBoot, Python, MySQL, Redis, Kubernetes, Docker, OpenTelemetry</div>
  <div class="summary-grid">
    <div class="summary-item">
      <div class="summary-label">NEW Jobs</div>
      <div class="summary-value">{len(new_jobs)}</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">Previously Sent</div>
      <div class="summary-value">{len(tracker['sent_jobs'])}</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">Filter Type</div>
      <div class="summary-value">Lenient ±2 Yrs</div>
    </div>
  </div>
</div>

<div class="section-title">🌟 New Opportunities (Not Previously Sent)</div>
"""

for i, job in enumerate(new_jobs, 1):
    html += f"""<div class="job">
    <div class="job-header">
      <div class="job-title">{i}. {job['title']}</div>
      <div class="job-badge">NEW ✓</div>
    </div>
    <div class="job-company">🏢 {job['company']}</div>
    <div class="job-location">📍 {job['location']}</div>
    <div class="job-meta">📅 Posted: {job['posted_at']} | 📊 Requires: {job['exp_required']} yrs</div>
    <div class="job-skills">✓ Skills: {', '.join(job['matched_skills'][:6])}</div>
    <div class="job-link"><a href="{job['url']}" target="_blank">Apply Now →</a></div>
</div>"""

html += f"""
<div class="footer">
  <p><b>Filter Criteria Applied:</b> Experience (6-10 years ±2yr tolerance) • Location (India/Remote) • Skills (2+ matched) • No Red Flags</p>
  <p>NEW: {len(new_jobs)} jobs | Previously sent: {len(tracker['sent_jobs'])} | Total evaluated: {len(jobs)}</p>
</div>
</div></body></html>"""

# Send email
print("SENDING EMAIL")
print("-" * 120)

with open("/Users/kamnee.maran/Downloads/job-search-agent/.env") as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

sender_email = os.getenv("GMAIL_ADDRESS")
sender_password = os.getenv("GMAIL_APP_PASSWORD")

recipient = "Gursimrankaur196@gmail.com"

msg = MIMEMultipart("alternative")
msg["Subject"] = f"🎯 {len(new_jobs)} NEW Senior Backend Engineer Opportunities | 8 Yrs | India | Lenient Match"
msg["From"] = sender_email
msg["To"] = recipient
msg.attach(MIMEText(html, "html"))

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, recipient, msg.as_string())
    server.quit()
    
    # Update tracker
    for job in new_jobs:
        tracker["sent_urls"].add(job["url"])
        tracker["sent_jobs"].append({
            "title": job["title"],
            "company": job["company"],
            "url": job["url"],
            "sent_date": datetime.now().isoformat(),
        })
    
    save_tracker(tracker_file, tracker)
    
    print(f"✅ EMAIL SENT TO {recipient}!")
    print()
    print("=" * 120)
    print("RESULTS SUMMARY")
    print("=" * 120)
    print(f"NEW jobs sent:       {len(new_jobs)}")
    print(f"Total sent so far:   {len(tracker['sent_jobs'])}")
    print()
    print("NEW OPPORTUNITIES:")
    for i, job in enumerate(new_jobs, 1):
        print(f"  {i}. {job['title'][:60]} @ {job['company'][:40]}")
    print()
    print("=" * 120)
    
except Exception as e:
    print(f"❌ ERROR: {e}")
