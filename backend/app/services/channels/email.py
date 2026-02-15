"""Email channel integration — SMTP and SendGrid.

Handles:
- Sending outbound emails via SMTP or SendGrid
- Parsing inbound email webhook payloads (SendGrid Inbound Parse)
- Verifying inbound webhook signatures
"""

import hashlib
import hmac
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Send and receive emails via SMTP or SendGrid."""

    SENDGRID_API_BASE = "https://api.sendgrid.com/v3"

    @property
    def is_configured(self) -> bool:
        """True if at least one email provider is configured."""
        return bool(settings.SENDGRID_API_KEY) or bool(settings.SMTP_USER)

    async def send_email(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """Send an email. Prefers SendGrid if configured, falls back to SMTP."""
        if settings.SENDGRID_API_KEY:
            return await self._send_via_sendgrid(to, subject, body_text, body_html)
        if settings.SMTP_USER:
            return self._send_via_smtp(to, subject, body_text, body_html)

        logger.warning("Email not configured — skipping send to %s", to)
        return False

    async def _send_via_sendgrid(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """Send email via SendGrid v3 API."""
        url = f"{self.SENDGRID_API_BASE}/mail/send"
        content = [{"type": "text/plain", "value": body_text}]
        if body_html:
            content.append({"type": "text/html", "value": body_html})

        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": settings.SMTP_FROM_EMAIL},
            "subject": subject,
            "content": content,
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
                logger.info("Email sent via SendGrid to %s", to)
                return True
            except httpx.HTTPStatusError as e:
                logger.error("SendGrid error: %s — %s", e.response.status_code, e.response.text)
                return False
            except Exception as e:
                logger.exception("Failed to send email via SendGrid: %s", e)
                return False

    def _send_via_smtp(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP (synchronous — runs in thread pool in practice)."""
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        try:
            if settings.SMTP_USE_TLS:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
                server.starttls()
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)

            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

            server.sendmail(settings.SMTP_FROM_EMAIL, to, msg.as_string())
            server.quit()
            logger.info("Email sent via SMTP to %s", to)
            return True
        except Exception as e:
            logger.exception("Failed to send email via SMTP: %s", e)
            return False

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """Verify SendGrid Inbound Parse webhook signature."""
        secret = settings.EMAIL_WEBHOOK_SECRET
        if not secret:
            logger.warning("No EMAIL_WEBHOOK_SECRET — skipping verification")
            return True  # Allow in dev mode

        computed = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed, signature)

    @staticmethod
    def parse_inbound(form_data: dict) -> dict:
        """Parse a SendGrid Inbound Parse webhook payload.

        Returns a normalized dict with sender, subject, body, etc.
        """
        return {
            "sender": form_data.get("from", ""),
            "to": form_data.get("to", ""),
            "subject": form_data.get("subject", ""),
            "body": form_data.get("text", "") or form_data.get("html", ""),
            "message_id": form_data.get("Message-Id", ""),
        }


# Module-level singleton
email_service = EmailService()

