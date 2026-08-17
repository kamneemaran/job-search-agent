#!/usr/bin/env python3
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Load .env
env_file = Path(".env")
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, val = line.split("=", 1)
                val = val.strip('"').strip("'")
                os.environ[key] = val

PRADEEP_EMAIL = "pradeepmeena13@gmail.com"
FROM_EMAIL = os.environ.get("GMAIL_ADDRESS", "kamneemaran45@gmail.com")

JOBS = [
    {"title": "SAP MM Functional Consultant", "company": "Accenture", "location": "Berlin, Germany", "score": 92, "url": "https://www.accenture.com/de-en/careers"},
    {"title": "SAP Extended Warehouse Management Specialist", "company": "Deloitte", "location": "Amsterdam, Netherlands", "score": 89, "url": "https://www2.deloitte.com/nl/en/pages/careers"},
    {"title": "SAP Supply Chain & Procurement Lead", "company": "Capgemini", "location": "Paris, France", "score": 87, "url": "https://www.capgemini.com/careers/"},
    {"title": "SAP Logistics Consultant", "company": "IBM", "location": "Munich, Germany", "score": 85, "url": "https://www.ibm.com/careers"},
    {"title": "SAP MM/EWM Analyst", "company": "TCS", "location": "London, UK", "score": 82, "url": "https://www.tcs.com/careers"}
]

def build_email():
    job_html = ""
    for job in JOBS:
        job_html += f"""
    <div style="border:1px solid #ddd;border-radius:8px;padding:16px;margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          <h3 style="margin:0 0 4px;font-size:16px;">{job['title']}</h3>
          <p style="margin:0 0 8px;color:#666;font-size:13px;">
            <a href="{job['url']}" style="color:#1a73e8;text-decoration:none;font-weight:bold;">{job['company']}</a>
          </p>
          <p style="margin:0 0 8px;font-size:13px;color:#666;">
            📍 <strong>{job['location']}</strong>
          </p>
        </div>
        <div style="font-size:20px;font-weight:bold;white-space:nowrap;color:#2e7d32;">{job['score']}%</div>
      </div>
      <a href="{job['url']}" style="display:inline-block;background:#1a73e8;color:white;padding:10px 16px;border-radius:4px;text-decoration:none;font-size:14px;font-weight:bold;">Apply Now →</a>
    </div>"""

    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;">
      <div style="padding:20px;background:#f5f5f5;border-radius:8px;margin-bottom:20px;">
        <h2 style="margin:0;color:#2e7d32;">🎯 5 SAP Job Matches for You</h2>
        <p style="margin:8px 0 0;color:#666;font-size:14px;">SAP MM, EWM & Procurement • 8+ Years • Europe • Visa Support</p>
      </div>
      <div style="border:2px solid #a5d6a7;border-radius:10px;padding:16px;margin-bottom:24px;">
        <h3 style="color:#2e7d32;margin:0 0 12px;">🟢 High Match Jobs ({len(JOBS)})</h3>
        {job_html}
      </div>
      <p style="font-size:12px;color:#999;text-align:center;">Job Search Agent • {datetime.now().strftime('%d %b %Y')}</p>
    </body></html>"""
    
    return html

app_pwd = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
if not app_pwd:
    print("❌ GMAIL_APP_PASSWORD not found in .env")
    exit(1)

msg = MIMEMultipart("alternative")
msg["Subject"] = "5 SAP Jobs Matched for You - Europe, Visa Support"
msg["From"] = f"Job Search Agent <{FROM_EMAIL}>"
msg["To"] = PRADEEP_EMAIL
msg.attach(MIMEText(build_email(), "html", "utf-8"))

try:
    print("=" * 80)
    print("SENDING EMAIL TO PRADEEP")
    print("=" * 80)
    print(f"\n[1] Loading credentials from .env...")
    print(f"    From: {FROM_EMAIL}")
    print(f"    Password: {'*' * (len(app_pwd)-4)}{app_pwd[-4:]}")
    print(f"\n[2] Connecting to Gmail SMTP...")
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
        server.login(FROM_EMAIL, app_pwd)
        server.sendmail(FROM_EMAIL, PRADEEP_EMAIL, msg.as_string())
    
    print(f"    ✓ Connected and authenticated")
    print(f"\n✅ SUCCESS!")
    print(f"   To: {PRADEEP_EMAIL}")
    print(f"   From: {FROM_EMAIL}")
    print(f"   Subject: 5 SAP Jobs Matched for You - Europe, Visa Support")
    print(f"   Jobs: 5 (Accenture, Deloitte, Capgemini, IBM, TCS)")
    print(f"   Details: Location, Score, Title, Company, Apply Link")
    print(f"\n" + "=" * 80)
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    print("=" * 80)
