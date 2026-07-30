"""Stable presentation-neutral API surface."""

from resilio.api.coaching_context import (
    CoachingContextError,
    get_weekly_coach_context,
)
from resilio.api.helpers import get_error_message, handle_error, is_error
from resilio.api.plan import (
    PlanError,
    PlanStatus,
    apply_week_file,
    build_macro_template,
    create_macro_plan,
    create_macro_plan_from_file,
    get_current_plan,
    get_plan_status,
    get_plan_week,
    validate_week_file,
)
from resilio.api.profile import (
    ProfileError,
    create_profile,
    get_profile,
    get_provider_profile_candidates,
    set_goal,
    update_profile,
)
from resilio.api.publication import (
    PublicationError,
    delete_published_workout,
    publish_plan_workouts,
    publish_workout,
)
from resilio.api.reconciliation import (
    ActivityReviewError,
    acknowledge_activity_quarantine_review,
    approve_activity_review,
)
from resilio.api.sync import SyncError, sync_activities
from resilio.api.vdot import (
    VDOTError,
    calculate_vdot_from_race,
    predict_race_times,
)
from resilio.api.weather import WeatherError, get_weekly_weather_forecast
from resilio.core.repository import RepositoryIO

__all__ = [
    "ActivityReviewError",
    "CoachingContextError",
    "PlanError",
    "PlanStatus",
    "ProfileError",
    "PublicationError",
    "RepositoryIO",
    "SyncError",
    "VDOTError",
    "WeatherError",
    "acknowledge_activity_quarantine_review",
    "apply_week_file",
    "approve_activity_review",
    "build_macro_template",
    "calculate_vdot_from_race",
    "create_macro_plan",
    "create_macro_plan_from_file",
    "create_profile",
    "delete_published_workout",
    "get_current_plan",
    "get_error_message",
    "get_plan_status",
    "get_plan_week",
    "get_profile",
    "get_provider_profile_candidates",
    "get_weekly_coach_context",
    "get_weekly_weather_forecast",
    "handle_error",
    "is_error",
    "predict_race_times",
    "publish_plan_workouts",
    "publish_workout",
    "set_goal",
    "sync_activities",
    "update_profile",
    "validate_week_file",
]
