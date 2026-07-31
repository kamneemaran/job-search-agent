import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from daily_scan import send_email
from datetime import datetime

jobs = [
    ("JP_BGSWP_SDS_SAP Logistics Consultant", "Bosch Japan", "Minato, Tokyo, Japan", "https://jp.linkedin.com/jobs/view/jp-bgswp-sds-sap-logistics-consultant-at-bosch-japan-4149628446", 100, "Yes", "Yes"),
    ("SAP SCM / SD_MM Functional Consultant", "Capgemini", "Tokyo, Tokyo, Japan", "https://jp.linkedin.com/jobs/view/sap-scm%E9%A0%98%E5%9F%9F%E3%82%B3%E3%83%B3%E3%82%B5%E3%83%AB%E3%82%BF%E3%83%B3%E3%83%88-sd-mm-functional-consultant-at-capgemini-4408526154", 100, "Yes", "Yes"),
    ("Staff Engineer (SAP MM)", "Nagarro", "Tokyo, Tokyo, Japan", "https://jp.linkedin.com/jobs/view/staff-engineer-sap-mm-at-nagarro-4446060969", 70, "Check JD", "Check JD"),
    ("SAP P2P Business Analyst (S/4HANA)", "HCLTech", "Chiyoda, Tokyo, Japan", "https://jp.linkedin.com/jobs/view/sap-p2p-business-analyst-s-4hana-at-hcltech-4435648922", 70, "Check JD", "Check JD"),
    ("SAP Logistics / MM Consultant", "Westernacher Consulting", "Tokyo, Tokyo, Japan", "https://jp.linkedin.com/jobs/view/sap-%E3%83%AD%E3%82%B8%E3%82%B9%E3%83%86%E3%82%A3%E3%82%AF%E3%82%B9-mm-%E3%82%B3%E3%83%B3%E3%82%B5%E3%83%AB%E3%82%BF%E3%83%B3%E3%83%88-at-westernacher-consulting-4295601422", 70, "Yes", "Yes"),
    ("Logistics SAP Specialist", "Randstad Japan (Auto Manufacturer)", "Greater Tokyo Area, Japan", "https://jp.linkedin.com/jobs/view/logistics-sap-specialist-at-european-auto-parts-manufacturer-at-randstad-japan-4436287367", 70, "Check JD", "Check JD"),
    ("Logistics SAP Specialist, East Asia (Inbound)", "MAHLE", "Tokyo, Japan", "https://jp.linkedin.com/jobs/view/logistics-sap-specialist-east-asia-inbound-module-at-mahle-4432573234", 70, "Check JD", "Check JD"),
    ("SAP EWM Consultant", "Westernacher Consulting", "Tokyo, Tokyo, Japan", "https://jp.linkedin.com/jobs/view/sap-ewm-%E3%82%B3%E3%83%B3%E3%82%B5%E3%83%AB%E3%82%BF%E3%83%B3%E3%83%88-at-westernacher-consulting-4295600396", 65, "Yes", "Yes"),
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

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM/EWM/Logistics Job Matches — Japan (Tokyo)</h2>
  <p style="color:#666;">Profile: SAP MM/EWM | 7+ yrs | S/4HANA Certified | P2P, Inventory, Logistics — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Selected high-score roles in Japan with English-friendly environment and visa support</p>
  {build_section("Japan (Tokyo)", "Tokyo, Minato, Chiyoda, Greater Tokyo", jobs)}
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP Logistics Job Matches - Japan (Tokyo)", recipient="pradeepmeena13@gmail.com")
print("Email sent successfully to pradeepmeena13@gmail.com")