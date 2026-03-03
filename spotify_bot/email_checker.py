import imaplib
import email
from email.header import decode_header
import re
import os
import datetime

# GCash Email Subject Pattern
# "You have received PHP 100.00 of GCash from JUAN DELA CRUZ"
# Or sometimes "Payment Received" - subject varies, Body is more reliable.
# But for now let's pattern match typical Subjects or Body.

def connect_imap(email_user, email_pass):
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(email_user, email_pass)
    return mail

def check_for_payments(email_user, email_pass):
    try:
        mail = connect_imap(email_user, email_pass)
        mail.select("inbox")

        # Search for UNSEEN emails from no-reply@gcash.com
        # Note: In production you might want to remove "UNSEEN" to check old ones, 
        # but for automation we only want new ones.
        status, messages = mail.search(None, '(UNSEEN FROM "no-reply@gcash.com")')
        
        found_transactions = []

        if status != "OK":
            return []

        email_ids = messages[0].split()
        
        for e_id in email_ids:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    # Pattern Match logic
                    # Subject: "You have received PHP 100.00 of GCash from JUAN DELA CRUZ"
                    # Regex to extract amount and name
                    match = re.search(r"received PHP ([\d,]+\.\d{2}) .* from (.*)", subject, re.IGNORECASE)
                    
                    if match:
                        amount_str = match.group(1).replace(",", "")
                        sender_name = match.group(2).strip()
                        print(f"Found GCash: {amount_str} from {sender_name}")
                        found_transactions.append({
                            "amount": float(amount_str),
                            "name": sender_name
                        })
                    else:
                        print(f"Skipping non-matching GCash email: {subject}")

        mail.logout()
        return found_transactions

    except Exception as e:
        print(f"Email Check Error: {e}")
        return []
