from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PolicyCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    is_active: bool = True


class PolicyUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class PolicyResponse(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    content: str
    category: Optional[str] = None
    is_active: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyListResponse(BaseModel):
    items: list[PolicyResponse]
    total: int

