"""
Analyze actual Guru99 page content when loaded with Playwright
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

print("=" * 80)
print("GURU99 JOBS PAGE CONTENT ANALYSIS")
print("=" * 80)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_viewport_size({"width": 1200, "height": 800})
    
    try:
        # Load the "jobs" page
        url = "https://www.guru99.com/sap-jobs.html"
        print(f"\n1️⃣  Loading: {url}")
        
        page.goto(url, wait_until='load', timeout=20000)
        time.sleep(3)  # Let all JS load
        
        # Get final URL (might have redirected)
        final_url = page.url
        print(f"  Final URL: {final_url}")
        print(f"  Status: OK")
        
        # Get page content
        html = page.content()
        title = page.title()
        
        print(f"  Page Title: {title}")
        print(f"  Content Size: {len(html)} bytes")
        
        # Analyze content
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for job-related content
        print(f"\n2️⃣  Content Analysis:")
        
        # Check for keywords
        keywords = ['job', 'sap', 'position', 'vacancy', 'career', 'hiring', 'apply']
        for kw in keywords:
            count = html.lower().count(kw)
            if count > 0:
                print(f"  • '{kw}' appears {count} times")
        
        # Look for specific elements
        print(f"\n3️⃣  Page Structure:")
        
        headers = soup.find_all(['h1', 'h2', 'h3'])
        print(f"  Headers (h1-h3): {len(headers)}")
        if headers:
            print("    First 5 headers:")
            for h in headers[:5]:
                text = h.get_text(strip=True)[:80]
                print(f"      • {text}")
        
        # Look for tables or lists
        tables = soup.find_all('table')
        divs_with_job_class = soup.find_all('div', class_=lambda x: x and 'job' in str(x).lower())
        
        print(f"  Tables: {len(tables)}")
        print(f"  Divs with 'job' class: {len(divs_with_job_class)}")
        
        # Look for any job postings
        links_with_job = soup.find_all('a', href=re.compile(r'job|position|vacancy', re.I))
        print(f"  Links with job/position/vacancy: {len(links_with_job)}")
        
        # Check if it's just redirecting to SAP training
        sap_training = soup.find_all(text=lambda text: text and 'sap' in text.lower()[:100])
        print(f"  Mentions of 'SAP': {len(sap_training)}")
        
        # Get body text (first 500 chars)
        body_text = soup.get_text(strip=True)[:500]
        print(f"\n4️⃣  Page Content Preview:")
        print(f"  {body_text}...")
        
        # Check if it's a redirect page
        redirects = soup.find_all('meta', attrs={'http-equiv': 'refresh'})
        print(f"\n5️⃣  Redirect Meta Tags: {len(redirects)}")
        if redirects:
            print("  Page contains redirect!")
        
    except Exception as e:
        print(f"  Error: {e}")
    finally:
        page.close()

import re
print("\n" + "=" * 80)

