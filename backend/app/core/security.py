"""Security middleware: rate limiting, input validation, security headers."""

import time
import re
from collections import defaultdict
from typing import Callable
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window rate limiter per IP."""

    def __init__(self, app, requests_per_minute: int = 60, requests_per_hour: int = 500):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.rph = requests_per_hour
        self.minute_hits: dict[str, list[float]] = defaultdict(list)
        self.hour_hits: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = self._get_client_ip(request)
        now = time.time()

        # Sliding window minute check
        self.minute_hits[ip] = [t for t in self.minute_hits[ip] if now - t < 60]
        if len(self.minute_hits[ip]) >= self.rpm:
            return Response(
                content='{"detail":"Rate limit exceeded. Try again in a minute."}',
                status_code=429,
                media_type="application/json",
            )
        self.minute_hits[ip].append(now)

        # Sliding window hour check
        self.hour_hits[ip] = [t for t in self.hour_hits[ip] if now - t < 3600]
        if len(self.hour_hits[ip]) >= self.rph:
            return Response(
                content='{"detail":"Hourly rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
            )
        self.hour_hits[ip].append(now)

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# =============================================================================
# INPUT VALIDATION
# =============================================================================

MAX_STRING_LENGTH = 1000
MAX_MESSAGE_LENGTH = 5000
DANGEROUS_PATTERNS = [
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"\b(exec|eval|system|subprocess)\b", re.IGNORECASE),
]


def validate_string_input(value: str, field_name: str, max_length: int = MAX_STRING_LENGTH) -> str:
    """Validate and sanitize a string input."""
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a string")
    value = value.strip()
    if len(value) > max_length:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be at most {max_length} characters",
        )
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(value):
            raise HTTPException(
                status_code=422,
                detail=f"{field_name} contains invalid content",
            )
    return value


def validate_chat_message(message: str) -> str:
    """Validate a chat message with more lenient limits."""
    if not isinstance(message, str):
        raise HTTPException(status_code=422, detail="Message must be a string")
    message = message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Message must be at most {MAX_MESSAGE_LENGTH} characters",
        )
    return message
