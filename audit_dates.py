import re

with open("daily_scan.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find all search functions
search_funcs = re.findall(r'def (search_[a-zA-Z0-9_]+)\(.*?\(jobs\.append\(({[^}]+})\)', content, re.DOTALL)
# Actually, re.finditer is better because we can extract function bodies.

# Let's find functions starting with "def search_"
funcs = []
for m in re.finditer(r'def (search_[a-zA-Z0-9_]+)\(', content):
    funcs.append((m.group(1), m.start()))

funcs.sort(key=lambda x: x[1])

results = []
for i in range(len(funcs)):
    name, start = funcs[i]
    end = funcs[i+1][1] if i + 1 < len(funcs) else len(content)
    body = content[start:end]
    
    # Check if "jobs.append" is inside body
    has_append = "jobs.append(" in body
    
    # Check if "posted_at" is inside body
    has_posted_at = "posted_at" in body
    
    results.append({
        "name": name,
        "has_append": has_append,
        "has_posted_at": has_posted_at,
        "body_snippet": body[:300].replace("\n", " ")
    })

print(f"Total search functions found: {len(results)}")
print("\n--- Scrapers missing 'posted_at' ---")
missing_count = 0
for r in results:
    if r["has_append"] and not r["has_posted_at"]:
        print(f"- {r['name']}")
        missing_count += 1

print(f"\nMissing count: {missing_count}")
