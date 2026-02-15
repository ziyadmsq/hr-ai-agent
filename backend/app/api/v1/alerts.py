"""Alert management endpoints.

CRUD for alert configurations, event listing, and external trigger endpoint.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_current_tenant, get_db
from app.models.alert_config import AlertConfig
from app.models.alert_event import AlertEvent
from app.models.employee import Employee
from app.models.user import User
from app.schemas.alerts import (
    AlertConfigCreate,
    AlertConfigListResponse,
    AlertConfigResponse,
    AlertConfigUpdate,
    AlertEventListResponse,
    AlertEventResponse,
    TriggerEventRequest,
)
from app.services.alerts.alert_engine import process_trigger_event
from app.services.alerts.triggers import TriggerEvent

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _require_admin(user: User) -> None:
    if user.role not in ("admin", "hr_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR manager access required",
        )


# ── Alert Config CRUD ────────────────────────────────────────────────────────


@router.get("/configs", response_model=AlertConfigListResponse)
async def list_alert_configs(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List alert configurations for the current organization."""
    query = select(AlertConfig).where(AlertConfig.organization_id == org_id)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(query.order_by(AlertConfig.created_at.desc()))
    configs = list(result.scalars().all())
    return AlertConfigListResponse(items=configs, total=total)


@router.post(
    "/configs",
    response_model=AlertConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert_config(
    data: AlertConfigCreate,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert configuration (admin/HR only)."""
    _require_admin(current_user)
    config = AlertConfig(
        organization_id=org_id,
        name=data.name,
        trigger_type=data.trigger_type,
        trigger_config=data.trigger_config,
        action_template=data.action_template,
        is_active=data.is_active,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


@router.patch("/configs/{config_id}", response_model=AlertConfigResponse)
async def update_alert_config(
    config_id: UUID,
    data: AlertConfigUpdate,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update an alert configuration (admin/HR only)."""
    _require_admin(current_user)
    result = await db.execute(
        select(AlertConfig).where(
            AlertConfig.id == config_id,
            AlertConfig.organization_id == org_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert config not found"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.flush()
    await db.refresh(config)
    return config


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_alert_config(
    config_id: UUID,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate (soft-delete) an alert configuration (admin/HR only)."""
    _require_admin(current_user)
    result = await db.execute(
        select(AlertConfig).where(
            AlertConfig.id == config_id,
            AlertConfig.organization_id == org_id,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert config not found"
        )
    config.is_active = False
    await db.flush()
    return None


# ── Alert Events ─────────────────────────────────────────────────────────────


@router.get("/events", response_model=AlertEventListResponse)
async def list_alert_events(
    status_filter: Optional[str] = Query(None, alias="status"),
    config_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List alert events for the current organization (with optional filters)."""
    query = select(AlertEvent).where(AlertEvent.organization_id == org_id)
    if status_filter:
        query = query.where(AlertEvent.status == status_filter)
    if config_id:
        query = query.where(AlertEvent.alert_config_id == config_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(AlertEvent.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    events = list(result.scalars().all())
    return AlertEventListResponse(items=events, total=total)


# ── External Trigger Endpoint ────────────────────────────────────────────────


@router.post("/trigger", response_model=AlertEventResponse)
async def trigger_alert(
    data: TriggerEventRequest,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """External trigger endpoint — org systems call this to report events.

    For example, an attendance system can POST here when an employee is absent.
    Requires JWT authentication.
    """
    # Verify the employee belongs to this org
    emp_result = await db.execute(
        select(Employee).where(
            Employee.id == data.employee_id,
            Employee.organization_id == org_id,
        )
    )
    if not emp_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found in this organization",
        )

    trigger_event = TriggerEvent(
        trigger_type=data.trigger_type,
        employee_id=data.employee_id,
        organization_id=org_id,
        context=data.context,
    )

    alert_event = await process_trigger_event(db, trigger_event)
    if not alert_event:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No active alert config found for trigger_type='{data.trigger_type}'",
        )

    return alert_event

