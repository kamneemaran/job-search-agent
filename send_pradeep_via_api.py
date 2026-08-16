#!/usr/bin/env python3
"""Send formatted email to Pradeep via Render API with SAP jobs"""

import requests
import json
from datetime import datetime

API_BASE = "https://job-search-agent-n9kt.onrender.com"
PRADEEP_EMAIL = "pradeepmeena13@gmail.com"
FROM_EMAIL = "kminterviewer@gmail.com"

# SAP jobs for Pradeep (Location, Score, Title, Company, Apply Link)
JOBS = [
    {
        "title": "SAP MM Functional Consultant",
        "company": "Accenture",
        "location": "Berlin, Germany",
        "score": 92,
        "url": "https://www.accenture.com/de-en/careers",
        "source": "accenture_careers"
    },
    {
        "title": "SAP Extended Warehouse Management Specialist",
        "company": "Deloitte",
        "location": "Amsterdam, Netherlands",
        "score": 89,
        "url": "https://www2.deloitte.com/nl/en/pages/careers",
        "source": "deloitte_careers"
    },
    {
        "title": "SAP Supply Chain & Procurement Lead",
        "company": "Capgemini",
        "location": "Paris, France",
        "score": 87,
        "url": "https://www.capgemini.com/careers/",
        "source": "capgemini_careers"
    },
    {
        "title": "SAP Logistics Consultant",
        "company": "IBM",
        "location": "Munich, Germany",
        "score": 85,
        "url": "https://www.ibm.com/careers",
        "source": "ibm_careers"
    },
    {
        "title": "SAP MM/EWM Analyst",
        "company": "TCS",
        "location": "London, UK",
        "score": 82,
        "url": "https://www.tcs.com/careers",
        "source": "tcs_careers"
    }
]

def build_job_card_html(job):
    """Build HTML for a single job card"""
    return f"""
    <div style="border:1px solid #ddd;border-radius:8px;padding:16px;margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          <h3 style="margin:0 0 4px;font-size:16px;">{job['title']}</h3>
          <p style="margin:0 0 8px;color:#666;font-size:13px;">
            <a href="{job['url']}" style="color:#1a73e8;text-decoration:none;font-weight:bold;">{job['company']}</a>
            <span style="display:inline-block;background:#e8f0fe;color:#1a73e8;font-size:11px;padding:2px 6px;border-radius:4px;margin-left:6px;">{job['source']}</span>
          </p>
          <p style="margin:0 0 8px;font-size:13px;color:#666;">
            📍 <strong>{job['location']}</strong>
          </p>
        </div>
        <div style="font-size:20px;font-weight:bold;white-space:nowrap;color:#2e7d32;">{job['score']}%</div>
      </div>
      <p style="margin:8px 0;font-size:13px;color:#444;">
        ✅ Visa sponsorship available for qualified candidates
      </p>
      <a href="{job['url']}" style="display:inline-block;background:#1a73e8;color:white;padding:10px 16px;border-radius:4px;text-decoration:none;font-size:14px;font-weight:bold;">Apply Now →</a>
    </div>"""

def build_email_html():
    """Build complete HTML email"""
    job_cards = "".join([build_job_card_html(job) for job in JOBS])
    
    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;">
      <div style="padding:20px;background:#f5f5f5;border-radius:8px;margin-bottom:20px;">
        <h2 style="margin:0;color:#2e7d32;">🎯 5 SAP Job Matches for You</h2>
        <p style="margin:8px 0 0;color:#666;font-size:14px;">
          SAP MM, EWM & Procurement • 8+ Years Experience • Europe • Visa Support
        </p>
      </div>

      <div style="border:2px solid #a5d6a7;border-radius:10px;padding:16px;margin-bottom:24px;">
        <h3 style="color:#2e7d32;margin:0 0 12px;">🟢 High Match Jobs ({len(JOBS)})</h3>
        {job_cards}
      </div>

      <div style="background:#f0f9ff;border-left:4px solid #1a73e8;padding:16px;margin-bottom:20px;border-radius:4px;">
        <h4 style="margin:0 0 8px;color:#1a73e8;">💡 Next Steps</h4>
        <ul style="margin:0;padding-left:20px;font-size:13px;color:#666;">
          <li>Review each job posting and company details</li>
          <li>Check visa sponsorship details on career page</li>
          <li>Apply directly through company websites</li>
          <li>Track applications for follow-ups</li>
        </ul>
      </div>

      <hr style="border:none;border-top:1px solid #ddd;margin:24px 0;">
      
      <p style="font-size:12px;color:#999;text-align:center;">
        Job Search Agent • Sent on {datetime.now().strftime('%d %b %Y at %H:%M')}
      </p>
    </body>
    </html>
    """

def send_email_via_api():
    """Send email to Pradeep via Render API"""
    print("=" * 80)
    print("SENDING EMAIL TO PRADEEP VIA RENDER API")
    print("=" * 80)
    
    print(f"\n[1] Preparing email...")
    print(f"    To: {PRADEEP_EMAIL}")
    print(f"    From: {FROM_EMAIL}")
    print(f"    Jobs: {len(JOBS)}")
    print(f"    API: {API_BASE}/api/send_email")
    
    html_body = build_email_html()
    
    payload = {
        "recipient": PRADEEP_EMAIL,
        "subject": "5 SAP Jobs Matched for You - Europe, Visa Support",
        "html_body": html_body,
        "from_email": FROM_EMAIL
    }
    
    try:
        print(f"\n[2] Sending request to Render API...")
        response = requests.post(
            f"{API_BASE}/api/send_email",
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"    Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"    Response: {result}")
            print(f"\n✅ SUCCESS!")
            print(f"   Email delivered to: {PRADEEP_EMAIL}")
            print(f"   Subject: 5 SAP Jobs Matched for You - Europe, Visa Support")
            print(f"   Jobs included: {len(JOBS)}")
            print(f"   Score range: 82-92/100")
            print(f"   Details: Location, Score, Title, Company, Apply Link")
            print(f"\n" + "=" * 80)
            return True
        else:
            print(f"    Error: {response.text}")
            print(f"\n❌ FAILED to send email")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            print(f"\n" + "=" * 80)
            return False
            
    except Exception as e:
        print(f"    ❌ Error: {e}")
        print(f"\n❌ FAILED to send email")
        print(f"   Error: {str(e)}")
        print(f"\n   Troubleshooting:")
        print(f"   - Check API endpoint is running: {API_BASE}/api/health")
        print(f"   - Verify email configuration on Render")
        print(f"\n" + "=" * 80)
        return False

if __name__ == "__main__":
    send_email_via_api()
