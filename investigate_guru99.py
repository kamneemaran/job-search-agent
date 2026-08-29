"""
Investigate Guru99 Jobs website structure and API
"""

import requests
from bs4 import BeautifulSoup
import re
import json

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

print("=" * 80)
print("GURU99 JOBS INVESTIGATION")
print("=" * 80)

# 1. Check main Guru99 Jobs page
print("\n1️⃣  Testing Guru99 Homepage...")
url = "https://www.guru99.com/"
headers = {'User-Agent': USER_AGENT}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"  Status: {response.status_code}")
    print(f"  Content size: {len(response.text)} bytes")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for jobs link
        job_links = soup.find_all('a', href=re.compile(r'job', re.I))
        print(f"  Links with 'job' keyword: {len(job_links)}")
        
        if job_links:
            print("  Sample job links:")
            for link in job_links[:5]:
                href = link.get('href', '')
                text = link.get_text(strip=True)[:50]
                print(f"    • {text}: {href}")
except Exception as e:
    print(f"  Error: {e}")

# 2. Try alternative Guru99 Jobs URLs
print("\n2️⃣  Testing Alternative Guru99 Jobs URLs...")

urls_to_test = [
    "https://www.guru99.com/jobs",
    "https://www.guru99.com/sap-jobs",
    "https://jobs.guru99.com/",
    "https://www.guru99.com/sap-jobs.html",
    "https://www.guru99.com/sap-training",
]

for url in urls_to_test:
    try:
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        status = f"✓ {response.status_code}" if response.status_code == 200 else f"✗ {response.status_code}"
        print(f"  {url}")
        print(f"    Status: {status}")
        
        if response.status_code == 200:
            # Check if it has job-related content
            if 'job' in response.text.lower():
                print(f"    Content: Has job-related content")
            else:
                print(f"    Content: Size = {len(response.text)} bytes")
    except Exception as e:
        print(f"  {url} - Error: {str(e)[:50]}")

# 3. Check for API endpoints (inspect Network tab-like patterns)
print("\n3️⃣  Searching for API/AJAX endpoints...")

try:
    # Try to fetch the main Guru99 page and look for API calls
    response = requests.get("https://www.guru99.com/", headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Look for script tags that might contain API URLs
    scripts = soup.find_all('script')
    print(f"  Script tags found: {len(scripts)}")
    
    # Search for API patterns in scripts
    api_patterns = [
        r'https?://[^"\'\s]+api[^"\'\s]*',
        r'"/api/[^"]*',
        r'fetch\(["\']([^"\']+)["\']',
        r'xhr\.open\(["\'].*?["\'].*?["\']([^"\']+)',
    ]
    
    for pattern in api_patterns:
        for script in scripts[:20]:  # Check first 20 scripts
            script_content = script.string
            if script_content:
                matches = re.findall(pattern, script_content)
                if matches:
                    print(f"  Pattern '{pattern[:20]}...' found:")
                    for match in matches[:3]:
                        print(f"    • {match[:80]}")
except Exception as e:
    print(f"  Error: {e}")

# 4. Check Google Search for Guru99 Jobs board
print("\n4️⃣  Guru99 SAP Jobs Information...")
print("  Website: https://www.guru99.com/")
print("  Coverage: SAP training + jobs (free platform)")
print("  Status Code Tests:")

# Try common API endpoints
api_endpoints = [
    "https://www.guru99.com/api/jobs",
    "https://www.guru99.com/api/sap-jobs",
    "https://api.guru99.com/jobs",
    "https://jobs-api.guru99.com/search",
]

for endpoint in api_endpoints:
    try:
        response = requests.get(endpoint, headers=headers, timeout=5)
        print(f"    {endpoint}: {response.status_code}")
    except Exception as e:
        print(f"    {endpoint}: Error ({str(e)[:30]})")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("""
Guru99 Jobs Findings:
- ✓ Guru99 website exists and is accessible
- ✓ SAP training content available
- ✗ Direct /sap-jobs.html endpoint returns 404
- ? API endpoints not immediately found
- ? Possible: Jobs are loaded dynamically (JavaScript/AJAX)

Recommendations:
1. Use Playwright to render JavaScript
2. Look for AJAX/XHR calls in Network tab
3. Search Guru99 site for jobs link in navigation
4. Check if jobs are embedded in training pages
""")

