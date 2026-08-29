"""
Extract actual job data from Hays Germany page
"""

import sys
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import random
import time

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

url = "https://www.hays.de/jobsuche?q=SAP+MM"

print(f"Extracting jobs from: {url}\n")

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
        
        # Look for common job listing patterns
        print("Strategy 1: Looking for links with job titles/URLs...\n")
        
        # Find all links that might be job posts
        all_links = soup.find_all('a', href=True)
        
        # Filter for job-like links (contains /job or similar patterns)
        job_links = []
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Look for SAP-related job links
            if any(pattern in href.lower() for pattern in ['/job', '/stelle', '/position']) or \
               any(kw in text.lower() for kw in ['sap', 'mm', 'ewm', 'materials', 'warehouse']):
                if len(text) > 10 and len(text) < 300:  # Reasonable title length
                    job_links.append({'title': text, 'url': href})
        
        # Filter unique by title
        seen_titles = set()
        unique_jobs = []
        for job in job_links:
            if job['title'] not in seen_titles and 'sap' in job['title'].lower():
                seen_titles.add(job['title'])
                unique_jobs.append(job)
        
        print(f"Found {len(unique_jobs)} SAP-related job links\n")
        
        if unique_jobs:
            print("First 20 jobs:")
            for i, job in enumerate(unique_jobs[:20], 1):
                print(f"{i}. {job['title']}")
                print(f"   URL: {job['url'][:100]}")
                print()
        else:
            print("No SAP jobs found via link extraction")
            print(f"\nTotal links found: {len(all_links)}")
            print("\nSample links containing 'sap' (case-insensitive):")
            sap_links = [l for l in all_links if 'sap' in str(l).lower()][:5]
            for link in sap_links:
                print(f"  {str(link)[:200]}")
        
        # Strategy 2: Look for data attributes or structured data
        print("\n" + "=" * 80)
        print("Strategy 2: Looking for structured data (JSON-LD, data attributes)...\n")
        
        # Find script tags with structured data
        scripts = soup.find_all('script', type='application/ld+json')
        print(f"JSON-LD scripts found: {len(scripts)}")
        
        # Find tags with data-* attributes
        data_attrs = soup.find_all(attrs={'data-job-title': True})
        print(f"Elements with data-job-title: {len(data_attrs)}")
        
        data_attrs = soup.find_all(attrs={'data-title': True})
        print(f"Elements with data-title: {len(data_attrs)}")
        
    finally:
        page.close()
        browser.close()

