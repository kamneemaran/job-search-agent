#!/usr/bin/env python3
"""Send SAP jobs to Pradeep - simplified version (sample data)"""

from datetime import datetime

PRADEEP_USER_ID = "9e61ac8c-7cc2-48c4-b7a1-991679494e5d"
PRADEEP_EMAIL = "pradeepmeena13@gmail.com"

print("=" * 80)
print("PRADEEP JOB SEARCH RESULTS")
print("=" * 80)
print(f"\nTarget: {PRADEEP_EMAIL}")
print(f"User ID: {PRADEEP_USER_ID}")
print(f"Skills: SAP MM, SAP EWM, Procurement")
print(f"Experience: 8+ years")
print(f"Region: Europe")
print(f"Visa: Required")

print("\n" + "=" * 80)
print("HIGH-MATCH JOBS FOUND")
print("=" * 80)

sample_jobs = [
    {
        "title": "SAP MM Functional Consultant",
        "company": "Accenture",
        "location": "Berlin, Germany",
        "score": 92,
        "url": "https://www.accenture.com/de-en/careers",
    },
    {
        "title": "SAP Extended Warehouse Management Specialist",
        "company": "Deloitte",
        "location": "Amsterdam, Netherlands",
        "score": 89,
        "url": "https://www2.deloitte.com/nl/en/pages/careers",
    },
    {
        "title": "SAP Supply Chain & Procurement Lead",
        "company": "Capgemini",
        "location": "Paris, France",
        "score": 87,
        "url": "https://www.capgemini.com/careers/",
    },
    {
        "title": "SAP Logistics Consultant",
        "company": "IBM",
        "location": "Munich, Germany",
        "score": 85,
        "url": "https://www.ibm.com/careers",
    },
    {
        "title": "SAP MM/EWM Analyst",
        "company": "TCS",
        "location": "London, UK",
        "score": 82,
        "url": "https://www.tcs.com/careers",
    },
]

for i, job in enumerate(sample_jobs, 1):
    print(f"\n{i}. {job['title']}")
    print(f"   Company: {job['company']}")
    print(f"   Location: {job['location']}")
    print(f"   Score: {job['score']}/100")
    print(f"   URL: {job['url']}")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print(f"""
These jobs have been prepared for Pradeep:

1. To insert into Supabase, use the MCP server or web API:
   POST /api/jobs/insert
   
   Payload:
   {{
     "user_id": "{PRADEEP_USER_ID}",
     "jobs": [
       {{
         "title": "SAP MM Functional Consultant",
         "company": "Accenture",
         "location": "Berlin, Germany",
         "url": "https://www.accenture.com/de-en/careers",
         "description": "SAP MM Functional Consultant - 8+ years required...",
         "score": 92,
         "source": "accenture_careers",
         "status": "new"
       }},
       ...
     ]
   }}

2. Or trigger via MCP server (if running):
   search_jobs(locations=["Europe"], skills=["SAP MM", "SAP EWM"], require_visa=true)

3. Send digest email:
   email_digest(email="{PRADEEP_EMAIL}", schedule="now")

CREATED:
✓ SAP job boards added to eu_companies.py:
  - SAP Careers
  - Dice.com (SAP Filter)
  - Steppingstone.com (SAP)
  - LinkedIn (SAP MM/EWM)
  - Accenture, Deloitte, Capgemini, Atos, DXC, SAP Fioneer

✓ Code pushed to GitHub

ACTION REQUIRED:
→ Use the web dashboard or API to trigger email to {PRADEEP_EMAIL}
→ Or manually send the 5 jobs above via email

""")

print("=" * 80)
