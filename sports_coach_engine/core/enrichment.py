"""
M12 - Data Enrichment

Add interpretive context to raw metrics and workouts.
"""

from typing import Any


def enrich_metrics(raw_metrics: Any) -> Any:
    """Add interpretive context to metrics."""
    raise NotImplementedError("Metrics enrichment not implemented yet")


def enrich_workout(workout: Any, metrics: Any) -> Any:
    """Add rationale and context to workout prescription."""
    raise NotImplementedError("Workout enrichment not implemented yet")
