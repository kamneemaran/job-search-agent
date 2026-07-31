import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from daily_scan import send_email
from datetime import datetime

jobs = [
    ("SAP MM/WM Functional Consultant", "ITC Infotech", "Melbourne, VIC, Australia", "https://au.linkedin.com/jobs/view/sap-mm-wm-functional-consultant-at-itc-infotech-4439956901", 100, "Yes", "Yes"),
    ("SAP Support Analyst – Supply Chain", "Speller International", "Melbourne, VIC, Australia", "https://au.linkedin.com/jobs/view/sap-support-analyst-%E2%80%93-supply-chain-at-speller-international-4437949632", 70, "Check JD", "Check JD"),
    ("Functional Analyst - Supply Chain", "Officeworks", "Chadstone, VIC, Australia", "https://au.linkedin.com/jobs/view/functional-analyst-supply-chain-at-officeworks-4424850323", 70, "Check JD", "Check JD"),
    ("SAP Engineering Project Manager, Logistics - IS&T", "Apple", "Singapore", "https://sg.linkedin.com/jobs/view/sap-engineering-project-manager-logistics-is-t-at-apple-4446064702", 70, "Yes", "Yes"),
    ("SAP RTL Manager", "Tapestry", "Singapore", "https://sg.linkedin.com/jobs/view/sap-rtl-manager-at-tapestry-4419610430", 60, "Check JD", "Check JD"),
]

def build_section(title, subtitle, jobs_list):
    rows = ""
    for title_j, company, location, url, score, visa, reloc in jobs_list:
        visa_color = "#16a34a" if visa in ("Yes",) else ("#ca8a04" if visa == "Likely" else "#666")
        reloc_color = "#16a34a" if reloc in ("Yes",) else ("#ca8a04" if reloc == "Likely" else "#666")
        rows += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee;"><a href="{url}" style="color:#1a73e8;text-decoration:none;">{title_j}</a></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{company}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{location}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;"><b>{score}%</b></td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;color:{visa_color};font-weight:600;">{visa}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;color:{reloc_color};font-weight:600;">{reloc}</td>
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
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Score</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Visa</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Relocation</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>"""

au_jobs = [j for j in jobs if "Australia" in j[2]]
sg_jobs = [j for j in jobs if "Singapore" in j[2]]

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM/WM/Logistics Job Matches — Australia & Singapore</h2>
  <p style="color:#666;">Profile: SAP MM/WM | 7+ yrs | S/4HANA Certified | P2P, Inventory, Logistics — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Selected high-score roles in APAC region</p>
  {build_section("Australia", "Melbourne, Sydney, Chadstone", au_jobs)}
  {build_section("Singapore", "Singapore Hub", sg_jobs)}
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP Logistics Job Matches - Australia & Singapore", recipient="pradeepmeena13@gmail.com")
print("Email sent successfully to pradeepmeena13@gmail.com")