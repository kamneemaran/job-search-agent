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
from dotenv import load_dotenv
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Lazy import for Playwright (headless browser for JS-rendered sites)
_playwright_browser = None
_playwright_pw = None
def _get_browser():
    global _playwright_browser, _playwright_pw
    if _playwright_browser is None:
        from playwright.sync_api import sync_playwright
        _playwright_pw = sync_playwright().start()
        _playwright_browser = _playwright_pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
    return _playwright_browser

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
        """)
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
    ],
    "current_role": "Senior Software Engineer",
    "seniority_keywords": ["senior", "staff", "lead", "principal", "sde-3", "sde 3"],
    "junior_red_flags": ["junior", "intern", "entry level", "graduate", "0-2 years"],
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
    "mollie": "No relocation support outside Europe (confirmed - application rejected screening)",
}

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
    {"name": "Anthropic", "url": "https://job-boards.greenhouse.io/anthropic", "region": "Global", "type": "company", "ats": "greenhouse", "ats_slug": "anthropic"},
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
    {"name": "Vercel", "url": "https://vercel.com/careers", "region": "Remote", "type": "company", "ats": "greenhouse", "ats_slug": "vercel"},
    {"name": "Meta (Facebook)", "url": "https://linkedin.com/company/meta", "region": "Global", "type": "company", "playwright": True},
    # --- IT Services / Enterprise (some SAP/ERP relevance) ---
    {"name": "TCS", "url": "https://www.tcs.com/careers", "region": "IN", "type": "company", "ats": "greenhouse", "ats_slug": "tcs"},
    # --- EU / NL / DE ---
    {"name": "Mollie", "url": "https://jobs.mollie.com/vacancies", "region": "NL", "type": "company", "playwright": True},
    {"name": "Booking.com", "url": "https://jobs.booking.com/booking/jobs?keywords=engineer", "region": "NL", "type": "company", "playwright": True},
    {"name": "Picnic Technologies", "url": "https://jobs.picnic.app/en/vacancies", "region": "EU", "type": "company", "playwright": True},
    {"name": "Personio", "url": "https://www.personio.com/about-personio/careers/#see-our-open-roles", "region": "DE", "type": "company", "playwright": True},
    # --- Germany (61 English-speaking companies with visa sponsorship) ---
    {"name": "3D Spark", "url": "https://www.3dspark.de/career#Job-Offers", "region": "DE", "type": "company", "playwright": True},
    {"name": "Aampere", "url": "https://linkedin.com/company/ampere-computing", "region": "DE", "type": "company", "playwright": True},
    {"name": "Ada", "url": "https://adaglobal.darwinbox.com/ms/candidatev2/main/careers/allJobs", "region": "DE", "type": "company", "playwright": True},
    {"name": "Adevinta", "url": "https://adevinta.com/careers/", "region": "DE", "type": "company", "playwright": True},
    {"name": "Aeyde", "url": "https://aeyde.jobs.personio.de/", "region": "DE", "type": "company", "ats": "personio"},
    {"name": "Adidas", "url": "https://linkedin.com/company/adidas", "region": "DE", "type": "company", "playwright": True},
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
    {"name": "Emma - The Sleep Co", "url": "https://jobs.lever.co/emma-sleep", "region": "DE", "type": "company"},
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
    {"name": "Spring Professional", "url": "https://linkedin.com/company/springprofessional"},
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

    # Strip seniority prefix to get base role (e.g., "software engineer" from "Senior Software Engineer")
    base_role = role_lower
    for prefix in _SENIORITY_PREFIXES:
        if base_role.startswith(prefix):
            base_role = base_role[len(prefix):]
            break

    keywords = [base_role]  # always match base role

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
        "backend": ["backend engineer", "backend developer", "back end engineer", "back-end engineer"],
        "platform": ["platform engineer"],
        "cloud infrastructure": ["cloud engineer", "infrastructure engineer"],
        "distributed systems": ["systems engineer", "distributed systems engineer"],
        "microservices": ["backend engineer", "backend developer"],
        "api development": ["api engineer", "api developer"],
        "data pipelines": ["data platform engineer"],
        "devops": ["platform engineer", "infrastructure engineer"],
        "system design": ["systems architect"],
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

    if any(re.search(r'(?<![a-z])' + re.escape(flag) + r'(?![a-z])', text) for flag in PROFILE["junior_red_flags"]):
        return 0, "Filtered: junior/entry-level role detected"

    # Reject roles whose titles match red-flag career tracks
    for red_flag in PROFILE["title_red_flags"]:
        if red_flag in title_lower:
            return 0, f"Filtered: title matches non-relevant track ({red_flag})"

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
    exp_patterns = [
        (r'(\d+)\+?\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)', 'min'),
        (r'(?:min|minimum|at least|≥)\s*(\d+)\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)', 'min'),
        (r'(?:max|maximum|up to|≤)\s*(\d+)\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)', 'max'),
        (r'(\d+)\s*(?:to|-|–)\s*(\d+)\s*(?:yrs?|years?)\s*(?:of)?\s*(?:exp|experience)', 'range'),
        (r'(\d+)\s*-\s*(\d+)\s*(?:yrs?|years?)\s*(?:of\s+)?(?:exp|experience|professional|relevant|work)', 'range'),
    ]
    for pattern, ptype in exp_patterns:
        matches = re.findall(pattern, text)
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

    # --- Reject roles requiring travel (not relevant for remote/backend roles) ---
    travel_patterns = [r'\d+%\s*travel', r'travel\s+up\s+to\s+\d+', r'willingness to travel',
                       r'require[sd]?\s+travel', r'must be willing to travel', r'overnight travel',
                       r'travel\s+\d+\s*-\s*\d+', r'able to travel']
    if any(re.search(p, text) for p in travel_patterns):
        return 0, "Filtered: role requires travel"

    # --- For roles outside India / Remote: visa & relocation assessment ---
    is_outside_india = "india" not in loc_lower and "india" not in text
    is_remote = "remote" in loc_lower or "remote" in text
    visa_note = ""
    has_visa_relo = False
    has_visa_sponsor = False
    has_relo_support = False
    in_friendly_list = False

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
        if has_visa_relo or in_friendly_list:
            parts = []
            if has_visa_sponsor or in_friendly_list:
                parts.append("Visa sponsorship")
            if has_relo_support or in_friendly_list:
                parts.append("Relocation support")
            visa_note = " + ".join(parts) + " mentioned"
        else:
            visa_note = "Visa sponsorship details not mentioned"

    # --- SAP roles: if title mentions SAP, require SAP MM in JD ---
    title_lower = title.lower().replace("-", " ")  # normalize hyphens for matching
    has_sap_in_title = "sap" in title_lower or "abap" in title_lower
    has_sap_skills = any("sap" in s or "abap" in s for s in PROFILE["core_skills"])
    if has_sap_in_title and has_sap_skills and "sap mm" not in text:
        return 0, "Filtered: SAP role requires SAP MM in JD"

    # --- Skill scoring (word-boundary matching; up to 50 points) ---
    skill_hits = sum(1 for skill in PROFILE["core_skills"]
                     if re.search(r'\b' + re.escape(skill) + r'\b', text))
    total_skills = len(PROFILE["core_skills"])
    # Need 40% of resume skills to appear in JD for full score (min 5 hits)
    skill_denominator = max(int(total_skills * 0.4), 5)
    skill_score = min(skill_hits / skill_denominator, 1.0) * 50  # up to 50 points

    # --- Title relevance scoring (derived from resume's current_role) ---
    title_relevance = 0
    exp_years = PROFILE["years_experience"]
    title_keywords = _derive_title_keywords(PROFILE.get("current_role", ""), exp_years)
    # Full role match = 30 (base role or skill-derived variant), partial word match = 10
    if title_keywords:
        base_role = title_keywords[0]  # first entry is always the base role
        # Full role variants include base_role + skill-derived roles (multi-word entries)
        full_role_variants = [kw for kw in title_keywords if " " in kw]
        # Single words are partial matches only
        partial_words = [kw for kw in title_keywords if " " not in kw]
        if any(variant in title_lower for variant in full_role_variants):
            title_relevance = 30
        elif any(kw in title_lower for kw in partial_words):
            title_relevance = 10

    # --- Seniority scoring (experience-appropriate) ---
    seniority_keywords = _get_seniority_keywords(exp_years)
    if seniority_keywords and any(k in text for k in seniority_keywords):
        seniority_score = 15
    elif not seniority_keywords:
        # Junior profiles (<3 yrs): give 10 points if role doesn't demand seniority
        senior_in_text = any(k in text for k in ["senior", "staff", "lead", "principal"])
        seniority_score = 10 if not senior_in_text else 0
    else:
        # Experienced profiles: many roles don't explicitly say "senior" but target 5-10yr candidates
        seniority_score = 10 if exp_years >= 5 else 5

    # --- International opportunity bonuses (visa & relocation scored independently) ---
    # For jobs outside India with a title match, visa sponsorship and relocation
    # support each contribute points independently. This relaxes skill requirements
    # for international opportunities worth pursuing.
    # Relocation-friendly companies count as both visa + relocation signals.
    visa_bonus = 0
    relo_bonus = 0
    relocation_note = ""
    company_lower = company.lower()
    for friendly_co, note in RELOCATION_FRIENDLY.items():
        if friendly_co in company_lower:
            relocation_note = note
            break
    if is_outside_india and title_relevance >= 10:
        # +5 if JD mentions visa sponsorship or company is known to sponsor
        if has_visa_sponsor or relocation_note:
            visa_bonus = 5
        # +5 if JD mentions relocation support or company is known to relocate
        if has_relo_support or relocation_note:
            relo_bonus = 5

    score = round(skill_score + title_relevance + seniority_score + visa_bonus + relo_bonus)
    score = max(0, min(100, score))
    # Combine relocation note and visa note
    notes = " | ".join(n for n in [relocation_note, visa_note] if n)
    return score, notes


def _title_only_bypass(job, score, relocation_note, threshold):
    """If description is too short to score skills but title matches well, auto-pass."""
    if score >= threshold or len(job.get("description", "")) >= 100:
        return score, relocation_note
    title_lower = job["title"].lower().replace("-", " ")
    title_keywords = _derive_title_keywords(PROFILE.get("current_role", ""), PROFILE["years_experience"])
    if title_keywords:
        base_role = title_keywords[0]
        if base_role in title_lower:
            score = max(score, 72)
            relocation_note = (relocation_note + " | " if relocation_note else "") + "Title-match pass (no full JD)"
    return score, relocation_note


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
    "cruise": {"median_tc": "$411,000", "currency": "USD", "levels": [
        {"level": "L3", "total": "$211,426"}, {"level": "L4", "total": "$314,025"},
        {"level": "L5", "total": "$403,434"}, {"level": "L6", "total": "$641,107"},
    ], "url": "https://www.levels.fyi/companies/cruise/salaries/software-engineer"},
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

    return None

def get_salary_info(company, title, description):
    """Get salary info: try JD first, fall back to static levels.fyi data."""
    jd_salary = _extract_salary_from_jd(description)
    if jd_salary:
        return {**jd_salary, "source": "jd"}

    levels_data = _get_static_levels_salary(company)
    if levels_data:
        return levels_data

    return None


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
                    "distributed systems engineer", "back-end engineer"],
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

    for title in config["titles"]:
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

def _is_within_months(date_val, months=6):
    """Check if date is within N months from now."""
    if date_val is None:
        return True  # no date = assume recent
    from datetime import timedelta
    cutoff = datetime.now(date_val.tzinfo if date_val.tzinfo else None) - timedelta(days=months*30)
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

    try:
        browser = _get_browser()
        page = browser.new_page()
        _with_stealth(page)
        page.goto(source["url"], timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        seen_urls = set()
        page_jobs = _extract_links(page)
        for j in page_jobs:
            if j["url"] not in seen_urls:
                seen_urls.add(j["url"])
                jobs.append(j)

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
                    next_btn.click()
                    page.wait_for_timeout(3000)
                    page.wait_for_selector("a", timeout=5000)
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
                            page.goto(next_url, timeout=30000, wait_until="domcontentloaded")
                            page.wait_for_timeout(3000)
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
    except Exception as e:
        pw_failed = True
        print(f"  [pw] Playwright failed for {source['name']}: {e}")
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass

    if pw_failed or not jobs:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        try:
            import requests as req
            resp = req.get(source["url"], headers=headers, timeout=15)
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
_PERSONIO_MIN_DELAY = 3.0  # minimum seconds between Personio requests


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
            global _personio_last_call
            import time as _time
            elapsed_since_last = _time.time() - _personio_last_call
            if elapsed_since_last < _PERSONIO_MIN_DELAY:
                _time.sleep(_PERSONIO_MIN_DELAY - elapsed_since_last)

            base_url = source["url"].rstrip("/").split("?")[0].rstrip("/")
            api_url = f"{base_url}/search.json"
            resp = None
            for _attempt in range(3):
                try:
                    _personio_last_call = _time.time()
                    resp = requests.get(api_url, timeout=10)
                    if resp.status_code == 429:
                        wait = 2 ** (_attempt + 1)
                        print(f"  [warn] Personio API returned 429 for {source['name']}, retrying in {wait}s...")
                        _time.sleep(wait)
                        continue
                    break
                except Exception:
                    break
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    postings = data if isinstance(data, list) else data.get("jobs", data.get("data", []))
                    for posting in postings:
                        if not isinstance(posting, dict):
                            continue
                        offices = posting.get("offices", [])
                        location = posting.get("office") or (offices[0] if offices and isinstance(offices[0], str) else "Germany")
                        # Fetch full description from individual job page (JSON-LD)
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

        elif source.get("playwright"):
            # For LinkedIn URLs, skip Playwright and use LinkedIn job search API directly
            if "linkedin.com/company/" in source["url"].lower():
                from urllib.parse import urlparse as _urlparse
                li_path = _urlparse(source["url"]).path.rstrip("/")
                company_slug = li_path.split("/company/")[-1].replace("-", " ").strip()
                locations_to_try = ["Remote"]
                region = source.get("region", "")
                if region and region not in ("Remote", "Global"):
                    locations_to_try.insert(0, region)
                queries = build_domain_queries()
                for loc in locations_to_try:
                    for q in queries[:6]:
                        try:
                            li_jobs = search_linkedin(q, location=loc, max_results=25)
                            for j in li_jobs:
                                lc = j.get("company", "").lower()
                                if company_slug in lc or any(w in lc for w in company_slug.split() if len(w) > 3):
                                    j["url"] = j.get("url") or source["url"]
                                    j["company"] = source["name"]
                                    if j not in jobs:
                                        jobs.append(j)
                        except Exception:
                            pass
                    if jobs:
                        break
                if jobs:
                    print(f"  [linkedin] {len(jobs)} jobs for {source['name']}")
                else:
                    print(f"  [linkedin] No LinkedIn jobs found for {source['name']}. Check manually: {source['url']}")
            else:
                jobs = _scrape_company_career_page(source)

        else:
            print(f"  [skip] {source['name']} - no public ATS API detected. "
                  f"Check manually: {source['url']}")
    except Exception as e:
        print(f"  [error] Failed to fetch {source['name']}: {e}")

    if not jobs and source.get("type") == "company":
        try:
            source_name_clean = re.sub(r'\s+(GmbH|AG|SE|& Co\. KG|Ltd|Limited|Inc|PLC|SA|BV|NV)($|\s|,|\()', '', source["name"]).strip().lower()
            locations_to_try = ["Remote"]
            region = source.get("region", "")
            if region and region not in ("Remote", "Global"):
                locations_to_try.insert(0, region)
            queries = build_domain_queries()
            for loc in locations_to_try:
                for q in queries[:6]:
                    try:
                        li_jobs = search_linkedin(q, location=loc, max_results=25)
                        for j in li_jobs:
                            lc = j.get("company", "").lower()
                            if source_name_clean in lc or lc in source_name_clean or any(w in lc for w in source_name_clean.split() if len(w) > 3):
                                j["url"] = j.get("url") or source["url"]
                                j["company"] = source["name"]
                                if j not in jobs:
                                    jobs.append(j)
                    except Exception:
                        pass
                if jobs:
                    break
            if jobs:
                print(f"  [linkedin] {len(jobs)} jobs for {source['name']} (fallback)")
        except Exception:
            pass
    return jobs


def search_linkedin(query, location="India", max_results=75):
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
            resp = requests.get(
                "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                params=params,
                headers=headers,
                timeout=15,
            )
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

            # Fallback patterns
            if not titles:
                titles = re.findall(r'"title":"([^"]+)"', html)
                companies = re.findall(r'"companyName":"([^"]+)"', html)
                locations = re.findall(r'"formattedLocation":"([^"]+)"', html)
                links = re.findall(r'"jobUrl":"([^"]+)"', html)

            if not titles:
                break  # No more results

            min_len = min(len(titles), len(companies), len(locations))
            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                url = links[i] if i < len(links) else ""
                # Try to fetch actual job description from the LinkedIn job page
                full_desc = ""
                if url:
                    try:
                        jd_resp = requests.get(url, headers=headers, timeout=10)
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
                desc = full_desc or f"LinkedIn job: {titles[i]} at {companies[i]} in {locations[i]}"
                jobs.append({
                    "title": titles[i].strip(),
                    "company": companies[i].strip(),
                    "location": locations[i].strip(),
                    "url": url,
                    "description": desc,
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


def search_indeed(query, location="India", max_results=50):
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

            if not titles:
                break  # No more results

            min_len = min(len(titles), len(companies), len(locations))
            for i in range(min_len):
                if len(jobs) >= max_results:
                    break
                job_url = "https://www.indeed.com" + links[i] if i < len(links) and links[i].startswith("/") else (links[i] if i < len(links) else "")
                jobs.append({
                    "title": titles[i].strip(),
                    "company": companies[i].strip() if i < len(companies) else "Unknown",
                    "location": locations[i].strip() if i < len(locations) else location,
                    "url": job_url,
                    "description": f"Indeed job: {titles[i]} at {companies[i]} in {locations[i]}",
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


def search_naukri(query, location="India", max_results=50):
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
                loc_raw = job.get("cityfield", "")
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
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location_str,
                    "url": job_url,
                    "description": f"Naukri job: {title} at {company}",
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


def search_instahyre(query, location="India", max_results=50):
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
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": job_url,
                    "description": f"Instahyre job: {title} at {company}",
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


def search_womenintech(query, location="UK", max_results=50):
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


def search_weworkremotely(query, location="Remote", max_results=25):
    """Search We Work Remotely for jobs matching a query."""
    jobs = []
    scraper = cloudscraper.create_scraper()
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    term = query.replace(" ", "+")
    try:
        resp = scraper.get(f"https://weworkremotely.com/remote-jobs/search?term={term}", headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"  [weworkremotely] HTTP {resp.status_code}")
            return jobs
        html = resp.text
        titles = re.findall(r'class="title"[^>]*>\s*([^<]+?)\s*</a>', html)
        companies = re.findall(r'class="company"[^>]*>\s*([^<]+)', html)
        links = re.findall(r'href="(/remote-jobs/[^"]+)"', html)
        min_len = min(len(titles), len(companies))
        for i in range(min(min_len, max_results)):
            t = titles[i].strip()
            if t.lower() in ("search remote jobs", "post a job", ""):
                continue
            url = f"https://weworkremotely.com{links[i]}" if i < len(links) else ""
            jobs.append({
                "title": t, "company": companies[i].strip(),
                "location": "Remote", "url": url,
                "description": f"WeWorkRemotely: {t} at {companies[i].strip()}",
            })
        if jobs:
            print(f"  [weworkremotely] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [weworkremotely] Error: {e}")
    return jobs


def search_simplyhired(query, location="India", max_results=50):
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


def search_glassdoor(query, location="India", max_results=50):
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


def _playwright_scrape(url, selector, extract_fn, wait_selector=None):
    """Generic helper to scrape JS-rendered pages using Playwright + stealth."""
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=10000)
        results = page.eval_on_selector_all(selector, extract_fn)
        context.close()
        return results
    except Exception as e:
        return []


def _playwright_load_more(url, max_clicks=5, wait_ms=2000):
    """Load a page with Playwright and click 'Load More'/'Show More' buttons
    or scroll for infinite scroll, returning the full HTML after expansion.

    Supports:
    - Buttons/links with text: Load More, Show More, More Results, View More, See More
    - Infinite scroll: scrolls to bottom and waits for new content
    """
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        for _ in range(max_clicks):
            # Try clicking "Load More" / "Show More" style buttons
            load_more_btn = page.query_selector(
                'button:has-text("Load More"), button:has-text("load more"), '
                'button:has-text("Show More"), button:has-text("show more"), '
                'button:has-text("More Results"), button:has-text("View More"), '
                'button:has-text("See More"), button:has-text("see more"), '
                'a:has-text("Load More"), a:has-text("load more"), '
                'a:has-text("Show More"), a:has-text("show more"), '
                'a:has-text("More Results"), a:has-text("View More"), '
                'a:has-text("See More"), a:has-text("see more"), '
                '[class*="load-more"], [class*="loadMore"], '
                '[class*="show-more"], [class*="showMore"], '
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

            # Fallback: infinite scroll - scroll to bottom
            prev_height = page.evaluate("document.body.scrollHeight")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(wait_ms)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                break  # No new content loaded

        html = page.content()
        context.close()
        return html
    except Exception as e:
        return ""

def _playwright_html(url, timeout=30000):
    """Load a JS-rendered page with Playwright + stealth and return full HTML."""
    try:
        browser = _get_browser()
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        _with_stealth(page)
        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        html = page.content()
        context.close()
        return html
    except Exception as e:
        return ""


def search_remoteok(query, location="Remote", max_results=50):
    """Search RemoteOK using Playwright with infinite scroll."""
    jobs = []
    term = query.replace(" ", "-").lower()
    url = f"https://remoteok.com/remote-{term}-jobs"
    try:
        # Use infinite scroll to load more results
        html = _playwright_load_more(url, max_clicks=5, wait_ms=2000)
        if not html:
            print(f"  [remoteok] No response for '{query}'")
            return jobs
        # Parse from expanded HTML
        titles = re.findall(r'itemprop="title"[^>]*>\s*([^<]{4,}?)\s*<', html)
        if not titles:
            titles = re.findall(r'class="[^"]*position[^"]*"[^>]*>\s*<h2[^>]*>\s*([^<]+)', html)
        companies = re.findall(r'itemprop="name"[^>]*>\s*([^<]{2,}?)\s*<', html)
        links = re.findall(r'href="(/remote-jobs/[^"]+)"', html)
        # Deduplicate links
        seen_links = set()
        unique_links = []
        for link in links:
            if link not in seen_links:
                seen_links.add(link)
                unique_links.append(link)
        min_len = min(len(titles), len(unique_links))
        for i in range(min(min_len, max_results)):
            jobs.append({
                "title": titles[i].strip(),
                "company": companies[i].strip() if i < len(companies) else "Unknown",
                "location": "Remote",
                "url": f"https://remoteok.com{unique_links[i]}",
                "description": f"RemoteOK: {titles[i].strip()}",
            })
        if jobs:
            print(f"  [remoteok] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [remoteok] Error: {e}")
    return jobs


def search_skipthedrive(query, location="Remote", max_results=50):
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


def search_workingnomads(query, location="Remote", max_results=50):
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
        page.goto("https://www.workingnomads.com/jobs", timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Click Load More / scroll for more results
        for _ in range(5):
            load_more = page.query_selector(
                'button:has-text("Load More"), button:has-text("Show More"), '
                'a:has-text("Load More"), a:has-text("Show More"), '
                '[class*="load-more"], [class*="loadMore"]'
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


def search_jobspresso(query, location="Remote", max_results=50):
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
                '[class*="load_more"], [class*="load-more"], '
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


def search_englishjobsearch(query, location="Remote", max_results=50):
    """Search EnglishJobSearch.ch for English-speaking jobs in Switzerland/EU (paginated).

    Uses plain HTTP + regex (the site is server-rendered, no JS needed).
    """
    jobs = []
    q = query.replace(" ", "+")
    max_pages = 3
    try:
        for page_num in range(1, max_pages + 1):
            page_url = f"https://englishjobsearch.ch/jobs/{q}?page={page_num}" if page_num > 1 else f"https://englishjobsearch.ch/jobs/{q}"
            resp = requests.get(
                page_url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"},
                timeout=15,
            )
            if resp.status_code != 200:
                if page_num == 1:
                    print(f"  [englishjobsearch] HTTP {resp.status_code}")
                break

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


def search_bulldogjob(query, location="Remote", max_results=50):
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
        page.goto(f"https://bulldogjob.pl/companies/jobs/s/skills,{q}", timeout=30000, wait_until="networkidle")
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


def search_workatstartup(query, location="Remote", max_results=50):
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


def search_stepstone(query, location="Germany", max_results=50):
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


def search_monsterde(query, location="Germany", max_results=50):
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

def build_email_html(matches):
    if not matches:
        return "<p>No new matches above threshold today. Sources checked, all clear.</p>"

    # Group matches by location
    from collections import OrderedDict
    grouped = OrderedDict()
    for m in matches:
        loc = m.get("location", "Unknown").strip() or "Unknown"
        grouped.setdefault(loc, []).append(m)

    sections = ""
    for loc, loc_matches in grouped.items():
        rows = ""
        for m in loc_matches:
            salary_line = _salary_html(m.get("salary_info"))
            rows += f"""
        <div style="border:1px solid #ddd;border-radius:8px;padding:16px;margin-bottom:12px;">
          <h3 style="margin:0 0 4px;font-size:16px;">{m['title']}</h3>
          <p style="margin:0 0 8px;color:#666;font-size:13px;">
            <a href="{m['url']}" style="color:#1a73e8;text-decoration:none;">{m['company']}</a>
          </p>
          <p style="margin:0 0 8px;font-size:14px;"><b>Fit score: {m['score']}%</b></p>
          {salary_line}
          <p style="margin:0 0 8px;font-size:13px;color:#444;">{m['relocation_note']}</p>
          <ul style="margin:0 0 8px;font-size:13px;color:#444;">
            {''.join(f'<li>{s}</li>' for s in m['suggestions'])}
          </ul>
          <a href="{m['url']}" style="font-size:13px;">Open job posting &rarr;</a>
        </div>
        """
        sections += f"""
    <div style="margin-bottom:24px;">
      <h3 style="background:#f0f4f8;padding:8px 12px;border-radius:6px;font-size:15px;">
        {loc} ({len(loc_matches)})
      </h3>
      {rows}
    </div>
    """
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;">
      <h2>Daily job matches - {datetime.now().strftime('%d %b %Y')}</h2>
      <p>{len(matches)} role(s) scored above threshold.</p>
      {sections}
    </body></html>
    """


def send_email(html_body, subject="Daily Job Matches"):
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("EMAIL_TO") or gmail_address

    if not gmail_address or not gmail_app_password:
        print("Email not sent - GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set.")
        print("See setup notes in README for how to create a Gmail App Password.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, recipient, msg.as_string())
        print(f"Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
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
    "fico", "fi module", "controlling", "cost center accounting",
    "procurement", "inventory management", "material management",
    "sap implementation", "sap support", "idoc", "bapi", "rfc",
    "oracle", "oracle erp", "oracle fusion", "peoplesoft",
    "salesforce", "microsoft dynamics", "erp",
]

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
                profile["current_role"] = line.strip()
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
        if kw in text_lower:
            found_skills.add(kw)
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
        gsheet_id = os.environ.get("GSHEET_ID") or "1NO-erkRi_aV7RSY8dMbZkxEZBA9jEN55IfIrK3S8WEg"
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


def search_remotive(query, location="Remote", max_results=50):
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
                })
            if jobs: print(f"  [remotive] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [remotive] Error: {e}")
    return jobs





def search_foundit(query, location="India", max_results=50):
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
            if not titles:
                break  # No more results
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "Unknown",
                    "location": locs[i] if i < len(locs) else location,
                    "url": "", "description": f"Foundit: {titles[i]}",
                })
            if len(jobs) >= max_results or len(titles) < page_size:
                break
            time.sleep(1)
        if jobs: print(f"  [foundit] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [foundit] Error: {e}")
    return jobs


def search_timesjobs(query, location="India", max_results=50):
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
                if t: jobs.append({"title": t, "company": c, "location": location, "url": "", "description": t})
            if len(jobs) >= max_results:
                break
            time.sleep(1)
        if jobs: print(f"  [timesjobs] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [timesjobs] Error: {e}")
    return jobs


def search_arcdev(query, location="Remote", max_results=50):
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


def search_seek(query, location="Australia", max_results=50):
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


def search_jora(query, location="Australia", max_results=50):
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
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "Jora",
                    "location": location, "url": "", "description": f"Jora AU: {titles[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs: print(f"  [jora] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [jora] Error: {e}")
    return jobs


def search_xing(query, location="Germany", max_results=50):
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


def search_jobsch(query, location="Switzerland", max_results=50):
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
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "Jobs.ch",
                    "location": location, "url": "", "description": f"Jobs.ch: {titles[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs: print(f"  [jobsch] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [jobsch] Error: {e}")
    return jobs


def search_jobsingermany(query, location="Germany", max_results=50):
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
            for i in range(len(titles)):
                if len(jobs) >= max_results:
                    break
                jobs.append({
                    "title": titles[i], "company": companies[i] if i < len(companies) else "JobsinGermany",
                    "location": location, "url": "", "description": f"JobsinGermany: {titles[i]}",
                })
            if len(jobs) >= max_results:
                break
            time.sleep(2)
        if jobs: print(f"  [jobsingermany] {len(jobs)} jobs for '{query}'")
    except Exception as e:
        print(f"  [jobsingermany] Error: {e}")
    return jobs


def search_arbeitnow(query, location="Remote", max_results=25):
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
                jobs.append({
                    "title": title,
                    "company": posting.get("company_name", ""),
                    "location": posting.get("location", location),
                    "url": posting.get("url", ""),
                    "description": f"Arbeitnow: {title} @ {posting.get('company_name', '')}",
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


def search_visasponsor(query, location="Remote", max_results=50):
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


def search_incluso(query, location="Remote", max_results=50):
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


# ---------------------------------------------------------------------------
# 7. MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Daily Job Scanner")
    parser.add_argument("--name", help="Your name (overrides PROFILE)")
    parser.add_argument("--skills", help="Comma-separated core skills (overrides PROFILE)")
    parser.add_argument("--exp", type=int, help="Years of experience (overrides PROFILE)")
    parser.add_argument("--resume", help="Path to resume PDF - auto-extracts profile")
    parser.add_argument("--email-to", help="Email recipient (overrides .env EMAIL_TO)")
    parser.add_argument("--gmail-user", help="Gmail address (overrides .env GMAIL_ADDRESS)")
    parser.add_argument("--gmail-pass", help="Gmail App Password (overrides .env)")
    parser.add_argument("--threshold", type=int, default=70, help="Match score threshold (default: 70)")
    parser.add_argument("--source-types", default="all",
                        choices=["all", "ats", "boards", "playwright"],
                        help="Which source types to scan: ats (Greenhouse/Lever/Ashby), "
                             "boards (LinkedIn/Indeed/Naukri/etc), playwright (RemoteOK/WorkingNomads/etc), "
                             "or all (default: all)")
    parser.add_argument("--email-scan-only", action="store_true",
                        help="Only scan Gmail for rejection emails (skip job scanning)")
    parser.add_argument("--batch", type=str, choices=["ats", "boards-major", "boards-niche", "playwright", "eu", "global", "apac", "us-canada", "middle-east"], default="",
                        help="Run in batches: ats=company ATS APIs, boards-major=LinkedIn/Indeed/Glassdoor etc, boards-niche=regional/niche boards, playwright=JS-rendered pages, eu/global/apac/us-canada/middle-east=region companies. Run sequentially.")
    parser.add_argument("--save", default="last_scan_results.json", help="Output JSON path")
    args = parser.parse_args()

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

    # Override .env from CLI args
    if args.resume and not args.resume.startswith("---"):  # already handled above
        pass
    if args.email_to:
        os.environ["EMAIL_TO"] = args.email_to
    if args.gmail_user:
        os.environ["GMAIL_ADDRESS"] = args.gmail_user
    if args.gmail_pass:
        os.environ["GMAIL_APP_PASSWORD"] = args.gmail_pass

    print(f"=== Daily job scan started: {datetime.now().isoformat()} ===")
    print(f"Profile: {PROFILE['name']}, {PROFILE['years_experience']}yr, {len(PROFILE['core_skills'])} skills")
    all_matches = []

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

    # Helper to check tracker before adding a match
    def should_include(job):
        if tracker.is_known(job["title"], job["company"]):
            return False
        # Skip jobs posted more than 6 months ago
        posted = job.get("posted_at")
        if posted is not None and not _is_within_months(posted, 6):
            print(f"  [skip] {job['title'][:40]}... posted {posted.strftime('%Y-%m-%d')} (>6mo)")
            return False
        return True

    if args.source_types in ("all", "ats") and (args.batch == "" or args.batch == "ats"):
        _score_debug = {"filtered": 0, "low_score": 0, "top_score": 0, "top_title": ""}
        for source in _interleave_sources(JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source['region']}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            for job in jobs:
                if not should_include(job):
                    continue
                score, relocation_note = score_job(job["title"], job["description"], job["company"])
                if score == 0:
                    _score_debug["filtered"] += 1
                elif score < args.threshold:
                    _score_debug["low_score"] += 1
                    if score > _score_debug["top_score"]:
                        _score_debug["top_score"] = score
                        _score_debug["top_title"] = f"{job['title']} @ {job['company']}"
                if score >= args.threshold:
                    print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                    resume = pick_resume(job["company"])
                    suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                    salary_info = get_salary_info(job["company"], job["title"], job["description"])
                    all_matches.append({
                        **job,
                        "score": score,
                        "resume": resume,
                        "company_url": company_url(job["company"], source.get("url")),
                        "relocation_note": relocation_note,
                        "suggestions": suggestions,
                        "salary_info": salary_info,
                    })
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")
        print(f"  [scoring-debug] Filtered: {_score_debug['filtered']}, Below threshold: {_score_debug['low_score']}, "
              f"Best non-match: {_score_debug['top_score']} ({_score_debug['top_title'][:60]})")

    # --- Web search: LinkedIn, Indeed, Naukri, Instahyre ---
    board_scrapers = [
        ("LinkedIn", search_linkedin),
        ("Indeed", search_indeed),
        ("Naukri", search_naukri),
        ("Glassdoor", search_glassdoor),
        ("SimplyHired", search_simplyhired),
        ("WeWorkRemotely", search_weworkremotely),
        ("WomenInTech", search_womenintech),
        ("Instahyre", search_instahyre),
        ("Remotive", search_remotive),

        ("Foundit", search_foundit),
        ("TimesJobs", search_timesjobs),
        ("ArcDev", search_arcdev),
        ("Seek", search_seek),
        ("Jora", search_jora),
        ("Xing", search_xing),
        ("JobsCh", search_jobsch),
        ("JobsinGermany", search_jobsingermany),
        ("Arbeitnow", search_arbeitnow),
        ("VisaSponsor", search_visasponsor),
        ("Incluso", search_incluso),
    ]
    # Split boards: boards-major = global/major boards, boards-niche = niche/regional boards
    _split = 10
    if args.batch == "boards-major":
        board_scrapers = board_scrapers[:_split]
    elif args.batch == "boards-niche":
        board_scrapers = board_scrapers[_split:]
    domain_queries = build_domain_queries()
    if args.source_types in ("all", "boards") and (args.batch == "" or args.batch in ("boards-major", "boards-niche")):
        for query in domain_queries:
            for board_name, board_fn in board_scrapers:
                au_boards = {"Seek", "Jora"}
                eu_boards = {"Xing", "JobsCh", "JobsinGermany"}
                if board_name in au_boards:
                    regions = ["Australia", "New Zealand"]
                elif board_name in eu_boards:
                    regions = ["Germany", "Switzerland", "Remote"]
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
                        score, relocation_note = score_job(job["title"], job["description"], job["company"])
                        score, relocation_note = _title_only_bypass(job, score, relocation_note, args.threshold)
                        if score >= args.threshold:
                            print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                            resume = pick_resume(job["company"])
                            suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                            salary_info = get_salary_info(job["company"], job["title"], job["description"])
                            all_matches.append({**job, "score": score, "resume": resume,
                                                "relocation_note": relocation_note, "suggestions": suggestions,
                                                "salary_info": salary_info})
                elapsed = (datetime.now() - t0).total_seconds()
                print(f"    [{board_name.lower()}] Done ({elapsed:.1f}s)")

    # --- Playwright-based scrapers (JS-rendered sites, called once not per query) ---
    is_sap_profile = any("sap" in s.lower() or "erp" in s.lower() for s in PROFILE["core_skills"][:5])
    exp = PROFILE["years_experience"]
    if is_sap_profile:
        pw_scrapers = [
            ("RemoteOK", search_remoteok),
        ]
    else:
        pw_scrapers = [
            ("RemoteOK", search_remoteok),
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
    ]
    if args.source_types in ("all", "playwright") and (args.batch == "" or args.batch == "playwright"):
        for pw_name, pw_fn in pw_scrapers:
            print(f"  [{pw_name.lower()}] Processing")
            t0 = datetime.now()
            try:
                jobs = pw_fn("", location="Remote")
                for job in jobs:
                    if not should_include(job):
                        continue
                    score, relocation_note = score_job(job["title"], job["description"], job["company"])
                    score, relocation_note = _title_only_bypass(job, score, relocation_note, args.threshold)
                    if score >= args.threshold:
                        print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                        resume = pick_resume(job["company"])
                        suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                        salary_info = get_salary_info(job["company"], job["title"], job["description"])
                        all_matches.append({**job, "score": score, "resume": resume,
                                            "relocation_note": relocation_note, "suggestions": suggestions,
                                            "salary_info": salary_info})
            except Exception as e:
                print(f"  [{pw_name.lower()}] Error: {e}")
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"    [{pw_name.lower()}] Done ({elapsed:.1f}s)")
        # Pass domain query to batch scrapers that support it
        for pw_name, pw_fn in pw_batch_scrapers:
            print(f"  [{pw_name.lower()}] Processing {len(domain_queries)} queries")
            t0 = datetime.now()
            for query in domain_queries:
                try:
                    jobs = pw_fn(query, location="Remote")
                    for job in jobs:
                        if not should_include(job):
                            continue
                        score, relocation_note = score_job(job["title"], job["description"], job["company"])
                        score, relocation_note = _title_only_bypass(job, score, relocation_note, args.threshold)
                        if score >= args.threshold:
                            print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                            resume = pick_resume(job["company"])
                            suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                            salary_info = get_salary_info(job["company"], job["title"], job["description"])
                            all_matches.append({**job, "score": score, "resume": resume,
                                                "relocation_note": relocation_note, "suggestions": suggestions,
                                                "salary_info": salary_info})
                except Exception as e:
                    print(f"  [{pw_name.lower()}] Error: {e}")
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"    [{pw_name.lower()}] Done ({elapsed:.1f}s)")

    # --- EU companies (batch: eu) ---
    if args.batch == "eu":
        for source in _interleave_sources(EU_JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source.get('region','EU')}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            for job in jobs:
                if not should_include(job):
                    continue
                score, relocation_note = score_job(job["title"], job["description"], job["company"])
                if score >= args.threshold:
                    print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                    resume = pick_resume(job["company"])
                    suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                    salary_info = get_salary_info(job["company"], job["title"], job["description"])
                    all_matches.append({
                        **job,
                        "score": score,
                        "resume": resume,
                        "company_url": company_url(job["company"], source.get("url")),
                        "relocation_note": relocation_note,
                        "suggestions": suggestions,
                        "salary_info": salary_info,
                    })
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")

    # --- Global companies / recruiters (batch: global) ---
    if args.batch == "global":
        for source in _interleave_sources(GLOBAL_JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source.get('region','Global')}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            for job in jobs:
                if not should_include(job):
                    continue
                score, relocation_note = score_job(job["title"], job["description"], job["company"])
                if score >= args.threshold:
                    print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                    resume = pick_resume(job["company"])
                    suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                    salary_info = get_salary_info(job["company"], job["title"], job["description"])
                    all_matches.append({
                        **job,
                        "score": score,
                        "resume": resume,
                        "company_url": company_url(job["company"], source.get("url")),
                        "relocation_note": relocation_note,
                        "suggestions": suggestions,
                        "salary_info": salary_info,
                    })
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")

    # --- APAC companies (batch: apac) ---
    if args.batch == "apac":
        for source in _interleave_sources(APAC_JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source.get('region','APAC')}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            for job in jobs:
                if not should_include(job):
                    continue
                score, relocation_note = score_job(job["title"], job["description"], job["company"])
                if score >= args.threshold:
                    print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                    resume = pick_resume(job["company"])
                    suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                    salary_info = get_salary_info(job["company"], job["title"], job["description"])
                    all_matches.append({
                        **job,
                        "score": score,
                        "resume": resume,
                        "company_url": company_url(job["company"], source.get("url")),
                        "relocation_note": relocation_note,
                        "suggestions": suggestions,
                        "salary_info": salary_info,
                    })
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")

    # --- US/Canada companies (batch: us-canada) ---
    if args.batch == "us-canada":
        for source in _interleave_sources(US_CANADA_JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source.get('region','US/Canada')}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            for job in jobs:
                if not should_include(job):
                    continue
                score, relocation_note = score_job(job["title"], job["description"], job["company"])
                if score >= args.threshold:
                    print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                    resume = pick_resume(job["company"])
                    suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                    salary_info = get_salary_info(job["company"], job["title"], job["description"])
                    all_matches.append({
                        **job,
                        "score": score,
                        "resume": resume,
                        "company_url": company_url(job["company"], source.get("url")),
                        "relocation_note": relocation_note,
                        "suggestions": suggestions,
                        "salary_info": salary_info,
                    })
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")

    # --- Middle East companies (batch: middle-east) ---
    if args.batch == "middle-east":
        for source in _interleave_sources(MIDDLE_EAST_JOB_SOURCES):
            print(f"Scanning: {source['name']} ({source.get('region','Middle East')}) - {source['url']}")
            t0 = datetime.now()
            jobs = fetch_jobs_from_source(source)
            for job in jobs:
                if not should_include(job):
                    continue
                score, relocation_note = score_job(job["title"], job["description"], job["company"])
                if score >= args.threshold:
                    print(f"  [match] {job['title'][:60]} @ {job['company']} (score {score})")
                    resume = pick_resume(job["company"])
                    suggestions = tailoring_suggestion(job["title"], job["description"], job["company"])
                    salary_info = get_salary_info(job["company"], job["title"], job["description"])
                    all_matches.append({
                        **job,
                        "score": score,
                        "resume": resume,
                        "company_url": company_url(job["company"], source.get("url")),
                        "relocation_note": relocation_note,
                        "suggestions": suggestions,
                        "salary_info": salary_info,
                    })
            elapsed = (datetime.now() - t0).total_seconds()
            print(f"  Done - {source['name']} ({elapsed:.1f}s, {len(jobs)} jobs)")

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
        if all_matches:
            person_name = PROFILE.get("name", "Job Seeker").split()[0].title()
            batch_labels = {
                "ats": "ATS-Company Scrape", "boards-major": "Major Job Boards",
                "boards-niche": "Niche Job Boards", "playwright": "Playwright Scrape",
                "eu": "EU Companies", "global": "Global Companies",
                "apac": "APAC Companies", "us-canada": "US-Canada Companies",
                "middle-east": "Middle East Companies",
            }
            label = batch_labels.get(args.batch, args.batch)
            subject = f"{person_name}-Job matches-{label}"
            html = build_email_html(all_matches)
            send_email(html, subject=subject)
        else:
            print(f"  [email] No matches found for resume - skipping email")

        if args.batch != "eu":
            batch_sequence = {
                "ats": "boards-major",
                "boards-major": "boards-niche",
                "boards-niche": "playwright",
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
        all_batch_ids = ["ats", "boards-major", "boards-niche", "playwright", "global", "apac", "us-canada", "middle-east", "eu"]
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

    print(f"Found {len(all_matches)} matches above {args.threshold}% threshold.")
    print(f"  [tracker] {len(tracker.data['jobs'])} total jobs tracked")

    if all_matches:
        html = build_email_html(all_matches)
        person_name = PROFILE.get("name", "Job Seeker").split()[0].title()
        batch_labels = {
            "ats": "ATS-Company Scrape", "boards-major": "Major Job Boards",
            "boards-niche": "Niche Job Boards", "playwright": "Playwright Scrape",
            "eu": "EU Companies", "global": "Global Companies",
            "apac": "APAC Companies", "us-canada": "US-Canada Companies",
            "middle-east": "Middle East Companies",
        }
        label = batch_labels.get(args.batch, "All Sources") if args.batch else "All Sources"
        send_email(html, subject=f"{person_name}-Job matches-{label}")
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
    gsheet_id = os.environ.get("GSHEET_ID") or "1NO-erkRi_aV7RSY8dMbZkxEZBA9jEN55IfIrK3S8WEg"
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
    gsheet_id = os.environ.get("GSHEET_ID") or "1NO-erkRi_aV7RSY8dMbZkxEZBA9jEN55IfIrK3S8WEg"
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
