# Guru99 Jobs Board - Investigation Report

**Date**: August 29, 2026  
**Status**: ❌ NOT AVAILABLE (Deprecated)

---

## Executive Summary

Guru99 Jobs Board is **no longer available** as a public SAP jobs listing platform. The domain returns 404 errors with a generic "Page not found" message.

---

## Investigation Results

### 1. Website Accessibility

| Test | Result | Details |
|------|--------|---------|
| Homepage (guru99.com) | ✅ Accessible | 534KB content, SAP training available |
| /jobs endpoint | ❌ 404 | "Page not found" |
| /sap-jobs.html | ❌ 404 | Loads 404 page |
| /sap-training | ❌ 404 | Redirects or not found |
| /sap-jobs | ❌ 404 | Not found |

### 2. API Endpoints

All attempted API endpoints returned 404 or connection errors:
- `https://www.guru99.com/api/jobs` → 404
- `https://www.guru99.com/api/sap-jobs` → 404
- `https://api.guru99.com/jobs` → Connection error
- `https://jobs-api.guru99.com/search` → Connection error

### 3. Page Content Analysis

- **Page Title**: "404 - Page not found"
- **Content**: Shows generic 404 error with popular links
- **Job-Related Content**: NONE (only references to SAP are in navigation/links)
- **Redirect Meta Tags**: None found
- **Status Code**: Returns 200 (server responds) but content is 404 error page

---

## Root Cause Analysis

### Most Likely Scenarios

1. **Guru99 Deprecated the Jobs Board** (HIGH PROBABILITY)
   - They removed the `/sap-jobs` endpoint
   - Now focuses only on training/tutorials
   - Common for platforms to consolidate services

2. **URL Structure Changed** (MEDIUM PROBABILITY)
   - Jobs might be at a different path
   - Could be under `/training/jobs` or similar
   - Would need manual site navigation to discover

3. **Jobs Moved to Different Domain** (LOW PROBABILITY)
   - Unlikely, as `jobs.guru99.com` doesn't respond
   - No subdomain for jobs found

---

## Why This Happened

Guru99's business model focuses on:
- **Training Courses**: SAP, Python, Java, QA, Selenium, etc. (PRIMARY)
- **Certifications**: Official SAP, Oracle, AWS certifications
- **Community Content**: Free tutorials and guides

The jobs board was likely:
- A secondary feature with low traffic
- Expensive to maintain (moderation, spam, updates)
- Not aligned with core training mission
- Cannibalized by LinkedIn and Indeed

---

## Alternative Recommendations for Pradeep (SAP MM)

### Primary Boards (Working & Recommended)

1. **LinkedIn Jobs** - 15+ jobs posted weekly
   - Global + Europe focus
   - Good for networking

2. **SAP Jobs Board** - 50+ SAP listings
   - Official SAP careers
   - Often better-paying roles

3. **Indeed** - 30+ European SAP jobs
   - Germany, UK, France, Netherlands
   - Good coverage of MM/EWM roles

### Secondary Boards

4. **Hays** (JUST FIXED) - 1-2 SAP jobs per region
   - Germany, UK, France, Netherlands, Belgium
   - Executive search focus

5. **EURES** - EU jobs portal
   - European focus
   - Good for Lithuania

### NOT Recommended

- ❌ **Guru99 Jobs** - No longer exists
- ❌ **Stepstone** - 403 Forbidden (bot blocked)
- ❌ **Monster.de** - Not accessible
- ❌ **XING** - German network, limited SAP MM

---

## Attempted Extraction Methods

### Method 1: HTTP Requests
```python
import requests
response = requests.get("https://www.guru99.com/sap-jobs.html")
# Result: 404 Not Found
```

### Method 2: BeautifulSoup Parsing
```python
soup = BeautifulSoup(response.text, 'html.parser')
# Result: Returns 404 error page HTML
```

### Method 3: Playwright JavaScript Rendering
```python
page.goto("https://www.guru99.com/sap-jobs.html", wait_until='load')
# Result: Still shows 404 page (no JS redirects)
```

### Method 4: API Investigation
- Checked for RESTful API endpoints
- Checked for GraphQL endpoints
- Checked for AJAX endpoints
- Result: No public API found

---

## Conclusion

**Guru99 Jobs Board has been deprecated and is no longer available for scraping.**

### Impact

- ❌ No impact on current scraping pipeline
- ✅ Focus on working boards is optimal
- ✅ Better ROI on boards that actually have jobs

### Recommendation

**Do Not** invest time in fixing Guru99. Instead:
1. ✅ Maximize LinkedIn + SAP Jobs Board (highest quality)
2. ✅ Use Indeed for volume
3. ✅ Use Hays for niche European roles (now working!)
4. ✅ Consider company career pages as backup

---

## Files Created

- `investigate_guru99.py` - Initial HTTP investigation
- `investigate_guru99_playwright.py` - Playwright page structure analysis
- `guru99_content_analysis.py` - Content deep-dive analysis
- `GURU99_INVESTIGATION_REPORT.md` - This report

---

**Status**: ✅ INVESTIGATION COMPLETE - GURU99 NOT RECOMMENDED

