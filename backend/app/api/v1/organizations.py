"""Organization management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import OrgResponse, UpdateApiConfigRequest, UpdateOrgRequest
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

