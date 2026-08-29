"""
Test refined job extraction from Hays
"""

import sys
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import random
import time

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def extract_hays_jobs_refined(url):
    """Refined extraction using href patterns"""
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
            
            # Look for links with href pattern: /jobsuche/stellenangebote-jobs-detail-...-\d+/\d+
            detail_links = soup.find_all('a', href=re.compile(r'/jobsuche/stellenangebote-jobs-detail-'))
            
            print(f"Found {len(detail_links)} job detail links\n")
            
            for link in detail_links[:30]:
                try:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # Make absolute URL
                    if href.startswith('/'):
                        href = f"https://www.hays.de{href}"
                    
                    # Extract location from title (usually "Title - Location" format)
                    location_match = re.search(r'–\s*([^–]+)$', title)
                    location = location_match.group(1).strip() if location_match else "Germany"
                    
                    jobs.append({
                        'title': title.split('–')[0].strip() if '–' in title else title,
                        'full_title': title,
                        'location': location,
                        'url': href,
                        'source': 'Hays',
                        'company': 'Hays'
                    })
                except Exception as e:
                    print(f"Error parsing link: {e}")
            
        finally:
            page.close()
            browser.close()
    
    return jobs

# Test on Germany
print("Testing Hays Germany extraction...\n")
jobs_de = extract_hays_jobs_refined("https://www.hays.de/jobsuche?q=SAP+MM")

print("Extracted Jobs:")
print("=" * 80)
for i, job in enumerate(jobs_de, 1):
    print(f"{i}. {job['full_title']}")
    print(f"   Location: {job['location']}")
    print(f"   URL: {job['url']}")
    print()

print(f"\nTotal: {len(jobs_de)} jobs extracted")

