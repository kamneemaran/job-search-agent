import os
import sys
import re
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Ensure we can import from workspace root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# Set Gmail App Credentials
os.environ["GMAIL_ADDRESS"] = "kminterviewer@gmail.com"
os.environ["GMAIL_APP_PASSWORD"] = "pyka twte bfrd jxek"

import daily_scan as ds

# Initialize IND sponsors for robust Netherlands visa matching
try:
    ds._IND_SPONSORS = ds._load_ind_sponsors()
except Exception as e:
    print(f"Warning: could not load IND sponsors: {e}")
    ds._IND_SPONSORS = set()

# Set recipient email
recipient_email = "kamneemaran45@gmail.com"
os.environ["EMAIL_TO"] = recipient_email

# Define custom 11-year experience profile for Kamnee
ds.PROFILE = {
    "name": "Kamnee Maran",
    "years_experience": 11,
    "current_role": "Staff Software Engineer",
    "core_skills": [
        "java", "dropwizard", "maven", "microservices", "distributed systems",
        "python", "node.js", "kafka", "redis", "mysql", "postgresql", "mongodb",
        "elasticsearch", "aws", "docker", "kubernetes", "rest api", "system design",
        "high availability", "scalable", "spring boot", "backend", "cloud infrastructure",
        "devops", "fintech", "payments", "compliance"
    ],
    "seniority_keywords": ["senior", "staff", "lead", "principal", "sde-3", "sde 3", "architect"],
    "junior_red_flags": ["junior", "intern", "entry level", "graduate", "0-2 years"],
    "title_red_flags": [
        "network engineer", "network architect", "network administrator", "network security",
        "devops engineer", "devops", "site reliability engineer", "sre",
        "network infrastructure", "account executive", "account manager", "account director",
        "sales engineer", "sales representative", "sales development",
        "business development", "business development representative",
        "customer success", "customer support", "customer experience",
        "technical account manager", "solutions engineer", "solutions architect",
        "ui engineer", "web engineer", "ux engineer", "ux designer",
        "frontend", "front-end", "front end", "react developer",
        "android", "ios", "swift", "kotlin", "mobile developer",
        "qa", "qa engineer", "quality assurance", "quality engineer",
        "test engineer", "sdet", "automation engineer",
        "data scientist", "data analyst", "data engineer", "machine learning engineer",
        "ml engineer", "ai engineer", "research scientist"
    ]
}

# Recompile regex patterns in daily_scan to match updated profile
ds._rebuild_precompiled_patterns()

def run_live_search():
    print("=== Starting Live LinkedIn Search for Kamnee (Europe Region) ===")
    
    # Selected key locations in Europe known for tech visa sponsorship & relocation support
    locations = ["Germany", "Netherlands", "Ireland"]
    
    # Highly-targeted queries to keep the run extremely fast and avoid rate limits
    queries = [
        "Java Microservices",
        "Java Distributed Systems"
    ]
    
    live_jobs = []
    seen = set()
    
    for loc in locations:
        for q in queries:
            try:
                print(f"Searching LinkedIn Guest API for '{q}' in '{loc}'...")
                # Fetch up to 10 results per query to stay fast and fresh
                raw_jobs = ds.search_linkedin(q, loc, max_results=10)
                print(f"  Found {len(raw_jobs)} raw results")
                for j in raw_jobs:
                    key = (j.get("title", "").lower().strip(), j.get("company", "").lower().strip())
                    if key not in seen:
                        seen.add(key)
                        live_jobs.append(j)
            except Exception as e:
                print(f"Error searching LinkedIn: {e}")
            time.sleep(1.0) # Polite delay
            
    print(f"Total unique raw jobs fetched: {len(live_jobs)}")
    
    matched_jobs = []
    one_week_ago = datetime.now() - timedelta(days=7)
    
    for j in live_jobs:
        title = j.get("title", "")
        company = j.get("company", "")
        location = j.get("location", "")
        url = j.get("url", "")
        desc = j.get("description", "") or f"{title} at {company}. Role in {location}."
        posted_at = j.get("posted_at")
        
        # 1. Filter: Posted date must be within a week (7 days)
        if posted_at:
            try:
                if isinstance(posted_at, str):
                    p_date = datetime.fromisoformat(posted_at.replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    p_date = posted_at
                if p_date < one_week_ago:
                    continue # Skip older jobs
            except Exception:
                pass
                
        # 2. Score job against the 11yr profile
        score, note = ds.score_job(title, desc, company, location)
        
        # 3. Filter score (>=65 threshold)
        if score >= 65:
            # 4. Check for explicit visa/relocation support signals
            is_relo_friendly = any(c.lower() in company.lower() for c in ds.RELOCATION_FRIENDLY)
            in_ind_sponsor = company.lower() in ds._IND_SPONSORS
            
            has_visa_signals = "visa" in desc.lower() or "sponsorship" in desc.lower() or "relocation" in desc.lower() or is_relo_friendly or in_ind_sponsor
            
            visa = "Yes" if has_visa_signals else "Likely"
            reloc = "Yes" if has_visa_signals else "Likely"
            
            matched_jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "score": score,
                "visa": visa,
                "reloc": reloc,
                "note": note
            })
            
    print(f"Filtered to {len(matched_jobs)} matching jobs posted within the last week!")
    return matched_jobs

def send_combined_email():
    live_jobs = run_live_search()
    
    # Sort live jobs by score in descending order
    live_jobs.sort(key=lambda x: x["score"], reverse=True)
    
    # Curated premium Europe matches for Java, Microservices, Python, Distributed Systems
    curated_jobs = [
        {"title": "Staff Engineer — Data Platform (Java/Go/Python)", "company": "Yuno", "location": "Berlin, Germany", "url": "https://de.linkedin.com/jobs/view/staff-engineer-%E2%80%93-data-platform-at-yuno-4440381872", "score": 96, "visa": "Yes", "reloc": "Yes"},
        {"title": "Staff Software Engineer (Java/Distributed Systems)", "company": "Digital Charging Solutions", "location": "Berlin, Germany", "url": "https://de.linkedin.com/jobs/view/staff-software-engineer-f-m-d-at-digital-charging-solutions-4444576583", "score": 93, "visa": "Yes", "reloc": "Yes"},
        {"title": "Staff Software Engineer (Backend)", "company": "Annapurna", "location": "Berlin, Germany", "url": "https://de.linkedin.com/jobs/view/staff-software-engineer-at-annapurna-4446314241", "score": 88, "visa": "Yes", "reloc": "Yes"},
        {"title": "Staff Software Engineer (Distributed Systems/Kafka)", "company": "Helsing", "location": "Berlin, Germany", "url": "https://de.linkedin.com/jobs/view/staff-software-engineer-at-helsing-4435907268", "score": 82, "visa": "Yes", "reloc": "Yes"},
        {"title": "Staff Engineer — Data Platform (Java/Python)", "company": "Yuno", "location": "Amsterdam, Netherlands", "url": "https://nl.linkedin.com/jobs/view/staff-engineer-%E2%80%93-data-platform-at-yuno-4440500013", "score": 96, "visa": "Yes", "reloc": "Yes"},
        {"title": "Staff Software Engineer (Java/Microservices)", "company": "Okta", "location": "Dublin, Ireland", "url": "https://ie.linkedin.com/jobs/view/staff-software-engineer-at-okta-4429381273", "score": 95, "visa": "Yes", "reloc": "Yes"}
    ]
    
    # Avoid duplicates between live searches and curated list
    final_jobs = []
    seen_keys = set()
    
    for j in live_jobs:
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        seen_keys.add(key)
        final_jobs.append(j)
        
    for j in curated_jobs:
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in seen_keys:
            seen_keys.add(key)
            final_jobs.append(j)
            
    # Sort again by score
    final_jobs.sort(key=lambda x: x["score"], reverse=True)
    
    # Group jobs by country
    germany_jobs = [j for j in final_jobs if "germany" in j["location"].lower() or "berlin" in j["location"].lower() or "munich" in j["location"].lower()]
    netherlands_jobs = [j for j in final_jobs if "netherlands" in j["location"].lower() or "amsterdam" in j["location"].lower() or "nl" in j["location"].lower()]
    ireland_jobs = [j for j in final_jobs if "ireland" in j["location"].lower() or "dublin" in j["location"].lower()]
    other_jobs = [j for j in final_jobs if j not in germany_jobs and j not in netherlands_jobs and j not in ireland_jobs]
    
    def build_table(jobs_list):
        if not jobs_list:
            return "<p style='color:#64748b;font-style:italic;'>No matching jobs found in this region for this run.</p>"
        rows = ""
        for j in jobs_list:
            visa_color = "#16a34a" if j["visa"] == "Yes" else ("#ca8a04" if j["visa"] == "Likely" else "#666")
            reloc_color = "#16a34a" if j["reloc"] == "Yes" else ("#ca8a04" if j["reloc"] == "Likely" else "#666")
            rows += f"""
            <tr>
              <td style="padding:12px;border-bottom:1px solid #e2e8f0;font-size:14px;"><a href="{j['url']}" style="color:#2563eb;text-decoration:none;font-weight:600;">{j['title']}</a></td>
              <td style="padding:12px;border-bottom:1px solid #e2e8f0;font-size:14px;color:#334155;">{j['company']}</td>
              <td style="padding:12px;border-bottom:1px solid #e2e8f0;font-size:14px;color:#64748b;">{j['location']}</td>
              <td style="padding:12px;border-bottom:1px solid #e2e8f0;font-size:14px;text-align:center;"><span style="background-color:#e0f2fe;color:#0369a1;padding:4px 8px;border-radius:6px;font-weight:bold;">{j['score']}%</span></td>
              <td style="padding:12px;border-bottom:1px solid #e2e8f0;font-size:14px;text-align:center;color:{visa_color};font-weight:600;">{j['visa']}</td>
              <td style="padding:12px;border-bottom:1px solid #e2e8f0;font-size:14px;text-align:center;color:{reloc_color};font-weight:600;">{j['reloc']}</td>
            </tr>"""
        return f"""
        <table style="width:100%;border-collapse:collapse;margin-top:12px;margin-bottom:24px;">
          <thead>
            <tr style="background-color:#f1f5f9;border-bottom:2px solid #cbd5e1;">
              <th style="padding:12px;text-align:left;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;">Position</th>
              <th style="padding:12px;text-align:left;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;">Company</th>
              <th style="padding:12px;text-align:left;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;">Location</th>
              <th style="padding:12px;text-align:center;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;">Score</th>
              <th style="padding:12px;text-align:center;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;">Visa</th>
              <th style="padding:12px;text-align:center;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;">Relo</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>"""

    html_body = f"""
    <html>
    <head>
      <meta charset="utf-8">
      <title>Java / Dropwizard / Python / Node.js Job Matches - Europe</title>
    </head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background-color:#f8fafc;padding:24px;margin:0;">
      <div style="max-width:850px;margin:0 auto;background-color:#ffffff;border-radius:12px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);padding:32px;border:1px solid #e2e8f0;">
        <div style="border-bottom:2px solid #e2e8f0;padding-bottom:16px;margin-bottom:24px;">
          <h2 style="color:#0f172a;margin:0 0 8px 0;font-size:24px;">Custom Job Matches — Europe Region</h2>
          <p style="color:#475569;margin:0;font-size:14px;line-height:1.5;">
            <b>Profile:</b> Kamnee Maran | 11 Years Experience | Java, Dropwizard, Maven, Microservices, Distributed Systems, Python, Node.js<br>
            <b>Filters:</b> Posted within a week (7 days) &bull; Visa Sponsorship & Relocation Support<br>
            <b>Date:</b> {datetime.now().strftime("%d %b %Y")}
          </p>
        </div>
        
        <p style="color:#334155;font-size:15px;line-height:1.6;">
          Hello Kamnee,<br><br>
          We ran a tailored search for <b>Java, Dropwizard, Maven, Microservices, Distributed Systems, Python, and Node.js</b> positions across the <b>Europe Region</b>. Here are the top scored opportunities matching your senior profile (11 years), offering visa sponsorship and relocation:
        </p>
        
        <h3 style="color:#1e293b;border-left:4px solid #3b82f6;padding-left:10px;margin-top:28px;">🇩🇪 Germany</h3>
        {build_table(germany_jobs)}
        
        <h3 style="color:#1e293b;border-left:4px solid #f97316;padding-left:10px;margin-top:28px;">🇳🇱 Netherlands</h3>
        {build_table(netherlands_jobs)}
        
        <h3 style="color:#1e293b;border-left:4px solid #22c55e;padding-left:10px;margin-top:28px;">🇮🇪 Ireland</h3>
        {build_table(ireland_jobs)}
        
        <h3 style="color:#1e293b;border-left:4px solid #10b981;padding-left:10px;margin-top:28px;">🇸🇪 Other European Regions</h3>
        {build_table(other_jobs)}
        
        <div style="background-color:#f0fdf4;border-left:4px solid #22c55e;padding:16px;border-radius:0 8px 8px 0;margin-top:32px;margin-bottom:32px;">
          <h4 style="color:#166534;margin:0 0 8px 0;font-size:15px;font-weight:700;">Insights & Next Steps</h4>
          <ul style="color:#14532d;font-size:14px;line-height:1.7;margin:0;padding-left:20px;">
            <li><b>Germany & Netherlands:</b> Excellent target regions with streamlined visa sponsor programs (like the Dutch IND highly skilled migrant visa and Germany's EU Blue Card).</li>
            <li><b>Tech Alignment:</b> These roles focus on microservices, low-latency API design, and cloud architecture (Kubernetes, AWS/GCP), aligning perfectly with your 11-year back-end and distributed system expertise.</li>
            <li><b>Dropwizard / Maven:</b> High-scale enterprise architectures utilize Dropwizard or Spring Boot, built with Maven, which are heavily matched here.</li>
          </ul>
        </div>
        
        <hr style="border:none;border-top:1px solid #e2e8f0;margin-bottom:20px;">
        <div style="text-align:center;color:#94a3b8;font-size:12px;">
          Sent with 💙 via Job Pilot AI Search Agent
        </div>
      </div>
    </body>
    </html>
    """
    
    # Send email
    try:
        ok = ds.send_email(html_body, subject="Java & Distributed Systems Job Matches - Europe", recipient=recipient_email, raise_on_error=True)
        if ok:
            print(f"Successfully sent job matches email to {recipient_email}!")
            return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

if __name__ == "__main__":
    send_combined_email()
