"""
Search for SAP MM jobs on Hays and Michael Page using simple requests
(avoiding Playwright issues)
"""

import json
import requests
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
import sys
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

# Set up session
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})

def search_hays_simple():
    """Search Hays for SAP MM jobs using direct URL."""
    jobs = []
    seen = set()
    
    # Hays search URLs for SAP MM
    search_urls = [
        "https://www.hays.de/jobsuche?q=SAP+MM&p=1",
        "https://www.hays.co.uk/job-search?q=SAP+MM&p=1",
        "https://www.hays.nl/vacatures?q=SAP+MM&p=1",
    ]
    
    print("🔍 Searching Hays for SAP MM jobs...")
    
    for url in search_urls:
        try:
            print(f"  Fetching: {url}")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all job listings
            job_elements = soup.find_all(['a', 'div'], {'data-job-id': True}) or \
                           soup.find_all('article', class_=lambda x: x and 'job' in x.lower()) or \
                           soup.find_all('div', class_=lambda x: x and 'vacancy' in x.lower())
            
            print(f"  Found {len(job_elements)} elements")
            
            # Alternative: look for links with job-related text
            if not job_elements:
                links = soup.find_all('a')
                job_elements = [l for l in links if 'sap' in l.get_text().lower() or 'mm' in l.get_text().lower()]
            
            for elem in job_elements[:20]:  # Limit to first 20 per page
                try:
                    # Extract title and link
                    if elem.name == 'a':
                        title = elem.get_text().strip()
                        href = elem.get('href', '')
                    else:
                        title_elem = elem.find('a')
                        if not title_elem:
                            continue
                        title = title_elem.get_text().strip()
                        href = title_elem.get('href', '')
                    
                    if not title or not href:
                        continue
                    
                    # Only keep SAP-related jobs
                    if 'sap' not in title.lower():
                        continue
                    
                    # Construct full URL
                    if href.startswith('/'):
                        if 'hays.de' in url:
                            full_url = f"https://www.hays.de{href}"
                        elif 'hays.co.uk' in url:
                            full_url = f"https://www.hays.co.uk{href}"
                        else:
                            full_url = f"https://www.hays.nl{href}"
                    else:
                        full_url = href
                    
                    dedup_key = f"hays|{title}"
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        jobs.append({
                            'title': title,
                            'company': 'Hays',
                            'url': full_url,
                            'source': 'Hays',
                        })
                except Exception as e:
                    continue
            
            time.sleep(2)  # Rate limit
            
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            continue
    
    return jobs


def search_michaelpage_simple():
    """Search Michael Page for SAP MM jobs using direct URL."""
    jobs = []
    seen = set()
    
    # Michael Page search URLs for SAP MM
    search_urls = [
        "https://www.michaelpage.de/jobs?keywords=SAP+MM",
        "https://www.michaelpage.co.uk/jobs?keywords=SAP+MM",
        "https://www.michaelpage.nl/jobs?keywords=SAP+MM",
    ]
    
    print("\n🔍 Searching Michael Page for SAP MM jobs...")
    
    for url in search_urls:
        try:
            print(f"  Fetching: {url}")
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job links
            job_links = soup.find_all('a', class_=lambda x: x and 'job' in x.lower())
            if not job_links:
                job_links = soup.find_all('a', href=lambda x: x and ('/jobs/' in x or '/job/' in x))
            
            print(f"  Found {len(job_links)} job links")
            
            for link in job_links[:20]:  # Limit to first 20
                try:
                    title = link.get_text().strip()
                    href = link.get('href', '')
                    
                    if not title or not href:
                        continue
                    
                    # Only keep SAP-related jobs
                    if 'sap' not in title.lower():
                        continue
                    
                    # Construct full URL
                    if href.startswith('/'):
                        if 'michaelpage.de' in url:
                            full_url = f"https://www.michaelpage.de{href}"
                        elif 'michaelpage.co.uk' in url:
                            full_url = f"https://www.michaelpage.co.uk{href}"
                        else:
                            full_url = f"https://www.michaelpage.nl{href}"
                    else:
                        full_url = href
                    
                    dedup_key = f"michaelpage|{title}"
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        jobs.append({
                            'title': title,
                            'company': 'Michael Page',
                            'url': full_url,
                            'source': 'Michael Page',
                        })
                except Exception as e:
                    continue
            
            time.sleep(2)  # Rate limit
            
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            continue
    
    return jobs


def main():
    print("=" * 80)
    print("SAP MM Job Search: Hays & Michael Page (Direct HTTP Scraping)")
    print("=" * 80)
    
    hays_jobs = search_hays_simple()
    mp_jobs = search_michaelpage_simple()
    
    all_jobs = hays_jobs + mp_jobs
    print(f"\n✅ Found {len(all_jobs)} total jobs")
    print(f"   Hays: {len(hays_jobs)}")
    print(f"   Michael Page: {len(mp_jobs)}")
    
    # Save results
    output_file = "/Users/kamnee.maran/Downloads/job-search-agent/pradeep_hays_michaelpage_sap_jobs.json"
    with open(output_file, 'w') as f:
        json.dump(all_jobs, f, indent=2)
    
    print(f"\n💾 Saved to {output_file}")
    
    # Print all jobs
    print("\n📋 Jobs found:")
    print("-" * 80)
    for job in all_jobs:
        print(f"  {job['title']}")
        print(f"    Source: {job['source']}")
        print(f"    URL: {job['url']}")
        print()


if __name__ == "__main__":
    main()
