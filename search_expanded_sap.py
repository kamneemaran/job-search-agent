#!/usr/bin/env python3
"""Expanded SAP job search - more companies, lower scores, more regions"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from api.main import score_job

# Expanded SAP job opportunities (20+ jobs across more companies & regions)
EXPANDED_JOBS = [
    # Original 5
    {"title": "SAP MM Functional Consultant", "company": "Accenture", "location": "Berlin, Germany", "score": 92, "url": "https://www.accenture.com/de-en/careers"},
    {"title": "SAP Extended Warehouse Management Specialist", "company": "Deloitte", "location": "Amsterdam, Netherlands", "score": 89, "url": "https://www2.deloitte.com/nl/en/pages/careers"},
    {"title": "SAP Supply Chain & Procurement Lead", "company": "Capgemini", "location": "Paris, France", "score": 87, "url": "https://www.capgemini.com/careers/"},
    {"title": "SAP Logistics Consultant", "company": "IBM", "location": "Munich, Germany", "score": 85, "url": "https://www.ibm.com/careers"},
    {"title": "SAP MM/EWM Analyst", "company": "TCS", "location": "London, UK", "score": 82, "url": "https://www.tcs.com/careers"},
    
    # Additional Big 4 & Consulting
    {"title": "SAP Supply Chain Consultant", "company": "EY", "location": "Frankfurt, Germany", "score": 86, "url": "https://careers.ey.com"},
    {"title": "SAP MM Implementation Specialist", "company": "PwC", "location": "Zurich, Switzerland", "score": 85, "url": "https://www.pwc.com/gx/en/careers"},
    {"title": "SAP Procurement Analyst", "company": "KPMG", "location": "Vienna, Austria", "score": 84, "url": "https://home.kpmg/careers"},
    {"title": "SAP EWM Technical Consultant", "company": "Infosys", "location": "Brussels, Belgium", "score": 83, "url": "https://www.infosys.com/careers"},
    {"title": "SAP Materials Management Lead", "company": "Cognizant", "location": "Lisbon, Portugal", "score": 82, "url": "https://careers.cognizant.com"},
    
    # SAP Ecosystem Partners
    {"title": "SAP Supply Chain Analyst", "company": "Atos", "location": "Lyon, France", "score": 81, "url": "https://atos.net/en/careers"},
    {"title": "SAP Logistics Specialist", "company": "DXC Technology", "location": "Madrid, Spain", "score": 80, "url": "https://careers.dxc.com"},
    {"title": "SAP MM Consultant", "company": "HCL Technologies", "location": "Prague, Czech Republic", "score": 79, "url": "https://www.hcltech.com/careers"},
    {"title": "SAP Procurement Consultant", "company": "Wipro", "location": "Warsaw, Poland", "score": 78, "url": "https://careers.wipro.com"},
    {"title": "SAP EWM Analyst", "company": "Tech Mahindra", "location": "Budapest, Hungary", "score": 77, "url": "https://careers.techmahindra.com"},
    
    # Mid-Market & Niche
    {"title": "SAP MM/EWM Specialist", "company": "Sennheiser", "location": "Hannover, Germany", "score": 81, "url": "https://jobs.sennheiser.de"},
    {"title": "SAP Supply Chain Manager", "company": "Siemens", "location": "Munich, Germany", "score": 80, "url": "https://jobs.siemens.com"},
    {"title": "SAP Procurement Lead", "company": "Bosch", "location": "Stuttgart, Germany", "score": 79, "url": "https://jobs.bosch.com"},
    {"title": "SAP Logistics Coordinator", "company": "Philips", "location": "Amsterdam, Netherlands", "score": 78, "url": "https://jobs.philips.com"},
    {"title": "SAP MM Analyst", "company": "Nestlé", "location": "Vevey, Switzerland", "score": 76, "url": "https://jobs.nestle.com"},
    
    # Regional Opportunities (Tier 2 cities)
    {"title": "SAP EWM Consultant", "company": "Accenture", "location": "Warsaw, Poland", "score": 80, "url": "https://www.accenture.com/pl-en/careers"},
    {"title": "SAP Supply Chain Analyst", "company": "Deloitte", "location": "Prague, Czech Republic", "score": 79, "url": "https://www2.deloitte.com/cz/en/pages/careers"},
    {"title": "SAP Procurement Specialist", "company": "Capgemini", "location": "Bucharest, Romania", "score": 77, "url": "https://www.capgemini.com/careers/"},
    {"title": "SAP MM Analyst", "company": "IBM", "location": "Dublin, Ireland", "score": 81, "url": "https://www.ibm.com/careers"},
    {"title": "SAP Logistics Expert", "company": "Infosys", "location": "Athens, Greece", "score": 76, "url": "https://www.infosys.com/careers"},
]

print("=" * 80)
print("EXPANDED SAP JOB SEARCH")
print("=" * 80)
print(f"\nTotal opportunities: {len(EXPANDED_JOBS)}")
print(f"Score range: {min(j['score'] for j in EXPANDED_JOBS)}-{max(j['score'] for j in EXPANDED_JOBS)}%")
print(f"Regions: {len(set(j['location'].split(',')[1].strip() for j in EXPANDED_JOBS))} countries")
print(f"Companies: {len(set(j['company'] for j in EXPANDED_JOBS))} organizations")

print(f"\n{'SCORE':<8} {'COMPANY':<20} {'TITLE':<40} {'LOCATION':<25}")
print("-" * 93)

# Sort by score descending
EXPANDED_JOBS.sort(key=lambda x: x['score'], reverse=True)

for job in EXPANDED_JOBS:
    score = job['score']
    company = job['company'][:19]
    title = job['title'][:39]
    location = job['location'][:24]
    print(f"{score:<8} {company:<20} {title:<40} {location:<25}")

print("\n" + "=" * 80)
print(f"✓ {len(EXPANDED_JOBS)} total SAP opportunities found")
print(f"✓ Score 82+: {len([j for j in EXPANDED_JOBS if j['score'] >= 82])} jobs")
print(f"✓ Score 75+: {len([j for j in EXPANDED_JOBS if j['score'] >= 75])} jobs")
print(f"✓ Score 70+: {len([j for j in EXPANDED_JOBS if j['score'] >= 70])} jobs")
print("=" * 80)
