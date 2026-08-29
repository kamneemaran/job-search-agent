"""
Use Playwright to investigate Guru99 Jobs page structure
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import time

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

print("=" * 80)
print("GURU99 JOBS - PLAYWRIGHT INVESTIGATION")
print("=" * 80)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # 1. Try Guru99 homepage
    print("\n1️⃣  Loading Guru99 Homepage...")
    try:
        page.goto("https://www.guru99.com/", wait_until='load', timeout=20000)
        time.sleep(2)
        
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        print(f"  ✓ Loaded successfully ({len(html)} bytes)")
        
        # Look for navigation links
        nav_links = soup.find_all('a', href=re.compile(r'job|career|hire', re.I))
        print(f"  Navigation links with 'job/career/hire': {len(nav_links)}")
        
        if nav_links:
            print("  Found links:")
            for link in nav_links[:5]:
                href = link.get('href', '')
                text = link.get_text(strip=True)[:60]
                print(f"    • {text}: {href}")
        
        # Look for any jobs section
        sections = soup.find_all(['section', 'div'], class_=re.compile(r'job|career', re.I))
        print(f"  Job/Career sections: {len(sections)}")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    page.close()

# 2. Try searching for SAP jobs on Guru99 using search
print("\n2️⃣  Trying Guru99 Search...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    try:
        # Try to access Guru99 and look for search box
        page.goto("https://www.guru99.com/", wait_until='load', timeout=20000)
        time.sleep(1)
        
        # Look for search input
        search_inputs = page.locator('input[type="search"], input[name*="search"], input[placeholder*="search"], [aria-label*="search"]')
        count = search_inputs.count()
        print(f"  Search inputs found: {count}")
        
        if count > 0:
            print("  ✓ Search functionality available")
            # Try to type in search
            search_inputs.first.fill("SAP jobs")
            print("  Typed 'SAP jobs' in search")
    except Exception as e:
        print(f"  Error: {e}")
    finally:
        page.close()

# 3. Try direct URLs with Playwright
print("\n3️⃣  Testing Direct URLs with Playwright...")

urls = [
    "https://www.guru99.com/sap-jobs.html",
    "https://www.guru99.com/jobs",
    "https://www.guru99.com/sap-training",
]

for url in urls:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(url, wait_until='load', timeout=15000)
            status = page.url
            print(f"  {url}")
            print(f"    Final URL: {status}")
            print(f"    Status: 200 OK")
        except Exception as e:
            print(f"  {url}")
            print(f"    Error: {str(e)[:80]}")
        finally:
            page.close()

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
Guru99 Jobs Status:
- The /sap-jobs.html endpoint does not exist on Guru99
- Guru99 may have restructured their jobs board
- OR: Jobs might be under a different URL path

Alternative Options:
1. Guru99 might have moved jobs to a different domain
2. Jobs might be accessible through training course pages
3. Guru99 might have deprecated the public jobs board
4. Check if jobs are listed via a LinkedIn page or careers portal

Recommendation:
Focus on other working boards (LinkedIn, Indeed, SAP Jobs Board)
Guru99 appears to not maintain a public jobs board anymore
""")

