import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from daily_scan import send_email
from datetime import datetime

jobs = [
    ("SAP FICA Consultant", "HCLTech", "Riyadh, Saudi Arabia", "https://sa.linkedin.com/jobs/view/sap-fica-consultant-at-hcltech-4443151406", 100, "1 - 4 yrs", "Yes (Global SI)"),
    ("SAP FICO Consultant", "Al Watania Information Systems (Wisys)", "Riyadh, Saudi Arabia", "https://sa.linkedin.com/jobs/view/sap-fico-consultant-at-al-watania-information-systems-wisys-4432577013", 95, "2 - 4 yrs", "Yes"),
    ("ERP Specialist (SAP)", "Stellar Hunters", "Dammam, Saudi Arabia", "https://sa.linkedin.com/jobs/view/erp-specialist-sap-at-stellar-hunters-4430828828", 60, "1 - 3 yrs", "Check JD"),
]

def build_section(title, subtitle, jobs_list):
    rows = ""
    for title_j, company, location, url, score, exp, visa in jobs_list:
        rows += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee;"><a href="{url}" style="color:#1a73e8;text-decoration:none;">{title_j}</a></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{company}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{location}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;">{exp}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;color:#16a34a;font-weight:600;">{visa}</td>
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
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Visa / Relo</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Score</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>"""

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM / FICO Job Matches — Middle East (Abhishek Meena)</h2>
  <p style="color:#666;">Profile: SAP MM / FICO Consultant | 2 years | India — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Selected entry/mid-level SAP MM and FICO roles matching 2 years experience in the Middle East with visa sponsorship support</p>
  {build_section("Middle East (Saudi Arabia / Riyadh / Dammam)", "English-friendly roles with relocation and sponsorship pathways", jobs)}
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP FICO / MM Job Matches - Abhishek Meena (Middle East)", recipient="marmatabhishek355@gmail.com")
print("Email sent successfully to marmatabhishek355@gmail.com")