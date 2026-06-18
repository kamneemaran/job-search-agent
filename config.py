# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # General settings
    TARGET_URLS = os.getenv('TARGET_URLS', '').split(',')
    RESUME_PATH = os.getenv('RESUME_PATH', 'resume.txt') # Assumes resume is a text file for simplicity
    APPLICATION_TRACKER_PATH = os.getenv('APPLICATION_TRACKER_PATH', 'job_application_tracker.md')

    # Email notification settings
    SMTP_SERVER = os.getenv('SMTP_SERVER')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD = ***'SMTP_PASSWORD')
    EMAIL_FROM = os.getenv('EMAIL_FROM')
    EMAIL_TO = os.getenv('EMAIL_TO', '').split(',')

    # WhatsApp notification settings (using Twilio as an example)
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = ***'TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    WHATSAPP_TO = os.getenv('WHATSAPP_TO', '').split(',')

    # OpenAI API (optional, for advanced matching/summarization)
    OPENAI_API_KEY = ***'OPENAI_API_KEY')

# Instantiate config
config = Config()

# Example .env file content:
# TARGET_URLS=https://www.examplejobs.com/remote,https://www.anotherjobs.com/eu
# RESUME_PATH=/path/to/your/resume.txt
# APPLICATION_TRACKER_PATH=job_application_tracker.md
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your_email@gmail.com
# SMTP_PASSWORD=your_g…word # Use an App Password for Gmail
# EMAIL_FROM=your_email@gmail.com
# EMAIL_TO=recipient1@example.com,recipient2@example.com
# TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# TWILIO_AUTH_TOKEN=***
# TWILIO_PHONE_NUMBER=whatsapp:+14155238886 # Or your Twilio number
# WHATSAPP_TO=+1XXXXXXXXXX,+1XXXXXXXXXX
# OPENAI_API_KEY=sk-xxx…xxxx
