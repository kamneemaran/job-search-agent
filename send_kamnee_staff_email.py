import os, sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from daily_scan import send_email
from datetime import datetime

jobs = [
    ("Staff Engineer — Data Platform", "Yuno", "Berlin, Germany", "https://de.linkedin.com/jobs/view/staff-engineer-%E2%80%93-data-platform-at-yuno-4440381872", 95, "Staff Level", "Yes"),
    ("Principal Engineer — Real-Time Data Systems", "Jobgether", "Berlin, Germany", "https://de.linkedin.com/jobs/view/principal-engineer-%E2%80%93-real-time-data-systems-at-jobgether-4443269858", 86, "Principal Level", "Yes"),
    ("Senior / Principal Software Engineer", "Weflow", "Germany (Remote)", "https://de.linkedin.com/jobs/view/senior-principal-software-engineer-m-f-d-remote-at-weflow-4442827388", 81, "Principal Level", "Yes"),
    ("Principal Engineer (FinTech / Banking)", "Solaris SE", "Berlin, Germany", "https://de.linkedin.com/jobs/view/principal-engineer-at-solaris-se-4433139015", 70, "Principal Level", "Yes"),
    ("Staff Engineer — Data Platform", "Yuno", "Amsterdam, Netherlands", "https://nl.linkedin.com/jobs/view/staff-engineer-%E2%80%93-data-platform-at-yuno-4440500013", 95, "Staff Level", "Yes"),
    ("Principal Engineer — Real-Time Data Systems", "Jobgether", "Amsterdam, Netherlands", "https://nl.linkedin.com/jobs/view/principal-engineer-%E2%80%93-real-time-data-systems-at-jobgether-4443276187", 86, "Principal Level", "Yes"),
    ("Senior Software Engineer - Payments & FinTech", "OrderYOYO", "Amsterdam, Netherlands", "https://nl.linkedin.com/jobs/view/senior-software-engineer-payments-at-orderyoyo-4441343693", 78, "Senior Level (Payments)", "Yes"),
    ("Staff Engineer — Data Platform", "Yuno", "Gothenburg, Sweden", "https://se.linkedin.com/jobs/view/staff-engineer-%E2%80%93-data-platform-at-yuno-4440397071", 95, "Staff Level", "Yes"),
    ("Staff Engineer", "Rain", "Stockholm, Sweden", "https://se.linkedin.com/jobs/view/staff-engineer-at-rain-4443541956", 65, "Staff Level", "Check JD"),
]

def build_section(title, subtitle, jobs_list):
    rows = ""
    for title_j, company, location, url, score, level, visa in jobs_list:
        rows += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee;"><a href="{url}" style="color:#1a73e8;text-decoration:none;">{title_j}</a></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{company}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{location}</td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;">{level}</td>
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
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Role Seniority</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Visa / Relo</th>
          <th style="padding:10px;text-align:center;font-size:13px;color:#555;">Score</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>"""

de_jobs = [j for j in jobs if "Germany" in j[2]]
nl_jobs = [j for j in jobs if "Netherlands" in j[2]]
se_jobs = [j for j in jobs if "Sweden" in j[2]]

html = f"""<html><body style="font-family:Arial,sans-serif;max-width:800px;margin:20px auto;padding:20px;">
  <h2 style="color:#333;">Staff & Principal Engineer Job Matches — Europe (Kamnee Maran)</h2>
  <p style="color:#666;">Profile: Staff Software Engineer | 11 years | Distributed Systems, FinTech, Payments, High Scale — {datetime.now().strftime("%d %b %Y")}</p>
  <p style="color:#888;font-size:13px;">Selected high-score Staff and Principal level roles in Europe with visa sponsorship and relocation support</p>
  {build_section("Germany", "Berlin, Remote", de_jobs)}
  {build_section("Netherlands", "Amsterdam, Eindhoven", nl_jobs)}
  {build_section("Sweden", "Gothenburg, Stockholm", se_jobs)}
  <hr style="margin-top:24px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#aaa;">Sent via Job Search Agent</p>
</body></html>"""

send_email(html, subject="Staff / Principal Software Engineer Job Matches - Europe (Kamnee)", recipient="kamneemaran45@gmail.com")
print("Email sent successfully to kamneemaran45@gmail.com")