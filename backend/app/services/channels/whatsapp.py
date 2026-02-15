"""WhatsApp channel integration via Twilio API.

Handles:
- Sending outbound WhatsApp messages via Twilio REST API
- Verifying inbound webhook signatures from Twilio
- Parsing inbound WhatsApp messages
"""

import hashlib
import hmac
import logging
from base64 import b64encode
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Send and receive WhatsApp messages via Twilio."""

    TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"

    def __init__(self):
        self._account_sid = settings.TWILIO_ACCOUNT_SID
        self._auth_token = settings.TWILIO_AUTH_TOKEN
        self._from_number = settings.TWILIO_WHATSAPP_FROM

    @property
    def is_configured(self) -> bool:
        return bool(self._account_sid and self._auth_token)

    async def send_message(self, to: str, body: str) -> Optional[dict]:
        """Send a WhatsApp message via Twilio.

        Args:
            to: Recipient phone number in E.164 format (e.g. +1234567890).
                Will be prefixed with 'whatsapp:' automatically.
            body: Message text (max 1600 chars for WhatsApp).
        """
        if not self.is_configured:
            logger.warning("WhatsApp not configured — skipping send to %s", to)
            return None

        to_whatsapp = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        url = f"{self.TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"

        payload = {
            "From": self._from_number,
            "To": to_whatsapp,
            "Body": body[:1600],
        }

        auth_header = b64encode(
            f"{self._account_sid}:{self._auth_token}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    url,
                    data=payload,
                    headers={
                        "Authorization": f"Basic {auth_header}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
                result = resp.json()
                logger.info("WhatsApp message sent: SID=%s", result.get("sid"))
                return result
            except httpx.HTTPStatusError as e:
                logger.error("Twilio API error: %s — %s", e.response.status_code, e.response.text)
                return None
            except Exception as e:
                logger.exception("Failed to send WhatsApp message: %s", e)
                return None

    def verify_signature(self, url: str, params: dict, signature: str) -> bool:
        """Verify Twilio webhook request signature.

        Twilio signs requests using HMAC-SHA1 of the full URL + sorted POST params.
        See: https://www.twilio.com/docs/usage/security#validating-requests
        """
        if not self._auth_token:
            logger.warning("No auth token configured — cannot verify signature")
            return False

        # Build the data string: URL + sorted param key-value pairs
        data = url
        for key in sorted(params.keys()):
            data += key + params[key]

        # Compute HMAC-SHA1
        computed = b64encode(
            hmac.new(
                self._auth_token.encode("utf-8"),
                data.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode()

        return hmac.compare_digest(computed, signature)

    @staticmethod
    def parse_inbound(form_data: dict) -> dict:
        """Parse an inbound Twilio WhatsApp webhook payload.

        Returns a normalized dict with sender, body, and metadata.
        """
        return {
            "sender": form_data.get("From", "").replace("whatsapp:", ""),
            "body": form_data.get("Body", ""),
            "message_sid": form_data.get("MessageSid", ""),
            "account_sid": form_data.get("AccountSid", ""),
            "num_media": int(form_data.get("NumMedia", "0")),
            "profile_name": form_data.get("ProfileName", ""),
        }


# Module-level singleton
whatsapp_service = WhatsAppService()

