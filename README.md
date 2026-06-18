# AI Job Search Assistant                                                                                                                                                                                                                   
This project is a Python-based AI assistant designed to help automate aspects of the job search process. It aims to fetch job listings from various sources, match them against your resume, score their relevance, and suggest next steps. 
                                                            
  ## Features                                                                                                                                                                                                                         
  *   **Job Fetching:** Retrieves content from specified job board URLs (requires enhancement for robust scraping). 
  *   **Resume Parsing:** Parses resume content (currently supports plain text, expandable to PDF/DOCX).  
  *   **Job Matching & Scoring:** Calculates a match score for jobs based on keywords, seniority, tech stack, and location/sponsorship criteria. 
  *   **Application Tracking:** Logs job applications, status, and notes into a CSV or Markdown file.
  *   **Notifications:** (Optional) Provides placeholders for email and WhatsApp notifications for promising leads.                                                                                                             
  ## Prerequisites                                                                                                                                                                                                                
  *   **Python 3.8+:** Ensure you have Python installed on your system. 
  *   **pip:** Python's package installer.                          
  *   **Git:** For version control and potentially for GitHub Actions integration. 
  *   **Virtual Environment:** Highly recommended for managing project dependencies.                                                                                                                                                          
  ## Setup Instructions                                          
  1.  **Clone the Repository:**                                  
      If you're using Git and have pushed these files to a GitHub repository, clone it to your local machine:                                                                                                                                 
      ```bash                                                    
      git clone <your-repository-url>                                                    
      cd <repository-directory>   
      ```                                                                                                                                                                                                                                     
      If you just have the files locally, navigate to the directory where you saved them: 
      ```bash                                                    
      cd /Users/admin/Downloads/files                                                                                                                                                                                                         
      ```                                                                                                                                                                                                                                   
  2.  **Create and Activate a Virtual Environment:**           
      It's best practice to use a virtual environment.                                                                                                                                                                                        
      ```bash                                                                                                                                                                                                                                 
      # Create the virtual environment                                                                                                                                                                                              
      python3 -m venv venv                                                     
      # Activate the virtual environment                                                                                                                                                                                                      
      # On macOS/Linux:                                                          
      source venv/bin/activate                                                                                                                                                                                                                
      # On Windows:                                                          
      # .\venv\Scripts\activate                                                                                                                                                                                                               
      ```                                                                                                                                                                                                                                   
  3.  **Install Dependencies:**                                  
      Install the necessary Python libraries.                    
      ```bash                                                                                                                                                                                                                                 
      pip install requests beautifulsoup4 python-dotenv pandas openai                                                                                                              # If using email notifications via SendGrid (example):                                                                                                                                                                                  
      # pip install sendgrid                                                                                                                                                                                                                  
      # If using WhatsApp notifications via Twilio:                                                                                                                                                                                           
      # pip install twilio                                                                                                                                                                                                                    
      ```                                                         
  4.  **Configure Environment Variables (`.env` file):**         
      *   Locate or create the `.env` file in the project's root directory (`/Users/admin/Downloads/files`).  
      *   **Crucially, update the following:**                   
          *   `RESUME_PATH`: The absolute path to your resume file (e.g., `/Users/admin/Downloads/files/resume.txt`). If your resume is in PDF/DOCX, you'll need to adapt `resume_parser.py` to handle those formats.                         
          *   `TARGET_URLS`: Comma-separated list of job board URLs to scrape. 
          *   `APPLICATION_TRACKER_PATH`: Path for your application tracker file (e.g., `job_application_tracker.md`).  
          *   **Notification Credentials (Optional):** `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` (use **App Password** for Gmail), `EMAIL_FROM`, `EMAIL_TO`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,                    
`TWILIO_PHONE_NUMBER`, `WHATSAPP_TO`.                         
          *   `OPENAI_API_KEY` (Optional): If you plan to use OpenAI functionalities.                                                                                                                                                        
  ### **Running the Job Search Script**                           
  Once your environment is set up and configured:             
  1.  **Execute `main_app.py`:**                                                             
      ```bash                                                                                                                                                                                                                                 
      python main_app.py                                                                                                                                                                                                                      
      ```                                                                                                                                                                                                                                     
      This will run the script once, performing the job search, matching, and printing results.                                                                                                                                           
  ### **Key Areas for Further Development**                                                                                                                                                                                                 
  The provided scripts offer a solid foundation, but for a robust, automated solution, consider these enhancements:                                                             1.  **Advanced Web Scraping:** The `job_fetcher.py` script has basic URL fetching. For effective job searching, you'll need to implement site-specific parsers using libraries like BeautifulSoup to extract actual job listings (titles,   
descriptions, application links, dates) from the HTML content of each target URL. This is the most complex part and requires continuous maintenance as websites change. 
  2.  **Resume Parsing for PDFs/DOCX:** Integrate libraries like `PyPDF2` or `python-docx` into `resume_parser.py` to handle common resume file formats beyond plain text.
  3.  **Sophisticated Matching:** Enhance `job_matcher.py` for more nuanced scoring, perhaps using NLP techniques to understand context and semantic similarity between your resume and job descriptions.                                     
  4.  **Error Handling & Logging:** Implement comprehensive error handling and logging to gracefully manage failures during fetching, parsing, or notification sending. 
  5.  **Notification Integration:** Fully implement the email and WhatsApp notification logic using appropriate libraries and API credentials.       
  6.  **Application Tracker Logic:** Enhance the `update_application_tracker` function in `main_app.py` for more robust handling of the Markdown file, ensuring correct formatting and appending.
  
  ### **Automating with GitHub Actions (Conceptual)**            
  To run this script automatically (e.g., daily):                
  1.  **Create a GitHub Repository:** Push all your project files (`.py` scripts, `.env`, `README.md`, `job_application_tracker.md`, `venv` - though `venv` is usually gitignored) to a GitHub repository.                                    
  2.  **Create Workflow File:** In your repository, create a directory `.github/workflows/` and add a YAML file (e.g., `job_search.yml`). 
  3.  **Configure Workflow:** This file will define the trigger (e.g., `on: schedule: cron: '0 8 * * *'` for 8 AM UTC daily) and the steps to run your script (e.g., checkout code, set up Python, install dependencies, run `python          
main_app.py`). You'll use GitHub Secrets to store sensitive `.env` variables like API keys.      
