"""
Job Search for 8-Year Backend Engineer (Senior/Staff Level)
==============================================================
Profile: Senior Software Engineer / Staff Software Engineer / Senior Backend Engineer
Experience: 8 years (strict: 7-10 years)
Location: India
Posted: < 7 days
Skills: Java, SpringBoot, Hibernate, Python, MySQL, Redis, ElasticSearch, Aerospike, HBase, MariaDB, DynamoDB, Docker, Kubernetes, AOP, Jenkins, OpenTelemetry
"""

import daily_scan
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
import re

def extract_experience_range(job_description, job_title):
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
        return None, None
    
    # Return min and max
    return min(years_found), max(years_found)

def is_recent_posting(posted_at):
    """Check if job was posted less than 7 days ago."""
    if not posted_at or posted_at == "Unknown":
        return True  # Assume recent if unknown
    
    try:
        if isinstance(posted_at, str):
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]:
                try:
                    post_date = datetime.strptime(posted_at.split()[0], fmt)
                    break
                except:
                    continue
            else:
                return True  # Can't parse, assume recent
        else:
            post_date = posted_at
        
        days_old = (datetime.now() - post_date).days
        return days_old <= 7
    except:
        return True

def filter_job_for_senior_backend(job, profile):
    """
    Strict filter for 8-year backend engineer.
    Returns: (is_relevant, reason)
    """
    title = job.get("title", "").lower()
    company = job.get("company", "").lower()
    desc = job.get("description", "").lower()
    posted_at = job.get("posted_at", "Unknown")
    
    # ===== CHECK 1: Role type matching =====
    # Only accept specific roles
    target_roles = [
        "senior software engineer", "senior engineer", "staff software engineer", 
        "staff engineer", "senior backend engineer", "backend engineer",
        "senior developer", "backend developer", "software engineer"
    ]
    
    has_target_role = any(role in title for role in target_roles)
    if not has_target_role:
        return False, f"Role mismatch: not in target roles (Senior/Staff/Backend)"
    
    # Red flags - exclude these roles completely
    red_flags = [
        "android", "ios", "swift", "kotlin",  # Mobile
        "frontend", "front-end", "front end", "ui ", "ux ", "web engineer",  # Frontend
        "qa", "qa engineer", "quality assurance", "test engineer", "sdet", "automation",  # QA
        "devops", "devops engineer", "sre", "site reliability",  # DevOps/SRE
        "product manager", "project manager", "program manager",  # Management
        "sales engineer", "customer success", "account manager",  # Sales
        "data scientist", "data analyst", "machine learning", "ai engineer", "ml engineer",  # Data/AI
        "recruiter", "marketing", "finance", "legal", "compliance",  # Non-engineering
        "network engineer", "network architect",  # Network
    ]
    
    for flag in red_flags:
        if flag in title:
            return False, f"Red flag: '{flag}' - wrong career track"
    
    # ===== CHECK 2: Experience level matching =====
    min_years, max_years = extract_experience_range(desc, title)
    profile_years = profile.get("years_experience", 8)
    
    if min_years is not None and max_years is not None:
        # Strict: 7-10 years bracket
        # Job should ask for 7-10 years (Candidate has 8)
        if max_years < 7 or min_years > 10:
            return False, f"Experience out of bracket: job requires {min_years}-{max_years} yrs (need 7-10)"
    
    # ===== CHECK 3: Posting date check =====
    if not is_recent_posting(posted_at):
        return False, f"Posting too old: {posted_at}"
    
    # ===== CHECK 4: Skill matching =====
    core_skills = profile.get("core_skills", [])
    full_text = title + " " + company + " " + desc
    matched_skills = [s for s in core_skills if s.lower() in full_text.lower()]
    
    # Require at least 3 matched skills for senior level
    if len(matched_skills) < 3:
        return False, f"Insufficient skill match: {len(matched_skills)} skills (need ≥3)"
    
    # ===== CHECK 5: Location check =====
    location = job.get("location", "").lower()
    if "india" not in location and "bangalore" not in location and "delhi" not in location and \
       "mumbai" not in location and "pune" not in location and "gurgaon" not in location and \
       "hyderabad" not in location and "noida" not in location and "kolkata" not in location:
        # Allow if location is unclear (assume India)
        if location and location != "unknown" and location != "remote":
            if not any(city in location for city in ["bangalore", "delhi", "mumbai", "pune", "hyderabad", "gurgaon", "noida", "bangalore", "kolkata", "india"]):
                return False, f"Location mismatch: {location} (need India)"
    
    # ===== All checks passed =====
    return True, f"✓ {len(matched_skills)} skills matched"

# ===== MAIN SEARCH =====
print("\n" + "=" * 110)
print("🔍 JOB SEARCH - SENIOR BACKEND ENGINEER (8 YEARS EXPERIENCE)")
print("=" * 110)
print()

# Profile
profile = {
    "name": "Senior Backend Engineer",
    "years_experience": 8,
    "core_skills": [
        "java", "springboot", "spring", "hibernate", "python",
        "mysql", "redis", "elasticsearch", "aerospike", "hbase", "mariadb", "dynamodb",
        "docker", "kubernetes", "aop", "jenkins", "opentelemetry",
        "microservices", "backend", "rest api", "distributed systems",
        "software engineer", "senior engineer"
    ],
}

# All India boards
india_boards = [
    ("Indeed", daily_scan.search_indeed, "India"),
    ("InstaHyre", daily_scan.search_instahyre, "India"),
    ("LinkedIn", daily_scan.search_linkedin, "India"),
    ("SimplyHired", daily_scan.search_simplyhired, "India"),
    ("Glassdoor", daily_scan.search_glassdoor, "India"),
]

all_jobs = []

print("SEARCHING ALL INDIA BOARDS")
print("-" * 110)

for board_name, search_func, location in india_boards:
    try:
        print(f"{board_name:20}", end=" ", flush=True)
        jobs = search_func("senior backend engineer", location, max_results=20)
        all_jobs.extend(jobs)
        print(f"✓ {len(jobs):2} jobs")
    except Exception as e:
        print(f"✗ ERROR: {str(e)[:40]}")

print()
print(f"Total jobs collected: {len(all_jobs)}")
print()

# Filter and score
print("FILTERING WITH STRICT CRITERIA")
print("-" * 110)

matches = []
seen_urls = set()
filtered_out = []

for job in all_jobs:
    url = job.get("url", "")
    
    # Skip duplicates
    if url in seen_urls:
        continue
    seen_urls.add(url)
    
    # Apply strict filter
    is_relevant, reason = filter_job_for_senior_backend(job, profile)
    
    if not is_relevant:
        filtered_out.append({
            "title": job.get("title", "Unknown")[:60],
            "reason": reason
        })
        continue
    
    # Calculate score
    title = job.get("title", "").lower()
    company = job.get("company", "").lower()
    desc = job.get("description", "").lower()
    full_text = title + " " + company + " " + desc
    matched_skills = [s for s in profile["core_skills"] if s.lower() in full_text.lower()]
    
    if len(matched_skills) >= 10:
        score = 100
    elif len(matched_skills) >= 8:
        score = 95
    elif len(matched_skills) >= 6:
        score = 85
    elif len(matched_skills) >= 4:
        score = 75
    else:
        score = 65
    
    matches.append({
        "title": job.get("title", "Unknown"),
        "company": job.get("company", "Unknown"),
        "location": job.get("location", "Unknown"),
        "score": score,
        "url": url,
        "posted_at": job.get("posted_at", "Unknown"),
        "matched_skills": matched_skills[:8],
    })

matches.sort(key=lambda x: x["score"], reverse=True)

print(f"Total matches: {len(matches)}")
print(f"Filtered out: {len(filtered_out)}")
print()

# Show filter reasons
if filtered_out:
    print("FILTER SUMMARY (Sample):")
    print("-" * 110)
    reasons_count = {}
    for job in filtered_out:
        reason = job['reason'].split(":")[0]
        reasons_count[reason] = reasons_count.get(reason, 0) + 1
    
    for reason, count in sorted(reasons_count.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason:40} {count:3} jobs")
    print()

if len(matches) == 0:
    print("❌ No matching jobs found. Adjust criteria.")
    exit(1)

print(f"✅ {len(matches)} high-quality matches found!")
print()

# Score distribution
score_dist = {
    "100%": len([m for m in matches if m['score'] == 100]),
    "95%": len([m for m in matches if m['score'] == 95]),
    "85%": len([m for m in matches if m['score'] == 85]),
    "75%": len([m for m in matches if m['score'] == 75]),
    "65%": len([m for m in matches if m['score'] == 65]),
}

print("SCORE DISTRIBUTION")
print("-" * 110)
for score, count in score_dist.items():
    if count > 0:
        print(f"  {score:5}  {count:3} jobs")
print()

# Generate HTML email
html = f"""<html><head><style>
body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
.container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
.header {{ background: linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }}
.header h1 {{ margin: 0; font-size: 26px; font-weight: bold; }}
.header p {{ margin: 8px 0 0 0; font-size: 15px; opacity: 0.95; }}
.summary {{ background: #eff6ff; border-left: 5px solid #1e40af; padding: 20px; border-radius: 5px; margin-bottom: 30px; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 15px; }}
.summary-item {{ }}
.summary-label {{ font-weight: bold; color: #1e40af; font-size: 12px; text-transform: uppercase; }}
.summary-value {{ font-size: 18px; font-weight: bold; color: #1e3a8a; margin-top: 5px; }}
.job {{ border: 1px solid #e5e7eb; border-left: 5px solid #1e40af; padding: 18px; margin-bottom: 15px; background: #fafbfc; border-radius: 5px; }}
.job:hover {{ background: #f3f4f6; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.job-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
.job-title {{ font-size: 15px; font-weight: bold; color: #1e3a8a; flex: 1; line-height: 1.4; }}
.job-score {{ background: #059669; color: white; padding: 5px 12px; border-radius: 4px; font-weight: bold; font-size: 13px; white-space: nowrap; margin-left: 10px; }}
.job-score.high {{ background: #dc2626; }}
.job-score.medium {{ background: #f59e0b; color: #000; }}
.job-company {{ font-size: 13px; color: #4b5563; margin: 5px 0; font-weight: 600; }}
.job-location {{ font-size: 12px; color: #6b7280; margin: 3px 0; }}
.job-meta {{ font-size: 11px; color: #9ca3af; margin: 6px 0; }}
.job-skills {{ background: #ecfdf5; border-left: 3px solid #059669; padding: 8px 10px; margin: 10px 0; border-radius: 3px; font-size: 12px; color: #047857; }}
.job-link a {{ background: #1e40af; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: bold; display: inline-block; margin-top: 10px; transition: background 0.2s; }}
.job-link a:hover {{ background: #1e3a8a; }}
.section-title {{ font-size: 18px; font-weight: bold; color: #1e3a8a; margin: 25px 0 15px 0; border-bottom: 2px solid #1e40af; padding-bottom: 10px; }}
.stats {{ background: #f0f9ff; padding: 20px; border-radius: 5px; margin-bottom: 25px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-top: 15px; }}
.stat-box {{ text-align: center; background: white; padding: 15px; border-radius: 5px; border: 1px solid #e5e7eb; }}
.stat-number {{ font-size: 22px; font-weight: bold; color: #1e40af; }}
.stat-label {{ font-size: 11px; color: #6b7280; margin-top: 5px; text-transform: uppercase; }}
.footer {{ text-align: center; padding-top: 25px; border-top: 2px solid #e5e7eb; margin-top: 30px; font-size: 11px; color: #9ca3af; }}
.badge {{ display: inline-block; background: #fecaca; color: #991b1b; padding: 3px 8px; border-radius: 3px; font-size: 10px; font-weight: bold; margin-left: 8px; }}
.profile-badge {{ background: #dcfce7; color: #166534; padding: 8px 12px; border-radius: 4px; font-size: 12px; margin-bottom: 10px; display: inline-block; }}
</style></head><body><div class="container">
<div class="header">
  <h1>🎯 Senior Backend Engineer - Curated Opportunities</h1>
  <p>8 Years Experience | India | Posted < 7 Days | Strict Quality Filter</p>
</div>

<div class="summary">
  <div class="profile-badge">👤 8 Years | Java, SpringBoot, Python, MySQL, Redis, Kubernetes, Docker, OpenTelemetry</div>
  <div class="summary-grid">
    <div class="summary-item">
      <div class="summary-label">Total Matches</div>
      <div class="summary-value">{len(matches)}</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">Jobs Evaluated</div>
      <div class="summary-value">{len(all_jobs)}</div>
    </div>
    <div class="summary-item">
      <div class="summary-label">Best Score</div>
      <div class="summary-value">{matches[0]['score']}%</div>
    </div>
  </div>
</div>

<div class="stats">
  <div style="font-weight: bold; color: #1e3a8a; margin-bottom: 10px;">Score Distribution</div>
  <div class="stats-grid">
    <div class="stat-box">
      <div class="stat-number" style="color: #dc2626;">{score_dist['100%']}</div>
      <div class="stat-label">100%</div>
    </div>
    <div class="stat-box">
      <div class="stat-number" style="color: #f59e0b;">{score_dist['95%']}</div>
      <div class="stat-label">95%</div>
    </div>
    <div class="stat-box">
      <div class="stat-number" style="color: #0891b2;">{score_dist['85%']}</div>
      <div class="stat-label">85%</div>
    </div>
    <div class="stat-box">
      <div class="stat-number" style="color: #059669;">{score_dist['75%']}</div>
      <div class="stat-label">75%</div>
    </div>
    <div class="stat-box">
      <div class="stat-number" style="color: #6b7280;">{score_dist['65%']}</div>
      <div class="stat-label">65%</div>
    </div>
  </div>
</div>

<div class="section-title">🌟 Top Opportunities</div>
"""

for i, job in enumerate(matches[:30], 1):
    if job['score'] >= 95:
        score_class = "high"
    elif job['score'] >= 80:
        score_class = "medium"
    else:
        score_class = ""
    
    html += f"""<div class="job">
    <div class="job-header">
      <div class="job-title">{i}. {job['title']}</div>
      <div class="job-score {score_class}">{job['score']}%</div>
    </div>
    <div class="job-company">🏢 {job['company']}</div>
    <div class="job-location">📍 {job['location']}</div>
    <div class="job-meta">📅 Posted: {job['posted_at']}</div>
    <div class="job-skills">✓ Skills: {', '.join(job['matched_skills'][:6])}</div>
    <div class="job-link"><a href="{job['url']}" target="_blank">Apply Now →</a></div>
</div>"""

html += f"""
<div class="footer">
  <p><b>Filter Criteria Applied:</b> Experience (7-10 years) • Role (Senior/Staff/Backend Engineer) • Location (India) • Posted (<7 days) • Skills (3+ matched)</p>
  <p>Evaluated: {len(all_jobs)} jobs across 5 India boards • Matched: {len(matches)} • Filtered: {len(filtered_out)}</p>
  <p>Boards: Indeed • InstaHyre • LinkedIn • SimplyHired • Glassdoor</p>
</div>
</div></body></html>"""

# Send email
print("SENDING EMAIL")
print("-" * 110)

with open("/Users/kamnee.maran/Downloads/job-search-agent/.env") as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

sender_email = os.getenv("GMAIL_ADDRESS")
sender_password = os.getenv("GMAIL_APP_PASSWORD")

# Get recipient email from user or use default
recipient = input("Enter recipient email (or press Enter for chandan.patra430@gmail.com): ").strip()
if not recipient:
    recipient = "chandan.patra430@gmail.com"

msg = MIMEMultipart("alternative")
msg["Subject"] = f"🎯 {len(matches)} Senior Backend Engineer Opportunities | 8 Yrs | India | < 7 Days"
msg["From"] = sender_email
msg["To"] = recipient
msg.attach(MIMEText(html, "html"))

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, recipient, msg.as_string())
    server.quit()
    
    print(f"✅ EMAIL SENT!")
    print()
    print("=" * 110)
    print("RESULTS SUMMARY")
    print("=" * 110)
    print(f"Recipient:           {recipient}")
    print(f"Subject:             {len(matches)} Senior Backend Engineer Opportunities | 8 Yrs | India")
    print(f"Total Jobs Sent:     {len(matches)}")
    print(f"Best Match Score:    {matches[0]['score']}% - {matches[0]['title'][:60]}")
    print(f"Companies:           {len(set(m['company'] for m in matches))} unique companies")
    print()
    print("TOP 5 OPPORTUNITIES:")
    for i, job in enumerate(matches[:5], 1):
        print(f"  {i}. [{job['score']}%] {job['title'][:60]} @ {job['company'][:40]}")
    print()
    print("=" * 110)
    
except Exception as e:
    print(f"❌ ERROR: {e}")

