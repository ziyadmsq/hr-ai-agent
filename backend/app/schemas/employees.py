from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class EmployeeCreate(BaseModel):
    full_name: str
    email: EmailStr
    employee_code: str
    department: Optional[str] = None
    position: Optional[str] = None
    hire_date: Optional[date] = None
    status: str = "active"
    metadata_: Optional[dict] = None


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    employee_code: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    hire_date: Optional[date] = None
    status: Optional[str] = None
    metadata_: Optional[dict] = None


class EmployeeResponse(BaseModel):
    id: UUID
    organization_id: UUID
    employee_code: str
    full_name: str
    email: str
    department: Optional[str] = None
    position: Optional[str] = None
    hire_date: Optional[date] = None
    status: str
    metadata_: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int

