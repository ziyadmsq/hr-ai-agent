from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_current_tenant, get_db
from app.models.leave_balance import LeaveBalance
from app.models.leave_request import LeaveRequest
from app.models.user import User
from app.schemas.leave import (
    LeaveBalanceResponse,
    LeaveRequestCreate,
    LeaveRequestListResponse,
    LeaveRequestResponse,
    LeaveRequestUpdate,
)

router = APIRouter(prefix="/leave", tags=["leave"])


def _require_admin(user: User) -> None:
    if user.role not in ("admin", "hr_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR manager access required",
        )


def _get_employee_id(user: User) -> UUID:
    if not user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No employee record linked to this user",
        )
    return user.employee_id


@router.get("/balance", response_model=list[LeaveBalanceResponse])
async def get_leave_balance(
    employee_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get leave balances. Admins can specify employee_id; others see their own."""
    if employee_id and current_user.role in ("admin", "hr_manager"):
        target_employee_id = employee_id
    else:
        target_employee_id = _get_employee_id(current_user)

    result = await db.execute(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == target_employee_id,
            LeaveBalance.organization_id == org_id,
        )
    )
    balances = result.scalars().all()
    response = []
    for b in balances:
        resp = LeaveBalanceResponse.model_validate(b)
        resp.remaining_days = b.total_days - b.used_days
        response.append(resp)
    return response


@router.post("/request", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def submit_leave_request(
    data: LeaveRequestCreate,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Submit a new leave request."""
    emp_id = _get_employee_id(current_user)
    leave_request = LeaveRequest(
        organization_id=org_id,
        employee_id=emp_id,
        leave_type=data.leave_type,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
    )
    db.add(leave_request)
    await db.flush()
    await db.refresh(leave_request)
    return leave_request


@router.get("/requests", response_model=LeaveRequestListResponse)
async def list_leave_requests(
    employee_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List leave requests. Admins see all for org; employees see their own."""
    query = select(LeaveRequest).where(LeaveRequest.organization_id == org_id)

    if current_user.role in ("admin", "hr_manager"):
        if employee_id:
            query = query.where(LeaveRequest.employee_id == employee_id)
    else:
        emp_id = _get_employee_id(current_user)
        query = query.where(LeaveRequest.employee_id == emp_id)

    if status_filter:
        query = query.where(LeaveRequest.status == status_filter)

    result = await db.execute(query)
    requests = result.scalars().all()
    return LeaveRequestListResponse(items=requests, total=len(requests))


@router.patch("/requests/{request_id}", response_model=LeaveRequestResponse)
async def update_leave_request(
    request_id: UUID,
    data: LeaveRequestUpdate,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a leave request (admin/HR only)."""
    _require_admin(current_user)

    result = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.id == request_id,
            LeaveRequest.organization_id == org_id,
        )
    )
    leave_req = result.scalar_one_or_none()
    if not leave_req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")

    if leave_req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update a leave request with status '{leave_req.status}'",
        )

    if data.status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be 'approved' or 'rejected'",
        )

    leave_req.status = data.status
    leave_req.approved_by = current_user.id
    await db.flush()
    await db.refresh(leave_req)
    return leave_req

