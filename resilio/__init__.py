"""
Sports Coach Engine - AI-powered adaptive running coach for multi-sport athletes.

This package provides an API layer for Claude Code to deliver personalized coaching
based on multi-sport training load, injury prevention, and evidence-based methodology.

Usage:
    from sports_coach_engine.api import sync_strava, get_todays_workout

    # Sync activities
    result = sync_strava()

    # Get today's workout
    workout = get_todays_workout()

Architecture:
    - api/: Public interface for Claude Code
    - core/: Internal modules (M1-M14)
    - schemas/: Pydantic data models
"""

__version__ = "0.1.0"

# Note: Imports are commented out until modules are implemented
# Re-export public API
# from sports_coach_engine.api.coach import (
#     get_todays_workout,
#     get_weekly_status,
#     get_training_status,
# )
# from sports_coach_engine.api.sync import (
#     sync_strava,
#     log_activity,
# )
# from sports_coach_engine.api.metrics import (
#     get_current_metrics,
#     get_readiness,
# )
# from sports_coach_engine.api.plan import (
#     get_current_plan,
#     regenerate_plan,
#     get_pending_suggestions,
#     accept_suggestion,
#     decline_suggestion,
# )
# from sports_coach_engine.api.profile import (
#     get_profile,
#     update_profile,
#     set_goal,
# )

# Also expose RepositoryIO for direct file access
# from sports_coach_engine.core.repository import RepositoryIO

__all__ = [
    # Coach operations
    # "get_todays_workout",
    # "get_weekly_status",
    # "get_training_status",

    # Sync operations
    # "sync_strava",
    # "log_activity",

    # Metrics operations
    # "get_current_metrics",
    # "get_readiness",

    # Plan operations
    # "get_current_plan",
    # "regenerate_plan",
    # "get_pending_suggestions",
    # "accept_suggestion",
    # "decline_suggestion",

    # Profile operations
    # "get_profile",
    # "update_profile",
    # "set_goal",

    # Direct access
    # "RepositoryIO",
]
