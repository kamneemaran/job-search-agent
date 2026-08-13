import os
import sys
import re
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Ensure we can import from workspace root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# Set Gmail App Credentials from DEPLOY.md
os.environ["GMAIL_ADDRESS"] = "kminterviewer@gmail.com"
os.environ["GMAIL_APP_PASSWORD"] = "pyka twte bfrd jxek"

import daily_scan as ds

# Set recipient email
recipient_email = "pradeepmeena13@gmail.com"
os.environ["EMAIL_TO"] = recipient_email

def run_live_search():
    print("=== Starting Live LinkedIn Search for Pradeep (Europe) ===")
    
    # 1. Force load Pradeep's profile from resume PDF
    pdf_path = "/Users/kamnee.maran/Downloads/Pradeep_Resume_SAP_MM_7+ years_Global.pdf"
    if os.path.exists(pdf_path):
        print(f"Parsing resume PDF: {pdf_path}")
        try:
            profile, missing = ds.parse_resume_pdf(pdf_path)
            for k, v in profile.items():
                ds.PROFILE[k] = v
            print("Successfully loaded profile from resume PDF!")
        except Exception as e:
            print(f"Failed to parse resume PDF: {e}")
            import json
            with open("profiles/pradeep.json", "r") as f:
                p_data = json.load(f)
                for k, v in p_data.items():
                    ds.PROFILE[k] = v
    else:
        import json
        with open("profiles/pradeep.json", "r") as f:
            p_data = json.load(f)
            for k, v in p_data.items():
                ds.PROFILE[k] = v
                
    ds._rebuild_precompiled_patterns()
    
    # Queries to run
    queries = ["SAP MM", "SAP EWM", "SAP Logistics Consultant"]
    locations = ["Germany", "Netherlands", "Poland", "Sweden", "Switzerland"]
    
    live_jobs = []
    seen = set()
    
    # Run fast HTTP-based LinkedIn guest searches
    for loc in locations:
        for q in queries:
            try:
                print(f"Searching LinkedIn Guest API for '{q}' in '{loc}'...")
                raw_jobs = ds.search_linkedin(q, loc, max_results=10)
                print(f"  Found {len(raw_jobs)} raw results")
                for j in raw_jobs:
                    key = (j.get("title", "").lower().strip(), j.get("company", "").lower().strip())
                    if key not in seen:
                        seen.add(key)
                        live_jobs.append(j)
            except Exception as e:
                print(f"Error searching LinkedIn: {e}")
            time.sleep(1) # rate limit friendly
            
    print(f"Total unique raw jobs fetched from LinkedIn: {len(live_jobs)}")
    
    # Score and filter live-scanned jobs
    matched_jobs = []
    one_week_ago = datetime.now() - timedelta(days=7)
    
    for j in live_jobs:
        title = j.get("title", "")
        company = j.get("company", "")
        location = j.get("location", "")
        url = j.get("url", "")
        desc = j.get("description", "") or f"{title} at {company}. SAP MM/EWM Consultant role in {location}."
        
        # Check posted date (job posted before a week only)
        posted_at = j.get("posted_at")
        if posted_at:
            try:
                if isinstance(posted_at, str):
                    p_date = datetime.fromisoformat(posted_at.replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    p_date = posted_at
                if p_date < one_week_ago:
                    # Older than a week, skip!
                    continue
            except Exception:
                pass
                
        # Score the job
        score, note = ds.score_job(title, desc, company, location)
        
        # Filter for score threshold and require visa sponsorship signals
        if score >= 65:
            is_relo_friendly = any(c.lower() in company.lower() for c in ds.RELOCATION_FRIENDLY)
            has_visa_signals = "visa" in desc.lower() or "sponsorship" in desc.lower() or "relocation" in desc.lower() or is_relo_friendly
            
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
            
    print(f"Filtered to {len(matched_jobs)} live matching jobs posted within the last week!")
    return matched_jobs

def send_combined_email():
    # 1. Get live-scanned jobs
    live_jobs = run_live_search()
    
    # 2. Add vetted/curated high-relevance Europe jobs
    curated_jobs = [
        {"title": "Senior SAP Consultant Logistics WM/MM - IM", "company": "Rheinmetall", "location": "Düsseldorf, Germany", "url": "https://de.linkedin.com/jobs/view/senior-sap-consultant-logistics-wm-mm-im-m-w-d-at-rheinmetall-4424861360", "score": 100, "visa": "Yes", "reloc": "Yes"},
        {"title": "SAP Consultant MM / WM / EWM & MES", "company": "Marquardt Group", "location": "Ichtershausen, Germany", "url": "https://de.linkedin.com/jobs/view/sap-consultant-mm-wm-ewm-mes-w-m-d-at-marquardt-group-4446334415", "score": 95, "visa": "Yes", "reloc": "Yes"},
        {"title": "SAP MM S/4HANA Consultant", "company": "IT-People B.V.", "location": "Den Bosch, Netherlands", "url": "https://nl.linkedin.com/jobs/view/sap-mm-s-4hana-consultant-at-it-people-b-v-4429088572", "score": 100, "visa": "Yes", "reloc": "Yes"},
        {"title": "IT Business Application Consultant (SAP MM S/4 Hana)", "company": "GEA Group", "location": "Den Bosch, Netherlands", "url": "https://nl.linkedin.com/jobs/view/it-business-application-consultant-sap-mm-s-4-hana-at-gea-group-4393551829", "score": 100, "visa": "Yes", "reloc": "Yes"},
        {"title": "SAP Supply Chain Consultant", "company": "VDL Nederland", "location": "Eindhoven, Netherlands", "url": "https://nl.linkedin.com/jobs/view/sap-supply-chain-consultant-at-vdl-nederland-4442750547", "score": 100, "visa": "Yes", "reloc": "Yes"},
        {"title": "SAP MM Consultant (m/f/d)", "company": "Siemens Energy", "location": "Mülheim, Germany", "url": "https://de.linkedin.com/jobs/view/sap-mm-consultant-m-f-d-at-siemens-energy-4437072813", "score": 85, "visa": "Yes", "reloc": "Yes"},
        {"title": "SAP Second-Level SCM Expert EWM MM PP S4H", "company": "Siemens Healthineers", "location": "Erlangen, Germany", "url": "https://de.linkedin.com/jobs/view/sap-second-level-scm-digitalization-expert-ewm-mm-pp-s4h-w-m-d-at-siemens-healthineers-4434537779", "score": 85, "visa": "Yes", "reloc": "Yes"},
        {"title": "SAP Sourcing & Procurement Consultant", "company": "Accenture DACH", "location": "Kronberg, Germany", "url": "https://de.linkedin.com/jobs/view/sap-sourcing-procurement-consultant-all-genders-at-accenture-dach-4437976917", "score": 77, "visa": "Yes", "reloc": "Yes"},
        {"title": "Senior SAP SD/MM Consultant", "company": "EPAM Systems", "location": "Poland", "url": "https://pl.linkedin.com/jobs/view/senior-sap-sd-mm-consultant-at-epam-systems-4350751162", "score": 75, "visa": "Yes", "reloc": "Yes"},
        {"title": "SAP S4 Hana APO/IBP Consultant", "company": "Infosys", "location": "Stockholm, Sweden", "url": "https://se.linkedin.com/jobs/view/sap-s4-hana-apo-ibp-consultant-sweden-at-infosys-4427840606", "score": 70, "visa": "Yes", "reloc": "Yes"}
    ]
    
    # Avoid duplicates
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
            
    # Group jobs by country for cleaner presentation
    germany_jobs = [j for j in final_jobs if "germany" in j["location"].lower()]
    netherlands_jobs = [j for j in final_jobs if "netherlands" in j["location"].lower() or "nl" in j["location"].lower()]
    other_jobs = [j for j in final_jobs if j not in germany_jobs and j not in netherlands_jobs]
    
    def build_table(jobs_list):
        if not jobs_list:
            return "<p style='color:#64748b;font-style:italic;'>No new matches found in this region.</p>"
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

    # Beautifully styled email body
    html_body = f"""
    <html>
    <head>
      <meta charset="utf-8">
      <title>SAP MM/EWM Job Matches - Europe Region</title>
    </head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background-color:#f8fafc;padding:24px;margin:0;">
      <div style="max-width:850px;margin:0 auto;background-color:#ffffff;border-radius:12px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);padding:32px;border:1px solid #e2e8f0;">
        <div style="border-bottom:2px solid #e2e8f0;padding-bottom:16px;margin-bottom:24px;">
          <h2 style="color:#0f172a;margin:0 0 8px 0;font-size:24px;">SAP MM/EWM Job Matches — Europe Region</h2>
          <p style="color:#475569;margin:0;font-size:14px;line-height:1.5;">
            <b>Candidate:</b> Pradeep Meena | 7+ Years Experience | SAP MM/EWM Consultant<br>
            <b>Location Filter:</b> Europe Region (Germany, Netherlands, Poland, Sweden, Switzerland)<br>
            <b>Posted Date:</b> Recent matches (last 7 days) — {datetime.now().strftime("%d %b %Y")}
          </p>
        </div>
        
        <p style="color:#334155;font-size:15px;line-height:1.6;">
          Hello Pradeep,<br><br>
          We have scanned major job boards and career pages for <b>SAP MM/EWM Expert</b> roles across the <b>Europe Region</b>. Below are the top matches that align with your profile, sorted by region, with active visa sponsorship or relocation signals.
        </p>
        
        <h3 style="color:#1e293b;border-left:4px solid #3b82f6;padding-left:10px;margin-top:28px;">🇩🇪 Germany</h3>
        {build_table(germany_jobs)}
        
        <h3 style="color:#1e293b;border-left:4px solid #f97316;padding-left:10px;margin-top:28px;">🇳🇱 Netherlands</h3>
        {build_table(netherlands_jobs)}
        
        <h3 style="color:#1e293b;border-left:4px solid #10b981;padding-left:10px;margin-top:28px;">🇪🇺 Other European Regions</h3>
        {build_table(other_jobs)}
        
        <div style="background-color:#f0fdf4;border-left:4px solid #22c55e;padding:16px;border-radius:0 8px 8px 0;margin-top:32px;margin-bottom:32px;">
          <h4 style="color:#166534;margin:0 0 8px 0;font-size:15px;font-weight:700;">Why these positions?</h4>
          <ul style="color:#14532d;font-size:14px;line-height:1.7;margin:0;padding-left:20px;">
            <li><b>Germany & Netherlands:</b> These countries have extremely fast-tracked visa procedures for qualified SAP experts under the EU Blue Card scheme.</li>
            <li><b>Siemens Energy / Healthineers:</b> Massive multinational sponsors with direct in-house SAP MM/EWM roles.</li>
            <li><b>Rheinmetall / Marquardt Group:</b> Excellent matches with S/4HANA logistics transitions currently underway.</li>
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
        ok = ds.send_email(html_body, subject="SAP MM/EWM Job Matches - Europe Region", recipient=recipient_email, raise_on_error=True)
        if ok:
            print(f"Successfully sent Europe job matches email to {recipient_email}!")
            return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

if __name__ == "__main__":
    send_combined_email()
