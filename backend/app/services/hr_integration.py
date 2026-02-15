"""HR Integration Service.

Provides an abstract base class for HR operations with two implementations:
1. LocalHRService - uses the local database
2. ExternalHRProxy - forwards requests to an organization's configured external API

Organizations can configure which endpoints use local DB vs external API
via their api_config JSON field.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance
from app.models.leave_request import LeaveRequest


class HRServiceBase(ABC):
    """Abstract base class for HR operations."""

    @abstractmethod
    async def list_employees(
        self, org_id: UUID, page: int = 1, page_size: int = 20, **filters
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    async def get_employee(self, org_id: UUID, employee_id: UUID) -> Optional[dict]:
        ...

    @abstractmethod
    async def get_leave_balances(
        self, org_id: UUID, employee_id: UUID
    ) -> list[dict]:
        ...

    @abstractmethod
    async def create_leave_request(
        self, org_id: UUID, employee_id: UUID, data: dict
    ) -> dict:
        ...


class LocalHRService(HRServiceBase):
    """Implementation that uses the local database."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_employees(
        self, org_id: UUID, page: int = 1, page_size: int = 20, **filters
    ) -> dict[str, Any]:
        query = select(Employee).where(Employee.organization_id == org_id)
        if filters.get("department"):
            query = query.where(Employee.department == filters["department"])
        if filters.get("status"):
            query = query.where(Employee.status == filters["status"])

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        employees = result.scalars().all()

        return {"items": employees, "total": total, "page": page, "page_size": page_size}

    async def get_employee(self, org_id: UUID, employee_id: UUID) -> Optional[Employee]:
        result = await self.db.execute(
            select(Employee).where(
                Employee.id == employee_id, Employee.organization_id == org_id
            )
        )
        return result.scalar_one_or_none()

    async def get_leave_balances(
        self, org_id: UUID, employee_id: UUID
    ) -> list[LeaveBalance]:
        result = await self.db.execute(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == employee_id,
                LeaveBalance.organization_id == org_id,
            )
        )
        return list(result.scalars().all())

    async def create_leave_request(
        self, org_id: UUID, employee_id: UUID, data: dict
    ) -> LeaveRequest:
        leave_request = LeaveRequest(
            organization_id=org_id,
            employee_id=employee_id,
            **data,
        )
        self.db.add(leave_request)
        await self.db.flush()
        return leave_request


class ExternalHRProxy(HRServiceBase):
    """Proxy that forwards requests to an organization's configured external API."""

    def __init__(self, api_config: dict):
        self.base_url = api_config.get("base_url", "")
        self.api_key = api_config.get("api_key", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method, f"{self.base_url}{path}", headers=self.headers, **kwargs
            )
            response.raise_for_status()
            return response.json()

    async def list_employees(
        self, org_id: UUID, page: int = 1, page_size: int = 20, **filters
    ) -> dict[str, Any]:
        params = {"page": page, "page_size": page_size, **filters}
        return await self._request("GET", "/employees", params=params)

    async def get_employee(self, org_id: UUID, employee_id: UUID) -> Optional[dict]:
        return await self._request("GET", f"/employees/{employee_id}")

    async def get_leave_balances(
        self, org_id: UUID, employee_id: UUID
    ) -> list[dict]:
        return await self._request("GET", f"/employees/{employee_id}/leave-balances")

    async def create_leave_request(
        self, org_id: UUID, employee_id: UUID, data: dict
    ) -> dict:
        return await self._request(
            "POST", f"/employees/{employee_id}/leave-requests", json=data
        )


def get_hr_service(db: AsyncSession, api_config: Optional[dict] = None) -> HRServiceBase:
    """Factory function to get the appropriate HR service.

    If the organization has an api_config with hr_api settings,
    use the external proxy. Otherwise, use the local DB.
    """
    if api_config and api_config.get("hr_api", {}).get("enabled"):
        return ExternalHRProxy(api_config["hr_api"])
    return LocalHRService(db)

