"""
M1 - Internal Workflows

Orchestrate multi-step operations by chaining modules in correct sequence.

This module provides workflow functions called by the API layer. It does NOT
handle intent parsing or response formatting (Claude Code does that).
"""

from datetime import date, datetime
from typing import Optional, Any


def run_sync_workflow(
    repo: Any,
    config: Any,
    since: Optional[datetime] = None,
) -> Any:
    """
    Execute full Strava sync pipeline.

    Pipeline: M5 (fetch) → M6 (normalize) → M7 (analyze) → M8 (loads)
              → M9 (metrics) → M11 (adaptations) → M13 (memories)

    Args:
        repo: Repository for file operations
        config: Application configuration with Strava credentials
        since: Only fetch activities after this time (default: last_sync_at)

    Returns:
        SyncWorkflowResult with all processed activities and updated metrics
    """
    raise NotImplementedError("Sync workflow not implemented yet")


def run_metrics_refresh(
    repo: Any,
    target_date: Optional[date] = None,
) -> Any:
    """
    Recompute metrics for a specific date.

    Pipeline: M9 (compute) → M11 (check adaptations)

    Args:
        repo: Repository for file operations
        target_date: Date to compute metrics for (default: today)

    Returns:
        MetricsRefreshResult with computed metrics and delta
    """
    raise NotImplementedError("Metrics refresh workflow not implemented yet")


def run_plan_generation(
    repo: Any,
    goal: Optional[Any] = None,
) -> Any:
    """
    Generate a new training plan.

    Pipeline: M4 (profile) → M9 (current metrics) → M10 (generate)

    Args:
        repo: Repository for file operations
        goal: Optional new goal (uses profile goal if not provided)

    Returns:
        PlanGenerationResult with generated plan
    """
    raise NotImplementedError("Plan generation workflow not implemented yet")


def run_adaptation_check(
    repo: Any,
    target_date: Optional[date] = None,
    wellness_override: Optional[dict] = None,
) -> Any:
    """
    Check if adaptations are needed for a workout.

    Pipeline: M9 (metrics) → M10 (get workout) → M11 (evaluate)

    Args:
        repo: Repository for file operations
        target_date: Date to check adaptations for (default: today)
        wellness_override: Manual wellness signals (fatigue, illness, etc.)

    Returns:
        AdaptationCheckResult with suggestions and any auto-applied changes
    """
    raise NotImplementedError("Adaptation check workflow not implemented yet")


def run_manual_activity_workflow(
    repo: Any,
    sport_type: str,
    duration_minutes: int,
    rpe: Optional[int] = None,
    notes: Optional[str] = None,
    activity_date: Optional[date] = None,
    distance_km: Optional[float] = None,
) -> Any:
    """
    Log a manual activity through full processing pipeline.

    Pipeline: (create) → M6 (normalize) → M7 (analyze) → M8 (loads) → M9 (metrics)

    Args:
        repo: Repository for file operations
        sport_type: Type of sport (running, cycling, etc.)
        duration_minutes: Duration in minutes
        rpe: Optional RPE value
        notes: Optional activity notes
        activity_date: Date of activity (default: today)
        distance_km: Optional distance

    Returns:
        ManualActivityResult with processed activity and updated metrics
    """
    raise NotImplementedError("Manual activity workflow not implemented yet")
