from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_current_tenant, get_db
from app.models.employee import Employee
from app.models.user import User
from app.schemas.employees import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)

router = APIRouter(prefix="/employees", tags=["employees"])


def _require_admin(user: User) -> None:
    if user.role not in ("admin", "hr_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or HR manager access required",
        )


@router.get("/me", response_model=EmployeeResponse)
async def get_my_employee_record(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's employee record."""
    if not current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No employee record linked to this user",
        )
    result = await db.execute(
        select(Employee).where(
            Employee.id == current_user.employee_id,
            Employee.organization_id == current_user.organization_id,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


@router.get("", response_model=EmployeeListResponse)
async def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List employees for the current organization (paginated)."""
    query = select(Employee).where(Employee.organization_id == org_id)
    if department:
        query = query.where(Employee.department == department)
    if status_filter:
        query = query.where(Employee.status == status_filter)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    employees = result.scalars().all()

    return EmployeeListResponse(
        items=employees, total=total, page=page, page_size=page_size
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: UUID,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific employee by ID."""
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id, Employee.organization_id == org_id
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreate,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a new employee record (admin/HR only)."""
    _require_admin(current_user)
    employee = Employee(
        organization_id=org_id,
        full_name=data.full_name,
        email=data.email,
        employee_code=data.employee_code,
        department=data.department,
        position=data.position,
        hire_date=data.hire_date,
        status=data.status,
        metadata_=data.metadata_,
    )
    db.add(employee)
    await db.flush()
    await db.refresh(employee)
    return employee


@router.patch("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: UUID,
    data: EmployeeUpdate,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update an employee record (admin/HR only)."""
    _require_admin(current_user)
    result = await db.execute(
        select(Employee).where(
            Employee.id == employee_id, Employee.organization_id == org_id
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(employee, field, value)

    await db.flush()
    await db.refresh(employee)
    return employee

