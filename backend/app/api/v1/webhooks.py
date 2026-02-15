"""Webhook endpoints for WhatsApp and Email channel integrations.

These endpoints do NOT require JWT authentication — they use their own
signature verification mechanisms (Twilio signature for WhatsApp,
HMAC for Email/SendGrid).
"""

import logging

from fastapi import APIRouter, Form, Header, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.core.database import async_session_factory
from app.services.channels.email import email_service
from app.services.channels.router import handle_email_message, handle_whatsapp_message
from app.services.channels.whatsapp import whatsapp_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── WhatsApp (Twilio) Webhooks ────────────────────────────────────────────────


@router.get("/whatsapp", response_class=PlainTextResponse)
async def whatsapp_verify(
    hub_mode: str = "",
    hub_verify_token: str = "",
    hub_challenge: str = "",
):
    """Webhook verification endpoint (used during Twilio/Meta setup).

    Twilio WhatsApp sandbox doesn't always use this, but Meta's Cloud API does.
    """
    # Support both Twilio and Meta-style verification
    if hub_verify_token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        return hub_challenge
    # Also accept simple GET health check
    return "WhatsApp webhook active"


@router.post("/whatsapp")
async def whatsapp_inbound(
    request: Request,
    x_twilio_signature: str = Header("", alias="X-Twilio-Signature"),
):
    """Receive inbound WhatsApp messages from Twilio.

    Twilio sends form-encoded POST data with the message details.
    """
    form_data = await request.form()
    params = {k: v for k, v in form_data.items()}

    # Verify Twilio signature in production
    if whatsapp_service.is_configured and settings.TWILIO_AUTH_TOKEN:
        request_url = str(request.url)
        if not whatsapp_service.verify_signature(request_url, params, x_twilio_signature):
            logger.warning("Invalid Twilio signature on WhatsApp webhook")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid signature",
            )

    parsed = whatsapp_service.parse_inbound(params)
    sender = parsed["sender"]
    body = parsed["body"]

    if not sender or not body:
        logger.warning("WhatsApp webhook missing sender or body")
        # Twilio expects 200 even for messages we can't process
        return PlainTextResponse("OK", status_code=200)

    logger.info("WhatsApp message from %s: %s", sender, body[:100])

    async with async_session_factory() as db:
        try:
            reply = await handle_whatsapp_message(db, sender, body)
            await db.commit()
            if reply is None:
                logger.info("Unknown WhatsApp sender %s — no reply sent", sender)
        except Exception:
            await db.rollback()
            logger.exception("Error processing WhatsApp message")

    # Twilio expects a 200 response (TwiML or empty)
    return PlainTextResponse(
        '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


# ── Email (SendGrid Inbound Parse) Webhooks ──────────────────────────────────


@router.post("/email")
async def email_inbound(request: Request):
    """Receive inbound emails via SendGrid Inbound Parse.

    SendGrid sends multipart form data with the parsed email fields.
    """
    # Verify webhook signature if configured
    if settings.EMAIL_WEBHOOK_SECRET:
        body_bytes = await request.body()
        signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
        if not email_service.verify_webhook_signature(body_bytes, signature):
            logger.warning("Invalid signature on email webhook")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid signature",
            )

    form_data = await request.form()
    params = {k: v for k, v in form_data.items()}
    parsed = email_service.parse_inbound(params)

    sender = parsed["sender"]
    subject = parsed["subject"]
    body = parsed["body"]

    if not sender or not body:
        logger.warning("Email webhook missing sender or body")
        return {"status": "ignored", "reason": "missing sender or body"}

    logger.info("Inbound email from %s: subject=%s", sender, subject[:100] if subject else "(none)")

    # Extract just the email address if it's in "Name <email>" format
    if "<" in sender and ">" in sender:
        sender = sender.split("<")[1].split(">")[0]

    async with async_session_factory() as db:
        try:
            reply = await handle_email_message(db, sender, subject, body)
            await db.commit()
            if reply is None:
                logger.info("Unknown email sender %s — no reply sent", sender)
        except Exception:
            await db.rollback()
            logger.exception("Error processing inbound email")

    return {"status": "ok"}

