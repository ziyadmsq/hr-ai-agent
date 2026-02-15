"""Pydantic schemas for alert configuration and event endpoints."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Alert Config Schemas ─────────────────────────────────────────────────────


class AlertConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    trigger_type: str = Field(
        ..., min_length=1, max_length=100,
        description="One of: absence, contract_expiry, probation_end, custom",
    )
    trigger_config: Optional[dict[str, Any]] = None
    action_template: Optional[str] = None
    is_active: bool = True


class AlertConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    trigger_type: Optional[str] = Field(None, min_length=1, max_length=100)
    trigger_config: Optional[dict[str, Any]] = None
    action_template: Optional[str] = None
    is_active: Optional[bool] = None


class AlertConfigResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    trigger_type: str
    trigger_config: Optional[dict[str, Any]] = None
    action_template: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertConfigListResponse(BaseModel):
    items: list[AlertConfigResponse]
    total: int


# ── Alert Event Schemas ──────────────────────────────────────────────────────


class AlertEventResponse(BaseModel):
    id: UUID
    alert_config_id: UUID
    organization_id: UUID
    employee_id: UUID
    status: str
    context: Optional[dict[str, Any]] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertEventListResponse(BaseModel):
    items: list[AlertEventResponse]
    total: int


# ── Trigger Endpoint Schema ──────────────────────────────────────────────────


class TriggerEventRequest(BaseModel):
    trigger_type: str = Field(
        ..., description="Type of trigger (absence, contract_expiry, probation_end, custom)"
    )
    employee_id: UUID = Field(..., description="ID of the employee this event relates to")
    context: Optional[dict[str, Any]] = Field(
        None, description="Additional context for the trigger (e.g., date, reason)"
    )

