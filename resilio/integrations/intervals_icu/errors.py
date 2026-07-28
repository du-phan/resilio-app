"""Typed, secret-safe Intervals.icu errors."""

from __future__ import annotations

from typing import Optional


class IntervalsIcuError(Exception):
    """Base error containing only sanitized operational metadata."""

    error_type = "integration"

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        status_code: Optional[int] = None,
        retry_after_seconds: Optional[int] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.operation = operation
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.request_id = request_id

    def __str__(self) -> str:
        fields = [self.args[0], f"operation={self.operation}"]
        if self.status_code is not None:
            fields.append(f"status={self.status_code}")
        if self.retry_after_seconds is not None:
            fields.append(f"retry_after={self.retry_after_seconds}s")
        if self.request_id:
            fields.append(f"request_id={self.request_id}")
        return "; ".join(fields)


class IntervalsAuthenticationError(IntervalsIcuError):
    error_type = "authentication_rejected"


class IntervalsAuthorizationError(IntervalsIcuError):
    error_type = "authorization_rejected"


class IntervalsRateLimitError(IntervalsIcuError):
    error_type = "rate_limited"


class IntervalsTransportError(IntervalsIcuError):
    error_type = "transport"


class IntervalsInvalidPayloadError(IntervalsIcuError):
    error_type = "invalid_payload"


class IntervalsNotFoundError(IntervalsIcuError):
    error_type = "not_found"


class UnsupportedSportError(IntervalsInvalidPayloadError):
    error_type = "unsupported_sport"
