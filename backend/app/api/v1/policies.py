from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_current_tenant, get_db
from app.models.policy_document import PolicyDocument
from app.models.user import User
from app.schemas.policies import (
    PolicyCreate,
    PolicyListResponse,
    PolicyResponse,
    PolicyUpdate,
)

router = APIRouter(prefix="/policies", tags=["policies"])


def _require_admin(user: User) -> None:
    if user.role not in ("admin", "hr_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR manager access required",
        )


@router.get("", response_model=PolicyListResponse)
async def list_policies(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List all active policies for the organization."""
    query = select(PolicyDocument).where(
        PolicyDocument.organization_id == org_id,
        PolicyDocument.is_active.is_(True),
    )
    result = await db.execute(query)
    policies = result.scalars().all()
    return PolicyListResponse(items=policies, total=len(policies))


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: UUID,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific policy by ID."""
    result = await db.execute(
        select(PolicyDocument).where(
            PolicyDocument.id == policy_id,
            PolicyDocument.organization_id == org_id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )
    return policy


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    data: PolicyCreate,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a new policy (admin/HR only)."""
    _require_admin(current_user)
    policy = PolicyDocument(
        organization_id=org_id,
        title=data.title,
        content=data.content,
        category=data.category,
        is_active=data.is_active,
    )
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: UUID,
    data: PolicyUpdate,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update a policy (admin/HR only)."""
    _require_admin(current_user)
    result = await db.execute(
        select(PolicyDocument).where(
            PolicyDocument.id == policy_id,
            PolicyDocument.organization_id == org_id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)

    await db.flush()
    await db.refresh(policy)
    return policy

