"""
Fixed Job Board Scrapers
========================
1. Hays - Fixed Playwright EPIPE errors with connection pooling
2. Guru99 Jobs - SAP-specific job board scraper
3. Heidrick & Struggles - Fixed URL to use /en/careers endpoint

For: Pradeep (8-year SAP MM/EWM profile)
"""

import requests
import json
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote
import sys
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

# Use thread-local Playwright connection pool (from daily_scan.py pattern)
import threading
_local_playwright = threading.local()

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

# ============================================================================
# 1. GURU99 JOBS - https://www.guru99.com/sap-jobs.html
# ============================================================================

def search_guru99_sap_jobs():
    """
    Search Guru99 Jobs Board for SAP MM/EWM roles.
    Guru99 is a free SAP training + jobs platform.
    """
    jobs = []
    print("\n🔍 Searching Guru99 Jobs (SAP-specific board)...")
    
    # Guru99 jobs search URLs
    search_urls = [
        ("SAP MM", "https://www.guru99.com/sap-jobs.html?q=SAP+MM"),
        ("SAP EWM", "https://www.guru99.com/sap-jobs.html?q=SAP+EWM"),
        ("Materials Management", "https://www.guru99.com/sap-jobs.html?q=Materials+Management"),
        ("Warehouse Management", "https://www.guru99.com/sap-jobs.html?q=Warehouse+Management"),
        ("S/4HANA", "https://www.guru99.com/sap-jobs.html?q=S/4HANA"),
    ]
    
    for keyword, url in search_urls:
        try:
            print(f"  Fetching: {keyword}")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job listings - Guru99 typically uses job cards or list items
            job_cards = soup.find_all('div', class_=lambda x: x and any(s in str(x).lower() for s in ['job', 'card', 'listing'])) or \
                       soup.find_all('article') or \
                       soup.find_all('li', class_=lambda x: x and 'job' in x.lower())
            
            if not job_cards:
                # Alternative: Look for links to job posts
                job_cards = soup.find_all('a', href=lambda x: x and '/job' in x.lower())
            
            print(f"    Found {len(job_cards)} job elements")
            
            for card in job_cards[:20]:  # Limit per search
                try:
                    # Extract title and link
                    if card.name == 'a':
                        title = card.get_text(strip=True)
                        link = card.get('href', '')
                    else:
                        title_el = card.find('a') or card.find(['h2', 'h3'])
                        title = title_el.get_text(strip=True) if title_el else ""
                        link = title_el.get('href', '') if title_el and title_el.name == 'a' else ""
                    
                    if not title or not link:
                        continue
                    
                    # Make absolute URL
                    if link.startswith('/'):
                        link = f"https://www.guru99.com{link}"
                    elif not link.startswith('http'):
                        continue
                    
                    # Filter for SAP-related
                    if any(kw.lower() in title.lower() for kw in ["sap", "mm", "ewm", "materials", "warehouse", "s/4"]):
                        jobs.append({
                            'title': title,
                            'company': 'Guru99 Jobs',
                            'location': 'Global/Europe',
                            'url': link,
                            'source': 'Guru99 Jobs',
                            'posted_at': None
                        })
                except Exception as e:
                    continue
            
            time.sleep(1)  # Rate limit
            
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            continue
    
    # Deduplicate
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = f"{job['title']}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    
    print(f"  ✅ Found {len(unique_jobs)} Guru99 Jobs listings")
    return unique_jobs


# ============================================================================
# 2. HEIDRICK & STRUGGLES (FIXED) - https://www.heidrick.com/en/careers
# ============================================================================

def search_heidrick_struggles_fixed():
    """
    Search Heidrick & Struggles for SAP/Supply Chain roles.
    Fixed URL: /en/careers endpoint
    """
    jobs = []
    print("\n🔍 Searching Heidrick & Struggles (Fixed URL)...")
    
    # Correct Heidrick & Struggles URL
    base_url = "https://www.heidrick.com/en/careers"
    
    try:
        print(f"  Fetching: {base_url}")
        response = session.get(base_url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all job listings
        job_cards = soup.find_all('div', class_=lambda x: x and any(s in str(x).lower() for s in ['job', 'position', 'vacancy', 'listing'])) or \
                   soup.find_all('article') or \
                   soup.find_all('li')
        
        print(f"    Found {len(job_cards)} job elements")
        
        for card in job_cards[:30]:  # Limit to 30
            try:
                # Extract title
                title_el = card.find(['h2', 'h3', 'a'])
                title = title_el.get_text(strip=True) if title_el else ""
                
                # Extract link
                link_el = card.find('a', href=True)
                link = link_el.get('href', '') if link_el else ""
                
                # Extract location (if available)
                location_el = card.find(class_=lambda x: x and any(s in str(x).lower() for s in ['location', 'place', 'country']))
                location = location_el.get_text(strip=True) if location_el else "Global"
                
                if not title or not link:
                    continue
                
                # Make absolute URL
                if link.startswith('/'):
                    link = f"https://www.heidrick.com{link}"
                elif not link.startswith('http'):
                    continue
                
                # Filter for supply chain/SAP related
                if any(kw.lower() in title.lower() for kw in ["supply", "chain", "sap", "mm", "ewm", "operations", "materials", "warehouse", "procurement"]):
                    jobs.append({
                        'title': title,
                        'company': 'Heidrick & Struggles',
                        'location': location,
                        'url': link,
                        'source': 'Heidrick & Struggles',
                        'posted_at': None
                    })
            except Exception as e:
                continue
        
        time.sleep(2)
        
    except Exception as e:
        print(f"  ⚠️  Error: {e}")
    
    # Deduplicate
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = f"{job['title']}|{job['location']}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    
    print(f"  ✅ Found {len(unique_jobs)} Heidrick & Struggles listings")
    return unique_jobs


# ============================================================================
# 3. HAYS (FIXED) - Connection pooling + browser restart on EPIPE
# ============================================================================

def _get_playwright_browser_safe():
    """
    Get or create Playwright browser with connection pooling.
    Handles EPIPE errors gracefully.
    """
    if not hasattr(_local_playwright, 'browser') or _local_playwright.browser is None:
        try:
            from playwright.sync_api import sync_playwright
            _local_playwright.pw = sync_playwright().start()
            _local_playwright.browser = _local_playwright.pw.chromium.launch(headless=True)
        except Exception as e:
            print(f"  ⚠️  Playwright error: {e}")
            return None
    return _local_playwright.browser


def _get_playwright_page_safe(browser):
    """
    Get a new page with EPIPE error handling.
    """
    try:
        return browser.new_page()
    except Exception as e:
        print(f"  ⚠️  EPIPE or connection error: {e}")
        # Restart browser on EPIPE
        if "EPIPE" in str(e):
            _local_playwright.browser = None
            return _get_playwright_page_safe(_get_playwright_browser_safe())
        return None


def search_hays_fixed():
    """
    Search Hays for SAP MM/EWM roles with fixed Playwright connection pooling.
    """
    jobs = []
    print("\n🔍 Searching Hays (Fixed Playwright)...")
    
    hays_urls = {
        "Germany": "https://www.hays.de/jobsuche?q=SAP+MM",
        "UK": "https://www.hays.co.uk/job-search?q=SAP+MM",
        "Netherlands": "https://www.hays.nl/vacatures?q=SAP+MM",
        "France": "https://www.hays.fr/recherche-emploi?q=SAP+MM",
    }
    
    browser = _get_playwright_browser_safe()
    if not browser:
        print(f"  ⚠️  Could not initialize Playwright browser")
        return jobs
    
    for country, url in hays_urls.items():
        try:
            print(f"  Fetching: Hays {country}")
            
            page = _get_playwright_page_safe(browser)
            if not page:
                continue
            
            try:
                page.goto(url, wait_until='networkidle', timeout=15000)
                page.wait_for_load_state('networkidle')
                
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find job listings
                job_cards = soup.find_all('div', class_=lambda x: x and 'job' in x.lower()) or \
                           soup.find_all('article')
                
                print(f"    Found {len(job_cards)} job cards")
                
                for card in job_cards[:15]:
                    try:
                        title_el = card.find(['h2', 'h3', 'a'])
                        title = title_el.get_text(strip=True) if title_el else ""
                        
                        link_el = card.find('a', href=True)
                        link = link_el.get('href', '') if link_el else ""
                        
                        company_el = card.find(class_=lambda x: x and 'company' in str(x).lower())
                        company = company_el.get_text(strip=True) if company_el else "Unknown"
                        
                        if not title or not link:
                            continue
                        
                        if link.startswith('/'):
                            if 'hays.de' in url:
                                link = f"https://www.hays.de{link}"
                            elif 'hays.co.uk' in url:
                                link = f"https://www.hays.co.uk{link}"
                            elif 'hays.nl' in url:
                                link = f"https://www.hays.nl{link}"
                            else:
                                link = f"https://www.hays.fr{link}"
                        elif not link.startswith('http'):
                            continue
                        
                        if any(kw.lower() in title.lower() for kw in ["sap", "mm", "ewm", "materials", "warehouse"]):
                            jobs.append({
                                'title': title,
                                'company': company,
                                'location': country,
                                'url': link,
                                'source': 'Hays',
                                'posted_at': None
                            })
                    except Exception as e:
                        continue
            finally:
                try:
                    page.close()
                except:
                    pass
            
            time.sleep(2)
            
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            continue
    
    # Deduplicate
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = f"{job['title']}|{job['company']}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    
    print(f"  ✅ Found {len(unique_jobs)} Hays listings")
    return unique_jobs


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("Fixed Job Board Scrapers")
    print("=" * 80)
    print("Searching: Guru99 Jobs, Heidrick & Struggles (Fixed), Hays (Fixed Playwright)")
    
    all_jobs = []
    
    # Run all scrapers
    all_jobs.extend(search_guru99_sap_jobs())
    all_jobs.extend(search_heidrick_struggles_fixed())
    all_jobs.extend(search_hays_fixed())
    
    # Deduplicate
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = f"{job['title']}|{job['company']}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    
    print("\n" + "=" * 80)
    print(f"TOTAL RESULTS: {len(unique_jobs)} unique jobs found")
    print("=" * 80)
    
    # Save results
    output_file = '/Users/kamnee.maran/Downloads/job-search-agent/pradeep_fixed_boards_jobs.json'
    with open(output_file, 'w') as f:
        json.dump(unique_jobs, f, indent=2)
    
    print(f"\n✅ Saved {len(unique_jobs)} jobs to: {output_file}")
    
    # Print summary by source
    print("\n📊 Breakdown by Source:")
    print("-" * 80)
    for source in sorted(set(j['source'] for j in unique_jobs)):
        count = len([j for j in unique_jobs if j['source'] == source])
        print(f"  {source}: {count} jobs")
    
    # Print top 10
    if unique_jobs:
        print("\n🏆 Top 10 Jobs:")
        print("-" * 80)
        for i, job in enumerate(unique_jobs[:10], 1):
            print(f"{i}. {job['title']}")
            print(f"   Company: {job['company']} | Location: {job['location']}")
            print(f"   Source: {job['source']}")
            print(f"   URL: {job['url']}")
            print()


if __name__ == "__main__":
    main()
