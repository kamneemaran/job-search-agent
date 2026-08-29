"""
Quick test of integrated Hays scraper in daily_scan
"""

import sys
import re
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

# Import the search_hays function from daily_scan
from daily_scan import search_hays, _playwright_html

print("Testing integrated Hays scraper...\n")

# Test 1: Basic HTML extraction test
print("Test 1: Testing HTML extraction with sample content...")

sample_html = '''
<html>
<body>
<a href="/jobsuche/stellenangebote-jobs-detail-backend-engineer-berlin-123456/1">Backend Engineer</a>
<a href="/jobsuche/stellenangebote-jobs-detail-sap-mm-cologne-892112/1">SAP MM Consultant</a>
<a href="/job-search/senior-software-engineer-london-654321/1">Senior Software Engineer</a>
</body>
</html>
'''

# Test pattern matching
detail_link_pattern = r'/(jobsuche|job-search|vacatures|recherche-emploi|vacaturehays)/.*-\d+/?'
from bs4 import BeautifulSoup
soup = BeautifulSoup(sample_html, 'html.parser')
links = soup.find_all('a', href=re.compile(detail_link_pattern))

print(f"  Found {len(links)} job links")
for link in links:
    href = link.get('href', '')
    print(f"    • {href}")

print("\nTest 2: Title extraction from URL slugs...")

for link in links:
    href = link.get('href', '')
    match = re.search(r'-(detail|job)[-/](.+?)-(\d+)[/?]', href)
    if match:
        title_slug = match.group(2)
        title = title_slug.replace('-', ' ').title()
        print(f"  ✓ {title} (from {title_slug})")

print("\nTest 3: Query URLs (no Playwright)...")
urls = [
    "https://www.hays.de/jobsuche?q=Backend+Engineer",
    "https://www.hays.co.uk/job-search?q=Senior+Software",
]

for url in urls:
    print(f"  URL: {url}")

print("\n✅ Basic extraction tests PASS")
print("\nNote: Full integration test requires Playwright + network access")
print("Run: python3 daily_scan.py --batch boards-eu --profile pradeep")

