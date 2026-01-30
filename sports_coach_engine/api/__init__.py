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
    - vdot: VDOT calculations and training paces
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
    export_plan_structure,
    build_macro_template,
    create_macro_plan,
    regenerate_plan,
    get_plan_weeks,
    get_pending_suggestions,
    accept_suggestion,
    decline_suggestion,
    PlanError,
    AcceptResult,
    DeclineResult,
    PlanWeeksResult,
    # Toolkit functions
    calculate_periodization,
    calculate_volume_progression,
    suggest_volume_adjustment,
    create_workout,
    detect_adaptation_triggers,
    assess_override_risk,
)

from sports_coach_engine.api.profile import (
    create_profile,
    get_profile,
    update_profile,
    set_goal,
    ProfileError,
)

from sports_coach_engine.api.helpers import (
    is_error,
    get_error_message,
    handle_error,
)

from sports_coach_engine.api.vdot import (
    calculate_vdot_from_race,
    get_training_paces,
    predict_race_times,
    apply_six_second_rule_paces,
    adjust_pace_for_environment,
    VDOTError,
)

from sports_coach_engine.api.guardrails import (
    validate_quality_volume,
    validate_weekly_progression,
    validate_long_run_limits,
    calculate_safe_volume_range,
    calculate_break_return_plan,
    calculate_masters_recovery,
    calculate_race_recovery,
    generate_illness_recovery_plan,
    GuardrailsError,
)

from sports_coach_engine.api.analysis import (
    api_validate_intensity_distribution,
    api_detect_activity_gaps,
    api_analyze_load_distribution_by_sport,
    api_check_weekly_capacity,
    api_assess_current_risk,
    api_estimate_recovery_window,
    api_forecast_training_stress,
    api_assess_taper_status,
    AnalysisError,
)

from sports_coach_engine.api.validation import (
    api_validate_interval_structure,
    api_validate_plan_structure,
    api_assess_goal_feasibility,
    ValidationError,
)

from sports_coach_engine.core.memory import (
    save_memory,
    load_memories,
    get_memories_by_type,
    get_relevant_memories,
    get_memories_with_tag,
    analyze_memory_patterns,
)

from sports_coach_engine.core.repository import RepositoryIO

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
