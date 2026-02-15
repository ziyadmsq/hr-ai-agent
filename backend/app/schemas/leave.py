from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class LeaveBalanceResponse(BaseModel):
    id: UUID
    employee_id: UUID
    leave_type: str
    total_days: float
    used_days: float
    remaining_days: float = 0.0
    year: int

    model_config = {"from_attributes": True}


class LeaveRequestCreate(BaseModel):
    leave_type: str
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveRequestUpdate(BaseModel):
    status: str  # approved, rejected


class LeaveRequestResponse(BaseModel):
    id: UUID
    organization_id: UUID
    employee_id: UUID
    leave_type: str
    start_date: date
    end_date: date
    status: str
    reason: Optional[str] = None
    approved_by: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaveRequestListResponse(BaseModel):
    items: list[LeaveRequestResponse]
    total: int

