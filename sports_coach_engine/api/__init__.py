"""
API Layer - Public interface for Claude Code.

This package provides high-level functions that Claude Code calls to fulfill
user requests. Functions return rich Pydantic models with interpretive context.

Modules:
    - coach: Coaching operations (get_todays_workout, etc.)
    - sync: Strava sync and activity logging
    - metrics: Metrics queries with interpretations
    - plan: Training plan operations
    - profile: Athlete profile management
"""

# Re-export all public functions for convenient access
from sports_coach_engine.api.coach import (
    get_todays_workout,
    get_weekly_status,
    get_training_status,
    CoachError,
    WeeklyStatus,
)

from sports_coach_engine.api.sync import (
    sync_strava,
    log_activity,
    SyncError,
)

from sports_coach_engine.api.metrics import (
    get_current_metrics,
    get_readiness,
    get_intensity_distribution,
    MetricsError,
)

from sports_coach_engine.api.plan import (
    get_current_plan,
    regenerate_plan,
    get_pending_suggestions,
    accept_suggestion,
    decline_suggestion,
    PlanError,
    AcceptResult,
    DeclineResult,
    # Toolkit functions
    calculate_periodization,
    calculate_volume_progression,
    suggest_volume_adjustment,
    create_workout,
    validate_guardrails,
    detect_adaptation_triggers,
    assess_override_risk,
)

from sports_coach_engine.api.profile import (
    get_profile,
    update_profile,
    set_goal,
    ProfileError,
)

__all__ = [
    # Coach operations
    "get_todays_workout",
    "get_weekly_status",
    "get_training_status",
    "CoachError",
    "WeeklyStatus",
    # Sync operations
    "sync_strava",
    "log_activity",
    "SyncError",
    # Metrics operations
    "get_current_metrics",
    "get_readiness",
    "get_intensity_distribution",
    "MetricsError",
    # Plan operations
    "get_current_plan",
    "regenerate_plan",
    "get_pending_suggestions",
    "accept_suggestion",
    "decline_suggestion",
    "PlanError",
    "AcceptResult",
    "DeclineResult",
    # Toolkit functions
    "calculate_periodization",
    "calculate_volume_progression",
    "suggest_volume_adjustment",
    "create_workout",
    "validate_guardrails",
    "detect_adaptation_triggers",
    "assess_override_risk",
    # Profile operations
    "get_profile",
    "update_profile",
    "set_goal",
    "ProfileError",
]
