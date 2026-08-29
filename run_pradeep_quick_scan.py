"""
Quick Pradeep scan - just SAP Jobs Board + Hays (no LinkedIn to save time)
"""

import sys
import json
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

print("=" * 80)
print("QUICK PRADEEP JOB SCAN (SAP Board + Hays + Indeed)")
print("=" * 80)
print("\nProfile: Pradeep (8 years SAP MM/EWM)\n")

all_jobs = []

# 1. SAP Jobs Board
print("1️⃣  Searching SAP Jobs Board...")
try:
    from daily_scan import search_sap_jobs_board
    sap_jobs = search_sap_jobs_board("SAP MM", "Europe", max_results=30)
    print(f"   ✅ Found {len(sap_jobs)} jobs\n")
    all_jobs.extend(sap_jobs)
except Exception as e:
    print(f"   ❌ Error: {e}\n")

# 2. Hays
print("2️⃣  Searching Hays (Germany)...")
try:
    from daily_scan import search_hays
    hays_jobs = search_hays("SAP MM", "Europe", max_results=20)
    print(f"   ✅ Found {len(hays_jobs)} jobs\n")
    all_jobs.extend(hays_jobs)
except Exception as e:
    print(f"   ❌ Error: {e}\n")

# 3. Indeed
print("3️⃣  Searching Indeed (Germany)...")
try:
    from daily_scan import search_indeed_de
    indeed_jobs = search_indeed_de("SAP MM", "Germany", max_results=20)
    print(f"   ✅ Found {len(indeed_jobs)} jobs\n")
    all_jobs.extend(indeed_jobs)
except Exception as e:
    print(f"   ❌ Error: {e}\n")

# Summary
print("=" * 80)
print("SCAN RESULTS")
print("=" * 80)
print(f"\nTotal jobs found: {len(all_jobs)}")

if all_jobs:
    print(f"\nBreakdown by source:")
    sources = {}
    for job in all_jobs:
        source = job.get('source', 'Unknown')
        sources[source] = sources.get(source, 0) + 1
    
    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {source}: {count} jobs")
    
    print(f"\nTop 10 jobs:")
    print("-" * 80)
    for i, job in enumerate(all_jobs[:10], 1):
        title = job.get('title', 'N/A')[:50]
        company = job.get('company', 'N/A')[:30]
        location = job.get('location', 'N/A')
        print(f"{i:2}. {title:50} | {company:30} | {location}")
    
    # Save results
    output_file = '/Users/kamnee.maran/Downloads/job-search-agent/pradeep_quick_scan_results.json'
    with open(output_file, 'w') as f:
        json.dump(all_jobs, f, indent=2)
    print(f"\n✅ Results saved to: {output_file}")

print("\n" + "=" * 80)

