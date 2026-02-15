"""Pydantic schemas for auth and organization endpoints."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Auth Schemas ──────────────────────────────────────────────────────────────


class RegisterOrgRequest(BaseModel):
    org_name: str = Field(..., min_length=1, max_length=255)
    admin_email: EmailStr
    password: str = Field(..., min_length=6)
    admin_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="employee", pattern="^(admin|hr_manager|employee)$")
    full_name: str = Field(..., min_length=1, max_length=255)


class JoinOrgRequest(BaseModel):
    invite_code: str
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    organization_id: UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteResponse(BaseModel):
    invite_code: str
    email: str
    message: str


# ── Organization Schemas ──────────────────────────────────────────────────────


class OrgResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    settings: Optional[dict[str, Any]] = None
    api_config: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateOrgRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    settings: Optional[dict[str, Any]] = None


class UpdateApiConfigRequest(BaseModel):
    api_config: dict[str, Any]

