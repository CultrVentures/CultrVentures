"""
Grounding Middleware — enforces hallucination prevention rules on agent outputs.
Checks response payloads for required grounding metadata when serving agent results.
"""

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("cultr.grounding")

# Paths that return agent-generated content (must include grounding metadata)
GROUNDED_PATHS = [
    "/api/v1/agents/",
    "/api/v1/mcp/execute",
]

REQUIRED_GROUNDING_FIELDS = {"source_ref", "confidence", "grounding_status"}


class GroundingMiddleware(BaseHTTPMiddleware):
    """
    Validates that agent-generated responses include grounding metadata.
    Non-grounded responses from agent endpoints are flagged in logs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only check agent-output routes
        path = request.url.path
        if not any(path.startswith(p) for p in GROUNDED_PATHS):
            return response

        # Only check successful JSON responses
        if response.status_code != 200:
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Read and check response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        try:
            data = json.loads(body)
            if isinstance(data, dict) and "result" in data:
                result = data["result"]
                if isinstance(result, dict):
                    missing = REQUIRED_GROUNDING_FIELDS - set(result.keys())
                    if missing:
                        logger.warning(
                            f"Ungrounded agent response on {path}: "
                            f"missing {missing}"
                        )
                        # Add grounding warning to response
                        data["_grounding_warning"] = (
                            f"Missing grounding fields: {list(missing)}"
                        )
                        body = json.dumps(data).encode()
        except (json.JSONDecodeError, KeyError):
            pass

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
