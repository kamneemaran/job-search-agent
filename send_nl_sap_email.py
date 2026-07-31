import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from daily_scan import send_email
from datetime import datetime

jobs = [
    ("SAP MM S/4HANA Consultant", "IT-People B.V.", "Den Bosch, Netherlands", "https://nl.linkedin.com/jobs/view/sap-mm-s-4hana-consultant-at-it-people-b-v-4429088572", 100, "Yes (IND Sponsor)", "Yes"),
    ("SAP MM Consultant", "IT-People B.V.", "Den Bosch, Netherlands", "https://nl.linkedin.com/jobs/view/sap-mm-consultant-at-it-people-b-v-4413309882", 100, "Yes (IND Sponsor)", "Yes"),
    ("SAP Supply Chain Consultant", "VDL Nederland", "Eindhoven, Netherlands", "https://nl.linkedin.com/jobs/view/sap-supply-chain-consultant-at-vdl-nederland-4442750547", 100, "Yes (IND Registered)", "Yes"),
    ("IT Business Application Consultant (SAP MM S/4 Hana)", "GEA Group", "Den Bosch, Netherlands", "https://nl.linkedin.com/jobs/view/it-business-application-consultant-sap-mm-s-4-hana-at-gea-group-4393551829", 100, "Yes (IND Registered)", "Yes"),
    ("SAP Supply Chain Consultant", "Eswelt", "Veghel, Netherlands", "https://nl.linkedin.com/jobs/view/sap-supply-chain-consultant-at-eswelt-4446715774", 95, "Yes (IND Sponsor)", "Yes"),
    ("Lead SAP Business Systems, Operations & Supply Chain", "Advanced Sterilization Products", "Eindhoven, Netherlands", "https://nl.linkedin.com/jobs/view/lead-sap-business-systems-operations-supply-chain-at-advanced-sterilization-products-4444706260", 90, "Yes (IND Sponsor)", "Yes"),
]

def build_section(title, subtitle, jobs_list):
    rows = ""
    for title_j, company, location, url, score, visa, reloc in jobs_list:
        visa_color = "#16a34a" if visa != "N/A" else "#666"
        rows += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee;"><a href="{url}" style="color:#1a73e8;text-decoration:none;">{title_j}</a></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{company}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{location}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;color:{visa_color};font-weight:600;">{visa}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;color:#16a34a;font-weight:600;">{reloc}</td>
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
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Visa / IND Sponsor</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Relocation</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Score</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>"""

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">Senior SAP MM/EWM Job Matches — Netherlands</h2>
  <p style="color:#666;">Profile: Senior SAP MM/WM/EWM | 8+ yrs | S/4HANA Certified | SCM & Logistics — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Highly targeted, premium matches in the Netherlands with confirmed IND registered visa sponsorship and full relocation support, posted within the last week</p>
  {build_section("Netherlands (IND Visa Sponsorship & Relocation)", "Amsterdam, Den Bosch, Eindhoven, Veghel", jobs)}
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="Senior SAP MM/WM/EWM Job Matches - Netherlands (Pradeep)", recipient="pradeepmeena13@gmail.com")
print("Email sent successfully to pradeepmeena13@gmail.com")