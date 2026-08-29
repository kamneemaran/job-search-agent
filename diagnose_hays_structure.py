"""
Diagnose Hays page structure to understand why SAP jobs aren't being extracted
"""

import sys
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

from playwright.sync_api import sync_playwright
import random
import time

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

url = "https://www.hays.de/jobsuche?q=SAP+MM"

print(f"Diagnosing Hays structure: {url}\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    ua = random.choice(USER_AGENTS)
    page.set_extra_http_headers({
        'User-Agent': ua,
        'Accept-Language': 'en-US,en;q=0.9',
    })
    
    try:
        page.goto(url, wait_until='load', timeout=20000)
        time.sleep(2)
        
        html = page.content()
        
        print(f"Page size: {len(html)} bytes")
        print(f"\nSearching for keywords...")
        
        # Look for common job board patterns
        patterns = {
            "SAP MM": "SAP" in html and "MM" in html,
            "job cards": 'class="job' in html or 'class=\'job' in html,
            "job-item": 'job-item' in html,
            "vacancy": 'vacancy' in html.lower(),
            "position": 'position' in html.lower(),
            "h2": '<h2' in html,
            "h3": '<h3' in html,
            "data attributes": 'data-' in html,
        }
        
        for pattern, found in patterns.items():
            status = "✓" if found else "✗"
            print(f"  {status} {pattern}")
        
        # Extract all classes used
        import re
        classes = set(re.findall(r'class=["\']([^"\']+)["\']', html))
        print(f"\nUnique CSS classes found ({len(classes)}):")
        for cls in sorted(classes)[:30]:
            print(f"  • {cls}")
        
        # Look for text content
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all links
        links = soup.find_all('a')
        print(f"\nTotal links found: {len(links)}")
        
        # Find job-related links
        job_links = [l for l in links if any(kw in l.get_text(strip=True).lower() or kw in str(l.get('href', '')).lower() for kw in ['sap', 'mm', 'ewm', 'job', 'position'])]
        print(f"Job-related links: {len(job_links)}")
        
        if job_links:
            print("\nFirst 10 job-related links:")
            for i, link in enumerate(job_links[:10], 1):
                title = link.get_text(strip=True)[:80]
                href = link.get('href', '')[:80]
                print(f"  {i}. Title: {title}")
                print(f"     URL: {href}")
        
        # Check specific structure for job cards
        print("\n" + "=" * 80)
        print("Looking for job card container structure...")
        print("=" * 80)
        
        # Look for divs that might be job cards
        all_divs = soup.find_all('div', class_=lambda x: x and any(s in str(x).lower() for s in ['card', 'item', 'result', 'job']))
        print(f"Divs with card/item/result/job classes: {len(all_divs)}")
        
        if all_divs:
            print("\nFirst container (first 200 chars):")
            print(str(all_divs[0])[:200])
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        page.close()
        browser.close()

