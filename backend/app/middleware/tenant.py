"""Tenant isolation middleware.

Extracts org_id from the JWT on every authenticated request and stores it
in a request-scoped context variable so that downstream code can use
`get_current_tenant` to filter queries by organization.
"""

from contextvars import ContextVar
from typing import Optional
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_access_token

# Context variable holding the current tenant's org_id for the request
_current_org_id: ContextVar[Optional[UUID]] = ContextVar("current_org_id", default=None)


def get_request_org_id() -> Optional[UUID]:
    """Return the org_id extracted from the JWT for the current request."""
    return _current_org_id.get()


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract org_id from the Authorization header and set it in context.

    This runs on every request. If the request has a valid Bearer token with
    an org_id claim, the org_id is stored in a context variable. Public
    endpoints (no token) simply proceed with org_id = None.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        org_id: Optional[UUID] = None

        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = decode_access_token(token)
                raw_org_id = payload.get("org_id")
                if raw_org_id:
                    org_id = UUID(raw_org_id)
            except (ValueError, Exception):
                # Invalid token — let the endpoint-level auth handle the 401
                pass

        token = _current_org_id.set(org_id)
        try:
            response = await call_next(request)
        finally:
            _current_org_id.reset(token)

        return response

