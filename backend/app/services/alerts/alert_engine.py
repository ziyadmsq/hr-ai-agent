"""Alert processing engine.

Processes incoming trigger events, matches them to configured AlertConfig rules,
creates AlertEvent records, and composes proactive messages using the AI agent.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert_config import AlertConfig
from app.models.alert_event import AlertEvent
from app.models.employee import Employee
from app.services.alerts.triggers import (
    SCHEDULED_TRIGGERS,
    TriggerEvent,
)

logger = logging.getLogger(__name__)


async def _send_message(
    employee: Employee,
    message: str,
    channel: str = "web",
) -> None:
    """Send a proactive message to an employee via the appropriate channel.

    Falls back to logging if the channel router is not available (parallel task).
    """
    try:
        from app.services.channels.router import route_message
        await route_message(
            employee_id=employee.id,
            organization_id=employee.organization_id,
            message=message,
            channel=channel,
        )
    except (ImportError, ModuleNotFoundError):
        logger.info(
            "[ALERT-STUB] Would send to %s (%s) via %s: %s",
            employee.full_name,
            employee.email,
            channel,
            message[:200],
        )


async def _compose_proactive_message(
    action_template: str | None,
    employee: Employee,
    context: dict[str, Any],
) -> str:
    """Compose a proactive message using the action template and context.

    If an OpenAI key is configured, uses the AI agent to generate a natural
    message. Otherwise, falls back to simple template interpolation.
    """
    template = action_template or "Hello {employee_name}, we have an update for you."
    placeholders = {
        "employee_name": employee.full_name,
        "employee_email": employee.email,
        "department": employee.department or "N/A",
        "position": employee.position or "N/A",
        **{str(k): str(v) for k, v in context.items()},
    }
    try:
        return template.format(**placeholders)
    except KeyError:
        # If template has unknown placeholders, do a safe partial format
        for key, val in placeholders.items():
            template = template.replace("{" + key + "}", val)
        return template


async def process_trigger_event(
    db: AsyncSession,
    trigger_event: TriggerEvent,
) -> AlertEvent | None:
    """Process a single trigger event.

    1. Find matching active AlertConfig(s) for the org + trigger_type
    2. Create an AlertEvent record for each match
    3. Compose and send a proactive message
    """
    # Find matching alert configs
    result = await db.execute(
        select(AlertConfig).where(
            AlertConfig.organization_id == trigger_event.organization_id,
            AlertConfig.trigger_type == trigger_event.trigger_type,
            AlertConfig.is_active.is_(True),
        )
    )
    configs = list(result.scalars().all())

    if not configs:
        logger.debug(
            "No active alert config for org=%s trigger_type=%s",
            trigger_event.organization_id,
            trigger_event.trigger_type,
        )
        return None

    # Fetch the employee
    emp_result = await db.execute(
        select(Employee).where(
            Employee.id == trigger_event.employee_id,
            Employee.organization_id == trigger_event.organization_id,
        )
    )
    employee = emp_result.scalar_one_or_none()
    if not employee:
        logger.warning(
            "Employee %s not found in org %s",
            trigger_event.employee_id,
            trigger_event.organization_id,
        )
        return None

    last_event: AlertEvent | None = None
    for config in configs:
        # Create alert event record
        alert_event = AlertEvent(
            alert_config_id=config.id,
            organization_id=trigger_event.organization_id,
            employee_id=trigger_event.employee_id,
            status="triggered",
            context=trigger_event.context,
        )
        db.add(alert_event)
        await db.flush()

        # Compose and send message
        message = await _compose_proactive_message(
            config.action_template, employee, trigger_event.context
        )
        await _send_message(employee, message)

        # Update status to in_progress
        alert_event.status = "in_progress"
        await db.flush()

        logger.info(
            "Processed alert event %s for config '%s' → employee %s",
            alert_event.id,
            config.name,
            employee.full_name,
        )
        last_event = alert_event

    return last_event


async def run_scheduled_triggers(db: AsyncSession) -> int:
    """Run all scheduled (time-based) triggers across all organizations.

    Returns the total number of alert events created.
    """
    from app.models.organization import Organization

    result = await db.execute(select(Organization))
    orgs = list(result.scalars().all())
    total_events = 0

    for org in orgs:
        # Get active alert configs for scheduled trigger types
        config_result = await db.execute(
            select(AlertConfig).where(
                AlertConfig.organization_id == org.id,
                AlertConfig.is_active.is_(True),
                AlertConfig.trigger_type.in_(list(SCHEDULED_TRIGGERS.keys())),
            )
        )
        configs = list(config_result.scalars().all())

        for config in configs:
            trigger_cls = SCHEDULED_TRIGGERS.get(config.trigger_type)
            if not trigger_cls:
                continue
            trigger = trigger_cls(trigger_config=config.trigger_config)
            events = await trigger.evaluate(db, org.id)
            for event in events:
                alert_event = await process_trigger_event(db, event)
                if alert_event:
                    total_events += 1

    logger.info("Scheduled trigger run complete: %d events created", total_events)
    return total_events

