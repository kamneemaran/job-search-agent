import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from daily_scan import send_email
from datetime import datetime

# Filtered jobs matching 2yr experience in Europe & APAC for FICO & MM
jobs = [
    ("junior SAP consultant", "Fundacja Grupy ERGO Hestia", "Pomorskie, Poland", "https://pl.linkedin.com/jobs/view/junior-sap-consultant-at-fundacja-grupy-ergo-hestia-integralia-4438336972", 85, "Junior Level", "Yes"),
    ("Business Support Analyst SAP FICO", "MKS Inc.", "Poznan, Poland", "https://pl.linkedin.com/jobs/view/business-support-analyst-sap-fico-at-mks-inc-4398486573", 80, "Analyst Level", "Yes"),
    ("SAP MM Business Analyst", "Snowrelic Inc", "Warsaw, Poland", "https://pl.linkedin.com/jobs/view/sap-mm-business-analyst-at-snowrelic-inc-4434781152", 70, "Analyst Level", "Yes"),
    ("SAP S/4HANA Finance Consultant", "DXC Technology", "Brisbane, Australia", "https://au.linkedin.com/jobs/view/sap-s-4hana-finance-consultant-at-dxc-technology-4443227010", 100, "Associate/Consultant", "Yes"),
    ("SAP FICO Consultant", "iSOFT", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/sap-fico-consultant-at-isoft-4442911356", 100, "Consultant", "Yes"),
    ("SAP Finance Consultant", "XPT Software", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/sap-finance-consultant-at-xpt-software-4442601004", 100, "Consultant", "Yes"),
    ("SAP Associate", "Tap Growth ai", "Singapore", "https://sg.linkedin.com/jobs/view/sap-associate-at-tap-growth-ai-4437326935", 55, "Associate Level", "Check JD"),
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

eu_jobs = [j for j in jobs if "Poland" in j[2]]
apac_jobs = [j for j in jobs if "Australia" in j[2] or "Singapore" in j[2]]

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM / FICO Job Matches — Global (Abhishek Meena)</h2>
  <p style="color:#666;">Profile: SAP MM / FICO Consultant | 2 years | India — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Selected entry/mid-level SAP MM and FICO roles matching 2 years experience in Europe and APAC with visa sponsorship pathways</p>
  {build_section("Europe (Poland / Eastern Europe Hubs)", "High-potential nearshoring hubs with lower visa barriers for junior talent", eu_jobs)}
  {build_section("APAC Region (Australia & Singapore)", "SDE-friendly English speaking environments", apac_jobs)}
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP FICO / MM Job Matches - Abhishek Meena (Global)", recipient="marmatabhishek355@gmail.com")
print("Email sent successfully to marmatabhishek355@gmail.com")