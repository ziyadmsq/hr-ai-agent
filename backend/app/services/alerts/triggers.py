"""Trigger definitions for the proactive alert system.

Each trigger produces a structured event with employee_id and context.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee

logger = logging.getLogger(__name__)


class TriggerEvent:
    """Structured event produced by a trigger."""

    def __init__(
        self,
        trigger_type: str,
        employee_id: UUID,
        organization_id: UUID,
        context: dict[str, Any] | None = None,
    ):
        self.trigger_type = trigger_type
        self.employee_id = employee_id
        self.organization_id = organization_id
        self.context = context or {}


class BaseTrigger(ABC):
    """Base class for all alert triggers."""

    trigger_type: str = ""

    @abstractmethod
    async def evaluate(
        self, db: AsyncSession, organization_id: UUID
    ) -> list[TriggerEvent]:
        """Evaluate the trigger and return matching events."""
        ...


class AbsenceTrigger(BaseTrigger):
    """Trigger when an employee is reported absent.

    This trigger is event-driven — it is invoked via the external trigger
    endpoint rather than the periodic scheduler.
    """

    trigger_type = "absence"

    async def evaluate(
        self, db: AsyncSession, organization_id: UUID
    ) -> list[TriggerEvent]:
        # Absence is event-driven (external POST), not scheduled.
        return []

    @staticmethod
    def from_external_event(
        employee_id: UUID, organization_id: UUID, context: dict[str, Any]
    ) -> TriggerEvent:
        return TriggerEvent(
            trigger_type="absence",
            employee_id=employee_id,
            organization_id=organization_id,
            context=context,
        )


class ContractExpiryTrigger(BaseTrigger):
    """Trigger when an employee's contract is expiring within N days.

    Reads `days_before` from trigger_config (default 30).
    Uses the employee metadata field `contract_end_date`.
    """

    trigger_type = "contract_expiry"

    def __init__(self, trigger_config: dict[str, Any] | None = None):
        self.days_before = (trigger_config or {}).get("days_before", 30)

    async def evaluate(
        self, db: AsyncSession, organization_id: UUID
    ) -> list[TriggerEvent]:
        today = date.today()
        threshold = today + timedelta(days=self.days_before)

        result = await db.execute(
            select(Employee).where(
                Employee.organization_id == organization_id,
                Employee.status == "active",
            )
        )
        events: list[TriggerEvent] = []
        for emp in result.scalars().all():
            meta = emp.metadata_ or {}
            end_str = meta.get("contract_end_date")
            if not end_str:
                continue
            try:
                end_date = date.fromisoformat(end_str)
            except (ValueError, TypeError):
                continue
            if today <= end_date <= threshold:
                events.append(TriggerEvent(
                    trigger_type=self.trigger_type,
                    employee_id=emp.id,
                    organization_id=organization_id,
                    context={
                        "contract_end_date": end_str,
                        "days_remaining": (end_date - today).days,
                    },
                ))
        return events


class ProbationEndTrigger(BaseTrigger):
    """Trigger when an employee's probation period is ending.

    Reads `days_before` from trigger_config (default 14).
    Uses the employee metadata field `probation_end_date`.
    """

    trigger_type = "probation_end"

    def __init__(self, trigger_config: dict[str, Any] | None = None):
        self.days_before = (trigger_config or {}).get("days_before", 14)

    async def evaluate(
        self, db: AsyncSession, organization_id: UUID
    ) -> list[TriggerEvent]:
        today = date.today()
        threshold = today + timedelta(days=self.days_before)

        result = await db.execute(
            select(Employee).where(
                Employee.organization_id == organization_id,
                Employee.status == "active",
            )
        )
        events: list[TriggerEvent] = []
        for emp in result.scalars().all():
            meta = emp.metadata_ or {}
            end_str = meta.get("probation_end_date")
            if not end_str:
                continue
            try:
                end_date = date.fromisoformat(end_str)
            except (ValueError, TypeError):
                continue
            if today <= end_date <= threshold:
                events.append(TriggerEvent(
                    trigger_type=self.trigger_type,
                    employee_id=emp.id,
                    organization_id=organization_id,
                    context={
                        "probation_end_date": end_str,
                        "days_remaining": (end_date - today).days,
                    },
                ))
        return events


class CustomTrigger(BaseTrigger):
    """Org-defined trigger with custom conditions (JSONB config).

    Custom triggers are event-driven — they are invoked via the external
    trigger endpoint with arbitrary context data.
    """

    trigger_type = "custom"

    async def evaluate(
        self, db: AsyncSession, organization_id: UUID
    ) -> list[TriggerEvent]:
        # Custom triggers are event-driven, not scheduled.
        return []

    @staticmethod
    def from_external_event(
        employee_id: UUID, organization_id: UUID, context: dict[str, Any]
    ) -> TriggerEvent:
        return TriggerEvent(
            trigger_type="custom",
            employee_id=employee_id,
            organization_id=organization_id,
            context=context,
        )


# ── Registry ─────────────────────────────────────────────────────────────────

SCHEDULED_TRIGGERS: dict[str, type[BaseTrigger]] = {
    "contract_expiry": ContractExpiryTrigger,
    "probation_end": ProbationEndTrigger,
}

EVENT_DRIVEN_TRIGGERS: dict[str, type[BaseTrigger]] = {
    "absence": AbsenceTrigger,
    "custom": CustomTrigger,
}

