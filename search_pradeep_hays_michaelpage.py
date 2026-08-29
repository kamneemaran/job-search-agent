"""
Search Hays and Michael Page for SAP MM jobs for Pradeep (8-year profile)
Uses Playwright to scrape JavaScript-rendered job boards
"""

import json
import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
import sys
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

from daily_scan import _playwright_html, score_job

def search_hays_sap_mm():
    """Search Hays for SAP MM jobs across Europe."""
    jobs = []
    seen = set()
    
    hays_urls = {
        "UK": "https://www.hays.co.uk/job-search?q=SAP+MM&industryf=Technology",
        "DE": "https://www.hays.de/jobsuche?q=SAP+MM",
        "FR": "https://www.hays.fr/recherche-emploi?q=SAP+MM",
        "NL": "https://www.hays.nl/vacatures?q=SAP+MM&industryf=Technology",
        "BE": "https://www.hays.be/job-search?q=SAP+MM",
    }
    
    print("🔍 Searching Hays for SAP MM jobs...")
    
    for country, url in hays_urls.items():
        try:
            print(f"  Scraping Hays {country}: {url}")
            html = _playwright_html(url, wait_ms=4000)
            
            if not html or len(html) < 2000:
                print(f"  ⚠️  Hays {country} returned empty/small HTML")
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try multiple selectors for job cards
            cards = soup.select('div[class*="job-result"]') or \
                    soup.select('div[class*="vacancy"]') or \
                    soup.select('article[class*="job"]') or \
                    soup.select('div[class*="card"]')
            
            if not cards:
                # Fallback: find all divs with job-like content
                cards = soup.find_all('div', class_=lambda x: x and any(s in str(x).lower() for s in ['result', 'listing', 'card']))
            
            print(f"  Found {len(cards)} job cards on Hays {country}")
            
            for card in cards:
                try:
                    # Extract title
                    title_el = card.select_one('h2') or card.select_one('h3') or card.select_one('a[class*="job"]')
                    title = title_el.get_text().strip() if title_el else ""
                    
                    # Extract company
                    company_el = card.select_one('[class*="company"]') or card.select_one('[class*="employer"]')
                    company = company_el.get_text().strip() if company_el else "Unknown"
                    
                    # Extract location
                    location_el = card.select_one('[class*="location"]') or card.select_one('[class*="place"]')
                    location = location_el.get_text().strip() if location_el else country
                    
                    # Extract URL
                    link_el = card.find('a', href=True)
                    href = link_el.get("href", "") if link_el else ""
                    
                    if href.startswith("/"):
                        url_full = f"https://www.hays.{_get_hays_domain_suffix(country)}{href}"
                    elif href.startswith("http"):
                        url_full = href
                    else:
                        url_full = ""
                    
                    # Dedup
                    dedup_key = f"{company}|{title}|{country}"
                    if title and "SAP" in title.upper() and dedup_key not in seen:
                        seen.add(dedup_key)
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": url_full,
                            "source": "Hays",
                            "country": country,
                            "posted_at": None
                        })
                        
                except Exception as e:
                    continue
            
            time.sleep(2)  # Rate limit
            
        except Exception as e:
            print(f"  ❌ Error scraping Hays {country}: {e}")
            continue
    
    return jobs


def search_michaelpage_sap_mm():
    """Search Michael Page for SAP MM jobs across Europe."""
    jobs = []
    seen = set()
    
    mp_urls = {
        "UK": "https://www.michaelpage.co.uk/jobs?keywords=SAP+MM",
        "DE": "https://www.michaelpage.de/jobs?keywords=SAP+MM",
        "FR": "https://www.michaelpage.fr/jobs?keywords=SAP+MM",
        "NL": "https://www.michaelpage.nl/jobs?keywords=SAP+MM",
        "BE": "https://www.michaelpage.be/jobs?keywords=SAP+MM",
    }
    
    print("\n🔍 Searching Michael Page for SAP MM jobs...")
    
    for country, url in mp_urls.items():
        try:
            print(f"  Scraping Michael Page {country}: {url}")
            html = _playwright_html(url, wait_ms=4000)
            
            if not html or len(html) < 2000:
                print(f"  ⚠️  Michael Page {country} returned empty/small HTML")
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try multiple selectors
            cards = soup.select('div[class*="job-card"]') or \
                    soup.select('div[class*="vacancy"]') or \
                    soup.select('article[class*="job"]') or \
                    soup.select('div[class*="result"]')
            
            if not cards:
                cards = soup.find_all('div', class_=lambda x: x and any(s in str(x).lower() for s in ['result', 'listing', 'item']))
            
            print(f"  Found {len(cards)} job cards on Michael Page {country}")
            
            for card in cards:
                try:
                    # Extract title
                    title_el = card.select_one('h2') or card.select_one('h3') or card.select_one('[class*="title"]')
                    title = title_el.get_text().strip() if title_el else ""
                    
                    # Extract company
                    company_el = card.select_one('[class*="company"]') or card.select_one('[class*="employer"]')
                    company = company_el.get_text().strip() if company_el else "Unknown"
                    
                    # Extract location
                    location_el = card.select_one('[class*="location"]') or card.select_one('[class*="place"]')
                    location = location_el.get_text().strip() if location_el else country
                    
                    # Extract URL
                    link_el = card.find('a', href=True)
                    href = link_el.get("href", "") if link_el else ""
                    
                    if href.startswith("/"):
                        url_full = f"https://www.michaelpage.{_get_mp_domain_suffix(country)}{href}"
                    elif href.startswith("http"):
                        url_full = href
                    else:
                        url_full = ""
                    
                    # Dedup
                    dedup_key = f"{company}|{title}|{country}"
                    if title and "SAP" in title.upper() and dedup_key not in seen:
                        seen.add(dedup_key)
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": url_full,
                            "source": "Michael Page",
                            "country": country,
                            "posted_at": None
                        })
                        
                except Exception as e:
                    continue
            
            time.sleep(2)  # Rate limit
            
        except Exception as e:
            print(f"  ❌ Error scraping Michael Page {country}: {e}")
            continue
    
    return jobs


def _get_hays_domain_suffix(country_code):
    """Get domain suffix for Hays based on country."""
    mapping = {
        "UK": "co.uk",
        "DE": "de",
        "FR": "fr",
        "NL": "nl",
        "BE": "be",
        "AT": "at",
        "CH": "ch",
        "IE": "ie",
    }
    return mapping.get(country_code, "com")


def _get_mp_domain_suffix(country_code):
    """Get domain suffix for Michael Page based on country."""
    mapping = {
        "UK": "co.uk",
        "DE": "de",
        "FR": "fr",
        "NL": "nl",
        "BE": "be",
        "AT": "at",
        "CH": "ch",
        "IE": "ie",
    }
    return mapping.get(country_code, "com")


def score_pradeep_sap_jobs(jobs):
    """Score jobs against Pradeep's SAP MM profile."""
    print(f"\n📊 Scoring {len(jobs)} jobs against Pradeep's profile...")
    
    scored_jobs = []
    
    for job in jobs:
        job_text = f"{job['title']} {job['company']}"
        description = job.get('description', '')
        
        # Use the score_job function from daily_scan
        score, note = score_job(job['title'], description, job['company'], job['location'])
        
        job['score'] = score
        job['score_note'] = note
        job['profile'] = 'Pradeep SAP MM'
        scored_jobs.append(job)
    
    # Sort by score descending
    scored_jobs.sort(key=lambda x: x['score'], reverse=True)
    
    return scored_jobs


def main():
    print("=" * 80)
    print("SAP MM Job Search: Hays & Michael Page for Pradeep (8-year profile)")
    print("=" * 80)
    
    # Search both boards
    hays_jobs = search_hays_sap_mm()
    mp_jobs = search_michaelpage_sap_mm()
    
    all_jobs = hays_jobs + mp_jobs
    print(f"\n✅ Found {len(all_jobs)} total jobs (Hays: {len(hays_jobs)}, Michael Page: {len(mp_jobs)})")
    
    # Score jobs
    scored_jobs = score_pradeep_sap_jobs(all_jobs)
    
    # Filter for high-quality matches (score >= 60)
    high_quality = [j for j in scored_jobs if j['score'] >= 60]
    perfect_matches = [j for j in scored_jobs if j['score'] >= 90]
    
    print(f"  📈 High-quality matches (60-100): {len(high_quality)}")
    print(f"  ⭐ Perfect matches (90-100): {len(perfect_matches)}")
    
    # Save results
    output_file = "/Users/kamnee.maran/Downloads/job-search-agent/pradeep_hays_michaelpage_sap_jobs.json"
    with open(output_file, 'w') as f:
        json.dump(scored_jobs, f, indent=2)
    
    print(f"\n💾 Saved {len(scored_jobs)} jobs to {output_file}")
    
    # Print top 10 matches
    print("\n🏆 Top 10 Matches:")
    print("-" * 80)
    for i, job in enumerate(scored_jobs[:10], 1):
        print(f"{i}. [{job['score']}%] {job['title']} @ {job['company']}")
        print(f"   Location: {job['location']} | Source: {job['source']}")
        print(f"   URL: {job['url']}")
        print()
    
    return scored_jobs


if __name__ == "__main__":
    jobs = main()
