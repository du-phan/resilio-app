"""
API layer for weekly analysis and risk assessment.

Wraps core analysis functions with error handling and input validation.
Returns Union[SuccessModel, AnalysisError] for all functions.
"""

from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass
from datetime import date

from sports_coach_engine.core.analysis import (
    analyze_week_adherence,
    validate_intensity_distribution,
    detect_activity_gaps,
    analyze_load_distribution_by_sport,
    check_weekly_capacity,
    assess_current_risk,
    estimate_recovery_window,
    forecast_training_stress,
    assess_taper_status,
)

from sports_coach_engine.schemas.analysis import (
    WeekAdherenceAnalysis,
    IntensityDistributionAnalysis,
    ActivityGapAnalysis,
    LoadDistributionAnalysis,
    WeeklyCapacityCheck,
    CurrentRiskAssessment,
    RecoveryWindowEstimate,
    TrainingStressForecast,
    TaperStatusAssessment,
)


# ============================================================
# ERROR TYPE
# ============================================================


@dataclass
class AnalysisError:
    """Analysis-specific error."""

    error_type: str  # invalid_input, insufficient_data, calculation_failed
    message: str


# ============================================================
# WEEKLY ANALYSIS FUNCTIONS
# ============================================================


def api_analyze_week_adherence(
    week_number: int,
    planned_workouts: List[Dict[str, Any]],
    completed_activities: List[Dict[str, Any]],
) -> Union[WeekAdherenceAnalysis, AnalysisError]:
    """
    Analyze planned vs actual training for a week.

    Args:
        week_number: Week number in plan (1-based)
        planned_workouts: List of planned workout dicts with keys:
            - workout_type (str)
            - duration_minutes (int)
            - distance_km (float)
            - target_systemic_load_au (float)
            - target_lower_body_load_au (float)
        completed_activities: List of completed activity dicts with keys:
            - sport (str)
            - duration_minutes (int)
            - distance_km (float)
            - systemic_load_au (float)
            - lower_body_load_au (float)
            - workout_type (Optional[str])

    Returns:
        WeekAdherenceAnalysis or AnalysisError

    Error types:
        - invalid_input: Week number < 1 or empty lists when analysis expected
        - insufficient_data: Not enough data for meaningful analysis
        - calculation_failed: Unexpected error during calculation
    """
    try:
        # Input validation
        if week_number < 1:
            return AnalysisError(
                error_type="invalid_input",
                message="Week number must be >= 1",
            )

        if not planned_workouts:
            return AnalysisError(
                error_type="insufficient_data",
                message="No planned workouts provided - cannot analyze adherence",
            )

        # Validate planned workout structure
        for i, workout in enumerate(planned_workouts):
            required_keys = ["workout_type", "duration_minutes", "distance_km"]
            missing = [k for k in required_keys if k not in workout]
            if missing:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Planned workout {i} missing required keys: {missing}",
                )

        # Validate completed activity structure
        for i, activity in enumerate(completed_activities):
            required_keys = ["sport", "duration_minutes", "systemic_load_au"]
            missing = [k for k in required_keys if k not in activity]
            if missing:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Completed activity {i} missing required keys: {missing}",
                )

        # Call core function
        result = analyze_week_adherence(
            week_number=week_number,
            planned_workouts=planned_workouts,
            completed_activities=completed_activities,
        )

        return result

    except Exception as e:
        return AnalysisError(
            error_type="calculation_failed",
            message=f"Failed to analyze adherence: {str(e)}",
        )


def api_validate_intensity_distribution(
    activities: List[Dict[str, Any]],
    date_range_days: int = 28,
) -> Union[IntensityDistributionAnalysis, AnalysisError]:
    """
    Validate 80/20 intensity distribution compliance.

    Args:
        activities: List of activity dicts with keys:
            - intensity_zone (str): z1, z2, z3, z4, z5
            - duration_minutes (int)
            - date (str or date)
        date_range_days: Rolling window in days (default 28 for 4 weeks)

    Returns:
        IntensityDistributionAnalysis or AnalysisError

    Error types:
        - invalid_input: Invalid date_range_days or malformed activities
        - insufficient_data: Too few activities for meaningful analysis
        - calculation_failed: Unexpected error during calculation
    """
    try:
        # Input validation
        if date_range_days < 7:
            return AnalysisError(
                error_type="invalid_input",
                message="date_range_days must be >= 7 (minimum one week)",
            )

        if not activities:
            return AnalysisError(
                error_type="insufficient_data",
                message="No activities provided - cannot validate intensity distribution",
            )

        if len(activities) < 3:
            return AnalysisError(
                error_type="insufficient_data",
                message=f"Only {len(activities)} activities provided - need at least 3 for meaningful 80/20 analysis",
            )

        # Validate activity structure
        for i, activity in enumerate(activities):
            required_keys = ["intensity_zone", "duration_minutes"]
            missing = [k for k in required_keys if k not in activity]
            if missing:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Activity {i} missing required keys: {missing}",
                )

            # Validate intensity zone
            zone = activity.get("intensity_zone", "").lower()
            if zone not in ["z1", "z2", "z3", "z4", "z5"]:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Activity {i} has invalid intensity_zone '{zone}' (must be z1-z5)",
                )

        # Call core function
        result = validate_intensity_distribution(
            activities=activities,
            date_range_days=date_range_days,
        )

        return result

    except Exception as e:
        return AnalysisError(
            error_type="calculation_failed",
            message=f"Failed to validate intensity distribution: {str(e)}",
        )


def api_detect_activity_gaps(
    activities: List[Dict[str, Any]],
    min_gap_days: int = 7,
) -> Union[ActivityGapAnalysis, AnalysisError]:
    """
    Detect training breaks/gaps with context.

    Args:
        activities: List of activity dicts with keys:
            - date (str or date)
            - ctl (Optional[float]): CTL on that date
            - notes (Optional[str]): Activity notes (for cause detection)
        min_gap_days: Minimum gap duration to report (default 7)

    Returns:
        ActivityGapAnalysis or AnalysisError

    Error types:
        - invalid_input: min_gap_days < 1 or malformed activities
        - insufficient_data: Too few activities to detect gaps
        - calculation_failed: Unexpected error during calculation
    """
    try:
        # Input validation
        if min_gap_days < 1:
            return AnalysisError(
                error_type="invalid_input",
                message="min_gap_days must be >= 1",
            )

        if not activities:
            return AnalysisError(
                error_type="insufficient_data",
                message="No activities provided - cannot detect gaps",
            )

        if len(activities) < 2:
            return AnalysisError(
                error_type="insufficient_data",
                message="Need at least 2 activities to detect gaps",
            )

        # Validate activity structure
        for i, activity in enumerate(activities):
            if "date" not in activity:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Activity {i} missing required key: date",
                )

        # Call core function
        result = detect_activity_gaps(
            activities=activities,
            min_gap_days=min_gap_days,
        )

        return result

    except Exception as e:
        return AnalysisError(
            error_type="calculation_failed",
            message=f"Failed to detect activity gaps: {str(e)}",
        )


def api_analyze_load_distribution_by_sport(
    activities: List[Dict[str, Any]],
    date_range_days: int = 7,
    sport_priority: str = "equal",
) -> Union[LoadDistributionAnalysis, AnalysisError]:
    """
    Analyze multi-sport load distribution.

    Args:
        activities: List of activity dicts with keys:
            - sport (str): running, climbing, cycling, etc.
            - systemic_load_au (float)
            - lower_body_load_au (float)
            - date (str or date)
        date_range_days: Analysis window in days (default 7)
        sport_priority: "running_primary", "equal", or "other_primary"

    Returns:
        LoadDistributionAnalysis or AnalysisError

    Error types:
        - invalid_input: Invalid date_range_days, sport_priority, or malformed activities
        - insufficient_data: No activities in date range
        - calculation_failed: Unexpected error during calculation
    """
    try:
        # Input validation
        if date_range_days < 1:
            return AnalysisError(
                error_type="invalid_input",
                message="date_range_days must be >= 1",
            )

        valid_priorities = ["running_primary", "equal", "other_primary"]
        if sport_priority not in valid_priorities:
            return AnalysisError(
                error_type="invalid_input",
                message=f"sport_priority must be one of {valid_priorities}",
            )

        if not activities:
            return AnalysisError(
                error_type="insufficient_data",
                message="No activities provided - cannot analyze load distribution",
            )

        # Validate activity structure
        for i, activity in enumerate(activities):
            required_keys = ["sport", "systemic_load_au", "lower_body_load_au"]
            missing = [k for k in required_keys if k not in activity]
            if missing:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Activity {i} missing required keys: {missing}",
                )

        # Call core function
        result = analyze_load_distribution_by_sport(
            activities=activities,
            date_range_days=date_range_days,
            sport_priority=sport_priority,
        )

        return result

    except Exception as e:
        return AnalysisError(
            error_type="calculation_failed",
            message=f"Failed to analyze load distribution: {str(e)}",
        )


def api_check_weekly_capacity(
    week_number: int,
    planned_volume_km: float,
    planned_systemic_load_au: float,
    historical_activities: List[Dict[str, Any]],
) -> Union[WeeklyCapacityCheck, AnalysisError]:
    """
    Validate planned volume against proven capacity.

    Args:
        week_number: Week number in plan
        planned_volume_km: Planned weekly running volume
        planned_systemic_load_au: Planned weekly systemic load
        historical_activities: List of activity dicts with keys:
            - distance_km (float)
            - systemic_load_au (float)
            - date (str or date)

    Returns:
        WeeklyCapacityCheck or AnalysisError

    Error types:
        - invalid_input: Negative values or malformed activities
        - insufficient_data: No historical data to establish capacity
        - calculation_failed: Unexpected error during calculation
    """
    try:
        # Input validation
        if week_number < 1:
            return AnalysisError(
                error_type="invalid_input",
                message="week_number must be >= 1",
            )

        if planned_volume_km < 0:
            return AnalysisError(
                error_type="invalid_input",
                message="planned_volume_km must be non-negative",
            )

        if planned_systemic_load_au < 0:
            return AnalysisError(
                error_type="invalid_input",
                message="planned_systemic_load_au must be non-negative",
            )

        if not historical_activities:
            return AnalysisError(
                error_type="insufficient_data",
                message="No historical activities - cannot establish capacity baseline",
            )

        # Validate activity structure
        for i, activity in enumerate(historical_activities):
            required_keys = ["distance_km", "systemic_load_au"]
            missing = [k for k in required_keys if k not in activity]
            if missing:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Historical activity {i} missing required keys: {missing}",
                )

        # Calculate historical max values from activities
        historical_max_volume_km = max(
            (a.get("distance_km", 0) for a in historical_activities), default=0
        )
        historical_max_systemic_load_au = max(
            (a.get("systemic_load_au", 0) for a in historical_activities), default=0
        )

        # Call core function with calculated max values
        result = check_weekly_capacity(
            week_number=week_number,
            planned_volume_km=planned_volume_km,
            planned_systemic_load_au=planned_systemic_load_au,
            historical_max_volume_km=historical_max_volume_km,
            historical_max_systemic_load_au=historical_max_systemic_load_au,
        )

        return result

    except Exception as e:
        return AnalysisError(
            error_type="calculation_failed",
            message=f"Failed to check weekly capacity: {str(e)}",
        )


# ============================================================
# RISK ASSESSMENT FUNCTIONS
# ============================================================


def api_assess_current_risk(
    current_metrics: Dict[str, Any],
    recent_activities: List[Dict[str, Any]],
    planned_workout: Optional[Dict[str, Any]] = None,
) -> Union[CurrentRiskAssessment, AnalysisError]:
    """
    Holistic injury risk assessment.

    Args:
        current_metrics: Dict with keys:
            - ctl (float)
            - atl (float)
            - tsb (float)
            - acwr (float)
            - readiness (float)
        recent_activities: List of activity dicts (last 7 days) with keys:
            - sport (str)
            - systemic_load_au (float)
            - lower_body_load_au (float)
            - date (str or date)
        planned_workout: Optional workout dict with keys:
            - workout_type (str)
            - expected_load_au (float)

    Returns:
        CurrentRiskAssessment or AnalysisError

    Error types:
        - invalid_input: Missing required metrics or malformed data
        - insufficient_data: Not enough data for risk assessment
        - calculation_failed: Unexpected error during calculation
    """
    try:
        # Input validation - current metrics
        required_metrics = ["ctl", "atl", "tsb", "acwr", "readiness"]
        missing = [k for k in required_metrics if k not in current_metrics]
        if missing:
            return AnalysisError(
                error_type="invalid_input",
                message=f"current_metrics missing required keys: {missing}",
            )

        # Validate metric ranges
        acwr = current_metrics.get("acwr", 0)
        if acwr < 0:
            return AnalysisError(
                error_type="invalid_input",
                message="ACWR cannot be negative",
            )

        readiness = current_metrics.get("readiness", 0)
        if not 0 <= readiness <= 100:
            return AnalysisError(
                error_type="invalid_input",
                message="Readiness must be 0-100",
            )

        # Validate recent activities
        if not recent_activities:
            return AnalysisError(
                error_type="insufficient_data",
                message="No recent activities - cannot assess contextual risk",
            )

        for i, activity in enumerate(recent_activities):
            required_keys = ["sport", "systemic_load_au", "lower_body_load_au"]
            missing = [k for k in required_keys if k not in activity]
            if missing:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Recent activity {i} missing required keys: {missing}",
                )

        # Call core function
        result = assess_current_risk(
            current_metrics=current_metrics,
            recent_activities=recent_activities,
            planned_workout=planned_workout,
        )

        return result

    except Exception as e:
        return AnalysisError(
            error_type="calculation_failed",
            message=f"Failed to assess current risk: {str(e)}",
        )


def api_estimate_recovery_window(
    trigger_type: str,
    current_value: float,
    safe_threshold: float,
) -> Union[RecoveryWindowEstimate, AnalysisError]:
    """
    Estimate recovery timeline to safe zone.

    Args:
        trigger_type: One of: ACWR_ELEVATED, TSB_OVERREACHED, READINESS_LOW, LOWER_BODY_SPIKE
        current_value: Current metric value
        safe_threshold: Safe threshold value

    Returns:
        RecoveryWindowEstimate or AnalysisError

    Error types:
        - invalid_input: Unknown trigger_type or invalid values
        - calculation_failed: Unexpected error during calculation
    """
    try:
        # Input validation
        valid_triggers = [
            "ACWR_ELEVATED",
            "TSB_OVERREACHED",
            "READINESS_LOW",
            "LOWER_BODY_SPIKE",
        ]
        if trigger_type not in valid_triggers:
            return AnalysisError(
                error_type="invalid_input",
                message=f"trigger_type must be one of {valid_triggers}",
            )

        # Call core function
        result = estimate_recovery_window(
            trigger_type=trigger_type,
            current_value=current_value,
            safe_threshold=safe_threshold,
        )

        return result

    except Exception as e:
        return AnalysisError(
            error_type="calculation_failed",
            message=f"Failed to estimate recovery window: {str(e)}",
        )


def api_forecast_training_stress(
    weeks_ahead: int,
    current_metrics: Dict[str, Any],
    planned_weeks: List[Dict[str, Any]],
) -> Union[TrainingStressForecast, AnalysisError]:
    """
    Project future CTL/ATL/TSB/ACWR.

    Args:
        weeks_ahead: Number of weeks to forecast (1-4)
        current_metrics: Dict with keys:
            - ctl (float)
            - atl (float)
            - tsb (float)
            - acwr (float)
            - date (str or date)
        planned_weeks: List of week plan dicts with keys:
            - week_number (int)
            - target_systemic_load_au (float)
            - end_date (str or date)

    Returns:
        TrainingStressForecast or AnalysisError

    Error types:
        - invalid_input: weeks_ahead out of range or malformed data
        - insufficient_data: Not enough planned weeks to forecast
        - calculation_failed: Unexpected error during calculation
    """
    try:
        # Input validation
        if not 1 <= weeks_ahead <= 4:
            return AnalysisError(
                error_type="invalid_input",
                message="weeks_ahead must be 1-4",
            )

        required_metrics = ["ctl", "atl", "tsb", "acwr", "date"]
        missing = [k for k in required_metrics if k not in current_metrics]
        if missing:
            return AnalysisError(
                error_type="invalid_input",
                message=f"current_metrics missing required keys: {missing}",
            )

        if not planned_weeks:
            return AnalysisError(
                error_type="insufficient_data",
                message="No planned weeks provided - cannot forecast",
            )

        if len(planned_weeks) < weeks_ahead:
            return AnalysisError(
                error_type="insufficient_data",
                message=f"Need {weeks_ahead} planned weeks, only {len(planned_weeks)} provided",
            )

        # Validate planned weeks
        for i, week in enumerate(planned_weeks):
            required_keys = ["week_number", "target_systemic_load_au", "end_date"]
            missing = [k for k in required_keys if k not in week]
            if missing:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Planned week {i} missing required keys: {missing}",
                )

        # Call core function
        result = forecast_training_stress(
            weeks_ahead=weeks_ahead,
            current_metrics=current_metrics,
            planned_weeks=planned_weeks,
        )

        return result

    except Exception as e:
        return AnalysisError(
            error_type="calculation_failed",
            message=f"Failed to forecast training stress: {str(e)}",
        )


def api_assess_taper_status(
    race_date: date,
    current_metrics: Dict[str, Any],
    recent_weeks: List[Dict[str, Any]],
) -> Union[TaperStatusAssessment, AnalysisError]:
    """
    Verify taper progression toward race.

    Args:
        race_date: Race date
        current_metrics: Dict with keys:
            - ctl (float)
            - tsb (float)
            - readiness (float)
            - date (str or date)
        recent_weeks: List of week dicts (last 3-4 weeks) with keys:
            - week_number (int)
            - actual_volume_km (float)
            - end_date (str or date)

    Returns:
        TaperStatusAssessment or AnalysisError

    Error types:
        - invalid_input: race_date in past or malformed data
        - insufficient_data: Not enough recent weeks to assess taper
        - calculation_failed: Unexpected error during calculation
    """
    try:
        # Input validation
        from datetime import datetime

        if isinstance(race_date, str):
            race_date = datetime.strptime(race_date, "%Y-%m-%d").date()

        today = date.today()
        if race_date < today:
            return AnalysisError(
                error_type="invalid_input",
                message="race_date cannot be in the past",
            )

        required_metrics = ["ctl", "tsb", "readiness", "date"]
        missing = [k for k in required_metrics if k not in current_metrics]
        if missing:
            return AnalysisError(
                error_type="invalid_input",
                message=f"current_metrics missing required keys: {missing}",
            )

        if not recent_weeks:
            return AnalysisError(
                error_type="insufficient_data",
                message="No recent weeks provided - cannot assess taper",
            )

        if len(recent_weeks) < 2:
            return AnalysisError(
                error_type="insufficient_data",
                message="Need at least 2 recent weeks to assess taper progression",
            )

        # Validate recent weeks
        for i, week in enumerate(recent_weeks):
            required_keys = ["week_number", "actual_volume_km", "end_date"]
            missing = [k for k in required_keys if k not in week]
            if missing:
                return AnalysisError(
                    error_type="invalid_input",
                    message=f"Recent week {i} missing required keys: {missing}",
                )

        # Call core function
        result = assess_taper_status(
            race_date=race_date,
            current_metrics=current_metrics,
            recent_weeks=recent_weeks,
        )

        return result

    except Exception as e:
        return AnalysisError(
            error_type="calculation_failed",
            message=f"Failed to assess taper status: {str(e)}",
        )
