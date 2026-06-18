# job_matcher.py
import re
from collections import Counter

# Assuming resume_data is the dictionary returned by resume_parser.py
# and job_description is a string

def calculate_match_score(resume_data: dict, job_description: str, job_url: str, job_title: str) -> float:
    """
    Calculates a simple match score based on keywords and essential criteria.
    Returns a score from 0 to 1.
    """
    score = 0.0
    total_weight = 0 # Sum of weights of all criteria considered

    print(f"Calculating match score for job: {job_title} at {job_url}")

    # --- Resume Data Keys ---
    resume_skills = {
        "languages": set(resume_data.get("skills", {}).get("languages", [])),
        "architecture": set(resume_data.get("skills", {}).get("architecture", [])),
        "cloud": set(resume_data.get("skills", {}).get("cloud", [])),
        "databases": set(resume_data.get("skills", {}).get("databases", [])),
        "ai_llm": set(resume_data.get("skills", {}).get("ai_llm", [])),
        "other_skills": set(resume_data.get("skills", {}).get("other_skills", [])) # Skills not in specific categories
    }
    resume_experience_count = len(resume_data.get("experience", []))
    resume_seniority = "Senior" in resume_data.get("name", "") or "Senior" in resume_data.get("experience", [{}])[0].get("title", "") # Simple check

    # --- Job Description Analysis ---
    job_description_lower = job_description.lower()

    # Keywords from resume to look for in job description
    keywords_to_find = set()
    for skill_list in resume_skills.values():
        keywords_to_find.update(skill_list)
    # Add seniority and experience level indicators
    keywords_to_find.add("senior backend")
    keywords_to_find.add("backend engineer")
    keywords_to_find.add("distributed systems")
    keywords_to_find.add("microservices")
    keywords_to_find.add("cloud")
    keywords_to_find.add("aws")
    keywords_to_find.add("kubernetes")
    keywords_to_find.add("java")
    keywords_to_find.add("python")
    keywords_to_find.add("node.js")
    keywords_to_find.add("ai")
    keywords_to_find.add("llm")
    keywords_to_find.add("fintech")
    keywords_to_find.add("payment")
    keywords_to_find.add("remote")
    keywords_to_find.add("visa sponsorship")
    keywords_to_find.add("relocation")
    keywords_to_find.add("europe")
    keywords_to_find.add("faang")
    keywords_to_find.add("product based")


    # Count keyword matches
    keyword_matches = 0
    for keyword in keywords_to_find:
        if keyword in job_description_lower:
            keyword_matches += 1
    
    # Weight: Give more importance to core skills and specific technologies
    # This is a simplified scoring. Real scoring would be more nuanced.
    score_weight_keyword_match = 0.4 # % of score from keyword presence
    
    if len(keywords_to_find) > 0:
        score += (keyword_matches / len(keywords_to_find)) * score_weight_keyword_match
        total_weight += score_weight_keyword_match


    # --- Specific Criteria Scoring ---
    criteria_score = 0.0
    criteria_weight_total = 1.0 - score_weight_keyword_match

    # 1. Seniority/Experience Check (Weight: 30% of the remaining criteria score)
    seniority_weight = criteria_weight_total * 0.3
    if resume_seniority: # Basic check
        if "senior" in job_title.lower() or "staff" in job_title.lower() or "lead" in job_title.lower():
            criteria_score += seniority_weight
        # print(f"Seniority check: +{seniority_weight} (Resume: {resume_seniority}, Job: {job_title})")
    total_weight += criteria_weight_total * 0.3

    # 2. Tech Stack Match (Weight: 40% of the remaining criteria score)
    tech_weight = criteria_weight_total * 0.4
    tech_keywords_in_job = set()
    for skill_category in resume_skills:
        for skill in resume_skills[skill_category]:
            if skill.lower() in job_description_lower:
                tech_keywords_in_job.add(skill.lower())
    
    if len(resume_skills.get("languages", []) + resume_skills.get("architecture", []) + resume_skills.get("cloud", [])) > 0: # if we have any tech skills to match
        match_ratio = len(tech_keywords_in_job) / len(keywords_to_find) # Rough ratio of found tech skills vs total relevant skills
        if len(tech_keywords_in_job) > 0: # Ensure we found at least one relevant tech skill
            criteria_score += tech_weight
        # print(f"Tech match (+{tech_weight}): Found {len(tech_keywords_in_job)} tech skills (out of {len(keywords_to_find) if len(keywords_to_find) > 0 else 'N/A'})")
    total_weight += criteria_weight_total * 0.4


    # 3. Remote/Location/Sponsorship Criteria (Weight: 30% of the remaining criteria score)
    location_weight = criteria_weight_total * 0.3
    location_score = 0.0
    
    # Determine job type (Remote, India, EU-specific, etc.)
    is_remote_job = "remote" in job_description_lower or "work from home" in job_description_lower or "anywhere" in job_description_lower
    is_india_job = "india" in job_description_lower or "pune" in job_description_lower or "mumbai" in job_description_lower or "bangalore" in job_description_lower
    is_eu_job = any(country.lower() in job_description_lower for country in ["germany", "netherlands", "france", "spain", "italy", "poland", "austria", "belgium", "sweden", "europe"])
    mentions_sponsorship = "visa sponsorship" in job_description_lower or "relocation" in job_description_lower or "work permit" in job_description_lower or "sponsorship" in job_description_lower # Broader check
    mentions_faang_level = "faang" in job_description_lower or "top tier" in job_description_lower or "high paying" in job_description_lower or "product based" in job_description_lower

    # Check against user's primary preference
    primary_goal_met = False
    if "europe" in job_url or "eu" in job_url or is_eu_job or (is_remote_job and not is_india_job): # Broad interpretation
        if mentions_sponsorship or "remote" in job_description_lower: # Remote implies global flexibility too
             primary_goal_met = True
             location_score += 0.5 # Higher score if it meets EU/remote/sponsorship criteria
             # print("Location: EU/Global/Remote with Sponsorship - High score")
    elif is_india_job and mentions_faang_level: # Check for FAANG-level in India
        primary_goal_met = True
        location_score += 0.5
        # print("Location: India FAANG-level - High score")
    
    # Basic check if job is clearly NOT aligned
    if not primary_goal_met:
        # If it's an India-specific role but not explicitly FAANG-level product
        if is_india_job and not mentions_faang_level:
            location_score -= 0.3 # Penalty if it's India but not FAANG target
        # If it's an EU role but no sponsorship/remote mentioned
        elif is_eu_job and not (mentions_sponsorship or is_remote_job):
            location_score -= 0.3 # Penalty if EU but no sponsorship/remote
    
    criteria_score += location_score * location_weight
    # print(f"Location score (+{location_weight*location_score}): {location_score}")
    
    total_score = score + criteria_score
    
    # Ensure score is between 0 and 1
    final_score = min(max(total_score, 0.0), 1.0)
    
    print(f"Final calculated score: {final_score:.2f}")
    return final_score

# Example Usage (requires resume_data and job_description)
if __name__ == "__main__":
    # This is a placeholder for actual resume parsing and job fetching
    # In a real scenario, you'd load resume_data from resume_parser.py
    # and job_description/job_url from job_fetcher.py
    
    # Mock resume data
    mock_resume_data = {
        "name": "Kamnee Maran",
        "contact": {"email": "kamneemaran45@gmail.com", "phone": "+91-7387233268", "linkedin": "linkedin.com/in/kamnee-maran", "github": "github.com/kamneemaran"},
        "summary": "Senior Backend Engineer with 10+ years owning distributed systems at scale...",
        "experience": [
            {"title": "Software Engineer – Backend & Distributed Systems", "dates": "Nov 2021 – Present", "company": "PhonePe Pvt Ltd", "location": "Pune, India", "responsibilities": ["Worked extensively on backend architecture, reliability...", "Eliminated a systemic reliability gap via provider-wise queue segregation (RabbitMQ) and Hystrix circuit breakers — cutting repeat provider incidents by 50–60%."]},
            {"title": "Senior Software Engineer (SDE-3)", "dates": "May 2017 – Oct 2021", "company": "Quantinsti Quantitative Pvt Ltd", "location": "Mumbai, India", "responsibilities": ["Architected Quantra from scratch...", "Built a browser-based coding environment..."]}
        ],
        "education": [{"degree": "B.Tech", "field": "Information Technology", "institution": "IIIT Allahabad", "dates": "Jul 2011 – May 2015"}],
        "skills": {
            "languages": ["Java", "Python", "Node.js"],
            "architecture": ["Distributed Systems", "System Design", "Microservices", "Event-Driven Architecture", "Async Processing", "High Availability", "Fault Tolerance", "Resilience Engineering"],
            "cloud": ["AWS", "Docker", "Kubernetes", "CI/CD", "SQS"],
            "databases": ["MySQL", "MongoDB", "Redis", "Elasticsearch"],
            "ai_llm": ["OpenAI API", "Gemini API", "AI-Assisted Tooling"],
            "other_skills": ["Dropwizard", "Jupyter Notebook Integration", "Circuit Breaker (Hystrix)", "Rate Limiting", "Observability", "Alerting", "RCA", "Incident Management"]
        }
    }
    
    # Mock job descriptions
    job_desc_1 = """
    Senior Backend Engineer (Remote, Visa Sponsorship)
    We are looking for a Senior Backend Engineer with experience in distributed systems and cloud platforms.
    Must have expertise in Java, Python, Node.js, AWS, Kubernetes, and Kafka.
    Experience with microservices and building scalable applications is essential.
    Competitive salary and full relocation support provided.
    """
    job_title_1 = "Senior Backend Engineer"
    job_url_1 = "https://example.com/jobs/remote-senior-backend"

    job_desc_2 = """
    Backend Engineer (Pune, India)
    Join a fast-growing product-based company in Pune. We need a Backend Engineer with strong Python skills
    to work on our core platform. Experience with Django or Flask preferred.
    Must be a graduate from a top Indian university.
    """
    job_title_2 = "Backend Engineer"
    job_url_2 = "https://example.com/jobs/india-backend-pune"
    
    job_desc_3 = """
    Platform Engineer - Fintech (Germany, Visa Sponsorship)
    We are a leading fintech company"""
    job_title_3 = "Platform Engineer - Fintech"
    job_url_3 = "https://example.com/jobs/germany-fintech-platform"


    # Calculate scores for mock jobs
    score1 = calculate_match_score(mock_resume_data, job_desc_1, job_url_1, job_title_1)
    score2 = calculate_match_score(mock_resume_data, job_desc_2, job_url_2, job_title_2)
    score3 = calculate_match_score(mock_resume_data, job_desc_3, job_url_3, job_title_3)

    print(f"\n--- Mock Scores ---")
    print(f"{job_title_1}: {score1:.2f}")
    print(f"{job_title_2}: {score2:.2f}")
    print(f"{job_title_3}: {score3:.2f}")
