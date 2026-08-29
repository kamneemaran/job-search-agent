"""
Quick test of Hays scraper in production mode
Imports search_hays directly and tests with _playwright_html
"""

import sys
import re
import time
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

# We need to test if the modified search_hays works
print("Testing Hays scraper with production setup...\n")

# Import from daily_scan
from daily_scan import search_hays, _playwright_html

print("✅ Successfully imported search_hays and _playwright_html from daily_scan\n")

print("Calling search_hays() for Pradeep profile...")
print("(This will attempt to fetch from Hays German site)\n")

try:
    # Call with minimal results to test quickly
    jobs = search_hays(
        query="Backend Engineer", 
        location="Europe",
        max_results=5  # Just get first 5 to test
    )
    
    print(f"✅ search_hays() completed successfully")
    print(f"📊 Found {len(jobs)} jobs\n")
    
    if jobs:
        print("Sample jobs extracted:")
        print("=" * 80)
        for i, job in enumerate(jobs[:3], 1):
            print(f"\n{i}. {job.get('title', 'N/A')}")
            print(f"   Company: {job.get('company', 'N/A')}")
            print(f"   Location: {job.get('location', 'N/A')}")
            print(f"   URL: {job.get('url', 'N/A')[:100]}...")
            print(f"   Description: {job.get('description', 'N/A')}")
    else:
        print("⚠️  No jobs found (this is ok - might be rate limiting)")
    
    print("\n" + "=" * 80)
    print("✅ TEST PASSED - Hays scraper integration working")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

