"""Channel router — dispatches inbound messages to the HR agent and sends responses.

Looks up the employee by phone/email, creates or reuses a conversation,
calls the HR agent, and sends the reply back through the originating channel.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.organization import Organization
from app.services.agent.hr_agent import HRAgent
from app.services.channels.email import email_service
from app.services.channels.whatsapp import whatsapp_service

logger = logging.getLogger(__name__)

# Shared agent instance (same as chat.py uses)
_agent = HRAgent()


async def _lookup_employee_by_phone(
    db: AsyncSession, phone: str
) -> Optional[Employee]:
    """Find an employee whose metadata contains the given phone number."""
    # We store phone in employee.metadata_['phone']
    result = await db.execute(
        select(Employee).where(
            Employee.metadata_["phone"].astext == phone,
            Employee.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def _lookup_employee_by_email(
    db: AsyncSession, email: str
) -> Optional[Employee]:
    """Find an active employee by email address."""
    result = await db.execute(
        select(Employee).where(
            Employee.email == email,
            Employee.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def _get_org_name(db: AsyncSession, org_id: UUID) -> str:
    result = await db.execute(
        select(Organization.name).where(Organization.id == org_id)
    )
    name = result.scalar_one_or_none()
    return name or "Your Organization"


async def _get_or_create_conversation(
    db: AsyncSession,
    organization_id: UUID,
    employee_id: UUID,
    channel: str,
) -> "Conversation":  # noqa: F821
    """Get the most recent active conversation or create a new one."""
    from app.models.conversation import Conversation

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.organization_id == organization_id,
            Conversation.employee_id == employee_id,
            Conversation.channel == channel,
            Conversation.status == "active",
        )
        .order_by(Conversation.started_at.desc())
        .limit(1)
    )
    conv = result.scalar_one_or_none()
    if conv:
        return conv

    return await _agent.conversation_manager.create_conversation(
        db, organization_id, employee_id, channel=channel
    )


async def handle_whatsapp_message(
    db: AsyncSession, sender_phone: str, message_body: str
) -> Optional[str]:
    """Process an inbound WhatsApp message and return the reply text.

    Returns None if the sender cannot be identified.
    """
    employee = await _lookup_employee_by_phone(db, sender_phone)
    if not employee:
        logger.warning("WhatsApp message from unknown phone: %s", sender_phone)
        return None

    conv = await _get_or_create_conversation(
        db, employee.organization_id, employee.id, channel="whatsapp"
    )
    org_name = await _get_org_name(db, employee.organization_id)

    result = await _agent.chat(
        db=db,
        conversation_id=conv.id,
        user_message=message_body,
        employee_id=employee.id,
        organization_id=employee.organization_id,
        org_name=org_name,
    )

    reply = result.get("response", "Sorry, I could not process your request.")

    # Send reply back via WhatsApp
    await whatsapp_service.send_message(sender_phone, reply)
    return reply


async def handle_email_message(
    db: AsyncSession,
    sender_email: str,
    subject: str,
    body: str,
) -> Optional[str]:
    """Process an inbound email and return the reply text.

    Returns None if the sender cannot be identified.
    """
    employee = await _lookup_employee_by_email(db, sender_email)
    if not employee:
        logger.warning("Email from unknown address: %s", sender_email)
        return None

    conv = await _get_or_create_conversation(
        db, employee.organization_id, employee.id, channel="email"
    )
    org_name = await _get_org_name(db, employee.organization_id)

    # Use subject + body as the message content
    full_message = f"[Subject: {subject}]\n{body}" if subject else body

    result = await _agent.chat(
        db=db,
        conversation_id=conv.id,
        user_message=full_message,
        employee_id=employee.id,
        organization_id=employee.organization_id,
        org_name=org_name,
    )

    reply = result.get("response", "Sorry, I could not process your request.")

    # Send reply back via email
    await email_service.send_email(
        to=sender_email,
        subject=f"Re: {subject}" if subject else "HR Assistant Response",
        body_text=reply,
    )
    return reply


async def route_message(
    employee_id: UUID,
    organization_id: UUID,
    message: str,
    channel: str = "web",
) -> None:
    """Route a proactive message to an employee via the specified channel.

    Used by the alert engine to send proactive notifications.
    Falls back to logging if the channel service is not configured.
    """
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        employee = (
            await db.execute(
                select(Employee).where(
                    Employee.id == employee_id,
                    Employee.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()

        if not employee:
            logger.warning(
                "route_message: employee %s not found in org %s",
                employee_id,
                organization_id,
            )
            return

        if channel == "whatsapp":
            phone = (employee.metadata_ or {}).get("phone")
            if phone:
                await whatsapp_service.send_message(phone, message)
            else:
                logger.warning("No phone number for employee %s", employee_id)
        elif channel == "email":
            await email_service.send_email(
                to=employee.email,
                subject="HR Assistant Notification",
                body_text=message,
            )
        else:
            # "web" or unknown — log only (web push not implemented)
            logger.info(
                "[route_message] channel=%s employee=%s msg=%s",
                channel,
                employee.full_name,
                message[:200],
            )

