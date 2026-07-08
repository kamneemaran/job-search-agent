"""Fetch IND recognised sponsors from the official register and cache to JSON."""
import requests
import json
from bs4 import BeautifulSoup

url = "https://ind.nl/en/public-register-recognised-sponsors/public-register-regular-labour-and-highly-skilled-migrants"
resp = requests.get(url, timeout=30)
soup = BeautifulSoup(resp.text, 'html.parser')

names = set()
for th in soup.select('table th[scope="row"]'):
    name = th.get_text(strip=True)
    if name:
        names.add(name.lower())

base = set()
for name in names:
    words = name.split()
    if words:
        c = words[0].rstrip(',.')
        if len(c) > 1:
            base.add(c)
        if len(words) >= 2:
            c2 = f"{words[0]} {words[1].rstrip(',.')}".lower()
            base.add(c2)

result = list(names | base)
with open("ind_sponsors_cache.json", "w") as f:
    json.dump(result, f)
print(f"Cached {len(result)} IND sponsor lookup keys")
