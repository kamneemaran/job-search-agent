import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from daily_scan import send_email
from datetime import datetime

# Filtered jobs matching 2yr experience in India for FICO & MM
fico_jobs = [
    ("SAP FICO Consultant", "NTT DATA North America", "Hyderabad, India", "https://in.linkedin.com/jobs/view/sap-fico-consultant-at-ntt-data-north-america-4411696109", 100, "1 - 3 yrs"),
    ("SAP FICO Consultant", "FiveForce Technologies", "Hyderabad, India", "https://in.linkedin.com/jobs/view/sap-fico-consultant-at-fiveforce-technologies-4445153135", 100, "1 - 4 yrs"),
    ("SAP FICO Consultant", "Quadric IT", "Hyderabad, India", "https://in.linkedin.com/jobs/view/sap-fico-consultant-at-quadric-it-4398514166", 100, "1 - 4 yrs"),
    ("SAP FICO Consultant", "India Nippon Electricals Limited", "Hosur, India", "https://in.linkedin.com/jobs/view/sap-fico-consultant-at-india-nippon-electricals-limited-inel-4426735561", 100, "2 - 4 yrs"),
    ("Sap Finance Control Consultant", "Coforge", "Hyderabad, India", "https://in.linkedin.com/jobs/view/sap-finance-control-consultant-at-coforge-4446993513", 100, "2 - 3 yrs"),
]

mm_jobs = [
    ("Certified Jr SAP MM Consultant", "ISS Softtech", "Hyderabad/Chennai/Delhi, India", "https://www.naukri.com/job-listings-certified-jr-sap-mm-consultant-for-hyderabad-chennai-delhi-iss-softtech-hyderabad-chennai-delhi-ncr-0-to-4-years-281024007131", 100, "0 - 4 yrs"),
    ("SAP Materials Management Analyst", "Capgemini Engineering", "Bengaluru, India", "https://in.linkedin.com/jobs/view/sap-materials-management-analyst-at-capgemini-engineering-4438751358", 85, "1 - 4 yrs"),
    ("Consultant - SAP MM", "Yash Technologies", "Hyderabad, India", "https://www.naukri.com/job-listings-consultant-sap-mm-yash-technologies-hyderabad-4-to-5-years-230726501358", 92, "4 - 5 yrs"),
]

def build_section(title, subtitle, jobs_list):
    rows = ""
    for title_j, company, location, url, score, exp in jobs_list:
        rows += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee;"><a href="{url}" style="color:#1a73e8;text-decoration:none;">{title_j}</a></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{company}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{location}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;">{exp}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;"><b>{score}%</b></td>
        </tr>"""
    return f"""
    <h3 style="color:#444;margin-top:28px;">{title}</h3>
    <p style="color:#888;font-size:13px;">{subtitle}</p>
    <table style="width:100%;border-collapse:collapse;margin-top:12px;">
      <thead>
        <tr style="background:#f0f4f8;">
          <th style="padding:10px;text-align:left;font-size:13px;color:#555;">Position</th>
          <th style="padding:10px;text-align:left;font-size:13px;color:#555;">Company</th>
          <th style="padding:10px;text-align:left;font-size:13px;color:#555;">Location</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Required Experience</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Score</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>"""

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM / FICO Job Matches — Abhishek Meena</h2>
  <p style="color:#666;">Profile: SAP MM / FICO Consultant | 2 years | India — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Selected entry/mid-level SAP MM and FICO roles matching 2 years experience in India</p>
  {build_section("SAP FICO Consultant Positions", "Financial Accounting & Controlling focus", fico_jobs)}
  {build_section("SAP MM Consultant Positions", "Materials Management & Logistics focus", mm_jobs)}
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP FICO / MM Job Matches - Abhishek Meena (India)", recipient="marmatabhishek355@gmail.com")
print("Email sent successfully to marmatabhishek355@gmail.com")