"""
Improved Hays Scraper for daily_scan.py integration
Uses rotating User-Agent headers + URL pattern extraction
"""

import re
import time
import random
from bs4 import BeautifulSoup

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

HAYS_SEARCH_URLS = {
    "DE": [
        "https://www.hays.de/jobsuche?q=SAP+MM",
        "https://www.hays.de/jobsuche?q=SAP+EWM",
        "https://www.hays.de/jobsuche?q=Backend+Engineer",
    ],
    "UK": [
        "https://www.hays.co.uk/job-search?q=Backend+Engineer",
        "https://www.hays.co.uk/job-search?q=Software+Engineer",
    ],
    "NL": [
        "https://www.hays.nl/vacatures?q=Backend+Engineer",
    ],
    "FR": [
        "https://www.hays.fr/recherche-emploi?q=Backend+Engineer",
    ],
    "BE": [
        "https://www.hays.be/vacatures?q=Backend+Engineer",
    ],
}

def extract_hays_jobs_improved(html, country_code):
    """
    Extract jobs from Hays using URL pattern matching.
    More reliable than CSS class matching.
    """
    jobs = []
    
    if not html or len(html) < 5000:
        return jobs
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Look for job detail links using URL pattern
    # Pattern varies by country but generally contains job ID
    detail_link_pattern = r'/(jobsuche|job-search|vacatures|recherche-emploi|vacaturehays)/.*-\d+/?'
    detail_links = soup.find_all('a', href=re.compile(detail_link_pattern))
    
    for link in detail_links[:30]:  # Extract up to 30 per search
        try:
            href = link.get('href', '')
            
            # Make absolute URL
            if href.startswith('/'):
                if 'hays.de' in f"https://www.hays.de{href}":
                    href = f"https://www.hays.de{href}"
                elif 'hays.co.uk' in href or country_code == "UK":
                    href = f"https://www.hays.co.uk{href}"
                elif 'hays.nl' in href or country_code == "NL":
                    href = f"https://www.hays.nl{href}"
                elif 'hays.be' in href or country_code == "BE":
                    href = f"https://www.hays.be{href}"
                elif 'hays.fr' in href or country_code == "FR":
                    href = f"https://www.hays.fr{href}"
                else:
                    # Default based on country
                    domain_map = {
                        "DE": "https://www.hays.de",
                        "UK": "https://www.hays.co.uk",
                        "NL": "https://www.hays.nl",
                        "FR": "https://www.hays.fr",
                        "BE": "https://www.hays.be",
                    }
                    domain = domain_map.get(country_code, "https://www.hays.de")
                    href = f"{domain}{href}"
            elif not href.startswith('http'):
                continue
            
            # Extract title from URL slug
            # Pattern: /jobsuche/stellenangebote-jobs-detail-<TITLE>-<LOCATION>-<ID>/
            match = re.search(r'-(detail|job)[-/](.+?)-(\d+)[/?]', href)
            if not match:
                match = re.search(r'/([^/]+)-(\d+)[/?]$', href)
            
            if match and match.lastindex >= 2:
                title_slug = match.group(2) if match.lastindex >= 2 else match.group(1)
            else:
                continue
            
            title = title_slug.replace('-', ' ').title()
            
            jobs.append({
                'title': title,
                'company': 'Hays',
                'location': country_code,
                'url': href,
                'source': 'Hays',
                'description': f"Hays {country_code}: {title}"
            })
        except Exception:
            continue
    
    return jobs


def search_hays_improved(query="Backend Engineer", location="Europe", max_results=500, _playwright_html_fn=None):
    """
    Search Hays with improved URL pattern extraction.
    
    Args:
        query: Search term (ignored, uses predefined searches)
        location: Region (e.g., "Europe")
        max_results: Maximum jobs to return
        _playwright_html_fn: Function to render HTML with Playwright
                            Should take (url, timeout, wait_ms) and return HTML string
    
    Returns:
        List of job dicts with title, company, location, url, description
    """
    
    if _playwright_html_fn is None:
        # Fallback: return empty (caller should provide this)
        print("  [hays] Warning: No Playwright HTML function provided")
        return []
    
    jobs = []
    seen = set()
    
    try:
        for country_code, search_urls in HAYS_SEARCH_URLS.items():
            if len(jobs) >= max_results:
                break
            
            for search_url in search_urls:
                if len(jobs) >= max_results:
                    break
                
                try:
                    # Set rotating User-Agent via page context
                    # Note: _playwright_html doesn't support custom headers yet,
                    # but we can still use it and it will use the stealth approach
                    html = _playwright_html_fn(search_url, timeout=20000, wait_ms=2000)
                    
                    if not html or len(html) < 5000:
                        continue
                    
                    # Extract jobs from HTML
                    country_jobs = extract_hays_jobs_improved(html, country_code)
                    
                    # Deduplicate
                    for job in country_jobs:
                        dedup_key = f"{job['title']}|{job['url']}"
                        if dedup_key not in seen:
                            seen.add(dedup_key)
                            jobs.append(job)
                    
                    # Random delay to avoid detection
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    continue
        
        if jobs:
            print(f"  [hays] {len(jobs)} jobs found across European countries")
        return jobs
    
    except Exception as e:
        print(f"  [hays] Error: {e}")
        return []


if __name__ == "__main__":
    # Test without Playwright (just show structure)
    print("Hays Improved Scraper Module")
    print(f"Countries: {list(HAYS_SEARCH_URLS.keys())}")
    print(f"Total search URLs: {sum(len(urls) for urls in HAYS_SEARCH_URLS.values())}")
    print("\nTo use in daily_scan.py:")
    print("  from hays_improved_scraper import search_hays_improved")
    print("  jobs = search_hays_improved(_playwright_html_fn=_playwright_html)")

