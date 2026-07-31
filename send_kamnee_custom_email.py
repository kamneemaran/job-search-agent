import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from daily_scan import send_email
from datetime import datetime

eu_jobs = [
    ("Staff Software Engineer", "Digital Charging Solutions", "Berlin, Germany", "https://de.linkedin.com/jobs/view/staff-software-engineer-f-m-d-at-digital-charging-solutions-4444576583", 91, "Yes (Full Relocation)"),
    ("Staff Software Engineer", "Annapurna", "Berlin, Germany", "https://de.linkedin.com/jobs/view/staff-software-engineer-at-annapurna-4446314241", 86, "Yes (Sponsorship)"),
    ("Staff Software Engineer", "Helsing", "Berlin/Munich, Germany", "https://de.linkedin.com/jobs/view/staff-software-engineer-at-helsing-4435907268", 78, "Yes (Full Relocation)"),
]

in_jobs = [
    ("Staff Software Engineer", "Okta", "Bengaluru, India", "https://www.naukri.com/job-listings-staff-software-engineer-okta-identity-india-private-limited-bengaluru-9-to-14-years-290726926835?xp=5", 95, "N/A"),
    ("Staff Software Engineer", "Logicmonitor", "Pune, India", "https://www.naukri.com/job-listings-staff-software-engineer-logicmonitor-pune-8-to-13-years-300726501874?xp=9", 95, "N/A"),
    ("Principal Software Engineer", "Eli Lilly and Company", "Hyderabad, India", "https://www.naukri.com/job-listings-principal-software-engineer-eli-lilly-and-company-hyderabad-8-to-13-years-300726501898?xp=11", 95, "N/A"),
]

apac_jobs = [
    ("Lead Software Engineer", "Nexus Corporation", "Tokyo, Japan", "https://jp.linkedin.com/jobs/view/lead-software-engineer-at-nexus-corporation-4443494236", 95, "Yes (Full Relocation)"),
    ("Principal Forward Deployed Engineer", "Microsoft", "Tokyo, Japan", "https://jp.linkedin.com/jobs/view/principal-forward-deployed-engineer-software-engineer-at-microsoft-4446594006", 76, "Yes (Sponsorship)"),
]

def build_section(title, subtitle, jobs_list):
    rows = ""
    for title_j, company, location, url, score, visa in jobs_list:
        visa_color = "#16a34a" if visa != "N/A" else "#666"
        rows += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee;"><a href="{url}" style="color:#1a73e8;text-decoration:none;">{title_j}</a></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{company}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{location}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;color:{visa_color};font-weight:600;">{visa}</td>
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
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Visa / Relo</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Score</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>"""

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">Staff & Principal Software Engineer Matches</h2>
  <p style="color:#666;">Profile: Staff Software Engineer | 11 years | Java, Python, Node.js, Microservices, Distributed Systems, Kafka, Kubernetes — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Highly targeted, premium matches based exactly on your tech stack and experience, posted within the last week</p>
  {build_section("Europe Region", "Germany & Netherlands Hubs (Full Visa & Relocation Support)", eu_jobs)}
  {build_section("India Region", "High-growth local hubs (Pune & Bengaluru)", in_jobs)}
  {build_section("APAC Region (Japan, Australia, New Zealand)", "Tokyo Tech Hubs (Full Visa & Relocation Support)", apac_jobs)}
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="Staff & Principal Software Engineer Job Matches - Global (Kamnee)", recipient="kamneemaran45@gmail.com")
print("Email sent successfully to kamneemaran45@gmail.com")