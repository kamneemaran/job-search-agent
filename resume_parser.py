# resume_parser.py
import json
import re
import os # Needed for load_resume to check file existence

# For actual PDF/DOCX parsing, you'd need libraries like:
# import PyPDF2
# from docx import Document

def parse_resume_string(resume_text: str) -> dict:
    """
    Parses resume text directly from a string to extract key information.
    This is a simplified example assuming a structured text format.
    A real-world parser would need more advanced NLP or specific format handling.
    """
    print("Parsing resume string...")
    parsed_data = {
        "name": "N/A",
        "contact": {"email": None, "phone": None, "linkedin": None, "github": None},
        "summary": "N/A",
        "experience": [], # List of job dictionaries
        "education": [],  # List of education dictionaries
        "skills": {"languages": [], "architecture": [], "cloud": [], "databases": [], "ai_llm": [], "other": []}
    }

    # --- Simplified Parsing Logic (Illustrative) ---
    # In a real application, you'd use regex, NLP libraries (like spaCy),
    # or specific parsers for different file formats.

    lines = resume_text.split('\n')
    current_section = None
    current_job = None
    job_entry_start_line = -1 # To help distinguish between job title and company/location

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Detect sections
        if line.startswith("PROFESSIONAL SUMMARY"):
            current_section = "summary"
            continue
        elif line.startswith("PROFESSIONAL EXPERIENCE"):
            current_section = "experience"
            continue
        elif line.startswith("EDUCATION"):
            current_section = "education"
            continue
        elif line.startswith("TECHNICAL SKILLS"):
            current_section = "skills"
            continue
        
        # Process based on current section
        if current_section == "summary":
            if not line.startswith("PROFESSIONAL EXPERIENCE"): # Stop when next section starts
                parsed_data["summary"] += " " + line
        
        elif current_section == "experience":
            # Detect start of a new job entry
            # A new job entry often starts with a title, followed by dates e.g., "Nov 2021 – Present"
            # Or it might start with a "Senior Software Engineer..." title before dates.
            # We'll use a heuristic: a line with '–' and containing months/years or 'Present' is often a date range.
            # Or a line starting with a common job title pattern.
            
            is_date_line = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s*–\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|\d{4}|Present', line)
            is_new_job_title_line = re.match(r'^(Software Engineer|Senior Software Engineer|Data Engineer|Platform Engineer)\s*–', line)
            
            if is_date_line or is_new_job_title_line:
                if current_job: # Save the previous job if it exists
                    parsed_data["experience"].append(current_job)
                
                # Reset current job details
                current_job = {"title": "", "dates": "", "company": "", "location": "", "responsibilities": []}
                job_entry_start_line = i # Mark the start of this job entry

                # Attempt to parse title, dates from this line
                # This needs careful regex or string splitting, depending on format
                # Example: "Senior Backend Engineer | Distributed Systems | Fintech Platform Architecture" -> Title is first part
                if '|' in line and is_new_job_title_line: # Common format
                    current_job["title"] = line.split('|')[0].strip()
                    # Need to find dates on the *same* line or next, this is complex
                elif is_new_job_title_line:
                     current_job["title"] = line.split('–')[0].strip() # Guessing title is before the date dash

                # More robust date parsing would be needed
                # This is just a placeholder for a complex task.
                # We'll try to capture the *full line* as dates if it looks like it
                if is_date_line:
                    current_job["dates"] = line

            elif current_job and i == job_entry_start_line + 1: # Assume next line is company and location
                # This is a very simplified heuristic.
                # It works for "PhonePe Pvt Ltd Pune, India"
                parts = line.split(' Pune, India')
                if len(parts) == 2:
                    current_job["company"] = parts[0].strip()
                    current_job["location"] = "Pune, India"
                else: # Try to split by common separators if 'Pune, India' isn't there
                    parts = line.split(',')
                    if len(parts) > 1:
                        current_job["company"] = parts[0].strip()
                        current_job["location"] = ','.join(parts[1:]).strip()
                    else:
                        current_job["company"] = line # Fallback if no clear separators

            elif line.startswith("•"): # Bullet points for responsibilities
                if current_job:
                    current_job["responsibilities"].append(line[1:].strip())
            
            # If we're still within the 'experience' section and have a current_job,
            # and it's not a date line, not a bullet, and not the company/location line,
            # it might be a responsibility or an empty line.

        elif current_section == "education":
            # Simplified education parsing
            if line.startswith("B.Tech") or line.startswith("M.Tech") or line.startswith("M.S.") or line.startswith("B.E."):
                education_entry = {"degree": "", "field": "", "institution": "", "dates": ""}
                if "in" in line:
                    degree_part, rest = line.split("in", 1)
                    education_entry["degree"] = degree_part.strip()
                    if "–" in rest:
                        field_dates = rest.split("–")
                        education_entry["field"] = field_part[0].strip()
                        education_entry["dates"] = field_part[1].strip()
                    else:
                        education_entry["field"] = rest.strip()
                else:
                    education_entry["degree"] = line # Fallback if 'in' not found
                
                # Try to infer institution from next line if available
                if i + 1 < len(lines) and lines[i+1].strip() and not lines[i+1].strip().startswith(('–', 'B.Tech', 'M.Tech', 'M.S.', 'B.E.')):
                    education_entry["institution"] = lines[i+1].strip()
                
                parsed_data["education"].append(education_entry)

    # Add the last job if loop finished during experience
    if current_job:
        parsed_data["experience"].append(current_job)

    print(f"Finished parsing. Found {len(parsed_data.get('experience', []))} experience entries and {len(parsed_data.get('education', []))} education entries.")
    # Basic fill for name/contact from first line if not derived from section parsing
    if parsed_data["name"] == "N/A" and lines:
        first_line = lines[0].strip()
        if '|' in first_line:
            parts = first_line.split('|')
            if parts:
                parsed_data["name"] = parts[0].strip()
            if len(parts) > 1 and '@' in parts[1]:
                parsed_data["contact"]["email"] = parts[1].strip()

    return parsed_data

def load_resume_from_file(path: str) -> str:
    """Loads resume content from a text file."""
    print(f"Loading resume from file: {path}")
    if not os.path.exists(path):
        print(f"Error: Resume file not found at {path}")
        return ""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        print(f"Error reading resume file {path}: {e}")
        return ""

# Example Usage:
if __name__ == "__main__":
    # --- Example 1: Using a string directly ---
    sample_resume_string = """
KAMNEE MARAN
Senior Backend Engineer | Distributed Systems | Large-Scale Infrastructure
kamneemaran45@gmail.com | +91-7387233268 | Pune, India
LinkedIn | GitHub | Technical Articles | Open to Relocation: EU · US · Singapore · Remote
PROFESSIONAL SUMMARY
Senior Backend Engineer with 10+ years owning distributed systems at scale — ~12K RPS peak, 15+
interconnected services, millions of users. Drives measurable outcomes: 50–60% incident reduction through
architectural changes, AI-assisted tooling that cut on-call investigation time, and compliance infrastructure
shipped without throughput regression. Experienced in driving technical alignment across engineering and
operational stakeholders; effective from system design through production ownership.
PROFESSIONAL EXPERIENCE
Software Engineer – Backend & Distributed Systems Nov 2021 – Present
PhonePe Pvt Ltd Pune, India
Systems Design & Ownership
• Worked extensively on backend architecture, reliability, and distributed workflows for Recharge and Bill
Payment systems at PhonePe — operating at ~12K RPS peak across 15+ microservices, serving tens
of millions of users.
• Eliminated a systemic reliability gap via provider-wise queue segregation (RabbitMQ) and Hystrix circuit
breakers — cutting repeat provider incidents by 50–60%.
• Designed and evolved event-driven microservices for async transaction processing and provider
orchestration, enabling fault-tolerant, independently scalable service communication.
• Delivered RENT and EDU category integrations end-to-end, including compliance infra: PAN
verification, FRA-based regulatory checks, and a transaction queuing mechanism for pending
resolutions — zero throughput regression.
TECHNICAL SKILLS
Languages: Java, Python, Node.js
Systems & Architecture: Distributed Systems, System Design, Microservices, Event-Driven Architecture,
Async Processing, High Availability, Fault Tolerance, Resilience Engineering
Cloud & Infrastructure: AWS, Docker, Kubernetes, CI/CD, SQS
"""
    
    print("--- Parsing resume from string ---")
    parsed_from_string = parse_resume_string(sample_resume_string)
    print(json.dumps(parsed_from_string, indent=2))

    # --- Example 2: Loading from a dummy file ---
    # For this to work, create a file named 'dummy_resume.txt' in the same directory
    # and paste some resume text into it.
    dummy_file_path = 'dummy_resume.txt'
    if not os.path.exists(dummy_file_path):
        with open(dummy_file_path, 'w', encoding='utf-8') as f:
            f.write(sample_resume_string) # Write the same sample for demo
        print(f"\nCreated dummy file: {dummy_file_path} for testing.")

    print(f"\n--- Parsing resume from file: {dummy_file_path} ---")
    resume_content_from_file = load_resume_from_file(dummy_file_path)
    if resume_content_from_file:
        parsed_from_file = parse_resume_string(resume_content_from_file)
        print(json.dumps(parsed_from_file, indent=2))
    else:
        print("Could not load resume from file.")

