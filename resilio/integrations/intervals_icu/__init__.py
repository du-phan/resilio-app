"""Strict Intervals.icu integration boundary."""

from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import (
    IntervalsAuthenticationError,
    IntervalsAuthorizationError,
    IntervalsInvalidPayloadError,
    IntervalsNotFoundError,
    IntervalsRateLimitError,
    IntervalsTransportError,
)

__all__ = [
    "IntervalsIcuClient",
    "IntervalsAuthenticationError",
    "IntervalsAuthorizationError",
    "IntervalsInvalidPayloadError",
    "IntervalsNotFoundError",
    "IntervalsRateLimitError",
    "IntervalsTransportError",
]
