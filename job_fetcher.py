# job_fetcher.py
import requests
from bs4 import BeautifulSoup
import time
from functools import lru_cache # For caching results to avoid re-fetching

from config import config # Assuming config.py is in the same directory

# Cache fetched URLs for a short period to avoid rate limiting and speed up runs
@lru_cache(maxsize=128)
def fetch_url_content(url: str, timeout: int = 10) -> str | None:
    """Fetches content from a URL. Returns None if fetching fails."""
    print(f"Attempting to fetch: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        # Try to extract readable text content. This is a basic approach.
        # For complex sites, specific parsing logic per site might be needed.
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract text from common meaningful tags
        text_content = soup.get_text(separator='\n', strip=True)
        
        # Further refine text extraction if needed (e.g., focus on job listing sections)
        # This part is highly dependent on the website's structure.
        
        return text_content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing {url}: {e}")
        return None

def get_job_listings_from_urls(urls: list[str]) -> dict:
    """Fetches content from multiple URLs and returns it."""
    all_content = {}
    for url in urls:
        content = fetch_url_content(url)
        if content:
            all_content[url] = content
        time.sleep(1) # Small delay between requests to be polite
    return all_content
