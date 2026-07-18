"""
Daily Job Matching Agent
========================
Scans company ATS APIs (Greenhouse, Lever, Ashby) plus job boards
(LinkedIn, Indeed, Naukri, Instahyre) for matching roles, scores
each posting against the resume profile, and emails a daily digest.

Run manually:   python daily_scan.py
Run on schedule: see .github/workflows/daily_scan.yml (GitHub Actions, free tier)

Required environment variables (set as GitHub Secrets or local .env):
  GMAIL_ADDRESS        - kamneemaran45@gmail.com
  GMAIL_APP_PASSWORD   - Gmail App Password (NOT your normal password - see setup notes)
  WHATSAPP_TO          - optional, +91XXXXXXXXXX (only if Twilio is configured)
  TWILIO_SID           - optional
  TWILIO_AUTH_TOKEN    - optional
  TWILIO_WHATSAPP_FROM - optional, e.g. whatsapp:+14155238886
"""

import os
import sys
import json
import re
import smtplib
import time
import imaplib
import email
import argparse
import threading
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import cloudscraper
import PyPDF2
from eu_companies import EU_JOB_SOURCES
from global_companies import GLOBAL_JOB_SOURCES
from apac_companies import APAC_JOB_SOURCES
from us_canada_companies import US_CANADA_JOB_SOURCES
from middle_east_companies import MIDDLE_EAST_JOB_SOURCES
from remote_companies import REMOTE_JOB_SOURCES
from dotenv import load_dotenv
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Lazy import for Playwright (headless browser for JS-rendered sites)
# Using thread-local storage to prevent Greenlet thread-switching conflicts in web servers like FastAPI.
_local_playwright = threading.local()
_personio_lock = threading.Lock()

def _get_browser():
    """Retrieve or create a thread-local Playwright browser to ensure thread-safety."""
    if not hasattr(_local_playwright, "pw") or _local_playwright.pw is None:
        from playwright.sync_api import sync_playwright
        _local_playwright.pw = sync_playwright().start()
        _local_playwright.page_count = 0
        
    if hasattr(_local_playwright, "browser") and _local_playwright.browser is not None:
        try:
            if not _local_playwright.browser.is_connected():
                _local_playwright.browser = None
                _local_playwright.page_count = 0
        except Exception:
            _local_playwright.browser = None
            _local_playwright.page_count = 0
        
    if not hasattr(_local_playwright, "browser") or _local_playwright.browser is None:
        _local_playwright.browser = _local_playwright.pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled", 
                "--disable-http2", 
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--disable-dev-shm-usage",
                "--js-flags=--max-old-space-size=512",
                "--disable-gpu",
                "--disable-extensions"
            ]
        )
    return _local_playwright.browser

def _check_reclaim_playwright():
    """Check and recycle the browser process if we have loaded multiple pages, preventing OOM memory accumulation."""
    if not hasattr(_local_playwright, "page_count"):
        _local_playwright.page_count = 0
    _local_playwright.page_count += 1
    if _local_playwright.page_count >= 15:
        try:
            if hasattr(_local_playwright, "browser") and _local_playwright.browser:
                _local_playwright.browser.close()
        except Exception:
            pass
        _local_playwright.browser = None
        _local_playwright.page_count = 0

def _with_stealth(page):
    """Apply stealth anti-detection to a page if playwright_stealth is available."""
    try:
        from playwright_stealth import Stealth
        Stealth().apply_stealth_sync(page)
    except ImportError:
        pass
    try:
        page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        // Bypass Cloudflare Turnstile
        window.turnstile = {
            render: (container, params) => {
                if (params && params.callback) params.callback('bypassed');
                return 'bypassed';
            },
            reset: () => {},
            getResponse: () => 'bypassed',
            remove: () => {},
            implicitRender: () => 'bypassed',
            ready: (fn) => fn && fn()
        };
        Object.defineProperty(window, 'cf_challenge_response', { get: () => 'bypassed' });
        """)
    except Exception:
        pass

_BLOCKED_RESOURCE_TYPES = {"image", "stylesheet", "media", "font"}
_BLOCKED_URL_KEYWORDS = ("analytics", "googletagmanager", "google-analytics", "hubspot",
                         "hotjar", "doubleclick", "facebook.net", "adservice",
                         "tracking", "pixel", "advertisement")

def _block_unnecessary_resources(page):
    """Intercept and abort requests for images, stylesheets, fonts, media, and tracking scripts."""
    def _route_handler(route):
        if route.request.resource_type in _BLOCKED_RESOURCE_TYPES:
            route.abort()
        elif any(kw in route.request.url for kw in _BLOCKED_URL_KEYWORDS):
            route.abort()
        else:
            route.continue_()
    page.route("**/*", _route_handler)

import hashlib as _hashlib
_STORAGE_STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".browser_state")
os.makedirs(_STORAGE_STATE_DIR, exist_ok=True)

def _storage_state_path(domain):
    """Get storage state file path for a given domain."""
    safe = _hashlib.md5(domain.encode()).hexdigest()[:12]
    return os.path.join(_STORAGE_STATE_DIR, f"{safe}.json")

def _get_domain(url):
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return "default"

def _create_context(browser, url=None):
    """Create a browser context with persisted storage state if available."""
    domain = _get_domain(url) if url else "default"
    state_path = _storage_state_path(domain)
    kwargs = dict(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
    )
    if os.path.exists(state_path):
        try:
            kwargs["storage_state"] = state_path
        except Exception:
            pass
    return browser.new_context(**kwargs)

def _save_context_state(context, url=None):
    """Save browser context storage state for future reuse."""
    try:
        domain = _get_domain(url) if url else "default"
        state_path = _storage_state_path(domain)
        context.storage_state(path=state_path)
    except Exception:
        pass

load_dotenv()


def strip_html(html):
    """Remove HTML tags and decode common entities for keyword matching."""
    text = html.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

# ---------------------------------------------------------------------------
# 1. CONFIGURATION - your sources, profile, and scoring rules
# ---------------------------------------------------------------------------

PROFILE = {
    "name": "Kamnee Maran",
    "years_experience": 10,
    "core_skills": [
        "java", "python", "node.js", "golang", "microservices", "distributed systems",
        "event-driven", "kafka", "redis", "mysql", "postgresql", "mongodb",
        "elasticsearch", "aws", "azure", "gcp", "docker", "kubernetes", "rest api",
        "api development", "system design", "high availability", "scalable",
        "spring boot", "backend", "cloud infrastructure", "devops",
        "fintech", "payments", "compliance", "incident management",
        "ci/cd", "terraform", "architecture", "soa", "data pipelines",
        # AI-infra / modern platform skills (helps match AI infrastructure companies)
        "fastapi", "grpc", "helm", "prometheus", "grafana", "gpu",
    ],
    "current_role": "Senior Software Engineer",
    "seniority_keywords": ["senior", "staff", "lead", "principal", "sde-3", "sde 3"],
    "junior_red_flags": [
        "junior", "intern", "entry level", "graduate", "0-2 years", "1-2 years",
        "sde-1", "sde 1", "sde1", "sde-i", "sde i", "sdei", "se-1", "se 1", "se1",
        "software engineer i", "software engineer 1", "associate software engineer", "associate engineer"
    ],
    # Job titles that are NOT relevant (different career tracks)
    "title_red_flags": [
        # Infrastructure / network / devops roles outside backend/platform engineering
        "network engineer", "network architect", "network administrator", "network security",
        "devops engineer", "devops", "site reliability engineer", "sre",
        "network infrastructure",
        # Sales / account / customer-facing roles
        "account executive", "account manager", "account director",
        "sales engineer", "sales representative", "sales development", "sales ",
        "business development", "business development representative",
        "customer success", "customer support", "customer experience",
        "technical account manager", "solutions engineer", "solutions architect",
        "technical account management", "technical account", "account management",
        # Product / program / project management
        "product manager", "program manager", "project manager", "product owner",
        "engineering manager", "manager, engineering", "director of engineering",
        "manager i", "manager ii", "manager iii", "engineering - applied", "engineering - ai",
        # People / HR
        "recruiter", "hiring", "talent acquisition", "hr ", "hris", "workday",
        "people technology", "people operations", "people partner", "people team",
        # Marketing / content / brand
        "marketing", "content writer", "content strategist", "social media", "brand ",
        "corporate communications", "communications lead", "communications manager",
        "public relations", "pr ", "media relations",
        # Finance / legal / compliance
        "finance", "accounting", "accountant", "legal", "lawyer",
        "compliance", "mlro", "money laundering", "regulatory",
        "payments risk", "payments compliance", "risk manager", "risk analyst",
        # Data science / analytics / pure AI
        "data scientist", "data analyst", "data engineer",
        "analytics",
        "machine learning engineer", "ml engineer", "deep learning",
        "ai research", "ai/ml", "prompt engineer", "llm engineer",
        "ai engineer", "applied scientist", "data science",
        "distinguished architect", "offensive security", "application security engineer",
        "security engineer - cloud", "security software engineer",
        # Business operations / strategy / non-eng management
        "process strategy", "process optimization", "process manager",
        "operations manager", "business operations", "strategy manager",
        "operations strategy", "business strategy",
        "strategic intelligence", "protective intelligence",
        "clearing operations", "clearing",
        "partner manager", "partner enablement", "enablement manager",
        "channel partner", "channel manager",
        "market manager", "marketplace manager", "mid market",
        "key account", "accounts executive",
        "gtm ", "go to market", "strategy/operations",
        "workforce management", "workforce",
        "delivery excellence", "delivery manager", "delivery lead",
        "field enablement", "field marketing",
        "business process", "process improvement",
        # Localization / translation
        "localization", "localization manager", "translator",
        # Design / UX
        "designer", "ui ", "ux ", "product design", "visual design",
        # Mobile / frontend / QA
        "android", "ios", "swift", "kotlin",
        "frontend", "front-end", "front end", "ui engineer", "web engineer",
        "qa ", "qa engineer", "quality assurance", "quality engineer", "test engineer",
        "sdet", "automation engineer",
        # Miscellaneous non-engineering
        "technical writer", "documentation", "analyst",
        "support engineer", "it support", "desktop support",
        "maintenance", "assistant", "associate ",
        "administrative", "admin assistant", "office manager",
        "safety", "safety specialist", "security specialist", "security guard",
        # Incident / escalation / support management
        "incident manager", "incident response", "escalations manager",
        "escalation manager", "escalation engineer", "incident commander",
        # Policy / government / regulatory affairs
        "public policy", "policy manager", "policy director", "policy advisor",
        "policy economist", "government affairs", "regulatory affairs",
        # Administrative / legal / HR
        "executive assistant",
        "stock administrator",
        "corporate counsel", "securities counsel", "legal counsel", "paralegal",
        "hr business partner", "hr coordinator", "payroll",
        # Customer-facing services / consulting / architect roles
        "services architect", "service architect", "implementation services",
        "customer onboarding", "customer implementation", "professional services",
        "services consultant", "implementation consultant", "implementation engineer",
        # Sales support / non-technical customer roles
        "inside sales", "sales support", "sales operations",
        "customer success manager", "customer support specialist",
        # Finance / accounting (non-SAP specific)
        "accountant", "accounts payable", "accounts receivable",
        "financial analyst", "finance manager", "controller",
        # Non-software engineering disciplines (aerospace, hardware, mechanical, etc.)
        "systems engineer", "it systems engineer", "ground segment",
        "space systems", "satellite", "aerospace", "avionics", "propulsion",
        "mechanical engineer", "electrical engineer", "hardware engineer",
        "rf engineer", "pcb engineer", "civil engineer", "chemical engineer",
        "biomedical", "embedded engineer", "firmware engineer",
        "systems administrator", "sysadmin",
    ],
}

# Role domains for auto-detecting relevant roles from resume skills.
# Each domain lists skills that identify it and title patterns to FILTER OUT.
ROLE_DOMAINS = {
    "backend": {
        "skills": {
            "java", "python", "golang", "go", "rust", "scala", "node.js", "nodejs",
            "spring", "spring boot", "django", "flask", "express", "fastapi",
            "microservices", "distributed systems", "system design", "rest api",
            "sql", "mysql", "postgresql", "mongodb", "redis", "kafka", "rabbitmq",
            "grpc", "soa", "event-driven", "backend",
        },
        "red_flags": [
            "frontend", "front-end", "front end", "ui engineer", "web engineer",
            "android", "ios", "swift", "kotlin", "flutter",
            "qa engineer", "quality assurance", "test engineer", "sdet", "automation engineer",
            "data scientist", "data analyst", "machine learning engineer", "ml engineer",
            "network engineer", "network architect", "devops engineer", "sre",
            "ux designer", "ui designer", "product designer",
        ],
    },
    "frontend": {
        "skills": {
            "javascript", "typescript", "react", "angular", "vue", "vue.js", "svelte",
            "html", "css", "sass", "less", "webpack", "vite", "next.js", "nuxt",
            "frontend", "front-end", "ui", "ux", "tailwind", "bootstrap",
        },
        "red_flags": [
            "android", "ios", "swift", "kotlin", "flutter",
            "qa engineer", "test engineer", "sdet", "automation engineer",
            "data scientist", "data engineer", "ml engineer",
            "network engineer", "devops engineer", "sre",
            "backend engineer", "distributed systems", "microservices",
            "cloud engineer", "infrastructure engineer",
        ],
    },
    "mobile": {
        "skills": {
            "android", "ios", "swift", "kotlin", "flutter", "react native", "dart",
            "mobile", "ipad", "iphone", "uikit", "jetpack",
        },
        "red_flags": [
            "frontend", "ui engineer", "web engineer",
            "qa", "quality assurance", "sdet", "automation engineer",
            "devops", "sre", "network engineer",
            "data scientist", "ml engineer",
        ],
    },
    "data_ml": {
        "skills": {
            "machine learning", "deep learning", "data science", "tensorflow", "pytorch",
            "pandas", "numpy", "scikit-learn", "spark", "hadoop", "airflow",
            "nlp", "computer vision", "statistics", "llm", "openai",
        },
        "red_flags": [
            "frontend", "ui engineer", "web engineer",
            "android", "ios", "swift", "kotlin",
            "qa engineer", "test engineer",
            "network engineer", "sre", "devops engineer",
            "mobile developer",
        ],
    },
    "devops_sre": {
        "skills": {
            "docker", "kubernetes", "k8s", "terraform", "ansible", "puppet", "chef",
            "ci/cd", "jenkins", "github actions", "gitlab ci", "argocd",
            "prometheus", "grafana", "datadog", "new relic", "splunk",
            "helm", "istio", "envoy", "cloudformation",
            "devops", "sre", "site reliability", "infrastructure",
        },
        "red_flags": [
            "frontend", "ui engineer", "web engineer",
            "android", "ios", "swift", "kotlin",
            "qa engineer", "test engineer",
            "data scientist", "ml engineer",
            "mobile developer",
        ],
    },
    "qa": {
        "skills": {
            "selenium", "cypress", "playwright", "testing", "test automation",
            "jest", "mocha", "junit", "pytest", "testng",
            "quality assurance", "qa", "sdet", "integration test",
        },
        "red_flags": [
            "frontend engineer", "ui engineer",
            "android", "ios", "swift", "kotlin",
            "data scientist", "ml engineer",
            "network engineer", "sre", "devops engineer",
        ],
    },
    "fullstack": {
        "skills": {
            "javascript", "typescript", "react", "node.js", "nodejs",
            "python", "java", "go", "ruby", "php",
            "html", "css", "rest api", "database", "sql",
            "full stack", "fullstack",
        },
        "red_flags": [
            "android", "ios", "swift", "kotlin", "flutter",
            "qa engineer", "quality assurance", "sdet",
            "data scientist", "ml engineer",
            "network engineer", "sre", "devops engineer",
            "ux designer", "product designer",
        ],
    },
    "sap_erp": {
        "skills": {
            "sap", "sap mm", "sap sd", "sap fico", "sap hana", "sap abap", "abap",
            "sap basis", "sap pp", "sap wm", "sap ewm", "sap ariba", "sap s/4hana",
            "sap bw", "sap crm", "erp", "materials management", "procurement",
            "supply chain", "inventory management", "warehouse management",
            "functional consultant", "configuration", "customizing",
        },
        "red_flags": [
            "frontend", "front-end", "ui engineer", "web engineer",
            "android", "ios", "swift", "kotlin",
            "machine learning", "ml engineer", "data scientist",
            "network engineer", "sre", "devops engineer",
            "ux designer", "product designer",
            "react", "angular", "vue",
        ],
    },
}

# Engineering domains that should NOT filter each other out (compatible tracks)
COMPATIBLE_DOMAINS = {
    "backend": {"devops_sre", "fullstack"},
    "frontend": {"fullstack"},
    "fullstack": {"backend", "frontend"},
    "devops_sre": {"backend"},
    "data_ml": {"backend"},
    "sap_erp": set(),  # SAP is a distinct domain, no cross-compatibility
}

# Universal filters that apply regardless of role (always-on non-engineering tracks)
UNIVERSAL_RED_FLAGS = [
    "account executive", "account manager", "account director",
    "sales engineer", "sales representative", "sales development",
    "business development", "customer success",
    "technical account manager", "solutions engineer", "account management",
    "product manager", "program manager", "project manager", "product owner",
    "engineering manager", "director of engineering",
    "recruiter", "hiring", "talent acquisition", "hr ", "hris",
    "people operations", "people partner",
    "marketing", "content writer", "social media", "brand ",
    "public relations", "pr ", "communications",
    "finance", "accounting", "tax", "audit", "legal", "lawyer", "compliance",
    "payments risk", "risk manager", "risk analyst",
    "operations manager", "business operations", "strategy",
    "partner manager", "channel partner",
    "designer", "product design", "visual design",
    "executive assistant", "administrative", "office manager",
    "assistant", "analyst",
    "technical writer", "documentation", "support engineer", "it support",
    "services architect", "implementation consultant",
    "professional services", "customer onboarding",
    "public policy", "government affairs", "regulatory affairs",
    "localization", "translator", "safety", "security guard",
    "incident manager", "incident response",
    # User Preferences Red Flags (Mobile, Frontend, QA, SRE/Network)
    "android", "ios", "swift", "kotlin",
    "frontend", "front-end", "front end", "ui engineer", "web engineer",
    "qa", "qa engineer", "quality assurance", "quality engineer", "test engineer", "sdet", "automation engineer",
    "network infrastructure", "network engineer", "network architect", "sre", "site reliability engineer", "devops", "devops engineer"
]


def auto_detect_title_red_flags(skills):
    """
    Given a list of skill keywords, detect the candidate's primary domain(s)
    and return the appropriate title red flags: universal filters + domain-specific ones.
    Compatible domains are kept (e.g. backend won't filter devops).
    """
    skill_set = set(s.lower() for s in skills)
    detected = []
    for domain, config in ROLE_DOMAINS.items():
        matches = len(skill_set & config["skills"])
        if matches >= 2:
            detected.append(domain)

    flags = list(UNIVERSAL_RED_FLAGS)
    if detected:
        compat = set()
        for d in detected:
            compat.add(d)
            compat.update(COMPATIBLE_DOMAINS.get(d, set()))
        for domain, config in ROLE_DOMAINS.items():
            if domain not in compat:
                flags.extend(config["red_flags"])
    return flags


# Keywords that indicate visa / relocation support in a job description
VISA_SPONSORSHIP_KEYWORDS = [
    "visa sponsorship", "work visa", "sponsorship available", "employment visa",
    "immigration support", "visa provided", "we sponsor", "will sponsor",
    "work authorization", "visa", "sponsor",
]

RELOCATION_SUPPORT_KEYWORDS = [
    "relocation support", "relocation assistance", "relocation package",
    "relocation provided", "relocation assistance available", "global mobility",
    "relocation",
]

# Combined list kept for backward-compat (informational note + mcp_server)
VISA_RELOCATION_KEYWORDS = VISA_SPONSORSHIP_KEYWORDS + RELOCATION_SUPPORT_KEYWORDS

# Explicit "no sponsorship" phrases — hard reject for non-India roles
NO_SPONSORSHIP_KEYWORDS = [
    "no visa sponsorship", "not sponsor", "cannot sponsor", "will not sponsor",
    "unable to sponsor", "no sponsorship", "not eligible for visa",
    "must be authorized to work", "must have existing right to work",
    "no relocation", "not provide visa", "only citizens",
    "do not offer sponsorship", "without sponsorship",
    "not able to sponsor", "sponsorship is not available",
]

# Keywords that suggest the role requires a specific non-English language
# (used to auto-reject roles that aren't primarily English-speaking)
NON_ENGLISH_LANGUAGE_KEYWORDS = [
    "fluent in german", "fluent in dutch", "fluent in french", "fluent in japanese",
    "fluent in mandarin", "fluent in spanish", "fluent in italian",
    "german speaking", "dutch speaking", "french speaking", "japanese speaking",
    "must speak german", "must speak dutch", "must speak french",
    "native german", "native dutch", "native french",
    "deutschkenntnisse", "niederländisch", "französisch",
]

# Companies known to NOT support relocation from outside the EU / no India hiring
# (update this list as you learn more - e.g. after Mollie's rejection)
NO_RELOCATION_FLAGS = {
    # REMOVED: Mollie - was auto-scoring ALL jobs to 0; user can manually reject if needed
    # "mollie": "No relocation support outside Europe (confirmed - application rejected screening)",
}

# IND recognised sponsors (Netherlands) — populated at startup from the official IND register
# Covers all organisations authorised to sponsor highly skilled migrants in the Netherlands
_IND_SPONSORS: set[str] = set()
_IND_SPONSORS_CACHE_FILE = "ind_sponsors_cache.json"


def _fetch_ind_sponsors() -> set[str]:
    """Fetch IND register from the official website and derive lookup keys."""
    from bs4 import BeautifulSoup
    url = ("https://ind.nl/en/public-register-recognised-sponsors/"
           "public-register-regular-labour-and-highly-skilled-migrants")
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        print(f"  [ind] HTTP {resp.status_code} loading IND register")
        return set()
    soup = BeautifulSoup(resp.text, 'html.parser')
    full_names: set[str] = set()
    for th in soup.select('table th[scope="row"]'):
        name = th.get_text(strip=True)
        if name:
            full_names.add(name.lower())
    # Derive short/base names for matching
    # e.g. "ASML Netherlands B.V." → {"asml", "asml netherlands"}
    # so job feed's "ASML" still matches
    base_names: set[str] = set()
    for name in full_names:
        words = name.split()
        if words:
            clean = words[0].rstrip(',.')
            if len(clean) > 1:
                base_names.add(clean)
            if len(words) >= 2:
                clean2 = f"{words[0]} {words[1].rstrip(',.')}".lower()
                base_names.add(clean2)
    result = full_names | base_names
    print(f"  [ind] Loaded {len(full_names)} IND recognised sponsors ({len(result)} lookup keys)")
    return result


def _load_ind_sponsors() -> set[str]:
    """Load IND sponsor list from cache file, falling back to live fetch.

    Checks _IND_SPONSORS_CACHE_FILE first for fast startup. If not found
    (first run or cache cleared), fetches from the official IND register
    and writes the cache file so subsequent runs/processes reuse it.
    """
    # Try cache file first
    if os.path.exists(_IND_SPONSORS_CACHE_FILE):
        try:
            with open(_IND_SPONSORS_CACHE_FILE) as f:
                data = json.load(f)
            result = set(data)
            print(f"  [ind] Loaded {len(result)} IND sponsors from cache")
            return result
        except Exception as e:
            print(f"  [ind] Cache read failed ({e}), fetching live...")

    # Fall back to live fetch
    result = _fetch_ind_sponsors()
    if result:
        try:
            with open(_IND_SPONSORS_CACHE_FILE, "w") as f:
                json.dump(list(result), f)
            print(f"  [ind] Cached {len(result)} sponsors to {_IND_SPONSORS_CACHE_FILE}")
        except Exception as e:
            print(f"  [ind] Failed to write cache: {e}")
    return result


# Companies confirmed to support relocation / sponsor visas / have India presence
RELOCATION_FRIENDLY = {
    "guerrilla games": "Explicit relocation + immigration support",
    "backbase": "Hyderabad office - no relocation needed",
    "booking.com": "Historically strong visa sponsorship",
    "xero": "NZ visa sponsorship available",
    "halter": "NZ visa sponsorship + relocation support",
    "canonical": "100% remote - no visa needed",
    "gitlab": "100% remote - no visa needed",
    "elastic": "100% remote - no visa needed",
    "stripe": "Global remote - visa sponsorship case-by-case",
    "dropbox": "Virtual First - limited sponsorship",
    "datadog": "Global hiring - sponsorship possible",
    "coinbase": "Remote - US/global roles with limited sponsorship",
    "airbnb": "Global - sponsorship for critical roles",
    # --- German companies (61 English-friendly with visa sponsorship) ---
    "3d spark": "Germany visa sponsorship + English-friendly",
    "aampere": "Germany visa sponsorship + English-friendly",
    "ada": "Germany visa sponsorship + English-friendly",
    "adevinta": "Germany visa sponsorship + English-friendly",
    "adidas": "Germany visa sponsorship + English-friendly",
    "adjoe": "Germany visa sponsorship + English-friendly",
    "aeyde": "Germany visa sponsorship + English-friendly",
    "akeneo": "Germany visa sponsorship + English-friendly",
    "aldi south it": "Germany visa sponsorship + English-friendly",
    "amazon": "Germany visa sponsorship + English-friendly",
    "applike": "Germany visa sponsorship + English-friendly",
    "arup deutschland": "Germany visa sponsorship + English-friendly",
    "awin": "Germany visa sponsorship + English-friendly",
    "bit capital": "Germany visa sponsorship + English-friendly",
    "bmw": "Germany visa sponsorship + English-friendly",
    "babbel": "Germany visa sponsorship + English-friendly",
    "bigpoint": "Germany visa sponsorship + English-friendly",
    "billie": "Germany visa sponsorship + English-friendly",
    "black forest labs": "Germany visa sponsorship + English-friendly",
    "bolt": "Germany visa sponsorship + English-friendly",
    "bonial": "Germany visa sponsorship + English-friendly",
    "bosch": "Germany visa sponsorship + English-friendly",
    "brainlab": "Germany visa sponsorship + English-friendly",
    "celonis": "Germany visa sponsorship + English-friendly",
    "celus": "Germany visa sponsorship + English-friendly",
    "choco": "Germany visa sponsorship + English-friendly",
    "clark": "Germany visa sponsorship + English-friendly",
    "codasip": "Germany visa sponsorship + English-friendly",
    "constellr": "Germany visa sponsorship + English-friendly",
    "crytek": "Germany visa sponsorship + English-friendly",
    "dhl group": "Germany visa sponsorship + English-friendly",
    "data guard": "Germany visa sponsorship + English-friendly",
    "deepl": "Germany visa sponsorship + English-friendly",
    "delivery hero": "Germany visa sponsorship + English-friendly",
    "deutsche telekom": "Germany visa sponsorship + English-friendly",
    "dexter health": "Germany visa sponsorship + English-friendly",
    "distribusion": "Germany visa sponsorship + English-friendly",
    "doctrine": "Germany visa sponsorship + English-friendly",
    "dr. oetker": "Germany visa sponsorship + English-friendly",
    "e.on": "Germany visa sponsorship + English-friendly",
    "ecosia": "Germany visa sponsorship + English-friendly",
    "elunic": "Germany visa sponsorship + English-friendly",
    "emma - the sleep co": "Germany visa sponsorship + English-friendly",
    "innogames": "Germany visa sponsorship + English-friendly",
    "intermate group": "Germany visa sponsorship + English-friendly",
    "join": "Germany visa sponsorship + English-friendly",
    "jetbrains": "Germany visa sponsorship + English-friendly",
    "keller executive search": "Germany visa sponsorship + English-friendly",
    "limehome": "Germany visa sponsorship + English-friendly",
    "moia": "Germany visa sponsorship + English-friendly",
    "onefootball": "Germany visa sponsorship + English-friendly",
    "payabl.": "Germany visa sponsorship + English-friendly",
    "realstudio": "Germany visa sponsorship + English-friendly",
    "sap fioneer": "Germany visa sponsorship + English-friendly",
    "sony music": "Germany visa sponsorship + English-friendly",
    "speechify": "Germany visa sponsorship + English-friendly",
    "spotify": "Germany visa sponsorship + English-friendly",
    "superchat": "Germany visa sponsorship + English-friendly",
    "taxfix": "Germany visa sponsorship + English-friendly",
    "trade republic": "Germany visa sponsorship + English-friendly",
    "vivenu": "Germany visa sponsorship + English-friendly",
    "yenlo": "Germany visa sponsorship + English-friendly",
    "zalando": "Germany visa sponsorship + English-friendly",
    "monzo": "UK visa sponsorship available",
    "datasnipper": "Netherlands visa sponsorship + relocation support",
    "fastned": "Netherlands visa sponsorship + relocation support",
    "fixico": "Netherlands visa sponsorship + relocation support",
    "polarsteps": "Netherlands visa sponsorship + relocation support",
    "channable": "Netherlands visa sponsorship + relocation support",
    "picnic": "Netherlands visa sponsorship + relocation support",
    "coolblue": "Netherlands visa sponsorship + relocation support",
    "asml": "Netherlands visa sponsorship + relocation support",
    "tiqets": "Netherlands visa sponsorship + relocation support",
    "adyen": "Netherlands visa sponsorship + relocation support",
}

# Job sources to scan. Each entry: name, url, region, type (board/company/agency)
# For Greenhouse/Lever/Ashby, set ats and ats_slug for API-based fetching.
JOB_SOURCES = [
    # --- REMOTE / GLOBAL (Greenhouse companies) ---
    {"name": "GitLab", "url": "https://about.gitlab.com/jobs/all-jobs/", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "gitlab"},
    {"name": "Elastic", "url": "https://jobs.elastic.co/jobs/department/engineering?size=n_20_n", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "elastic"},
    {"name": "Stripe", "url": "https://stripe.com/jobs", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "stripe"},
    {"name": "Airbnb", "url": "https://careers.airbnb.com", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "airbnb"},
    # REMOVED: Anthropic duplicate - kept in us_canada_companies.py:14
    # {"name": "Anthropic", "url": "https://job-boards.greenhouse.io/anthropic", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "anthropic"},
    {"name": "Dropbox", "url": "https://www.dropbox.com/jobs", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "dropbox"},
    {"name": "Datadog", "url": "https://www.datadoghq.com/careers/", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "datadog"},
    {"name": "Discord", "url": "https://discord.com/careers", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "discord"},
    {"name": "Coinbase", "url": "https://www.coinbase.com/careers", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "coinbase"},
    {"name": "Reddit", "url": "https://www.redditinc.com/careers", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "reddit"},
    {"name": "Lyft", "url": "https://www.lyft.com/careers#openings", "region": "US", "type": "company", "playwright": True},
    {"name": "Monzo", "url": "https://monzo.com/careers", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "monzo"},
    {"name": "Adyen", "url": "https://careers.adyen.com/vacancies", "region": "EU", "type": "company", "ats": "greenhouse", "ats_slug": "adyen"},
    {"name": "OpenSRE", "url": "https://jobs.ashbyhq.com/tracer", "region": "Global", "type": "company", "ats": "ashby", "ats_slug": "tracer"},
    {"name": "Pinterest", "url": "https://www.pinterestcareers.com", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "pinterest"},
    {"name": "Preply", "url": "https://jobs.ashbyhq.com/preply", "region": "Global", "type": "company", "ats": "ashby", "ats_slug": "preply"},
    {"name": "Instacart", "url": "https://instacart.careers", "region": "US", "type": "company", "ats": "greenhouse", "ats_slug": "instacart"},
    {"name": "Webflow", "url": "https://webflow.com/jobs", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "webflow"},
    {"name": "Upwork", "url": "https://www.upwork.com/careers", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "upwork"},
    {"name": "Betterment", "url": "https://www.betterment.com/careers", "region": "US", "type": "company", "ats": "greenhouse", "ats_slug": "betterment"},
    {"name": "GoDaddy", "url": "https://careers.godaddy.com", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "godaddy"},
    # REMOVED: Vercel duplicate - kept in us_canada_companies.py:27
    # {"name": "Vercel", "url": "https://vercel.com/careers", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "vercel"},
    {"name": "Meta (Facebook)", "url": "https://www.metacareers.com/", "region": "Global", "type": "company", "playwright": True},
    # --- IT Services / Enterprise (some SAP/ERP relevance) ---
    {"name": "TCS", "url": "https://www.tcs.com/careers", "region": "IN", "type": "company", "playwright": True},
    # --- EU / NL / DE ---
    {"name": "Mollie", "url": "https://jobs.mollie.com/vacancies", "region": "NL", "type": "company", "playwright": True},
    {"name": "Booking.com", "url": "https://jobs.booking.com/booking/jobs?keywords=engineer", "region": "NL", "type": "company", "playwright": True},
    {"name": "Picnic Technologies", "url": "https://jobs.picnic.app/en/vacancies", "region": "EU", "type": "company", "playwright": True},
    {"name": "Personio", "url": "https://www.personio.com/about-personio/careers/#see-our-open-roles", "region": "DE", "type": "company", "playwright": True},
    # --- Germany (61 English-speaking companies with visa sponsorship) ---
    {"name": "3D Spark", "url": "https://www.3dspark.de/career#Job-Offers", "region": "DE", "type": "company", "playwright": True},
    {"name": "Aampere", "url": "https://amperecomputing.com/careers", "region": "DE", "type": "company", "playwright": True},
    {"name": "Ada", "url": "https://adaglobal.darwinbox.com/ms/candidatev2/main/careers/allJobs", "region": "DE", "type": "company", "playwright": True},
    {"name": "Adevinta", "url": "https://adevinta.com/careers/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Aeyde", "url": "https://aeyde.jobs.personio.de/", "region": "DE", "type": "company", "ats": "personio"},
    {"name": "Adidas", "url": "https://careers.adidas-group.com/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Adjoe", "url": "https://adjoe.io/careers/open-positions/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Akeneo", "url": "https://careers.akeneo.com/jobs", "region": "DE", "type": "company", "ats": "teamtailor"},
    {"name": "Amazon", "url": "https://www.amazon.jobs/content/en/job-categories", "region": "DE", "type": "company", "playwright": True},
    {"name": "Applike", "url": "https://applike-group.com/jobs/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Arup Deutschland", "url": "https://jobs.arup.com/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Awin", "url": "https://www.awin.com/gb/careers/vacancies", "region": "DE", "type": "company", "ats": "greenhouse", "ats_slug": "awin"},
    {"name": "BIT Capital", "url": "https://bitcap.com/en/karriere", "region": "DE", "type": "company", "playwright": True},
    {"name": "BMW", "url": "https://www.bmwgroup.jobs/en.html", "region": "DE", "type": "company", "playwright": True},
    {"name": "Babbel", "url": "https://jobs.babbel.com/en?size=n_3_n", "region": "DE", "type": "company", "playwright": True},
    {"name": "Bigpoint", "url": "https://bigpoint.jobs.personio.de/", "region": "DE", "type": "company", "ats": "personio"},
    {"name": "Billie", "url": "https://www.billie.io/en/jobs", "region": "DE", "type": "company", "playwright": True},
    {"name": "Black Forest Labs", "url": "https://bfl.ai/careers", "region": "DE", "type": "company", "ats": "greenhouse", "ats_slug": "blackforestlabs"},
    {"name": "Bolt", "url": "https://bolt.eu/en/careers/positions/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Bonial", "url": "https://bonial.recruitee.com/", "region": "DE", "type": "company", "ats": "recruitee", "ats_slug": "bonial"},
    {"name": "Bosch", "url": "https://www.bosch.de/karriere/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Brainlab", "url": "https://www.brainlab.com/career/jobs/?country=germany", "region": "DE", "type": "company", "ats": "smartrecruiters", "ats_slug": "Brainlab"},
    {"name": "Celonis", "url": "https://careers.celonis.com/join-us/open-positions", "region": "DE", "type": "company", "playwright": True},
    {"name": "Celus", "url": "https://join.com/companies/contunity", "region": "DE", "type": "company", "playwright": True},
    {"name": "Choco", "url": "https://jobs.ashbyhq.com/choco", "region": "DE", "type": "company", "ats": "ashby", "ats_slug": "choco"},
    {"name": "Clark", "url": "https://clark.jobs.personio.de/", "region": "DE", "type": "company", "ats": "personio"},
    {"name": "Codasip", "url": "https://codasip.bamboohr.com/careers", "region": "DE", "type": "company", "ats": "bamboohr", "ats_slug": "codasip"},
    {"name": "Constellr", "url": "https://constellr.recruitee.com/", "region": "DE", "type": "company", "ats": "recruitee", "ats_slug": "constellr"},
    {"name": "Crytek", "url": "https://www.crytek.com/career", "region": "DE", "type": "company", "playwright": True},
    {"name": "Danske Commodities", "url": "https://danskecommodities.com/careers/vacancies", "region": "DE", "type": "company", "playwright": True},
    {"name": "Data Guard", "url": "https://www.dataguard.com/careers/jobs/", "region": "DE", "type": "company", "ats": "ashby", "ats_slug": "dataguard"},
    {"name": "DeepL", "url": "https://jobs.ashbyhq.com/DeepL", "region": "DE", "type": "company", "ats": "ashby", "ats_slug": "DeepL"},
    {"name": "Delivery Hero", "url": "https://careers.deliveryhero.com/jobs", "region": "DE", "type": "company", "playwright": True},
    {"name": "Deutsche Telekom", "url": "https://careers.telekom.com/en/jobs", "region": "DE", "type": "company", "playwright": True},
    {"name": "Dexter Health", "url": "https://join.com/companies/dexter-health", "region": "DE", "type": "company", "playwright": True},
    {"name": "Distribusion", "url": "https://distribusion.recruitee.com/", "region": "DE", "type": "company", "ats": "recruitee"},
    {"name": "Doctrine", "url": "https://jobs.lever.co/doctrine", "region": "DE", "type": "company", "ats": "lever", "ats_slug": "doctrine"},
    {"name": "Dr. Oetker", "url": "https://www.oetker.de/karriere", "region": "DE", "type": "company", "playwright": True},
    {"name": "Dynatrace", "url": "https://www.dynatrace.com/careers/jobs/", "region": "DE", "type": "company", "playwright": True},
    {"name": "eDreams ODIGEO", "url": "https://www.edreamsodigeocareers.com/jobs/", "region": "DE", "type": "company", "playwright": True},
    {"name": "E.ON", "url": "https://jobs.eon.com/en?jobField=Engineering", "region": "DE", "type": "company", "playwright": True},
    {"name": "Ecosia", "url": "https://jobs.ashbyhq.com/ecosia.org", "region": "DE", "type": "company", "ats": "ashby", "ats_slug": "ecosia"},
    {"name": "Elunic", "url": "https://jobs.elunic.com/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Emma - The Sleep Co", "url": "https://jobs.lever.co/emma-sleep", "region": "DE", "type": "company", "ats": "lever", "ats_slug": "emma-sleep"},
    {"name": "InnoGames", "url": "https://www.innogames.com/career/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Intermate Group", "url": "https://intermategroupgmbh.recruitee.com/", "region": "DE", "type": "company", "ats": "recruitee", "ats_slug": "intermategroupgmbh"},
    {"name": "JOIN", "url": "https://join.com/companies/join", "region": "DE", "type": "company", "playwright": True},
    {"name": "JetBrains", "url": "https://job-boards.eu.greenhouse.io/jetbrains", "region": "DE", "type": "company", "ats": "greenhouse", "ats_slug": "jetbrains"},
    {"name": "Keller Executive Search", "url": "https://kellerexecutivesearch.com/careers/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Limehome", "url": "https://limehome.recruitee.com/", "region": "DE", "type": "company", "ats": "recruitee"},
    {"name": "MOIA", "url": "https://www.moia.io/en/career", "region": "DE", "type": "company", "ats": "greenhouse", "ats_slug": "moia"},
    {"name": "Nexthink", "url": "https://nexthink.com/company/careers/jobs", "region": "DE", "type": "company", "playwright": True},
    {"name": "OneFootball", "url": "https://onefootball.applytojob.com/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Payabl.", "url": "https://apply.workable.com/payabl/", "region": "DE", "type": "company", "ats": "workable", "ats_slug": "payabl"},
    {"name": "SAP Fioneer", "url": "https://apply.workable.com/fioneer/#jobs", "region": "DE", "type": "company", "ats": "workable", "ats_slug": "fioneer"},
    {"name": "Sony Music", "url": "https://careers.sonymusic.com/jobs", "region": "DE", "type": "company", "playwright": True},
    {"name": "Speechify", "url": "https://speechify.com/careers/#open-positions", "region": "DE", "type": "company", "playwright": True},
    {"name": "Spotify", "url": "https://www.lifeatspotify.com/jobs", "region": "DE", "type": "company", "ats": "spotify"},
    {"name": "Superchat", "url": "https://www.superchat.com/careers/#openings", "region": "DE", "type": "company", "playwright": True},
    {"name": "Taxfix", "url": "https://taxfix.de/en/job-openings/", "region": "DE", "type": "company", "ats": "ashby", "ats_slug": "taxfix.com"},
    {"name": "Trade Republic", "url": "https://traderepublic.com/en-de/about#career", "region": "DE", "type": "company", "playwright": True},
    {"name": "Vivenu", "url": "https://jobs.lever.co/vivenu", "region": "DE", "type": "company", "ats": "lever", "ats_slug": "vivenu"},
    {"name": "Wolt", "url": "https://job-boards.greenhouse.io/wolt", "region": "DE", "type": "company", "ats": "greenhouse", "ats_slug": "wolt"},
    {"name": "Yenlo", "url": "https://www.yenlo.com/careers/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Zalando", "url": "https://jobs.zalando.com/en/jobs", "region": "DE", "type": "company", "playwright": True},
]

RECRUITER_AGENCIES = [
    {"name": "Hays Europe", "url": "https://www.hays.nl"},
    # REMOVED: Spring Professional - LinkedIn URL always skipped at runtime
    # {"name": "Spring Professional", "url": "https://linkedin.com/company/springprofessional"},
    {"name": "Michael Page", "url": "https://www.michaelpage.nl"},
    {"name": "Randstad", "url": "https://www.randstad.nl"},
    {"name": "Robert Half", "url": "https://www.roberthalf.nl"},
    {"name": "Darwin Recruitment", "url": "https://www.darwinrecruitment.com"},
]

RESUME_VERSIONS = {
    "faang": "Kamnee_Maran_Resume_FAANG.pdf",
    "indian_tech": "Kamnee_Maran_Resume_IndianTech.pdf",
    "general": "Kamnee_Maran_Resume_v2.pdf",
    "pradeep": "CV_Pradeep_SAP MM.pdf",
}

# Map companies to resume version (extend this as you add companies)
COMPANY_RESUME_MAP = {
    "picnic": "faang", "booking.com": "faang", "bol.com": "faang",
    "guerrilla games": "faang", "mollie": "faang", "just eat takeaway": "faang",
    "raisin": "faang", "solaris": "faang", "sumup": "faang", "celonis": "faang",
    "personio": "faang", "gitlab": "faang", "elastic": "faang",
    "hashicorp": "faang", "canonical": "faang", "atlassian": "faang",
    "xero": "faang", "halter": "faang",
    "backbase": "faang",
}


# ---------------------------------------------------------------------------
# 2. FIT SCORING
# ---------------------------------------------------------------------------

# Seniority prefixes to strip when extracting base role
_SENIORITY_PREFIXES = ["senior ", "sr. ", "sr ", "lead ", "staff ", "principal ", "junior ", "associate ", "chief "]

# --- Precompiled regex patterns (avoid re-compiling per job in score_job) ---
# These are rebuilt by _rebuild_precompiled_patterns() whenever PROFILE is
# mutated (e.g. via --resume or --profile).  Initial build uses the default
# hardcoded PROFILE so standalone imports still work.
_JUNIOR_RE = []
_TITLE_RED_FLAG_RE = []
_SKILL_RE = []
_EXP_PATTERNS = [
    (re.compile(r'(\d+)\+?\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)'), 'min'),
    (re.compile(r'(?:min|minimum|at least|≥)\s*(\d+)\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)'), 'min'),
    (re.compile(r'(?:max|maximum|up to|≤)\s*(\d+)\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)'), 'max'),
    (re.compile(r'(\d+)\s*(?:to|-|–)\s*(\d+)\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)'), 'range'),
    (re.compile(r'(\d+)\s*-\s*(\d+)\s*(?:yrs?|years?)\s*(?:of\s+)?(?:exp|experience|professional|relevant|work)'), 'range'),
]
_TRAVEL_HEAVY_RE = re.compile(r'(\d+)\s*%\s*travel')
_TRAVEL_MANDATORY_RE = [re.compile(p) for p in [
    r'must be willing to travel', r'overnight travel',
    r'require[sd]?\s+travel\s+(?:extensively|frequently|regularly)',
    r'extensive\s+travel', r'frequent\s+travel',
]]
# Cache title keywords and seniority keywords — invalidated by _rebuild_precompiled_patterns()
_CACHED_TITLE_KEYWORDS = None
_CACHED_SENIORITY_KEYWORDS = None


def _rebuild_precompiled_patterns():
    """Rebuild all precompiled regex patterns and caches from current PROFILE.

    MUST be called after any mutation of PROFILE (--resume, --profile, CLI overrides).
    """
    global _JUNIOR_RE, _TITLE_RED_FLAG_RE, _SKILL_RE, _CORE_SKILL_RE, _BONUS_SKILL_RE
    global _CACHED_TITLE_KEYWORDS, _CACHED_SENIORITY_KEYWORDS

    _JUNIOR_RE = [re.compile(r'(?<![a-z])' + re.escape(flag) + r'(?![a-z])')
                  for flag in PROFILE["junior_red_flags"]]
    _TITLE_RED_FLAG_RE = [(flag.strip(), re.compile(r'(?<![a-z])' + re.escape(flag.strip()) + r'(?![a-z])'))
                          for flag in PROFILE["title_red_flags"]]
    
    TECH_ALIASES = {
        "node.js": ["node.js", "nodejs", "node-js", r"node\s+js"],
        "ci/cd": ["ci/cd", "cicd", "ci-cd", "continuous integration"],
        "system design": ["system design", "system-design"],
        "distributed systems": ["distributed systems", "distributed-systems"],
        "fastapi": ["fastapi", "fast-api", r"fast\s+api"],
        "spring boot": ["spring boot", "springboot", "spring-boot"],
        "mysql": ["mysql", "my-sql", r"my\s+sql"],
        "postgresql": ["postgresql", "postgres"],
    }

    def _compile_skill_pattern(skill):
        sk_lower = skill.lower()
        if sk_lower in TECH_ALIASES:
            joint_pattern = '|'.join(TECH_ALIASES[sk_lower])
            return re.compile(r'\b(' + joint_pattern + r')\b', re.IGNORECASE)
        return re.compile(r'\b' + re.escape(skill) + r'\b', re.IGNORECASE)

    # Complete list of skills for backwards compatibility
    _SKILL_RE = [(skill, _compile_skill_pattern(skill))
                 for skill in PROFILE["core_skills"]]

    # Split core_skills into Primary (Core) vs Auxiliary (Bonus)
    primary_tech_terms = {
        "java", "python", "node.js", "golang", "go", "c++", "c#", "ruby", "typescript",
        "system design", "distributed systems", "microservices", "architecture", "api", "apis",
        "backend", "back-end", "database design", "datastructures", "algorithms",
        "sap mm", "sap ewm", "sap wm", "materials management", "warehouse management",
        "extended warehouse management"
    }

    core_skills_list = []
    bonus_skills_list = []

    for skill in PROFILE["core_skills"]:
        sk_lower = skill.lower()
        if sk_lower in primary_tech_terms:
            core_skills_list.append(skill)
        else:
            bonus_skills_list.append(skill)

    # Ensure we always have at least some core skills
    if len(core_skills_list) < max(4, int(len(PROFILE["core_skills"]) * 0.3)):
        split_idx = max(4, int(len(PROFILE["core_skills"]) * 0.35))
        core_skills_list = PROFILE["core_skills"][:split_idx]
        bonus_skills_list = PROFILE["core_skills"][split_idx:]

    _CORE_SKILL_RE = [(skill, _compile_skill_pattern(skill))
                      for skill in core_skills_list]
    _BONUS_SKILL_RE = [(skill, _compile_skill_pattern(skill))
                       for skill in bonus_skills_list]

    # Invalidate cached derived values so they're recomputed from updated PROFILE
    _CACHED_TITLE_KEYWORDS = None
    _CACHED_SENIORITY_KEYWORDS = None


# Initial build from default hardcoded PROFILE
_rebuild_precompiled_patterns()


def _get_cached_title_keywords():
    global _CACHED_TITLE_KEYWORDS
    if _CACHED_TITLE_KEYWORDS is None:
        _CACHED_TITLE_KEYWORDS = _derive_title_keywords(
            PROFILE.get("current_role", ""), PROFILE["years_experience"])
    return _CACHED_TITLE_KEYWORDS


def _get_cached_seniority_keywords():
    global _CACHED_SENIORITY_KEYWORDS
    if _CACHED_SENIORITY_KEYWORDS is None:
        _CACHED_SENIORITY_KEYWORDS = _get_seniority_keywords(PROFILE["years_experience"])
    return _CACHED_SENIORITY_KEYWORDS


def _derive_title_keywords(current_role, years_experience):
    """
    From a resume's current_role + years of experience, derive title keywords
    for scoring JD titles. Returns list of keyword phrases to match.
    """
    if not current_role:
        return []
    role_lower = current_role.lower().strip()

    # Strip pipe-separated extras (e.g., "Senior Engineer | Team Lead" → "Senior Engineer")
    if "|" in role_lower:
        role_lower = role_lower.split("|")[0].strip()

    # Normalize hyphens to spaces (e.g., "full-stack" → "full stack")
    role_lower = role_lower.replace("-", " ")

    # Normalize special characters: em-dashes, en-dashes, ampersands, pipes, slashes
    # e.g., "Software Engineer – Backend & Distributed Systems" → "software engineer backend distributed systems"
    role_lower = re.sub(r'[–—&|/\\,;:()]', ' ', role_lower)
    role_lower = re.sub(r'\s+', ' ', role_lower).strip()

    # Strip seniority prefix to get base role (e.g., "software engineer" from "Senior Software Engineer")
    base_role = role_lower
    for prefix in _SENIORITY_PREFIXES:
        if base_role.startswith(prefix):
            base_role = base_role[len(prefix):]
            break

    keywords = [base_role]  # always match base role

    # Extract meaningful sub-role variants from compound roles
    # e.g., "software engineer backend distributed systems" →
    #   also generate "backend engineer", "backend developer",
    #   "software engineer", "software developer"
    _role_words = {"engineer", "developer", "consultant", "architect", "lead"}
    base_parts = base_role.split()
    if len(base_parts) > 2:
        # Find the role noun (engineer/developer/etc.)
        role_noun = None
        for w in base_parts:
            if w in _role_words:
                role_noun = w
                break
        if role_noun:
            # Add each domain word + role_noun as a variant
            for w in base_parts:
                if w != role_noun and len(w) > 2:
                    variant = f"{w} {role_noun}"
                    if variant not in keywords:
                        keywords.append(variant)
                    # Also add engineer ↔ developer equivalents
                    if role_noun == "engineer":
                        alt = f"{w} developer"
                    elif role_noun == "developer":
                        alt = f"{w} engineer"
                    else:
                        alt = None
                    if alt and alt not in keywords:
                        keywords.append(alt)

    # Add "developer" ↔ "engineer" equivalents for base role
    if "engineer" in base_role:
        dev_variant = base_role.replace("engineer", "developer")
        keywords.append(dev_variant)
    elif "developer" in base_role:
        eng_variant = base_role.replace("developer", "engineer")
        keywords.append(eng_variant)

    # Add seniority variants based on experience level
    if years_experience >= 10:
        keywords.extend([f"senior {base_role}", f"staff {base_role}", f"lead {base_role}",
                         f"principal {base_role}", "sde-3", "sde 3", "sde-4", "sde 4", "sde-5"])
    elif years_experience >= 5:
        keywords.extend([f"senior {base_role}", f"lead {base_role}"])
    elif years_experience >= 3:
        keywords.append(f"senior {base_role}")
    # For <3 years, only base role matches

    # Add related role variants derived from core_skills
    # Maps skill keywords → additional title variants to match
    _skill_role_map = {
        "java": ["java engineer", "java developer", "java software engineer", "java developer engineer"],
        "python": ["python engineer", "python developer", "python software engineer"],
        "golang": ["go engineer", "go developer", "golang engineer", "golang developer"],
        "backend": ["backend engineer", "backend developer", "back end engineer", "back-end engineer"],
        "platform": ["platform engineer"],
        "cloud infrastructure": ["cloud engineer", "infrastructure engineer"],
        "distributed systems": ["systems engineer", "distributed systems engineer"],
        "microservices": ["backend engineer", "backend developer"],
        "api development": ["api engineer", "api developer"],
        "data pipelines": ["data platform engineer"],
        "devops": ["platform engineer", "infrastructure engineer"],
        "system design": ["systems architect"],
        "sap mm": ["sap mm consultant", "sap mm lead", "sap materials management consultant"],
        "sap ewm": ["sap ewm consultant", "sap ewm lead", "sap warehouse management consultant"],
        "sap wm": ["sap wm consultant", "sap wm lead"],
        "sap s/4hana": ["sap s/4hana consultant", "sap s/4hana lead", "sap s4hana consultant", "sap s4hana lead"],
        # NOTE: generic "sap" deliberately does NOT map to "sap consultant" — too broad,
        # would bypass any SAP module (Ariba, EHS, FICO, etc.) to 72 via _title_only_bypass.
        "erp": ["erp consultant", "erp lead"],
        "procurement": ["procurement consultant", "procurement lead"],
    }
    core_skills = PROFILE.get("core_skills", [])
    for skill, role_variants in _skill_role_map.items():
        if skill in core_skills:
            for variant in role_variants:
                if variant not in keywords:
                    keywords.append(variant)

    # Add individual meaningful words from base role (for partial title matches)
    # e.g., "sap consultant" → also match titles containing "consultant"
    # Skip generic words that would match too broadly
    _generic_words = {"engineer", "developer", "manager", "lead", "senior", "junior", "specialist", "analyst", "consultant"}
    role_words = [w for w in base_role.split() if len(w) > 3 and w not in _generic_words]
    for word in role_words:
        if word not in keywords:
            keywords.append(word)

    return keywords


def _get_seniority_keywords(years_experience):
    """Return appropriate seniority keywords based on years of experience."""
    if years_experience >= 10:
        return ["senior", "staff", "lead", "principal", "sde-3", "sde 3", "sde-4", "sde 4"]
    elif years_experience >= 5:
        return ["senior", "lead", "experienced"]
    elif years_experience >= 3:
        return ["mid", "intermediate"]
    else:
        return []  # No seniority bonus for <3 years

def score_job(title, description, company, location=""):
    """
    Returns (score 0-100, note string).
    For roles outside India: visa sponsorship & relocation support are mandatory.
    """
    text = (title + " " + description).lower()
    title_lower = title.lower()
    loc_lower = location.lower()

    if any(pat.search(text) for pat in _JUNIOR_RE):
        return 0, "Filtered: junior/entry-level role detected"

    # Check if title matches red-flag career tracks (word-boundary matching).
    # Instead of hard-rejecting, flag it — if skill overlap is high enough later,
    # we let the job through (some companies title backend roles as "DevOps", etc.)
    red_flag_match = None
    for red_flag, pat in _TITLE_RED_FLAG_RE:
        if pat.search(title_lower):
            red_flag_match = red_flag
            break

    # --- Seniority filter: reject roles too senior for candidate's experience ---
    exp_years = PROFILE["years_experience"]
    senior_patterns = [
        (["vice president", "vp ", " vp,", "vp of", "rvp ", "svp ", "evp ", "chief ", "cfo", "cto", "ceo",
          "head of"], 12),
        (["director", "senior director", "managing director", "associate director"], 8),
        (["principal", "staff", "senior manager"], 5),
        (["senior ", "lead ", "manager ", "head "], 3),
    ]
    for patterns, min_exp in senior_patterns:
        if exp_years < min_exp:
            for pat in patterns:
                # Use word-boundary check to avoid substring false positives (e.g. "cto" in "vector")
                if re.search(r'(?<![a-z])' + re.escape(pat.strip()) + r'(?![a-z])', title_lower):
                    return 0, f"Filtered: too senior ({pat.strip()}) for {exp_years}yr profile"

    # --- Experience range filter: match JD's explicit experience requirements ---
    # If resume says X years, consider jobs requiring X-4 to X+3 years
    max_allowed = exp_years + 3
    min_allowed = max(0, exp_years - 4)
    for pattern, ptype in _EXP_PATTERNS:
        matches = pattern.findall(text)
        for m in matches:
            if ptype == 'min':
                req = int(m)
                if req > max_allowed:
                    return 0, f"Filtered: requires {req}+yr, candidate max {max_allowed}"
            elif ptype == 'max':
                req = int(m)
                if req < min_allowed:
                    return 0, f"Filtered: max {req}yr, candidate min {min_allowed}"
            elif ptype == 'range':
                lo, hi = int(m[0]), int(m[1])
                if lo > max_allowed or hi < min_allowed:
                    return 0, f"Filtered: requires {lo}-{hi}yr, candidate range {min_allowed}-{max_allowed}"

    # --- Reject roles requiring significant travel (>25%) or mandatory travel ---
    travel_pct_match = _TRAVEL_HEAVY_RE.search(text)
    if travel_pct_match and int(travel_pct_match.group(1)) > 25:
        return 0, f"Filtered: role requires {travel_pct_match.group(1)}% travel"
    if any(p.search(text) for p in _TRAVEL_MANDATORY_RE):
        return 0, "Filtered: role requires significant travel"

    # --- For roles outside India / Remote: visa & relocation assessment ---
    _INDIA_MARKERS = ["india", "pune", "mumbai", "bangalore", "bengaluru", "hyderabad",
                      "chennai", "delhi", "gurgaon", "gurugram", "noida", "kolkata",
                      "ahmedabad", "jaipur", "thiruvananthapuram", "kochi", "coimbatore"]
    is_outside_india = not any(m in loc_lower or m in text for m in _INDIA_MARKERS)
    is_remote = any(kw in loc_lower or kw in text for kw in ["remote", "work from home", "wfh", "virtual"])
    visa_note = ""
    has_visa_relo = False
    has_visa_sponsor = False
    has_relo_support = False
    in_friendly_list = False
    in_ind_sponsor = False

    if is_outside_india or is_remote:
        company_lower = company.lower()

        # Hard reject: company known to NOT sponsor/relocate
        in_blocked_list = any(co in company_lower for co in NO_RELOCATION_FLAGS)
        if in_blocked_list:
            note = next(NO_RELOCATION_FLAGS[c] for c in NO_RELOCATION_FLAGS if c in company_lower)
            return 0, f"No visa/relocation: {note}"

        # Hard reject: JD explicitly says no sponsorship
        if any(kw in text for kw in NO_SPONSORSHIP_KEYWORDS):
            return 0, "Filtered: job explicitly states no visa sponsorship"

        # Hard reject: non-English language required (and English not mentioned)
        if any(lang_kw in text for lang_kw in NON_ENGLISH_LANGUAGE_KEYWORDS):
            if "english" not in text:
                return 0, "Filtered: non-English language requirement detected"

        # Detect visa sponsorship and relocation support independently
        has_visa_sponsor = any(kw in text for kw in VISA_SPONSORSHIP_KEYWORDS)
        has_relo_support = any(kw in text for kw in RELOCATION_SUPPORT_KEYWORDS)
        has_visa_relo = has_visa_sponsor or has_relo_support
        in_friendly_list = any(co in company_lower for co in RELOCATION_FRIENDLY)
        # Check IND registered sponsors (Netherlands)
        in_ind_sponsor = company_lower in _IND_SPONSORS
        if not in_ind_sponsor:
            fw = company_lower.split()[0] if company_lower.split() else ""
            in_ind_sponsor = fw in _IND_SPONSORS
        has_sponsor_signal = has_visa_sponsor or in_friendly_list or in_ind_sponsor
        has_relo_signal = has_relo_support or in_friendly_list or in_ind_sponsor
        if has_visa_relo or in_friendly_list or in_ind_sponsor:
            parts = []
            if has_sponsor_signal:
                src = []
                if has_visa_sponsor: src.append("JD")
                if in_friendly_list: src.append("known list")
                if in_ind_sponsor: src.append("IND register")
                parts.append(f"Visa sponsorship ({'+'.join(src)})")
            if has_relo_signal:
                src = []
                if has_relo_support: src.append("JD")
                if in_friendly_list: src.append("known list")
                if in_ind_sponsor: src.append("IND register")
                parts.append(f"Relocation support ({'+'.join(src)})")
            visa_note = " + ".join(parts)
        else:
            visa_note = "Visa sponsorship details not mentioned"

    # --- Industry detection: auto-bias scoring for SAP vs non-SAP ---
    is_sap_profile = any("sap" in s.lower() or "erp" in s.lower() for s in PROFILE["core_skills"][:5])
    text_has_sap = "sap" in text or "erp" in text or "s/4hana" in text or "s4hana" in text
    if is_sap_profile and not text_has_sap:
        return 0, "Filtered: non-SAP/ERP role for SAP profile"

    # --- SAP module matching (relaxed: standalone module names count too) ---
    # Use a separate variable for SAP-normalized title to avoid mutating title_lower
    # (which is needed unmodified for title relevance scoring later)
    sap_title = title.lower().replace("-", " ").replace("/", " ")
    sap_title = re.sub(r'[()\[\]{}]', ' ', sap_title)
    sap_title = re.sub(r'\s+', ' ', sap_title).strip()
    has_sap_skills = any("sap" in s or "abap" in s for s in PROFILE["core_skills"])

    _SAP_MODULE_ALIASES = {
        "sap mm": [
            r"materials?\s+management", r"material\s+management",
            r"procurement", r"sourcing\s+(?:and|&)\s+procurement",
            r"sourcing\s+and\s+procurement", r"sap\s+procurement",
            r"supply\s+chain", r"scm", r"logistics"
        ],
        "sap ewm": [r"extended\s+warehouse\s+management", r"ewm"],
        "sap wm": [r"warehouse\s+management", r"wm"],
        "sap qm": [r"quality\s+management", r"qm"],
        "sap pp": [r"production\s+planning", r"pp", r"manufacturing"],
        "sap sd": [r"sales\s+(?:and|&)\s+distribution", r"sales\s+and\s+distribution", r"sd", r"order\s+to\s+cash", r"otc"],
        "sap pm": [r"plant\s+maintenance", r"pm", r"asset\s+management", r"eam"],
        "sap fi": [r"financial\s+accounting", r"fi", r"finance", r"financials"],
        "sap co": [r"controlling", r"co"],
        "sap hcm": [r"human\s+capital\s+management", r"hcm", r"hr", r"human\s+resources"],
        "sap successfactors": [r"successfactors", r"success\s+factors"],
        "sap trm": [r"treasury", r"trm", r"treasury\s+and\s+risk", r"treasury\s+(?:and|&)\s+risk", r"treasury\s+risk\s+management"],
        "sap ps": [r"project\s+system", r"ps"],
        "sap mdg": [r"master\s+data\s+governance", r"mdg"],
        "sap integration": [r"integration", r"cpi", r"pi/po", r"po/pi", r"btp"],
        "sap tm": [r"transportation\s+management", r"tm"],
        "sap ariba": [r"ariba"],
        "sap data migration": [r"data\s+migration"],
        "sap service": [r"\bservice\b", r"\bcs\b"],
        "sap cloud platform": [r"\bcloud\s+public\b", r"\bpublic\s+edition\b"]
    }

    _known_modules = [
        "sap mm", "sap sd", "sap fi", "sap co", "sap hr", "sap hcm",
        "sap payroll", "sap successfactors", "sap s/4hana", "sap s4hana",
        "sap abap", "sap basis", "sap bi", "sap bw", "sap fiori",
        "sap hana", "sap pp", "sap qm", "sap pm", "sap fico",
        "sap ewm", "sap wm", "sap trm", "sap eam", "sap ps", "sap mdg",
        "sap integration", "sap pi", "sap po", "sap cpi", "sap btp",
        "sap security", "sap grc", "sap ariba", "sap tm", "sap data migration",
        "sap service", "sap cloud platform"
    ]

    _standalone_modules = {
        "mm": "sap mm", "ewm": "sap ewm", "wm": "sap wm", "sd": "sap sd",
        "fi": "sap fi", "co": "sap co", "fico": "sap fico",
        "hr": "sap hr", "hcm": "sap hcm", "pp": "sap pp",
        "qm": "sap qm", "pm": "sap pm", "abap": "sap abap",
        "basis": "sap basis", "s/4hana": "sap s/4hana", "s4hana": "sap s4hana",
        "fiori": "sap fiori", "hana": "sap hana", "bi": "sap bi", "bw": "sap bw",
        "successfactors": "sap successfactors", "payroll": "sap payroll",
        "trm": "sap trm", "treasury": "sap trm", "eam": "sap eam", "ps": "sap ps",
        "mdg": "sap mdg", "ariba": "sap ariba", "tm": "sap tm",
        "cpi": "sap cpi", "btp": "sap btp", "data migration": "sap data migration",
        "service": "sap service", "cloud public": "sap cloud platform", "public edition": "sap cloud platform"
    }

    sap_module_mismatch = False
    if has_sap_skills:
        profile_sap_modules = {s.lower() for s in PROFILE["core_skills"] if "sap" in s or s.lower() in ("materials management", "warehouse management", "extended warehouse management", "procurement", "sourcing", "logistics", "supply chain")}
        # Map our profile skills properly to standardized module names
        for skill in list(profile_sap_modules):
            if skill in ("materials management", "procurement", "sourcing"):
                profile_sap_modules.add("sap mm")
            elif skill in ("warehouse management",):
                profile_sap_modules.add("sap wm")
            elif skill in ("extended warehouse management",):
                profile_sap_modules.add("sap ewm")
            elif skill in ("logistics", "supply chain"):
                profile_sap_modules.add("sap mm")
                profile_sap_modules.add("sap ewm")

        # Now extract modules from the title using aliases, known modules, and standalone modules
        title_modules = {m for m in _known_modules if re.search(r'\b' + re.escape(m) + r'\b', sap_title)}
        for standalone, mapped in _standalone_modules.items():
            if re.search(r'\b' + re.escape(standalone) + r'\b', sap_title):
                title_modules.add(mapped)
        for mod, aliases in _SAP_MODULE_ALIASES.items():
            for alias_pat in aliases:
                if re.search(alias_pat, sap_title, re.IGNORECASE):
                    title_modules.add(mod)
                    break

        if title_modules:
            # Generic/platform keywords should not override a mismatch
            specific_title_modules = title_modules - {"sap s/4hana", "sap s4hana", "sap hana", "sap"}
            profile_specific = profile_sap_modules - {"sap s/4hana", "sap s4hana", "sap hana", "sap"}
            if specific_title_modules and not (specific_title_modules & profile_specific):
                return 0, f"Filtered: title matches non-relevant SAP module ({', '.join(sorted(specific_title_modules))})"

    # --- Skill scoring (word-boundary matching; Core: up to 35 points, Bonus: up to 15 points) ---
    core_hits = sum(1 for _, pat in _CORE_SKILL_RE if pat.search(text))
    bonus_hits = sum(1 for _, pat in _BONUS_SKILL_RE if pat.search(text))

    # Relaxed SAP module matching (adds to core_hits)
    if has_sap_skills:
        for sap_skill in PROFILE["core_skills"]:
            if "sap " in sap_skill.lower():
                module_part = sap_skill.lower().replace("sap ", "", 1).strip()
                if module_part and module_part not in ("s/4hana", "s4hana"):
                    if re.search(r'\b' + re.escape(module_part) + r'\b', text):
                        core_hits += 1
                        break  # at most one extra point from this relaxation
    if has_sap_skills:
        for sap_skill in PROFILE["core_skills"]:
            sk = sap_skill.lower()
            if sk in _SAP_MODULE_ALIASES:
                for alias_pat in _SAP_MODULE_ALIASES[sk]:
                    if re.search(alias_pat, text, re.IGNORECASE):
                        core_hits += 1
                        break  # one extra hit per module alias
    # Also count supply chain / logistics as adjacent hits for MM/EWM profiles
    if has_sap_skills and any(s in PROFILE["core_skills"] for s in ("sap mm", "sap ewm", "sap wm")):
        for adj_pat in [r"supply\s+chain", r"\blogistics?\b", r"procure.to.pay", r"\bscm\b"]:
            if re.search(adj_pat, text, re.IGNORECASE):
                core_hits += 1
                break  # at most one adjacent hit

    core_total = len(_CORE_SKILL_RE)
    bonus_total = len(_BONUS_SKILL_RE)

    # Scale core and bonus denominators based on description length (prevents snippet penalties)
    # Capped to a small, realistic maximum (2, 3, or 4) so that matching even 1-3 core skills
    # contributes to a very good score, which is much more realistic for single-stack job postings!
    if len(description) < 500:
        core_denom = min(max(int(core_total * 0.15), 1), 2)
        bonus_denom = min(max(int(bonus_total * 0.10), 1), 2)
    elif len(description) < 1800:
        core_denom = min(max(int(core_total * 0.35), 2), 3)
        bonus_denom = min(max(int(bonus_total * 0.20), 1), 2)
    else:
        core_denom = min(max(int(core_total * 0.60), 3), 4)
        bonus_denom = min(max(int(bonus_total * 0.40), 2), 3)

    core_score = min(core_hits / core_denom, 1.0) * 35
    bonus_score = min(bonus_hits / bonus_denom, 1.0) * 15
    skill_score = core_score + bonus_score

    # Penalize skill score when title explicitly names a DIFFERENT SAP module
    # Generic SAP skills (sap, erp, configuration) inflate the score even though
    # the candidate doesn't have the specific module expertise (e.g. FICO vs MM)
    if sap_module_mismatch:
        skill_score *= 0.4  # 60% penalty — generic SAP overlap shouldn't dominate

    # --- Title relevance scoring (derived from resume's current_role) ---
    title_relevance = 0
    title_keywords = _get_cached_title_keywords()
    # Full role match = 30 (base role or skill-derived variant), partial word match = 10
    if title_keywords:
        base_role = title_keywords[0]  # first entry is always the base role
        # Full role variants include base_role + skill-derived roles (multi-word entries)
        full_role_variants = [kw for kw in title_keywords if " " in kw]
        # Single words are partial matches only
        partial_words = [kw for kw in title_keywords if " " not in kw]
        # Word-level match: check if all words of a variant appear in title (any order)
        # Normalize hyphens/slashes and strip punctuation to avoid comma/punctuation split issues
        clean_title_words = title_lower.replace("-", " ").replace("/", " ")
        clean_title_words = re.sub(r'[^a-z0-9\s]', ' ', clean_title_words)
        title_words = set(clean_title_words.split())
        def _words_in_title(variant):
            return set(variant.split()).issubset(title_words)
        if any(_words_in_title(v) for v in full_role_variants):
            title_relevance = 30
        elif any(kw in title_lower for kw in partial_words):
            title_relevance = 10

    # --- Seniority scoring (experience-appropriate) ---
    # Prioritize title match over full-text match to avoid false positives
    # (e.g. "mentor senior engineers" in JD body shouldn't count)
    seniority_keywords = _get_cached_seniority_keywords()
    if seniority_keywords:
        if any(k in title_lower for k in seniority_keywords):
            seniority_score = 15  # seniority keyword in title = full points
        elif any(k in text for k in seniority_keywords):
            seniority_score = 10  # seniority keyword in body only = partial credit
        else:
            # Experienced profiles: many roles don't explicitly say "senior" but target 5-10yr candidates
            seniority_score = 10 if exp_years >= 5 else 5
    else:
        # Junior profiles (<3 yrs): give 10 points if role doesn't demand seniority
        senior_in_title = any(k in title_lower for k in ["senior", "staff", "lead", "principal"])
        seniority_score = 10 if not senior_in_title else 0

    # --- Skill-match inference bonus ---
    # When the JD strongly matches the profile's skills but the title is generic
    # (e.g. "SAP Consultant" instead of "SAP MM Consultant", or "Software Engineer"
    # instead of "Backend Engineer"), infer partial title relevance from skill overlap.
    # This avoids penalizing roles that match on substance but use broad titles.
    total_skills = len(PROFILE["core_skills"])
    total_hits = core_hits + bonus_hits
    skill_match_ratio = total_hits / total_skills if total_skills > 0 else 0
    if title_relevance == 0 and skill_match_ratio >= 0.7:
        # 70%+ of profile skills found in JD — strong evidence of relevance
        title_relevance = 15
    if skill_match_ratio >= 0.85:
        # 85%+ — very strong evidence; boost even if partial title match (10) already set
        title_relevance = max(title_relevance, 20)

    # --- Title SAP module bonus ---
    # When the title explicitly names a SAP module that matches the profile's skills,
    # the role is unambiguously relevant. Thin JDs shouldn't penalize an exact match.
    # E.g. "SAP MM Consultant" for an SAP MM profile = guaranteed match (+10).
    # Also match full module names: "Materials Management" = MM, etc.
    title_module_bonus = 0
    if has_sap_skills and not sap_module_mismatch:
        profile_sap_modules = {s for s in PROFILE["core_skills"] if s.startswith("sap ") and s != "sap"}
        # Check abbreviations in title
        for mod in profile_sap_modules:
            mod_part = mod.replace("sap ", "", 1)
            if re.search(r'\b' + re.escape(mod_part) + r'\b', title_lower):
                title_module_bonus = 10
                break
        # Check full module names in title
        if title_module_bonus == 0:
            for mod, aliases in _SAP_MODULE_ALIASES.items():
                if mod in profile_sap_modules:
                    for alias_pat in aliases:
                        if re.search(alias_pat, title_lower, re.IGNORECASE):
                            title_module_bonus = 10
                            break
                    if title_module_bonus > 0:
                        break

    # --- International opportunity bonuses (visa & relocation scored independently) ---
    # For jobs outside India with a relevant match (title OR skills), visa sponsorship
    # and relocation support each contribute points independently.
    # Relocation-friendly companies count as both visa + relocation signals.
    visa_bonus = 0
    relo_bonus = 0
    relocation_note = ""
    company_lower = company.lower()
    for friendly_co, note in RELOCATION_FRIENDLY.items():
        if friendly_co in company_lower:
            relocation_note = note
            break
    if not relocation_note and in_ind_sponsor:
        relocation_note = "IND recognised sponsor (Netherlands)"
    if is_outside_india and (title_relevance >= 10 or skill_score >= 20):
        # +5 if JD mentions visa sponsorship or company is known to sponsor
        if has_visa_sponsor or relocation_note:
            visa_bonus = 5
        # +5 if JD mentions relocation support or company is known to relocate
        if has_relo_support or relocation_note:
            relo_bonus = 5

    # --- Thin-JD title boost ---
    # When a job title strongly matches the profile role (title_relevance >= 30)
    # but the JD is ultra-short (scraper snippet with no real content), there are
    # zero skills to match against. The job is very likely relevant based on title
    # alone, so apply a minimum skill floor to avoid unfairly penalizing it.
    if title_relevance >= 30 and len(description) < 200 and skill_score < 20:
        skill_score = 20  # floor: title is a strong match, assume skill relevance

    score = round(skill_score + title_relevance + seniority_score + title_module_bonus + visa_bonus + relo_bonus)
    score = max(0, min(100, score))
    # Combine relocation note and visa note
    notes = " | ".join(n for n in [relocation_note, visa_note] if n)
    if sap_module_mismatch:
        prefix = "Title: non-matching SAP module — scored by JD"
        notes = f"{prefix} | {notes}" if notes else prefix

    # --- Red-flag title enforcement ---
    # If title matched a red-flag track, check if skill overlap is high enough
    # to override. Some companies use titles like "DevOps Engineer" for roles
    # that are really backend/platform engineering. Use denominator-adjusted
    # skill_score (not raw ratio) since profiles with many skills have a low
    # raw ratio even when the JD matches well.
    if red_flag_match:
        if skill_score >= 35:
            # Strong skill overlap (≥70% of adjusted denominator) — let score stand
            notes = (f"Title red-flag ({red_flag_match}) overridden by skill match "
                     f"({total_hits}/{total_skills})" + (" | " + notes if notes else ""))
        else:
            # Skill overlap too low — enforce the filter
            return 0, f"Filtered: title matches non-relevant track ({red_flag_match})"

    return score, notes


def _title_only_bypass(job, score, relocation_note, threshold):
    """If description is too short to score skills but title matches well, auto-pass."""
    if score >= threshold or len(job.get("description", "")) >= 100:
        return score, relocation_note
    # Don't bypass explicit filters (e.g., junior role, etc.) or SAP module mismatches
    if relocation_note.startswith("Filtered:") or "non-matching SAP module" in relocation_note:
        return score, relocation_note
    title_lower = job["title"].lower().replace("-", " ").replace("/", " ")
    title_lower = re.sub(r'[()\[\]{}]', ' ', title_lower)
    title_lower = re.sub(r'\s+', ' ', title_lower).strip()

    # SAP module guard: for SAP profiles, only bypass when the title explicitly
    # contains one of the profile's SAP modules (mm, ewm, etc.). There are 100+
    # SAP modules/products so a blocklist is impractical. Instead, require a
    # positive match. Generic "SAP Consultant" with no JD is also skipped —
    # too risky when we can't verify the module from description.
    has_sap_skills = any(s.startswith("sap ") for s in PROFILE.get("core_skills", []))
    if has_sap_skills and "sap" in title_lower.split():
        profile_sap_modules = {s.replace("sap ", "") for s in PROFILE.get("core_skills", [])
                               if s.startswith("sap ") and s != "sap"}
        # Check if any profile module word appears in the title
        title_has_profile_module = any(
            re.search(r'\b' + re.escape(mod) + r'\b', title_lower)
            for mod in profile_sap_modules
        )
        if not title_has_profile_module:
            # Title is either generic "SAP Consultant" or names a different module
            # Either way, without a JD we can't confirm it's a match — skip bypass
            return score, relocation_note

    title_keywords = _derive_title_keywords(PROFILE.get("current_role", ""), PROFILE["years_experience"])
    if title_keywords:
        # Check multi-word role variants (e.g. "software engineer", "platform engineer",
        # "infrastructure engineer"), not just the base_role.
        # This ensures Playwright-scraped titles like "Staff Platform Engineer" or
        # "Senior Infrastructure Engineer" also get the bypass.
        # Exclude ambiguous variants that match non-software roles (aerospace, IT, etc.)
        _BYPASS_AMBIGUOUS = {"systems engineer", "systems architect", "distributed systems engineer"}
        full_role_variants = [kw for kw in title_keywords if " " in kw and kw not in _BYPASS_AMBIGUOUS]
        title_words = set(title_lower.split())
        matched_variants = [v for v in full_role_variants if set(v.split()).issubset(title_words)]
        if matched_variants:
            # Require the matched variant to contain at least one profile skill word.
            # This prevents generic titles like "Software Engineer" (no domain signal)
            # from bypassing, while allowing "Backend Engineer" ("backend" is a skill),
            # "SAP MM Consultant" ("sap"/"mm" are skill words), etc.
            # Generic words that appear in many titles are excluded.
            _GENERIC_TITLE_WORDS = {
                "engineer", "developer", "software", "senior", "junior", "lead",
                "staff", "principal", "manager", "consultant", "architect", "analyst",
                "specialist", "associate", "intern", "head", "director", "vp",
            }
            skill_words = set()
            for s in PROFILE.get("core_skills", []):
                skill_words.update(s.lower().split())
            skill_words -= _GENERIC_TITLE_WORDS

            has_skill_signal = any(
                set(v.split()) & skill_words
                for v in matched_variants
            )
            if has_skill_signal:
                score = max(score, 72)
                relocation_note = (relocation_note + " | " if relocation_note else "") + "Title-match pass (no full JD)"
    return score, relocation_note


_translation_cache = {}
_translation_lock = threading.Lock()


def _detect_total_count(soup, default=500):
    """Try to detect total job count from a page. Look for common count patterns."""
    import re
    txt = soup.get_text()[:3000]
    patterns = [
        # German: "13.406 Jobs", "224 Ergebnisse", "1.234 Stellen"
        r'(\d[\d.]*)\s*(?:Jobs?|Stellen?|Ergebnisse?|Angebote?|Treffer)',
        # Portuguese: "244 Ofertas", "244 resultados"
        r'(\d[\d.]*)\s*(?:Ofertas?|resultados?|vagas?)',
        # Spanish: "244 ofertas", "244 empleos"
        r'(\d[\d.]*)\s*(?:ofertas?|empleos?|puestos?)',
        # French: "244 offres", "244 résultats"
        r'(\d[\d.]*)\s*(?:offres?|résultats?|emplois?)',
        # Dutch: "244 vacatures", "244 resultaten"
        r'(\d[\d.]*)\s*(?:vacatures?|resultaten?|banen?)',
        # English: "224 jobs", "224 results", "224 matching offers"
        r'(\d[\d,.]+)\s*(?:jobs?|results?|offers?|matches?|vacancies?|positions?)',
        r'(?:of|Found)\s+(\d[\d,.]+)',
    ]
    for p in patterns:
        m = re.search(p, txt, re.IGNORECASE)
        if m:
            num = m.group(1).replace('.', '').replace(',', '')
            try:
                return int(num)
            except ValueError:
                pass
    return default


def _translate_to_english(text):
    """Translate non-English text to English. Caches results (thread-safe).
    Skips translation only if text contains English stop words (strong signal it's already English).
    Tech keywords alone (Java, Docker, AWS) don't block — they appear in many languages."""
    if not text or len(text.strip()) < 5:
        return text
    text = text.strip()
    key = text[:200]
    # Fast path: check cache without lock (dict reads are atomic in CPython)
    cached = _translation_cache.get(key)
    if cached is not None:
        return cached
    # English stop words — strong signal text is already English
    if re.search(r'\b(the|is|at|and|for|with|this|that|from|are|was|were|has|have|been|will|would|could|should|about|than|then|also|its|into|more|some|such|than|they|what|when|which|your|being|been|both|each|most|other|over|their|there|these|where|while|after|before|between|during|without|through|under|above|along|around|because|before|behind|below|beneath|beside|beyond|upon|within)\b', text, re.I):
        with _translation_lock:
            _translation_cache[key] = text
        return text
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source='auto', target='en').translate(text[:300])
        if translated:
            with _translation_lock:
                _translation_cache[key] = translated
            if translated != text:
                print(f"  [translate] \"{text[:50]}...\" -> \"{translated[:50]}...\"")
            return translated
    except Exception:
        pass
    with _translation_lock:
        _translation_cache[key] = text
    return text


def pick_resume(company):
    resume_path = os.environ.get("RESUME_PATH")
    if resume_path:
        return os.path.basename(resume_path)
    company_lower = company.lower()
    for key, resume in COMPANY_RESUME_MAP.items():
        if key in company_lower:
            return RESUME_VERSIONS[resume]
    return RESUME_VERSIONS["faang"]  # default for unknown EU/global companies


def company_url(company_name, career_page=None):
    if career_page:
        return career_page
    slug = re.sub(r"[^a-zA-Z0-9]", "", company_name.lower().replace(" ", ""))
    return f"https://linkedin.com/company/{slug}"


def tailoring_suggestion(title, description, company):
    """
    Compares job description against the candidate's known skills and suggests
    what to highlight or add to the resume.
    """
    text = (title + " " + description).lower()
    resume_skills = set(s.lower() for s in PROFILE["core_skills"])
    suggestions = []

    # Find skills the JD asks for that the candidate already has (should highlight)
    jd_keywords_found = [kw for kw in COMMON_TECH_KEYWORDS if kw in text]
    own_skills_in_jd = [s for s in jd_keywords_found if s in resume_skills]

    if own_skills_in_jd:
        top = own_skills_in_jd[:5]
        suggestions.append(
            f"JD mentions: {', '.join(top)} — ensure these are prominent in your resume summary."
        )

    # Find skills the JD asks for that the candidate DOESN'T have (skill gap)
    missing = [s for s in jd_keywords_found if s not in resume_skills and len(s) > 2]
    if missing:
        suggestions.append(
            f"Skill gap detected: {', '.join(missing[:5])}. Consider noting willingness to learn or relevant adjacent experience."
        )

    if not suggestions:
        suggestions.append("No specific gaps detected — standard tailoring pass recommended before applying.")
    return suggestions


# ---------------------------------------------------------------------------
# 3a. SALARY EXTRACTION + LEVELS.FYI LOOKUP
# ---------------------------------------------------------------------------

_SALARY_JD_PATTERNS = [
    # $120k - $180k or $150k-$200k
    (re.compile(r'\$(\d{2,3})[kK]\s*[-–to]+\s*\$?(\d{2,3})[kK]'), 'USD', True),
    # $120k (single, no range)
    (re.compile(r'\$(\d{2,3})[kK]\b'), 'USD', True),
    # $120,000 - $180,000 (full dollar amounts, with commas)
    (re.compile(r'(?:\$|USD\s+)(\d{1,3}(?:,\d{3})+)(?:\s*[-–to]+\s*(?:\$|USD\s+)?(\d{1,3}(?:,\d{3})+))?'), 'USD', False),
    # EUR 80,000 - 100,000 or €80,000 - €100,000
    (re.compile(r'(?:EUR\s+)?[€](\d{1,3}(?:[.,]\d{3})*(?:,\d{3})?)(?:\s*[-–to]+\s*(?:\d{1,3}(?:[.,]\d{3})*(?:,\d{3})?))?'), 'EUR', False),
    (re.compile(r'EUR\s+(\d{1,3}(?:[.,]\d{3})*(?:,\d{3})?)(?:\s*[-–to]+\s*(\d{1,3}(?:[.,]\d{3})*(?:,\d{3})?))?'), 'EUR', False),
    # £70,000 - £90,000 or GBP 70,000 - 90,000
    (re.compile(r'(?:GBP\s+)?[£](\d{1,3}(?:[.,]\d{3})*(?:,\d{3})?)(?:\s*[-–to]+\s*(?:\d{1,3}(?:[.,]\d{3})*(?:,\d{3})?))?'), 'GBP', False),
    (re.compile(r'GBP\s+(\d{1,3}(?:[.,]\d{3})*(?:,\d{3})?)(?:\s*[-–to]+\s*(\d{1,3}(?:[.,]\d{3})*(?:,\d{3})?))?'), 'GBP', False),
    # ₹20,00,000 - ₹30,00,000 or ₹20L - ₹30L
    (re.compile(r'[₹](\d+)\s*(?:L|lakh|lacs?)\s*[-–to]+\s*[₹]?(\d+)\s*(?:L|lakh|lacs?)'), 'INR', False),
    # salary: $150,000 or salary range: $120,000-$180,000 (generic catch-all)
    (re.compile(r'salary\s*(?:range)?\s*:?\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)(?:\s*[-–to]+\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?))?'), 'USD', False),
]

def _parse_salary_amount(val):
    """Parse a salary string like '120,000' or '120k' to int."""
    val = val.strip()
    if val.lower().endswith('k'):
        return int(float(val[:-1].replace(',', '')) * 1000)
    # Remove thousands separators but preserve decimal point
    # "120,000.50" -> 120000, "120.000" (EU format) -> 120000
    clean = val.replace(',', '')
    if '.' in clean:
        # Check if it's a decimal (e.g., "120000.50") or EU thousands separator (e.g., "120.000")
        parts = clean.split('.')
        if len(parts[-1]) == 2:  # likely decimal cents, e.g., "120000.50"
            return int(float(clean))
        else:  # likely EU thousands separator, e.g., "120.000"
            clean = clean.replace('.', '')
    return int(clean) if clean else 0

def _extract_salary_from_jd(description):
    """Extract salary range from job description text."""
    for pattern, currency, is_k in _SALARY_JD_PATTERNS:
        m = pattern.search(description)
        if m:
            g = m.groups()
            min_raw = g[0]
            max_raw = g[1] if len(g) > 1 else None
            if is_k:
                min_val = int(min_raw) * 1000 if min_raw else None
                max_val = int(max_raw) * 1000 if max_raw else None
            else:
                min_val = _parse_salary_amount(min_raw) if min_raw else None
                max_val = _parse_salary_amount(max_raw) if max_raw else min_val
            if min_val:
                return {
                    "min": min_val,
                    "max": max_val or min_val,
                    "currency": currency,
                    "text": m.group(0).strip(),
                }
    return None

# Static salary data for well-known tech companies (sourced from levels.fyi).
# Median Total Compensation for Software Engineer roles in USD or local currency.
# Update periodically from https://www.levels.fyi
LEVELS_STATIC_SALARIES = {
    "databricks": {"median_tc": "$460,000", "currency": "USD", "levels": [
        {"level": "L3", "total": "$249,532"}, {"level": "L4", "total": "$434,654"},
        {"level": "L5", "total": "$664,790"}, {"level": "L6", "total": "$1,049,577"},
    ], "url": "https://www.levels.fyi/companies/databricks/salaries/software-engineer"},
    "google": {"median_tc": "$312,000", "currency": "USD", "levels": [
        {"level": "L3", "total": "$209,679"}, {"level": "L4", "total": "$308,305"},
        {"level": "L5", "total": "$409,536"}, {"level": "L6", "total": "$576,059"},
    ], "url": "https://www.levels.fyi/companies/google/salaries/software-engineer"},
    "meta": {"median_tc": "$420,000", "currency": "USD", "levels": [
        {"level": "E3", "total": "$182,272"}, {"level": "E4", "total": "$303,298"},
        {"level": "E5", "total": "$468,127"}, {"level": "E6", "total": "$708,559"},
    ], "url": "https://www.levels.fyi/companies/meta/salaries/software-engineer"},
    "stripe": {"median_tc": "$369,250", "currency": "USD", "levels": [
        {"level": "L1", "total": "$209,323"}, {"level": "L2", "total": "$290,432"},
        {"level": "L3", "total": "$463,543"}, {"level": "L4", "total": "$745,265"},
    ], "url": "https://www.levels.fyi/companies/stripe/salaries/software-engineer"},
    "coinbase": {"median_tc": "$375,000", "currency": "USD", "levels": [
        {"level": "IC3", "total": "$205,502"}, {"level": "IC4", "total": "$261,370"},
        {"level": "IC5", "total": "$390,708"}, {"level": "IC6", "total": "$550,985"},
    ], "url": "https://www.levels.fyi/companies/coinbase/salaries/software-engineer"},
    "booking.com": {"median_tc": "€137,781", "currency": "EUR", "levels": [
        {"level": "E", "total": "€69,490"}, {"level": "F", "total": "€114,583"},
        {"level": "G", "total": "€208,345"}, {"level": "H", "total": "€225,726"},
    ], "url": "https://www.levels.fyi/companies/bookingcom/salaries/software-engineer"},
    "bookingcom": {"median_tc": "€137,781", "currency": "EUR", "levels": [
        {"level": "E", "total": "€69,490"}, {"level": "F", "total": "€114,583"},
        {"level": "G", "total": "€208,345"}, {"level": "H", "total": "€225,726"},
    ], "url": "https://www.levels.fyi/companies/bookingcom/salaries/software-engineer"},
    # REMOVED: Cruise - company shut down Dec 2024; salary data no longer relevant
    # "cruise": {"median_tc": "$411,000", "currency": "USD", "levels": [
    #     {"level": "L3", "total": "$211,426"}, {"level": "L4", "total": "$314,025"},
    #     {"level": "L5", "total": "$403,434"}, {"level": "L6", "total": "$641,107"},
    # ], "url": "https://www.levels.fyi/companies/cruise/salaries/software-engineer"},
    "airbnb": {"median_tc": "$318,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/airbnb/salaries/software-engineer"},
    "amazon": {"median_tc": "$350,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/amazon/salaries/software-engineer"},
    "apple": {"median_tc": "$320,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/apple/salaries/software-engineer"},
    "microsoft": {"median_tc": "$285,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/microsoft/salaries/software-engineer"},
    "netflix": {"median_tc": "$500,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/netflix/salaries/software-engineer"},
    "spotify": {"median_tc": "$225,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/spotify/salaries/software-engineer"},
    "twitter": {"median_tc": "$310,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/twitter/salaries/software-engineer"},
    "lyft": {"median_tc": "$365,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/lyft/salaries/software-engineer"},
    "uber": {"median_tc": "$380,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/uber/salaries/software-engineer"},
    "linkedin": {"median_tc": "$350,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/linkedin/salaries/software-engineer"},
    "salesforce": {"median_tc": "$280,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/salesforce/salaries/software-engineer"},
    "oracle": {"median_tc": "$250,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/oracle/salaries/software-engineer"},
    "snowflake": {"median_tc": "$450,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/snowflake/salaries/software-engineer"},
    "atlassian": {"median_tc": "$275,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/atlassian/salaries/software-engineer"},
    "twilio": {"median_tc": "$260,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/twilio/salaries/software-engineer"},
    "github": {"median_tc": "$300,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/github/salaries/software-engineer"},
    "gitlab": {"median_tc": "$260,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/gitlab/salaries/software-engineer"},
    "cloudflare": {"median_tc": "$275,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/cloudflare/salaries/software-engineer"},
    "datadog": {"median_tc": "$325,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/datadog/salaries/software-engineer"},
    "mongodb": {"median_tc": "$300,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/mongodb/salaries/software-engineer"},
    "elastic": {"median_tc": "$280,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/elastic/salaries/software-engineer"},
    "palantir": {"median_tc": "$350,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/palantir/salaries/software-engineer"},
    "shopify": {"median_tc": "$220,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/shopify/salaries/software-engineer"},
    "canonical": {"median_tc": "$200,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/canonical/salaries/software-engineer"},
    "dropbox": {"median_tc": "$330,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/dropbox/salaries/software-engineer"},
    "discord": {"median_tc": "$310,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/discord/salaries/software-engineer"},
    "reddit": {"median_tc": "$290,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/reddit/salaries/software-engineer"},
    "pinterest": {"median_tc": "$330,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/pinterest/salaries/software-engineer"},
    # SAP / ERP consulting firms
    "infosys": {"median_tc": "$120,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/infosys/salaries/sap-consultant"},
    "accenture": {"median_tc": "$145,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/accenture/salaries/sap-consultant"},
    "accenture federal services": {"median_tc": "$145,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/accenture/salaries/sap-consultant"},
    "deloitte": {"median_tc": "$155,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/deloitte/salaries/sap-consultant"},
    "capgemini": {"median_tc": "$130,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/capgemini/salaries/sap-consultant"},
    "ibm": {"median_tc": "$160,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/ibm/salaries/sap-consultant"},
    "tcs": {"median_tc": "$95,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/tcs/salaries/sap-consultant"},
    "wipro": {"median_tc": "$100,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/wipro/salaries/sap-consultant"},
    "hcl": {"median_tc": "$100,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/hcl/salaries/sap-consultant"},
    "cognizant": {"median_tc": "$115,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/cognizant/salaries/sap-consultant"},
    "epam systems": {"median_tc": "$140,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/epam-systems/salaries/sap-consultant"},
    "ncs group": {"median_tc": "$120,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/ncs-group/salaries/sap-consultant"},
    "dxc technology": {"median_tc": "$125,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/dxc-technology/salaries/sap-consultant"},
    "atos": {"median_tc": "$115,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/atos/salaries/sap-consultant"},
    "sap": {"median_tc": "$175,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/sap/salaries/sap-consultant"},
    "ntt data": {"median_tc": "$120,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/ntt-data/salaries/sap-consultant"},
    "xcede": {"median_tc": "$130,000", "currency": "USD", "levels": [], "url": ""},
    # Additional tech companies
    "anthropic": {"median_tc": "$400,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/anthropic/salaries/software-engineer"},
    "openai": {"median_tc": "$450,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/openai/salaries/software-engineer"},
    "vercel": {"median_tc": "$250,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/vercel/salaries/software-engineer"},
    "grafana": {"median_tc": "$235,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/grafana/salaries/software-engineer"},
    "confluent": {"median_tc": "$340,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/confluent/salaries/software-engineer"},
    "hashicorp": {"median_tc": "$310,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/hashicorp/salaries/software-engineer"},
    "nvidia": {"median_tc": "$420,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/nvidia/salaries/software-engineer"},
    "doordash": {"median_tc": "$360,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/doordash/salaries/software-engineer"},
    "block": {"median_tc": "$320,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/block/salaries/software-engineer"},
    "robinhood": {"median_tc": "$380,000", "currency": "USD", "levels": [], "url": "https://www.levels.fyi/companies/robinhood/salaries/software-engineer"},
}

def _get_static_levels_salary(company):
    """Look up salary from static table. Returns None if unavailable."""
    slug = company.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip()).strip('-')

    direct = LEVELS_STATIC_SALARIES.get(slug) or LEVELS_STATIC_SALARIES.get(slug.replace('-', ''))
    if direct:
        return {**direct, "source": "levels.fyi"}

    # Fuzzy match: try removing common suffixes
    for key in slug.split('-'):
        if key in LEVELS_STATIC_SALARIES:
            return {**LEVELS_STATIC_SALARIES[key], "source": "levels.fyi"}

    # Check if any known key is a substring of the company name
    for known_key, data in LEVELS_STATIC_SALARIES.items():
        if known_key in slug and len(known_key) > 3:
            return {**data, "source": "levels.fyi"}

    return None

# Static company descriptions (shown in email cards)
_COMPANY_DESCRIPTIONS = {
    "infosys": "Indian IT services company",
    "accenture": "Global professional services (IT consulting)",
    "deloitte": "Big 4 professional services firm",
    "capgemini": "French IT services & consulting",
    "ibm": "American tech & consulting giant",
    "tcs": "India's largest IT services company",
    "wipro": "Indian IT services company",
    "hcl": "Indian IT services company",
    "cognizant": "US-based IT services company",
    "epam systems": "Eastern European software engineering",
    "ncs group": "Australian IT services company",
    "dxc technology": "US IT services (HP Enterprise spin-off)",
    "sap": "German enterprise software (ERP)",
    "ntt data": "Japanese IT services company",
    "xcede": "UK-based SAP recruitment agency",
    "google": "Search & cloud computing giant",
    "microsoft": "Software & cloud platform giant",
    "amazon": "E-commerce & cloud (AWS) giant",
    "meta": "Social media & platforms (Facebook)",
    "apple": "Consumer tech & hardware",
    "netflix": "Streaming & entertainment",
    "spotify": "Music streaming platform",
    "stripe": "Online payment infrastructure",
    "coinbase": "Cryptocurrency exchange platform",
    "databricks": "Data & AI platform (Spark)",
    "snowflake": "Cloud data warehouse platform",
    "mongodb": "NoSQL database company",
    "elastic": "Search & observability (Elasticsearch)",
    "datadog": "Cloud monitoring & observability",
    "cloudflare": "CDN & security infrastructure",
    "hashicorp": "Cloud infrastructure (Terraform, Vault)",
    "confluent": "Data streaming (Kafka) platform",
    "nvidia": "GPU & AI hardware leader",
    "anthropic": "AI safety research (Claude)",
    "openai": "AI research (ChatGPT, GPT-4)",
    "vercel": "Frontend deployment platform",
    "gitlab": "DevOps platform (CI/CD)",
    "github": "Code hosting & collaboration (Microsoft)",
    "shopify": "E-commerce platform",
    "atlassian": "Team collaboration (Jira, Confluence)",
}

def _company_description(company):
    slug = company.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    for known, desc in _COMPANY_DESCRIPTIONS.items():
        if known in slug:
            return desc
    return ""

def get_salary_info(company, title, description):
    """Get salary info: try JD first, fall back to static levels.fyi data."""
    jd_salary = _extract_salary_from_jd(description)
    if jd_salary:
        return {**jd_salary, "source": "jd"}

    levels_data = _get_static_levels_salary(company)
    if levels_data:
        return levels_data

    return None


# Build company → ATS lookup from JOB_SOURCES
_COMPANY_ATS = {}
for _src in JOB_SOURCES:
    _name = _src.get("name", "").lower()
    _ats = _src.get("ats", "")
    if _name and _ats:
        _COMPANY_ATS[_name] = _ats

def _easy_apply_ats(company):
    """Check if a company uses an easy-apply ATS (greenhouse/lever/ashby)."""
    slug = company.lower().strip()
    # Direct match
    if _COMPANY_ATS.get(slug):
        return _COMPANY_ATS[slug]
    # Fuzzy: check if any key is in company name
    for known, ats in _COMPANY_ATS.items():
        if known in slug and len(known) > 3:
            return ats
    return None

EASY_APPLY_ATS = {"greenhouse", "lever", "ashby"}

# ---------------------------------------------------------------------------
# 3b. PROFILE-AWARE QUERY EXPANSION
# ---------------------------------------------------------------------------

SENIORITY_PREFIXES = {
    0: [],
    2: ["junior"],
    5: ["senior", "lead"],
    8: ["senior", "staff", "principal", "lead"],
}

ROLE_DOMAIN_QUERIES = {
    "sap": {
        "titles": ["SAP FICO", "SAP MM", "SAP consultant", "SAP S/4HANA", "SAP"],
        "stems": [],
    },
    "backend": {
        "titles": ["backend engineer", "software engineer", "platform engineer",
                    "distributed systems engineer"],
        "stems": ["backend", "software", "platform", "distributed"],
    },
    "frontend": {
        "titles": ["frontend engineer", "front-end engineer", "ui engineer",
                    "software engineer"],
        "stems": ["frontend", "front-end", "ui", "software"],
    },
    "mobile": {
        "titles": ["mobile engineer", "ios engineer", "android engineer",
                    "mobile developer"],
        "stems": ["mobile", "ios", "android"],
    },
    "data_ml": {
        "titles": ["data engineer", "data scientist", "ml engineer",
                    "machine learning engineer", "data platform engineer"],
        "stems": ["data", "ml", "machine learning"],
    },
    "devops_sre": {
        "titles": ["devops engineer", "sre", "site reliability engineer",
                    "platform engineer", "infrastructure engineer"],
        "stems": ["devops", "sre", "platform", "infrastructure"],
    },
    "fullstack": {
        "titles": ["fullstack engineer", "full stack engineer",
                    "software engineer"],
        "stems": ["fullstack", "full stack", "software"],
    },
}

def detect_profile_domain(skills=None):
    """
    Detect the primary role domain from profile skills using a scoring approach.
    Prefers backend over devops_sre when both match (common for polyglot engineers).
    """
    if skills is None:
        skills = PROFILE["core_skills"]
    skill_set = set(s.lower() for s in skills)

    if any("sap" in s or "erp" in s for s in skill_set):
        return "sap"

    domain_scores = {}
    for domain, config in ROLE_DOMAINS.items():
        domain_skills = config.get("skills", set())
        if domain_skills:
            overlap = len(skill_set & domain_skills)
            if overlap > 0:
                domain_scores[domain] = overlap

    if not domain_scores:
        return "backend"

    # Boost backend score to avoid devops_sre/frontend taking over
    domain_scores["backend"] = domain_scores.get("backend", 0) * 1.5

    return max(domain_scores, key=domain_scores.get)

def build_domain_queries(skills=None, exp_years=None, prefer_role=None):
    """
    Generate a list of search queries matching the profile's domain and seniority.
    Used by both daily_scan.py and the MCP server.
    """
    if skills is None:
        skills = PROFILE["core_skills"]
    if exp_years is None:
        exp_years = PROFILE["years_experience"]

    domain = detect_profile_domain(skills)
    config = ROLE_DOMAIN_QUERIES.get(domain, ROLE_DOMAIN_QUERIES["backend"])

    prefixes = []
    for min_exp, titles in sorted(SENIORITY_PREFIXES.items()):
        if exp_years >= min_exp:
            prefixes = titles

    queries = set()
    queries.add("+".join(skills[:3]))

    titles_to_use = list(config["titles"])
    if domain == "sap":
        # Extract actual sap modules from candidate's skills
        profile_sap_titles = [s.upper() for s in skills if s.lower().startswith("sap ") and s.lower() != "sap"]
        # Add generic SAP consultant and SAP if not present
        titles_to_use = profile_sap_titles + ["SAP consultant", "SAP"]

    for title in titles_to_use:
        queries.add(title)
        for prefix in prefixes:
            queries.add(f"{prefix} {title}")

    if prefer_role:
        queries.add(prefer_role)
        for prefix in prefixes:
            queries.add(f"{prefix} {prefer_role}")

    return [q for q in queries if q]


# ---------------------------------------------------------------------------
# 4. SCANNING (placeholder - wire up real scraping/APIs here)
# ---------------------------------------------------------------------------

def _parse_date(date_str):
    """Parse ISO date string or Unix timestamp (ms) to datetime, return None if unparseable."""
    if not date_str:
        return None
    try:
        # Handle Unix timestamps in milliseconds (e.g., Lever API createdAt)
        if isinstance(date_str, (int, float)) or (isinstance(date_str, str) and date_str.isdigit()):
            ts = int(date_str)
            if ts > 1e12:  # milliseconds
                ts = ts / 1000
            return datetime.fromtimestamp(ts)
        return datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_relative_date(text):
    """Convert relative date strings like '3 days ago', 'Just posted' to ISO date string."""
    if not text:
        return None
    text = text.strip().lower()
    from datetime import timedelta
    today = datetime.now()
    if "just" in text or "today" in text or "now" in text:
        return today.strftime("%Y-%m-%d")
    m = re.search(r'(\d+)\s*hour', text)
    if m:
        return today.strftime("%Y-%m-%d")
    m = re.search(r'(\d+)\s*day', text)
    if m:
        return (today - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r'(\d+)\s*week', text)
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r'(\d+)\s*month', text)
    if m:
        return (today - timedelta(days=int(m.group(1)) * 30)).strftime("%Y-%m-%d")
    return None

def _is_within_months(date_val, months=6):
    """Check if date is within N months from now."""
    if date_val is None:
        return True  # no date = assume recent
    from datetime import timedelta
    # Handle string dates
    if isinstance(date_val, str):
        try:
            if "T" in date_val:
                date_val = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            else:
                date_val = datetime.strptime(date_val, "%Y-%m-%d")
        except (ValueError, TypeError):
            return True  # unparseable = assume recent
    cutoff = datetime.now(date_val.tzinfo if hasattr(date_val, 'tzinfo') and date_val.tzinfo else None) - timedelta(days=months*30)
    return date_val >= cutoff


def _scrape_company_career_page(source):
    """Scrape company career page using Playwright with pagination + profile filtering."""
    jobs = []
    browser = None
    page = None
    pw_failed = False

    # Build profile keywords for early job title filtering
    profile_kw = set(w.lower() for w in PROFILE.get("core_skills", []))
    profile_kw.update(w.lower() for w in PROFILE.get("seniority_keywords", []))
    profile_kw.update([
        "engineer", "developer", "architect", "backend", "full stack",
        "software", "platform", "infrastructure", "data", "sap",
        "consultant", "specialist", "analyst", "manager", "lead",
        "staff", "principal", "sde",
    ])
    title_red_flags = set(f.lower() for f in PROFILE.get("title_red_flags", []))

    def _is_relevant(title):
        t = title.lower()
        for rf in title_red_flags:
            if rf in t:
                return False
        return any(kw in t for kw in profile_kw)

    def _extract_links(pg):
        result = []
        try:
            raw = pg.eval_on_selector_all("a", """
                els => els.map(e => {
                    const href = e.href || '';
                    const text = (e.innerText || '').trim();
                    let titleFromCard = '';
                    const card = e.closest('li, [class*="card"], [class*="item"], [class*="job"], [class*="row"], [class*="result"], [class*="flex"], [class*="p-"]') || e.parentElement;
                    if (card) {
                        const cardText = card.innerText || '';
                        const lines = cardText.split('\\n').filter(l => l.trim().length > 5);
                        let fallback = '';
                        for (const ln of lines) {
                            const t = ln.trim().toLowerCase();
                            const generic = ['job listing', 'apply now', 'learn more', 'read more', 'view', 'open positions'];
                            if (generic.some(g => t.includes(g))) continue;
                            // Skip single-word category headers (all caps or short words like "ENGINEERING", "SALES")
                            const words = t.split(/\\s+/);
                            if (words.length <= 2 && t === t.toUpperCase() && t.length < 20) continue;
                            if (!fallback) fallback = ln.trim();
                            if (t.includes('engineer') || t.includes('developer') || t.includes('manager')
                                || t.includes('architect') || t.includes('specialist') || t.includes('consultant')
                                || t.includes('sap') || t.includes('senior') || t.includes('staff')
                                || t.includes('lead') || t.includes('principal') || t.includes('software')
                                || t.includes('backend') || t.includes('platform') || t.includes('full stack')
                                || t.includes('infrastructure') || t.includes('sde') || t.includes('analyst')) {
                                titleFromCard = ln.trim();
                                break;
                            }
                        }
                        if (!titleFromCard && fallback) titleFromCard = fallback;
                    }
                    return {href, text, titleFromCard};
                })
                    .filter(e => {
                        const t = e.text.toLowerCase();
                        const h = e.href.toLowerCase();
                        const c = (e.titleFromCard || '').toLowerCase();
                        const skip = ['consent', 'cookie', 'privacy', 'sign in', 'log in', 'subscribe'];
                        if (skip.some(s => t.includes(s))) return false;
                        const hasTextKw = t.includes('engineer') || t.includes('developer')
                            || t.includes('senior') || t.includes('software') || t.includes('backend')
                            || t.includes('platform') || t.includes('lead');
                        const cardHasKw = c.includes('engineer') || c.includes('developer')
                            || c.includes('senior') || c.includes('software') || c.includes('backend');
                        const urlIsJob = h.includes('/vacancies/') || h.includes('/jobs/')
                            || h.includes('/position/') || h.includes('/opening/')
                            || h.includes('jobId=') || h.includes('job-id=') || h.includes('reqId=')
                            || h.includes('smartrecruiters.com/') || h.includes('workable.com/')
                            || h.includes('bamboohr.com/');
                        return (hasTextKw || cardHasKw) || urlIsJob;
                    })
            """)
            seen_local = set()
            for link in raw:
                href = link["href"]
                if not href or href in seen_local:
                    continue
                seen_local.add(href)
                title = link["titleFromCard"] or link["text"].split('\n')[0].strip()
                if not title or len(title) < 5:
                    continue
                if _is_relevant(title):
                    result.append({
                        "title": title[:120],
                        "company": source["name"],
                        "location": source.get("region", ""),
                        "url": href,
                        "description": title[:120],
                        "posted_at": None,
                    })
            if not result:
                fallback = pg.eval_on_selector_all("a[href], h2, h3, h4, [class*='cursor-pointer'], [class*='clickable']", """
                    els => els.map(e => ({href: e.href || '', text: (e.innerText || '').trim()}))
                        .filter(e => e.text.length > 10 && e.text.length < 120)
                """)
                for link in fallback:
                    title = link["text"].split('\n')[0].strip()
                    href = link["href"]
                    if href in seen_local:
                        continue
                    seen_local.add(href)
                    if _is_relevant(title):
                        result.append({
                            "title": title[:120],
                            "company": source["name"],
                            "location": source.get("region", ""),
                            "url": href or source["url"],
                            "description": title[:120],
                            "posted_at": None,
                        })
        except Exception:
            pass
        return result

    for attempt in range(2):
        if attempt > 0:
            print(f"  [pw] Retry attempt {attempt+1} for {source['name']}")
        context = None
        success = False
        pw_failed = False
        try:
            browser = _get_browser()
            context = _create_context(browser, source.get("url"))
            page = context.new_page()
            page.set_default_timeout(source.get("timeout", 20000))
            _with_stealth(page)
            pw_timeout = source.get("timeout", 20000)
            page.goto(source["url"], timeout=pw_timeout, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
    
            page.evaluate("""
                () => {
                    const overlays = document.querySelectorAll(
                        '#gdpr, #cookie, .cookie-banner, #igdpr-alert, ' +
                        '[class*="cookie"], [class*="gdpr"], [class*="consent"], ' +
                        '[id*="cookie"], [id*="gdpr"], [class*="overlay"], ' +
                        '[class*="modal"], [class*="banner"], ' +
                        '[role="dialog"], [aria-modal="true"]'
                    );
                    overlays.forEach(el => el.remove());
                }
            """)
    
            seen_urls = set()
            page_jobs = _extract_links(page)
            for j in page_jobs:
                if j["url"] not in seen_urls:
                    seen_urls.add(j["url"])
                    jobs.append(j)
    
            # Try "Show More" / "Load More" / "Show more results" buttons up to 5 times
            for _sm in range(5):
                show_more = page.query_selector(
                    'button:has-text("Show More"), button:has-text("show more"), '
                    'button:has-text("Load More"), button:has-text("load more"), '
                    'button:has-text("Show more results"), button:has-text("show more results"), '
                    'button:has-text("More Results"), button:has-text("more results"), '
                    'button:has-text("View More"), button:has-text("view more"), '
                    'button:has-text("See More"), button:has-text("see more"), '
                    'button:has-text("More jobs"), button:has-text("more jobs"), '
                    'button:has-text("Load more jobs"), button:has-text("load more jobs"), '
                    'button:has-text("View All"), button:has-text("view all"), '
                    'a:has-text("Show More"), a:has-text("show more"), '
                    'a:has-text("Load More"), a:has-text("load more"), '
                    'a:has-text("Show more results"), a:has-text("show more results"), '
                    'a:has-text("More Results"), a:has-text("more results"), '
                    'a:has-text("View More"), a:has-text("view more"), '
                    'a:has-text("See More"), a:has-text("see more"), '
                    'a:has-text("More jobs"), a:has-text("more jobs"), '
                    'a:has-text("View All"), a:has-text("view all"), '
                    '[class*="show-more"], [class*="showMore"], '
                    '[class*="load-more"], [class*="loadMore"], '
                    '[class*="load-more-jobs"], [class*="loadMoreJobs"], '
                    '[class*="show-more-results"], [class*="showMoreResults"], '
                    '[class*="view-more"], [class*="viewMore"], '
                    '[class*="view-all"], [class*="viewAll"]'
                )
                if show_more:
                    try:
                        show_more.scroll_into_view_if_needed()
                        page.evaluate("""
                            () => {
                                const overlays = document.querySelectorAll(
                                    '#gdpr, #cookie, .cookie-banner, #igdpr-alert, ' +
                                    '[class*="cookie"], [class*="gdpr"], [class*="consent"], ' +
                                    '[id*="cookie"], [id*="gdpr"], [class*="overlay"], ' +
                                    '[class*="modal"], [class*="banner"], ' +
                                    '[role="dialog"], [aria-modal="true"]'
                                );
                                overlays.forEach(el => el.remove());
                            }
                        """)
                        show_more.click()
                        page.wait_for_timeout(2000)
                        page_jobs = _extract_links(page)
                        for j in page_jobs:
                            if j["url"] not in seen_urls:
                                seen_urls.add(j["url"])
                                jobs.append(j)
                        continue
                    except Exception:
                        pass
                break
    
            # Pagination: up to 5 additional pages
            for _pg in range(2, 7):
                next_btn = None
                try:
                    next_btn = page.query_selector(
                        'a[rel="next"], button[aria-label*="Next" i], '
                        'a.pagination__next, .pagination a.next, '
                        'a:has-text("Next"), a:has-text("next"), '
                        'button:has-text("Next"), button:has-text("next")'
                    )
                except Exception:
                    pass
                if next_btn:
                    try:
                        disabled = page.evaluate(
                            '(el) => el.disabled || el.classList.contains("disabled") '
                            '|| el.getAttribute("aria-disabled") === "true"',
                            next_btn
                        )
                        if disabled:
                            break
                        page.evaluate("""
                            () => {
                                const overlays = document.querySelectorAll(
                                    '#gdpr, #cookie, .cookie-banner, #igdpr-alert, ' +
                                    '[class*="cookie"], [class*="gdpr"], [class*="consent"], ' +
                                    '[id*="cookie"], [id*="gdpr"], [class*="overlay"], ' +
                                    '[class*="modal"], [class*="banner"], ' +
                                    '[role="dialog"], [aria-modal="true"]'
                                );
                                overlays.forEach(el => el.remove());
                            }
                        """)
                        next_btn.click(force=True)
                        page.wait_for_timeout(2000)
                        try:
                            page.wait_for_selector("a", timeout=5000)
                        except Exception:
                            pass
                    except Exception:
                        break
                else:
                    # Try URL-based pagination (page=2, start=10, offset=10, p=2)
                    import re as _re
                    cur = page.url
                    for pat, param in [(r'[?&]page=(\d+)', 'page'), (r'[?&]start=(\d+)', 'start'),
                                       (r'[?&]offset=(\d+)', 'offset'), (r'[?&]p=(\d+)', 'p')]:
                        m = _re.search(pat, cur)
                        if m:
                            base = _re.sub(r'[?&]' + param + r'=\d+', '', cur)
                            sep = '&' if '?' in base else '?'
                            next_url = f"{base}{sep}{param}={_pg}"
                            try:
                                page.goto(next_url, timeout=pw_timeout, wait_until="domcontentloaded")
                                page.wait_for_timeout(2000)
                            except Exception:
                                break
                            break
                    else:
                        break  # No pagination pattern found
    
                page_jobs = _extract_links(page)
                new_count = 0
                for j in page_jobs:
                    if j["url"] not in seen_urls:
                        seen_urls.add(j["url"])
                        jobs.append(j)
                        new_count += 1
                if new_count == 0:
                    break
            success = True
        except Exception as e:
            pw_failed = True
            pw_error = str(e)
            print(f"  [pw] Playwright failed for {source['name']}: {e}")
            if "browser has been closed" in pw_error.lower() or "Target page" in pw_error:
                if hasattr(_local_playwright, "browser"):
                    _local_playwright.browser = None
                    _local_playwright.page_count = 0
                continue  # retry with fresh browser
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            _check_reclaim_playwright()
        if success:
            break

    if pw_failed or not jobs:
        # Skip HTTP fallback if Playwright failed due to Cloudflare, download trigger, or connection reset
        if pw_failed and any(kw in pw_error.lower() for kw in ["cloudflare", "cf-ray", "download is starting", "connection aborted", "remote end closed"]):
            if not jobs:
                print(f"  [http] Skipped fallback for {source['name']} (blocked: {pw_error[:60]})")
        else:
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
            try:
                import requests as req
                http_timeout = max(10, source.get("timeout", 10) // 2)
                resp = req.get(source["url"], headers=headers, timeout=http_timeout, verify=False)
                if resp.status_code == 200:
                    import re
                    html = resp.text
                    for p in ['window.__INITIAL_STATE__', 'window.__DATA__', 'window.__NEXT_DATA__']:
                        idx = html.find(p + '=')
                        if idx >= 0:
                            end = html.find(';\n', idx) if html.find(';\n', idx) > 0 else html.find('\n', idx)
                            chunk = html[idx + len(p) + 1:end]
                            import json as _j
                            try:
                                data = _j.loads(chunk)
                                items = data.get('jobs', data.get('vacancies', data.get('data', [])))
                                if isinstance(items, dict):
                                    items = list(items.values())
                                if isinstance(items, list):
                                    for item in items[:30]:
                                        if isinstance(item, dict):
                                            t = item.get('title', item.get('name', item.get('jobTitle', '')))
                                            if t and _is_relevant(t):
                                                jobs.append({'title': t, 'company': source['name'],
                                                             'location': item.get('location', source.get('region', '')),
                                                             'url': item.get('url', item.get('applyUrl', source['url'])),
                                                             'description': t, 'posted_at': None})
                            except Exception:
                                pass
                    if not jobs:
                        job_links = re.findall(r'href=[\"\']([^\"\']*/(?:job|vacancy|position|opening)/[^\"\']+)[\"\']', html, re.IGNORECASE)
                        seen = set()
                        for href in job_links:
                            full = href if href.startswith('http') else source['url'].rstrip('/') + '/' + href.lstrip('/')
                            clean = full.split('?')[0]
                            if clean in seen:
                                continue
                            seen.add(clean)
                            segs = clean.rstrip('/').split('/')
                            title = ''
                            for seg in segs:
                                if seg.replace('-', '').replace('.', '').isdigit():
                                    continue
                                if any(kw in seg.lower() for kw in ['job', 'vacancy', 'position', 'opening']):
                                    continue
                                title = seg
                            title = title.replace('-', ' ').replace('+', ' ').replace('&amp;', '&')
                            from urllib.parse import unquote
                            title = unquote(title)
                            title = re.sub(r'\s+', ' ', title).strip()
                            title = ' '.join(w.capitalize() if w.lower() not in ('and', 'or', 'the', 'of', 'in', 'for', '&') else w for w in title.split())
                            if len(title) > 5 and _is_relevant(title):
                                jobs.append({'title': title[:100], 'company': source['name'],
                                             'location': source.get('region', ''), 'url': full.split('?')[0],
                                             'description': title[:100], 'posted_at': None})
                if jobs:
                    print(f"  [http] {len(jobs)} jobs from {source['name']}")
            except Exception as e2:
                print(f"  [http] Fallback failed for {source['name']}: {e2}")

    if jobs and not pw_failed:
        print(f"  [pw] {len(jobs)} jobs from {source['name']}")
    return jobs


# ---------------------------------------------------------------------------
# Personio rate-limit throttle & source interleaving
# ---------------------------------------------------------------------------
_personio_last_call = 0.0  # timestamp of last Personio API call
_PERSONIO_MIN_DELAY = 5.0  # minimum seconds between Personio requests (was 3s, increased to reduce 429s)
_personio_backoff = 1.0  # multiplier that increases when 429s are hit


def _is_personio_source(source):
    """Check if a source uses the Personio API."""
    if source.get("ats") == "personio":
        return True
    url = source.get("url", "")
    return "personio.de" in url or "personio.com" in url


def _interleave_sources(sources):
    """Reorder sources so Personio companies are evenly spread out among others.

    This avoids hitting Personio's rate limit by ensuring other ATS calls
    (Lever, Greenhouse, Workable, etc.) happen between Personio calls.
    """
    personio = [s for s in sources if _is_personio_source(s)]
    others = [s for s in sources if not _is_personio_source(s)]

    if not personio or not others:
        return sources  # nothing to interleave

    # Calculate spacing: place one Personio source every N entries
    spacing = max(1, (len(others) + len(personio)) // (len(personio) + 1))
    result = []
    pi = 0  # personio index
    oi = 0  # others index

    while oi < len(others) or pi < len(personio):
        # Add a batch of non-Personio sources
        for _ in range(spacing):
            if oi < len(others):
                result.append(others[oi])
                oi += 1
        # Add one Personio source
        if pi < len(personio):
            result.append(personio[pi])
            pi += 1

    return result


def fetch_jobs_from_source(source):
    """
    Pulls live job postings from public ATS APIs where available.
    Confirmed working, no-auth-required APIs (as of mid-2026):
      - Lever:      https://api.lever.co/v0/postings/{company}?mode=json
                    (EU-hosted Lever accounts use the same endpoint format)
      - Greenhouse: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
      - Ashby:      https://api.ashbyhq.com/posting-api/job-board/{company}

    For sites without a public ATS feed (most custom company career pages),
    this prints a manual-check reminder rather than attempting fragile HTML
    scraping, which breaks every time a site redesigns.
    """
    jobs = []
    try:
        if "lever.co" in source["url"]:
            company_slug = source["url"].rstrip("/").split("/")[-1]
            api_url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                for posting in resp.json():
                    # Combine descriptionPlain + lists content + additionalPlain for full JD
                    desc_parts = [posting.get("descriptionPlain", "")]
                    for lst in posting.get("lists", []):
                        if isinstance(lst, dict):
                            desc_parts.append(lst.get("text", ""))  # section title
                            content = lst.get("content", "")
                            if content:
                                desc_parts.append(strip_html(content))
                    desc_parts.append(posting.get("additionalPlain", ""))
                    description = " ".join(p for p in desc_parts if p)[:8000]
                    jobs.append({
                        "title": posting.get("text", ""),
                        "company": source["name"],
                        "location": posting.get("categories", {}).get("location", "Unknown"),
                        "url": posting.get("hostedUrl", source["url"]),
                        "description": description,
                        "posted_at": _parse_date(posting.get("createdAt")),
                    })
            else:
                print(f"  [warn] Lever API returned {resp.status_code} for {source['name']}")

        elif "greenhouse.io" in source["url"] or source.get("ats") == "greenhouse":
            company_slug = source.get("ats_slug") or source["url"].rstrip("/").split("/")[-1]
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                for posting in resp.json().get("jobs", []):
                    raw_content = posting.get("content", "") or ""
                    posted = _parse_date(posting.get("first_published")) or _parse_date(posting.get("updated_at"))
                    jobs.append({
                        "title": posting.get("title", ""),
                        "company": source["name"],
                        "location": posting.get("location", {}).get("name", "Unknown"),
                        "url": posting.get("absolute_url", source["url"]),
                        "description": strip_html(raw_content)[:8000],
                        "posted_at": posted,
                    })
            else:
                print(f"  [warn] Greenhouse API returned {resp.status_code} for {source['name']}")

        elif "ashbyhq.com" in source["url"] or source.get("ats") == "ashby":
            company_slug = source.get("ats_slug") or source["url"].rstrip("/").split("/")[-1]
            api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                for posting in resp.json().get("jobs", []):
                    jobs.append({
                        "title": posting.get("title", ""),
                        "company": source["name"],
                        "location": posting.get("location", "Unknown"),
                        "url": posting.get("jobUrl", source["url"]),
                        "description": posting.get("descriptionPlain", "")[:8000],
                        "posted_at": _parse_date(posting.get("publishedAt")),
                    })
            else:
                print(f"  [warn] Ashby API returned {resp.status_code} for {source['name']}")

        elif source.get("ats") == "personio" or "personio.de" in source["url"] or "personio.com" in source["url"]:
            # Personio: https://company.jobs.personio.de/search.json
            # Throttle to avoid 429 rate limits
            with _personio_lock:
                global _personio_last_call, _personio_backoff
                import time as _time
                elapsed_since_last = _time.time() - _personio_last_call
                delay = _PERSONIO_MIN_DELAY * _personio_backoff
                if elapsed_since_last < delay:
                    _time.sleep(delay - elapsed_since_last)

                base_url = source["url"].rstrip("/").split("?")[0].rstrip("/")
                api_url = f"{base_url}/search.json"
                resp = None
                for _attempt in range(4):
                    try:
                        _personio_last_call = _time.time()
                        resp = requests.get(api_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                        if resp.status_code == 429:
                            _personio_backoff = min(_personio_backoff * 2, 10.0)
                            wait = 2 ** (_attempt + 1) * _personio_backoff
                            print(f"  [warn] Personio API returned 429 for {source['name']}, retrying in {wait:.0f}s...")
                            _time.sleep(wait)
                            continue
                        break
                    except Exception:
                        break
                if resp and resp.status_code == 200:
                    _personio_backoff = max(1.0, _personio_backoff / 2)  # reset backoff on success
                    try:
                        data = resp.json()
                        postings = data if isinstance(data, list) else data.get("jobs", data.get("data", []))
                        for posting in postings:
                            if not isinstance(posting, dict):
                                continue
                            offices = posting.get("offices", [])
                            location = posting.get("office") or (offices[0] if offices and isinstance(offices[0], str) else "Germany")
                            # Fetch full description from individual job page (JSON-LD)
                            title_name = posting.get("name", "")
                            title_lower = title_name.lower()
                            
                            # Skip obviously irrelevant titles to prevent hitting details API and hanging
                            is_tech_role = any(kw in title_lower for kw in ["backend", "python", "node", "go", "java", "developer", "engineer", "fullstack", "full stack", "software", "sap", "data", "cloud", "aws", "platform", "infrastructure", "systems"])
                            is_red_flag = any(rf in title_lower for rf in ["frontend", "front-end", "ui", "qa", "quality assurance", "test engineer", "android", "ios", "sdet", "marketing", "sales", "hr", "recruiter", "accountant", "product manager", "scrum master", "design"])
                            
                            if is_red_flag or (not is_tech_role and len(postings) > 10):
                                continue

                            description = posting.get("description", "")
                            job_id = posting.get("id", "")
                            job_url = source["url"]
                            if not description and job_id:
                                try:
                                    detail_url = f"{base_url}/job/{job_id}"
                                    det = requests.get(detail_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                                    if det.status_code == 200:
                                        ld_match = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', det.text, re.DOTALL)
                                        if ld_match:
                                            ld_data = json.loads(ld_match.group(1))
                                            if isinstance(ld_data, dict) and ld_data.get("description"):
                                                description = strip_html(ld_data["description"])[:8000]
                                            if isinstance(ld_data, dict) and ld_data.get("url"):
                                                job_url = ld_data["url"]
                                    time.sleep(0.5)  # rate limit (Personio is strict)
                                except Exception:
                                    pass
                            if not description:
                                description = posting.get("name", "")
                            jobs.append({
                                "title": posting.get("name", ""),
                                "company": source["name"],
                                "location": location,
                                "url": job_url,
                                "description": description,
                                "posted_at": None,
                            })
                    except (ValueError, KeyError) as e:
                        print(f"  [warn] Personio JSON parse error for {source['name']}: {e}")
                elif resp:
                    print(f"  [warn] Personio API returned {resp.status_code} for {source['name']}")

        elif source.get("ats") == "recruitee":
            # Recruitee: https://{company}.recruitee.com/api/offers/
            base_url = source["url"].rstrip("/")
            api_url = f"{base_url}/api/offers/"
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                for offer in resp.json().get("offers", []):
                    desc_parts = [offer.get("description", ""), offer.get("requirements", "")]
                    description = strip_html(" ".join(p for p in desc_parts if p))[:8000] or offer.get("title", "")
                    jobs.append({
                        "title": offer.get("title", ""),
                        "company": source["name"],
                        "location": offer.get("office", offer.get("location", source.get("region", ""))),
                        "url": offer.get("careers_url", offer.get("url", source["url"])),
                        "description": description,
                        "posted_at": None,
                    })
            else:
                print(f"  [warn] Recruitee API returned {resp.status_code} for {source['name']}")

        elif source.get("ats") == "smartrecruiters":
            slug = source.get("ats_slug") or source["name"].lower().replace(" ", "")
            api_url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
            offset = 0
            limit = 100  # Max per page for SmartRecruiters
            while True:
                resp = requests.get(api_url, params={"offset": offset, "limit": limit}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    postings = data.get("content", [])
                    if not postings:
                        break
                    for posting in postings:
                        loc = posting.get("location", {})
                        city = loc.get("city", "")
                        country = loc.get("country", "")
                        location = f"{city}, {country}".strip(", ")
                        posting_id = posting.get("id", "")
                        # Fetch full description from detail API
                        description = ""
                        if posting_id:
                            try:
                                detail_url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{posting_id}"
                                det = requests.get(detail_url, timeout=10)
                                if det.status_code == 200:
                                    dj = det.json()
                                    sections = dj.get("jobAd", {}).get("sections", {})
                                    desc_parts = []
                                    for key in ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]:
                                        sec = sections.get(key, {})
                                        if isinstance(sec, dict) and sec.get("text"):
                                            desc_parts.append(sec["text"])
                                    if desc_parts:
                                        description = strip_html(" ".join(desc_parts))[:8000]
                                time.sleep(0.3)  # rate limit
                            except Exception:
                                pass
                        if not description:
                            description = posting.get("name", "")
                        jobs.append({
                            "title": posting.get("name", ""),
                            "company": source["name"],
                            "location": location or source.get("region", ""),
                            "url": posting.get("applyUrl", posting.get("postingUrl", source["url"])),
                            "description": description,
                            "posted_at": _parse_date(posting.get("releasedDate")),
                        })
                    # Check if there are more pages
                    total = data.get("totalFound", 0)
                    offset += limit
                    if offset >= total or len(postings) < limit:
                        break
                else:
                    print(f"  [warn] SmartRecruiters API returned {resp.status_code} for {source['name']}")
                    break

        elif source.get("ats") == "teamtailor":
            # Teamtailor JSON Feed: https://company.teamtailor.com/jobs.json
            base_url = source["url"].rstrip("/")
            if not base_url.endswith("/jobs"):
                base_url += "/jobs"
            feed_base = base_url.rstrip("/") + ".json"
            max_pages = 5  # Fetch up to 5 pages
            for page_num in range(1, max_pages + 1):
                api_url = f"{feed_base}?page={page_num}" if page_num > 1 else feed_base
                resp = requests.get(api_url, timeout=10)
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    if not items:
                        break
                    for item in items:
                        title = item.get("title", "")
                        if not title:
                            continue
                        jp = item.get("_jobposting", {})
                        company = jp.get("hiringOrganization", {}).get("name", source["name"]) if jp else source["name"]
                        locs = jp.get("jobLocation", []) if jp else []
                        loc = ", ".join(
                            l.get("address", {}).get("addressLocality", "")
                            for l in locs if l.get("address", {}).get("addressLocality")
                        ) if locs else source.get("region", "")
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": loc,
                            "url": item.get("url", source["url"]),
                            "description": item.get("content_text", "")[:8000] or title,
                            "posted_at": _parse_date(item.get("date_published")),
                        })
                    # If fewer items than expected, no more pages
                    if len(items) < 20:
                        break
                else:
                    if page_num == 1:
                        print(f"  [warn] Teamtailor API returned {resp.status_code} for {source['name']}")
                    break

        elif source.get("ats") == "workable" or ("workable.com" in source["url"] and not source.get("playwright")):
            # Workable: list at /api/v1/widget/accounts/{company}, detail at /api/v2/accounts/{company}/jobs/{shortcode}
            slug = source.get("ats_slug") or source["url"].rstrip("/").split("#")[0].rstrip("/").split("/")[-1]
            api_url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                for posting in resp.json().get("jobs", []):
                    shortcode = posting.get("shortcode", "")
                    # Fetch full description from detail API
                    description = ""
                    if shortcode:
                        try:
                            detail_url = f"https://apply.workable.com/api/v2/accounts/{slug}/jobs/{shortcode}"
                            det = requests.get(detail_url, timeout=10)
                            if det.status_code == 200:
                                dj = det.json()
                                desc_parts = [dj.get("description", ""), dj.get("requirements", ""), dj.get("benefits", "")]
                                description = strip_html(" ".join(p for p in desc_parts if p))[:8000]
                            time.sleep(0.3)  # rate limit
                        except Exception:
                            pass
                    if not description:
                        description = posting.get("title", "")
                    jobs.append({
                        "title": posting.get("title", ""),
                        "company": source["name"],
                        "location": posting.get("location", source.get("region", "")),
                        "url": posting.get("url", f"https://apply.workable.com/{slug}"),
                        "description": description,
                        "posted_at": _parse_date(posting.get("published_on")),
                    })
            else:
                print(f"  [warn] Workable API returned {resp.status_code} for {source['name']}")

        elif source.get("ats") == "bamboohr" or ("bamboohr.com" in source["url"] and not source.get("playwright")):
            # BambooHR: use /careers/list JSON endpoint (old gateway API returns 401)
            slug = source.get("ats_slug") or source["url"].split(".bamboohr.com")[0].split("//")[-1]
            api_url = f"https://{slug}.bamboohr.com/careers/list"
            resp = requests.get(api_url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}, timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    job_list = data.get("result", data) if isinstance(data, dict) else data
                    if isinstance(job_list, list):
                        for posting in job_list:
                            if not isinstance(posting, dict):
                                continue
                            loc = posting.get("location", posting.get("atsLocation", {}))
                            if isinstance(loc, dict):
                                city = loc.get("city", "")
                                state = loc.get("state", loc.get("province", ""))
                                location = f"{city}, {state}".strip(", ") if city else ""
                            else:
                                location = str(loc)
                            jobs.append({
                                "title": posting.get("jobOpeningName", posting.get("title", "")),
                                "company": source["name"],
                                "location": location or source.get("region", ""),
                                "url": f"https://{slug}.bamboohr.com/careers/{posting.get('id', '')}",
                                "description": posting.get("jobOpeningName", posting.get("title", "")),
                                "posted_at": None,
                            })
                except (ValueError, KeyError):
                    print(f"  [warn] BambooHR unexpected response for {source['name']}")
            else:
                print(f"  [warn] BambooHR API returned {resp.status_code} for {source['name']}")

        elif source.get("ats") == "breezy" or ("breezy.hr" in source["url"] and not source.get("playwright")):
            # Breezy.hr: https://{company}.breezy.hr → JSON at /{company}/json
            slug = source.get("ats_slug") or source["url"].rstrip("/").split(".breezy.hr")[0].split("//")[-1]
            api_url = f"https://{slug}.breezy.hr/json"
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                try:
                    for posting in resp.json():
                        if not isinstance(posting, dict):
                            continue
                        loc = posting.get("location", {})
                        location = loc.get("name", "") if isinstance(loc, dict) else str(loc)
                        jobs.append({
                            "title": posting.get("name", ""),
                            "company": source["name"],
                            "location": location or source.get("region", ""),
                            "url": posting.get("url", f"https://{slug}.breezy.hr"),
                            "description": posting.get("description", posting.get("name", "")),
                            "posted_at": _parse_date(posting.get("published_date")),
                        })
                except (ValueError, KeyError):
                    print(f"  [warn] Breezy unexpected response for {source['name']}")
            else:
                print(f"  [warn] Breezy API returned {resp.status_code} for {source['name']}")

        elif source.get("ats") == "freshteam" or ("freshteam.com" in source["url"] and not source.get("playwright")):
            # Freshteam: https://{company}.freshteam.com/jobs → JSON embed
            base_url = source["url"].rstrip("/")
            if not base_url.endswith("/jobs"):
                base_url += "/jobs"
            resp = requests.get(base_url, headers={"Accept": "text/html"}, timeout=10)
            if resp.status_code == 200:
                # Try to extract JSON data from script tag
                import re as _re
                json_match = _re.search(r'<script[^>]*>.*?jobPostings\s*[:=]\s*(\[.*?\])\s*[;<]', resp.text, _re.DOTALL)
                if not json_match:
                    # Fallback: parse job links from HTML
                    links = _re.findall(r'href=[\"\']([^\"\']*job[^\"\']*)[\"\']\s*[^>]*>\s*([^<]+)', resp.text, _re.IGNORECASE)
                    for href, title in links[:30]:
                        title = title.strip()
                        if title and len(title) > 5:
                            full_url = href if href.startswith("http") else source["url"].split("/jobs")[0] + href
                            jobs.append({
                                "title": title,
                                "company": source["name"],
                                "location": source.get("region", ""),
                                "url": full_url,
                                "description": title,
                                "posted_at": None,
                            })
                else:
                    try:
                        for posting in json.loads(json_match.group(1)):
                            if not isinstance(posting, dict):
                                continue
                            jobs.append({
                                "title": posting.get("title", ""),
                                "company": source["name"],
                                "location": posting.get("location", source.get("region", "")),
                                "url": posting.get("url", source["url"]),
                                "description": posting.get("description", posting.get("title", "")),
                                "posted_at": None,
                            })
                    except (ValueError, KeyError):
                        pass
            else:
                print(f"  [warn] Freshteam returned {resp.status_code} for {source['name']}")

        elif source.get("ats") == "spotify":
            # Spotify custom API: https://api.lifeatspotify.com/wp-json/animal/v1/job/search
            try:
                per_page = 100
                max_pages = 5  # Fetch up to 500 jobs
                for page_num in range(1, max_pages + 1):
                    resp = requests.get("https://api.lifeatspotify.com/wp-json/animal/v1/job/search",
                                        params={"per_page": per_page, "page": page_num}, timeout=10)
                    if resp.status_code == 200:
                        postings = resp.json().get("result", [])
                        if not postings:
                            break
                        for posting in postings:
                            locs = posting.get("locations", [])
                            loc = locs[0].get("location", "Remote") if locs else "Remote"
                            job_id = posting.get("id", "")
                            job_url = f"https://www.lifeatspotify.com/jobs/{job_id}"
                            # Fetch full description from job page (__NEXT_DATA__)
                            description = ""
                            try:
                                detail = requests.get(job_url, timeout=10,
                                                      headers={"User-Agent": "Mozilla/5.0"})
                                if detail.status_code == 200:
                                    nd = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', detail.text, re.DOTALL)
                                    if nd:
                                        jdata = json.loads(nd.group(1))
                                        jcontent = jdata.get("props", {}).get("pageProps", {}).get("job", {}).get("content", {})
                                        if isinstance(jcontent, dict):
                                            desc_parts = [jcontent.get("description", ""), jcontent.get("closing", "")]
                                            for lst in jcontent.get("lists", []):
                                                if isinstance(lst, dict):
                                                    desc_parts.append(lst.get("text", ""))
                                                    # Content is HTML with the actual requirements
                                                    html_content = lst.get("content", "")
                                                    if html_content:
                                                        desc_parts.append(re.sub(r'<[^>]+>', ' ', html_content))
                                            description = " ".join(p for p in desc_parts if p)
                                time.sleep(0.5)  # rate limit
                            except Exception:
                                pass
                            if not description:
                                description = posting.get("text", "")
                            jobs.append({
                                "title": posting.get("text", ""),
                                "company": source["name"],
                                "location": loc,
                                "url": job_url,
                                "description": description,
                                "posted_at": None,
                            })
                        if len(postings) < per_page:
                            break  # Last page
                    else:
                        if page_num == 1:
                            print(f"  [warn] Spotify API returned {resp.status_code}")
                        break
            except Exception as e:
                print(f"  [warn] Spotify API error: {e}")

        elif source.get("ats") == "join" or "join.com/companies/" in source["url"]:
            # JOIN.com: Next.js page with job data in __NEXT_DATA__ → props.pageProps.initialState.jobs.items
            try:
                resp = requests.get(source["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                if resp.status_code == 200:
                    import re as _re
                    nd_match = _re.search(r'<script id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>(.*?)</script>', resp.text, _re.DOTALL)
                    if nd_match:
                        nd = json.loads(nd_match.group(1))
                        items = nd.get("props", {}).get("pageProps", {}).get("initialState", {}).get("jobs", {}).get("items", [])
                        for posting in items:
                            if not isinstance(posting, dict):
                                continue
                            title = posting.get("title", "")
                            if not title:
                                continue
                            city = posting.get("city", {}) or {}
                            loc_parts = [city.get("cityName", ""), city.get("countryName", "")]
                            location = ", ".join(p for p in loc_parts if p) or source.get("region", "")
                            slug = posting.get("idParam", "")
                            job_url = f"{source['url'].rstrip('/')}/{slug}" if slug else source["url"]
                            jobs.append({
                                "title": title,
                                "company": source["name"],
                                "location": location,
                                "url": job_url,
                                "description": title,
                                "posted_at": None,
                            })
                        if items:
                            print(f"  [join] {len(items)} jobs from {source['name']}")
                        else:
                            print(f"  [join] No jobs found for {source['name']}")
                    else:
                        print(f"  [join] Could not find __NEXT_DATA__ for {source['name']}")
                else:
                    print(f"  [join] HTTP {resp.status_code} for {source['name']}")
            except Exception as e:
                print(f"  [join] Error fetching {source['name']}: {e}")

        elif source.get("playwright"):
            if "linkedin.com/company/" in source["url"].lower():
                print(f"  [linkedin] Skipping {source['name']} - LinkedIn search is handled by boards-major batch")
            else:
                jobs = _scrape_company_career_page(source)

        else:
            print(f"  [skip] {source['name']} - no public ATS API detected. "
                  f"Check manually: {source['url']}")
    except Exception as e:
        print(f"  [error] Failed to fetch {source['name']}: {e}")

    return jobs


def search_linkedin(query, location="India", max_results=500):
    """Search LinkedIn Guest API for jobs matching a query (paginated)."""
    jobs = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    page_size = 25  # LinkedIn returns ~25 results per page
    max_pages = min(3, (max_results + page_size - 1) // page_size)
    try:
        for page_num in range(max_pages):
            start = page_num * page_size
            params = {"keywords": query, "location": location, "start": start}
            retries = 3
            for attempt in range(retries):
                resp = requests.get(
                    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                    params=params,
                    headers=headers,
                    timeout=15,
                )
                if resp.status_code == 429:
                    wait = (attempt + 1) * 10
                    print(f"  [web] LinkedIn 429 for '{query}' in {location}, retry {attempt+1}/{retries} in {wait}s")
                    time.sleep(wait)
                    continue
                break
            if resp.status_code != 200:
                if page_num == 0:
                    print(f"  [web] LinkedIn HTTP {resp.status_code} for '{query}' in {location}")
                break

            html = resp.text
            # Parse job cards from LinkedIn guest HTML
            titles = re.findall(r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>\s*([^<]+?)\s*</h3>', html, re.DOTALL)
            companies = re.findall(r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>\s*<a[^>]*>\s*([^<]+?)\s*</a>', html, re.DOTALL)
            locations = re.findall(r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>\s*([^<]+?)\s*</span>', html, re.DOTALL)
            links = re.findall(r'<a[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"', html)
            posted_dates = re.findall(r'<time[^>]*datetime="([^"]+)"', html)

            # Fallback patterns
            if not titles:
                titles = re.findall(r'"title":"([^"]+)"', html)
                companies = re.findall(r'"companyName":"([^"]+)"', html)
                locations = re.findall(r'"formattedLocation":"([^"]+)"', html)
                links = re.findall(r'"jobUrl":"([^"]+)"', html)

            if not titles:
                break  # No more results

            min_len = min(len(titles), len(companies), len(locations))
            
            # Helper to fetch a single description
            def _fetch_desc(idx):
                url = links[idx] if idx < len(links) else ""
                full_desc = ""
                if url:
                    try:
                        jd_resp = requests.get(url, headers=headers, timeout=5)
                        if jd_resp.status_code == 200:
                            jd_html = jd_resp.text
                            desc_match = re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>', jd_html, re.DOTALL)
                            if desc_match:
                                full_desc = strip_html(desc_match.group(1))[:2000]
                            if not full_desc:
                                desc_match2 = re.search(r'"description":\s*"([^"]+)"', jd_html)
                                if desc_match2:
                                    full_desc = desc_match2.group(1)[:2000]
                    except Exception:
                        pass
                return idx, full_desc or f"LinkedIn job: {titles[idx]} at {companies[idx]} in {locations[idx]}"

            # Fetch all descriptions in parallel using ThreadPoolExecutor
            from concurrent.futures import ThreadPoolExecutor as TPE, as_completed
            descs = [f"LinkedIn job: {titles[i]} at {companies[i]} in {locations[i]}" for i in range(min_len)]
            
            with TPE(max_workers=min(15, min_len)) as tpe:
                futures = [tpe.submit(_fetch_desc, i) for i in range(min_len)]
                for fut in as_completed(futures):
                    try:
                        idx, d_text = fut.result()
                        descs[idx] = d_text
                    except Exception:
                        pass

            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i].strip(),
                    "company": companies[i].strip(),
                    "location": locations[i].strip(),
                    "url": links[i] if i < len(links) else "",
                    "description": descs[i],
                    "posted_at": posted_dates[i].strip() if i < len(posted_dates) else None,
                })

            if len(jobs) >= max_results:
                break
            time.sleep(1)  # Polite delay between pages

        if jobs:
            print(f"  [web] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [web] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [web] Error searching '{query}' in {location}: {e}")
    return jobs


def search_linkedin_au(query, location="Australia", max_results=500):
    jobs = search_linkedin(query, location, max_results)
    au_kw = ["australia", "sydney", "melbourne", "brisbane", "perth", "adelaide", "canberra", "gold coast", "newcastle", "au"]
    return [j for j in jobs if any(k in j.get("location", "").lower() for k in au_kw)]

def search_linkedin_nz(query, location="New Zealand", max_results=500):
    jobs = search_linkedin(query, location, max_results)
    nz_kw = ["new zealand", "nz", "auckland", "wellington", "christchurch", "hamilton", "tauranga", "dunedin", "queenstown"]
    return [j for j in jobs if any(k in j.get("location", "").lower() for k in nz_kw)]

def search_linkedin_sg(query, location="Singapore", max_results=500):
    jobs = search_linkedin(query, location, max_results)
    sg_kw = ["singapore", "sg"]
    return [j for j in jobs if any(k in j.get("location", "").lower() for k in sg_kw)]

def search_linkedin_jp(query, location="Japan", max_results=500):
    jobs = search_linkedin(query, location, max_results)
    jp_kw = ["japan", "tokyo", "osaka", "kyoto", "yokohama", "nagoya", "sapporo", "fukuoka", "kobe"]
    return [j for j in jobs if any(k in j.get("location", "").lower() for k in jp_kw)]

def search_linkedin_kr(query, location="South Korea", max_results=500):
    jobs = search_linkedin(query, location, max_results)
    kr_kw = ["south korea", "korea", "seoul", "busan", "incheon", "daegu", "daejeon"]
    return [j for j in jobs if any(k in j.get("location", "").lower() for k in kr_kw)]

def search_linkedin_hk(query, location="Hong Kong", max_results=500):
    jobs = search_linkedin(query, location, max_results)
    hk_kw = ["hong kong", "hk"]
    return [j for j in jobs if any(k in j.get("location", "").lower() for k in hk_kw)]

def search_linkedin_uk(query, location="United Kingdom", max_results=500):
    return search_linkedin(query, location, max_results)

def search_linkedin_de(query, location="Germany", max_results=500):
    return search_linkedin(query, location, max_results)


def search_indeed(query, location="India", max_results=500):
    """Search Indeed for jobs matching a query using Playwright (paginated)."""
    jobs = []
    loc_param = location.replace(" ", "+")
    query_param = query.replace(" ", "+")
    page_size = 15  # Indeed shows ~15 results per page
    max_pages = min(3, (max_results + page_size - 1) // page_size)
    try:
        for page_num in range(max_pages):
            start = page_num * 10  # Indeed uses start=0, 10, 20...
            page_url = f"https://www.indeed.com/jobs?q={query_param}&l={loc_param}&start={start}"
            html = _playwright_html(page_url)
            titles = re.findall(r'class="jcs-JobTitle[^"]*"[^>]*>\s*<span[^>]*>([^<]+)', html)
            companies = re.findall(r'data-testid="company-name"[^>]*>([^<]+)', html)
            if not companies:
                companies = re.findall(r'[Cc]ompany[Nn]ame[^"]*"[^>]*>\s*([^<]+)', html)
            if not companies:
                companies = re.findall(r'class="[^"]*companyName[^"]*"[^>]*>\s*([^<]+)', html)
            locations = re.findall(r'data-testid="text-location"[^>]*>([^<]+)', html)
            if not locations:
                locations = re.findall(r'class="[^"]*companyLocation[^"]*"[^>]*>\s*([^<]+)', html)
            links = re.findall(r'class="jcs-JobTitle[^"]*"[^>]*href="([^"]+)"', html)
            if not links:
                links = re.findall(r'href="/company/jobs/view/[^"]+"', html)
            # Extract relative date strings like "Posted 3 days ago", "Just posted"
            date_texts = re.findall(r'class="[^"]*date[^"]*"[^>]*>([^<]+)', html)
            if not date_texts:
                date_texts = re.findall(r'data-testid="myJobsStateDate"[^>]*>([^<]+)', html)

            if not titles:
                break  # No more results

            min_len = min(len(titles), len(companies), len(locations))
            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                job_url = "https://www.indeed.com" + links[i] if i < len(links) and links[i].startswith("/") else (links[i] if i < len(links) else "")
                posted_at = _parse_relative_date(date_texts[i]) if i < len(date_texts) else None
                jobs.append({
                    "title": titles[i].strip(),
                    "company": companies[i].strip() if i < len(companies) else "Unknown",
                    "location": locations[i].strip() if i < len(locations) else location,
                    "url": job_url,
                    "description": f"Indeed job: {titles[i]} at {companies[i]} in {locations[i]}",
                    "posted_at": posted_at,
                })

            if len(jobs) >= max_results:
                break
            time.sleep(2)  # Polite delay between pages

        if jobs:
            print(f"  [indeed] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [indeed] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [indeed] Error searching '{query}': {e}")
    return jobs


def search_indeed_au(query, location="Australia", max_results=500):
    return search_indeed(query, location, max_results)

def search_indeed_nz(query, location="New Zealand", max_results=500):
    return search_indeed(query, location, max_results)

def search_indeed_sg(query, location="Singapore", max_results=500):
    return search_indeed(query, location, max_results)

def search_indeed_jp(query, location="Japan", max_results=500):
    return search_indeed(query, location, max_results)

def search_indeed_kr(query, location="South Korea", max_results=500):
    return search_indeed(query, location, max_results)

def search_indeed_hk(query, location="Hong Kong", max_results=500):
    return search_indeed(query, location, max_results)

def search_indeed_uk(query, location="United Kingdom", max_results=500):
    return search_indeed(query, location, max_results)

def search_indeed_de(query, location="Germany", max_results=500):
    return search_indeed(query, location, max_results)


def _indeed_parse_page(html, location):
    """Parse Indeed NL job listings from HTML. Returns list of job dicts."""
    titles = re.findall(r'class="jcs-JobTitle[^"]*"[^>]*>\s*<span[^>]*>([^<]+)', html)
    companies = re.findall(r'data-testid="company-name"[^>]*>([^<]+)', html)
    if not companies:
        companies = re.findall(r'[Cc]ompany[Nn]ame[^"]*"[^>]*>\s*([^<]+)', html)
    if not companies:
        companies = re.findall(r'class="[^"]*companyName[^"]*"[^>]*>\s*([^<]+)', html)
    locations = re.findall(r'data-testid="text-location"[^>]*>([^<]+)', html)
    if not locations:
        locations = re.findall(r'class="[^"]*companyLocation[^"]*"[^>]*>\s*([^<]+)', html)
    links = re.findall(r'class="jcs-JobTitle[^"]*"[^>]*href="([^"]+)"', html)
    if not links:
        links = re.findall(r'href="/company/jobs/view/[^"]+"', html)

    if not titles:
        return []

    jobs = []
    min_len = min(len(titles), len(companies), len(locations))
    for i in range(min_len):
        job_url = "https://nl.indeed.com" + links[i] if i < len(links) and links[i].startswith("/") else (links[i] if i < len(links) else "")
        jobs.append({
            "title": titles[i].strip(),
            "company": companies[i].strip() if i < len(companies) else "Unknown",
            "location": locations[i].strip() if i < len(locations) else location,
            "url": job_url,
            "description": f"Indeed NL job: {titles[i]} at {companies[i]} in {locations[i]}",
        })
    return jobs


def search_indeed_nl(query, location="Netherlands", max_results=500):
    """Search Indeed Netherlands for jobs via HTTP + Playwright fallback."""
    jobs = []
    query_param = query.replace(" ", "+")
    page_size = 15
    max_pages = min(3, (max_results + page_size - 1) // page_size)
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
    try:
        for page_num in range(max_pages):
            start = page_num * 10
            page_url = f"https://nl.indeed.com/vacatures?q={query_param}&l=Netherlands&start={start}"
            # Try HTTP first — Indeed sends job data in initial HTML
            html = ""
            try:
                resp = requests.get(page_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    html = resp.text
            except Exception:
                pass
            # Fall back to Playwright if HTTP returned nothing parseable
            page_jobs = _indeed_parse_page(html, location)
            if not page_jobs:
                try:
                    pw_html = _playwright_html(page_url, timeout=20000, wait_ms=3000)
                    page_jobs = _indeed_parse_page(pw_html, location)
                except Exception:
                    pass
            if not page_jobs:
                break
            jobs.extend(page_jobs[:max_results - len(jobs)])
            if len(jobs) >= max_results:
                break
            time.sleep(1.5)

        if jobs:
            print(f"  [indeed-nl] {len(jobs)} jobs for '{query}' in Netherlands")
        else:
            print(f"  [indeed-nl] No jobs parsed for '{query}' in Netherlands")
    except Exception as e:
        print(f"  [indeed-nl] Error searching '{query}': {e}")
    return jobs


def search_welcome_to_nl(query, location="Netherlands", max_results=500):
    """Search Welcome to NL (welcome-to-nl.nl/jobs) via Elastic App Search API.

    Uses the Nuxt site's internal Elastic search API with a static Bearer token.
    """
    api_url = "https://jobportal.ent.europe-west4.gcp.elastic-cloud.com/api/as/v1/engines/rvo/search"
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": "Bearer search-o21ix7ak2jiao92yvzceums2",
        "Accept": "application/json",
    })
    jobs = []
    page_size = 50
    page = 1
    consecutive_errors = 0
    try:
        while len(jobs) < max_results:
            payload = {
                "page": {"current": page, "size": min(page_size, max_results - len(jobs))},
                "query": query,
                "sort": [{"created_at": "desc"}],
            }
            try:
                resp = session.post(api_url, json=payload, timeout=30)
                if resp.status_code != 200:
                    if page == 1:
                        print(f"  [welcome-to-nl] API returned HTTP {resp.status_code}")
                    break
                consecutive_errors = 0
            except Exception:
                consecutive_errors += 1
                if consecutive_errors >= 2:
                    break
                time.sleep(2)
                continue
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            for r in results:
                raw = r.get("_meta", {}).get("raw", r)
                title = raw.get("title", {}).get("raw", "") or ""
                if not title:
                    continue
                company = raw.get("company_name", {}).get("raw", "Unknown")
                locs = raw.get("locations", {}).get("raw", [])
                loc = locs[0] if locs else "Netherlands"
                url = raw.get("url", {}).get("raw", "")
                job_fn = raw.get("job_functions", {}).get("raw", [])
                seniority = raw.get("seniority", {}).get("raw", "")
                work_mode = raw.get("work_mode", {}).get("raw", "")
                # Since Welcome to NL is managed by RVO (Netherlands Enterprise Agency) specifically for registered
                # highly skilled migrant sponsors, all listed roles support visa sponsorship and relocation by default.
                description = f"{title} at {company}. Seniority: {seniority or 'N/A'}, Work mode: {work_mode or 'N/A'}, Functions: {', '.join(job_fn) if job_fn else 'N/A'}. Visa sponsorship and relocation support available."
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": url,
                    "description": description,
                })
                if len(jobs) >= max_results:
                    break
            total_results = data.get("meta", {}).get("page", {}).get("total_results", 0)
            if page * page_size >= total_results:
                break
            page += 1
            time.sleep(1)
            # Recreate session periodically to avoid stale connections
            if page % 5 == 0:
                session.close()
                session = requests.Session()
                session.headers.update({
                    "Content-Type": "application/json",
                    "Authorization": "Bearer search-o21ix7ak2jiao92yvzceums2",
                    "Accept": "application/json",
                })

        if jobs:
            print(f"  [welcome-to-nl] {len(jobs)} jobs for '{query}' in Netherlands")
        else:
            print(f"  [welcome-to-nl] No jobs for '{query}' in Netherlands")
    except Exception as e:
        print(f"  [welcome-to-nl] Error searching '{query}': {e}")
    finally:
        session.close()
    return jobs


def search_naukri(query, location="India", max_results=500):
    """Search Naukri for jobs matching a query using their API (paginated)."""
    jobs = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        "appid": "109",
        "clientid": "d3skt0p",
        "systemid": "Naukri",
        "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
        "Referer": "https://www.naukri.com/",
    })
    try:
        session.get("https://www.naukri.com", timeout=15)
        keyword = query.replace(" ", "+")
        session.headers["Referer"] = f"https://www.naukri.com/{keyword.replace('+', '-')}-jobs"

        max_pages = 3  # Fetch up to 3 pages
        for page_num in range(1, max_pages + 1):
            api_url = f"https://www.naukri.com/jobapi/v2/search?keyword={keyword}&location={location}&pageNo={page_num}"
            resp = session.get(api_url, timeout=15)
            if resp.status_code != 200:
                if page_num == 1:
                    print(f"  [naukri] Naukri HTTP {resp.status_code} for '{query}'")
                break
            data = resp.json()
            listings = data.get("list", [])
            if not listings:
                break
            for job in listings:
                if len(jobs) >= max_results:
                    break
                title = job.get("post", "").strip()
                if not title:
                    title = job.get("JOB_SPEC", "").strip()
                company = job.get("companyName", "Unknown").strip()
                loc_raw = job.get("cityfield") or ""
                loc_clean = re.sub(r'\s{2,}', ', ', loc_raw).strip()
                loc_clean = re.sub(r'\s*\(.*?\)\s*', '', loc_clean)
                loc_clean = ', '.join(dict.fromkeys(loc_clean.split(', ')))
                for tag in ["Metropolitan Cities", "Top", "Popular Locations", "Preferred Jobseeker",
                             "Anywhere in", "South India", "West India", "North India",
                             "Southindia", "westindia", "northindia"]:
                    loc_clean = loc_clean.replace(tag, "").strip()
                loc_clean = re.sub(r',\s*,', ',', loc_clean).strip(', ')
                location_str = loc_clean if loc_clean else location
                job_url = job.get("urlStr", "")
                desc_snippet = job.get("jobDesc", "") or ""
                keywords = job.get("keywords", "") or ""
                posted_at = job.get("addDate")[:10] if job.get("addDate") else None
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location_str,
                    "url": job_url,
                    "description": f"Naukri job: {title} at {company}. {desc_snippet}. Skills: {keywords}",
                    "posted_at": posted_at,
                })
            if len(jobs) >= max_results:
                break
            time.sleep(1)  # Polite delay between pages

        if jobs:
            print(f"  [naukri] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [naukri] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [naukri] Error searching '{query}': {e}")
    return jobs


def search_instahyre(query, location="India", max_results=500):
    """Search Instahyre for jobs matching a query using their API (paginated)."""
    jobs = []
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instahyre.com/jobs/",
        "X-Requested-With": "XMLHttpRequest",
    })
    query_param = query.replace(" ", "+")
    query_lower = query.lower()
    query_terms = query_lower.split()
    max_pages = 3  # Fetch up to 3 pages
    try:
        for page_num in range(1, max_pages + 1):
            api_url = f"https://www.instahyre.com/api/v1/job_search?search={query_param}&location={location}&page={page_num}"
            resp = scraper.get(api_url, timeout=15)
            if resp.status_code != 200:
                if page_num == 1:
                    print(f"  [instahyre] Instahyre HTTP {resp.status_code} for '{query}'")
                break
            data = resp.json()
            objects = data.get("objects", [])
            if not objects:
                break
            for obj in objects:
                title = obj.get("candidate_title") or obj.get("title", "").strip()
                company = obj.get("employer", {}).get("company_name", "Unknown").strip()
                loc = obj.get("locations", location).strip()
                keywords = " ".join(obj.get("keywords", []) or []).lower()
                # Client-side filter since API doesn't filter for anonymous users
                text = f"{title.lower()} {company.lower()} {keywords}"
                if not all(term in text for term in query_terms):
                    continue
                job_url = obj.get("public_url", "")
                keywords_raw = ", ".join(obj.get("keywords", []) or [])
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": job_url,
                    "description": f"Instahyre job: {title} at {company}. Skills: {keywords_raw}",
                    "posted_at": obj.get("created_at") or obj.get("published_at") or None,
                })
                if len(jobs) >= max_results:
                    break
            if len(jobs) >= max_results:
                break
            # Check if there are more pages
            if not data.get("meta", {}).get("next"):
                break
            time.sleep(1)  # Polite delay between pages

        if jobs:
            print(f"  [instahyre] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [instahyre] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [instahyre] Error searching '{query}': {e}")
    return jobs


def search_womenintech(query, location="UK", max_results=500):
    """Search WomenInTech UK job board using Playwright with Load More support."""
    jobs = []
    try:
        # Use Load More / infinite scroll to get all listings
        html = _playwright_load_more("https://jobs.womenintech.co.uk/jobs", max_clicks=5, wait_ms=2000)
        if not html:
            print(f"  [womenintech] No response for '{query}'")
            return jobs
        links = re.findall(r'href="(/jobs/\d+-[^"]+)"', html)
        seen = set()
        for link in links:
            if len(jobs) >= max_results:
                break
            parts = link.split("/")[-1]
            without_id = re.sub(r'^\d+-', '', parts)
            if "-at-" in without_id:
                title_part, company = without_id.rsplit("-at-", 1)
                title = title_part.replace("-", " ").title()
                company_pretty = company.replace("-", " ").title()
            else:
                title = without_id.replace("-", " ").title()
                company_pretty = "Unknown"
            if title in seen:
                continue
            seen.add(title)
            full_url = f"https://jobs.womenintech.co.uk{link}"
            jobs.append({
                "title": title,
                "company": company_pretty,
                "location": "UK",
                "url": full_url,
                "description": f"WomenInTech UK job: {title} at {company_pretty}",
            })
        if jobs:
            print(f"  [womenintech] {len(jobs)} jobs for '{query}' in UK")
        else:
            print(f"  [womenintech] No jobs parsed")
    except Exception as e:
        print(f"  [womenintech] Error: {e}")
    return jobs


def search_weworkremotely(query, location="Remote", max_results=500):
    """Search We Work Remotely for jobs matching a query via their public RSS feed."""
    jobs = []
    import requests
    import xml.etree.ElementTree as ET
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get("https://weworkremotely.com/remote-jobs.rss", headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  [weworkremotely] HTTP {resp.status_code}")
            return jobs
        
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        
        q_terms = [term.strip().lower() for term in query.lower().split() if term.strip()]
        
        for item in items:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            region_el = item.find("region")
            pubdate_el = item.find("pubDate")
            
            title = title_el.text if title_el is not None else ""
            link = link_el.text if link_el is not None else ""
            description = desc_el.text if desc_el is not None else ""
            region = region_el.text if region_el is not None else "Remote"
            posted_at = None
            if pubdate_el is not None and pubdate_el.text:
                try:
                    from email.utils import parsedate_to_datetime
                    posted_at = parsedate_to_datetime(pubdate_el.text).strftime("%Y-%m-%d")
                except Exception:
                    pass
            
            match = True
            for term in q_terms:
                if term not in title.lower() and term not in description.lower():
                    match = False
                    break
            
            if match and title:
                title_clean = title
                company = "We Work Remotely"
                if ":" in title:
                    parts = title.split(":", 1)
                    company = parts[0].strip()
                    title_clean = parts[1].strip()
                
                jobs.append({
                    "title": title_clean,
                    "company": company,
                    "location": region,
                    "url": link,
                    "description": description,
                    "posted_at": posted_at,
                })
                
                if len(jobs) >= max_results:
                    break
        if jobs:
            print(f"  [weworkremotely] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [weworkremotely] Error: {e}")
    return jobs


def search_simplyhired(query, location="India", max_results=500):
    """Search SimplyHired for jobs matching a query using Playwright (paginated).
    Fetches actual job descriptions from detail pages for better scoring."""
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://www.simplyhired.com/search?q={q}&pn={page_num}" if page_num > 1 else f"https://www.simplyhired.com/search?q={q}"
            html = _playwright_html(page_url)
            if not html:
                if page_num == 1:
                    print(f"  [simplyhired] No response for '{query}'")
                break
            titles = re.findall(r'<h2[^>]*>\s*<a[^>]*>\s*([^<]+)', html)
            companies = re.findall(r'data-testid="companyName"[^>]*>\s*([^<]+)', html)
            locs = re.findall(r'data-testid="searchSerpJobLocation"[^>]*>\s*([^<]+)', html)
            links = re.findall(r'href="(/job/[^"]+)"', html)

            if not titles:
                break  # No more results

            min_len = min(len(titles), len(companies))
            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                url = f"https://www.simplyhired.com{links[i]}" if i < len(links) else ""
                l = locs[i].strip() if i < len(locs) else location
                jobs.append({
                    "title": titles[i].strip(), "company": companies[i].strip(),
                    "location": l, "url": url,
                    "description": "",  # filled below from detail page
                })

            if len(jobs) >= max_results:
                break
            time.sleep(2)  # Polite delay between pages

        # Fetch actual job descriptions from detail pages (top results)
        for job in jobs[:20]:  # Limit to top 20 to avoid excessive requests
            if not job["url"]:
                continue
            try:
                detail_html = _playwright_html(job["url"])
                if detail_html:
                    # Extract job description text
                    desc_match = re.search(
                        r'data-testid="viewJobBodyJobFullDescriptionContent"[^>]*>(.*?)</div>',
                        detail_html, re.DOTALL)
                    if not desc_match:
                        desc_match = re.search(
                            r'class="[^"]*jobposting-description[^"]*"[^>]*>(.*?)</div>',
                            detail_html, re.DOTALL)
                    if not desc_match:
                        desc_match = re.search(
                            r'id="[^"]*job[-_]?desc[^"]*"[^>]*>(.*?)</(?:div|section)>',
                            detail_html, re.DOTALL | re.IGNORECASE)
                    if desc_match:
                        job["description"] = strip_html(desc_match.group(1))[:3000]
                    else:
                        # Fallback: grab all text from the main content area
                        body = re.sub(r'<script[^>]*>.*?</script>', '', detail_html, flags=re.DOTALL)
                        body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL)
                        text = strip_html(body)
                        # Take a reasonable chunk as description
                        if len(text) > 500:
                            job["description"] = text[:3000]
                time.sleep(1)  # Polite delay between detail page fetches
            except Exception:
                pass
            # Set fallback description if still empty
            if not job["description"]:
                job["description"] = f"SimplyHired: {job['title']} at {job['company']}"

        if jobs:
            print(f"  [simplyhired] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [simplyhired] Error: {e}")
    return jobs


def search_glassdoor(query, location="India", max_results=500):
    """Search Glassdoor for jobs matching a query using Playwright (paginated)."""
    jobs = []
    loc_map = {"India": "113", "Remote": "0", "Germany": "96", "Netherlands": "178",
               "UK": "243", "United Kingdom": "243", "USA": "1", "United States": "1",
               "Canada": "3", "Australia": "16", "Switzerland": "215", "Singapore": "200"}
    loc_id = loc_map.get(location, "113")
    query_param = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={query_param}&locT=C&locId={loc_id}&p={page_num}"
            html = _playwright_html(url)
            if not html:
                if page_num == 1:
                    print(f"  [glassdoor] No response for '{query}' in {location}")
                break
            titles = re.findall(r'class="[^"]*JobCard_jobTitle[^"]*"[^>]*>\s*([^<]+)', html)
            companies = re.findall(r'class="[^"]*EmployerProfile_compactEmployerName[^"]*"[^>]*>\s*([^<]+)', html)
            if not companies:
                companies = re.findall(r'class="[^"]*EmployerProfile_employerName[^"]*"[^>]*>\s*([^<]+)', html)
            locations = re.findall(r'class="[^"]*JobCard_location[^"]*"[^>]*>\s*([^<]+)', html)
            links = re.findall(r'href="(/partner/jobListing[^"]+)"', html)

            if not titles:
                break  # No more results

            min_len = min(len(titles), len(companies), len(locations))
            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                link = "https://www.glassdoor.co.in" + links[i] if i < len(links) and links[i].startswith("/") else (links[i] if i < len(links) else "")
                jobs.append({
                    "title": titles[i].strip(),
                    "company": companies[i].strip() if i < len(companies) else "Unknown",
                    "location": locations[i].strip() if i < len(locations) else location,
                    "url": link,
                    "description": f"Glassdoor job: {titles[i]} at {companies[i]}",
                })

            if len(jobs) >= max_results:
                break
            time.sleep(2)  # Polite delay between pages

        if jobs:
            print(f"  [glassdoor] {len(jobs)} jobs for '{query}' in {location}")
        else:
            print(f"  [glassdoor] No jobs parsed for '{query}' in {location}")
    except Exception as e:
        print(f"  [glassdoor] Error searching '{query}': {e}")
    return jobs


def search_glassdoor_au(query, location="Australia", max_results=500):
    return search_glassdoor(query, location, max_results)

def search_glassdoor_sg(query, location="Singapore", max_results=500):
    return search_glassdoor(query, location, max_results)

def search_glassdoor_uk(query, location="United Kingdom", max_results=500):
    return search_glassdoor(query, location, max_results)

def search_glassdoor_de(query, location="Germany", max_results=500):
    return search_glassdoor(query, location, max_results)


def _playwright_scrape(url, selector, extract_fn, wait_selector=None):
    """Generic helper to scrape JS-rendered pages using Playwright + stealth."""
    context = None
    try:
        browser = _get_browser()
        context = _create_context(browser, url)
        page = context.new_page()
        _block_unnecessary_resources(page)
        _with_stealth(page)
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=10000)
        results = page.eval_on_selector_all(selector, extract_fn)
        _save_context_state(context, url)
        return results
    except Exception as e:
        return []
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        _check_reclaim_playwright()


def _playwright_load_more(url, max_clicks=5, wait_ms=2000):
    """Load a page with Playwright and click 'Load More'/'Show More' buttons
    or scroll for infinite scroll, returning the full HTML after expansion.

    Supports:
    - Buttons/links with text: Load More, Show More, More Results, View More, See More
    - Infinite scroll: scrolls to bottom and waits for new content
    """
    context = None
    try:
        browser = _get_browser()
        context = _create_context(browser, url)
        page = context.new_page()
        _block_unnecessary_resources(page)
        _with_stealth(page)
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        for _ in range(max_clicks):
            # Try clicking "Load More" / "Show More" style buttons
            load_more_btn = page.query_selector(
                'button:has-text("Load More"), button:has-text("load more"), '
                'button:has-text("Show More"), button:has-text("show more"), '
                'button:has-text("Show more results"), button:has-text("show more results"), '
                'button:has-text("More Results"), button:has-text("more results"), '
                'button:has-text("View More"), button:has-text("view more"), '
                'button:has-text("See More"), button:has-text("see more"), '
                'button:has-text("More jobs"), button:has-text("more jobs"), '
                'button:has-text("Load more jobs"), button:has-text("load more jobs"), '
                'button:has-text("View All"), button:has-text("view all"), '
                'a:has-text("Load More"), a:has-text("load more"), '
                'a:has-text("Show More"), a:has-text("show more"), '
                'a:has-text("Show more results"), a:has-text("show more results"), '
                'a:has-text("More Results"), a:has-text("more results"), '
                'a:has-text("View More"), a:has-text("view more"), '
                'a:has-text("See More"), a:has-text("see more"), '
                'a:has-text("More jobs"), a:has-text("more jobs"), '
                'a:has-text("View All"), a:has-text("view all"), '
                '[class*="load-more"], [class*="loadMore"], '
                '[class*="show-more"], [class*="showMore"], '
                '[class*="load-more-jobs"], [class*="loadMoreJobs"], '
                '[class*="show-more-results"], [class*="showMoreResults"], '
                '[class*="view-more"], [class*="viewMore"], '
                '[class*="view-all"], [class*="viewAll"], '
                '[data-testid*="load-more"], [data-testid*="show-more"]'
            )
            if load_more_btn:
                try:
                    load_more_btn.scroll_into_view_if_needed()
                    load_more_btn.click()
                    page.wait_for_timeout(wait_ms)
                    continue
                except Exception:
                    pass

            # Fallback: try "Next" pagination link
            next_btn = page.query_selector(
                'a:has-text("Next"), a:has-text("next"), a:has-text("›"), a:has-text("»"), '
                'button:has-text("Next"), button:has-text("next"), button:has-text("›"), button:has-text("»"), '
                'a[rel="next"], link[rel="next"], '
                '[aria-label="Next"], [aria-label="next"], '
                '[class*="next"]'
            )
            if next_btn:
                try:
                    next_btn.scroll_into_view_if_needed()
                    next_btn.click()
                    page.wait_for_timeout(wait_ms)
                    continue
                except Exception:
                    pass

            # Fallback: infinite scroll - scroll to bottom
            prev_height = page.evaluate("document.body.scrollHeight")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(wait_ms)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                break  # No new content loaded

        html = page.content()
        _save_context_state(context, url)
        return html
    except Exception as e:
        return ""
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        _check_reclaim_playwright()

def _playwright_html(url, timeout=30000, wait_ms=2000):
    """Load a JS-rendered page with Playwright + stealth and return full HTML."""
    context = None
    try:
        browser = _get_browser()
        context = _create_context(browser, url)
        page = context.new_page()
        page.set_default_timeout(timeout)
        _block_unnecessary_resources(page)
        _with_stealth(page)
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        page.wait_for_timeout(wait_ms)
        html = page.content()
        _save_context_state(context, url)
        return html
    except Exception as e:
        return ""
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        _check_reclaim_playwright()


_remoteok_cache = None
_remoteok_cache_time = 0

def search_remoteok(query, location="Remote", max_results=500):
    """Search RemoteOK using public JSON API (no auth needed)."""
    global _remoteok_cache, _remoteok_cache_time
    jobs = []
    term = query.lower()
    try:
        now = time.time()
        if now - _remoteok_cache_time > 60:
            resp = requests.get(
                "https://remoteok.com/api",
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            _remoteok_cache = data if isinstance(data, list) else []
            _remoteok_cache_time = now
        for item in _remoteok_cache:
            if not isinstance(item, dict) or "id" not in item:
                continue
            title = (item.get("position") or "").strip()
            company = (item.get("company") or "Unknown").strip()
            url = (item.get("url") or "").strip()
            tags = [t.lower() for t in (item.get("tags") or [])]
            desc = (item.get("description") or "").lower()
            if not title or not url:
                continue
            if term != "remote" and term not in title.lower() and term not in desc and not any(term in t for t in tags):
                continue
            salary_parts = []
            if item.get("salary_min"):
                salary_parts.append(f"${int(item['salary_min']):,}")
            if item.get("salary_max"):
                salary_parts.append(f"${int(item['salary_max']):,}")
            salary_str = f" ({' - '.join(salary_parts)})" if salary_parts else ""
            jobs.append({
                "title": title,
                "company": company,
                "location": "Remote",
                "url": url,
                "description": f"RemoteOK: {title} at {company}{salary_str}",
            })
            if len(jobs) >= max_results:
                break
        if jobs:
            print(f"  [remoteok] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [remoteok] Error: {e}")
    return jobs


def search_skipthedrive(query, location="Remote", max_results=500):
    """Search SkipTheDrive for remote jobs using HTTP (paginated)."""
    jobs = []
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'mobile': False})
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://www.skipthedrive.com/page/{page_num}/?s={q}" if page_num > 1 else f"https://www.skipthedrive.com/?s={q}"
            resp = scraper.get(page_url, timeout=20)
            if resp.status_code != 200:
                break
            html = resp.text
            titles = re.findall(r'class="[^"]*entry-title[^"]*"[^>]*>\s*<a[^>]*>\s*([^<]+)', html)
            links = re.findall(r'class="[^"]*entry-title[^"]*"[^>]*>\s*<a[^"]*href="([^"]+)"', html)
            if not titles:
                break
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                t = titles[i].strip()
                t = re.sub(r'&#8211;', '-', t)
                t = re.sub(r'&#\d+;', '', t)
                jobs.append({
                    "title": t, "company": "SkipTheDrive",
                    "location": "Remote", "url": links[i] if i < len(links) else "",
                    "description": f"SkipTheDrive: {t}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(1)
        if jobs:
            print(f"  [skipthedrive] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [skipthedrive] Error: {e}")
    return jobs


def search_workingnomads(query, location="Remote", max_results=500):
    """Search WorkingNomads using Playwright with Load More / infinite scroll."""
    jobs = []
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        page.goto("https://www.workingnomads.com/jobs", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Click Load More / scroll for more results
        for _ in range(5):
            load_more = page.query_selector(
                'button:has-text("Load More"), button:has-text("Show More"), '
                'button:has-text("Show more results"), button:has-text("More jobs"), '
                'button:has-text("View More"), button:has-text("See More"), '
                'a:has-text("Load More"), a:has-text("Show More"), '
                'a:has-text("Show more results"), a:has-text("More jobs"), '
                'a:has-text("View More"), a:has-text("See More"), '
                '[class*="load-more"], [class*="loadMore"], '
                '[class*="show-more"], [class*="showMore"], '
                '[class*="view-more"], [class*="viewMore"]'
            )
            if load_more:
                try:
                    load_more.scroll_into_view_if_needed()
                    load_more.click()
                    page.wait_for_timeout(2000)
                    continue
                except Exception:
                    pass
            # Infinite scroll fallback
            prev_height = page.evaluate("document.body.scrollHeight")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                break

        links = page.eval_on_selector_all(
            'a[href*="/jobs/"]',
            '''els => els.map(e => ({
                text: e.innerText.trim(),
                href: e.href
            })).filter(j => j.text.length > 3 && j.href.includes('/jobs/'))'''
        )
        context.close()
        q_lower = query.lower()
        q_terms = q_lower.split()
        for l in links:
            if len(jobs) >= max_results:
                break
            text_lower = l['text'].lower()
            if not all(term in text_lower for term in q_terms):
                continue
            title_parts = l['text'].split('\n')
            title = title_parts[0].strip()
            company = title_parts[1].strip() if len(title_parts) > 1 else "WorkingNomads"
            jobs.append({
                "title": title, "company": company,
                "location": "Remote", "url": l['href'],
                "description": f"WorkingNomads: {title}",
            })
        if jobs:
            print(f"  [workingnomads] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [workingnomads] Error: {e}")
    return jobs


def search_jobspresso(query, location="Remote", max_results=500):
    """Search Jobspresso using Playwright with Load More button clicking."""
    jobs = []
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        page.goto("https://jobspresso.co/remote-work/", timeout=30000, wait_until="load")
        page.wait_for_timeout(3000)

        # Click Load More buttons to expand listings
        for _ in range(5):
            load_more = page.query_selector(
                'button:has-text("Load More"), a:has-text("Load More"), '
                'button:has-text("Show More"), a:has-text("Show More"), '
                'button:has-text("Show more results"), a:has-text("Show more results"), '
                'button:has-text("More jobs"), a:has-text("More jobs"), '
                'button:has-text("View More"), a:has-text("View More"), '
                'button:has-text("See More"), a:has-text("See More"), '
                '[class*="load_more"], [class*="load-more"], '
                '[class*="show-more"], [class*="showMore"], '
                '[class*="view-more"], [class*="viewMore"], '
                '.load_more_jobs, a.load_more_listings'
            )
            if load_more:
                try:
                    load_more.scroll_into_view_if_needed()
                    load_more.click()
                    page.wait_for_timeout(2000)
                except Exception:
                    break
            else:
                # Try infinite scroll
                prev_height = page.evaluate("document.body.scrollHeight")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == prev_height:
                    break

        items = page.eval_on_selector_all(
            'li.job_listing',
            '''els => els.map(el => ({
                title: el.getAttribute('data-title') || '',
                href: el.getAttribute('data-href') || ''
            })).filter(j => j.title.length > 3)'''
        )
        context.close()
        q_lower = query.lower()
        q_terms = q_lower.split()
        for item in items:
            if len(jobs) >= max_results:
                break
            if not all(term in item['title'].lower() for term in q_terms):
                continue
            t = item['title']
            company = "Jobspresso"
            if " at " in t:
                parts = t.rsplit(" at ", 1)
                t = parts[0].strip()
                company = parts[1].strip()
            jobs.append({
                "title": t, "company": company,
                "location": "Remote", "url": item['href'],
                "description": f"Jobspresso: {t}",
            })
        if jobs:
            print(f"  [jobspresso] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [jobspresso] Error: {e}")
    return jobs


def search_englishjobsearch(query, location="Remote", max_results=500):
    """Search EnglishJobSearch.ch for English-speaking jobs in Switzerland/EU (paginated).

    Uses plain HTTP + regex (the site is server-rendered, no JS needed).
    """
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'mobile': False})
        for page_num in range(1, max_pages + 1):
            page_url = f"https://englishjobsearch.ch/jobs/{q}?page={page_num}" if page_num > 1 else f"https://englishjobsearch.ch/jobs/{q}"
            resp = scraper.get(page_url, timeout=15)
            if resp.status_code != 200:
                if page_num == 1:
                    print(f"  [englishjobsearch] HTTP {resp.status_code}")
                break
            if page_num > 1:
                time.sleep(1)  # polite delay between pages

            html = resp.text
            # Each job is a div with class "job js-job"
            job_blocks = re.findall(
                r'class="job js-job[^"]*"[^>]*>(.*?)(?=class="job js-job|$)',
                html, re.DOTALL,
            )
            if not job_blocks:
                break
            for block in job_blocks:
                if len(jobs) >= max_results:
                    break
                # Title from <h3 itemprop="title">
                h3 = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.DOTALL)
                title = re.sub(r'<[^>]+>', '', h3.group(1)).strip() if h3 else ""
                if not title or len(title) < 4:
                    continue

                # Clickout link
                link_match = re.search(r'href="(/clickout/[^"]+)"', block)
                url = f"https://englishjobsearch.ch{link_match.group(1)}" if link_match else ""
                # Unescape &amp; in URL
                url = url.replace("&amp;", "&")

                # Company and location from <li> text nodes (1st = company, 2nd = location)
                li_texts = re.findall(r'<li[^>]*>.*?</svg>\s*([^<]+)', block, re.DOTALL)
                li_texts = [t.strip() for t in li_texts if t.strip()]
                company = li_texts[0] if len(li_texts) >= 1 else "EnglishJobSearch"
                loc = li_texts[1] if len(li_texts) >= 2 else "Switzerland"

                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": url,
                    "description": f"EnglishJobSearch: {title} at {company}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(1)
        if jobs:
            print(f"  [englishjobsearch] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [englishjobsearch] Error: {e}")
    return jobs


def search_bulldogjob(query, location="Remote", max_results=500):
    """Search BulldogJob.pl for tech jobs in Poland/EU with Load More support."""
    jobs = []
    q = query.replace(" ", "+")
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        page.goto(f"https://bulldogjob.pl/companies/jobs/s/skills,{q}", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Click Load More / scroll for more results
        for _ in range(5):
            load_more = page.query_selector(
                'button:has-text("Load More"), button:has-text("Pokaż więcej"), '
                'a:has-text("Load More"), a:has-text("Pokaż więcej"), '
                '[class*="load-more"], [class*="loadMore"], '
                'button:has-text("More"), a:has-text("More")'
            )
            if load_more:
                try:
                    load_more.scroll_into_view_if_needed()
                    load_more.click()
                    page.wait_for_timeout(2000)
                    continue
                except Exception:
                    pass
            # Infinite scroll fallback
            prev_height = page.evaluate("document.body.scrollHeight")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                break

        links = page.eval_on_selector_all(
            'a[href*="/companies/jobs/"]',
            '''els => els.map(e => ({
                text: e.innerText.trim(),
                href: e.href
            })).filter(j => j.text.length > 5 && !j.text.includes('Praca'))'''
        )
        context.close()
        for l in links[:max_results]:
            t_parts = l['text'].split('\n')
            title = t_parts[0].strip()
            company = t_parts[1].strip() if len(t_parts) > 1 else "BulldogJob"
            jobs.append({
                "title": title, "company": company,
                "location": "Poland/EU", "url": l['href'],
                "description": f"BulldogJob: {title}",
            })
        if jobs:
            print(f"  [bulldogjob] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [bulldogjob] Error: {e}")
    return jobs


def search_workatstartup(query, location="Remote", max_results=500):
    """Search WorkAtAStartup (YC) using Playwright with infinite scroll."""
    jobs = []
    exp = PROFILE["years_experience"]
    min_exp = max(0, exp - 1)
    top_skills = PROFILE["core_skills"][:3]
    is_sap = any("sap" in s.lower() for s in top_skills)
    role = "swe" if is_sap else "eng"
    role_type = "be"  # backend
    url = (
        f"https://www.workatastartup.com/companies?"
        f"demographic=any&hasEquity=any&hasSalary=any&industry=any"
        f"&interviewProcess=any&jobType=fulltime&layout=list-compact"
        f"&role={role}&role_type={role_type}&sortBy=created_desc"
        f"&tab=any&usVisaNotRequired=any&minExperience={min_exp}"
    )
    try:
        # Use Load More / infinite scroll to get more results
        html = _playwright_load_more(url, max_clicks=5, wait_ms=3000)
        if not html:
            print(f"  [workatstartup] No response")
            return jobs
        # Extract from expanded HTML
        titles = re.findall(r'font-bold[^>]*>\s*([^<]{4,}?)\s*<', html)
        links = re.findall(r'href="(/companies/[^"]+)"', html)
        seen = set()
        for i in range(len(titles)):
            if len(jobs) >= max_results:
                break
            t = titles[i].strip()
            if t in seen or len(t) < 5:
                continue
            seen.add(t)
            link = f"https://www.workatastartup.com{links[i]}" if i < len(links) else url
            jobs.append({
                "title": t,
                "company": "YC Startup",
                "location": "Remote/US",
                "url": link,
                "description": f"WorkAtAStartup: {t}",
            })
        if jobs:
            print(f"  [workatstartup] {len(jobs)} jobs")
    except Exception as e:
        print(f"  [workatstartup] Error: {e}")
    return jobs


def search_stepstone(query, location="Germany", max_results=500):
    """Search StepStone Germany for jobs using Playwright (paginated)."""
    jobs = []
    q = query.replace(" ", "-").lower()
    loc = location.lower().replace(" ", "-")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://www.stepstone.de/jobs/{q}/{loc}.html?page={page_num}" if page_num > 1 else f"https://www.stepstone.de/jobs/{q}/{loc}.html"
            titles = _playwright_scrape(
                page_url,
                "[data-at='job-item-title']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 3)",
                wait_selector="[data-at='job-item-title']",
            )
            if not titles:
                break
            companies = _playwright_scrape(
                page_url,
                "[data-at='job-item-company']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)",
            )
            locations = _playwright_scrape(
                page_url,
                "[data-at='job-item-location']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)",
            )
            links = _playwright_scrape(
                page_url,
                "a[data-at='job-item-title']",
                "els => els.map(e => e.href)",
            )
            min_len = min(len(titles), len(companies), len(links))
            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i],
                    "company": companies[i] if i < len(companies) else "Unknown",
                    "location": locations[i] if i < len(locations) else location,
                    "url": links[i],
                    "description": f"StepStone: {titles[i]} at {companies[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs:
            print(f"  [stepstone] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [stepstone] Error: {e}")
    return jobs


def search_monsterde(query, location="Germany", max_results=500):
    """Search Monster Germany for jobs using Playwright (paginated)."""
    jobs = []
    q = query.replace(" ", "+").lower()
    loc = location.lower().replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://www.monster.de/jobs/suche/?q={q}&where={loc}&page={page_num}" if page_num > 1 else f"https://www.monster.de/jobs/suche/?q={q}&where={loc}"
            titles = _playwright_scrape(
                page_url,
                "[data-testid='jobTitle']",
                "els => els.map(e => e.textContent.trim()).filter(t => t.length > 1)",
                wait_selector="[data-testid='jobTitle']",
            )
            if not titles:
                break
            companies = _playwright_scrape(
                page_url,
                "[data-testid='company']",
                "els => els.map(e => e.textContent.trim()).filter(t => t.length > 1)",
            )
            locations = _playwright_scrape(
                page_url,
                "[data-testid='location']",
                "els => els.map(e => e.textContent.trim()).filter(t => t.length > 1)",
            )
            links = _playwright_scrape(
                page_url,
                "a[data-testid='jobTitle']",
                "els => els.map(e => e.href)",
            )
            min_len = min(len(titles), len(companies), len(links))
            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i],
                    "company": companies[i] if i < len(companies) else "Unknown",
                    "location": locations[i] if i < len(locations) else location,
                    "url": links[i],
                    "description": f"MonsterDE: {titles[i]} at {companies[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs:
            print(f"  [monsterde] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [monsterde] Error: {e}")
    return jobs


_adzuna_last_call = 0.0  # rate limiter for Adzuna queries
_adzuna_delay = 10.0     # base delay between queries (safe for dedicated thread)

def search_adzuna(query, location="Remote", max_results=500):
    """Search Adzuna UK for jobs using cloudscraper (paginated, bypasses Cloudflare)."""
    global _adzuna_last_call, _adzuna_delay
    elapsed = time.time() - _adzuna_last_call
    if elapsed < _adzuna_delay:
        time.sleep(_adzuna_delay - elapsed)
    _adzuna_last_call = time.time()
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'mobile': False})
        for page_num in range(1, max_pages + 1):
            url = f"https://www.adzuna.co.uk/search?q={q}&page={page_num}" if page_num > 1 else f"https://www.adzuna.co.uk/search?q={q}"
            
            # Request with robust retry loop for HTTP 429
            resp = None
            retries = 3
            backoff = 15.0
            for attempt in range(retries + 1):
                resp = scraper.get(url, timeout=20)
                if resp.status_code == 429:
                    print(f"  [adzuna] HTTP 429 — rate limited on attempt {attempt + 1}/{retries + 1}, backing off {backoff}s")
                    _adzuna_delay = max(_adzuna_delay, 15.0)  # dynamically increase inter-query delay
                    time.sleep(backoff)
                    backoff *= 2.0  # exponential backoff
                else:
                    break
            
            if resp.status_code != 200:
                if page_num == 1:
                    print(f"  [adzuna] HTTP {resp.status_code}")
                break
            if page_num > 1:
                time.sleep(2)  # polite delay between pages
            html = resp.text
            # Extract job articles
            article_pattern = r'<article[^>]*data-aid="(\d+)"[^>]*>(.*?)</article>'
            articles = re.findall(article_pattern, html, re.DOTALL)
            if not articles:
                break
            for aid, card in articles:
                if len(jobs) >= max_results:
                    break
                # Title from <h2><a href="...">TITLE</a></h2>
                title_match = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', card, re.DOTALL)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
                if not title or len(title) < 4:
                    continue
                # URL from title link or job link
                url_match = re.search(r'href="(https://www\.adzuna\.co\.uk/jobs/details/\d+)"', card)
                job_url = url_match.group(1) if url_match else ""
                # Company from ui-company div (text or link)
                company_match = re.search(r'<div[^>]*class="[^"]*ui-company[^"]*"[^>]*>(.*?)</div>', card, re.DOTALL)
                company = re.sub(r'<[^>]+>', '', company_match.group(1)).strip() if company_match else "Unknown"
                # Location from ui-location div
                loc_match = re.search(r'class="[^"]*ui-location[^"]*"[^>]*>([^<]+)', card)
                loc = loc_match.group(1).strip() if loc_match else location
                # Description from ad-description
                desc_match = re.search(r'class="[^"]*ad-description[^"]*"[^>]*>(.*?)</span>', card, re.DOTALL)
                desc_text = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ""
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": job_url,
                    "description": desc_text if desc_text else f"Adzuna: {title} at {company}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(1)
        if jobs:
            print(f"  [adzuna] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [adzuna] Error: {e}")
    return jobs


_adzuna_au_last_call = 0.0
_adzuna_au_delay = 10.0

def search_adzuna_au(query, location="Australia", max_results=500):
    """Search Adzuna Australia for jobs using cloudscraper (paginated)."""
    global _adzuna_au_last_call, _adzuna_au_delay
    elapsed = time.time() - _adzuna_au_last_call
    if elapsed < _adzuna_au_delay:
        time.sleep(_adzuna_au_delay - elapsed)
    _adzuna_au_last_call = time.time()
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'mobile': False})
        for page_num in range(1, max_pages + 1):
            url = f"https://www.adzuna.com.au/search?cat=2&loc=105392&q={q}&page={page_num}" if page_num > 1 else f"https://www.adzuna.com.au/search?cat=2&loc=105392&q={q}"
            resp = None
            retries = 3
            backoff = 15.0
            for attempt in range(retries + 1):
                resp = scraper.get(url, timeout=20)
                if resp.status_code == 429:
                    print(f"  [adzuna-au] HTTP 429 — rate limited, backing off {backoff}s")
                    _adzuna_au_delay = max(_adzuna_au_delay, 15.0)
                    time.sleep(backoff)
                    backoff *= 2.0
                else:
                    break
            if resp.status_code != 200:
                if page_num == 1: print(f"  [adzuna-au] HTTP {resp.status_code}")
                break
            if page_num > 1: time.sleep(2)
            html = resp.text
            articles = re.findall(r'<article[^>]*data-aid="(\d+)"[^>]*>(.*?)</article>', html, re.DOTALL)
            if not articles: break
            for aid, card in articles:
                if len(jobs) >= max_results: break
                title_match = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', card, re.DOTALL)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
                if not title or len(title) < 4: continue
                url_match = re.search(r'href="(https://www\.adzuna\.com\.au/jobs/details/\d+)"', card)
                job_url = url_match.group(1) if url_match else ""
                company_match = re.search(r'<div[^>]*class="[^"]*ui-company[^"]*"[^>]*>(.*?)</div>', card, re.DOTALL)
                company = re.sub(r'<[^>]+>', '', company_match.group(1)).strip() if company_match else "Unknown"
                loc_match = re.search(r'class="[^"]*ui-location[^"]*"[^>]*>([^<]+)', card)
                loc = loc_match.group(1).strip() if loc_match else location
                desc_match = re.search(r'class="[^"]*ad-description[^"]*"[^>]*>(.*?)</span>', card, re.DOTALL)
                desc_text = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ""
                jobs.append({
                    "title": title, "company": company, "location": loc,
                    "url": job_url, "description": desc_text or f"Adzuna AU: {title} at {company}",
                })
            if len(jobs) >= max_results: break
            time.sleep(1)
        if jobs: print(f"  [adzuna-au] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [adzuna-au] Error: {e}")
    return jobs


def search_freelancermap(query, location="Germany", max_results=100):
    """Search freelancermap.com (German IT freelancer marketplace, many SAP projects)."""
    from bs4 import BeautifulSoup
    q = query.replace(" ", "+")
    jobs = []
    seen = set()
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://www.freelancermap.com/projects?search={q}&page={page_num}"
            html = _playwright_html(page_url)
            if not html:
                break
            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("[class*=project-card]")
            if not cards:
                break
            page_jobs = 0
            for card in cards:
                if len(jobs) >= max_results:
                    break
                text = card.get_text(separator=" | ", strip=True)
                parts = [p.strip() for p in text.split(" | ") if p.strip()]
                if len(parts) < 2:
                    continue
                company = parts[0]
                title = parts[1] if len(parts) > 1 else ""
                loc = next((p for p in parts[2:] if any(c in p for c in [",", "Remote", "On-site"])), "")
                link = card.find("a", href=re.compile(r"^/project/"))
                url = f"https://www.freelancermap.com{link['href']}" if link and link.get("href") else ""
                dedup_key = url or f"{title}|{company}"
                if title and dedup_key not in seen:
                    seen.add(dedup_key)
                    jobs.append({
                        "title": title, "company": company, "location": loc,
                        "url": url, "description": text,
                    })
                    page_jobs += 1
            if page_jobs == 0 or len(jobs) >= max_results:
                break
        if jobs:
            print(f"  [freelancermap] {len(jobs)} jobs for '{query}' ({page_num} pages)")
    except Exception as e:
        print(f"  [freelancermap] Error: {e}")
    return jobs


def _accept_dpg_privacy(page):
    """Click 'Akkoord' on DPG Media privacy gate if present. Returns True if accepted."""
    try:
        if 'privacy' in page.url.lower() or 'consent' in page.url.lower():
            accept = page.query_selector('button:has-text("Akkoord")')
            if accept:
                with page.expect_navigation(timeout=15000):
                    accept.click()
                page.wait_for_timeout(3000)
                return True
    except Exception:
        pass
    return False


def search_intermediair(query, location="Netherlands", max_results=500):
    """Search Intermediair.nl for jobs using Playwright (DPG Media, paginated)."""
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        for page_num in range(1, max_pages + 1):
            url = f"https://www.intermediair.nl/vacature/zoeken?q={q}&sort=relevance&page={page_num}"
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            _accept_dpg_privacy(page)
            page.wait_for_timeout(2000)
            cards = page.evaluate(f"""() => {{
                const links = document.querySelectorAll('a[href*="/vacature/"]');
                const results = [];
                const seen = new Set();
                for (const link of links) {{
                    const h2 = link.querySelector('h2');
                    if (!h2) continue;
                    const title = h2.innerText.trim();
                    if (!title || title.length < 3) continue;
                    const key = title.toLowerCase();
                    if (seen.has(key)) continue;
                    seen.add(key);
                    const strong = link.querySelector('strong');
                    const company = strong ? strong.innerText.trim() : '';
                    const spans = link.querySelectorAll('span');
                    let location = '';
                    for (const sp of spans) {{
                        const t = sp.innerText.trim();
                        if (t && t !== company && t.length > 1 && !t.includes('\u20AC') && !t.includes('uur') && !t.includes('UUR')) {{
                            location = t;
                            break;
                        }}
                    }}
                    const href = link.getAttribute('href') || '';
                    results.push({{ title, company, location, url: href.startsWith('http') ? href : 'https://www.intermediair.nl' + href }});
                    if (results.length >= {max_results}) break;
                }}
                return results;
            }}""")
            for card in cards:
                jobs.append({
                    "title": card["title"],
                    "company": card["company"] if card["company"] else "Unknown",
                    "location": card["location"] if card["location"] else location,
                    "url": card["url"],
                    "description": f"Intermediair: {card['title']} at {card['company']}",
                })
            if len(jobs) >= max_results:
                break
            page.wait_for_timeout(2000)
        context.close()
        if jobs:
            print(f"  [intermediair] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [intermediair] Error: {e}")
    return jobs


def search_nationalevacaturebank(query, location="Netherlands", max_results=500):
    """Search NationaleVacaturebank.nl for jobs using Playwright (DPG Media, paginated)."""
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        for page_num in range(1, max_pages + 1):
            url = f"https://www.nationalevacaturebank.nl/vacature/zoeken?q={q}&sort=relevance&page={page_num}"
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            _accept_dpg_privacy(page)
            page.wait_for_timeout(2000)
            cards = page.evaluate(f"""() => {{
                const links = document.querySelectorAll('a[href*="/vacature/"]');
                const results = [];
                const seen = new Set();
                for (const link of links) {{
                    const h2 = link.querySelector('h2');
                    if (!h2) continue;
                    const title = h2.innerText.trim();
                    if (!title || title.length < 3) continue;
                    const key = title.toLowerCase();
                    if (seen.has(key)) continue;
                    seen.add(key);
                    const strong = link.querySelector('strong');
                    const company = strong ? strong.innerText.trim() : '';
                    const spans = link.querySelectorAll('span');
                    let location = '';
                    for (const sp of spans) {{
                        const t = sp.innerText.trim();
                        if (t && t !== company && t.length > 1 && !t.includes('\u20AC') && !t.includes('uur') && !t.includes('UUR')) {{
                            location = t;
                            break;
                        }}
                    }}
                    const href = link.getAttribute('href') || '';
                    results.push({{ title, company, location, url: href.startsWith('http') ? href : 'https://www.nationalevacaturebank.nl' + href }});
                    if (results.length >= {max_results}) break;
                }}
                return results;
            }}""")
            for card in cards:
                jobs.append({
                    "title": card["title"],
                    "company": card["company"] if card["company"] else "Unknown",
                    "location": card["location"] if card["location"] else location,
                    "url": card["url"],
                    "description": f"NationaleVacaturebank: {card['title']} at {card['company']}",
                })
            if len(jobs) >= max_results:
                break
            page.wait_for_timeout(2000)
        context.close()
        if jobs:
            print(f"  [nationalevacaturebank] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [nationalevacaturebank] Error: {e}")
    return jobs


def search_philips(query="", location="Remote", max_results=500):
    """Search Philips careers for Software Dev + IT jobs using Playwright (Phenom ATS, paginated).

    Pagination: ?s=1 (page 1), ?from=10&s=1 (page 2), ?from=20&s=1 (page 3), etc.
    Two category pages: software-development and IT.
    """
    jobs = []
    categories = [
        ("software-development", "https://www.careers.philips.com/global/en/c/software-development-jobs"),
        ("it", "https://www.careers.philips.com/global/en/c/it-jobs"),
    ]
    max_pages = 5  # 10 jobs per page
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        for cat_name, base_url in categories:
            for pg in range(max_pages):
                offset = pg * 10
                if pg == 0:
                    url = f"{base_url}?s=1"
                else:
                    url = f"{base_url}?from={offset}&s=1"
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)  # Phenom widget needs time to render
                cards = page.evaluate("""() => {
                    const links = document.querySelectorAll('a[data-ph-at-id="job-link"]');
                    const results = [];
                    for (const link of links) {
                        const title = (link.getAttribute('data-ph-at-job-title-text') || '').trim();
                        if (!title || title.length < 3) continue;
                        const location = (link.getAttribute('data-ph-at-job-location-text') || '').trim();
                        const href = link.getAttribute('href') || '';
                        const descEl = link.closest('li') ? link.closest('li').querySelector('p.job-description') : null;
                        const desc = descEl ? descEl.innerText.trim() : '';
                        results.push({ title, location, url: href, description: desc });
                    }
                    return results;
                }""")
                if not cards:
                    break
                for card in cards:
                    if len(jobs) >= max_results:
                        break
                    href = card["url"]
                    if href and not href.startswith("http"):
                        href = f"https://www.careers.philips.com{href}"
                    jobs.append({
                        "title": card["title"],
                        "company": "Philips",
                        "location": card["location"] if card["location"] else "Global",
                        "url": href,
                        "description": card["description"] if card["description"] else f"Philips: {card['title']}",
                    })
                if len(jobs) >= max_results:
                    break
                page.wait_for_timeout(2000)
        context.close()
        if jobs:
            print(f"  [philips] {len(jobs)} jobs across {len(categories)} categories")
    except Exception as e:
        print(f"  [philips] Error: {e}")
    return jobs


def search_liebherr(query="", location="Remote", max_results=500):
    """Search Liebherr IT/Software vacancies using Playwright (paginated, &p=N).

    Pagination: base URL (page 1), &p=2 (page 2), &p=3, etc.
    Filtered to Information technology / Software category.
    """
    jobs = []
    base_url = "https://www.liebherr.com/en-int/careers/job-vacancies-5370609"
    filter_param = "filter=1557062143"
    max_pages = 5  # 10 jobs per page, up to 50
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        for pg in range(1, max_pages + 1):
            if pg == 1:
                url = f"{base_url}?{filter_param}"
            else:
                url = f"{base_url}?{filter_param}&p={pg}"
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            # Dismiss cookie banner if present
            try:
                btn = page.query_selector('button:has-text("Accept all")')
                if not btn:
                    btn = page.query_selector('button:has-text("Accept All")')
                if btn:
                    btn.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass
            cards = page.evaluate("""() => {
                const items = document.querySelectorAll('li[data-testid="jlp-item"]');
                const results = [];
                for (const item of items) {
                    const titleLink = item.querySelector('p.font-text-bold a');
                    if (!titleLink) continue;
                    const title = titleLink.innerText.trim();
                    if (!title || title.length < 3) continue;
                    const href = titleLink.getAttribute('href') || '';
                    // Location + dept + company in a comma-separated <p>
                    const infoParagraphs = item.querySelectorAll('p');
                    let location = '', company = 'Liebherr';
                    for (const p of infoParagraphs) {
                        if (p.classList.contains('font-text-bold')) continue;
                        const text = p.innerText.trim();
                        if (text && text.includes(',')) {
                            const parts = text.split(',').map(s => s.trim());
                            location = parts[0] || '';
                            company = parts.length >= 3 ? parts[parts.length - 1] : 'Liebherr';
                            break;
                        }
                    }
                    results.push({ title, location, company, url: href });
                }
                return results;
            }""")
            if not cards:
                break
            for card in cards:
                if len(jobs) >= max_results:
                    break
                href = card["url"]
                if href and not href.startswith("http"):
                    href = f"https://www.liebherr.com{href}"
                jobs.append({
                    "title": card["title"],
                    "company": card["company"] if card["company"] else "Liebherr",
                    "location": card["location"] if card["location"] else "Germany",
                    "url": href,
                    "description": f"Liebherr: {card['title']}",
                })
            if len(jobs) >= max_results:
                break
            # Check if there's a next page
            has_next = page.evaluate("""() => {
                const pag = document.querySelector('patternlib-pagination');
                if (!pag) return false;
                const current = parseInt(pag.getAttribute('current-page') || '0');
                const last = parseInt(pag.getAttribute('last-page') || '0');
                return current < last;
            }""")
            if not has_next:
                break
            page.wait_for_timeout(2000)
        context.close()
        if jobs:
            print(f"  [liebherr] {len(jobs)} IT/Software vacancies")
    except Exception as e:
        print(f"  [liebherr] Error: {e}")
    return jobs


def search_reed(query, location="Remote", max_results=500):
    """Search Reed.co.uk for jobs using Playwright (paginated)."""
    jobs = []
    q = query.replace(" ", "-").lower()
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            url = f"https://www.reed.co.uk/jobs/{q}-jobs?page={page_num}" if page_num > 1 else f"https://www.reed.co.uk/jobs/{q}-jobs"
            titles = _playwright_scrape(
                url,
                "a[data-qa='job-card-title']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 3)",
                wait_selector="a[data-qa='job-card-title']",
            )
            if not titles:
                break
            companies = _playwright_scrape(
                url,
                "div[data-qa='job-posted-by'] a",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)",
            )
            locations = _playwright_scrape(
                url,
                "li[data-qa='job-metadata-location']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)",
            )
            links = _playwright_scrape(
                url,
                "a[data-qa='job-card-title']",
                "els => els.map(e => e.href)",
            )
            min_len = min(len(titles), len(companies), len(links))
            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i],
                    "company": companies[i] if i < len(companies) else "Unknown",
                    "location": locations[i] if i < len(locations) else "UK",
                    "url": links[i],
                    "description": f"Reed: {titles[i]} at {companies[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs:
            print(f"  [reed] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [reed] Error: {e}")
    return jobs


def search_jobsite(query, location="Remote", max_results=500):
    """Search Jobsite.co.uk for jobs using Playwright (paginated, StepStone Group)."""
    jobs = []
    q = query.replace(" ", "-").lower()
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            url = f"https://www.jobsite.co.uk/jobs/{q}?page={page_num}" if page_num > 1 else f"https://www.jobsite.co.uk/jobs/{q}"
            titles = _playwright_scrape(
                url,
                "a[data-at='job-item-title']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 3)",
                wait_selector="a[data-at='job-item-title']",
            )
            if not titles:
                break
            companies = _playwright_scrape(
                url,
                "[data-at='job-item-company-name']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)",
            )
            locations = _playwright_scrape(
                url,
                "[data-at='job-item-location']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)",
            )
            links = _playwright_scrape(
                url,
                "a[data-at='job-item-title']",
                "els => els.map(e => e.href)",
            )
            min_len = min(len(titles), len(companies), len(links))
            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i],
                    "company": companies[i] if i < len(companies) else "Unknown",
                    "location": locations[i] if i < len(locations) else "UK",
                    "url": links[i],
                    "description": f"Jobsite: {titles[i]} at {companies[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs:
            print(f"  [jobsite] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [jobsite] Error: {e}")
    return jobs


# ---------------------------------------------------------------------------
# 4. EMAIL DIGEST
# ---------------------------------------------------------------------------

def _salary_html(salary_info):
    if not salary_info:
        return ""
    if salary_info["source"] == "jd":
        fmt = _format_salary(salary_info)
        return f'<p style="margin:0 0 4px;font-size:13px;color:#2e7d32;"><b>💰 {fmt}</b> (from JD)</p>'
    if salary_info["source"] == "levels.fyi" and salary_info.get("median_tc"):
        src = f'<a href="{salary_info["url"]}" style="color:#1a73e8;text-decoration:none;">Levels.fyi</a>'
        return f'<p style="margin:0 0 4px;font-size:13px;color:#2e7d32;"><b>💰 Median: {salary_info["median_tc"]}</b> from {src}</p>'
    return ""

def _format_salary(s):
    c = s.get("currency", "USD")
    fmt_min = f"{s['min']:,}" if s.get("min") else ""
    fmt_max = f"{s['max']:,}" if s.get("max") else ""
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}
    sym = symbols.get(c, c + " ")
    if fmt_min and fmt_max and fmt_min != fmt_max:
        return f"{sym}{fmt_min} - {sym}{fmt_max}"
    if fmt_min:
        return f"{sym}{fmt_min}"
    return ""

def _job_type_badge(m):
    jt = m.get("job_type", "") or ""
    if jt:
        return jt
    text = ((m.get("title", "") or "") + " " + (m.get("description", "") or "")).lower()
    if any(kw in text for kw in ["contract", "contractor", "freelance", "temporary", "12-month", "6-month"]):
        return "Contract"
    if any(kw in text for kw in ["full-time", "full time", "part-time", "part time", "permanent"]):
        return "Full-Time"
    return ""

def _card_rows(matches):
    rows = ""
    for m in matches:
        salary_line = _salary_html(m.get("salary_info"))
        url = m.get("url", "#")
        jt = _job_type_badge(m)
        jt_html = f"""<span style="display:inline-block;background:#fff3e0;color:#e65100;font-size:11px;padding:2px 6px;border-radius:4px;margin-left:6px;">{jt}</span>""" if jt else ""
        ea = _easy_apply_ats(m.get("company", ""))
        ea_html = f"""<span style="display:inline-block;background:#e8f5e9;color:#2e7d32;font-size:11px;padding:2px 6px;border-radius:4px;margin-left:6px;">✅ Easy Apply ({ea})</span>""" if ea and ea in EASY_APPLY_ATS else ""
        tr_status = m.get("tracker_status")
        tr_html = ""
        if tr_status:
            tr_date = m.get("tracker_date", "")
            tr_icon = "✅" if tr_status == "applied" else "❌" if tr_status == "rejected" else "⚠️"
            tr_bg = "#e8f5e9" if tr_status == "applied" else "#ffebee" if tr_status == "rejected" else "#fff8e1"
            tr_color = "#2e7d32" if tr_status == "applied" else "#c62828" if tr_status == "rejected" else "#f57f17"
            date_label = f" on {tr_date}" if tr_date else ""
            tr_html = f"""<br><span style="display:inline-block;background:{tr_bg};color:{tr_color};font-size:12px;padding:3px 8px;border-radius:4px;margin-top:6px;">{tr_icon} Already {tr_status}{date_label}</span>"""
        ago = m.get("ago", "") or ""
        posted = m.get("posted_at") or ""
        if hasattr(posted, 'strftime'):
            posted_str = posted.strftime("%Y-%m-%d")
        elif posted:
            posted_str = str(posted)[:10]
        else:
            posted_str = ""
        date_html = ""
        if ago:
            date_html = f"""<span style="margin-left:6px;font-size:11px;color:#999;">{ago}</span>"""
        elif posted_str:
            date_html = f"""<span style="margin-left:6px;font-size:11px;color:#999;">Posted {posted_str}</span>"""
        co_desc = _company_description(m.get("company", ""))
        co_desc_html = f"""<br><span style="font-size:12px;color:#888;">{co_desc}</span>""" if co_desc else ""
        rows += f"""
    <div style="border:1px solid #ddd;border-radius:8px;padding:16px;margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;">
        <div>
          <h3 style="margin:0 0 4px;font-size:16px;">{m['title']}</h3>
          <p style="margin:0 0 8px;color:#666;font-size:13px;">
            <a href="{url}" style="color:#1a73e8;text-decoration:none;">{m['company']}</a>
            <span style="display:inline-block;background:#e8f0fe;color:#1a73e8;font-size:11px;padding:2px 6px;border-radius:4px;margin-left:6px;">{m.get('source', '')}</span>
            {jt_html}{ea_html}
            <span style="margin-left:6px;font-size:12px;color:#888;">{m.get('location', 'N/A')}</span>{co_desc_html}{date_html}
          </p>
        </div>
        <div style="font-size:20px;font-weight:bold;white-space:nowrap;">{m['score']}%</div>
      </div>
      {salary_line}
      <p style="margin:0 0 8px;font-size:13px;color:#444;">{m.get('relocation_note', '')}{tr_html}</p>
      <ul style="margin:0 0 8px;font-size:13px;color:#444;">
        {''.join(f'<li>{s}</li>' for s in m.get('suggestions', []))}
      </ul>
      <a href="{url}" style="font-size:13px;">Open job posting &rarr;</a>
    </div>"""
    return rows

def _posted_days_ago(m):
    """Return number of days since posted_at, or -1 if unknown."""
    posted = m.get("posted_at")
    if not posted:
        return -1
    try:
        if isinstance(posted, str):
            if "T" in posted:
                dt = datetime.fromisoformat(posted.replace("Z", "+00:00")).replace(tzinfo=None)
            else:
                dt = datetime.strptime(posted[:10], "%Y-%m-%d")
        elif hasattr(posted, 'date'):
            dt = posted.replace(tzinfo=None) if hasattr(posted, 'tzinfo') and posted.tzinfo else posted
        else:
            return -1
        return (datetime.now() - dt).days
    except Exception:
        return -1

def build_email_html(matches, failed_parse=None):
    if not matches:
        body = "<p>No new matches above threshold today.</p>"
    else:
        # Group by recency: Fresh (≤7d or unknown), Recent (8-30d), Older (30+d)
        fresh = []
        recent = []
        older = []
        for m in matches:
            days = _posted_days_ago(m)
            if days < 0 or days <= 7:
                fresh.append(m)
            elif days <= 30:
                recent.append(m)
            else:
                older.append(m)

        # Sort each group by score descending
        fresh.sort(key=lambda x: x["score"], reverse=True)
        recent.sort(key=lambda x: x["score"], reverse=True)
        older.sort(key=lambda x: x["score"], reverse=True)

        sections = ""

        if fresh:
            sections += f"""
    <div style="border:2px solid #a5d6a7;border-radius:10px;padding:12px;margin-bottom:24px;">
      <h3 style="color:#2e7d32;margin:0 0 4px;">🟢 Fresh — Last 7 Days ({len(fresh)})</h3>
      <p style="font-size:12px;color:#666;margin:0 0 12px;">Apply quickly — these are new postings</p>
      {_card_rows(fresh)}
    </div>"""

        if recent:
            sections += f"""
    <div style="border:2px solid #ffcc80;border-radius:10px;padding:12px;margin-bottom:24px;">
      <h3 style="color:#e65100;margin:0 0 4px;">🟡 Recent — 1 to 4 Weeks ({len(recent)})</h3>
      <p style="font-size:12px;color:#666;margin:0 0 12px;">Still active — most companies take 2-4 weeks to close</p>
      {_card_rows(recent)}
    </div>"""

        if older:
            sections += f"""
    <div style="border:2px solid #bdbdbd;border-radius:10px;padding:12px;margin-bottom:24px;">
      <h3 style="color:#616161;margin:0 0 4px;">⚪ Older — 30+ Days ({len(older)})</h3>
      <p style="font-size:12px;color:#666;margin:0 0 12px;">May be filled — check if still open before applying</p>
      {_card_rows(older)}
    </div>"""

        body = f"""
      <h2>Daily job matches - {datetime.now().strftime('%d %b %Y')}</h2>
      <p>{len(matches)} role(s) scored above threshold.</p>
      {sections}
    """

    failed_html = ""
    if failed_parse:
        rows = ""
        for s in failed_parse:
            rows += f"""
        <div style="border:1px solid #eee;border-radius:6px;padding:10px;margin-bottom:6px;">
          <a href="{s['url']}" style="font-size:13px;color:#d32f2f;">{s['name']}</a>
        </div>
        """
        failed_html = f"""
    <hr style="margin:24px 0;">
    <h3 style="color:#d32f2f;">Failed to parse ({len(failed_parse)} companies)</h3>
    <p style="font-size:13px;color:#666;">These company career pages could not be scanned. Check manually for relevant roles.</p>
    {rows}
    """

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:900px;">
      {body}
      {failed_html}
    </body></html>
    """


def send_email(html_body, subject="Daily Job Matches", recipient=None, raise_on_error=False):
    gmail_address = os.environ.get("GMAIL_ADDRESS") or "kminterviewer@gmail.com"
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    sendgrid_key = os.environ.get("SENDGRID_API_KEY")
    if not recipient:
        recipient = os.environ.get("EMAIL_TO") or gmail_address

    # Prefer SendGrid (HTTP API) over SMTP — works on Vercel serverless
    if sendgrid_key:
        try:
            resp = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                json={
                    "personalizations": [{"to": [{"email": recipient}]}],
                    "from": {"email": gmail_address},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}],
                },
                headers={
                    "Authorization": f"Bearer {sendgrid_key}",
                },
                timeout=15,
            )
            resp.raise_for_status()
            print(f"Email sent to {recipient} via SendGrid")
            return True
        except Exception as e:
            print(f"Failed to send email via SendGrid: {e}")
            if raise_on_error:
                raise
            return False

    if not gmail_app_password:
        msg = "GMAIL_APP_PASSWORD not set in environment"
        print(f"Email not sent - {msg}")
        if raise_on_error:
            raise RuntimeError(msg)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, recipient, msg.as_string())
        print(f"Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        if raise_on_error:
            raise
        return False


def send_whatsapp(message):
    """Optional - requires Twilio account with WhatsApp sandbox or approved number."""
    sid = os.environ.get("TWILIO_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM")
    to_number = os.environ.get("WHATSAPP_TO")

    if not all([sid, token, from_number, to_number]):
        print("WhatsApp not sent - Twilio environment variables not fully set.")
        return False

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        resp = requests.post(
            url,
            auth=(sid, token),
            data={"From": from_number, "To": to_number, "Body": message},
            timeout=10,
        )
        if resp.status_code == 201:
            print("WhatsApp message sent.")
            return True
        else:
            print(f"WhatsApp send failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"WhatsApp error: {e}")
        return False


# ---------------------------------------------------------------------------
# 5. RESUME PARSER (auto-detect profile from any PDF)
# ---------------------------------------------------------------------------

# Broad tech skills vocabulary used for auto-detection from any resume
# Covers backend, frontend, cloud, DevOps, ERP/SAP, data, and more.
COMMON_TECH_KEYWORDS = [
    # Languages
    "java", "python", "javascript", "typescript", "golang", "go", "rust", "c++", "c#",
    "ruby", "php", "swift", "kotlin", "scala", "perl", "r",
    "node.js", "nodejs", "react", "angular", "vue.js", "vue", "svelte",
    # Backend frameworks
    "spring", "spring boot", "django", "flask", "express", "rails", "asp.net",
    ".net", "fastapi", "laravel",
    # Cloud & infra
    "aws", "azure", "gcp", "cloud", "docker", "kubernetes", "k8s", "terraform",
    "microservices", "distributed systems", "system design", "architecture",
    "kafka", "rabbitmq", "redis", "mysql", "postgresql", "mongodb", "cassandra",
    "elasticsearch", "rest api", "graphql", "grpc", "soap",
    "ci/cd", "jenkins", "github actions", "gitlab ci", "devops", "ansible",
    "puppet", "chef", "helm", "istio",
    # Data & ML
    "machine learning", "deep learning", "ai", "nlp", "tensorflow", "pytorch",
    "pandas", "numpy", "spark", "hadoop", "airflow",
    # Project management
    "agile", "scrum", "leadership", "mentoring", "jira", "confluence",
    # General tech
    "sql", "nosql", "database", "api", "backend", "frontend", "full stack",
    "linux", "unix", "bash", "shell", "git", "github", "gitlab",
    # SAP / ERP
    "sap", "abap", "sap s/4hana", "sap fico", "sap mm", "sap sd", "sap hana",
    "sap basis", "sap bw", "sap pi", "sap po", "sap successfactors",
    "sap ewm", "sap wm", "sap qm", "sap pm", "sap pp", "sap hr", "sap hcm",
    "sap ariba", "sap concur", "sap mdg", "sap grc", "sap solman",
    "sap activate", "sap fiori",
    "fico", "fi module", "controlling", "cost center accounting",
    "procurement", "inventory management", "material management",
    "sap implementation", "sap support", "idoc", "bapi", "rfc",
    "oracle", "oracle erp", "oracle fusion", "peoplesoft",
    "salesforce", "microsoft dynamics", "erp",
    # SAP tools & processes
    "servicenow", "solman", "solution manager", "panaya",
    "ltmc", "lsmw", "data migration",
    "p2p", "procure to pay", "procure-to-pay",
    "configuration", "customizing", "master data",
    "cutover", "hypercare", "go-live",
    "fiori", "sap gui",
]

# Keywords that are too short / ambiguous for substring matching in resumes.
# These require word-boundary regex to avoid false positives
# (e.g. "go" matching "go-live", "r" matching "your", "ai" matching "said").
_AMBIGUOUS_TECH_KEYWORDS = {"r", "go", "ai", "api", "c#", "c++", "vue", "git", "sql"}

def extract_text_from_pdf(path):
    """Extract all text from a PDF file using PyPDF2."""
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

_REQUIRED_RESUME_FIELDS = {
    "current_role": "Most recent job title (e.g. 'Senior Backend Engineer')",
    "years_experience": "Years of professional experience (e.g. 10)",
    "core_skills": "Technical skills list (e.g. Java, Python, AWS, Kubernetes)",
}


_MONTH_RE = re.compile(
    r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
    r'Dec(?:ember)?)[,.]?\s*\d{4}\b', re.IGNORECASE)
_PRESENT_RE = re.compile(r'\b(?:Present|Current|Till\s+Date|Ongoing)\b', re.IGNORECASE)
_YEAR_RANGE_RE = re.compile(r'\(?\d{4}\s*[-–—]\s*\d{4}\)?')
_TRAILING_DASH_RE = re.compile(r'\s*[–—]\s*$')

def _clean_role_title(raw_line, role_keywords):
    """Extract clean role title from a verbose resume experience line.

    Handles formats like:
      "Accenture (ATCI) — SAP MM/EWM Consultant - Team Lead Sep 2024 – Present"
      "Senior Software Engineer | Company Name | Jan 2020 - Present"
      "Company Name — Backend Engineer Sep 2020 – Dec 2023"
    Returns only the role portion (e.g. "SAP MM/EWM Consultant - Team Lead").
    """
    text = raw_line.strip()
    # 1. Strip date patterns: "Sep 2024", "January 2020", "Present", year ranges
    text = _MONTH_RE.sub('', text)
    text = _PRESENT_RE.sub('', text)
    text = _YEAR_RANGE_RE.sub('', text)
    text = _TRAILING_DASH_RE.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # 2. Split on em-dash (—) or pipe (|) — common company/role separators
    segments = re.split(r'\s*[—|]\s*', text)

    # 3. Pick the segment containing a role keyword
    for seg in segments:
        seg_clean = seg.strip(' -–,.')
        if any(kw in seg_clean.lower() for kw in role_keywords) and len(seg_clean) > 3:
            return re.sub(r'\s+', ' ', seg_clean).strip()

    # 4. Fallback: longest non-trivial segment
    segments = [s.strip(' -–,.') for s in segments if len(s.strip()) > 3]
    return max(segments, key=len) if segments else raw_line.strip()


def parse_resume_pdf(path):
    """
    Given a PDF resume path, extract name, email, current role, skills,
    and experience. Validates that required fields are present.
    Returns a tuple of (profile dict, missing_fields list).
    """
    raw = extract_text_from_pdf(path)
    lines = raw.split("\n")
    non_empty = [l.strip() for l in lines if l.strip()]

    profile = {
        "name": "", "email": "", "current_role": "",
        "core_skills": [], "years_experience": 0,
    }

    # --- Extract name (first non-title line is the name) ---
    title_keywords = ["engineer", "developer", "consultant", "architect", "manager",
                      "analyst", "specialist", "lead", "scientist"]
    for line in non_empty:
        cleaned = line.strip("|").strip().replace(" ", "")
        is_title = any(kw in cleaned.lower() for kw in title_keywords)
        if not is_title and len(cleaned) > 2:
            profile["name"] = cleaned
            break

    # --- Extract email ---
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", raw)
    if email_match:
        profile["email"] = email_match.group(0)

    # --- Extract most recent role (first job title in experience section) ---
    role_keywords = [
        "engineer", "developer", "architect", "manager", "lead", "intern",
        "consultant", "specialist", "analyst", "scientist", "director",
        "head", "principal", "staff", "sde", "swe",
    ]
    in_experience = False
    for line in non_empty:
        stripped = line.strip().lower()
        if any(kw in stripped for kw in ["experience", "work experience", "employment",
                                           "professional experience", "work history"]):
            in_experience = True
            continue
        if in_experience and not profile["current_role"]:
            if any(kw in stripped for kw in role_keywords) and len(stripped) > 5:
                profile["current_role"] = _clean_role_title(line.strip(), role_keywords)
        if in_experience and profile["current_role"] and any(
            kw in stripped for kw in ["education", "skills", "projects", "certifications"]
        ):
            break

    # --- Extract skills ---
    skill_section_text = ""
    in_skills = False
    for line in lines:
        stripped = line.strip().lower()
        if any(kw in stripped for kw in ["technical skills", "technologies", "tech stack",
                                           "skills &", "skills:", "core competencies",
                                           "programming languages", "tools &"]):
            in_skills = True
            continue
        if in_skills:
            if any(kw in stripped for kw in ["experience", "education", "projects",
                                              "certifications", "publications"]):
                if len(skill_section_text) > 50:
                    break
            skill_section_text += line + " "

    if not skill_section_text:
        skill_section_text = raw

    found_skills = set()
    text_lower = skill_section_text.lower()
    for kw in COMMON_TECH_KEYWORDS:
        # Use word-boundary regex for all keywords to avoid substring false positives
        # (e.g. "go" in "go-live", "r" in "your", "ai" in "said")
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            # Extra guard for ambiguous short keywords: require they appear in
            # an explicit skills/tools section, not just the general resume text
            if kw in _AMBIGUOUS_TECH_KEYWORDS and skill_section_text == raw:
                continue  # skip — only found in full-text fallback, too risky
            found_skills.add(kw)

    # SAP module inference: if "sap" is detected, scan for standalone SAP module
    # abbreviations (e.g. "EWM" in "SAP MM / EWM") and add combined "sap ewm" etc.
    if "sap" in found_skills:
        _SAP_MODULE_ABBREVS = {
            "ewm": "sap ewm", "wm": "sap wm", "qm": "sap qm",
            "pm": "sap pm", "pp": "sap pp", "hr": "sap hr", "hcm": "sap hcm",
            "bw": "sap bw", "grc": "sap grc", "mdg": "sap mdg",
            "ariba": "sap ariba", "concur": "sap concur",
            "fiori": "sap fiori",
        }
        for abbrev, full_skill in _SAP_MODULE_ABBREVS.items():
            if full_skill not in found_skills and re.search(r'\b' + re.escape(abbrev) + r'\b', text_lower):
                found_skills.add(full_skill)

    profile["core_skills"] = sorted(found_skills)

    # --- Extract years of experience ---
    raw_lower = raw.lower()
    year_month = re.findall(r"(\d+)\s*years?\s*(\d+)\s*months?", raw_lower)
    if not year_month:
        year_month = re.findall(r"(\d+)year\s*(\d+)months?", raw_lower)
    if year_month:
        profile["years_experience"] = max(int(y) + round(int(m) / 12) for y, m in year_month)
    else:
        exp_matches = re.findall(r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+of\s+experience|\s+exp|\s+owning|\s+in|\s+working|\s+of)?", raw_lower)
        exp_matches = [int(e) for e in exp_matches if 3 <= int(e) <= 45]
        if exp_matches:
            profile["years_experience"] = max(exp_matches)
        else:
            dates = re.findall(r"\b(?:19|20)\d{2}\b", raw)
            if dates:
                dates = sorted(int(d) for d in dates)
                span = max(dates) - min(dates) + 1
                profile["years_experience"] = max(span, 1)

    # --- Validate required fields ---
    missing = []
    if not profile.get("current_role"):
        missing.append("current_role")
    if not profile.get("years_experience") or profile["years_experience"] < 1:
        missing.append("years_experience")
    if not profile.get("core_skills") or len(profile["core_skills"]) < 3:
        missing.append("core_skills")

    print(f"  Parsed resume: {profile['name']}, "
          f"role={profile['current_role'] or 'MISSING'}, "
          f"{profile['years_experience'] or 'MISSING'}yr, "
          f"{len(profile['core_skills'])} skills")
    return profile, missing


# ---------------------------------------------------------------------------
# 6. JOB TRACKER - persistent status tracking + email rejection detection
# ---------------------------------------------------------------------------

TRACKER_FILE = "job_tracker.json"

class JobTracker:
    """Tracks job application status to avoid re-recommending applied/rejected jobs."""

    def __init__(self, path=TRACKER_FILE):
        self.path = path
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"jobs": {}}

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def job_key(self, title, company):
        return f"{company.lower()}|{title.lower()}"

    def is_known(self, title, company):
        key = self.job_key(title, company)
        entry = self.data["jobs"].get(key)
        return entry and entry.get("status") in ("applied", "rejected", "offer")

    def get_status(self, title, company):
        key = self.job_key(title, company)
        entry = self.data["jobs"].get(key, {})
        return entry.get("status", "new")

    def get_tracker_info(self, title, company):
        """Return (status, date_updated) if this exact (title, company) is tracked, else (None, None)."""
        key = self.job_key(title, company)
        entry = self.data["jobs"].get(key)
        if entry and entry.get("status") in ("applied", "rejected", "offer"):
            return entry["status"], entry.get("date_updated", "") or entry.get("date_found", "")
        return None, None

    def get_company_status(self, company, within_months=6):
        """Check if company has any applied/rejected/offer entry within the given months.
        Returns (status, title, date) of the most recent entry, or (None, None, None)."""
        best_status, best_title, best_date = None, None, None
        now = datetime.now()
        for entry in self.data["jobs"].values():
            if entry.get("company", "").lower() != company.lower():
                continue
            status = entry.get("status", "")
            if status not in ("applied", "rejected", "offer"):
                continue
            date_str = entry.get("date_updated", "") or entry.get("date_found", "")
            if date_str:
                try:
                    d = datetime.fromisoformat(date_str)
                    if (now - d).days <= within_months * 30:
                        if best_date is None or d > datetime.fromisoformat(best_date):
                            best_status, best_title, best_date = status, entry.get("title", ""), date_str
                except ValueError:
                    continue
        return best_status, best_title, best_date

    def add_job(self, title, company, url="", score=0, status="new", resume=""):
        key = self.job_key(title, company)
        if key not in self.data["jobs"]:
            self.data["jobs"][key] = {
                "title": title, "company": company, "url": url,
                "score": score, "status": status, "resume": resume,
                "date_found": datetime.now().isoformat(),
                "date_updated": datetime.now().isoformat(),
            }
            self._save()
        elif resume and not self.data["jobs"][key].get("resume"):
            self.data["jobs"][key]["resume"] = resume
            self._save()

    def update_status(self, title, company, status, notes=""):
        key = self.job_key(title, company)
        if key in self.data["jobs"]:
            self.data["jobs"][key]["status"] = status
            self.data["jobs"][key]["date_updated"] = datetime.now().isoformat()
            if notes:
                self.data["jobs"][key]["notes"] = notes
            self._save()
            return True
        return False

    def scan_email_for_rejections(self, gmail_user, gmail_pass, days_back=7):
        """
        Scan Gmail inbox for rejection emails and update tracker status.
        Returns list of newly detected rejections.
        Timeout after 30s to avoid hanging the scan.
        """
        def _run():
            result_list = []
            try:
                mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=15)
                mail.login(gmail_user, gmail_pass)
                mail.select("inbox")

                from datetime import timedelta
                since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
                search_criteria = f'(SINCE {since_date})'

                rejection_keywords = [
                    "unfortunately", "not moving forward", "position has been filled",
                    "regret to inform", "not selected", "decided to move forward with other candidates",
                    "we will not be moving forward", "application status", "update on your application",
                    "your application at", "thank you for your interest",
                ]

                result, data = mail.search(None, search_criteria)
                if result != "OK":
                    return result_list

                for num in data[0].split():
                    try:
                        result, msg_data = mail.fetch(num, "(RFC822)")
                        if result != "OK":
                            continue
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        subject = msg["subject"] or ""
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True) or b""
                                    body = body.decode("utf-8", errors="ignore")
                                    break
                        else:
                            body = msg.get_payload(decode=True) or b""
                            body = body.decode("utf-8", errors="ignore")

                        full_text = (subject + " " + body).lower()
                        is_rejection = any(kw in full_text for kw in rejection_keywords)

                        if is_rejection:
                            for key, entry in self.data["jobs"].items():
                                if entry.get("status") != "applied":
                                    continue
                                company = entry["company"].lower()
                                if company in full_text and len(company) > 3:
                                    self.update_status(entry["title"], entry["company"], "rejected",
                                                       notes=f"Auto-detected from email: {subject[:80]}")
                                    result_list.append((entry["title"], entry["company"], subject))
                                    break
                    except Exception:
                        continue

                mail.logout()
            except Exception:
                pass
            return result_list

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run)
            try:
                return fut.result(timeout=60)
            except Exception:
                print("  [tracker] Email scan timed out (60s)")
                return []

    def load_from_gsheet(self):
        """Load tracked jobs from Google Sheets 'All Jobs' tab.
        Falls back to local file if sheets unavailable."""
        gsheet_id = os.environ.get("GSHEET_ID")
        gsheet_sa_path = os.environ.get("GSHEET_SERVICE_ACCOUNT") or "gsheet_service_account.json"
        if not gsheet_id or not os.path.exists(gsheet_sa_path):
            return False
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = service_account.Credentials.from_service_account_file(gsheet_sa_path, scopes=SCOPES)
            service = build("sheets", "v4", credentials=creds)
            sheet = service.spreadsheets()

            spreadsheet = sheet.get(spreadsheetId=gsheet_id).execute()
            existing_tabs = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

            all_tab = None
            for t in existing_tabs:
                if t.lower().startswith("all jobs"):
                    all_tab = t
                    break
            if not all_tab:
                return False

            result = sheet.values().get(spreadsheetId=gsheet_id, range=f"'{all_tab}'!A:H").execute()
            rows = result.get("values", [])
            if not rows or len(rows) < 2:
                return False

            count = 0
            for row in rows[1:]:
                if len(row) < 3:
                    continue
                title = row[1].strip()
                company = row[2].strip()
                status = row[6].strip().lower() if len(row) > 6 else "new"
                url = row[4].strip() if len(row) > 4 else ""
                score = int(row[0]) if len(row) > 0 and row[0].strip().isdigit() else 0
                date_found = row[7].strip() if len(row) > 7 else ""

                if not title or not company:
                    continue
                if status not in ("new", "applied", "rejected", "offer"):
                    status = "new"

                key = self.job_key(title, company)
                self.data["jobs"][key] = {
                    "title": title,
                    "company": company,
                    "url": url,
                    "score": score,
                    "status": status,
                    "resume": "",
                    "date_found": date_found,
                    "date_updated": datetime.now().isoformat(),
                }
                count += 1

            print(f"  [gsheet] Loaded {count} tracked jobs from '{all_tab}'")
            self._save()
            return True
        except Exception as e:
            print(f"  [gsheet] Load error (starting fresh): {e}")
            return False


def search_remotive(query, location="Remote", max_results=500):
    """Search Remotive public API for remote jobs."""
    jobs = []
    try:
        resp = requests.get("https://remotive.com/api/remote-jobs", params={"search": query, "limit": max_results}, timeout=15)
        if resp.status_code == 200:
            for job in resp.json().get("jobs", []):
                jobs.append({
                    "title": job.get("title", ""), "company": job.get("company_name", ""),
                    "location": job.get("candidate_required_location", "Remote"),
                    "url": job.get("url", ""),
                    "description": f"Remotive: {job.get('title', '')} @ {job.get('company_name', '')}",
                    "posted_at": job.get("publication_date") or None,
                })
            if jobs: print(f"  [remotive] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [remotive] Error: {e}")
    return jobs





def search_foundit(query, location="India", max_results=500):
    """Search Foundit (Monster India) for jobs (paginated)."""
    jobs = []
    q = query.replace(" ", "+")
    page_size = 25
    max_pages = min(3, (max_results + page_size - 1) // page_size)
    try:
        for page_num in range(max_pages):
            start = page_num * page_size
            resp = requests.get(f"https://www.foundit.in/sapi/search?query={q}&locations={location}&limit={page_size}&start={start}",
                                headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if resp.status_code != 200:
                break
            titles = re.findall(r'"title":"([^"]+)"', resp.text)
            companies = re.findall(r'"company":"([^"]+)"', resp.text)
            locs = re.findall(r'"location":"([^"]+)"', resp.text)
            urls = re.findall(r'"(?:url|applyUrl|jobUrl|jdUrl)":"([^"]+)"', resp.text)
            if not titles:
                break  # No more results
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                raw_url = urls[i] if i < len(urls) else ""
                if raw_url and not raw_url.startswith("http"):
                    raw_url = "https://www.foundit.in" + raw_url
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "Unknown",
                    "location": locs[i] if i < len(locs) else location,
                    "url": raw_url, "description": f"Foundit: {titles[i]}",
                })
            if len(jobs) >= max_results or len(titles) < page_size:
                break
            time.sleep(1)
        if jobs: print(f"  [foundit] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [foundit] Error: {e}")
    return jobs


def search_timesjobs(query, location="India", max_results=500):
    """Search TimesJobs for jobs (paginated)."""
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            url = f"https://www.timesjobs.com/jobfunction/json/mjobs?q={q}&location={location}&sequence={page_num}"
            resp = requests.get(url, verify=False,
                                headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if resp.status_code != 200:
                break
            data = resp.json()
            items = data.get("jobList", data.get("jobs", data.get("data", [])))
            if isinstance(items, dict): items = list(items.values())
            if not items:
                break
            for item in items if isinstance(items, list) else []:
                if len(jobs) >= max_results:
                    break
                t = item.get("jobTitle", item.get("title", "")) if isinstance(item, dict) else str(item)
                c = item.get("companyName", item.get("company", "")) if isinstance(item, dict) else ""
                raw_url = item.get("jdUrl", item.get("jobUrl", item.get("url", ""))) if isinstance(item, dict) else ""
                if raw_url and not raw_url.startswith("http"):
                    raw_url = "https://www.timesjobs.com" + raw_url
                if t: jobs.append({"title": t, "company": c, "location": location, "url": raw_url, "description": t})
            if len(jobs) >= max_results:
                break
            time.sleep(1)
        if jobs: print(f"  [timesjobs] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [timesjobs] Error: {e}")
    return jobs


def search_arcdev(query, location="Remote", max_results=500):
    """Search Arc.dev for remote developer jobs using Playwright (JS-rendered)."""
    jobs = []
    q = query.replace(" ", "-")
    url = f"https://arc.dev/remote-jobs/{q}"
    try:
        html = _playwright_load_more(url, max_clicks=3, wait_ms=2500)
        if not html:
            print(f"  [arcdev] No response from Playwright")
            return jobs
        # Extract job titles and links from rendered HTML
        titles = re.findall(r'class="[^"]*job[^"]*title[^"]*"[^>]*>\s*([^<]+)', html)
        if not titles:
            titles = re.findall(r'<h[234][^>]*>\s*<a[^>]*>\s*([^<]{10,80})', html)
        links = re.findall(r'href="(https?://[^"]*(?:arc\.dev|weworkremotely|remoteok)[^"]*job[^"]*)"', html)
        if not links:
            links = re.findall(r'href="([^"]+)"[^>]*>[^<]*(?:engineer|developer|architect|manager)[^<]*<', html, re.IGNORECASE)
        # Also try generic job card extraction
        if not titles:
            titles = re.findall(r'>([^<]*(?:Engineer|Developer|Architect|Manager|Designer|Lead|Senior|Staff|Principal)[^<]*)<', html)
        seen = set()
        for i in range(len(titles)):
            if len(jobs) >= max_results:
                break
            t = titles[i].strip()
            if t in seen or len(t) < 5:
                continue
            seen.add(t)
            link = links[i] if i < len(links) else url
            jobs.append({
                "title": t, "company": "Arc.dev",
                "location": "Remote", "url": link,
                "description": f"Arc.dev: {t}",
            })
        if jobs: print(f"  [arcdev] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [arcdev] Error: {e}")
    return jobs


def search_seek(query, location="Australia", max_results=500):
    """Search Seek (AU/NZ) for jobs using Playwright (paginated)."""
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://www.seek.com.au/{q}-jobs?page={page_num}" if page_num > 1 else f"https://www.seek.com.au/{q}-jobs"
            titles = _playwright_scrape(
                page_url,
                "a[data-automation='jobTitle'], article h3, [data-testid='job-card-title']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 3).slice(0, 25)"
            )
            if not titles:
                break
            companies = _playwright_scrape(
                page_url,
                "[data-automation='jobCompany'], [data-testid='job-card-company']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)"
            )
            links = _playwright_scrape(
                page_url,
                "a[data-automation='jobTitle']",
                "els => els.map(e => e.href).filter(h => h.includes('/job/'))"
            )
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "Seek",
                    "location": location, "url": links[i] if i < len(links) else "",
                    "description": f"Seek AU: {titles[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs: print(f"  [seek] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [seek] Error: {e}")
    return jobs


def search_jora(query, location="Australia", max_results=500):
    """Search Jora (AU/NZ) for jobs using Playwright (paginated)."""
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://au.jora.com/j?q={q}&l=Australia&page={page_num}" if page_num > 1 else f"https://au.jora.com/j?q={q}&l=Australia"
            titles = _playwright_scrape(
                page_url,
                "a[class*='title'], [data-test='job-title'], h2 a, a[class*='job-link']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 5).slice(0, 25)"
            )
            if not titles:
                break
            companies = _playwright_scrape(
                page_url,
                "[data-test='company-name'], .company-name, span[class*='company']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)"
            )
            links = _playwright_scrape(
                page_url,
                "a[class*='title'], [data-test='job-title'], h2 a, a[class*='job-link']",
                "els => els.map(e => e.href).filter(h => h && h.startsWith('http')).slice(0, 25)"
            )
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                link = links[i] if i < len(links) else ""
                if link and not link.startswith("http"):
                    link = "https://au.jora.com" + link
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "Jora",
                    "location": location, "url": link, "description": f"Jora AU: {titles[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs: print(f"  [jora] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [jora] Error: {e}")
    return jobs


def search_xing(query, location="Germany", max_results=500):
    """Search Xing (Europe) for jobs using Playwright (paginated)."""
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://www.xing.com/jobs/search?keywords={q}&page={page_num}" if page_num > 1 else f"https://www.xing.com/jobs/search?keywords={q}"
            titles = _playwright_scrape(
                page_url,
                "a[href*='/jobs/'] > span, a[class*='job-title'], [data-qa='jobTitle']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 5).slice(0, 25)"
            )
            if not titles:
                break
            companies = _playwright_scrape(
                page_url,
                "span[class*='company'], [data-qa='companyName']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)"
            )
            links = _playwright_scrape(
                page_url,
                "a[href*='/jobs/']",
                "els => els.map(e => e.href).filter(h => h.includes('/jobs/'))"
            )
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "Xing",
                    "location": location, "url": links[i] if i < len(links) else "",
                    "description": f"Xing DE: {titles[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs: print(f"  [xing] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [xing] Error: {e}")
    return jobs


def search_jobsch(query, location="Switzerland", max_results=500):
    """Search Jobs.ch (Switzerland) for jobs using Playwright (paginated)."""
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://www.jobs.ch/en/search/?q={q}&page={page_num}" if page_num > 1 else f"https://www.jobs.ch/en/search/?q={q}"
            titles = _playwright_scrape(
                page_url,
                "a[class*='title'], h2 a, [data-test='job-title']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 5).slice(0, 25)"
            )
            if not titles:
                break
            companies = _playwright_scrape(
                page_url,
                "span[class*='company'], [data-test='company']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)"
            )
            links = _playwright_scrape(
                page_url,
                "a[class*='title'], h2 a, [data-test='job-title']",
                "els => els.map(e => e.href).filter(h => h && h.startsWith('http')).slice(0, 25)"
            )
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                link = links[i] if i < len(links) else ""
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "Jobs.ch",
                    "location": location, "url": link, "description": f"Jobs.ch: {titles[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs: print(f"  [jobsch] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [jobsch] Error: {e}")
    return jobs


def search_jobsingermany(query, location="Germany", max_results=500):
    """Search JobsinGermany for jobs using Playwright (paginated)."""
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://www.jobsinGermany.com/jobs?q={q}&page={page_num}" if page_num > 1 else f"https://www.jobsinGermany.com/jobs?q={q}"
            titles = _playwright_scrape(
                page_url,
                "h2 a, h3 a, a[class*='job'], [data-test='job-title']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 5).slice(0, 25)"
            )
            if not titles:
                break
            companies = _playwright_scrape(
                page_url,
                "span[class*='company'], [data-test='company']",
                "els => els.map(e => e.innerText.trim()).filter(t => t.length > 1)"
            )
            links = _playwright_scrape(
                page_url,
                "h2 a, h3 a, a[class*='job'], [data-test='job-title']",
                "els => els.map(e => e.href).filter(h => h && h.startsWith('http')).slice(0, 25)"
            )
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                link = links[i] if i < len(links) else ""
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "JobsinGermany",
                    "location": location, "url": link, "description": f"JobsinGermany: {titles[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs: print(f"  [jobsingermany] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [jobsingermany] Error: {e}")
    return jobs


def search_arbeitnow(query, location="Remote", max_results=500):
    """Search Arbeitnow API for jobs matching a query.

    The public API (www.arbeitnow.com/api/job-board-api) returns all jobs
    paginated at 100/page with no server-side search filter, so we fetch
    up to 3 pages and do client-side keyword matching.
    """
    jobs = []
    query_terms = [t.lower() for t in query.split() if len(t) > 2]
    try:
        for page in range(1, 4):  # up to 3 pages (300 jobs)
            resp = requests.get(
                f"https://www.arbeitnow.com/api/job-board-api?page={page}",
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  [arbeitnow] HTTP {resp.status_code} on page {page}")
                break
            data = resp.json()
            page_data = data.get("data", [])
            if not page_data:
                break
            for posting in page_data:
                if not isinstance(posting, dict):
                    continue
                title = posting.get("title", "")
                title_lower = title.lower()
                # Client-side filter: at least one query term must appear in the title
                if not any(term in title_lower for term in query_terms):
                    continue
                created = posting.get("created_at")
                posted_at = None
                if created:
                    try:
                        from datetime import datetime
                        posted_at = datetime.fromtimestamp(int(created)).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                jobs.append({
                    "title": title,
                    "company": posting.get("company_name", ""),
                    "location": posting.get("location", location),
                    "url": posting.get("url", ""),
                    "description": f"Arbeitnow: {title} @ {posting.get('company_name', '')}",
                    "posted_at": posted_at,
                })
                if len(jobs) >= max_results:
                    break
            if len(jobs) >= max_results:
                break
        if jobs:
            print(f"  [arbeitnow] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [arbeitnow] Error: {e}")
    return jobs


def search_visasponsor(query, location="Remote", max_results=500):
    """Search VisaSponsor.Jobs for visa-sponsored jobs using Playwright with Load More / scroll."""
    jobs = []
    classifications = "Engineering&classification=Financial-Services&classification=Information-Technology&classification=Management-and-Strategy&classification=Manufacturing-and-Logistics"
    url = f"https://visasponsor.jobs/api/jobs?classification={classifications}&showMoreOptions=false"
    try:
        # Use Load More / infinite scroll to get more results
        html = _playwright_load_more(url, max_clicks=5, wait_ms=2000)
        if not html:
            print(f"  [visasponsor] No response for '{query}'")
            return jobs
        # Each job is an <a href="/api/jobs/..."> wrapping a card
        cards = re.findall(
            r'<a[^>]*href="(/api/jobs/[^"]+)"[^>]*>.*?'
            r'class="fs-5[^"]*"[^>]*>([^<]+).*?'
            r'employer-name[^>]*>([^<]+).*?'
            r'col-11[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        for link, title, company, loc_html in cards[:max_results]:
            loc = re.sub(r'<[^>]+>', '', loc_html).strip()
            jobs.append({
                "title": title.strip(),
                "company": company.strip(),
                "location": loc if loc else location,
                "url": "https://visasponsor.jobs" + link,
                "description": f"Visa-sponsored: {title.strip()} at {company.strip()}",
            })
        if jobs:
            print(f"  [visasponsor] {len(jobs)} jobs")
    except Exception as e:
        print(f"  [visasponsor] Error: {e}")
    return jobs


def search_incluso(query, location="Remote", max_results=500):
    """Search Incluso (Teamtailor) jobs via JSON Feed (paginated)."""
    jobs = []
    query_lower = query.lower()
    query_terms = query_lower.split()
    max_pages = 5
    try:
        for page_num in range(1, max_pages + 1):
            api_url = f"https://openings.incluso.se/jobs.json?page={page_num}" if page_num > 1 else "https://openings.incluso.se/jobs.json"
            resp = requests.get(
                api_url,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                break
            items = resp.json().get("items", [])
            if not items:
                break
            for item in items:
                if len(jobs) >= max_results:
                    break
                title = item.get("title", "").strip()
                if not title:
                    continue
                # Client-side keyword filter
                if not all(term in title.lower() for term in query_terms):
                    continue
                jp = item.get("_jobposting", {})
                company = "Incluso"
                if jp:
                    org = jp.get("hiringOrganization", {})
                    if org.get("name"):
                        company = org["name"]
                    locs = jp.get("jobLocation", [])
                    loc = ", ".join(
                        l.get("address", {}).get("addressLocality", "")
                        for l in locs if l.get("address", {}).get("addressLocality")
                    ) if locs else location
                else:
                    loc = location
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": item.get("url", ""),
                    "description": f"Incluso: {title}",
                })
            if len(jobs) >= max_results or len(items) < 20:
                break
            time.sleep(1)
        if jobs:
            print(f"  [incluso] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [incluso] Error: {e}")
    return jobs


def search_workinfinland(query, location="Finland", max_results=500):
    """Search Work in Finland for jobs using Playwright (Next.js, paginated)."""
    jobs = []
    cats = "ict%2Csoftware-development%2Cengineering"
    from urllib.parse import quote
    q = quote(query.strip())
    max_pages = 5
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        for pg in range(1, max_pages + 1):
            page_url = f"https://www.workinfinland.com/en/open-jobs/?category={cats}&query={q}&page={pg}"
            page.goto(page_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            try:
                btn = page.query_selector('button:has-text("Allow all")')
                if btn:
                    btn.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass
            cards = page.query_selector_all("a.job-card")
            if not cards:
                break
            for card in cards:
                if len(jobs) >= max_results:
                    break
                try:
                    title_el = card.query_selector(".job-card__title")
                    company_el = card.query_selector(".job-card__employerName")
                    loc_el = card.query_selector(".job-card--footer--left-item")
                    title = title_el.inner_text().strip() if title_el else ""
                    company = company_el.inner_text().strip() if company_el else ""
                    loc_text = loc_el.inner_text().strip() if loc_el else location
                    href = card.get_attribute("href") or ""
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": loc_text,
                        "url": href if href.startswith("http") else f"https://www.workinfinland.com{href}",
                        "description": f"Work in Finland: {title} at {company}",
                    })
                except Exception:
                    continue
            if len(jobs) >= max_results:
                break
            page.wait_for_timeout(2000)
        context.close()
        if jobs:
            print(f"  [workinfinland] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [workinfinland] Error: {e}")
    return jobs


def search_eures(query, location="Europe", max_results=500):
    """Search EURES via their Angular app API (requires Playwright session)."""
    jobs = []
    query_lower = query.lower()
    query_terms = query_lower.split()
    country_codes = ["at", "be", "ch", "de", "dk", "lu", "nl", "pl", "se"]
    max_pages = 3
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        base_url = "https://europa.eu/eures/portal/jv-se/search?lang=en"
        page.goto(base_url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        for pg in range(1, max_pages + 1):
            results = page.evaluate('''(args) => fetch('https://europa.eu/eures/api/jv-searchengine/public/jv-search/search', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify({
                    resultsPerPage: 50,
                    page: args.pg,
                    sortSearch: 'BEST_MATCH',
                    keywords: [],
                    publicationPeriod: null,
                    occupationUris: [],
                    skillUris: [],
                    requiredExperienceCodes: [],
                    positionScheduleCodes: ['fulltime'],
                    sectorCodes: ['k', 'n'],
                    locationCodes: args.locCodes,
                    requiredLanguages: [{"isoCode": "en", "level": "C2"}],
                    requestLanguage: 'en'
                })
            }).then(r => r.json()).then(d => d.jvs || [])''', {"pg": pg, "locCodes": country_codes})
            if not results:
                break
            for item in results:
                if len(jobs) >= max_results:
                    break
                title = item.get("title", "")
                if not title:
                    continue
                desc = item.get("description", "")
                # Client-side keyword filter
                if not all(term in title.lower() or term in desc.lower() for term in query_terms):
                    continue
                employer = item.get("employer") or {}
                company = employer.get("name", "") if isinstance(employer, dict) else ""
                loc_codes = list(item.get("locationMap", {}).keys())
                loc = ", ".join(loc_codes) if loc_codes else location
                job_id = item.get("id", "")
                url = f"https://europa.eu/eures/portal/jv-se/jv-details/{job_id}" if job_id else ""
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": url,
                    "description": desc or f"EURES: {title}",
                })
            if len(jobs) >= max_results or len(results) < 50:
                break
            page.wait_for_timeout(2000)
        context.close()
        if jobs:
            print(f"  [eures] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [eures] Error: {e}")
    return jobs


# ---------------------------------------------------------------------------
# 6b. EU JOB BOARD SCRAPERS (for boards-eu batch)
# ---------------------------------------------------------------------------

def _extract_jobs_bs4(html, title_sel, company_sel=None, link_sel=None, loc_sel=None,
                      link_prefix="", base_url="", default_loc="", max_results=500):
    """Helper: parse HTML with BeautifulSoup and extract job listings."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []
    titles = soup.select(title_sel)
    companies = soup.select(company_sel) if company_sel else []
    links = soup.select(link_sel) if link_sel else []
    locs = soup.select(loc_sel) if loc_sel else []
    for i in range(min(len(titles), max_results)):
        t = titles[i].get_text().strip()
        u = ""
        if i < len(links):
            u = links[i].get("href", "")
            if u and not u.startswith("http"):
                u = base_url + u
        c = companies[i].get_text().strip() if i < len(companies) else "Unknown"
        if not c and companies:
            c = companies[i].get("alt", "") or companies[i].get("title", "") or "Unknown"
        l = locs[i].get_text().strip() if i < len(locs) else default_loc
        jobs.append({"title": t, "company": c, "location": l, "url": u, "description": t})
    return jobs


def _extract_monster_jobs(resp_text, link_prefix, base_url, default_loc, max_results):
    """Extract jobs from Monster sites (data-jobtitle pattern)."""
    import json
    jobs = []
    # Try JSON-LD first
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', resp_text, re.DOTALL | re.I):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    title = item.get("title", "")
                    company = ""
                    if item.get("hiringOrganization"):
                        company = item["hiringOrganization"].get("name", "")
                    loc = ""
                    if item.get("jobLocation") and isinstance(item["jobLocation"], dict):
                        loc = item["jobLocation"].get("address", {}).get("addressLocality", "")
                    url = item.get("url", "")
                    if title:
                        jobs.append({"title": title, "company": company, "location": loc or default_loc,
                                     "url": url or base_url, "description": title})
            if jobs:
                return jobs
        except (json.JSONDecodeError, AttributeError):
            pass
    # Fallback: data- attributes
    titles = re.findall(r'data-jobtitle[^=]*=\s*"([^"]+)"', resp_text)
    companies = re.findall(r'data-company[^=]*=\s*"([^"]+)"', resp_text)
    links = re.findall(r'href="(/[^"]+)"', resp_text)
    for i in range(min(len(titles), max_results)):
        c = companies[i] if i < len(companies) else "Unknown"
        u = links[i] if i < len(links) else ""
        if u and not u.startswith("http"):
            u = base_url + u
        jobs.append({"title": titles[i], "company": c, "location": default_loc,
                     "url": u, "description": titles[i]})
    return jobs


def _enrich_descriptions(jobs, max_workers=8):
    """Fetch full job descriptions in parallel for jobs that have URLs."""
    from bs4 import BeautifulSoup
    from concurrent.futures import ThreadPoolExecutor
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    def fetch(job):
        url = job.get("url", "")
        if not url or len(url) < 10:
            return job
        try:
            r = requests.get(url, headers=h, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    tag.decompose()
                text = soup.get_text(separator=' ', strip=True)
                text = re.sub(r'\s+', ' ', text)
                if len(text) > 100:
                    job["description"] = text[:3000]
        except Exception:
            pass
        return job
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(fetch, jobs))


def search_netempregos(query, location="Portugal", max_results=500):
    """Search Net-Empregos (Portugal) for jobs with pagination."""
    from bs4 import BeautifulSoup
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    q = query.replace(" ", "+")
    jobs = []
    seen = set()
    try:
        resp = requests.get(f"https://www.net-empregos.com/pesquisa/?q={q}", headers=h, timeout=15)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        total_count = _detect_total_count(soup)
        effective_max = min(total_count, max_results)
        page_num = 1
        max_pages = 3
        while len(jobs) < effective_max and page_num <= max_pages:
            if page_num > 1:
                pag_url = f"https://www.net-empregos.com/pesquisa-empregos.asp?page={page_num}&chaves=pesquisa"
                resp = requests.get(pag_url, headers=h, timeout=15)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.select(".media-body.align-self-center")
            if not cards:
                break
            for card in cards:
                if len(jobs) >= effective_max:
                    break
                h2 = card.find("h2")
                a = h2.find("a") if h2 else None
                title = a.get_text().strip() if a else (h2.get_text().strip() if h2 else "")
                href = a.get("href", "") if a else ""
                url = f"https://www.net-empregos.com{href}" if href else ""
                img = card.find("img", class_="net-img-logo")
                company = img.get("alt", "Unknown") if img else "Unknown"
                dedup_key = href or f"{title}|{company}"
                if title and dedup_key not in seen:
                    seen.add(dedup_key)
                    jobs.append({"title": title, "company": company, "location": "Portugal",
                                 "url": url, "description": title})
            page_num += 1
        if jobs:
            print(f"  [netempregos] {len(jobs)} jobs for '{query}'")
        return jobs
    except Exception as e:
        print(f"  [netempregos] Error: {e}")
    return []


def search_sapoemprego(query, location="Portugal", max_results=500):
    """Search SAPO Emprego (Portugal) for jobs with pagination."""
    from bs4 import BeautifulSoup
    base_url = "https://emprego.sapo.pt/offers?categoria=engenharia,informatica-tecnologias&hora=full-time&ordem=mais-recentes"
    jobs = []
    seen = set()
    try:
        html = _playwright_html(base_url, timeout=30000)
        if not html:
            return jobs
        soup = BeautifulSoup(html, 'html.parser')
        total = _detect_total_count(soup, default=500)
        total_pages = min((total // 20) + 1, 327)
        print(f"  [sapoemprego] ~{total} jobs across ~{total_pages} pages for '{query}'")

        def _parse_articles(soup):
            parsed = []
            articles = soup.find_all("article")
            for art in articles:
                if len(jobs) + len(parsed) >= max_results:
                    break
                classes = art.get("class", [])
                if "picture-card" in classes or "ad" in classes:
                    continue
                title_el = art.select_one("h3 a") or art.select_one("h3")
                if not title_el:
                    continue
                title = title_el.get_text().strip()
                company_el = art.select_one("ul.company li.name a") or art.select_one("ul.company li.name")
                company = company_el.get_text().strip() if company_el else "Unknown"
                key = (title, company)
                if key in seen:
                    continue
                seen.add(key)
                txt_all = art.get_text(" ", strip=True)
                loc = "Portugal"
                for city in ["Lisboa", "Porto", "Braga", "Coimbra", "Aveiro", "Faro",
                             "Sintra", "Cascais", "Oeiras", "Setúbal", "Évora"]:
                    if city in txt_all:
                        loc = city
                        break
                link_el = art.select_one("a[href*='/offers/']")
                url_full = link_el.get("href", "") if link_el else ""
                if title and company:
                    parsed.append({"title": title, "company": company, "location": loc,
                                   "url": url_full, "description": title})
            return parsed

        jobs.extend(_parse_articles(soup))

        for page in range(2, total_pages + 1):
            if len(jobs) >= max_results:
                break
            page_url = f"{base_url}&pagina={page}"
            html = _playwright_html(page_url, timeout=30000)
            if not html:
                continue
            soup = BeautifulSoup(html, 'html.parser')
            page_jobs = _parse_articles(soup)
            jobs.extend(page_jobs)
            if not page_jobs:
                break

        if jobs:
            print(f"  [sapoemprego] {len(jobs)} jobs for '{query}'")
        return jobs
    except Exception as e:
        print(f"  [sapoemprego] Error: {e}")
    return jobs


def search_bundesagentur(query, location="Germany", max_results=500):
    """Search Bundesagentur für Arbeit (Germany) for IT/software jobs."""
    from bs4 import BeautifulSoup
    q = query.replace(" ", "+")
    berufsfeld = "IT-Systemanalyse,%20-Anwendungsberatung%20und%20-Vertrieb;Informatik;Softwareentwicklung%20und%20Programmierung"
    base = f"https://www.arbeitsagentur.de/jobsuche/suche?berufsfeld={berufsfeld}&angebotsart=1&begriff={q}"
    jobs = []
    seen = set()
    page = 1
    max_pages = 3
    try:
        effective_max = max_results
        while len(jobs) < effective_max and page <= max_pages:
            html = _playwright_html(f"{base}&seite={page}")
            if not html:
                break
            soup = BeautifulSoup(html, 'html.parser')
            if page == 1:
                total_count = _detect_total_count(soup)
                effective_max = min(total_count, max_results)
                if total_count > max_results:
                    print(f"    (capped to {effective_max} of {total_count} available)")
            links = soup.select('a[href*="jobdetail"]')
            if not links:
                break
            for a in links:
                if len(jobs) >= max_results:
                    break
                href = a.get("href", "")
                if href in seen:
                    continue
                seen.add(href)
                full_url = href if href.startswith("http") else f"https://www.arbeitsagentur.de{href}"
                title = a.get_text().strip()
                title = re.sub(r'^\d+\.\s*Ergebnis:\s*', '', title).strip()
                if title:
                    jobs.append({"title": title, "company": "", "location": "Germany",
                                 "url": full_url, "description": title})
            page += 1
        if jobs:
            print(f"  [bundesagentur] {len(jobs)} jobs for '{query}'")
        return jobs
    except Exception as e:
        print(f"  [bundesagentur] Error: {e}")
    return []


def search_iamexpat(query, location="Netherlands", max_results=500):
    """Search IamExpat (Netherlands) for English-friendly jobs with pagination."""
    from bs4 import BeautifulSoup
    base_url = "https://www.iamexpat.nl/career/jobs-netherlands?category=it-technology,engineering&language=english"
    jobs = []
    seen = set()
    max_pages = 3
    try:
        for page_num in range(0, max_pages):
            page_url = f"{base_url}&page={page_num}" if page_num > 0 else base_url
            html = _playwright_html(page_url)
            if not html:
                break
            soup = BeautifulSoup(html, 'html.parser')
            cards = soup.select('a[class*=cardWrapper]')
            if not cards:
                break
            page_jobs = 0
            for card in cards:
                if len(jobs) >= max_results:
                    break
                title_el = card.select_one('.title-7')
                title = title_el.get_text().strip() if title_el else ""
                href = card.get("href", "")
                url_full = f"https://www.iamexpat.nl{href}" if href.startswith("/") else href
                # Extract location from SVG+text divs
                loc = "Netherlands"
                info_els = card.select('[class*=JobBoardItemCard_jobInfoElement]')
                for el in info_els:
                    txt = el.get_text().strip()
                    for city in ["Amsterdam", "Utrecht", "Rotterdam", "The Hague", "Den Haag",
                                 "Eindhoven", "Groningen", "Maastricht", "Leiden", "Delft",
                                 "Haarlem", "Arnhem", "Enschede", "Tilburg", "Breda",
                                 "Nijmegen", "Almere", "Amersfoort", "Dordrecht", "Heerenveen"]:
                        if city in txt:
                            loc = city
                            break
                # Extract date from info elements (e.g. "2 days ago", "1 week ago")
                posted_at = None
                for el in info_els:
                    txt = el.get_text().strip()
                    if re.search(r'\d+\s*(day|week|hour|month)s?\s*ago|just|today', txt, re.IGNORECASE):
                        posted_at = _parse_relative_date(txt)
                        break
                dedup_key = url_full or title
                if title and dedup_key not in seen:
                    seen.add(dedup_key)
                    jobs.append({"title": title, "company": "", "location": loc,
                                 "url": url_full, "description": title,
                                 "posted_at": posted_at})
                    page_jobs += 1
            if page_jobs == 0 or len(jobs) >= max_results:
                break
        if jobs: print(f"  [iamexpat] {len(jobs)} jobs for '{query}' ({page_num + 1} pages)")
    except Exception as e:
        print(f"  [iamexpat] Error: {e}")
    return jobs


def search_workinlux(query, location="Luxembourg", max_results=500):
    """Search Work in Luxembourg for jobs."""
    from bs4 import BeautifulSoup
    import re
    base = ("https://jobs.workinluxembourg.com/offers?"
            "e34647bc-f73a-4055-bf2c-0a4ee9c3a12b=e4b6947d-32a2-45ce-8f4d-8fedff4b559d"
            "&e34647bc-f73a-4055-bf2c-0a4ee9c3a12b=485b8c96-35f4-49ae-b321-69109eaea14d")
    jobs = []
    seen = set()
    page = 1
    max_pages = 3
    try:
        effective_max = max_results
        while len(jobs) < effective_max and page <= max_pages:
            html = _playwright_html(f"{base}&page={page}", wait_ms=5000)
            if not html:
                break
            soup = BeautifulSoup(html, 'html.parser')
            if page == 1:
                total_count = _detect_total_count(soup)
                effective_max = min(total_count, max_results)
                if total_count > max_results:
                    print(f"    (capped to {effective_max} of {total_count} available)")
            cards = soup.select('.offer-card__info')
            if not cards:
                break
            for card in cards:
                if len(jobs) >= max_results:
                    break
                company_el = card.select_one('.offer-card-info__header .text, .offer-card-info__header')
                title_el = card.select_one('.offer-card-info__body')
                company = company_el.get_text().strip() if company_el else "Unknown"
                title = title_el.get_text().strip() if title_el else ""
                wrapper = card.find_parent('a')
                href = wrapper.get("href", "") if wrapper else ""
                url_full = f"https://jobs.workinluxembourg.com{href}" if href.startswith("/") else href
                dedup_key = f"{company}|{title}"
                if title and dedup_key not in seen:
                    seen.add(dedup_key)
                    jobs.append({"title": title, "company": company, "location": "Luxembourg",
                                 "url": url_full, "description": title})
            page += 1
        if jobs:
            print(f"  [workinlux] {len(jobs)} jobs for '{query}'")
        return jobs
    except Exception as e:
        print(f"  [workinlux] Error: {e}")
    return []


def search_togetherabroad(query, location="Netherlands", max_results=500):
    """Search Together Abroad (Netherlands job board) for jobs.

    Uses the IT category page with server-side pagination (/p/{n}/...).
    """
    from bs4 import BeautifulSoup
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
    jobs = []
    seen = set()
    page = 1
    try:
        while len(jobs) < max_results:
            if page == 1:
                url = "https://www.togetherabroad.nl/information-technology-jobs-netherlands.html"
            else:
                url = f"https://www.togetherabroad.nl/p/{page}/information-technology-jobs-netherlands"
            resp = requests.get(url, headers=h, timeout=15)
            if resp.status_code != 200:
                break
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.select('h3.itemTitle.actItemTitle a')
            if not items:
                break
            for a in items:
                if len(jobs) >= max_results:
                    break
                text = a.get_text().strip()
                if not text:
                    continue
                parts = [p.strip() for p in text.split(" - ")]
                if len(parts) < 3:
                    continue
                title = " - ".join(parts[:-2])
                location = parts[-2]
                company = parts[-1]
                href = a.get("href", "")
                dedup_key = f"{company}|{title}"
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    jobs.append({"title": title, "company": company,
                                 "location": location, "url": href,
                                 "description": title})
            # Check for next page
            next_link = soup.select_one('a.pnNext')
            if not next_link:
                break
            page += 1
        if jobs:
            print(f"  [togetherabroad] {len(jobs)} jobs for '{query}'")
        return jobs
    except Exception as e:
        print(f"  [togetherabroad] Error: {e}")
    return []


_himalayas_cache = None
_himalayas_cache_time = 0

def search_himalayas(query, location="Remote", max_results=500):
    """Search Himalayas remote jobs using public JSON API."""
    global _himalayas_cache, _himalayas_cache_time
    jobs = []
    term = query.lower()
    try:
        now = time.time()
        if now - _himalayas_cache_time > 300:
            resp = requests.get(
                "https://himalayas.app/jobs/api",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            _himalayas_cache = data.get("jobs", [])
            _himalayas_cache_time = now
        for item in _himalayas_cache:
            title = (item.get("title") or "").strip()
            company = (item.get("companyName") or "Unknown").strip()
            guid = (item.get("guid") or "").strip()
            url = guid if guid.startswith("http") else f"https://himalayas.app/jobs/{guid}" if guid else ""
            categories = [c.lower() for c in (item.get("categories") or [])]
            desc = (item.get("description") or "").lower()
            if not title or not url:
                continue
            if term != "remote" and term not in title.lower() and term not in desc and not any(term in c for c in categories):
                continue
            salary_parts = []
            if item.get("minSalary"):
                salary_parts.append(f"${int(item['minSalary']):,}")
            if item.get("maxSalary"):
                salary_parts.append(f"${int(item['maxSalary']):,}")
            currency = item.get("currency") or ""
            salary_str = f" ({' '.join(salary_parts)} {currency})" if salary_parts else ""
            seniority = ", ".join(item.get("seniority") or [])
            locs = ", ".join(item.get("locationRestrictions") or ["Remote"])
            et = item.get("employmentType") or ""
            jt = "Contract" if any(k in (et or "").lower() for k in ["contract", "freelance", "temporary"]) else "Full-Time" if et else ""
            jobs.append({
                "title": title,
                "company": company,
                "location": locs,
                "url": url,
                "job_type": jt,
                "description": f"Himalayas: {title} at {company}{salary_str}. Seniority: {seniority}",
            })
            if len(jobs) >= max_results:
                break
        if jobs:
            print(f"  [himalayas] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [himalayas] Error: {e}")
    return jobs


def search_infojobs(query, location="Spain", max_results=500):
    """Search InfoJobs (Spain) for jobs with pagination."""
    from bs4 import BeautifulSoup
    q = query.replace(" ", "+")
    jobs = []
    seen = set()
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            url = f"https://www.infojobs.net/jobsearch/search-results/list?query={q}&page={page_num}"
            html = _playwright_html(url)
            if not html or len(html) < 2000:
                break
            soup = BeautifulSoup(html, 'html.parser')
            # Look for job cards with h2 or specific classes
            links = soup.select('a[href*="of_oferta-empleo"]')
            if not links:
                links = soup.select('h2 a')
            if not links:
                break
            page_jobs = 0
            for a in links:
                if len(jobs) >= max_results:
                    break
                title = a.get_text().strip()
                href = a.get("href", "")
                url_full = href if href.startswith("http") else f"https://www.infojobs.net{href}"
                # Find company in parent card
                parent = a.find_parent(['div', 'article', 'li'])
                company = "Unknown"
                if parent:
                    for c in parent.select('[class*="company"], [class*="empresa"], [class*="corporation"]'):
                        txt = c.get_text().strip()
                        if txt:
                            company = txt
                            break
                dedup_key = url_full or title
                if title and dedup_key not in seen:
                    seen.add(dedup_key)
                    jobs.append({"title": title, "company": company, "location": "Spain",
                                 "url": url_full, "description": title})
                    page_jobs += 1
            if page_jobs == 0 or len(jobs) >= max_results:
                break
        if jobs: print(f"  [infojobs] {len(jobs)} jobs for '{query}' ({page_num} pages)")
    except Exception as e:
        print(f"  [infojobs] Error: {e}")
    return jobs


def search_monsterlu(query, location="Luxembourg", max_results=500):
    """Search Monster.lu for jobs (paginated, max 3 pages)."""
    import time
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    q = query.replace(" ", "+")
    jobs = []
    seen = set()
    max_pages = 3
    try:
        for page in range(1, max_pages + 1):
            url = f"https://www.monster.lu/jobs/search/?q={q}&page={page}"
            resp = requests.get(url, headers=h, timeout=15)
            if resp.status_code != 200:
                break
            page_jobs = _extract_monster_jobs(resp.text, "/job/", "https://www.monster.lu", "Luxembourg", max_results)
            if not page_jobs:
                break
            new_count = 0
            for j in page_jobs:
                dedup_key = j.get("url") or f"{j['title']}|{j['company']}"
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    jobs.append(j)
                    new_count += 1
            if new_count == 0 or len(jobs) >= max_results:
                break
            if page < max_pages:
                time.sleep(0.5)
        if jobs:
            print(f"  [monsterlu] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [monsterlu] Error: {e}")
    return jobs


def search_monsterboardnl(query, location="Netherlands", max_results=500):
    """Search Monsterboard.nl for jobs (paginated, max 3 pages)."""
    import time
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    q = query.replace(" ", "+")
    jobs = []
    seen = set()
    max_pages = 3
    try:
        for page in range(1, max_pages + 1):
            url = f"https://www.monsterboard.nl/vacatures/zoeken/?q={q}&page={page}"
            resp = requests.get(url, headers=h, timeout=15)
            if resp.status_code != 200:
                break
            page_jobs = _extract_monster_jobs(resp.text, "/vacatures/", "https://www.monsterboard.nl", "Netherlands", max_results)
            if not page_jobs:
                break
            new_count = 0
            for j in page_jobs:
                dedup_key = j.get("url") or f"{j['title']}|{j['company']}"
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    jobs.append(j)
                    new_count += 1
            if new_count == 0 or len(jobs) >= max_results:
                break
            if page < max_pages:
                time.sleep(0.5)
        if jobs:
            print(f"  [monsterboardnl] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [monsterboardnl] Error: {e}")
    return jobs


def search_infoempleo(query, location="Spain", max_results=500):
    """Search Infoempleo (Spain) for jobs — uses tech + eng filtered URLs with pagination."""
    from bs4 import BeautifulSoup
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    jobs = []
    base_urls = [
        "https://www.infoempleo.com/trabajo/area-de-empresa_tecnologia-e-informatica",
        "https://www.infoempleo.com/trabajo/area-de-empresa_ingenieria-y-produccion",
    ]
    seen = set()
    for base in base_urls:
        page = 1
        try:
            while len(jobs) < max_results:
                url = f"{base}/{page}/?ordenacion=fechaAlta" if page > 1 else f"{base}/?ordenacion=fechaAlta"
                resp = requests.get(url, headers=h, timeout=15)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.select("li.offerblock")
                if not cards:
                    break
                import time
                if page > 1:
                    time.sleep(0.5)
                for card in cards:
                    if len(jobs) >= max_results:
                        break
                    a = card.select_one("h2.title a")
                    title = a.get_text().strip() if a else ""
                    href = a.get("href", "") if a else ""
                    url_full = f"https://www.infoempleo.com{href}" if href.startswith("/") else href
                    company_el = card.select_one(".logoplusname span.extra-data")
                    company = company_el.get_text().strip() if company_el else "Unknown"
                    loc_el = card.select_one("p.extra-data")
                    loc = "Spain"
                    if loc_el:
                        txt = loc_el.get_text().strip()
                        for city in ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao",
                                     "Málaga", "Zaragoza", "Alicante", "Murcia", "Palma",
                                     "Granada", "Vigo", "Gijón", "Pamplona", "San Sebastián",
                                     "Valladolid", "Toledo", "Badajoz", "Logroño", "Huelva"]:
                            if city in txt:
                                loc = city
                                break
                    if title and href not in seen:
                        seen.add(href)
                        jobs.append({"title": title, "company": company, "location": loc,
                                     "url": url_full, "description": title})
                page += 1
        except Exception as e:
            print(f"  [infoempleo] Error on {base}: {e}")
    if jobs:
        print(f"  [infoempleo] {len(jobs)} jobs for '{query}'")
    return jobs[:max_results]


def search_crossover(query, location="Remote", max_results=500):
    """Search Crossover.com for jobs — JS-rendered page with card elements."""
    from bs4 import BeautifulSoup
    url = f"https://www.crossover.com/jobs?Search={query}&Location=Any%20Country"
    jobs = []
    seen = set()
    try:
        html = _playwright_html(url, wait_ms=8000)
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            cards = soup.select('[class*=card]')
            for card in cards:
                if len(jobs) >= max_results:
                    break
                title_el = card.select_one('h1, h2, h3, h4, strong')
                title = title_el.get_text().strip() if title_el else ""
                if not title:
                    continue
                if title not in seen:
                    seen.add(title)
                    link_el = card.select_one('a[href]')
                    card_url = ""
                    if link_el:
                        href = link_el.get("href", "")
                        if href.startswith("/"):
                            card_url = "https://www.crossover.com" + href
                        elif href.startswith("http"):
                            card_url = href
                    jobs.append({"title": title, "company": "Crossover",
                                 "location": "Remote", "url": card_url,
                                 "description": title})
            if jobs:
                print(f"  [crossover] {len(jobs)} jobs for '{query}'")
            return jobs
    except Exception as e:
        print(f"  [crossover] Error: {e}")
    return []


def search_nodesk(query, location="Remote", max_results=500):
    """Search NoDesk (remote jobs board) for jobs."""
    from bs4 import BeautifulSoup
    url = "https://nodesk.co/remote-jobs/engineering/"
    jobs = []
    seen = set()
    try:
        html = _playwright_html(url, wait_ms=6000)
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            main = soup.find('main')
            if main:
                for a in main.find_all('a', href=True):
                    href = a.get('href', '')
                    if '/remote-jobs/' in href and href != '/remote-jobs/' \
                            and not href.startswith('/remote-jobs/new/'):
                        title = a.get_text().strip()
                        if len(title) > 10 and href not in seen:
                            seen.add(href)
                            path = href.split('/remote-jobs/')[-1].strip('/')
                            company = path.split('-')[0].title() if '-' in path else "Unknown"
                            url_full = f"https://nodesk.co{href}" if href.startswith('/') else href
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": location,
                                "url": url_full,
                                "description": title
                            })
            if jobs:
                print(f"  [nodesk] {len(jobs)} jobs for '{query}'")
            return jobs[:max_results]
    except Exception as e:
        print(f"  [nodesk] Error: {e}")
    return []


def search_kelly(query, location="Remote", max_results=500):
    """Search KellyOCG careers via Playwright + BeautifulSoup with pagination."""
    from bs4 import BeautifulSoup
    import re
    jobs = []
    seen = set()
    page = 1
    try:
        while len(jobs) < max_results:
            url = "https://careers.kellyocg.com/search" if page == 1 else f"https://careers.kellyocg.com/search?PageID={page}"
            html = _playwright_html(url, wait_ms=8000)
            if not html:
                break
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.select('a[href*="/job/"]')
            if not links:
                break
            for a in links:
                if len(jobs) >= max_results:
                    break
                href = a.get("href", "")
                if href in seen:
                    continue
                seen.add(href)
                title = a.get_text().strip()
                if not title:
                    continue
                url_full = f"https://careers.kellyocg.com{href}" if href.startswith("/") else href
                # Extract location from title
                loc = location
                if "Remote" in title:
                    loc = "Remote"
                elif "|" in title:
                    for part in title.split("|"):
                        m = re.search(r'([A-Za-z].*?,\s*[A-Z]{2})', part)
                        if m:
                            loc = m.group(1).strip()
                            break
                jobs.append({"title": title, "company": "Kelly", "location": loc,
                             "url": url_full, "description": title})
            if not soup.select_one('a.page-link-next, a.JQPagingLinkNext'):
                break
            page += 1
        if jobs:
            print(f"  [kelly] {len(jobs)} jobs for '{query}'")
        return jobs[:max_results]
    except Exception as e:
        print(f"  [kelly] Error: {e}")
        return []


def search_workew(query, location="Remote", max_results=500):
    """Search Workew.com for remote jobs using Playwright (paginated, max 3 pages)."""
    from bs4 import BeautifulSoup
    q = query.replace(" ", "+")
    base_url = f"https://workew.com/remote-jobs/?search_keywords={q}&search_region=&search_categories%5B%5D=5"
    jobs = []
    seen = set()
    max_pages = 3
    try:
        for page in range(1, max_pages + 1):
            url = base_url if page == 1 else f"{base_url}&paged={page}"
            html = _playwright_html(url, wait_ms=6000)
            if not html or len(html) <= 2000:
                break
            soup = BeautifulSoup(html, 'html.parser')
            cards = soup.select('li.w-job-card')
            if not cards:
                cards = soup.select('[class*=card]')
                cards = [c for c in cards if c.name == 'li']
            if not cards:
                break
            new_count = 0
            for card in cards:
                if len(jobs) >= max_results:
                    break
                title_el = card.select_one('h3.w-job-card__title') or card.select_one('h2')
                title = title_el.get_text().strip() if title_el else ""
                link_el = card.select_one('a.w-job-card__link')
                href = link_el.get("href", "") if link_el else ""
                if not title and link_el:
                    title = link_el.get("aria-label", "")
                img_el = card.select_one('img.w-job-card__logo img, .w-job-card__logo img')
                if not img_el:
                    img_el = card.select_one('.w-job-card__logo img')
                company = img_el.get("alt", "").strip() if img_el else ""
                if not company:
                    company_el = card.select_one('.w-job-card__company')
                    company = company_el.get_text().strip().split(" ")[0] if company_el else "Unknown"
                dedup_key = href or f"{title}|{company}"
                if title and dedup_key not in seen:
                    seen.add(dedup_key)
                    jobs.append({"title": title, "company": company, "location": "Remote",
                                 "url": href, "description": title})
                    new_count += 1
            if new_count == 0 or len(jobs) >= max_results:
                break
        if jobs:
            print(f"  [workew] {len(jobs)} jobs for '{query}'")
        return jobs
    except Exception as e:
        print(f"  [workew] Error: {e}")
    return jobs if jobs else []


# ---------------------------------------------------------------------------
# 7. MAIN
# ---------------------------------------------------------------------------

def _fetch_source_jobs(src):
    """Run in child process — each process gets its own Playwright browser."""
    try:
        jobs = fetch_jobs_from_source(src)
        return src, jobs, None
    except Exception as e:
        return src, [], str(e)


def main():
    parser = argparse.ArgumentParser(description="Daily Job Scanner")
    parser.add_argument("--name", help="Your name (overrides PROFILE)")
    parser.add_argument("--skills", help="Comma-separated core skills (overrides PROFILE)")
    parser.add_argument("--exp", type=int, help="Years of experience (overrides PROFILE)")
    parser.add_argument("--resume", help="Path to resume PDF - auto-extracts profile")
    parser.add_argument("--profile", help="Load profile from profiles/<name>.json (e.g. pradeep, kamnee)")
    parser.add_argument("--email-to", help="Email recipient (overrides .env EMAIL_TO)")
    parser.add_argument("--gmail-user", help="Gmail address (overrides .env GMAIL_ADDRESS)")
    parser.add_argument("--gmail-pass", help="Gmail App Password (overrides .env)")
    parser.add_argument("--threshold", type=int, default=65, help="Match score threshold (default: 65)")
    parser.add_argument("--source-types", default="all",
                        choices=["all", "ats", "boards", "playwright"],
                        help="Which source types to scan: ats (Greenhouse/Lever/Ashby), "
                             "boards (LinkedIn/Indeed/Naukri/etc), playwright (RemoteOK/WorkingNomads/etc), "
                             "or all (default: all)")
    parser.add_argument("--email-scan-only", action="store_true",
                        help="Only scan Gmail for rejection emails (skip job scanning)")
    parser.add_argument("--digest", action="store_true",
                        help="Also scan Gmail for Glassdoor/Indeed job digest emails")
    parser.add_argument("--digest-label", default=None,
                        help="Gmail label for digest emails (default: INBOX or GMAIL_DIGEST_LABEL env)")
    _BATCH_CHOICES = ["ats", "boards-major", "boards-AU-NZ", "boards-eu", "boards-remote", "playwright", "eu", "global", "apac", "us-canada", "middle-east", "remote"]
    parser.add_argument("--batch", type=str, default="",
                        help=f"Batch(es) to run: comma-separated ({', '.join(_BATCH_CHOICES)}) or 'all'. Examples: --batch boards-major or --batch boards-major,boards-eu")
    parser.add_argument("--preview", action="store_true",
                        help="Save email HTML to preview.html instead of sending")
    parser.add_argument("--save", default="last_scan_results.json", help="Output JSON path")
    parser.add_argument("--user-id", type=str, default="",
                        help="Supabase user ID — load profile from Supabase instead of hardcoded PROFILE")
    parser.add_argument("--scan-id", type=str, default="",
                        help="Scan ID for tracking progress in Supabase sent_history")
    parser.add_argument("--posted-date-filter", type=str, default="any",
                        help="Filter jobs by posted date: 1d, 1w, 1m, 3m, any (default: any)")
    args = parser.parse_args()

    # --- If --user-id is provided, load profile from Supabase ---
    _supabase_user_profile = None  # will hold {core_skills, years_experience, current_role, email}
    _supabase_client = None
    _webhook_url = ""
    _supabase_scan_id = args.scan_id or None
    _supabase_posted_date_filter = args.posted_date_filter or "any"

    if args.user_id:
        print(f"  [supabase] Loading profile for user_id={args.user_id}...")
        _sb_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
        _sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not _sb_url or not _sb_key:
            print("Error: NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
            sys.exit(1)

        from supabase import create_client as _sb_create
        _supabase_client = _sb_create(_sb_url, _sb_key)

        # Load user profile
        _profile_result = _supabase_client.table("profiles").select("*").eq("id", args.user_id).maybe_single().execute()
        if not _profile_result.data:
            print(f"Error: No profile found for user_id={args.user_id}")
            sys.exit(1)

        _row = _profile_result.data
        _core_skills = _row.get("core_skills") or []
        if isinstance(_core_skills, str):
            try:
                _core_skills = json.loads(_core_skills)
            except Exception:
                _core_skills = []
        if not _core_skills or not isinstance(_core_skills, list):
            print(f"Error: User {args.user_id} has no core_skills")
            sys.exit(1)

        # Enrich skills from active resume's parsed_skills (resume parser extracts 40+ detailed keywords)
        try:
            _resume_result = _supabase_client.table("resumes").select("parsed_skills, filename, parsed_name").eq("user_id", args.user_id).eq("is_active", True).order("created_at", desc=True).limit(5).execute()
            _best_resume_skills = []
            _best_resume_name = ""
            _user_name = (_row.get("full_name") or _row.get("name") or "").lower().replace(" ", "")
            if _resume_result and _resume_result.data:
                # First pass: find resume matching user's profile name
                for _rrow in _resume_result.data:
                    _parsed_name = (_rrow.get("parsed_name") or "").lower().replace(" ", "")
                    if _user_name and _parsed_name and _user_name in _parsed_name or _parsed_name in _user_name:
                        _rs = _rrow.get("parsed_skills") or []
                        if isinstance(_rs, str):
                            try:
                                _rs = json.loads(_rs)
                            except Exception:
                                _rs = []
                        if _rs:
                            _best_resume_skills = _rs
                            _best_resume_name = _rrow.get("filename", "active resume")
                            break
                # Fallback: use most recent resume with skills (first in list, ordered by created_at desc)
                if not _best_resume_skills:
                    for _rrow in _resume_result.data:
                        _rs = _rrow.get("parsed_skills") or []
                        if isinstance(_rs, str):
                            try:
                                _rs = json.loads(_rs)
                            except Exception:
                                _rs = []
                        if _rs:
                            _best_resume_skills = _rs
                            _best_resume_name = _rrow.get("filename", "active resume")
                            break
            if _best_resume_skills and len(_best_resume_skills) > len(_core_skills):
                print(f"  [supabase] Enriching profile skills: {len(_core_skills)} profile skills -> {len(_best_resume_skills)} resume skills (from {_best_resume_name})")
                # Merge: resume skills + any profile skills not already covered
                _resume_set = set(s.lower() for s in _best_resume_skills)
                _merged = list(_best_resume_skills)
                for _s in _core_skills:
                    if _s.lower() not in _resume_set:
                        _merged.append(_s)
                _core_skills = _merged
            elif _best_resume_skills:
                # Resume has fewer skills, but still merge unique ones in
                _profile_set = set(s.lower() for s in _core_skills)
                for _s in _best_resume_skills:
                    if _s.lower() not in _profile_set:
                        _core_skills.append(_s)
                        _profile_set.add(_s.lower())
        except Exception as _e:
            print(f"  [supabase] Warning: Could not load resume skills: {_e}")

        # Load email from email_preferences
        _pref_result = _supabase_client.table("email_preferences").select("*").eq("user_id", args.user_id).maybe_single().execute()
        _to_email = ""
        _batches_from_db = []
        if _pref_result and _pref_result.data:
            _to_email = _pref_result.data.get("email", "")
            _batches_from_db = _pref_result.data.get("batches") or []
            _webhook_url = _pref_result.data.get("webhook_url", "")

            # Extract batches and posted_date_filter from RUNNING token if scan_id matches
            _sent_hist = _pref_result.data.get("sent_history") or []
            for _item in _sent_hist:
                if isinstance(_item, str) and _item.startswith("RUNNING:"):
                    if _supabase_scan_id and f"scan_id:{_supabase_scan_id}" in _item:
                        for _part in _item.split("|"):
                            if _part.startswith("batches:"):
                                _batches_from_db = _part.replace("batches:", "").split(",")
                            elif _part.startswith("posted_date_filter:"):
                                _supabase_posted_date_filter = _part.replace("posted_date_filter:", "").strip()
                        break

        _supabase_user_profile = {
            "core_skills": _core_skills,
            "years_experience": _row.get("years_experience", 0) or 0,
            "current_role": _row.get("current_role", ""),
            "email": _to_email,
            "batches": _batches_from_db,
            "posted_date_filter": _supabase_posted_date_filter,
        }

        # Swap PROFILE with Supabase user's profile
        PROFILE["name"] = _row.get("full_name") or _row.get("name") or PROFILE["name"]
        PROFILE["core_skills"] = _core_skills
        PROFILE["years_experience"] = _supabase_user_profile["years_experience"]
        PROFILE["current_role"] = _supabase_user_profile.get("current_role", "")
        PROFILE["title_red_flags"] = auto_detect_title_red_flags(_core_skills)
        _rebuild_precompiled_patterns()

        # Set email recipient
        if _to_email:
            os.environ["EMAIL_TO"] = _to_email

        # If --batch not provided on CLI, use batches from Supabase
        if not args.batch and _batches_from_db:
            args.batch = ",".join(_batches_from_db) if len(_batches_from_db) > 1 else _batches_from_db[0] if _batches_from_db else ""

        # Map Supabase/digest batch names to daily_scan batch names
        # Some Supabase names expand to multiple daily_scan batches
        _BATCH_NAME_MAP = {
            "india": ["ats"],
            "europe_companies": ["eu"],
            "europe_boards": ["boards-eu"],
            "middle_east": ["middle-east"],
            "us_canada": ["us-canada"],
            "remote": ["boards-remote", "remote"],  # both remote job boards + remote company ATS
        }
        if args.batch:
            _mapped_batches = []
            for _b in args.batch.split(","):
                _b = _b.strip()
                _mapped_batches.extend(_BATCH_NAME_MAP.get(_b, [_b]))
            # Deduplicate while preserving order
            _seen_batches = set()
            _deduped = []
            for _b in _mapped_batches:
                if _b not in _seen_batches:
                    _seen_batches.add(_b)
                    _deduped.append(_b)
            args.batch = ",".join(_deduped)
            print(f"  [supabase] Mapped batches: {args.batch}")

        # Update existing RUNNING token (created by digest.py) with run_id and progress
        # Don't create a new token — just update the one matching our scan_id
        _github_run_id = os.environ.get("GITHUB_RUN_ID") or "pending"
        _batches_str = args.batch or "all"
        import time as _time_mod
        _batch_label = args.batch or _batches_str
        try:
            # Re-fetch latest sent_history (may have changed since initial load)
            _pref_refresh = _supabase_client.table("email_preferences").select("sent_history").eq("user_id", args.user_id).maybe_single().execute()
            _curr_hist = (_pref_refresh.data.get("sent_history") or []) if (_pref_refresh and _pref_refresh.data) else []
            _new_hist = []
            _updated = False
            for _x in _curr_hist:
                if isinstance(_x, str) and _x.startswith("RUNNING:") and _supabase_scan_id and f"scan_id:{_supabase_scan_id}" in _x:
                    # Update the existing token with run_id and current batch progress
                    # Preserve original batches list, just update status and run_id
                    import re as _re_tok
                    _updated_token = _re_tok.sub(r'run_id:[^|]*', f'run_id:{_github_run_id}', _x)
                    # Update status text
                    _updated_token = _re_tok.sub(r'^RUNNING:[^|]*', f'RUNNING:Scraping {_batch_label}...', _updated_token)
                    _new_hist.append(_updated_token)
                    _updated = True
                else:
                    _new_hist.append(_x)
            if _updated:
                _supabase_client.table("email_preferences").update({
                    "sent_history": _new_hist,
                }).eq("user_id", args.user_id).execute()
                print(f"  [supabase] Updated RUNNING token with run_id={_github_run_id}, batch={_batch_label}")
            else:
                print(f"  [supabase] No RUNNING token found for scan_id={_supabase_scan_id}, skipping update")
        except Exception as _e:
            print(f"  [supabase] Warning: Failed to update running token: {_e}")

        print(f"  [supabase] Profile loaded: {PROFILE['name']} | {PROFILE['years_experience']}yr | {len(_core_skills)} skills")
        print(f"  [supabase] Email: {_to_email} | Batches: {args.batch or 'all'}")

    # --- If --profile is provided, load profile from JSON ---
    if args.profile:
        profile_path = os.path.join(os.path.dirname(__file__) or ".", "profiles", f"{args.profile}.json")
        if not os.path.exists(profile_path):
            print(f"Error: profile not found at {profile_path}")
            print(f"Available profiles: {', '.join(sorted(f.replace('.json','') for f in os.listdir(os.path.join(os.path.dirname(__file__) or '.', 'profiles')) if f.endswith('.json')))}")
            sys.exit(1)
        with open(profile_path) as f:
            loaded = json.load(f)
        PROFILE["name"] = loaded.get("name", PROFILE["name"])
        PROFILE["years_experience"] = loaded.get("years_experience", PROFILE["years_experience"])
        PROFILE["current_role"] = loaded.get("current_role", PROFILE.get("current_role", ""))
        if loaded.get("core_skills"):
            PROFILE["core_skills"] = loaded["core_skills"]
        if loaded.get("seniority_keywords"):
            PROFILE["seniority_keywords"] = loaded["seniority_keywords"]
        if loaded.get("junior_red_flags"):
            PROFILE["junior_red_flags"] = loaded["junior_red_flags"]
        if loaded.get("title_red_flags"):
            PROFILE["title_red_flags"] = loaded["title_red_flags"]
        _rebuild_precompiled_patterns()  # rebuild regex from updated PROFILE
        print(f"  Loaded profile: {PROFILE['name']} | {PROFILE['years_experience']}yr | role: {PROFILE.get('current_role', 'N/A')}")
        print(f"  Skills ({len(PROFILE['core_skills'])}): {', '.join(PROFILE['core_skills'][:10])}...")
        # Auto-set recipient email from profile name if no --email-to given
        if not args.email_to and not os.environ.get("EMAIL_TO"):
            os.environ["EMAIL_TO"] = os.environ.get("GMAIL_ADDRESS", "")

    # --- If --resume is provided, auto-build profile from PDF ---
    if args.resume:
        resume_path = args.resume
        # Handle Google Drive URLs
        if "drive.google.com" in resume_path:
            import re as _re
            file_id_match = _re.search(r'/file/d/([^/]+)', resume_path)
            if not file_id_match:
                file_id_match = _re.search(r'id=([^&]+)', resume_path)
            if file_id_match:
                file_id = file_id_match.group(1)
                dl_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                print(f"Downloading resume from Google Drive (file ID: {file_id})...")
                try:
                    import requests as _requests
                    resp = _requests.get(dl_url, timeout=30)
                    if "downloadWarning" in resp.text or "Google Drive" in resp.text[:500]:
                        # Try with confirm token
                        import re as _re2
                        confirm = _re2.search(r'confirm=([^&"]+)', resp.text)
                        if confirm:
                            dl_url += f"&confirm={confirm.group(1)}"
                            resp = _requests.get(dl_url, timeout=30)
                    ct = resp.headers.get("Content-Type", "")
                    if "pdf" not in ct.lower() and "octet" not in ct.lower():
                        print(f"  Unexpected content type: {ct}, trying alternate download...")
                        dl_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
                        resp = _requests.get(dl_url, timeout=30)
                    resume_path = f"/tmp/resume_{file_id}.pdf"
                    with open(resume_path, "wb") as f:
                        f.write(resp.content)
                    print(f"  Downloaded ({len(resp.content)} bytes) to {resume_path}")
                except Exception as e:
                    print(f"Error downloading from Google Drive: {e}")
                    sys.exit(1)
            else:
                print(f"Error: could not extract file ID from Google Drive URL: {resume_path}")
                sys.exit(1)
        if not os.path.exists(resume_path):
            print(f"Error: resume not found at {resume_path}")
            sys.exit(1)
        print(f"Loading resume: {resume_path}")
        parsed, _missing = parse_resume_pdf(resume_path)
        PROFILE["name"] = parsed["name"] or args.name or PROFILE["name"]
        if parsed["core_skills"]:
            PROFILE["core_skills"] = parsed["core_skills"]
        if parsed["years_experience"]:
            PROFILE["years_experience"] = parsed["years_experience"]
        if parsed.get("current_role"):
            PROFILE["current_role"] = parsed["current_role"]
        # Auto-configure title filters based on detected role domain
        PROFILE["title_red_flags"] = auto_detect_title_red_flags(PROFILE["core_skills"])
        _rebuild_precompiled_patterns()  # rebuild regex from resume-derived PROFILE
        os.environ["RESUME_PATH"] = resume_path
        # Auto-set recipient email from resume (sender stays as .env GMAIL_ADDRESS)
        if parsed["email"] and not args.email_to:
            os.environ["EMAIL_TO"] = parsed["email"]
            print(f"  Auto-detected email: {parsed['email']}")
        print(f"  Profile: {PROFILE['name']} | {PROFILE['years_experience']}yr | role: {PROFILE.get('current_role', 'N/A')}")
        print(f"  Skills ({len(PROFILE['core_skills'])}): {', '.join(PROFILE['core_skills'][:10])}...")

    # Override PROFILE from CLI args (takes priority over resume parse)
    if args.name:
        PROFILE["name"] = args.name
    if args.skills:
        PROFILE["core_skills"] = [s.strip() for s in args.skills.split(",")]
    if args.exp is not None:
        PROFILE["years_experience"] = args.exp
    # If CLI overrode skills or experience, rebuild precompiled patterns
    if args.skills or args.exp is not None:
        _rebuild_precompiled_patterns()

    # Override .env from CLI args
    if args.resume and not args.resume.startswith("---"):  # already handled above
        pass
    if args.email_to:
        os.environ["EMAIL_TO"] = args.email_to
    if args.gmail_user:
        os.environ["GMAIL_ADDRESS"] = args.gmail_user
    if args.gmail_pass:
        os.environ["GMAIL_APP_PASSWORD"] = args.gmail_pass

    # Load IND recognised sponsors (one-time, shared across all batches)
    global _IND_SPONSORS
    if not _IND_SPONSORS:
        _IND_SPONSORS = _load_ind_sponsors()

    print(f"=== Daily job scan started: {datetime.now().isoformat()} ===")
    print(f"Profile: {PROFILE['name']}, {PROFILE['years_experience']}yr, {len(PROFILE['core_skills'])} skills")
    all_matches = []
    failed_parse = []  # companies where no jobs could be parsed (for email report)

    # --- If --batch is comma-separated, run each batch as a subprocess ---
    if args.batch and "," in args.batch:
        batches = [b.strip() for b in args.batch.split(",")]
        for b in batches:
            print(f"\n{'='*60}\nBatch: {b}\n{'='*60}")
            new_argv = [sys.argv[0]]
            skip_next = False
            for a in sys.argv[1:]:
                if skip_next:
                    skip_next = False
                    continue
                if a == "--batch":
                    skip_next = True
                    continue
                if a.startswith("--batch="):
                    continue
                new_argv.append(a)
            new_argv += ["--batch", b]
            import subprocess as _sp
            result = _sp.run([sys.executable] + new_argv)
            if result.returncode != 0:
                print(f"  Batch '{b}' failed with exit code {result.returncode}")
        return

    # --- Load job tracker ---
    tracker = JobTracker()
    tracker.load_from_gsheet()
    print(f"  [tracker] {len(tracker.data['jobs'])} tracked jobs loaded")

    # --email-scan-only: scan Gmail for rejections and exit
    if args.email_scan_only:
        gmail_user = os.environ.get("GMAIL_ADDRESS", "")
        gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
        if not gmail_user or not gmail_pass:
            print("Error: GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env")
            sys.exit(1)
        print("Scanning Gmail for rejection emails...")
        rejections = tracker.scan_email_for_rejections(gmail_user, gmail_pass)
        if rejections:
            print(f"  Detected {len(rejections)} new rejection(s):")
            for t, c, s in rejections:
                print(f"    {t} @ {c} - {s[:80]}")
        else:
            print("  No new rejections found.")
        sync_tracker_to_gsheet(tracker)
        return

    # Inline dedup set — prevents duplicate [match] prints and duplicate entries
    # in all_matches. Checked at insert time in _score_collect, _score_collect_ats,
    # and the board scraper loop. Uses (title, company) key, same as global dedup.
    # Lock protects against race conditions in threaded board scrapers.
    _seen_match_keys = set()
    _seen_match_lock = threading.Lock()

    # Helper to check tracker before adding a match
    def should_include(job):
        # Skip jobs posted more than 6 months ago
        posted = job.get("posted_at")
        if posted is not None and not _is_within_months(posted, 6):
            print(f"  [skip] {job['title'][:40]}... posted {posted if isinstance(posted, str) else posted.strftime('%Y-%m-%d')} (>6mo)")
            return False
        return True

    def _is_permanent_error(msg):
        if not msg:
            return False
        kw = ["cloudflare", "captcha", "access denied", "403", "blocked", "challenge", "unreachable"]
        return any(k in msg.lower() for k in kw)

    def _score_collect(jobs, src_name, src_url, matches):
        for job in jobs:
            if not should_include(job):
                continue
            score, rn = score_job(job["title"], job["description"], job["company"])
            score, rn = _title_only_bypass(job, score, rn, args.threshold)
            if score >= args.threshold:
                dedup_key = (job["title"].strip().lower(), job["company"].strip().lower())
                with _seen_match_lock:
                    if dedup_key in _seen_match_keys:
                        continue
                    _seen_match_keys.add(dedup_key)
                print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                matches.append({**job, "score": score, "resume": pick_resume(job["company"]),
                    "company_url": company_url(job["company"], src_url),
                    "relocation_note": rn,
                    "suggestions": tailoring_suggestion(job["title"], job["description"], job["company"]),
                    "salary_info": get_salary_info(job["company"], job["title"], job["description"]),
                    "source": src_name})
            elif score >= 50:
                print(f"  [near-miss] {job['title'][:60]} @ {job['company']} (score {score})")

    def _score_collect_ats(job, src_name, src_url, matches, sd):
        if not should_include(job):
            return
        score, rn = score_job(job["title"], job["description"], job["company"])
        score, rn = _title_only_bypass(job, score, rn, args.threshold)
        if score == 0:
            sd["filtered"] += 1
        elif score < args.threshold:
            sd["low_score"] += 1
            if score > sd["top_score"]:
                sd["top_score"] = score
                sd["top_title"] = f"{job['title']} @ {job['company']}"
        if score >= args.threshold:
            dedup_key = (job["title"].strip().lower(), job["company"].strip().lower())
            with _seen_match_lock:
                if dedup_key in _seen_match_keys:
                    return
                _seen_match_keys.add(dedup_key)
            print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
            matches.append({**job, "score": score, "resume": pick_resume(job["company"]),
                "company_url": company_url(job["company"], src_url),
                "relocation_note": rn,
                "suggestions": tailoring_suggestion(job["title"], job["description"], job["company"]),
                "salary_info": get_salary_info(job["company"], job["title"], job["description"]),
                "source": src_name})
        elif score >= 50:
            print(f"  [near-miss] {job['title'][:60]} @ {job['company']} (score {score})")

    def _retry_empty(empty, fetch_fn, label):
        if not empty:
            return
        print(f"\n  [retry] Retrying {len(empty)} {label} with 30s buffer...")
        for src in empty:
            time.sleep(30)
            t0 = datetime.now()
            jobs = fetch_fn(src)
            if jobs:
                if isinstance(src, dict):
                    src_name = src.get("name", src.get("url", "unknown"))
                    src_url = src.get("url")
                elif isinstance(src, (list, tuple)) and len(src) > 0:
                    src_name = src[0]
                    src_url = src[1] if len(src) > 1 else None
                else:
                    src_name = str(src)
                    src_url = None
                print(f"  Scanning: {src_name} (retry)")
                _score_collect(jobs, src_name, src_url, all_matches)
                print(f"  Done - {src_name} (retry, {len(jobs)} jobs)")

    if args.source_types in ("all", "ats") and (args.batch == "" or args.batch == "ats"):
        _score_debug = {"filtered": 0, "low_score": 0, "top_score": 0, "top_title": ""}
        ats_empty = []
        for source in _interleave_sources(JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source['region']}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            if not jobs:
                ats_empty.append(source)
            for job in jobs:
                _score_collect_ats(job, source["name"], source.get("url"), all_matches, _score_debug)
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")
        _retry_empty(ats_empty, fetch_jobs_from_source, "empty ATS sources")
        print(f"  [scoring-debug] Filtered: {_score_debug['filtered']}, Below threshold: {_score_debug['low_score']}, "
              f"Best non-match: {_score_debug['top_score']} ({_score_debug['top_title'][:60]})")

    # --- Web search: LinkedIn, Indeed, Naukri, Instahyre ---
    board_scrapers = [
        ("LinkedIn", search_linkedin),
        ("Indeed", search_indeed),
        ("Naukri", search_naukri),
        ("Glassdoor", search_glassdoor),
        ("SimplyHired", search_simplyhired),
        ("WomenInTech", search_womenintech),
        ("Instahyre", search_instahyre),

        ("Foundit", search_foundit),
        ("TimesJobs", search_timesjobs),
        ("Seek", search_seek),
        ("Jora", search_jora),
        ("Xing", search_xing),
        ("JobsCh", search_jobsch),
        ("JobsinGermany", search_jobsingermany),
        ("WorkinFinland", search_workinfinland),
        ("EURES", search_eures),

        # APAC region-specific boards
        ("LinkedInAU", search_linkedin_au),
        ("LinkedInNZ", search_linkedin_nz),
        ("LinkedInSG", search_linkedin_sg),
        ("IndeedAU", search_indeed_au),
        ("IndeedNZ", search_indeed_nz),
        ("IndeedSG", search_indeed_sg),
        ("GlassdoorAU", search_glassdoor_au),
        ("GlassdoorSG", search_glassdoor_sg),
    ]
    # Split boards: boards-major = global/major boards, boards-AU-NZ = niche/regional boards
    _split = 9
    if args.batch == "boards-major":
        board_scrapers = board_scrapers[:_split]
    elif args.batch == "boards-AU-NZ":
        board_scrapers = board_scrapers[_split:]
    elif args.batch == "boards-eu":
        # Pre-warm Playwright in main thread so SAPOEmprego's ThreadPoolExecutor
        # doesn't create the browser in a subthread (causes greenlet thread errors
        # that break all subsequent Playwright calls from the main thread).
        _get_browser()
        board_scrapers = [
            ("NetEmpregos", search_netempregos),
            ("SAPOEmprego", search_sapoemprego),
            ("Infoempleo", search_infoempleo),
            ("Bundesagentur", search_bundesagentur),
            ("IamExpat", search_iamexpat),
            ("WorkInLux", search_workinlux),
            ("IndeedNL", search_indeed_nl),
            ("WelcomeToNL", search_welcome_to_nl),
            ("TogetherAbroad", search_togetherabroad),
            ("StepStone", search_stepstone),
            ("Adzuna", search_adzuna),
            ("Freelancermap", search_freelancermap),
            ("Intermediair", search_intermediair),
            ("NationaleVacaturebank", search_nationalevacaturebank),
        ]
    elif args.batch == "boards-remote":
        _get_browser()
        board_scrapers = [
            ("WeWorkRemotely", search_weworkremotely),
            ("Remotive", search_remotive),
            ("ArcDev", search_arcdev),
            ("RemoteOK", search_remoteok),
            ("Himalayas", search_himalayas),
            ("SkipTheDrive", search_skipthedrive),
            ("WorkingNomads", search_workingnomads),
            ("Jobspresso", search_jobspresso),
            ("Arbeitnow", search_arbeitnow),
            ("EnglishJobSearch", search_englishjobsearch),
            ("Bulldogjob", search_bulldogjob),
            ("VisaSponsor", search_visasponsor),
            ("Incluso", search_incluso),
            ("Crossover", search_crossover),
            ("NoDesk", search_nodesk),
            ("Workew", search_workew),
            ("Kelly", search_kelly),
        ]
    domain_queries = build_domain_queries()
    if args.source_types in ("all", "boards") and (args.batch == "" or args.batch in ("boards-major", "boards-AU-NZ", "boards-eu", "boards-remote", "remote")):
        au_boards = {"Seek", "Jora", "LinkedInAU", "LinkedInNZ", "IndeedAU", "IndeedNZ", "GlassdoorAU"}
        sg_boards = {"LinkedInSG", "IndeedSG", "GlassdoorSG"}
        eu_boards = {"Xing", "JobsCh", "JobsinGermany", "WorkinFinland", "EURES"}
        remote_boards = {"WeWorkRemotely", "Remotive", "ArcDev", "RemoteOK", "SkipTheDrive", "WorkingNomads", "Jobspresso", "Arbeitnow", "EnglishJobSearch", "Bulldogjob", "VisaSponsor", "Incluso", "Crossover", "NoDesk", "Workew", "Kelly"}
        single_run_boards = {"NetEmpregos", "SAPOEmprego", "Infoempleo", "Bundesagentur", "IamExpat", "WorkInLux", "IndeedNL", "WelcomeToNL", "TogetherAbroad", "StepStone", "Adzuna", "Intermediair", "NationaleVacaturebank"} | remote_boards
        pw_names = {"SAPOEmprego", "Bundesagentur", "IamExpat", "WorkInLux", "IndeedNL", "StepStone", "Freelancermap", "Intermediair", "NationaleVacaturebank", "WorkingNomads", "Jobspresso", "Bulldogjob", "Crossover", "Kelly"}
        static_boards = {"SAPOEmprego", "Infoempleo", "IamExpat", "WorkInLux", "TogetherAbroad", "VisaSponsor", "WorkingNomads", "Jobspresso", "NoDesk"}

        def _process_board(board_name, board_fn):
            collected = []
            is_slow = board_name in pw_names or board_name == "Adzuna"
            current_queries = domain_queries
            if is_slow:
                pruned = []
                for q in domain_queries:
                    starts_with_prefix = False
                    for prefix in ["senior", "lead", "staff", "principal", "junior", "associate", "sr.", "sr"]:
                        if q.lower().startswith(prefix + " "):
                            starts_with_prefix = True
                            break
                    if not starts_with_prefix:
                        pruned.append(q)
                current_queries = pruned
                print(f"  [{board_name.lower()}] Pruned queries from {len(domain_queries)} to {len(current_queries)} for optimized execution")

            if board_name in static_boards:
                current_queries = [current_queries[0]] if current_queries else [""]
                print(f"  [{board_name.lower()}] Board ignores search query; executing exactly once to avoid redundant page loads")
            elif board_name in pw_names:
                # Playwright boards are slow (20-60s per query). Already pruned of seniority
                # prefixes above. Keep all base title variants to avoid missing matches.
                pass

            for query in current_queries:
                if board_name in au_boards:
                    regions = ["Australia", "New Zealand"]
                elif board_name in sg_boards:
                    regions = ["Singapore"]
                elif board_name in eu_boards:
                    regions = ["Germany", "Switzerland", "Remote"]
                elif board_name in single_run_boards:
                    regions = ["Remote"]
                elif board_name in ("Naukri", "Instahyre"):
                    regions = ["India"]
                else:
                    regions = ["India", "Remote"]
                print(f"  [{board_name.lower()}] Processing '{query}' @ {', '.join(regions)}")
                t0 = datetime.now()
                for region in regions:
                    jobs = board_fn(query, location=region)
                    for job in jobs:
                        if not should_include(job):
                            continue
                        job["title"] = _translate_to_english(job.get("title", ""))
                        job["description"] = _translate_to_english(job.get("description", ""))
                        score, relocation_note = score_job(job["title"], job["description"], job["company"])
                        score, relocation_note = _title_only_bypass(job, score, relocation_note, args.threshold)
                        if score >= args.threshold:
                            dedup_key = (job["title"].strip().lower(), job["company"].strip().lower())
                            with _seen_match_lock:
                                if dedup_key in _seen_match_keys:
                                    continue
                                _seen_match_keys.add(dedup_key)
                            print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                            resume = pick_resume(job["company"])
                            suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                            salary_info = get_salary_info(job["company"], job["title"], job["description"])
                            collected.append({**job, "score": score, "resume": resume,
                                                "relocation_note": relocation_note, "suggestions": suggestions,
                                                "salary_info": salary_info, "source": board_name})
                        elif score >= 50:
                            print(f"  [near-miss] {job['title'][:60]} @ {job['company']} (score {score})")
                elapsed = (datetime.now() - t0).total_seconds()
                print(f"    [{board_name.lower()}] Done ({elapsed:.1f}s)")
            return collected

        if args.batch == "boards-eu":
            from concurrent.futures import ThreadPoolExecutor, as_completed
            # Playwright sync_api is NOT thread-safe. Keep Playwright scrapers out of the thread pool.
            pw_names = {
                "SAPOEmprego", "Bundesagentur", "IamExpat", "WorkInLux", 
                "IndeedNL", "StepStone", "Freelancermap", "Intermediair", 
                "NationaleVacaturebank"
            }
            # Separate HTTP-based scrapers (thread pool safe) and Playwright-based scrapers
            pool_board_scrapers = [(n, f) for n, f in board_scrapers if n != "Adzuna" and n not in pw_names]
            playwright_scrapers = [(n, f) for n, f in board_scrapers if n in pw_names]
            adzuna_entry = next(((n, f) for n, f in board_scrapers if n == "Adzuna"), None)

            # Start Adzuna in dedicated thread (5s rate-limited between queries)
            adzuna_results = []
            def _adzuna_dedicated():
                if adzuna_entry:
                    adzuna_results.extend(_process_board(*adzuna_entry))
            adzuna_thread = threading.Thread(target=_adzuna_dedicated, name="adzuna-dedicated", daemon=True)
            adzuna_thread.start()
            print("  [adzuna] Started in dedicated thread (5s inter-query delay)")

            # Execute HTTP scrapers in thread pool (safe and fast)
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {}
                for name, fn in pool_board_scrapers:
                    futures[pool.submit(_process_board, name, fn)] = name
                for f in as_completed(futures):
                    board = futures[f]
                    try:
                        all_matches.extend(f.result())
                    except Exception as e:
                        print(f"  [thread-error] {board}: {e}")

            # Wait for Adzuna dedicated thread to finish
            adzuna_thread.join(timeout=300)
            all_matches.extend(adzuna_results)
            if adzuna_thread.is_alive():
                print("  [adzuna] Warning: dedicated thread still running after 5min timeout")

            # Execute Playwright scrapers in parallel batches of 3
            # (separate processes, each with own Chromium — safe and fast)
            pw_filter = os.environ.get("PLAYWRIGHT_SCRAPER_FILTER", "")
            pw_to_run = [(name, fn) for name, fn in playwright_scrapers if not pw_filter or name == pw_filter]
            
            if pw_to_run:
                print(f"  [playwright] Running {len(pw_to_run)} EU Playwright scrapers in batches of 3")
                PW_BATCH_SIZE = 3
                for pw_batch_idx in range(0, len(pw_to_run), PW_BATCH_SIZE):
                    pw_batch = pw_to_run[pw_batch_idx:pw_batch_idx + PW_BATCH_SIZE]
                    pw_threads = []
                    pw_batch_results = []
                    
                    def _run_pw_scraper(name, fn, results_list):
                        try:
                            results_list.extend(_process_board(name, fn))
                        except Exception as e:
                            print(f"  [{name.lower()}] Error: {e}")
                    
                    for name, fn in pw_batch:
                        result_list = []
                        pw_batch_results.append(result_list)
                        t = threading.Thread(target=_run_pw_scraper, args=(name, fn, result_list), daemon=True)
                        pw_threads.append(t)
                        t.start()
                    
                    for t in pw_threads:
                        t.join(timeout=300)
                    
                    for result_list in pw_batch_results:
                        all_matches.extend(result_list)

            # --- Paginated company scrapers (run once, not per query) ---
            for pw_name, pw_fn in [("Philips", search_philips), ("Liebherr", search_liebherr)]:
                print(f"  [{pw_name.lower()}] Scraping with pagination")
                t0 = datetime.now()
                try:
                    jobs = pw_fn()
                    _score_collect(jobs, pw_name, None, all_matches)
                except Exception as e:
                    print(f"  [{pw_name.lower()}] Error: {e}")
                elapsed = (datetime.now() - t0).total_seconds()
                print(f"    [{pw_name.lower()}] Done ({elapsed:.1f}s)")
        else:
            for board_name, board_fn in board_scrapers:
                all_matches.extend(_process_board(board_name, board_fn))

    # --- Playwright-based scrapers (JS-rendered sites, called once not per query) ---
    is_sap_profile = any("sap" in s.lower() or "erp" in s.lower() for s in PROFILE["core_skills"][:5])
    exp = PROFILE["years_experience"]
    if is_sap_profile:
        pw_scrapers = []
    else:
        pw_scrapers = [
            ("WorkAtAStartup", search_workatstartup),
        ]
    # Batch scrapers (HTTP + Playwright) that support domain-specific queries
    pw_batch_scrapers = [
        ("SkipTheDrive", search_skipthedrive),
        ("WorkingNomads", search_workingnomads),
        ("Jobspresso", search_jobspresso),
        ("EnglishJobSearch", search_englishjobsearch),
        ("BulldogJob", search_bulldogjob),
        ("StepStone", search_stepstone),
        ("MonsterDE", search_monsterde),
        ("Adzuna", search_adzuna),
        ("Reed", search_reed),
        ("Jobsite", search_jobsite),
        ("Intermediair", search_intermediair),
        ("NationaleVacaturebank", search_nationalevacaturebank),
    ]
    if args.source_types in ("all", "playwright") and (args.batch == "" or args.batch == "playwright"):
        for pw_name, pw_fn in pw_scrapers:
            print(f"  [{pw_name.lower()}] Processing")
            t0 = datetime.now()
            try:
                jobs = pw_fn("", location="Remote")
                _score_collect(jobs, pw_name, None, all_matches)
            except Exception as e:
                print(f"  [{pw_name.lower()}] Error: {e}")
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"    [{pw_name.lower()}] Done ({elapsed:.1f}s)")
        for pw_name, pw_fn in pw_batch_scrapers:
            print(f"  [{pw_name.lower()}] Processing {len(domain_queries)} queries")
            t0 = datetime.now()
            for query in domain_queries:
                try:
                    jobs = pw_fn(query, location="Remote")
                    _score_collect(jobs, pw_name, None, all_matches)
                except Exception as e:
                    print(f"  [{pw_name.lower()}] Error: {e}")
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"    [{pw_name.lower()}] Done ({elapsed:.1f}s)")

    # --- EU companies (batch: eu) ---
    if args.batch == "eu":
        import multiprocessing as _mp
        # Use get_context instead of set_start_method to avoid polluting
        # the global multiprocessing state for the rest of the process
        _ctx = _mp.get_context("spawn")

        sources = list(_interleave_sources(EU_JOB_SOURCES))

        with _ctx.Pool(processes=4) as pool:
            results = pool.map(_fetch_source_jobs, sources)

        for source, jobs, error in results:
            print(f"Scanning: {source['name']} ({source.get('region','EU')}) - {source['url']}")
            t0 = datetime.now()
            if error:
                print(f"  [error] {source['name']}: {error}")
                failed_parse.append(source)
                continue
            if jobs:
                _score_collect(jobs, source["name"], source.get("url"), all_matches)
            print(f"  Done - {source['name']} ({(datetime.now()-t0).total_seconds():.1f}s, {len(jobs)} jobs)")
        _retry_empty(failed_parse, fetch_jobs_from_source, "EU sources")

    # --- Global companies / recruiters (batch: global) ---
    if args.batch == "global":
        empty = []
        for source in _interleave_sources(GLOBAL_JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source.get('region','Global')}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            if not jobs:
                empty.append(source)
            else:
                _score_collect(jobs, source["name"], source.get("url"), all_matches)
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")
        _retry_empty(empty, fetch_jobs_from_source, "global sources")

    # --- APAC companies (batch: apac) ---
    if args.batch == "apac":
        empty = []
        for source in _interleave_sources(APAC_JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source.get('region','APAC')}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            if not jobs:
                empty.append(source)
            else:
                _score_collect(jobs, source["name"], source.get("url"), all_matches)
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")
        _retry_empty(empty, fetch_jobs_from_source, "APAC sources")

    # --- US/Canada companies (batch: us-canada) ---
    if args.batch == "us-canada":
        empty = []
        for source in _interleave_sources(US_CANADA_JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source.get('region','US/Canada')}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            if not jobs:
                empty.append(source)
            else:
                _score_collect(jobs, source["name"], source.get("url"), all_matches)
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")
        _retry_empty(empty, fetch_jobs_from_source, "US/Canada sources")

    # --- Middle East companies (batch: middle-east) ---
    if args.batch == "middle-east":
        empty = []
        for source in _interleave_sources(MIDDLE_EAST_JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source.get('region','Middle East')}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            if not jobs:
                empty.append(source)
            else:
                _score_collect(jobs, source["name"], source.get("url"), all_matches)
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")
        _retry_empty(empty, fetch_jobs_from_source, "Middle East sources")

    # --- Remote companies (batch: remote) ---
    if args.batch == "remote":
        import multiprocessing as _mp
        _ctx = _mp.get_context("spawn")
        sources = list(_interleave_sources(REMOTE_JOB_SOURCES))
        with _ctx.Pool(processes=4) as pool:
            results = pool.map(_fetch_source_jobs, sources)
        for source, jobs, error in results:
            print(f"Scanning: {source['name']} ({source.get('region','Remote')}) - {source['url']}")
            if error:
                print(f"  [error] {source['name']}: {error}")
                failed_parse.append(source)
                continue
            if jobs:
                _score_collect(jobs, source["name"], source.get("url"), all_matches)
        _retry_empty(failed_parse, fetch_jobs_from_source, "Remote sources")

    # --- Email digest scan (Glassdoor / Indeed) — set GMAIL_ADDRESS/GMAIL_APP_PASSWORD env or secrets ---
    if args.digest:
        digest_label = args.digest_label or os.environ.get("GMAIL_DIGEST_LABEL")
        if not digest_label:
            print(f"\n  [digest] No GMAIL_DIGEST_LABEL set — skipping digest scan")
        else:
            print(f"\n  [digest] Scanning Gmail for job digest emails...")
            try:
                from email_digest_scan import parse_all_digests
                digest_jobs = parse_all_digests(days=7, label=digest_label)
                print(f"  [digest] {len(digest_jobs)} jobs parsed, scoring...")
                for dj in digest_jobs:
                    if not should_include(dj):
                        continue
                    score, relocation_note = score_job(dj.get("title", ""), dj.get("description", ""), dj.get("company", ""))
                    score, relocation_note = _title_only_bypass(dj, score, relocation_note, args.threshold)
                    if score >= 50:
                        if score >= args.threshold:
                            print(f"  [digest-match] {dj['title'][:60]} @ {dj.get('company','?')} (score {score})")
                        else:
                            print(f"  [digest-near] {dj['title'][:60]} @ {dj.get('company','?')} (score {score})")
                        resume = pick_resume(dj.get("company", ""))
                        suggestions = tailoring_suggestion(dj.get("title", ""), "", dj.get("company", ""))
                        salary_info = get_salary_info(dj.get("company", ""), dj.get("title", ""), "")
                        all_matches.append({
                            **dj,
                            "score": score,
                            "resume": resume,
                            "company_url": company_url(dj.get("company", ""), ""),
                            "relocation_note": relocation_note,
                            "suggestions": suggestions,
                            "salary_info": salary_info,
                            "source": dj.get("source", "email-digest"),
                        })
            except Exception as e:
                print(f"  [digest] ERROR: {e}")

    all_matches.sort(key=lambda m: m["score"], reverse=True)

    # --- Deduplicate matches (same job from multiple sources) ---
    seen_keys = set()
    unique_matches = []
    for m in all_matches:
        # Key on normalized title + company (case-insensitive) to catch dupes across scrapers
        key = (m["title"].strip().lower(), m["company"].strip().lower())
        # Also deduplicate by URL if available
        url_key = m.get("url", "").rstrip("/").lower()
        if key not in seen_keys and (not url_key or url_key not in seen_keys):
            seen_keys.add(key)
            if url_key:
                seen_keys.add(url_key)
            unique_matches.append(m)
    if len(all_matches) != len(unique_matches):
        print(f"  [dedup] Removed {len(all_matches) - len(unique_matches)} duplicate matches")
    all_matches = unique_matches

    # --- Batch mode: save per-batch results, merge on final batch ---
    if args.batch:
        batch_path = f"last_scan_results_batch_{args.batch}.json"
        with open(batch_path, "w") as f:
            json.dump(all_matches, f, indent=2, default=str)
        print(f"  [batch {args.batch}] Saved {len(all_matches)} matches to {batch_path}")

        # Send email after every batch run with that batch's results
        # (skip for terminal batch 'eu' — it sends a merged email below)
        if all_matches or failed_parse:
            person_name = PROFILE.get("name", "Job Seeker").split()[0].title()
            batch_labels = {
                "ats": "ATS-Company Scrape", "boards-major": "Major Job Boards",
                "boards-AU-NZ": "AU-NZ+Regional Boards", "boards-remote": "Remote Job Boards", "playwright": "Playwright Scrape",
                "eu": "EU Companies", "global": "Global Companies",
                "apac": "APAC Companies", "us-canada": "US-Canada Companies",
                "middle-east": "Middle East Companies",
            }
            label = batch_labels.get(args.batch, args.batch)
            subject = f"{person_name}-Job matches-{label}"
            html = build_email_html(all_matches, failed_parse)
            if args.preview:
                with open("preview.html", "w") as f:
                    f.write(html)
                print(f"  [preview] Saved to preview.html ({len(html)} bytes) — open in browser")
            else:
                send_email(html, subject=subject)
            # Auto-log jobs to web tracker
            try:
                from api.email_tracker import log_jobs_to_tracker
                logged = log_jobs_to_tracker(all_matches)
                if logged:
                    print(f"  [tracker] Logged {logged} jobs to web tracker")
            except Exception:
                pass
        else:
            print(f"  [email] No matches found for resume - skipping email")

        if args.batch != "eu":
            batch_sequence = {
                "ats": "boards-major",
                "boards-major": "boards-AU-NZ",
                "boards-AU-NZ": "boards-remote",
                "boards-remote": "remote",
                "remote": "boards-eu",
                "boards-eu": "playwright",
                "playwright": "global",
                "global": "apac",
                "apac": "us-canada",
                "us-canada": "middle-east",
                "middle-east": "eu",
            }
            batch_next = batch_sequence.get(args.batch)
            if batch_next:
                print(f"Batch '{args.batch}' done. Run --batch {batch_next} next for remaining sources.")
                return

        # Terminal batch (eu): load all previous batch results and merge
        all_batch_ids = ["ats", "boards-major", "boards-AU-NZ", "boards-remote", "boards-eu", "playwright", "global", "apac", "us-canada", "middle-east", "eu"]
        for b in all_batch_ids:
            if b == args.batch:
                continue  # current batch is already in all_matches
            prev_path = f"last_scan_results_batch_{b}.json"
            if os.path.exists(prev_path):
                with open(prev_path) as f:
                    prev = json.load(f)
                all_matches.extend(prev)
                print(f"  [merge] Loaded {len(prev)} matches from {prev_path}")
        all_matches.sort(key=lambda m: m["score"], reverse=True)
        # Deduplicate again after merging batches
        seen_keys = set()
        unique_matches = []
        for m in all_matches:
            key = (m["title"].strip().lower(), m["company"].strip().lower())
            url_key = m.get("url", "").rstrip("/").lower()
            if key not in seen_keys and (not url_key or url_key not in seen_keys):
                seen_keys.add(key)
                if url_key:
                    seen_keys.add(url_key)
                unique_matches.append(m)
        if len(all_matches) != len(unique_matches):
            print(f"  [dedup] Removed {len(all_matches) - len(unique_matches)} duplicate matches after merge")
        all_matches = unique_matches

    # --- Save new matches to tracker (with resume info) ---
    for m in all_matches:
        tracker.add_job(m["title"], m["company"], m.get("url", ""), m["score"], resume=m.get("resume", ""))

    # --- Annotate matches with previous tracker status (same company, within 6 months) ---
    if args.profile or args.resume:
        for m in all_matches:
            tr_status, tr_title, tr_date = tracker.get_company_status(m["company"], within_months=6)
            if tr_status:
                m["tracker_status"] = tr_status
                m["tracker_date"] = tr_date[:10] if tr_date else ""
                print(f"  [tracked] {m['company']} — already {tr_status} ({tr_date[:10] if tr_date else '?'})")

    print(f"Found {len(all_matches)} matches above {args.threshold}% threshold.")
    print(f"  [tracker] {len(tracker.data['jobs'])} total jobs tracked")

    if all_matches or failed_parse:
        html = build_email_html(all_matches, failed_parse)
        person_name = PROFILE.get("name", "Job Seeker").split()[0].title()
        batch_labels = {
            "ats": "ATS-Company Scrape", "boards-major": "Major Job Boards",
            "boards-AU-NZ": "AU-NZ+Regional Boards", "boards-remote": "Remote Job Boards", "playwright": "Playwright Scrape",
            "eu": "EU Companies", "global": "Global Companies",
            "apac": "APAC Companies", "us-canada": "US-Canada Companies",
            "middle-east": "Middle East Companies",
        }
        label = batch_labels.get(args.batch, "All Sources") if args.batch else "All Sources"
        if args.digest:
            label += "+Digests"
        send_email(html, subject=f"{person_name}-Job matches-{label}")
        # Auto-log jobs to web tracker
        try:
            from api.email_tracker import log_jobs_to_tracker
            logged = log_jobs_to_tracker(all_matches)
            if logged:
                print(f"  [tracker] Logged {logged} jobs to web tracker")
        except Exception:
            pass
    else:
        print(f"  [email] No matches found for resume - skipping email")

    # WhatsApp disabled per user request - all results go via email only
    # if all_matches:
    #     top3 = all_matches[:3]
    #     whatsapp_msg = "Top job matches:\n"
    #     for m in top3:
    #         whatsapp_msg += f"- {m['title']} at {m['company']} ({m['score']}%)\n"
    #     whatsapp_msg += "Check your email for full details."
    #     send_whatsapp(whatsapp_msg)

    with open("last_scan_results.json", "w") as f:
        json.dump(all_matches, f, indent=2, default=str)

    # Also save as CSV for Google Sheets / Excel
    csv_path = "job_matches.csv"
    try:
        import csv
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Score", "Title", "Company", "Location", "Salary", "URL", "Company Link", "Relocation Note", "Suggestions", "Status"])
            for m in all_matches:
                suggestions = "; ".join(m.get("suggestions", []))
                status = tracker.get_status(m["title"], m["company"])
                salary_str = _format_salary(m.get("salary_info", {})) if m.get("salary_info") else ""
                writer.writerow([
                    m["score"], m["title"], m["company"], m.get("location", ""),
                    salary_str,
                    m.get("url", ""), m.get("company_url", company_url(m["company"])),
                    m.get("relocation_note", ""), suggestions, status
                ])
        print(f"  [csv] Saved {len(all_matches)} matches to {csv_path}")
    except Exception as e:
        print(f"  [csv] Error saving CSV: {e}")

    # --- Push to Google Sheets if service account exists ---
    gsheet_id = os.environ.get("GSHEET_ID")
    gsheet_sa_path = os.environ.get("GSHEET_SERVICE_ACCOUNT") or "gsheet_service_account.json"
    if gsheet_id and os.path.exists(gsheet_sa_path):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = service_account.Credentials.from_service_account_file(gsheet_sa_path, scopes=SCOPES)
            service = build("sheets", "v4", credentials=creds)
            sheet = service.spreadsheets()

            # Build rows: header + data
            rows = [["Score", "Title", "Company", "Location", "Salary", "URL", "Company Link", "Relocation Note", "Suggestions", "Status"]]
            for m in all_matches:
                suggestions = "; ".join(m.get("suggestions", []))
                status = tracker.get_status(m["title"], m["company"])
                salary_str = _format_salary(m.get("salary_info", {})) if m.get("salary_info") else ""
                rows.append([
                    m["score"], m["title"], m["company"], m.get("location", ""),
                    salary_str,
                    m.get("url", ""), m.get("company_url", company_url(m["company"])),
                    m.get("relocation_note", ""), suggestions, status
                ])

            # First clear existing data, then write
            sheet.values().clear(spreadsheetId=gsheet_id, range="Sheet1!A:Z").execute()
            sheet.values().update(
                spreadsheetId=gsheet_id,
                range="Sheet1!A1",
                valueInputOption="RAW",
                body={"values": rows}
            ).execute()
            print(f"  [gsheet] Synced {len(all_matches)} matches to Google Sheet")
        except Exception as e:
            print(f"  [gsheet] Error: {e}")

    # --- Supabase: update sent_history and log jobs to tracker ---
    if args.user_id and _supabase_client:
        import time as _time_mod2
        try:
            # Load current sent_history
            _pref_r = _supabase_client.table("email_preferences").select("sent_history").eq("user_id", args.user_id).maybe_single().execute()
            _curr_h = (_pref_r.data.get("sent_history") or []) if (_pref_r and _pref_r.data) else []

            # Don't remove the RUNNING token here — parallel batch jobs share it.
            # The scans UI endpoint cleans up finished runs by checking GitHub API.
            # Just append a COMPLETED entry for this batch.
            _batch_label2 = args.batch or "all"
            _curr_h.append(f"COMPLETED_INSTANT:{int(_time_mod2.time())}|jobs:{len(all_matches)}|batch:{_batch_label2}")

            _supabase_client.table("email_preferences").update({
                "sent_history": _curr_h,
                "last_sent_at": datetime.now().isoformat(),
            }).eq("user_id", args.user_id).execute()
            print(f"  [supabase] Updated sent_history: COMPLETED with {len(all_matches)} jobs")
        except Exception as _e:
            print(f"  [supabase] Warning: Failed to update completion status: {_e}")

        # Log jobs to Supabase jobs table
        try:
            _logged = 0
            for _m in all_matches:
                _existing = (
                    _supabase_client.table("jobs")
                    .select("id")
                    .eq("user_id", args.user_id)
                    .eq("title", _m["title"])
                    .eq("company", _m["company"])
                    .limit(1)
                    .execute()
                )
                if _existing.data:
                    continue
                _supabase_client.table("jobs").insert({
                    "user_id": args.user_id,
                    "title": _m["title"],
                    "company": _m["company"],
                    "url": _m.get("url", ""),
                    "score": _m.get("score", 0),
                    "location": _m.get("location", ""),
                    "salary": _format_salary(_m.get("salary_info", {})) if _m.get("salary_info") else "",
                    "source": _m.get("source", "daily_scan"),
                    "status": "new",
                }).execute()
                _logged += 1
            if _logged:
                print(f"  [supabase] Logged {_logged} jobs to tracker for user {args.user_id}")
        except Exception as _e:
            print(f"  [supabase] Warning: Failed to log jobs to tracker: {_e}")

        # Send webhook notification if configured
        if _webhook_url:
            try:
                _webhook_payload = {
                    "text": f"Scan complete: {len(all_matches)} job matches found (batch: {args.batch or 'all'})",
                    "content": f"Scan complete: {len(all_matches)} job matches found (batch: {args.batch or 'all'})",
                    "username": "JobPilot",
                    "matches": len(all_matches),
                    "batch": args.batch or "all",
                    "top_jobs": [{"title": m["title"], "company": m["company"], "score": m["score"], "url": m.get("url", "")} for m in all_matches[:5]],
                }
                _wh_resp = requests.post(_webhook_url, json=_webhook_payload, timeout=10)
                if _wh_resp.status_code < 300:
                    print(f"  [webhook] Notified: {_webhook_url[:50]}...")
                else:
                    print(f"  [webhook] Warning: status {_wh_resp.status_code}")
            except Exception as _e:
                print(f"  [webhook] Warning: Failed to send webhook: {_e}")

    print("=== Scan complete ===")


def _gsheet_tab_name(resume_name, existing_tabs):
    """Generate a valid sheet tab name (<=100 chars, unique)."""
    base = re.sub(r'[\/\?\*\[\]]', '', resume_name or "All Jobs")
    base = base[:95]
    name = base
    n = 2
    while name in existing_tabs:
        name = f"{base[:92]} ({n})"
        n += 1
    return name

def sync_tracker_to_gsheet(tracker_instance=None):
    """
    Push all tracked jobs with their current statuses to Google Sheets,
    organized into tabs by resume version. A main "All Jobs" tab is also created.
    Can be called standalone (e.g. from MCP server after status updates).
    Returns True on success, False otherwise.
    """
    gsheet_id = os.environ.get("GSHEET_ID")
    gsheet_sa_path = os.environ.get("GSHEET_SERVICE_ACCOUNT") or "gsheet_service_account.json"
    if not gsheet_id or not os.path.exists(gsheet_sa_path):
        return False
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        if tracker_instance is None:
            tracker_instance = JobTracker()

        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = service_account.Credentials.from_service_account_file(gsheet_sa_path, scopes=SCOPES)
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        # Get existing tabs
        spreadsheet = sheet.get(spreadsheetId=gsheet_id).execute()
        existing_tabs = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

        # Group jobs by resume
        jobs_by_resume = {}
        for key, entry in tracker_instance.data.get("jobs", {}).items():
            resume = entry.get("resume", "") or "No Resume"
            jobs_by_resume.setdefault(resume, []).append(entry)

        # Build rows per resume group
        header = ["Score", "Title", "Company", "Location", "URL", "Company Link", "Status", "Date Found"]
        resume_tabs = {}
        for resume_name, jobs in jobs_by_resume.items():
            rows = [header]
            for j in jobs:
                rows.append([
                    j.get("score", ""),
                    j.get("title", ""),
                    j.get("company", ""),
                    "",
                    j.get("url", ""),
                    company_url(j.get("company", "")),
                    j.get("status", "new"),
                    j.get("date_found", "")[:10],
                ])
            tab_name = _gsheet_tab_name(resume_name, existing_tabs)
            resume_tabs[tab_name] = rows

        # Also make an "All Jobs" tab
        all_rows = [header]
        for key, entry in tracker_instance.data.get("jobs", {}).items():
            all_rows.append([
                entry.get("score", ""),
                entry.get("title", ""),
                entry.get("company", ""),
                "",
                entry.get("url", ""),
                company_url(entry.get("company", "")),
                entry.get("status", "new"),
                entry.get("date_found", "")[:10],
            ])
        all_tab = _gsheet_tab_name("All Jobs", existing_tabs)
        resume_tabs[all_tab] = all_rows

        # Clear and write each tab
        for tab_name, rows in resume_tabs.items():
            if tab_name in existing_tabs:
                sheet.values().clear(spreadsheetId=gsheet_id, range=f"'{tab_name}'!A:Z").execute()
            else:
                sheet.batchUpdate(spreadsheetId=gsheet_id, body={
                    "requests": [{
                        "addSheet": {"properties": {"title": tab_name}}
                    }]
                }).execute()
                existing_tabs.append(tab_name)

            sheet.values().update(
                spreadsheetId=gsheet_id,
                range=f"'{tab_name}'!A1",
                valueInputOption="RAW",
                body={"values": rows}
            ).execute()

        print(f"  [gsheet] Synced {len(all_rows)-1} jobs across {len(resume_tabs)} tabs: {', '.join(resume_tabs.keys())}")
        return True
    except Exception as e:
        print(f"  [gsheet] Error: {e}")
        return False


if __name__ == "__main__":
    main()
