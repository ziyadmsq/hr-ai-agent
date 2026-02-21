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


# ── AI Config Schemas ────────────────────────────────────────────────────────

_VALID_PROVIDERS = ("openai", "groq", "ollama")


class AIConfigRequest(BaseModel):
    """Request schema for updating per-org AI configuration."""

    provider: Optional[str] = Field(
        None,
        description="AI provider: openai, groq, or ollama",
    )
    model: Optional[str] = Field(None, description="Model name (e.g. gpt-4o, llama3)")
    api_key: Optional[str] = Field(None, description="Provider API key")
    base_url: Optional[str] = Field(
        None, description="Custom base URL (required for ollama)"
    )
    embedding_provider: Optional[str] = Field(
        None, description="Embedding provider: openai or ollama"
    )
    embedding_model: Optional[str] = Field(
        None, description="Embedding model name"
    )

    def model_post_init(self, __context: Any) -> None:
        if self.provider is not None and self.provider not in _VALID_PROVIDERS:
            raise ValueError(
                f"provider must be one of {', '.join(_VALID_PROVIDERS)}"
            )
        if self.provider == "ollama" and not self.base_url:
            raise ValueError("base_url is required when provider is 'ollama'")


def _mask_api_key(key: Optional[str]) -> Optional[str]:
    """Mask an API key for safe display: sk-...xxxx."""
    if not key or len(key) < 8:
        return key
    return f"{key[:3]}...{key[-4:]}"


class AIConfigResponse(BaseModel):
    """Response schema for AI configuration — API key is always masked."""

    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None

    @classmethod
    def from_settings(cls, settings: Optional[dict[str, Any]]) -> "AIConfigResponse":
        """Build response from the org settings dict, masking the API key."""
        if not settings or "ai_config" not in settings:
            return cls()
        cfg = settings["ai_config"]
        return cls(
            provider=cfg.get("provider"),
            model=cfg.get("model"),
            api_key=_mask_api_key(cfg.get("api_key")),
            base_url=cfg.get("base_url"),
            embedding_provider=cfg.get("embedding_provider"),
            embedding_model=cfg.get("embedding_model"),
        )

