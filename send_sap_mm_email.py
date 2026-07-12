import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()
os.environ.setdefault("EMAIL_TO", "pradeepmeena13@gmail.com")

from daily_scan import send_email
from datetime import datetime

jobs = [
    # GERMANY
    ("SAP MM Consultant (m/f/d)", "Siemens Energy", "Mülheim, Germany", "https://de.linkedin.com/jobs/view/sap-mm-consultant-m-f-d-at-siemens-energy-4437072813", 85, "Yes", "Yes"),
    ("SAP Second-Level SCM Expert EWM MM PP S4H", "Siemens Healthineers", "Erlangen, Germany", "https://de.linkedin.com/jobs/view/sap-second-level-scm-digitalization-expert-ewm-mm-pp-s4h-w-m-d-at-siemens-healthineers-4434537779", 85, "Yes", "Yes"),
    ("(Senior) SAP MM Consultant (m/w/d)", "Cpro Industry", "Germany", "https://de.linkedin.com/jobs/view/senior-sap-mm-consultant-m-w-d-at-cpro-industry-projects-solutions-gmbh-4437507684", 80, "Likely", "Likely"),
    ("SAP MM Inhouse Consultant S/4HANA (m/f/d)", "Mehler Protection", "Fulda, Germany", "https://de.linkedin.com/jobs/view/sap-mm-inhouse-consultant-s-4hana-m-f-d-at-mehler-protection-4438306580", 80, "Check JD", "Check JD"),
    ("SAP MM-Berater (w/m/d)", "sympacon TS GmbH", "Hannover, Germany", "https://de.linkedin.com/jobs/view/sap-mm-berater-w-m-d-at-sympacon-ts-gmbh-4439061427", 80, "Check JD", "Check JD"),
    ("SAP Inhouse Consultant MM (m/w/d)", "Greifenberg", "Augsburg, Germany", "https://de.linkedin.com/jobs/view/sap-inhouse-consultant-mm-m-w-d-at-greifenberg-4435988135", 78, "Check JD", "Check JD"),
    ("SAP Inhouse Consultant MM (m/w/d)", "Gebr. Kemper GmbH", "Olpe, Germany", "https://de.linkedin.com/jobs/view/sap-inhouse-consultant-mm-m-w-d-at-gebr-kemper-gmbh-%2B-co-kg-4438582405", 78, "Check JD", "Check JD"),
    ("SAP MM Senior Consultant", "IgniteSAP", "Germany", "https://de.linkedin.com/jobs/view/sap-mm-senior-consultant-at-ignitesap-4428851034", 78, "Likely", "Likely"),
    ("In-House SAP MM Consultant", "Energize Group", "Frankfurt, Germany", "https://de.linkedin.com/jobs/view/in-house-sap-mm-consultant-at-energize-group-4436825287", 78, "Check JD", "Check JD"),
    ("SAP Sourcing & Procurement Consultant", "Accenture DACH", "Kronberg, Germany", "https://de.linkedin.com/jobs/view/sap-sourcing-procurement-consultant-all-genders-at-accenture-dach-4437976917", 77, "Yes", "Yes"),
    ("Senior SAP SD/MM Berater (m/w/d)", "Westernacher Consulting", "Berlin, Germany", "https://de.linkedin.com/jobs/view/senior-sap-sd-mm-berater-m-w-d-at-westernacher-consulting-4411342828", 76, "Likely", "Likely"),
    ("SAP Consultant MM/SRM", "Tata Consultancy Services", "Frankfurt, Germany", "https://de.linkedin.com/jobs/view/sap-consultant-mm-srm-all-genders-at-tata-consultancy-services-4414114109", 76, "Yes", "Yes"),
    ("SAP Consultant P2P (Purchase-to-Pay)", "Brückner Maschinenbau", "Siegsdorf, Germany", "https://de.linkedin.com/jobs/view/sap-consultant-p2p-purchase-to-pay-at-br%C3%BCckner-maschinenbau-4429973513", 75, "Check JD", "Check JD"),
    ("Senior Consultant S/4HANA Sales & Procurement", "Velvet Mind GmbH", "Germany", "https://de.linkedin.com/jobs/view/senior-consultant-sap-s-4hana-sales-procurement-e2e-processes-m-w-d-at-velvet-mind-gmbh-4433915636", 75, "Likely", "Likely"),
    ("Senior SAP Consultant (Procurement)", "iTrust Partnering", "Germany", "https://de.linkedin.com/jobs/view/senior-sap-consultant-procurement-at-itrust-partnering-4433951472", 75, "Likely", "Likely"),
    # NETHERLANDS
    ("SAP MM Consultant – Deta vast", "All About Work", "Delft, Netherlands", "https://nl.linkedin.com/jobs/view/sap-mm-consultant-%E2%80%93-deta-vast-at-all-about-work-4439500528", 78, "Check JD", "Check JD"),
    # SWEDEN
    ("Senior SAP Consultant", "Implema", "Malmö, Sweden", "https://se.linkedin.com/jobs/view/senior-sap-consultant-at-implema-4427325283", 72, "Check JD", "Check JD"),
    ("SAP S4 Hana APO/IBP Consultant", "Infosys", "Stockholm, Sweden", "https://se.linkedin.com/jobs/view/sap-s4-hana-apo-ibp-consultant-sweden-at-infosys-4427840606", 70, "Yes", "Yes"),
    # POLAND
    ("Senior SAP SD/MM Consultant", "EPAM Systems", "Poland", "https://pl.linkedin.com/jobs/view/senior-sap-sd-mm-consultant-at-epam-systems-4350751162", 75, "Yes", "Yes"),
    ("SAP Consultant", "RED Global", "Poland", "https://pl.linkedin.com/jobs/view/sap-consultant-at-red-global-4435952751", 70, "Likely", "Likely"),
    # AUSTRALIA
    ("SAP MM/WM Functional Consultant", "ITC Infotech", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/sap-mm-wm-functional-consultant-at-itc-infotech-4437922929", 85, "Yes", "Yes"),
    ("S/4HANA MM - Lean Services Consultant", "Infosys", "Brisbane, Australia", "https://au.linkedin.com/jobs/view/s-4hana-mm-lean-services-consultant-at-infosys-4427332918", 83, "Yes", "Yes"),
    ("SAP EWM Functional Consultant", "Capgemini", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/sap-ewm-functional-consultant-at-capgemini-4429907770", 80, "Yes", "Yes"),
    ("SAP Support Analyst – Supply Chain", "Speller International", "Melbourne, Australia", "https://au.linkedin.com/jobs/view/sap-support-analyst-%E2%80%93-supply-chain-at-speller-international-4437949632", 75, "Check JD", "Check JD"),
    # NEW ZEALAND
    ("SAP Functional Lead – Order Management", "Accenture NZ", "Auckland, New Zealand", "https://nz.linkedin.com/jobs/view/sap-functional-lead-%E2%80%93-order-management-at-accenture-new-zealand-4401425325", 75, "Yes", "Yes"),
    # INDIA (Remote / Hybrid)
    ("SAP MM/LE Systems Analyst", "Chemelex", "Mumbai, India", "https://in.linkedin.com/jobs/view/sap-mm-le-systems-analyst-at-chemelex-4411656783", 85, "N/A", "N/A"),
    ("SAP MM-LE S4HANA Lead Functional Consultant", "Fujitsu", "Chennai, India", "https://in.linkedin.com/jobs/view/sap-mm-le-s4hana-lead-functional-consultant-9358-at-fujitsu-4437784171", 85, "N/A", "N/A"),
    ("SAP MM / P2P Consultant", "MyCareernet", "Hyderabad, India", "https://in.linkedin.com/jobs/view/sap-mm-procure-to-pay-p2p-consultant-100644-at-mycareernet-4435655506", 83, "N/A", "N/A"),
    ("SAP MM/P2P Expert Consultant", "MyCareernet", "Hyderabad, India", "https://in.linkedin.com/jobs/view/sap-mm-p2p-expert-consultant-100737-at-mycareernet-4435632710", 83, "N/A", "N/A"),
    ("Sr Lead Consultant SAP MM", "Birlasoft", "Pune, India", "https://in.linkedin.com/jobs/view/sr-lead-consultant-sap-mm-at-birlasoft-4429047323", 82, "N/A", "N/A"),
    ("SAP Procure To Pay (P2P)", "PwC Acceleration Centers", "Bengaluru, India", "https://in.linkedin.com/jobs/view/sap-procure-to-pay-p2p-10-14y-hyd-blr-pwc-ac-at-pwc-acceleration-centers-4437980819", 82, "N/A", "N/A"),
    ("SAP S/4 SD/MM Lead - Manufacturing & Supply Chain", "Tata Electronics", "Bengaluru, India", "https://in.linkedin.com/jobs/view/sap-s-4-sd-mm-lead-manufacturing-supply-chain-at-tata-electronics-4399908269", 82, "N/A", "N/A"),
    ("SAP S/4HANA MM & WM Manager", "Artech L.L.C.", "Bengaluru, India", "https://in.linkedin.com/jobs/view/sap-s-4hana-mm-wm-manager-at-artech-l-l-c-4436508821", 82, "N/A", "N/A"),
    ("IT Business Consultant Supply Chain - SAP MM", "Clariant", "Navi Mumbai, India", "https://in.linkedin.com/jobs/view/it-business-consultant-supply-chain-sap-mm-at-clariant-4401710324", 80, "N/A", "N/A"),
    ("SAP WM/LE/MM Consultant", "CloudLabs Inc", "India (Remote)", "https://in.linkedin.com/jobs/view/sap-wm-le-mm-consultant-at-cloudlabs-inc-4436083088", 80, "N/A", "N/A"),
    ("Subject Matter Expert – Procure to Pay", "IKEA", "Bengaluru, India", "https://in.linkedin.com/jobs/view/%E2%80%8B%E2%80%8Bsubject-matter-expert-%E2%80%93-procure-to-pay-at-ikea-4437022043", 80, "N/A", "N/A"),
    ("IN_Senior Manager SAP MM - Advisory", "PwC India", "Gurugram, India", "https://in.linkedin.com/jobs/view/in-senior-manager-sap-mm-sap-advisory-gurgaon-at-pwc-india-4439565799", 80, "N/A", "N/A"),
    ("SAP EWM Functional Consultant", "Westernacher Consulting", "Kolkata, India", "https://in.linkedin.com/jobs/view/sap-ewm-functional-consultant-at-westernacher-consulting-4411336811", 82, "N/A", "N/A"),
    ("SAP EWM Consultant (Grade 3)", "Umanist NA", "India (Remote)", "https://in.linkedin.com/jobs/view/sap-ewm-consultant-grade-3-at-umanist-na-4437982478", 80, "N/A", "N/A"),
    ("SAP EWM Functional Consultant", "Capgemini", "Bengaluru, India", "https://in.linkedin.com/jobs/view/sap-ewm-consultant-at-capgemini-4433935574", 80, "N/A", "N/A"),
    ("SAP EWM Consultant", "NTT DATA", "Hyderabad, India", "https://in.linkedin.com/jobs/view/sap-ewm-consultant-at-ntt-data-north-america-4411607809", 78, "N/A", "N/A"),
    ("SAP EWM Consultant", "Infosys", "Bengaluru, India", "https://in.linkedin.com/jobs/view/sap-ewm-consultant-at-infosys-4436883356", 78, "N/A", "N/A"),
    ("IT&D Senior Analyst SAP Procurement", "Reckitt", "Hyderabad, India", "https://in.linkedin.com/jobs/view/it-d-senior-analyst-sap-procurement-at-reckitt-4438230842", 78, "N/A", "N/A"),
    ("Functional Lead - SAP SCM", "Dover India", "Bengaluru, India", "https://in.linkedin.com/jobs/view/functional-lead-sap-scm-at-dover-india-4434860511", 77, "N/A", "N/A"),
    ("SAP Functional Analyst - Distribution (eWM)", "McCormick & Company", "Gurugram, India", "https://in.linkedin.com/jobs/view/sap-functional-analyst-distribution-ewm-at-mccormick-company-4437019863", 77, "N/A", "N/A"),
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

eu_jobs = [j for j in jobs if any(c in j[2] for c in ("Germany", "Netherlands", "Sweden", "Poland"))]
au_nz_jobs = [j for j in jobs if any(c in j[2] for c in ("Australia", "New Zealand"))]
india_jobs = [j for j in jobs if "India" in j[2]]

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">SAP MM Job Matches — Pradeep Meena</h2>
  <p style="color:#666;">Profile: SAP MM/EWM | 7+ yrs | S/4HANA Certified | P2P, Inventory, Cross-module Integration — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Posted within 1 week | Visa sponsorship & relocation support indicated</p>
  {build_section("Europe", "Germany, Netherlands, Sweden, Poland", eu_jobs)}
  {build_section("Australia & New Zealand", "Melbourne, Brisbane, Auckland", au_nz_jobs)}
  {build_section("India (Remote / Hybrid)", "Pune, Bengaluru, Hyderabad, Chennai, Mumbai, Gurugram", india_jobs)}
  <h3 style="color:#444;margin-top:28px;">Top Picks for Visa Sponsorship</h3>
  <ul style="color:#555;font-size:14px;line-height:1.8;">
    <li><b>Siemens Energy / Healthineers</b> (Germany) — exact SAP MM+EWM match, global sponsor</li>
    <li><b>ITC Infotech</b> (Melbourne) — SAP MM/WM, matches profile perfectly</li>
    <li><b>Infosys</b> (Brisbane + Stockholm) — Pradeep's ex-employer, internal transfer possible</li>
    <li><b>Capgemini</b> (Melbourne) — SAP EWM, large multinational</li>
    <li><b>Accenture</b> (Germany + NZ) — Pradeep currently at Accenture</li>
    <li><b>TCS / EPAM</b> (Germany / Poland) — known sponsors for Indian consultants</li>
  </ul>
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="SAP MM Job Matches - Pradeep (EU + Australia + NZ)")
