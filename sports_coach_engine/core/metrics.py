"""
M9 - Metrics Engine

Compute CTL/ATL/TSB, ACWR, readiness, and intensity distribution.
"""

from typing import Any
from datetime import date


def compute_daily_metrics(repo: Any, target_date: date) -> Any:
    """Compute daily metrics for a specific date."""
    raise NotImplementedError("Daily metrics computation not implemented yet")


def compute_readiness(repo: Any, target_date: date) -> Any:
    """Compute readiness score for a specific date."""
    raise NotImplementedError("Readiness computation not implemented yet")
