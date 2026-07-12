import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()
os.environ.setdefault("EMAIL_TO", "manju.baligeri@gmail.com")

from daily_scan import send_email
from datetime import datetime

jobs = [
    ("SAP MM/WM Functional Consultant", "ITC Infotech", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/sap-mm-wm-functional-consultant-at-itc-infotech-4437922929", 85),
    ("S/4HANA MM - Lean Services Consultant", "Infosys", "Brisbane, Australia", "https://au.linkedin.com/jobs/view/s-4hana-mm-lean-services-consultant-at-infosys-4427332918", 85),
    ("SAP EWM Functional Consultant", "Capgemini", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/sap-ewm-functional-consultant-at-capgemini-4429907770", 82),
    ("SAP Support Analyst – Supply Chain", "Speller International", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/sap-support-analyst-%E2%80%93-supply-chain-at-speller-international-4437949632", 78),
    ("S/4HANA Data Migration", "Infosys", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/s-4hana-data-migration-at-infosys-4435670336", 78),
    ("SAP Master Data Specialist", "CBH Group", "Perth, Australia", "https://au.linkedin.com/jobs/view/sap-master-data-specialist-at-cbh-group-4438613285", 77),
    ("Domain Architect – ERP, Merch & Supply", "Super Retail Group", "Brisbane, Australia", "https://au.linkedin.com/jobs/view/domain-architect-%E2%80%93-erp-merch-supply-at-super-retail-group-4419033194", 76),
    ("V.I.E. Contract - SAP Consultant", "Capgemini", "Sydney, Australia", "https://au.linkedin.com/jobs/view/v-i-e-contract-sap-consultant-at-capgemini-4387434309", 75),
    ("SAP Deployment Coordinator", "Speller International", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/sap-deployment-coordinator-at-speller-international-4437029912", 75),
    ("Product Lifecycle Management (PLM) Lead", "Chobani Australia", "Dandenong, VIC", "https://au.linkedin.com/jobs/view/product-lifecycle-management-plm-lead-12-month-ftc-at-chobani-australia-4427679335", 75),
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

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:750px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM Job Matches — Australia</h2>
  <p style="color:#666;">Scored against your SAP MM/EWM/PLM profile (13+ yr IT, 7+ yr SAP MM, S/4HANA Certified, PR Visa) — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Posted within 1 week | Match score >= 75% | Australia only</p>
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
  <h3 style="color:#444;margin-top:28px;">Top Picks</h3>
  <ul style="color:#555;font-size:14px;line-height:1.8;">
    <li><b>ITC Infotech (Melbourne)</b> — SAP MM/WM, exact profile match, strong fit</li>
    <li><b>Infosys (Brisbane)</b> — S/4HANA MM Lean Services, matches your S/4HANA certification</li>
    <li><b>Capgemini (Melbourne)</b> — SAP EWM, matches your EWM experience</li>
    <li><b>Chobani Australia</b> — PLM Lead, matches your SAP PLM expertise</li>
  </ul>
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP MM Job Matches - Manjunath (Australia)")
