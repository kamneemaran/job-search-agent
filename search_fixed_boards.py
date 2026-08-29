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
import random
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote
import sys
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

# Use thread-local Playwright connection pool (from daily_scan.py pattern)
import threading
_local_playwright = threading.local()

# Rotating User-Agents to bypass bot detection
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

def get_rotating_session():
    """Create a new session with random User-Agent"""
    session = requests.Session()
    ua = random.choice(USER_AGENTS)
    session.headers.update({
        'User-Agent': ua,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    return session

# Default session
session = get_rotating_session()

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


def search_hays_with_rotating_headers():
    """
    Search Hays for SAP MM/EWM roles with rotating User-Agent headers.
    Strategy: Extract jobs from URL patterns + rotating headers to bypass bot detection.
    """
    jobs = []
    print("\n🔍 Searching Hays (Rotating User-Agents + URL pattern extraction)...")
    
    hays_urls = {
        "Germany": ["https://www.hays.de/jobsuche?q=SAP+MM", "https://www.hays.de/jobsuche?q=SAP+EWM"],
        "UK": ["https://www.hays.co.uk/job-search?q=SAP+MM"],
        "Netherlands": ["https://www.hays.nl/vacatures?q=SAP+MM"],
        "France": ["https://www.hays.fr/recherche-emploi?q=SAP+MM"],
        "Belgium": ["https://www.hays.be/vacatures?q=SAP+MM"],
    }
    
    browser = _get_playwright_browser_safe()
    if not browser:
        print(f"  ⚠️  Could not initialize Playwright browser")
        return jobs
    
    for country, url_list in hays_urls.items():
        try:
            print(f"  Fetching: Hays {country}")
            
            for search_url in url_list:
                page = _get_playwright_page_safe(browser)
                if not page:
                    continue
                
                try:
                    # Set rotating User-Agent
                    ua = random.choice(USER_AGENTS)
                    page.set_extra_http_headers({
                        'User-Agent': ua,
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://www.google.com/',
                    })
                    
                    # Use 'load' for faster loading
                    try:
                        page.goto(search_url, wait_until='load', timeout=20000)
                        time.sleep(1)
                    except:
                        try:
                            page.goto(search_url, wait_until='networkidle', timeout=25000)
                        except:
                            continue
                    
                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Check page loaded
                    if len(html) < 5000:
                        continue
                    
                    # Look for job detail links using URL pattern
                    # Pattern varies by country, but generally contains job ID
                    detail_links = soup.find_all('a', href=re.compile(r'/(jobsuche|job-search|vacatures|recherche-emploi|vacaturehays)/.*-\d+'))
                    
                    for link in detail_links[:30]:  # Extract up to 30 per search
                        try:
                            href = link.get('href', '')
                            
                            # Make absolute URL
                            if href.startswith('/'):
                                if 'hays.de' in search_url:
                                    href = f"https://www.hays.de{href}"
                                elif 'hays.co.uk' in search_url:
                                    href = f"https://www.hays.co.uk{href}"
                                elif 'hays.nl' in search_url:
                                    href = f"https://www.hays.nl{href}"
                                elif 'hays.be' in search_url:
                                    href = f"https://www.hays.be{href}"
                                else:
                                    href = f"https://www.hays.fr{href}"
                            elif not href.startswith('http'):
                                continue
                            
                            # Extract title from URL slug
                            match = re.search(r'-(detail|job)[-/](.+?)-(\d+)[/?]', href)
                            if not match:
                                match = re.search(r'/([^/]+)-(\d+)[/?]$', href)
                            
                            if match:
                                title_slug = match.group(2) if match.lastindex >= 2 else match.group(1)
                                title = title_slug.replace('-', ' ').title()
                                
                                # Check if SAP-related
                                if any(kw.lower() in title_slug.lower() for kw in ['sap', 'mm', 'ewm', 'supply', 'materials', 'warehouse']):
                                    jobs.append({
                                        'title': title,
                                        'company': 'Hays',
                                        'location': country,
                                        'url': href,
                                        'source': 'Hays',
                                        'posted_at': None
                                    })
                        except:
                            continue
                    
                finally:
                    try:
                        page.close()
                    except:
                        pass
                
                time.sleep(random.uniform(1, 2))
            
        except Exception as e:
            print(f"  ⚠️  Error on {country}: {str(e)[:100]}")
            continue
    
    # Deduplicate
    seen = set()
    unique_jobs = []
    for job in jobs:
        key = f"{job['title']}|{job['url']}"
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
    print("Fixed Job Board Scrapers - Enhanced")
    print("=" * 80)
    print("Searching: Guru99 Jobs, Heidrick & Struggles (Fixed), Hays (Rotating Headers)")
    print("Enhancements:")
    print("  • Hays: Rotating User-Agent headers + 'load' wait strategy")
    print("  • All: Added random delays to avoid bot detection")
    print("=" * 80)
    
    all_jobs = []
    
    # Run all scrapers
    all_jobs.extend(search_guru99_sap_jobs())
    all_jobs.extend(search_heidrick_struggles_fixed())
    all_jobs.extend(search_hays_with_rotating_headers())
    
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
