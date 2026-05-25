"""
test_smtp.py
------------
Run this standalone to diagnose exactly why SMTP is failing.
Place it in the same folder as your .env and run:
    python test_smtp.py
"""

import smtplib
import sys
from dotenv import load_dotenv
import os

load_dotenv()

HOST     = os.environ.get("SMTP_HOST", "smtp.office365.com")
PORT     = int(os.environ.get("SMTP_PORT", 587))
USER     = os.environ.get("SMTP_USER", "")
PASSWORD = os.environ.get("SMTP_PASSWORD", "")
TO_EMAIL = os.environ.get("IT_TEAM_EMAIL", "")

print("=" * 55)
print("SMTP Diagnostic Test")
print("=" * 55)
print(f"  Host     : {HOST}")
print(f"  Port     : {PORT}")
print(f"  User     : {USER}")
print(f"  Password : {'*' * len(PASSWORD)} ({len(PASSWORD)} chars)")
print(f"  To       : {TO_EMAIL}")
print("=" * 55)

if not USER or not PASSWORD:
    print("❌ SMTP_USER or SMTP_PASSWORD is empty in .env")
    sys.exit(1)

try:
    print("\n[1] Connecting to SMTP server...")
    server = smtplib.SMTP(HOST, PORT, timeout=10)
    print("    ✅ Connected")

    print("[2] Sending EHLO...")
    server.ehlo()
    print("    ✅ EHLO OK")

    print("[3] Starting TLS (STARTTLS)...")
    server.starttls()
    server.ehlo()
    print("    ✅ TLS OK")

    print("[4] Logging in...")
    server.login(USER, PASSWORD)
    print("    ✅ Login successful!")

    print("[5] Sending test email...")
    from email.mime.text import MIMEText
    msg = MIMEText("This is a test email from your IT Helpdesk Bot SMTP diagnostic script.")
    msg["Subject"] = "IT Helpdesk Bot — SMTP Test"
    msg["From"]    = USER
    msg["To"]      = TO_EMAIL or USER   # send to self if IT_TEAM_EMAIL not set
    server.send_message(msg)
    print(f"    ✅ Test email sent to {TO_EMAIL or USER}")

    server.quit()
    print("\n✅ ALL CHECKS PASSED — SMTP is working correctly.")

except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ AUTHENTICATION FAILED: {e}")
    print("""
Possible fixes:
  1. You are using your ACCOUNT password instead of an APP PASSWORD.
     → Go to https://myaccount.microsoft.com → Security → App passwords
     → Create a new app password and paste it as SMTP_PASSWORD in .env

  2. SMTP AUTH is disabled for your mailbox by your tenant admin.
     → Ask your admin to run in Exchange Online PowerShell:
         Set-CASMailbox -Identity your@email.com -SmtpClientAuthenticationDisabled $false

  3. MFA is enforced and basic auth is blocked tenant-wide.
     → Use Microsoft Graph API instead (set USE_GRAPH_EMAIL=true in .env)
""")

except smtplib.SMTPConnectError as e:
    print(f"\n❌ CONNECTION FAILED: {e}")
    print("  → Check SMTP_HOST and SMTP_PORT in your .env")
    print("  → Try PORT=465 with SSL, or PORT=587 with STARTTLS")

except smtplib.SMTPException as e:
    print(f"\n❌ SMTP ERROR: {e}")

except TimeoutError:
    print("\n❌ CONNECTION TIMED OUT")
    print("  → Your network or firewall may be blocking port 587")
    print("  → Try from a different network or check with your IT admin")

except Exception as e:
    print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")