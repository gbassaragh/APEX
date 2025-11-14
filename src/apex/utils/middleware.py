"""
FastAPI middleware for request tracking and error handling.
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add unique request ID to each request.

    Request ID is added to response headers and available in request.state.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and add request ID.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint

        Returns:
            Response with X-Request-ID header
        """
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response
