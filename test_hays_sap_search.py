"""
Test Hays scraper with SAP-specific search for Pradeep
"""

import sys
import re
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import random
import time

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

print("Testing Hays SAP-specific search for Pradeep...\n")

# SAP-specific Hays URLs
sap_urls = {
    "DE_SAP_MM": "https://www.hays.de/jobsuche?q=SAP+MM",
    "DE_SAP_EWM": "https://www.hays.de/jobsuche?q=SAP+EWM",
    "DE_Backend": "https://www.hays.de/jobsuche?q=Backend+Engineer",
}

results = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    for search_name, url in sap_urls.items():
        print(f"Searching: {search_name}")
        print(f"URL: {url}")
        
        page = browser.new_page()
        ua = random.choice(USER_AGENTS)
        page.set_extra_http_headers({'User-Agent': ua})
        
        try:
            page.goto(url, wait_until='load', timeout=20000)
            time.sleep(2)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for job detail links
            detail_link_pattern = r'/(jobsuche|job-search|vacatures|recherche-emploi|vacaturehays)/.*-\d+/?'
            detail_links = soup.find_all('a', href=re.compile(detail_link_pattern))
            
            jobs = []
            for link in detail_links[:10]:  # First 10
                try:
                    href = link.get('href', '')
                    if href.startswith('/'):
                        href = f"https://www.hays.de{href}"
                    
                    match = re.search(r'-(detail|job)[-/](.+?)-(\d+)[/?]', href)
                    if match:
                        title_slug = match.group(2)
                        title = title_slug.replace('-', ' ').title()
                        jobs.append({'title': title, 'url': href[:80]})
                except:
                    pass
            
            results[search_name] = jobs
            print(f"  ✅ Found {len(jobs)} jobs")
            for i, job in enumerate(jobs[:3], 1):
                print(f"     {i}. {job['title']}")
            print()
            
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}\n")
        finally:
            page.close()
    
    browser.close()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
total_jobs = sum(len(jobs) for jobs in results.values())
print(f"\nTotal jobs found across {len(results)} searches: {total_jobs}")

for search_name, jobs in results.items():
    if jobs:
        print(f"\n✅ {search_name}: {len(jobs)} jobs")
        for i, job in enumerate(jobs[:2], 1):
            print(f"   {i}. {job['title']}")

if total_jobs > 0:
    print("\n✅ HAYS SAP SEARCH WORKING - Ready for production")
else:
    print("\n⚠️  No SAP jobs found on this scan (may be rate limiting or low volume)")

