"""
Request ID Middleware — adds a unique trace ID to every request/response.
Used for log correlation across services.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Use existing X-Request-Id (from Cloudflare Worker) or generate one
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))

        # Make available in request state for logging
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
