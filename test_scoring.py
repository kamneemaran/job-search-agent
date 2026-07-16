import sys
import re
import daily_scan

# Define clean profiles for testing
KAMNEE_PROFILE = {
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
        "fastapi", "grpc", "helm", "prometheus", "grafana", "gpu",
    ],
    "current_role": "Senior Software Engineer",
    "seniority_keywords": ["senior", "staff", "lead", "principal", "sde-3", "sde 3"],
    "junior_red_flags": ["junior", "intern", "entry level", "graduate", "0-2 years"],
    "title_red_flags": [
        "network engineer", "network architect", "network administrator", "network security",
        "devops engineer", "devops", "site reliability engineer", "sre", "network infrastructure",
        "product manager", "program manager", "project manager", "product owner",
        "engineering manager", "manager, engineering", "director of engineering",
        "recruiter", "talent acquisition", "hr ", "data scientist", "data analyst",
        "data engineer", "machine learning engineer", "ml engineer", "ai engineer"
    ]
}

PRADEEP_PROFILE = {
    "name": "Pradeep",
    "years_experience": 7,
    "core_skills": [
        "sap", "sap mm", "sap ewm", "sap wm", "sap s/4hana", "sap s4hana",
        "materials management", "warehouse management", "extended warehouse management",
        "inventory management", "procure to pay", "p2p", "logistics", "supply chain",
        "integration", "idoc", "edi", "rfid", "abap", "debugging", "configuration",
        "functional specifications", "implementation", "support"
    ],
    "current_role": "SAP MM Consultant",
    "seniority_keywords": ["senior", "staff", "lead", "principal", "manager", "architect"],
    "junior_red_flags": ["junior", "intern", "entry level", "graduate", "associate"],
    "title_red_flags": [
        "sap sd", "sap fi", "sap co", "sap hcm", "sap pp", "sap fico",
        "developer", "programmer", "recruiter", "sales", "marketing"
    ]
}

def run_tests():
    test_cases = [
        # --- KAMNEE TEST CASES ---
        {
            "profile": "Kamnee",
            "title": "Senior Backend Engineer (Python)",
            "company": "Paylogic",
            "description": "Senior Backend Engineer (Python) at Paylogic. Seniority: senior, Work mode: N/A, Functions: N/A. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 75,
            "max_score": 95,
            "expect_match": True,
            "label": "Kamnee - Senior Backend with Python match (Thin JD with Visa/Relo)"
        },
        {
            "profile": "Kamnee",
            "title": "Senior Backend Engineer",
            "company": "Polarsteps",
            "description": "Senior Backend Engineer at Polarsteps. Seniority: senior, Work mode: N/A, Functions: N/A. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 70,
            "max_score": 80,
            "expect_match": True,
            "label": "Kamnee - Generic Senior Backend (Thin JD with Visa/Relo)"
        },
        {
            "profile": "Kamnee",
            "title": "Senior Software Engineer, AI Agents",
            "company": "DataSnipper",
            "description": "Senior Software Engineer, AI Agents at DataSnipper. Seniority: senior, Work mode: N/A, Functions: N/A. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 70,
            "max_score": 80,
            "expect_match": True,
            "label": "Kamnee - Senior AI Agents without specific backend stack (Punctuation comma-split check)"
        },
        {
            "profile": "Kamnee",
            "title": "Backend Developer Customer Data Platform",
            "company": "GUTS Tickets",
            "description": "Backend Developer Customer Data Platform at GUTS Tickets. Seniority: N/A, Work mode: N/A, Functions: N/A. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 65,
            "max_score": 75,
            "expect_match": True,
            "label": "Kamnee - Mid-level Backend (no senior keyword, thin JD)"
        },
        {
            "profile": "Kamnee",
            "title": "Junior Backend Developer",
            "company": "Mollie",
            "description": "Junior Backend Developer with Java experience.",
            "location": "Netherlands",
            "min_score": 0,
            "max_score": 0,
            "expect_match": False,
            "label": "Kamnee - Junior Red Flag hard filter"
        },
        
        # --- PRADEEP TEST CASES ---
        {
            "profile": "Pradeep",
            "title": "SAP MM Consultant",
            "company": "ASML",
            "description": "SAP MM Consultant at ASML. Seniority: senior, Work mode: N/A, Functions: N/A. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 70,
            "max_score": 100,
            "expect_match": True,
            "label": "Pradeep - Exact SAP MM Title Match (Thin JD with Visa/Relo)"
        },
        {
            "profile": "Pradeep",
            "title": "SAP FICO Consultant",
            "company": "Belsimpel",
            "description": "SAP FICO Consultant with Financial Accounting experience.",
            "location": "Netherlands",
            "min_score": 0,
            "max_score": 0,
            "expect_match": False,
            "label": "Pradeep - SAP Module Mismatch (FICO vs MM/EWM)"
        },
        {
            "profile": "Pradeep",
            "title": "SAP Treasury Risk Management",
            "company": "Accenture",
            "description": "SAP Treasury Risk Management Consultant with TRM experience. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 0,
            "max_score": 0,
            "expect_match": False,
            "label": "Pradeep - SAP Module Mismatch (Treasury/TRM)"
        },
        {
            "profile": "Pradeep",
            "title": "SAP S/4HANA (Senior) Manager Order to Cash",
            "company": "EY",
            "description": "SAP S/4HANA (Senior) Manager Order to Cash (SD) Consultant. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 0,
            "max_score": 0,
            "expect_match": False,
            "label": "Pradeep - SAP Module Mismatch (Order to Cash/SD on S/4HANA)"
        },
        {
            "profile": "Pradeep",
            "title": "Team Lead Freight Forwarder",
            "company": "DSV",
            "description": "Freight forwarding team lead. Logistics and warehouse operations.",
            "location": "Netherlands",
            "min_score": 0,
            "max_score": 0,
            "expect_match": False,
            "label": "Pradeep - Non-SAP Role Filter (Freight Forwarder Logistics)"
        },
        {
            "profile": "Pradeep",
            "title": "Manager SAP S/4HANA Service",
            "company": "Deloitte",
            "description": "Manager SAP S/4HANA Customer Service consultant. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 0,
            "max_score": 0,
            "expect_match": False,
            "label": "Pradeep - SAP Module Mismatch (Service)"
        },
        {
            "profile": "Pradeep",
            "title": "SAP S/4HANA - Cloud Public Edition Manager",
            "company": "EY",
            "description": "SAP S/4HANA - Cloud Public Edition Manager. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 0,
            "max_score": 0,
            "expect_match": False,
            "label": "Pradeep - SAP Module Mismatch (Cloud Public Edition)"
        },
        {
            "profile": "Pradeep",
            "title": "(Senior) Manager SAP Procurement",
            "company": "Deloitte",
            "description": "(Senior) Manager SAP Procurement. Must have SAP MM / Sourcing & Procurement experience. Visa sponsorship and relocation support available.",
            "location": "Netherlands",
            "min_score": 75,
            "max_score": 100,
            "expect_match": True,
            "label": "Pradeep - SAP Procurement Match (SAP MM)"
        }
    ]

    failed = 0
    passed = 0

    print("=" * 80)
    print("RUNNING JOB SCAN SCORING VALIDATION SUITE")
    print("=" * 80)

    for i, tc in enumerate(test_cases, 1):
        print(f"\nTest {i}: {tc['label']}")
        
        # 1. Mutate global PROFILE
        if tc["profile"] == "Kamnee":
            for k, v in KAMNEE_PROFILE.items():
                daily_scan.PROFILE[k] = v
        else:
            for k, v in PRADEEP_PROFILE.items():
                daily_scan.PROFILE[k] = v
                
        # 2. Rebuild precompiled regex patterns
        daily_scan._rebuild_precompiled_patterns()
        
        # 3. Execute score_job
        score, note = daily_scan.score_job(tc["title"], tc["description"], tc["company"], tc["location"])
        
        # 4. Assert correctness
        in_range = tc["min_score"] <= score <= tc["max_score"]
        is_match = score >= 70
        match_correct = is_match == tc["expect_match"]
        
        if in_range and match_correct:
            print(f"  --> PASSED: Score = {score} ({note})")
            passed += 1
        else:
            print(f"  --> FAILED:")
            print(f"      Got Score  = {score}")
            print(f"      Got Note   = {note}")
            print(f"      Expected Range = [{tc['min_score']}, {tc['max_score']}] (Matched expectation? {tc['expect_match']})")
            failed += 1

    print("\n" + "=" * 80)
    print(f"VALIDATION COMPLETED: {passed} PASSED, {failed} FAILED")
    print("=" * 80)

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    run_tests()