"""
Recruitment Agency Job Board Scrapers
=====================================
Search for SAP MM/EWM jobs on recruitment agency sites:
1. Robert Walters - https://www.robertwalters.com/
2. Hudson - https://www.hudson.com/
3. Heidrick & Struggles - https://www.heidrick.com/

For: Pradeep (8-year SAP MM/EWM profile)
"""

import requests
import json
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

# ============================================================================
# 1. ROBERT WALTERS - https://www.robertwalters.com/
# ============================================================================

def search_robert_walters():
    """
    Search Robert Walters for SAP MM/EWM roles.
    Focuses on technology/consulting recruitment.
    """
    jobs = []
    print("\n🔍 Searching Robert Walters...")
    
    # Robert Walters search URLs by location
    search_urls = [
        ("Germany", "https://www.robertwalters.de/jobs?keywords=SAP+MM"),
        ("Germany", "https://www.robertwalters.de/jobs?keywords=SAP+EWM"),
        ("UK", "https://www.robertwalters.com/jobs?keywords=SAP+MM"),
        ("UK", "https://www.robertwalters.com/jobs?keywords=SAP+EWM"),
        ("Netherlands", "https://www.robertwalters.nl/jobs?keywords=SAP+MM"),
        ("France", "https://www.robertwalters.fr/jobs?keywords=SAP+MM"),
    ]
    
    for location, url in search_urls:
        try:
            print(f"  Fetching: Robert Walters {location}")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job listings
            job_cards = soup.find_all('div', class_=lambda x: x and 'job' in x.lower()) or \
                       soup.find_all('article') or \
                       soup.find_all('div', class_=lambda x: x and 'vacancy' in x.lower())
            
            print(f"    Found {len(job_cards)} job elements")
            
            for card in job_cards[:20]:  # Limit to 20 per search
                try:
                    # Extract title
                    title_el = card.find(['h2', 'h3', 'a'], class_=lambda x: x and any(s in str(x).lower() for s in ['title', 'job']))
                    if not title_el:
                        title_el = card.find('a')
                    title = title_el.get_text(strip=True) if title_el else ""
                    
                    # Extract link
                    link_el = card.find('a', href=True)
                    link = link_el.get('href', '') if link_el else ""
                    
                    # Extract company
                    company_el = card.find(class_=lambda x: x and 'company' in x.lower())
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    
                    if not title or not link:
                        continue
                    
                    # Make absolute URL
                    if link.startswith('/'):
                        if 'robertwalters.de' in url:
                            link = f"https://www.robertwalters.de{link}"
                        elif 'robertwalters.nl' in url:
                            link = f"https://www.robertwalters.nl{link}"
                        elif 'robertwalters.fr' in url:
                            link = f"https://www.robertwalters.fr{link}"
                        else:
                            link = f"https://www.robertwalters.com{link}"
                    elif not link.startswith('http'):
                        continue
                    
                    # Filter for SAP-related
                    if any(kw.lower() in title.lower() for kw in ["sap", "mm", "ewm", "materials", "warehouse"]):
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': location,
                            'url': link,
                            'source': 'Robert Walters',
                            'posted_at': None
                        })
                except Exception as e:
                    continue
            
            time.sleep(2)  # Rate limit
            
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
    
    print(f"  ✅ Found {len(unique_jobs)} Robert Walters listings")
    return unique_jobs


# ============================================================================
# 2. HUDSON - https://www.hudson.com/
# ============================================================================

def search_hudson():
    """
    Search Hudson for SAP MM/EWM roles.
    Global recruitment agency with strong SAP practice.
    """
    jobs = []
    print("\n🔍 Searching Hudson...")
    
    # Hudson search URLs by location
    search_urls = [
        ("Germany", "https://www.hudson.com/de/jobs?keywords=SAP+MM"),
        ("Germany", "https://www.hudson.com/de/jobs?keywords=SAP+EWM"),
        ("UK", "https://www.hudson.com/en-gb/jobs?keywords=SAP+MM"),
        ("UK", "https://www.hudson.com/en-gb/jobs?keywords=SAP+EWM"),
        ("Netherlands", "https://www.hudson.com/nl/jobs?keywords=SAP+MM"),
        ("France", "https://www.hudson.com/fr/jobs?keywords=SAP+MM"),
    ]
    
    for location, url in search_urls:
        try:
            print(f"  Fetching: Hudson {location}")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job listings
            job_cards = soup.find_all('div', class_=lambda x: x and 'job' in x.lower()) or \
                       soup.find_all('article') or \
                       soup.find_all('li', class_=lambda x: x and any(s in str(x).lower() for s in ['result', 'card']))
            
            print(f"    Found {len(job_cards)} job elements")
            
            for card in job_cards[:20]:  # Limit to 20 per search
                try:
                    # Extract title
                    title_el = card.find(['h2', 'h3', 'a'])
                    title = title_el.get_text(strip=True) if title_el else ""
                    
                    # Extract link
                    link_el = card.find('a', href=True)
                    link = link_el.get('href', '') if link_el else ""
                    
                    # Extract company
                    company_el = card.find(class_=lambda x: x and any(s in str(x).lower() for s in ['company', 'employer', 'client']))
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    
                    if not title or not link:
                        continue
                    
                    # Make absolute URL
                    if link.startswith('/'):
                        if 'hudson.com/de' in url:
                            link = f"https://www.hudson.com/de{link}"
                        elif 'hudson.com/nl' in url:
                            link = f"https://www.hudson.com/nl{link}"
                        elif 'hudson.com/fr' in url:
                            link = f"https://www.hudson.com/fr{link}"
                        else:
                            link = f"https://www.hudson.com/en-gb{link}"
                    elif not link.startswith('http'):
                        continue
                    
                    # Filter for SAP-related
                    if any(kw.lower() in title.lower() for kw in ["sap", "mm", "ewm", "materials", "warehouse"]):
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': location,
                            'url': link,
                            'source': 'Hudson',
                            'posted_at': None
                        })
                except Exception as e:
                    continue
            
            time.sleep(2)  # Rate limit
            
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
    
    print(f"  ✅ Found {len(unique_jobs)} Hudson listings")
    return unique_jobs


# ============================================================================
# 3. HEIDRICK & STRUGGLES - https://www.heidrick.com/
# ============================================================================

def search_heidrick_struggles():
    """
    Search Heidrick & Struggles for SAP MM/EWM roles.
    Premium executive search firm, focus on senior roles.
    """
    jobs = []
    print("\n🔍 Searching Heidrick & Struggles...")
    
    # Heidrick & Struggles search URL (global)
    search_urls = [
        ("Europe", "https://www.heidrick.com/en/open-positions?search=SAP+MM"),
        ("Europe", "https://www.heidrick.com/en/open-positions?search=SAP+EWM"),
        ("Europe", "https://www.heidrick.com/en/open-positions?search=Materials+Management"),
    ]
    
    for location, url in search_urls:
        try:
            print(f"  Fetching: Heidrick & Struggles {location}")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job listings
            job_cards = soup.find_all('div', class_=lambda x: x and any(s in str(x).lower() for s in ['job', 'position', 'vacancy'])) or \
                       soup.find_all('article') or \
                       soup.find_all('li')
            
            print(f"    Found {len(job_cards)} job elements")
            
            for card in job_cards[:20]:  # Limit to 20 per search
                try:
                    # Extract title
                    title_el = card.find(['h2', 'h3', 'a'])
                    title = title_el.get_text(strip=True) if title_el else ""
                    
                    # Extract link
                    link_el = card.find('a', href=True)
                    link = link_el.get('href', '') if link_el else ""
                    
                    # Extract location from card
                    location_el = card.find(class_=lambda x: x and any(s in str(x).lower() for s in ['location', 'place', 'country']))
                    job_location = location_el.get_text(strip=True) if location_el else "Europe"
                    
                    if not title or not link:
                        continue
                    
                    # Make absolute URL
                    if link.startswith('/'):
                        link = f"https://www.heidrick.com{link}"
                    elif not link.startswith('http'):
                        continue
                    
                    # Filter for SAP-related
                    if any(kw.lower() in title.lower() for kw in ["sap", "mm", "ewm", "materials", "warehouse", "supply", "chain"]):
                        jobs.append({
                            'title': title,
                            'company': 'Heidrick & Struggles (Client Company)',
                            'location': job_location,
                            'url': link,
                            'source': 'Heidrick & Struggles',
                            'posted_at': None
                        })
                except Exception as e:
                    continue
            
            time.sleep(2)  # Rate limit
            
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
    
    print(f"  ✅ Found {len(unique_jobs)} Heidrick & Struggles listings")
    return unique_jobs


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("=" * 80)
    print("Recruitment Agency SAP Job Search")
    print("=" * 80)
    print("Searching: Robert Walters, Hudson, Heidrick & Struggles")
    
    all_jobs = []
    
    # Run all scrapers
    all_jobs.extend(search_robert_walters())
    all_jobs.extend(search_hudson())
    all_jobs.extend(search_heidrick_struggles())
    
    # Deduplicate across all sources
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = f"{job['title']}|{job['company']}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    
    print("\n" + "=" * 80)
    print(f"TOTAL RESULTS: {len(unique_jobs)} unique recruitment agency SAP listings found")
    print("=" * 80)
    
    # Save to file
    output_file = "/Users/kamnee.maran/Downloads/job-search-agent/pradeep_recruitment_agencies_sap_jobs.json"
    with open(output_file, 'w') as f:
        json.dump(unique_jobs, f, indent=2)
    
    print(f"\n✅ Saved {len(unique_jobs)} jobs to: {output_file}")
    
    # Print summary by source
    print("\n📊 Breakdown by Source:")
    print("-" * 80)
    for source in sorted(set(j['source'] for j in unique_jobs)):
        count = len([j for j in unique_jobs if j['source'] == source])
        print(f"  {source}: {count} jobs")
    
    # Print top 15 jobs
    if unique_jobs:
        print("\n🏆 Top 15 Jobs:")
        print("-" * 80)
        for i, job in enumerate(unique_jobs[:15], 1):
            print(f"{i}. {job['title']}")
            print(f"   Company: {job['company']} | Location: {job['location']}")
            print(f"   Source: {job['source']}")
            print(f"   URL: {job['url']}")
            print()
    else:
        print("\n⚠️  No jobs found from recruitment agencies")


if __name__ == "__main__":
    main()
