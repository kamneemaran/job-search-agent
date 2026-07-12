import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()
os.environ.setdefault("EMAIL_TO", "manju.baligeri@gmail.com")

from daily_scan import send_email
from datetime import datetime

# (title, company, location, url, score, job_type)
# job_type: Permanent / Contract / Check JD
jobs = [
    # AUSTRALIA - Remote / Hybrid
    ("SAP MM/WM Functional Consultant", "ITC Infotech", "Melbourne (Remote)", "https://au.linkedin.com/jobs/view/sap-mm-wm-functional-consultant-at-itc-infotech-4437922929", 85, "Contract"),
    ("S/4HANA MM - Lean Services Consultant", "Infosys", "Brisbane (Remote)", "https://au.linkedin.com/jobs/view/s-4hana-mm-lean-services-consultant-at-infosys-4427332918", 85, "Permanent"),
    ("SAP EWM Functional Consultant", "Capgemini", "Melbourne (Remote)", "https://au.linkedin.com/jobs/view/sap-ewm-functional-consultant-at-capgemini-4429907770", 82, "Contract"),
    ("SAP Support Analyst – Supply Chain", "Speller International", "Melbourne (Remote)", "https://au.linkedin.com/jobs/view/sap-support-analyst-%E2%80%93-supply-chain-at-speller-international-4437949632", 78, "Contract"),
    ("SAP Master Data Specialist", "CBH Group", "Perth (Remote)", "https://au.linkedin.com/jobs/view/sap-master-data-specialist-at-cbh-group-4438613285", 77, "Permanent"),
    ("SAP Deployment Coordinator", "Speller International", "Melbourne (Remote)", "https://au.linkedin.com/jobs/view/sap-deployment-coordinator-at-speller-international-4437029912", 75, "Contract"),
    ("*SAP Referral/Expression of Interest*", "Accenture Australia", "Melbourne (Remote)", "https://au.linkedin.com/jobs/view/sap-referral-expression-of-interest-at-accenture-australia-4328099455", 75, "Permanent"),
    # WORLDWIDE - Remote
    ("SAP EWM (Senior) Consultant - S/4HANA - 100% Remote", "The Recruitment 2.0 Group", "Germany (Remote)", "https://de.linkedin.com/jobs/view/sap-ewm-senior-consultant-s-4hana-100%25-remote-germany-at-the-recruitment-2-0-group-4415015635", 80, "Contract"),
    ("SAP MM/SD with S4 HANA CONSULTANT", "eNcloud Services LLC", "USA (Remote)", "https://www.linkedin.com/jobs/view/sap-mm-sd-with-s4-hana-consultant-at-encloud-services-llc-4437995729", 78, "Contract"),
    ("SAP MM Consultant", "Inherent Technologies", "USA (Remote)", "https://www.linkedin.com/jobs/view/sap-mm-consultant-at-inherent-technologies-4439345324", 78, "Contract"),
    ("SAP MM/SD Functional Consultant", "eNcloud Services LLC", "USA (Remote)", "https://www.linkedin.com/jobs/view/sap-mm-sd-functional-consultant-at-encloud-services-llc-4437995730", 77, "Contract"),
    ("MM/PP SAP System Analyst", "Teledyne Technologies", "UK (Remote)", "https://uk.linkedin.com/jobs/view/mm-pp-sap-system-analyst-at-teledyne-technologies-incorporated-4434876466", 77, "Permanent"),
    ("SAP MM/PP Functional Analyst", "Pure Fishing", "USA (Remote)", "https://www.linkedin.com/jobs/view/sap-mm-pp-functional-analyst-at-pure-fishing-4429587580", 77, "Permanent"),
    ("Sourcing Systems Specialist III (SAP S/4HANA)", "Woodward Inc", "USA (Remote)", "https://www.linkedin.com/jobs/view/sourcing-systems-specialist-iii-sap-s-4hana-at-woodward-inc-4426884503", 76, "Permanent"),
    ("Senior Associate SAP MM Data Specialist", "RWE", "USA (Remote)", "https://www.linkedin.com/jobs/view/senior-associate-sap-mm-data-specialist-at-rwe-4438234835", 76, "Permanent"),
    ("SAP WM / HUM Functional Consultant – S/4HANA", "DHV (Deliver High Value)", "Romania (Remote)", "https://ro.linkedin.com/jobs/view/sap-wm-hum-functional-consultant-%E2%80%93-s-4hana-industrial-deployment-at-dhv-deliver-high-value-4435694456", 75, "Contract"),
    ("Senior SAP Consultant | Remote", "Sonova Group", "Canada (Remote)", "https://ca.linkedin.com/jobs/view/senior-sap-consultant-remote-at-sonova-group-4418550816", 75, "Permanent"),
]

rows = ""
for title, company, location, url, score, job_type in jobs:
    color = "#16a34a" if job_type == "Permanent" else "#2563eb"
    rows += f"""
    <tr>
      <td style="padding:10px;border-bottom:1px solid #eee;"><a href="{url}" style="color:#1a73e8;text-decoration:none;">{title}</a></td>
      <td style="padding:10px;border-bottom:1px solid #eee;">{company}</td>
      <td style="padding:10px;border-bottom:1px solid #eee;">{location}</td>
      <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;"><b>{score}%</b></td>
      <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;color:{color};font-weight:600;">{job_type}</td>
    </tr>"""

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:850px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM Remote Job Matches — Manjunath</h2>
  <p style="color:#666;">Profile: SAP MM/EWM/PLM | 13+ yr IT, 7+ yr SAP MM | S/4HANA Certified | PR Visa Australia — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Posted within 1 week | Match score >= 75% | Remote only</p>
  <table style="width:100%;border-collapse:collapse;margin-top:16px;">
    <thead>
      <tr style="background:#f0f4f8;">
        <th style="padding:10px;text-align:left;font-size:13px;color:#555;">Position</th>
        <th style="padding:10px;text-align:left;font-size:13px;color:#555;">Company</th>
        <th style="padding:10px;text-align:left;font-size:13px;color:#555;">Location</th>
        <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Score</th>
        <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Job Type</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
  <h3 style="color:#444;margin-top:28px;">Top Picks</h3>
  <ul style="color:#555;font-size:14px;line-height:1.8;">
    <li><b>ITC Infotech (Melbourne, Remote)</b> — SAP MM/WM, exact match, Contract</li>
    <li><b>Infosys (Brisbane, Remote)</b> — S/4HANA MM, Permanent, ex-employer</li>
    <li><b>Capgemini (Melbourne, Remote)</b> — SAP EWM, Contract</li>
    <li><b>CBH Group (Perth, Remote)</b> — SAP Master Data, Permanent</li>
    <li><b>Accenture Australia (Remote)</b> — SAP Referral/EOI, Permanent</li>
    <li><b>Sonova Group (Canada, Remote)</b> — Senior SAP Consultant, Permanent</li>
  </ul>
  <p style="margin-top:16px;font-size:13px;color:#888;"><b>Note:</b> <span style="color:#16a34a;">Permanent</span> = Full-time employee | <span style="color:#2563eb;">Contract</span> = Fixed-term/consulting. Please verify on each job page before applying.</p>
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP MM Remote Jobs - Manjunath (Australia + Worldwide)")
