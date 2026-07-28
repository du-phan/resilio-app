"""
API Layer - Public interface for Claude Code.

This package provides high-level functions that Claude Code calls to fulfill
user requests. Functions return rich Pydantic models with interpretive context.

Modules:
    - coach: Coaching operations (get_todays_workout, etc.)
    - sync: completed-activity synchronization
    - metrics: Metrics queries with interpretations
    - plan: Training plan operations
    - profile: Athlete profile management
    - vdot: VDOT calculations and training paces
"""

# Re-export all public functions for convenient access
from resilio.api.analysis import (
    AnalysisError,
    api_analyze_load_distribution_by_sport,
    api_assess_current_risk,
    api_assess_taper_status,
    api_check_weekly_capacity,
    api_detect_activity_gaps,
    api_estimate_recovery_window,
    api_forecast_training_stress,
    api_validate_intensity_distribution,
)
from resilio.api.coach import (
    CoachError,
    WeeklyStatus,
    get_todays_workout,
    get_training_status,
    get_weekly_status,
)
from resilio.api.guardrails import (
    GuardrailsError,
    calculate_break_return_plan,
    calculate_masters_recovery,
    calculate_race_recovery,
    calculate_safe_volume_range,
    generate_illness_recovery_plan,
    validate_long_run_limits,
    validate_quality_volume,
    validate_weekly_progression,
)
from resilio.api.helpers import (
    get_error_message,
    handle_error,
    is_error,
)
from resilio.api.historical_backfill import (
    BackfillOperationError,
    dry_run_historical_backfill,
    historical_backfill_status,
    mutate_historical_backfill,
    record_historical_backfill_approval,
)
from resilio.api.metrics import (
    MetricsError,
    get_current_metrics,
    get_intensity_distribution,
    get_readiness,
)
from resilio.api.plan import (
    AcceptResult,
    DeclineResult,
    PlanError,
    PlanWeeksResult,
    accept_suggestion,
    assess_override_risk,
    build_macro_template,
    # Toolkit functions
    calculate_periodization,
    calculate_volume_progression,
    create_macro_plan,
    create_workout,
    decline_suggestion,
    detect_adaptation_triggers,
    export_plan_structure,
    get_current_plan,
    get_pending_suggestions,
    get_plan_weeks,
    regenerate_plan,
    suggest_volume_adjustment,
)
from resilio.api.profile import (
    ProfileError,
    create_profile,
    get_profile,
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
    get_activity_quarantines,
    get_activity_reviews,
    get_external_deletion_reviews,
)
from resilio.api.sync import (
    SyncError,
    sync_activities,
)
from resilio.api.validation import (
    ValidationError,
    api_assess_goal_feasibility,
    api_validate_interval_structure,
    api_validate_plan_structure,
)
from resilio.api.vdot import (
    VDOTError,
    adjust_pace_for_environment,
    apply_six_second_rule_paces,
    calculate_vdot_from_race,
    get_training_paces,
    predict_race_times,
)
from resilio.api.weather import (
    WeatherError,
    get_weekly_weather_forecast,
)
from resilio.core.memory import (
    analyze_memory_patterns,
    get_memories_by_type,
    get_memories_with_tag,
    get_relevant_memories,
    load_memories,
    save_memory,
)
from resilio.core.repository import RepositoryIO

__all__ = [
    # Coach operations
    "get_todays_workout",
    "get_weekly_status",
    "get_training_status",
    "CoachError",
    "WeeklyStatus",
    # Sync operations
    "sync_activities",
    "SyncError",
    # Historical activity backfill
    "dry_run_historical_backfill",
    "historical_backfill_status",
    "record_historical_backfill_approval",
    "mutate_historical_backfill",
    "BackfillOperationError",
    # Metrics operations
    "get_current_metrics",
    "get_readiness",
    "get_intensity_distribution",
    "MetricsError",
    # Plan operations
    "get_current_plan",
    "export_plan_structure",
    "build_macro_template",
    "create_macro_plan",
    "regenerate_plan",
    "get_plan_weeks",
    "get_pending_suggestions",
    "accept_suggestion",
    "decline_suggestion",
    "PlanError",
    "AcceptResult",
    "DeclineResult",
    "PlanWeeksResult",
    # Toolkit functions
    "calculate_periodization",
    "calculate_volume_progression",
    "suggest_volume_adjustment",
    "create_workout",
    "detect_adaptation_triggers",
    "assess_override_risk",
    # Profile operations
    "create_profile",
    "get_profile",
    "update_profile",
    "set_goal",
    "ProfileError",
    # Helper functions
    "is_error",
    "get_error_message",
    "handle_error",
    # VDOT operations
    "calculate_vdot_from_race",
    "get_training_paces",
    "predict_race_times",
    "apply_six_second_rule_paces",
    "adjust_pace_for_environment",
    "VDOTError",
    # Guardrails operations
    "validate_quality_volume",
    "validate_weekly_progression",
    "validate_long_run_limits",
    "calculate_safe_volume_range",
    "calculate_break_return_plan",
    "calculate_masters_recovery",
    "calculate_race_recovery",
    "generate_illness_recovery_plan",
    "GuardrailsError",
    # Analysis operations
    "api_validate_intensity_distribution",
    "api_detect_activity_gaps",
    "api_analyze_load_distribution_by_sport",
    "api_check_weekly_capacity",
    "api_assess_current_risk",
    "api_estimate_recovery_window",
    "api_forecast_training_stress",
    "api_assess_taper_status",
    "AnalysisError",
    # Validation operations
    "api_validate_interval_structure",
    "api_validate_plan_structure",
    "api_assess_goal_feasibility",
    "ValidationError",
    # Weather operations
    "get_weekly_weather_forecast",
    "WeatherError",
    # Workout publication
    "publish_workout",
    "publish_plan_workouts",
    "delete_published_workout",
    "PublicationError",
    # Activity reconciliation review
    "get_activity_reviews",
    "approve_activity_review",
    "get_activity_quarantines",
    "acknowledge_activity_quarantine_review",
    "get_external_deletion_reviews",
    "ActivityReviewError",
    # Memory operations
    "save_memory",
    "load_memories",
    "get_memories_by_type",
    "get_relevant_memories",
    "get_memories_with_tag",
    "analyze_memory_patterns",
    # Repository access
    "RepositoryIO",
]
