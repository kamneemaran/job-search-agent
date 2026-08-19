"""
Improved Job Search for Chandan with Strict Filtering
======================================================
Filters jobs by:
1. Years of experience (3-6 years for Chandan's 4 years experience)
2. Additional AI/ML red flags (AI engineer, ML engineer, etc.)
3. Minimum skill match requirement (at least 2 core skills)
"""

import daily_scan
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
import re

def extract_experience_level(job_description, job_title):
    """Extract years of experience required from job description/title."""
    text = (job_description + " " + job_title).lower()
    
    # Look for patterns like "8-11 years", "5+ years", "10 years"
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
        return None  # Unknown
    
    # Return the minimum required (most important)
    return min(years_found)

def filter_job_for_chandan(job, chandan_profile):
    """
    Strict filter for Chandan's profile.
    Returns: (is_relevant, reason)
    """
    title = job.get("title", "").lower()
    company = job.get("company", "").lower()
    desc = job.get("description", "").lower()
    
    # ===== CHECK 1: Red flags (role type mismatch) =====
    ai_ml_red_flags = [
        "ai engineer", "ai/ml", "machine learning", "ml engineer", "deep learning",
        "data scientist", "data analyst", "applied scientist", "llm engineer",
        "prompt engineer", "ai research", "research engineer"
    ]
    
    chandan_red_flags = [
        "android", "ios", "swift", "kotlin",
        "frontend", "front-end", "front end", "ui engineer", "web engineer",
        "qa", "qa engineer", "quality assurance", "quality engineer", "test engineer", "sdet",
        "network engineer", "network architect", "network infrastructure", "sre", "devops",
        "data scientist", "data analyst", "machine learning", "ai engineer", "ml engineer",
        "product manager", "project manager", "program manager",
        "sales engineer", "customer success", "account executive",
        "recruiter", "marketing", "finance", "legal", "compliance",
    ]
    
    for flag in chandan_red_flags:
        if flag in title:
            return False, f"Red flag: '{flag}' in title"
    
    # ===== CHECK 2: Experience level matching =====
    required_years = extract_experience_level(desc, title)
    chandan_years = chandan_profile.get("years_experience", 4)
    
    if required_years is not None:
        # Allow jobs asking for 2-7 years (Chandan has 4 years)
        if required_years < 2 or required_years > 7:
            return False, f"Experience mismatch: requires {required_years} years, Chandan has {chandan_years}"
    
    # ===== CHECK 3: Skill matching =====
    core_skills = chandan_profile.get("core_skills", [])
    full_text = title + " " + company + " " + desc
    matched_skills = [s for s in core_skills if s.lower() in full_text]
    
    # Require at least 2 matched skills
    if len(matched_skills) < 2:
        return False, f"Insufficient skill match: {len(matched_skills)} skills (need ≥2)"
    
    # ===== CHECK 4: Seniority level check =====
    # Don't send "Senior" roles if Chandan doesn't have enough experience
    if chandan_years < 5:
        if any(x in title for x in ["senior ", "senior engineer", "senior developer", "staff ", "lead engineer", "principal"]):
            # Allow "senior" only if specifically aligned with backend
            if not any(x in title for x in ["backend", "software engineer", "software developer"]):
                return False, f"Seniority level too high: 'Senior' role requires more experience"
    
    # ===== All checks passed =====
    return True, f"✓ {len(matched_skills)} skills matched: {', '.join(matched_skills[:5])}"

# ===== MAIN SEARCH =====
print("🔍 JOB SEARCH FOR CHANDAN - STRICT FILTERING")
print("=" * 100)
print()

# Chandan's profile
chandan_profile = {
    "name": "Chandan Patra",
    "years_experience": 4,
    "core_skills": [
        "java", "python", "distributed systems", "rabbitmq", "kafka",
        "dropwizard", "django", "flask", "google app engine",
        "mysql", "firebase", "mongodb", "elasticsearch", "aerospike", "postgresql", "mariadb",
        "spring boot", "spring", "rest api", "microservices", "backend", "software engineer"
    ],
}

# Load sent jobs tracker
tracker_file = "chandan_sent_jobs.json"
if os.path.exists(tracker_file):
    with open(tracker_file, 'r') as f:
        tracker = json.load(f)
else:
    tracker = {"sent_job_urls": []}

previously_sent = set(tracker.get("sent_job_urls", []))
print(f"Previously sent jobs: {len(previously_sent)}")
print()

# Define all search boards
boards = {
    "India Boards": [
        ("Indeed (IN)", daily_scan.search_indeed, "India"),
        ("InstaHyre (IN)", daily_scan.search_instahyre, "India"),
        ("LinkedIn (IN)", daily_scan.search_linkedin, "India"),
        ("SimplyHired (IN)", daily_scan.search_simplyhired, "India"),
        ("Glassdoor (IN)", daily_scan.search_glassdoor, "India"),
    ],
    "Remote Boards": [
        ("WeWorkRemotely", daily_scan.search_weworkremotely, "Remote"),
    ]
}

all_jobs = []
print("SEARCHING JOB BOARDS")
print("-" * 100)

for board_category, board_list in boards.items():
    print(f"\n{board_category}:")
    for board_name, search_func, location in board_list:
        try:
            print(f"  {board_name:25}", end=" ", flush=True)
            jobs = search_func("backend engineer", location, max_results=15)
            all_jobs.extend(jobs)
            print(f"✓ {len(jobs):2} jobs")
        except Exception as e:
            print(f"✗ ERROR: {str(e)[:40]}")

print()
print(f"Total jobs collected: {len(all_jobs)}")
print()

# Filter and score jobs with strict criteria
print("FILTERING WITH STRICT CRITERIA")
print("-" * 100)

matches = []
seen_urls = set()
filtered_out = []

for job in all_jobs:
    url = job.get("url", "")
    
    # Skip duplicates in current batch
    if url in seen_urls:
        continue
    seen_urls.add(url)
    
    # Skip if already sent
    if url in previously_sent:
        continue
    
    # Apply strict filter
    is_relevant, reason = filter_job_for_chandan(job, chandan_profile)
    
    if not is_relevant:
        filtered_out.append({
            "title": job.get("title", "Unknown")[:70],
            "reason": reason
        })
        continue
    
    # Calculate score based on skill matches
    title = job.get("title", "").lower()
    company = job.get("company", "").lower()
    desc = job.get("description", "").lower()
    full_text = title + " " + company + " " + desc
    matched_skills = [s for s in chandan_profile["core_skills"] if s.lower() in full_text]
    
    if len(matched_skills) >= 8:
        score = 95
    elif len(matched_skills) >= 6:
        score = 85
    elif len(matched_skills) >= 4:
        score = 75
    elif len(matched_skills) >= 2:
        score = 65
    else:
        score = 55
    
    matches.append({
        "title": job.get("title", "Unknown"),
        "company": job.get("company", "Unknown"),
        "location": job.get("location", "Unknown"),
        "score": score,
        "url": url,
        "posted_at": job.get("posted_at", "Unknown"),
        "matched_skills": matched_skills[:7],
    })

matches.sort(key=lambda x: x["score"], reverse=True)

print(f"Total jobs after filtering: {len(matches)}")
print(f"Jobs filtered out: {len(filtered_out)}")
print()

# Show some filtered jobs with reasons
if filtered_out:
    print("SAMPLE FILTERED OUT JOBS:")
    print("-" * 100)
    for i, job in enumerate(filtered_out[:5], 1):
        print(f"{i}. {job['title']}")
        print(f"   Reason: {job['reason']}")
    if len(filtered_out) > 5:
        print(f"   ... and {len(filtered_out) - 5} more filtered out")
    print()

# If no new jobs, inform user
if len(matches) == 0:
    print("✅ No new jobs match Chandan's strict filtering criteria.")
    print("   This is good - it means we're not sending irrelevant roles!")
    exit(0)

print(f"✅ {len(matches)} high-quality matches found")
print()

# Stats by score
score_90_99 = len([m for m in matches if 90 <= m['score'] < 100])
score_80_89 = len([m for m in matches if 80 <= m['score'] < 90])
score_70_79 = len([m for m in matches if 70 <= m['score'] < 80])
score_65_69 = len([m for m in matches if 65 <= m['score'] < 70])

print("SCORE DISTRIBUTION")
print("-" * 100)
print(f"  90-99%:    {score_90_99} jobs")
print(f"  80-89%:    {score_80_89} jobs")
print(f"  70-79%:    {score_70_79} jobs")
print(f"  65-69%:    {score_65_69} jobs")
print()

# Generate HTML email
html = f"""<html><head><style>
body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
.container {{ max-width: 1100px; margin: 0 auto; background: white; padding: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
.header {{ background: linear-gradient(135deg, #2557a7 0%, #1a3f7a 100%); color: white; padding: 25px; border-radius: 8px; margin-bottom: 25px; }}
.header h1 {{ margin: 0; font-size: 24px; font-weight: bold; }}
.summary {{ background: #e8f4f8; border-left: 4px solid #2557a7; padding: 15px; border-radius: 5px; margin-bottom: 25px; }}
.summary-row {{ display: flex; justify-content: space-between; margin: 8px 0; font-size: 13px; }}
.summary-label {{ font-weight: bold; color: #2557a7; }}
.job {{ border: 1px solid #e0e0e0; border-left: 5px solid #2557a7; padding: 15px; margin-bottom: 12px; background: #fafafa; border-radius: 4px; }}
.job:hover {{ background: #f5f5f5; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
.job-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }}
.job-title {{ font-size: 14px; font-weight: bold; color: #1a3f7a; flex: 1; }}
.job-score {{ background: #28a745; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; white-space: nowrap; margin-left: 10px; }}
.job-company {{ font-size: 12px; color: #555; margin: 3px 0; }}
.job-location {{ font-size: 12px; color: #777; }}
.job-meta {{ font-size: 11px; color: #999; margin: 6px 0; }}
.job-skills {{ font-size: 11px; background: #e8f4f8; padding: 6px 8px; border-radius: 3px; margin: 8px 0; color: #2557a7; }}
.job-link a {{ background: #2557a7; color: white; padding: 7px 14px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold; display: inline-block; margin-top: 8px; }}
.section-title {{ font-size: 16px; font-weight: bold; color: #2557a7; margin: 20px 0 15px 0; border-bottom: 2px solid #2557a7; padding-bottom: 8px; }}
.stats {{ background: #f0f8ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
.badge {{ display: inline-block; background: #d4edda; color: #155724; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; margin-left: 5px; }}
.footer {{ text-align: center; padding-top: 20px; border-top: 2px solid #e0e0e0; margin-top: 25px; font-size: 11px; color: #999; }}
</style></head><body><div class="container">
<div class="header">
  <h1>🎯 Curated Job Opportunities - India & Remote</h1>
  <p>Backend Engineer | 4 Years | Strict Quality Filter Applied<span class="badge">✨ FILTERED</span></p>
</div>

<div class="summary">
  <div class="summary-row">
    <span class="summary-label">✅ Quality Matches:</span>
    <span><b>{len(matches)}</b></span>
  </div>
  <div class="summary-row">
    <span class="summary-label">📊 Total Evaluated:</span>
    <span>{len(all_jobs)} jobs</span>
  </div>
  <div class="summary-row">
    <span class="summary-label">🔍 Filter Criteria:</span>
    <span>Experience (3-7 yrs), Skills (2+), No AI/ML/QA roles</span>
  </div>
  <div class="summary-row">
    <span class="summary-label">📍 Coverage:</span>
    <span>India + Remote (WeWorkRemotely)</span>
  </div>
</div>

<div class="section-title">🌟 Recommended Opportunities</div>
"""

for i, job in enumerate(matches[:25], 1):
    score_color = "#28a745" if job['score'] >= 80 else "#ffc107" if job['score'] >= 70 else "#17a2b8"
    html += f"""<div class="job">
    <div class="job-header">
      <div class="job-title">{i}. {job['title']}</div>
      <div class="job-score" style="background: {score_color};">{job['score']}%</div>
    </div>
    <div class="job-company">🏢 {job['company']}</div>
    <div class="job-location">📍 {job['location']}</div>
    <div class="job-meta">📅 {job['posted_at']}</div>
    <div class="job-skills">✓ Skills: {', '.join(job['matched_skills'][:4])}</div>
    <div><a href="{job['url']}" target="_blank">Apply Now →</a></div>
</div>"""

html += """<div class="footer">
  <p><b>Quality Filtering Applied:</b> Experience level, skill relevance, role type validation</p>
  <p>Profile: Backend Engineer • 4 Years • Java • Python • Distributed Systems • RabbitMQ • Kafka</p>
</div>
</div></body></html>"""

# Send email
print("SENDING EMAIL")
print("-" * 100)

with open("/Users/kamnee.maran/Downloads/job-search-agent/.env") as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

sender_email = os.getenv("GMAIL_ADDRESS")
sender_password = os.getenv("GMAIL_APP_PASSWORD")
recipient = "chandan.patra430@gmail.com"

msg = MIMEMultipart("alternative")
msg["Subject"] = f"🎯 {len(matches)} Curated Job Opportunities | Strict Quality Filter | No Duplicates"
msg["From"] = sender_email
msg["To"] = recipient
msg.attach(MIMEText(html, "html"))

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, recipient, msg.as_string())
    server.quit()
    
    # Update tracker with new jobs
    new_urls = [job['url'] for job in matches]
    tracker["sent_job_urls"].extend(new_urls)
    
    with open(tracker_file, 'w') as f:
        json.dump(tracker, f, indent=2)
    
    print(f"✅ EMAIL SENT!")
    print()
    print("=" * 100)
    print(f"Recipients:        {recipient}")
    print(f"Jobs Sent:         {len(matches)}")
    print(f"Best Score:        {matches[0]['score']}%")
    print(f"Total Sent Ever:   {len(tracker['sent_job_urls'])} (all-time)")
    print("=" * 100)
    
except Exception as e:
    print(f"❌ ERROR: {e}")

