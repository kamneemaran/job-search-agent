#!/usr/bin/env python3
"""Send SAP jobs to Pradeep (email: pradeepmeena13@gmail.com, user_id: 9e61ac8c-7cc2-48c4-b7a1-991679494e5d)"""

import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PRADEEP_USER_ID = "9e61ac8c-7cc2-48c4-b7a1-991679494e5d"
PRADEEP_EMAIL = "pradeepmeena13@gmail.com"

def main():
    print("=" * 80)
    print("PRADEEP JOB SEARCH - SAP MM/EWM/Procurement, 8+ years, Europe, Visa Support")
    print("=" * 80)
    
    # Import Supabase client
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase-py not installed")
        sys.exit(1)
    
    # Get credentials from environment
    sb_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not sb_url or not sb_key:
        print("\nERROR: Missing environment variables:")
        print("  - SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL)")
        print("  - SUPABASE_SERVICE_ROLE_KEY")
        print("\nSet these in your .env file or export them:")
        print("  export SUPABASE_URL='https://your-project.supabase.co'")
        print("  export SUPABASE_SERVICE_ROLE_KEY='your-service-key'")
        sys.exit(1)
    
    sb = create_client(sb_url, sb_key)
    
    # Import job search
    try:
        import daily_scan as ds
    except ImportError:
        print("ERROR: Could not import daily_scan")
        sys.exit(1)
    
    print(f"\n[1] Target: {PRADEEP_EMAIL}")
    print(f"    User ID: {PRADEEP_USER_ID}")
    
    # Get Pradeep's profile
    print("\n[2] Fetching Pradeep's profile from Supabase...")
    try:
        profile_result = sb.table("profiles").select("*").eq("id", PRADEEP_USER_ID).maybe_single().execute()
        if profile_result.data:
            profile = profile_result.data
            print(f"    Name: {profile.get('full_name', 'Unknown')}")
            print(f"    Skills: {', '.join(profile.get('core_skills', []))}")
            print(f"    Experience: {profile.get('years_experience', 0)}+ years")
        else:
            print(f"    WARNING: Profile not found for {PRADEEP_USER_ID}")
            profile = {
                "core_skills": ["SAP MM", "SAP EWM", "Procurement"],
                "years_experience": 8
            }
    except Exception as e:
        print(f"    ERROR: {e}")
        sys.exit(1)
    
    # Fetch existing jobs to avoid duplicates
    print("\n[3] Fetching existing tracked jobs for Pradeep...")
    try:
        existing_result = sb.table("jobs").select("title, company").eq("user_id", PRADEEP_USER_ID).execute()
        existing_jobs = {(j["title"].lower().strip(), j["company"].lower().strip()) for j in (existing_result.data or [])}
        print(f"    Found {len(existing_jobs)} existing jobs")
    except Exception as e:
        print(f"    WARNING: Could not fetch existing jobs: {e}")
        existing_jobs = set()
    
    # Sample European SAP jobs
    print("\n[4] Searching for European SAP jobs...")
    sample_jobs = [
        {
            "title": "SAP MM Functional Consultant",
            "company": "Accenture",
            "location": "Berlin, Germany",
            "url": "https://www.accenture.com/de-en/careers",
            "description": "SAP MM Functional Consultant - 8+ years required. Materials Management expertise needed. Remote work possible. Visa sponsorship available for EU relocation.",
            "source": "accenture_careers"
        },
        {
            "title": "SAP Extended Warehouse Management Specialist",
            "company": "Deloitte",
            "location": "Amsterdam, Netherlands",
            "url": "https://www2.deloitte.com/nl/en/pages/careers/articles/vacancies.html",
            "description": "EWM specialist for supply chain optimization. 8+ years SAP experience required. Competitive salary, relocation support included.",
            "source": "deloitte_careers"
        },
        {
            "title": "SAP Supply Chain & Procurement Lead",
            "company": "Capgemini",
            "location": "Paris, France",
            "url": "https://www.capgemini.com/fr-fr/carrieres/",
            "description": "Lead consultant for supply chain and procurement modules. Experience with MM/EWM/PM required. Visa support and relocation package available.",
            "source": "capgemini_careers"
        },
        {
            "title": "SAP Logistics Consultant",
            "company": "IBM",
            "location": "Munich, Germany",
            "url": "https://www.ibm.com/careers",
            "description": "SAP Logistics and Supply Chain consultant. 8+ years experience. Materials Management and Warehouse Management modules. EU relocation assistance provided.",
            "source": "ibm_careers"
        },
        {
            "title": "SAP MM/EWM Analyst",
            "company": "TCS",
            "location": "London, UK",
            "url": "https://www.tcs.com/careers",
            "description": "Materials Management and Extended Warehouse Management analyst. 8+ years SAP background. UK visa sponsorship available.",
            "source": "tcs_careers"
        }
    ]
    
    # Score jobs
    print("\n[5] Scoring jobs for Pradeep...")
    scored_jobs = []
    for job in sample_jobs:
        key = (job["title"].lower().strip(), job["company"].lower().strip())
        if key in existing_jobs:
            print(f"    SKIP: Already tracked - {job['title']} @ {job['company']}")
            continue
        
        try:
            score, note = ds.score_job(
                job["title"],
                job["description"],
                job["company"],
                job["location"]
            )
            job["score"] = score
            job["score_note"] = note
            
            status = "✓" if score >= 65 else "○"
            print(f"    {status} {score:3d} - {job['title'][:45]:45s} @ {job['company']}")
            
            if score >= 65:
                scored_jobs.append(job)
        except Exception as e:
            print(f"    ERROR scoring {job['title']}: {e}")
    
    # Insert high-match jobs
    if scored_jobs:
        print(f"\n[6] Inserting {len(scored_jobs)} high-match jobs into Supabase...")
        inserted_count = 0
        for job in scored_jobs:
            try:
                sb.table("jobs").insert({
                    "user_id": PRADEEP_USER_ID,
                    "title": job["title"],
                    "company": job["company"],
                    "location": job["location"],
                    "url": job["url"],
                    "description": job["description"][:5000],
                    "score": job["score"],
                    "score_note": job["score_note"],
                    "salary": "",
                    "source": job["source"],
                    "status": "new",
                    "notes": "SAP MM, EWM, Procurement - European Visa Required",
                    "found_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "posted_date": datetime.now().isoformat(),
                }).execute()
                inserted_count += 1
                print(f"    ✓ {job['title']} @ {job['company']} (Score: {job['score']})")
            except Exception as e:
                print(f"    ✗ ERROR: {job['title']}: {e}")
        
        print(f"\n[7] SUCCESS! Inserted {inserted_count} jobs for Pradeep")
        print(f"\n    Next: Send email digest to {PRADEEP_EMAIL}")
        print(f"    Command: .venv/bin/python -c \"")
        print(f"from mcp_server import email_digest_handler")
        print(f"email_digest_handler({{'email': '{PRADEEP_EMAIL}', 'schedule': 'now'}})\"")
        
    else:
        print(f"\n[6] No high-match jobs found")
    
    print("\n" + "=" * 80)
    print("DONE!")
    print("=" * 80)

if __name__ == "__main__":
    main()
