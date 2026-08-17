#!/usr/bin/env python3
"""
Fix misaligned Supabase job data.

The data was inserted in wrong column order, causing:
- company column ← receiving location values
- location column ← receiving status values
- url column ← receiving date values

This script corrects the alignment by:
1. Reading all rows with misaligned data
2. Extracting actual values from wrong columns
3. Reconstructing and updating with correct mapping
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Supabase credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
USER_ID = os.environ.get("SUPABASE_USER_ID", "")  # Or pass as argument

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_KEY not set in .env")
    sys.exit(1)

from supabase import create_client, Client

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fix_alignment(user_id: str = None):
    """
    Fix misaligned data in the jobs table.
    
    Original (wrong) mapping was:
    - company ← location (wrong)
    - location ← status (wrong)
    - url ← posted_at/date (wrong)
    - status ← ??? (should be "new")
    
    We need to:
    1. Read rows with misaligned data
    2. Move values to correct columns
    3. Update the table
    """
    
    try:
        # Get all jobs for this user
        query = supabase.table("jobs")
        if user_id:
            query = query.eq("user_id", user_id)
        
        result = query.select("*").execute()
        rows = result.data
        
        if not rows:
            print("✓ No rows found to fix")
            return
        
        print(f"Found {len(rows)} rows to analyze")
        print("\n" + "="*80)
        
        # Analyze and show current state
        misaligned_count = 0
        for i, row in enumerate(rows):
            # Check if data looks misaligned
            # If location field contains status values (new, applied, rejected)
            # or url field contains dates (YYYY-MM-DD)
            location = row.get("location", "")
            url = row.get("url", "")
            status = row.get("status", "")
            company = row.get("company", "")
            
            is_misaligned = False
            
            # Check for status value in location column
            if location and location.lower() in ["new", "applied", "rejected", "offer"]:
                is_misaligned = True
            
            # Check for date in url column (YYYY-MM-DD pattern)
            if url and len(url) == 10 and url[4] == "-" and url[7] == "-":
                is_misaligned = True
            
            # Check for empty or suspicious values
            if location and status.strip() == "" and company and company not in ["", "Unknown"]:
                # location has value, status is empty - likely shifted
                is_misaligned = True
            
            if is_misaligned:
                misaligned_count += 1
                print(f"\n[Row {row['id']}] MISALIGNED:")
                print(f"  company: {company[:50]}")
                print(f"  location: {location}")
                print(f"  url: {url}")
                print(f"  status: {status}")
        
        print("\n" + "="*80)
        print(f"✓ Found {misaligned_count} misaligned rows out of {len(rows)}")
        
        if misaligned_count == 0:
            print("✓ All data appears to be correctly aligned!")
            return
        
        # Ask for confirmation before fixing
        print("\n⚠️  Ready to fix these rows?")
        print("This will update the following columns:")
        print("  - company: extracted from current 'company' (should stay)")
        print("  - location: extracted from current 'company' value")
        print("  - url: extracted from current 'location' value")
        print("  - status: extracted from current 'url' value (if matches new/applied/rejected)")
        
        confirm = input("\nType 'YES' to proceed with fixing: ").strip().upper()
        if confirm != "YES":
            print("❌ Fix cancelled")
            return
        
        # Fix the data
        fixed_count = 0
        for row in rows:
            location = row.get("location", "")
            url = row.get("url", "")
            status = row.get("status", "")
            company = row.get("company", "")
            
            # Detect if misaligned and fix
            is_misaligned = False
            new_status = "new"
            new_url = url if url and not (len(url) == 10 and url[4] == "-") else ""
            new_location = company if company and location and location.lower() in ["new", "applied", "rejected", "offer"] else location
            new_company = company
            
            # If url looks like a date, move it to status
            if url and len(url) == 10 and url[4] == "-" and url[7] == "-":
                is_misaligned = True
                new_status = location if location.lower() in ["new", "applied", "rejected", "offer"] else "new"
                new_url = url if not (len(url) == 10 and url[4] == "-") else ""
            
            if is_misaligned:
                print(f"\n✓ Fixing row {row['id']}")
                print(f"  Before → After:")
                print(f"  company: {company} → {new_company}")
                print(f"  location: {location} → {new_location}")
                print(f"  url: {url} → {new_url}")
                print(f"  status: {status} → {new_status}")
                
                # Update the row
                try:
                    supabase.table("jobs").update({
                        "company": new_company,
                        "location": new_location,
                        "url": new_url,
                        "status": new_status,
                    }).eq("id", row["id"]).execute()
                    fixed_count += 1
                except Exception as e:
                    print(f"  ❌ Error updating: {e}")
        
        print(f"\n{'='*80}")
        print(f"✓ Fixed {fixed_count} rows successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    user_id = sys.argv[1] if len(sys.argv) > 1 else USER_ID
    
    if not user_id:
        print("Usage: python fix_supabase_alignment.py [USER_ID]")
        print("\nOr set SUPABASE_USER_ID in .env file")
        sys.exit(1)
    
    fix_alignment(user_id)
