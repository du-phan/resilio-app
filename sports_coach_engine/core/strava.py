"""
M5 - Strava Integration

Strava OAuth, activity fetch, token refresh, and rate limit handling.
"""

from typing import Any, Optional
from datetime import datetime


def fetch_activities(config: Any, since: Optional[datetime] = None) -> list[Any]:
    """Fetch activities from Strava API."""
    raise NotImplementedError("Strava activity fetch not implemented yet")


def refresh_token(config: Any) -> Any:
    """Refresh Strava OAuth token."""
    raise NotImplementedError("Token refresh not implemented yet")
