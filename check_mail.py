"""Search Gmail for recent job match emails."""
import imaplib, email, os
from datetime import datetime, timedelta

USER = "kamneemaran45@gmail.com"
PASS = "qnvp dgrz aaxv vtnn"

mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
mail.login(USER, PASS)

# Search in INBOX, Spam, All Mail for emails from last 24 hours
since = (datetime.now() - timedelta(hours=24)).strftime("%d-%b-%Y")

for folder in ["INBOX", '"[Gmail]/Spam"', '"[Gmail]/All Mail"', '"[Gmail]/Sent Mail"']:
    try:
        mail.select(folder)
        r, d = mail.search(None, '(SINCE %s SUBJECT "Job matches")' % since)
        if r == "OK" and d[0]:
            nums = d[0].split()
            print(f"=== {folder}: {len(nums)} emails ===")
            for num in nums[-10:]:
                r2, md = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(md[0][1])
                print(f"  Subject: {msg['subject']}")
                print(f"  Date: {msg['date']}")
                print(f"  To: {msg['to']}")
                print()
        else:
            print(f"=== {folder}: 0 emails ===")
    except Exception as e:
        print(f"  {folder}: {e}")

mail.logout()
