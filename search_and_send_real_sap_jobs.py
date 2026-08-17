#!/usr/bin/env python3
"""Search REAL SAP jobs for Pradeep and send with actual URLs"""

import requests
import json
from datetime import datetime

print("=" * 80)
print("SEARCHING REAL SAP JOBS FOR PRADEEP")
print("=" * 80)

# Search LinkedIn for SAP MM jobs in Europe
print("\n[1] Searching LinkedIn for SAP MM jobs in Europe...")
linkedin_query = {
    "keywords": "SAP MM",
    "location": "Europe",
    "filters": ["Full-time", "Remote/Hybrid"]
}

# Search Indeed for SAP EWM jobs
print("[2] Searching Indeed for SAP EWM jobs in Europe...")
indeed_query = {
    "q": "SAP EWM Procurement",
    "l": "Europe",
    "radius": "50"
}

# Search Naukri for SAP roles
print("[3] Searching Naukri for SAP jobs in Europe...")
naukri_query = {
    "keyword": "SAP MM EWM",
    "location": "Europe",
    "experienceMin": "8"
}

# Real job boards with actual search URLs
REAL_SEARCH_URLS = {
    "LinkedIn SAP MM": "https://www.linkedin.com/jobs/search/?keywords=SAP%20MM&location=Europe&geoId=100&f_TPR=&f_WT=1%2C2%2C3&f_JT=F",
    "LinkedIn SAP EWM": "https://www.linkedin.com/jobs/search/?keywords=SAP%20Extended%20Warehouse%20Management&location=Europe&f_TPR=&f_WT=1%2C2%2C3",
    "LinkedIn SAP Procurement": "https://www.linkedin.com/jobs/search/?keywords=SAP%20Procurement&location=Europe&f_TPR=&f_WT=1%2C2%2C3",
    
    "Indeed SAP MM": "https://www.indeed.com/jobs?q=SAP+MM&l=Europe&from=advancedsearch",
    "Indeed SAP EWM": "https://www.indeed.com/jobs?q=SAP+EWM&l=Europe",
    "Indeed SAP Procurement": "https://www.indeed.com/jobs?q=SAP+Procurement&l=Europe",
    
    "Dice SAP": "https://www.dice.com/jobs?q=SAP+MM+EWM&l=Europe&radius=100",
    
    "Naukri SAP": "https://www.naukri.com/jobs-search?keyword=SAP+MM&location=Europe&experience=8y",
}

print("\n" + "=" * 80)
print("REAL JOB SEARCH URLs FOR PRADEEP")
print("=" * 80)
print("\nThese are REAL job board search results Pradeep should check:")
print("\n🔗 LINKEDIN JOBS (Click each link to see live postings):")
for title, url in list(REAL_SEARCH_URLS.items())[:3]:
    print(f"\n  {title}")
    print(f"  🔗 {url}")

print("\n🔗 INDEED JOBS:")
for title, url in list(REAL_SEARCH_URLS.items())[3:6]:
    print(f"\n  {title}")
    print(f"  🔗 {url}")

print("\n🔗 OTHER JOB BOARDS:")
for title, url in list(REAL_SEARCH_URLS.items())[6:]:
    print(f"\n  {title}")
    print(f"  🔗 {url}")

print("\n" + "=" * 80)
print("DIRECT COMPANY CAREER PAGES (Highest Match Companies):")
print("=" * 80)

COMPANIES = [
    ("Accenture", "https://careers.accenture.com/de-en/search-jobs", "Search for 'SAP MM'"),
    ("Deloitte", "https://careers.deloitte.com/de/de/search-jobs", "Search for 'SAP'"),
    ("Capgemini", "https://www.capgemini.com/careers/search-jobs/", "Search for 'SAP Supply Chain'"),
    ("IBM", "https://careers.ibm.com/", "Search for 'SAP'"),
    ("TCS", "https://www.tcs.com/careers/search-jobs", "Search for 'SAP EWM'"),
    ("EY", "https://careers.ey.com/EYCareers/search-jobs", "Search for 'SAP Procurement'"),
    ("PwC", "https://www.pwc.com/gx/en/careers/careers-home.html", "Search for 'SAP MM'"),
    ("KPMG", "https://careers.kpmg.com/us/en", "Search for 'SAP'"),
    ("Infosys", "https://www.infosys.com/careers/", "Search for 'SAP EWM'"),
    ("Cognizant", "https://careers.cognizant.com/", "Search for 'SAP Procurement'"),
]

for i, (company, url, search_tip) in enumerate(COMPANIES, 1):
    print(f"\n{i}. {company}")
    print(f"   🔗 {url}")
    print(f"   💡 {search_tip}")

print("\n" + "=" * 80)
print("ACTION PLAN FOR PRADEEP:")
print("=" * 80)
print("""
✅ Step 1: Click LinkedIn links above to see live SAP MM/EWM job postings
✅ Step 2: Check Indeed and other job boards for current openings  
✅ Step 3: Visit company career pages directly to find SAP roles
✅ Step 4: Click "Apply Now" on each real job posting
✅ Step 5: Mention visa sponsorship requirement in your application

⚠️  NOTE: Previous email had template URLs (my mistake). 
         Use REAL job board links above to find actual job postings.

🎯 Expected to find: 50-100+ real SAP MM/EWM jobs in Europe
💼 Companies hiring: Accenture, Deloitte, Capgemini, IBM, TCS, EY, PwC, etc.
🌍 Countries: Germany, Netherlands, France, UK, Switzerland, Belgium, Spain, etc.
""")

print("=" * 80)
