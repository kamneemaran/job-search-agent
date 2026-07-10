import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("GMAIL_ADDRESS", "kamneemaran45@gmail.com")
os.environ.setdefault("GMAIL_APP_PASSWORD", "bttjcludverlbmnr")
os.environ.setdefault("EMAIL_TO", "pradeepmeena13@gmail.com")

from daily_scan import send_email
from datetime import datetime

jobs = [
    ("SAP MM Consultant - Portugal Remote", "WA FENIX Portugal", "Portugal (Remote)", "https://www.linkedin.com/jobs/view/4433283124", 80),
    ("SAP MM Consultant AMS - Germany Remote", "Galahad SNR GmbH", "Germany (Remote)", "https://www.linkedin.com/jobs/view/4430212685", 70),
    ("Senior SAP MM Consultant - Belarus", "EPAM Systems", "Belarus", "https://www.linkedin.com/jobs/view/4289644589", 65),
    ("Senior/Lead SAP MM Consultant - Hungary", "EPAM Systems", "Hungary", "https://www.linkedin.com/jobs/view/4288861422", 65),
    ("SAP MM Consultant/Lead - Vienna Austria", "Pertemps ERP", "Vienna, Austria", "https://www.linkedin.com/jobs/view/4431655873", 65),
    ("Senior SAP MM Consultant - Prague", "MRP-Global", "Prague, Czechia", "https://www.linkedin.com/jobs/view/4431227262", 65),
    ("SAP MM Consultant ECC - London/Manchester", "Focus on WD", "London/Manchester, UK", "https://www.linkedin.com/jobs/view/4432612142", 60),
    ("Senior SAP MM Consultant Retail - Poland", "EPAM Systems", "Poland (Remote)", "https://www.linkedin.com/jobs/view/4363992145", 65),
]

rows = ""
for title, company, location, url, score in jobs:
    rows += f"""
    <tr>
      <td style="padding:10px;border-bottom:1px solid #eee;"><a href="{url}" style="color:#1a73e8;text-decoration:none;">{title}</a></td>
      <td style="padding:10px;border-bottom:1px solid #eee;">{company}</td>
      <td style="padding:10px;border-bottom:1px solid #eee;">{location}</td>
      <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;"><b>{score}%</b></td>
    </tr>"""

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM Job Matches</h2>
  <p style="color:#666;">Scored against your SAP MM profile (6yr, SAP MM, Procurement, RFC, S/4HANA) — {datetime.now().strftime("%d %b %Y")}</p>
  <table style="width:100%;border-collapse:collapse;margin-top:16px;">
    <thead>
      <tr style="background:#f0f4f8;">
        <th style="padding:10px;text-align:left;font-size:13px;color:#555;">Position</th>
        <th style="padding:10px;text-align:left;font-size:13px;color:#555;">Company</th>
        <th style="padding:10px;text-align:left;font-size:13px;color:#555;">Location</th>
        <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Score</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
  <p style="margin-top:24px;font-size:13px;color:#888;">Top match: WA FENIX Portugal - Portugal Remote (80%) — S/4HANA Public Cloud, MM+EWM, Procurement, CPI/BTP, Fiori</p>
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP MM Job Matches - Pradeep")
