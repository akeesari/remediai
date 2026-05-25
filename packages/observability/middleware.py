from __future__ import annotations

from uuid import uuid4

import structlog
import structlog.contextvars
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_ID_HEADER = "X-Correlation-Id"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that binds a correlation_id to every request's log context.

    Reads X-Correlation-Id from the incoming request header; generates a UUID
    if absent.  The same value is echoed back in the response header so callers
    can trace their request across service boundaries.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid4())
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
