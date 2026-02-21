"""Organization management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    AIConfigRequest,
    AIConfigResponse,
    OrgResponse,
    UpdateApiConfigRequest,
    UpdateOrgRequest,
)
from app.core.dependencies import get_current_user, get_db
from app.core.security import require_role
from app.models.organization import Organization

router = APIRouter(prefix="/org", tags=["organization"])


# ── GET /org ──────────────────────────────────────────────────────────────────


@router.get("", response_model=OrgResponse)
async def get_org(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's organization details."""
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


# ── PATCH /org ────────────────────────────────────────────────────────────────


@router.patch("", response_model=OrgResponse)
async def update_org(
    body: UpdateOrgRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update organization settings (admin only)."""
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if body.name is not None:
        org.name = body.name
    if body.settings is not None:
        org.settings = body.settings

    return org


# ── PATCH /org/api-config ─────────────────────────────────────────────────────


@router.patch("/api-config", response_model=OrgResponse)
async def update_api_config(
    body: UpdateApiConfigRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update the HR system API endpoint configuration (admin only)."""
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org.api_config = body.api_config
    return org


# ── GET /org/ai-config ───────────────────────────────────────────────────────


@router.get("/ai-config", response_model=AIConfigResponse)
async def get_ai_config(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the organization's AI provider configuration (API key masked)."""
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return AIConfigResponse.from_settings(org.settings)


# ── PATCH /org/ai-config ─────────────────────────────────────────────────────


@router.patch("/ai-config", response_model=AIConfigResponse)
async def update_ai_config(
    body: AIConfigRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update the organization's AI provider configuration (admin only).

    Merges provided fields into the existing ai_config; omitted fields are unchanged.
    """
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Merge into existing settings
    current_settings = dict(org.settings) if org.settings else {}
    current_ai = dict(current_settings.get("ai_config", {}))

    update_data = body.model_dump(exclude_none=True)
    # Strip empty strings — treat them as "not provided"
    update_data = {k: v for k, v in update_data.items() if v != ""}
    current_ai.update(update_data)
    current_settings["ai_config"] = current_ai
    org.settings = current_settings

    return AIConfigResponse.from_settings(org.settings)

