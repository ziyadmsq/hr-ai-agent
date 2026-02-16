"""Authentication endpoints: register-org, login, invite-user, join, me."""

import re
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    InviteResponse,
    InviteUserRequest,
    JoinOrgRequest,
    LoginRequest,
    RegisterOrgRequest,
    TokenResponse,
    UserResponse,
)
from app.core.dependencies import get_current_user, get_db
from app.core.security import (
    create_access_token,
    hash_password,
    require_role,
    verify_password,
)
from app.models.employee import Employee
from app.models.organization import Organization
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory invite store (keyed by invite_code)
# In production this would be a DB table or Redis
_pending_invites: dict[str, dict] = {}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


# ── POST /register-org ────────────────────────────────────────────────────────


@router.post("/register-org", response_model=TokenResponse, status_code=201)
async def register_org(body: RegisterOrgRequest, db: AsyncSession = Depends(get_db)):
    """Create a new organization and its admin user. Returns a JWT."""

    # Check if email already taken
    existing = await db.execute(select(User).where(User.email == body.admin_email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create org
    base_slug = _slugify(body.org_name)
    slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
    org = Organization(name=body.org_name, slug=slug)
    db.add(org)
    await db.flush()  # get org.id

    # Create corresponding employee record so chat works
    employee = Employee(
        organization_id=org.id,
        employee_code=f"ADMIN-{uuid.uuid4().hex[:6].upper()}",
        full_name=body.admin_name,
        email=body.admin_email,
        department="Management",
        position="Administrator",
        status="active",
    )
    db.add(employee)
    await db.flush()

    # Create admin user
    user = User(
        organization_id=org.id,
        email=body.admin_email,
        hashed_password=hash_password(body.password),
        role="admin",
        full_name=body.admin_name,
        employee_id=employee.id,
    )
    db.add(user)
    await db.flush()

    token = create_access_token(
        {"sub": str(user.id), "org_id": str(org.id), "role": user.role}
    )
    return TokenResponse(access_token=token)


# ── POST /login ───────────────────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token(
        {"sub": str(user.id), "org_id": str(user.organization_id), "role": user.role}
    )
    return TokenResponse(access_token=token)


# ── POST /invite-user (admin only) ───────────────────────────────────────────


@router.post("/invite-user", response_model=InviteResponse)
async def invite_user(
    body: InviteUserRequest,
    current_user=Depends(require_role("admin", "hr_manager")),
):
    invite_code = secrets.token_urlsafe(16)
    _pending_invites[invite_code] = {
        "org_id": str(current_user.organization_id),
        "email": body.email,
        "role": body.role,
        "full_name": body.full_name,
    }
    return InviteResponse(
        invite_code=invite_code,
        email=body.email,
        message="Invite created. Share the invite_code with the user.",
    )


# ── POST /join ────────────────────────────────────────────────────────────────


@router.post("/join", response_model=TokenResponse, status_code=201)
async def join_org(body: JoinOrgRequest, db: AsyncSession = Depends(get_db)):
    """User joins an organization using an invite code."""
    invite = _pending_invites.pop(body.invite_code, None)
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code")

    # Check email not already registered
    existing = await db.execute(select(User).where(User.email == invite["email"]))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create corresponding employee record so chat works
    employee = Employee(
        organization_id=uuid.UUID(invite["org_id"]),
        employee_code=f"EMP-{uuid.uuid4().hex[:6].upper()}",
        full_name=invite["full_name"],
        email=invite["email"],
        department=None,
        position=None,
        status="active",
    )
    db.add(employee)
    await db.flush()

    user = User(
        organization_id=uuid.UUID(invite["org_id"]),
        email=invite["email"],
        hashed_password=hash_password(body.password),
        role=invite["role"],
        full_name=invite["full_name"],
        employee_id=employee.id,
    )
    db.add(user)
    await db.flush()

    token = create_access_token(
        {"sub": str(user.id), "org_id": invite["org_id"], "role": user.role}
    )
    return TokenResponse(access_token=token)


# ── GET /me ───────────────────────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return current_user

