"""
Final test: Extract actual job titles from Hays
"""

import sys
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import random
import time
import json

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def extract_hays_jobs_final(url):
    """Final refined extraction - look for title text near links"""
    jobs = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        ua = random.choice(USER_AGENTS)
        page.set_extra_http_headers({'User-Agent': ua})
        
        try:
            page.goto(url, wait_until='load', timeout=20000)
            time.sleep(2)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for job result containers
            # Find the parent container of job links
            detail_links = soup.find_all('a', href=re.compile(r'/jobsuche/stellenangebote-jobs-detail-'))
            
            print(f"Found {len(detail_links)} job links\n")
            
            for link in detail_links[:25]:
                try:
                    href = link.get('href', '')
                    
                    # Extract title from URL (it contains the job title and location)
                    # Pattern: /jobsuche/stellenangebote-jobs-detail-<title>-<location>-<id>/
                    match = re.search(r'/stellenangebote-jobs-detail-(.+?)-(\d+)/', href)
                    if not match:
                        continue
                    
                    url_title = match.group(1)
                    job_id = match.group(2)
                    
                    # Convert URL slug to readable title
                    # Format: title-location, with multiple hyphens
                    # Try to find location (usually last word or after last hyphen + number pattern)
                    parts = url_title.rsplit('-', 1)
                    if len(parts) == 2 and parts[-1].replace('-', '').isalpha():
                        title = parts[0].replace('-', ' ').title()
                        location = parts[-1].replace('-', ' ').title()
                    else:
                        title = url_title.replace('-', ' ').title()
                        location = "Germany"  # default
                    
                    # Make absolute URL
                    if href.startswith('/'):
                        href = f"https://www.hays.de{href}"
                    
                    # Filter for SAP-related (check URL or title)
                    if any(kw.lower() in url_title.lower() for kw in ['sap', 'mm', 'ewm', 'supply', 'materials', 'warehouse']):
                        jobs.append({
                            'title': title,
                            'url_title': url_title,
                            'location': location,
                            'url': href,
                            'source': 'Hays',
                            'company': 'Hays',
                            'job_id': job_id
                        })
                
                except Exception as e:
                    continue
            
        finally:
            page.close()
            browser.close()
    
    return jobs

# Test on Germany
print("Testing refined Hays Germany extraction...\n")
jobs_de = extract_hays_jobs_final("https://www.hays.de/jobsuche?q=SAP+MM")

print("Extracted Jobs:")
print("=" * 80)
for i, job in enumerate(jobs_de, 1):
    print(f"{i}. {job['title']}")
    print(f"   URL Title: {job['url_title']}")
    print(f"   Location: {job['location']}")
    print(f"   URL: {job['url']}")
    print()

print(f"\nTotal: {len(jobs_de)} SAP-related jobs extracted")

# Save to file
output_file = '/Users/kamnee.maran/Downloads/job-search-agent/hays_test_extraction.json'
with open(output_file, 'w') as f:
    json.dump(jobs_de, f, indent=2)
print(f"Saved to: {output_file}")

