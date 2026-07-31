import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from daily_scan import send_email
from datetime import datetime

jobs = [
    ("Senior SAP Consultant Logistics WM/MM - IM", "Rheinmetall", "Düsseldorf, Germany", "https://de.linkedin.com/jobs/view/senior-sap-consultant-logistics-wm-mm-im-m-w-d-at-rheinmetall-4424861360", 100, "Yes", "Yes"),
    ("SAP Consultant MM / WM / EWM & MES", "Marquardt Group", "Ichtershausen, Germany", "https://de.linkedin.com/jobs/view/sap-consultant-mm-wm-ewm-mes-w-m-d-at-marquardt-group-4446334415", 95, "Yes", "Yes"),
    ("SAP MM/WM Inhouse Consultant", "Aenova Group", "Starnberg, Germany", "https://de.linkedin.com/jobs/view/sap-mm-wm-inhouse-consultant-w-m-d-at-aenova-group-4443126856", 90, "Check JD", "Check JD"),
    ("SAP MM S/4HANA Consultant", "IT-People B.V.", "Den Bosch, Netherlands", "https://nl.linkedin.com/jobs/view/sap-mm-s-4hana-consultant-at-it-people-b-v-4429088572", 100, "Yes", "Yes"),
    ("IT Business Application Consultant (SAP MM S/4 Hana)", "GEA Group", "Den Bosch, Netherlands", "https://nl.linkedin.com/jobs/view/it-business-application-consultant-sap-mm-s-4-hana-at-gea-group-4393551829", 100, "Yes", "Yes"),
    ("SAP Supply Chain Consultant", "VDL Nederland", "Eindhoven, Netherlands", "https://nl.linkedin.com/jobs/view/sap-supply-chain-consultant-at-vdl-nederland-4442750547", 100, "Yes", "Yes"),
    ("Lead SAP Business Systems, Operations & Supply Chain", "Advanced Sterilization Products", "Eindhoven, Netherlands", "https://nl.linkedin.com/jobs/view/lead-sap-business-systems-operations-supply-chain-at-advanced-sterilization-products-4444706260", 90, "Check JD", "Check JD"),
    ("SAP S/4HANA Source-to-Pay Lead", "BPX", "Warsaw, Poland", "https://pl.linkedin.com/jobs/view/sap-s-4hana-source-to-pay-lead-at-bpx-4444426426", 75, "Check JD", "Check JD"),
    ("SAP MM Business Analyst", "Snowrelic Inc", "Warsaw, Poland", "https://pl.linkedin.com/jobs/view/sap-mm-business-analyst-at-snowrelic-inc-4434781152", 70, "Yes", "Yes"),
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

de_jobs = [j for j in jobs if "Germany" in j[2]]
nl_jobs = [j for j in jobs if "Netherlands" in j[2]]
pl_jobs = [j for j in jobs if "Poland" in j[2]]

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM/EWM/Logistics Job Matches — Europe</h2>
  <p style="color:#666;">Profile: SAP MM/EWM | 7+ yrs | S/4HANA Certified | P2P, Inventory, Logistics — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Selected high-score roles in Germany, Netherlands, and Poland with visa sponsorship and English-friendly environment</p>
  {build_section("Germany", "Düsseldorf, Ichtershausen, Starnberg", de_jobs)}
  {build_section("Netherlands", "Den Bosch, Eindhoven", nl_jobs)}
  {build_section("Poland", "Warsaw", pl_jobs)}
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP Logistics Job Matches - Europe", recipient="pradeepmeena13@gmail.com")
print("Email sent successfully to pradeepmeena13@gmail.com")