#!/usr/bin/env python3
"""Send email digest to Pradeep via MCP server"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PRADEEP_EMAIL = "pradeepmeena13@gmail.com"
PRADEEP_USER_ID = "9e61ac8c-7cc2-48c4-b7a1-991679494e5d"

def send_email_via_mcp():
    """Call MCP server to send email digest"""
    try:
        # Import the MCP server functions
        from mcp_server import email_digest_handler
        
        print("=" * 80)
        print("SENDING EMAIL DIGEST TO PRADEEP")
        print("=" * 80)
        print(f"\nEmail: {PRADEEP_EMAIL}")
        print(f"User ID: {PRADEEP_USER_ID}")
        print(f"Schedule: now (immediate)")
        
        print("\n[1] Calling MCP email_digest_handler...")
        
        # Call the MCP handler
        result = email_digest_handler({
            "email": PRADEEP_EMAIL,
            "schedule": "now"
        })
        
        print(f"\n[2] Response:")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Message: {result.get('message', 'No message')}")
        print(f"   Sent: {result.get('sent', False)}")
        print(f"   Count: {result.get('count', 0)} jobs")
        
        if result.get('sent'):
            print(f"\n✓ SUCCESS! Email sent to {PRADEEP_EMAIL}")
            print(f"  {result.get('count', 0)} job(s) included in digest")
        else:
            print(f"\n✗ Email not sent")
            print(f"  Message: {result.get('message', 'Unknown error')}")
        
        print("\n" + "=" * 80)
        return result
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        print("\nFALLBACK: Use web API or Cursor/Claude Desktop MCP interface")
        print(f"  Call: email_digest(email='{PRADEEP_EMAIL}', schedule='now')")
        return {"status": "error", "message": str(e), "sent": False}

if __name__ == "__main__":
    send_email_via_mcp()
