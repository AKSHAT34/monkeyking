"""Email Agent — Gmail IMAP for account verification."""
import imaplib
import email
import re
import time
from email.header import decode_header
from typing import Optional


class EmailAgent:
    """
    Connects to Gmail via IMAP to:
    - Read verification emails from job portals
    - Extract verification links
    - Monitor application confirmation emails
    """

    def __init__(self, config: dict):
        self.imap_server = config.get("imap_server", "imap.gmail.com")
        self.email_address = config.get("address", "")
        self.app_password = config.get("app_password", "")
        self._connection = None

    def connect(self) -> bool:
        """Connect to Gmail IMAP."""
        if not self.app_password:
            print("[EmailAgent] No app password configured. Set up Gmail App Password.")
            print("  Go to: https://myaccount.google.com/apppasswords")
            return False
        try:
            self._connection = imaplib.IMAP4_SSL(self.imap_server)
            self._connection.login(self.email_address, self.app_password)
            return True
        except Exception as e:
            print(f"[EmailAgent] Connection failed: {e}")
            return False

    def find_verification_email(self, from_domain: str, max_wait: int = 120,
                                 poll_interval: int = 10) -> Optional[str]:
        """
        Wait for and find a verification email from a specific domain.
        Returns the verification link if found.
        """
        if not self._connection:
            if not self.connect():
                return None

        elapsed = 0
        while elapsed < max_wait:
            link = self._search_for_verification(from_domain)
            if link:
                return link
            time.sleep(poll_interval)
            elapsed += poll_interval

        return None

    def _search_for_verification(self, from_domain: str) -> Optional[str]:
        """Search inbox for verification emails from a domain."""
        try:
            self._connection.select("INBOX")
            # Search for recent unread emails from the domain
            query = f'(UNSEEN FROM "@{from_domain}")'
            _, message_ids = self._connection.search(None, query)

            if not message_ids[0]:
                return None

            for msg_id in message_ids[0].split()[-5:]:  # Check last 5
                _, msg_data = self._connection.fetch(msg_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                body = self._get_email_body(msg)
                link = self._extract_verification_link(body)
                if link:
                    return link
        except Exception as e:
            print(f"[EmailAgent] Search error: {e}")
        return None

    def _get_email_body(self, msg) -> str:
        """Extract text body from email message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/html":
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    break
                elif content_type == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        return body

    def _extract_verification_link(self, body: str) -> Optional[str]:
        """Extract verification/confirmation link from email body."""
        patterns = [
            r'href=["\']?(https?://[^"\'>\s]+(?:verify|confirm|activate|validate)[^"\'>\s]*)',
            r'(https?://[^\s<>"]+(?:verify|confirm|activate|validate|token)[^\s<>"]*)',
            r'href=["\']?(https?://[^"\'>\s]+(?:email|account)[^"\'>\s]*(?:confirm|verify)[^"\'>\s]*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def get_recent_emails(self, count: int = 10) -> list[dict]:
        """Get recent emails for dashboard display."""
        if not self._connection:
            if not self.connect():
                return []
        try:
            self._connection.select("INBOX")
            _, message_ids = self._connection.search(None, "ALL")
            ids = message_ids[0].split()[-count:]
            results = []
            for msg_id in reversed(ids):
                _, msg_data = self._connection.fetch(msg_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")
                results.append({
                    "from": msg["From"],
                    "subject": subject,
                    "date": msg["Date"],
                })
            return results
        except Exception as e:
            print(f"[EmailAgent] Error: {e}")
            return []

    def disconnect(self):
        """Close IMAP connection."""
        if self._connection:
            try:
                self._connection.logout()
            except Exception:
                pass
