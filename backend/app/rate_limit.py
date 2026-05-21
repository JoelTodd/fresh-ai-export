"""Helpers for preserving Freshdesk rate-limit context.

Freshdesk returns several proprietary rate-limit headers. The backend exposes
the known headers to the UI and manifest while retaining the original raw names
for debugging.
"""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from time import time

from httpx import Headers

from .schemas import RateLimitInfo


RATE_HEADER_NAMES = {
    "x-ratelimit-total": "limit",
    "x-ratelimit-remaining": "remaining",
    "x-ratelimit-used-currentrequest": "used_current_request",
    "x-ratelimit-reset": "reset",
    "retry-after": "retry_after",
}


def extract_rate_limit(headers: Headers | dict[str, str]) -> RateLimitInfo:
    """Map Freshdesk response headers into the public API schema."""
    raw_headers = {key.lower(): value for key, value in dict(headers).items()}
    values: dict[str, str] = {}
    visible: dict[str, str] = {}
    for header, attr in RATE_HEADER_NAMES.items():
        if header in raw_headers:
            values[attr] = raw_headers[header]
            visible[header] = raw_headers[header]
    return RateLimitInfo(**values, raw=visible)


def retry_after_seconds(value: str | None, default: float = 1.0) -> float:
    """Return a sleep interval for numeric or HTTP-date Retry-After values."""
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, parsed.timestamp() - time())
