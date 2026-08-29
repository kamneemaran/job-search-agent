"""
Combine and Score All SAP Jobs
================================
Combine SAP Jobs Board + Indeed + Recruitment Agency results
Score against Pradeep's profile and send email digest
"""

import json
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import os
from dotenv import load_dotenv

sys.path.insert(0, '/Users/kamnee.maran/Downloads/job-search-agent')
from daily_scan import score_job

load_dotenv()

def load_all_jobs():
    """Load all SAP job sources"""
    all_jobs = []
    
    # Load SAP job boards
    try:
        with open('/Users/kamnee.maran/Downloads/job-search-agent/pradeep_sap_job_boards.json', 'r') as f:
            sap_board_jobs = json.load(f)
            all_jobs.extend(sap_board_jobs)
            print(f"✅ Loaded {len(sap_board_jobs)} from SAP Job Boards")
    except:
        print("⚠️  Could not load SAP Job Boards")
    
    # Load recruitment agency jobs
    try:
        with open('/Users/kamnee.maran/Downloads/job-search-agent/pradeep_recruitment_agencies_sap_jobs.json', 'r') as f:
            recruit_jobs = json.load(f)
            all_jobs.extend(recruit_jobs)
            print(f"✅ Loaded {len(recruit_jobs)} from Recruitment Agencies")
    except:
        print("⚠️  Could not load Recruitment Agency jobs")
    
    return all_jobs


def score_jobs(jobs):
    """Score all jobs against Pradeep's profile"""
    print(f"\n📊 Scoring {len(jobs)} total jobs...")
    
    scored_jobs = []
    
    for job in jobs:
        title = job.get('title', '')
        description = f"{title} at {job.get('company', '')} in {job.get('location', '')}"
        company = job.get('company', '')
        location = job.get('location', '')
        
        score, note = score_job(title, description, company, location)
        
        job['score'] = score
        job['score_note'] = note
        scored_jobs.append(job)
    
    # Sort by score descending
    scored_jobs.sort(key=lambda x: x['score'], reverse=True)
    
    # Statistics
    perfect = [j for j in scored_jobs if j['score'] >= 90]
    good = [j for j in scored_jobs if 70 <= j['score'] < 90]
    moderate = [j for j in scored_jobs if 60 <= j['score'] < 70]
    filtered = [j for j in scored_jobs if j['score'] < 60]
    
    print(f"  Perfect (90-100%): {len(perfect)}")
    print(f"  Good (70-89%): {len(good)}")
    print(f"  Moderate (60-69%): {len(moderate)}")
    print(f"  Filtered (<60%): {len(filtered)}")
    
    return scored_jobs


def create_email_body(scored_jobs):
    """Create HTML email body with job listings"""
    
    high_quality = [j for j in scored_jobs if j['score'] >= 60]
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
            .summary {{ background: #f0f4f8; padding: 15px; margin: 15px 0; border-left: 4px solid #667eea; }}
            .job-card {{ background: white; border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .job-title {{ font-size: 16px; font-weight: bold; color: #667eea; }}
            .job-company {{ color: #666; font-size: 14px; }}
            .job-score {{ display: inline-block; background: #667eea; color: white; padding: 5px 10px; border-radius: 20px; font-weight: bold; margin-left: 10px; }}
            .job-url {{ color: #667eea; text-decoration: none; word-break: break-all; }}
            .section-title {{ font-size: 18px; font-weight: bold; color: #667eea; margin-top: 20px; margin-bottom: 10px; border-bottom: 2px solid #667eea; padding-bottom: 5px; }}
            .stats {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; margin: 15px 0; }}
            .stat-box {{ background: white; padding: 15px; border: 1px solid #ddd; text-align: center; border-radius: 5px; }}
            .stat-number {{ font-size: 24px; font-weight: bold; color: #667eea; }}
            .stat-label {{ font-size: 12px; color: #666; }}
            .footer {{ background: #f0f4f8; padding: 15px; text-align: center; font-size: 12px; color: #666; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎯 SAP MM/EWM Job Opportunities for Pradeep</h1>
            <p>Fresh SAP Job Board & Recruitment Agency Listings</p>
            <p>{datetime.now().strftime('%B %d, %Y')}</p>
        </div>
        
        <div class="summary">
            <h2>📊 Summary</h2>
            <p>Hi Pradeep,</p>
            <p>We found <strong>{len(scored_jobs)} total SAP job listings</strong> from multiple sources (SAP Jobs Board, Indeed, Recruitment Agencies).</p>
            <p>Below are the <strong>{len(high_quality)} high-quality matches (Score 60%+)</strong> for your 8-year SAP MM/EWM profile.</p>
        </div>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{len([j for j in scored_jobs if j['score'] >= 90])}</div>
                <div class="stat-label">Perfect (90-100%)</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len([j for j in scored_jobs if 70 <= j['score'] < 90])}</div>
                <div class="stat-label">Good (70-89%)</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len([j for j in scored_jobs if 60 <= j['score'] < 70])}</div>
                <div class="stat-label">Moderate (60-69%)</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{len([j for j in scored_jobs if j['score'] < 60])}</div>
                <div class="stat-label">Filtered (<60%)</div>
            </div>
        </div>
        
        <div class="section-title">🏆 Top Matching Jobs</div>
    """
    
    # Add high-quality jobs
    if high_quality:
        for i, job in enumerate(high_quality[:20], 1):  # Top 20
            score_color = "#28a745" if job['score'] >= 90 else "#ffc107" if job['score'] >= 70 else "#fd7e14"
            html += f"""
            <div class="job-card">
                <div class="job-title">
                    {i}. {job['title']}
                    <span class="job-score" style="background: {score_color};">{job['score']}%</span>
                </div>
                <div class="job-company">
                    <strong>Company:</strong> {job['company']} | 
                    <strong>Location:</strong> {job['location']} | 
                    <strong>Source:</strong> {job['source']}
                </div>
                <div style="margin-top: 10px; font-size: 12px; color: #666;">
                    <strong>Note:</strong> {job.get('score_note', 'No additional notes')}
                </div>
                <div style="margin-top: 10px;">
                    <a href="{job['url']}" class="job-url" target="_blank">View Job →</a>
                </div>
            </div>
            """
    else:
        html += "<p>No high-quality matches found at this time.</p>"
    
    html += f"""
        <div class="section-title">📈 What's Next?</div>
        <div style="background: #f0f4f8; padding: 15px; border-radius: 5px;">
            <ol>
                <li><strong>Start with Perfect Matches (90%+)</strong> - These are the closest fit to your profile</li>
                <li><strong>Contact Recruitment Agencies</strong> - They often have exclusive SAP MM placements not posted publicly</li>
                <li><strong>Check Company Career Pages</strong> - Apply directly: Siemens, VW, Nestlé, DHL, BMW, BASF</li>
                <li><strong>Consider Visa Strategy</strong> - Most European companies sponsor visas for senior SAP MM roles (85-95% likelihood)</li>
            </ol>
        </div>
        
        <div class="footer">
            <p>Job Search Agent | Pradeep SAP MM/EWM Profile</p>
            <p>Generated on {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    """
    
    return html


def send_email(html_body, recipient_email):
    """Send email digest to Pradeep"""
    
    sender_email = os.getenv('GMAIL_ADDRESS')
    app_password = os.getenv('GMAIL_APP_PASSWORD')
    
    if not sender_email or not app_password:
        print("❌ Email credentials not found in .env")
        return False
    
    try:
        print(f"\n📧 Sending email to {recipient_email}...")
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "🎯 SAP MM/EWM Job Opportunities - Latest Board Results"
        msg['From'] = sender_email
        msg['To'] = recipient_email
        
        # Attach HTML
        part = MIMEText(html_body, 'html')
        msg.attach(part)
        
        # Send email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        
        print(f"✅ Email sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def main():
    print("=" * 80)
    print("SAP Jobs - Combined Scoring & Email Digest")
    print("=" * 80)
    
    # Load all jobs
    all_jobs = load_all_jobs()
    print(f"\n📂 Loaded {len(all_jobs)} total jobs from all sources")
    
    # Score jobs
    scored_jobs = score_jobs(all_jobs)
    
    # Save combined results
    combined_file = '/Users/kamnee.maran/Downloads/job-search-agent/pradeep_sap_all_sources_combined.json'
    with open(combined_file, 'w') as f:
        json.dump(scored_jobs, f, indent=2)
    print(f"\n💾 Saved combined results to: {combined_file}")
    
    # Create email body
    print("\n📧 Creating email digest...")
    html_body = create_email_body(scored_jobs)
    
    # Send email
    pradeep_email = "pradeepmeena13@gmail.com"
    send_email(html_body, pradeep_email)
    
    # Also save email HTML for reference
    email_file = '/Users/kamnee.maran/Downloads/job-search-agent/pradeep_sap_jobs_email.html'
    with open(email_file, 'w') as f:
        f.write(html_body)
    print(f"💾 Saved email HTML to: {email_file}")
    
    print("\n" + "=" * 80)
    print("✅ Complete! Email sent to Pradeep with SAP job listings")
    print("=" * 80)


if __name__ == "__main__":
    main()
