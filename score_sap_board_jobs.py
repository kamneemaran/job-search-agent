"""
Score SAP job boards results against Pradeep's profile
"""

import json
import sys
sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')

from daily_scan import score_job

def score_sap_board_jobs():
    """Load and score SAP board jobs for Pradeep"""
    
    # Load jobs
    with open('/Users/kamnee.maran/Downloads/job-search-agent/pradeep_sap_job_boards.json', 'r') as f:
        jobs = json.load(f)
    
    print(f"📊 Scoring {len(jobs)} SAP board jobs for Pradeep...")
    
    scored_jobs = []
    
    for job in jobs:
        # Score using daily_scan function
        title = job['title']
        description = f"{job['title']} at {job['company']} in {job['location']}"
        company = job['company']
        location = job['location']
        
        score, note = score_job(title, description, company, location)
        
        job['score'] = score
        job['score_note'] = note
        scored_jobs.append(job)
    
    # Sort by score
    scored_jobs.sort(key=lambda x: x['score'], reverse=True)
    
    # Filter by quality tiers
    high_quality = [j for j in scored_jobs if j['score'] >= 60]
    perfect = [j for j in scored_jobs if j['score'] >= 90]
    good = [j for j in scored_jobs if 70 <= j['score'] < 90]
    moderate = [j for j in scored_jobs if 60 <= j['score'] < 70]
    filtered = [j for j in scored_jobs if j['score'] < 60]
    
    print(f"\n✅ Scored Results:")
    print(f"  Perfect matches (90-100): {len(perfect)}")
    print(f"  Good matches (70-89): {len(good)}")
    print(f"  Moderate (60-69): {len(moderate)}")
    print(f"  High-quality total (60+): {len(high_quality)}")
    print(f"  Filtered out (<60): {len(filtered)}")
    
    # Save all scored jobs
    output_file = '/Users/kamnee.maran/Downloads/job-search-agent/pradeep_sap_board_jobs_scored.json'
    with open(output_file, 'w') as f:
        json.dump(scored_jobs, f, indent=2)
    
    print(f"\n💾 Saved all {len(scored_jobs)} scored jobs to: {output_file}")
    
    # Save high-quality only
    if high_quality:
        hq_file = '/Users/kamnee.maran/Downloads/job-search-agent/pradeep_sap_board_jobs_high_quality.json'
        with open(hq_file, 'w') as f:
            json.dump(high_quality, f, indent=2)
        print(f"💾 Saved {len(high_quality)} high-quality jobs to: {hq_file}")
    
    # Print top 15
    print(f"\n🏆 Top 15 Scored Jobs:")
    print("-" * 100)
    for i, job in enumerate(scored_jobs[:15], 1):
        print(f"{i}. [{job['score']}%] {job['title']}")
        print(f"   Company: {job['company']} | Location: {job['location']}")
        print(f"   Source: {job['source']}")
        print(f"   Note: {job['score_note']}")
        print(f"   URL: {job['url']}")
        print()
    
    return scored_jobs, high_quality

if __name__ == "__main__":
    all_scored, high_quality = score_sap_board_jobs()
