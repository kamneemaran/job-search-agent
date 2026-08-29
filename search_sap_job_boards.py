"""
SAP Job Board Scrapers - Non-LinkedIn
======================================
Search for SAP MM/EWM jobs across:
1. SAP Jobs Board (Official) - https://jobs.sap.com/
2. Stepstone (Germany/UK) - https://www.stepstone.de/
3. Indeed (DE/UK/NL) - https://indeed.com/
4. Dice - https://dice.com/
5. eJob.de - https://www.e-job.de/

For: Pradeep (8-year SAP MM profile)
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
# 1. SAP JOBS BOARD - https://jobs.sap.com/
# ============================================================================

def search_sap_jobs_board():
    """
    Search SAP's official jobs board for MM/EWM roles.
    Uses API endpoint for structured data.
    """
    jobs = []
    print("\n🔍 Searching SAP Jobs Board (Official)...")
    
    keywords = ["SAP MM", "Materials Management", "SAP EWM", "Warehouse Management", "S/4HANA"]
    locations = ["Germany", "United Kingdom", "France", "Netherlands", "Belgium", "Europe"]
    
    for keyword in keywords:
        for location in locations:
            try:
                # SAP Jobs Board search URL
                search_url = f"https://jobs.sap.com/search/?q={quote(keyword)}&l={quote(location)}"
                print(f"  Fetching: {keyword} in {location}")
                
                response = session.get(search_url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try to find job listings
                job_cards = soup.find_all('div', class_=lambda x: x and 'job' in x.lower())
                
                if not job_cards:
                    # Alternative: look for links to job postings
                    job_links = soup.find_all('a', href=lambda x: x and '/job/' in x.lower())
                    job_cards = job_links
                
                for card in job_cards[:10]:  # Limit per search
                    try:
                        if isinstance(card, str):
                            continue
                        
                        # Extract title and link
                        if card.name == 'a':
                            title = card.get_text(strip=True)
                            link = card.get('href', '')
                        else:
                            title_el = card.find(['h2', 'h3', 'a'])
                            title = title_el.get_text(strip=True) if title_el else ""
                            link = title_el.get('href', '') if title_el and title_el.name == 'a' else ""
                        
                        if not title or not link:
                            continue
                        
                        # Make absolute URL
                        if link.startswith('/'):
                            link = f"https://jobs.sap.com{link}"
                        elif not link.startswith('http'):
                            continue
                        
                        # Filter for SAP-related
                        if any(kw.lower() in title.lower() for kw in ["sap", "mm", "ewm", "materials", "warehouse", "s/4"]):
                            jobs.append({
                                'title': title,
                                'company': 'SAP SE',
                                'location': location,
                                'url': link,
                                'source': 'SAP Jobs Board',
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
        key = f"{job['title']}|{job['company']}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    
    print(f"  ✅ Found {len(unique_jobs)} SAP Jobs Board listings")
    return unique_jobs


# ============================================================================
# 2. STEPSTONE - https://www.stepstone.de/ (Germany/UK)
# ============================================================================

def search_stepstone():
    """
    Search Stepstone for SAP MM/EWM roles (Germany & UK).
    """
    jobs = []
    print("\n🔍 Searching Stepstone (Germany/UK)...")
    
    search_urls = [
        ("Germany", "https://www.stepstone.de/stellenangebote--SAP-MM.html"),
        ("Germany", "https://www.stepstone.de/stellenangebote--SAP-EWM.html"),
        ("UK", "https://www.stepstone.co.uk/jobs/sap/"),
        ("UK", "https://www.stepstone.co.uk/jobs/materials-management/"),
    ]
    
    for location, url in search_urls:
        try:
            print(f"  Fetching: Stepstone {location}")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job listings
            job_elements = soup.find_all('article', class_=lambda x: x and 'job' in x.lower()) or \
                           soup.find_all('div', class_=lambda x: x and 'jobitem' in x.lower()) or \
                           soup.find_all('li', class_=lambda x: x and 'job' in x.lower())
            
            print(f"    Found {len(job_elements)} job elements")
            
            for elem in job_elements[:15]:
                try:
                    # Extract title
                    title_el = elem.find(['h2', 'h3', 'a'], class_=lambda x: x and any(s in str(x).lower() for s in ['title', 'heading', 'job'])) or \
                              elem.find('a')
                    title = title_el.get_text(strip=True) if title_el else ""
                    
                    # Extract link
                    link_el = elem.find('a', href=True)
                    link = link_el.get('href', '') if link_el else ""
                    
                    # Extract company
                    company_el = elem.find(class_=lambda x: x and any(s in str(x).lower() for s in ['company', 'employer']))
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    
                    if not title or not link:
                        continue
                    
                    # Make absolute URL
                    if link.startswith('/'):
                        if 'stepstone.de' in url:
                            link = f"https://www.stepstone.de{link}"
                        else:
                            link = f"https://www.stepstone.co.uk{link}"
                    elif not link.startswith('http'):
                        continue
                    
                    # Filter for SAP-related
                    if any(kw.lower() in title.lower() for kw in ["sap", "mm", "ewm", "materials", "warehouse"]):
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': location,
                            'url': link,
                            'source': 'Stepstone',
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
        key = f"{job['title']}|{job['location']}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    
    print(f"  ✅ Found {len(unique_jobs)} Stepstone listings")
    return unique_jobs


# ============================================================================
# 3. INDEED - https://indeed.de/, indeed.co.uk, indeed.nl
# ============================================================================

def search_indeed():
    """
    Search Indeed for SAP MM/EWM roles across Europe.
    """
    jobs = []
    print("\n🔍 Searching Indeed (DE/UK/NL)...")
    
    search_urls = [
        ("Germany", "https://de.indeed.com/jobs?q=SAP+MM&l=Deutschland"),
        ("Germany", "https://de.indeed.com/jobs?q=SAP+EWM&l=Deutschland"),
        ("UK", "https://www.indeed.co.uk/jobs?q=SAP+MM"),
        ("UK", "https://www.indeed.co.uk/jobs?q=SAP+EWM"),
        ("Netherlands", "https://nl.indeed.com/jobs?q=SAP+MM"),
        ("Netherlands", "https://nl.indeed.com/jobs?q=SAP+EWM"),
    ]
    
    for location, url in search_urls:
        try:
            print(f"  Fetching: Indeed {location}")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job listings (Indeed structure)
            job_cards = soup.find_all('div', {'data-job-id': True}) or \
                       soup.find_all('div', class_=lambda x: x and 'job' in x.lower() and 'card' in x.lower()) or \
                       soup.find_all('div', id=lambda x: x and x.startswith('p_'))
            
            print(f"    Found {len(job_cards)} job cards")
            
            for card in job_cards[:15]:
                try:
                    # Extract title
                    title_el = card.find('h2') or card.find('a', class_=lambda x: x and 'job' in x.lower())
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
                        if 'de.indeed.com' in url:
                            link = f"https://de.indeed.com{link}"
                        elif 'nl.indeed.com' in url:
                            link = f"https://nl.indeed.com{link}"
                        else:
                            link = f"https://www.indeed.co.uk{link}"
                    elif not link.startswith('http'):
                        continue
                    
                    # Filter for SAP-related
                    if any(kw.lower() in title.lower() for kw in ["sap", "mm", "ewm"]):
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': location,
                            'url': link,
                            'source': 'Indeed',
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
    
    print(f"  ✅ Found {len(unique_jobs)} Indeed listings")
    return unique_jobs


# ============================================================================
# 4. DICE - https://dice.com/ (Tech-focused)
# ============================================================================

def search_dice():
    """
    Search Dice for SAP MM/EWM technical roles.
    """
    jobs = []
    print("\n🔍 Searching Dice (Tech SAP roles)...")
    
    keywords = ["SAP MM", "SAP EWM", "SAP ABAP", "SAP Fiori"]
    
    for keyword in keywords:
        try:
            url = f"https://www.dice.com/jobs?q={quote(keyword)}&country=de"
            print(f"  Fetching: Dice - {keyword}")
            
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job listings
            job_cards = soup.find_all('div', class_=lambda x: x and 'card' in x.lower()) or \
                       soup.find_all('article') or \
                       soup.find_all('div', {'data-testid': lambda x: x and 'job' in x.lower()})
            
            print(f"    Found {len(job_cards)} job cards")
            
            for card in job_cards[:10]:
                try:
                    # Extract title and link
                    title_el = card.find('a')
                    title = title_el.get_text(strip=True) if title_el else ""
                    link = title_el.get('href', '') if title_el else ""
                    
                    # Extract company
                    company_el = card.find(class_=lambda x: x and any(s in str(x).lower() for s in ['company', 'employer']))
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    
                    if not title or not link:
                        continue
                    
                    # Make absolute URL
                    if link.startswith('/'):
                        link = f"https://www.dice.com{link}"
                    elif not link.startswith('http'):
                        continue
                    
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': 'Europe',
                        'url': link,
                        'source': 'Dice',
                        'posted_at': None
                    })
                except Exception as e:
                    continue
            
            time.sleep(1)
            
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
    
    print(f"  ✅ Found {len(unique_jobs)} Dice listings")
    return unique_jobs


# ============================================================================
# 5. eJOB.DE - https://www.e-job.de/ (Germany SAP-focused)
# ============================================================================

def search_ejob_de():
    """
    Search eJob.de for SAP roles (Germany focus).
    """
    jobs = []
    print("\n🔍 Searching eJob.de (Germany SAP)...")
    
    keywords = ["SAP MM", "SAP EWM", "SAP S/4HANA"]
    
    for keyword in keywords:
        try:
            url = f"https://www.e-job.de/stellenangebote/{quote(keyword)}"
            print(f"  Fetching: eJob.de - {keyword}")
            
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job listings
            job_elements = soup.find_all('div', class_=lambda x: x and 'job' in x.lower()) or \
                          soup.find_all('article')
            
            print(f"    Found {len(job_elements)} job elements")
            
            for elem in job_elements[:10]:
                try:
                    # Extract title
                    title_el = elem.find(['h2', 'h3', 'a'])
                    title = title_el.get_text(strip=True) if title_el else ""
                    
                    # Extract link
                    link_el = elem.find('a', href=True)
                    link = link_el.get('href', '') if link_el else ""
                    
                    # Extract company
                    company_el = elem.find(class_=lambda x: x and 'company' in x.lower())
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    
                    if not title or not link:
                        continue
                    
                    # Make absolute URL
                    if link.startswith('/'):
                        link = f"https://www.e-job.de{link}"
                    elif not link.startswith('http'):
                        continue
                    
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': 'Germany',
                        'url': link,
                        'source': 'eJob.de',
                        'posted_at': None
                    })
                except Exception as e:
                    continue
            
            time.sleep(1)
            
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
    
    print(f"  ✅ Found {len(unique_jobs)} eJob.de listings")
    return unique_jobs


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("=" * 80)
    print("SAP Job Board Search (Non-LinkedIn)")
    print("=" * 80)
    print("Searching: SAP Jobs Board, Stepstone, Indeed, Dice, eJob.de")
    
    all_jobs = []
    
    # Run all scrapers
    all_jobs.extend(search_sap_jobs_board())
    all_jobs.extend(search_stepstone())
    all_jobs.extend(search_indeed())
    all_jobs.extend(search_dice())
    all_jobs.extend(search_ejob_de())
    
    # Deduplicate across all sources
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = f"{job['title']}|{job['company']}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    
    print("\n" + "=" * 80)
    print(f"TOTAL RESULTS: {len(unique_jobs)} unique SAP job listings found")
    print("=" * 80)
    
    # Save to file
    output_file = "/Users/kamnee.maran/Downloads/job-search-agent/pradeep_sap_job_boards.json"
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
    print("\n🏆 Top 15 Jobs:")
    print("-" * 80)
    for i, job in enumerate(unique_jobs[:15], 1):
        print(f"{i}. {job['title']}")
        print(f"   Company: {job['company']} | Location: {job['location']}")
        print(f"   Source: {job['source']}")
        print(f"   URL: {job['url']}")
        print()


if __name__ == "__main__":
    main()
