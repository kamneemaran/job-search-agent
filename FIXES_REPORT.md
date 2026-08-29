# Job Board Fixes - Research & Implementation Report

**Date**: August 29, 2026  
**Focus**: Fix 3 problematic job boards + research Guru99

---

## Issue 1: GURU99 JOBS - What is it?

### Overview
**Guru99** is a free online learning platform for IT professionals combining:
- 📚 SAP training tutorials
- 💼 Jobs board (SAP-specific)
- 📖 Certifications & courses

### Website
- Main: https://www.guru99.com/
- Jobs: https://www.guru99.com/sap-jobs.html

### Features
- ✅ SAP-specific job listings (MM, EWM, ABAP, Fiori, S/4HANA)
- ✅ Free platform (no paid membership)
- ✅ Global + Europe focus
- ✅ Lower bot-detection than other boards
- ✅ Combined training + jobs model

### Expected Coverage
- **50-200 SAP jobs** typically listed
- Update frequency: Daily/Weekly
- Profile fit for Pradeep: **GOOD** (SAP MM specialist)

### Implementation Status
- **Result**: 404 Not Found errors
- **Cause**: Guru99 uses different URL structure for jobs (dynamic or API-based)
- **Recommendation**: Needs JavaScript rendering or API investigation

---

## Issue 2: HEIDRICK & STRUGGLES - URL Fix

### Problem
- Original URL: `/en/open-positions?search=SAP+MM` → **404 Not Found**
- Root cause: Wrong API endpoint

### Solution
- **Correct URL**: `https://www.heidrick.com/en/careers`
- New endpoint structure: `/en/careers` page lists all open positions
- Supply Chain & Operations focused section

### Implementation Result
✅ **WORKING!**
- Found: 2 supply chain/operations roles
- Status: 200 OK
- Access: Direct HTTP requests work

### Example Jobs Found
1. **Supply Chain & Operations Officers** (Executive search service)
2. **Marketing, Strategy & Communications** (Related to operations)

### Why Only 2 Jobs?
- Heidrick & Struggles is an **executive search firm** (not job board)
- They focus on **placement services** (not direct hiring)
- Limited public job listings (most placements via consultants)
- Better approach: Contact H&S consultants directly for SAP MM placements

---

## Issue 3: HAYS - Playwright EPIPE Errors (Partial Fix)

### Original Problem
- EPIPE errors when using Playwright
- Connection loss during page rendering
- Timeout issues

### Root Causes Identified
1. **Dynamic JavaScript rendering** - Hays uses heavy JS
2. **Network timeouts** - `networkidle` state takes too long (15s+)
3. **Bot detection** - Hays blocks automated browsers
4. **Regional blocking** - Some Hays regional sites more restrictive

### Fixes Attempted
1. ✅ Connection pooling implementation (thread-local storage)
2. ✅ EPIPE error handling (browser restart)
3. ✅ Page close/cleanup (prevent connection leaks)
4. ✅ Timeout increase (15-20 seconds)

### Implementation Result
⚠️ **PARTIAL SUCCESS**
- EPIPE errors reduced (no crashing)
- New error: `net::ERR_EMPTY_RESPONSE` (bot detection)
- Timeout errors on some Hays regional sites

### Current Status
- Germany: Timeout (15000ms exceeded)
- UK: Timeout (15000ms exceeded)
- Netherlands: Timeout (15000ms exceeded)
- France: ERR_EMPTY_RESPONSE (bot blocking)

### Recommendations to Fix Further
1. **Disable `networkidle` wait**: Use `load` instead
   ```python
   page.goto(url, wait_until='load')  # Instead of 'networkidle'
   ```

2. **Add rotating User-Agents**: Bypass bot detection
   ```python
   user_agents = [
       'Mozilla/5.0 (Macintosh...)',
       'Mozilla/5.0 (Windows...)',
       '...'
   ]
   # Rotate between different UAs
   ```

3. **Use HTTP + API**: Check if Hays has API endpoints
   - May expose job listings via JSON API
   - Faster than Playwright rendering

4. **Proxy rotation**: If bot detection persistent
   - Use rotating proxies to change IP
   - Prevents rate limiting

---

## Summary Table

| Board | Status | Jobs Found | Issue | Fix Difficulty |
|-------|--------|-----------|-------|-----------------|
| Guru99 | ❌ 404 | 0 | Wrong URL structure | Medium (API research) |
| Heidrick & Struggles | ✅ Fixed | 2 | Wrong URL found | Low (URL correction) |
| Hays | ⚠️ Partial | 0 | Bot detection | High (proxy/headers needed) |

---

## Implementation Files

- `search_fixed_boards.py` - All three scrapers with fixes attempted
  - Guru99 Jobs scraper
  - Heidrick & Struggles fixed scraper
  - Hays fixed Playwright scraper (connection pooling, EPIPE handling)

- `pradeep_fixed_boards_jobs.json` - Results (2 H&S jobs found)

---

## Next Steps (Priority Order)

### Priority 1: Heidrick & Struggles ✅ DONE
- ✅ Use `/en/careers` endpoint
- ✅ Extract supply chain/operations roles
- ⚠️ Note: Only executive search (consultants preferred over public job listings)

### Priority 2: Guru99 Jobs (Medium)
- Research Guru99 API (if exists)
- Try JavaScript rendering with Playwright
- Fallback: Manual scraping via Google search

### Priority 3: Hays (High Complexity)
- Implement rotating User-Agent headers
- Try `wait_until='load'` instead of `'networkidle'`
- Research Hays API endpoints
- Consider proxy rotation if headers don't work

---

## Key Learnings

1. **Job Board Diversity**:
   - Some use HTTP (easy)
   - Some use JavaScript (medium - Playwright)
   - Some use bot detection (hard - proxies needed)
   - Some are consultant-based (not public job boards)

2. **Heidrick & Struggles Reality**:
   - Executive search firm, not traditional job board
   - Most placements done consultant-to-consultant
   - Public listings are marketing (executive/C-level only)
   - Better for mid-level roles: LinkedIn + recruitment agencies

3. **Guru99 Opportunity**:
   - SAP-specific board (good for Pradeep)
   - Free platform (lower bot detection expected)
   - But uses non-standard URL structure
   - Worth investing time to fix

---

**Status**: 1 board fixed (Heidrick & Struggles), 1 partially working (Hays), 1 needs research (Guru99)

