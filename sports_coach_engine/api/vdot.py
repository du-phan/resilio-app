"""
VDOT API - Training pace calculations and race predictions.

Provides high-level functions for Claude Code to:
- Calculate VDOT from race performances
- Generate training pace zones
- Predict equivalent race times
- Apply environmental pace adjustments
- Use six-second rule for novices

This API wraps the core VDOT module with error handling and convenient interfaces.
"""

from typing import Union, Optional
from dataclasses import dataclass

from sports_coach_engine.schemas.vdot import (
    RaceDistance,
    VDOTResult,
    TrainingPaces,
    RaceEquivalents,
    SixSecondRulePaces,
    PaceAdjustment,
    ConditionType,
    PaceUnit,
    ConfidenceLevel,
    VDOTEstimate,
    WorkoutPaceData,
)
from sports_coach_engine.core.vdot import (
    calculate_vdot as core_calculate_vdot,
    calculate_training_paces as core_calculate_paces,
    calculate_race_equivalents as core_calculate_equivalents,
    apply_six_second_rule as core_six_second_rule,
    adjust_pace_for_conditions as core_adjust_pace,
    parse_time_string,
)


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class VDOTError:
    """Error result from VDOT operations."""

    error_type: str  # "invalid_input", "out_of_range", "calculation_failed"
    message: str


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


def calculate_vdot_from_race(
    race_distance: str,
    race_time: str,
    race_date: Optional[str] = None,
) -> Union[VDOTResult, VDOTError]:
    """
    Calculate VDOT from race performance.

    Args:
        race_distance: Race distance ("mile", "5k", "10k", "15k", "half_marathon", "marathon")
        race_time: Race time as string ("MM:SS" or "HH:MM:SS")
        race_date: Optional race date to determine confidence level (ISO format "YYYY-MM-DD")

    Returns:
        VDOTResult on success, VDOTError on failure

    Examples:
        >>> calculate_vdot_from_race("10k", "42:30")
        VDOTResult(vdot=48, source_race='10k', ...)

        >>> calculate_vdot_from_race("half_marathon", "1:30:00", "2026-01-01")
        VDOTResult(vdot=52, source_race='half_marathon', confidence='high', ...)
    """
    try:
        # Validate and convert race distance
        try:
            race_dist = RaceDistance(race_distance.lower())
        except ValueError:
            return VDOTError(
                error_type="invalid_input",
                message=f"Invalid race distance '{race_distance}'. Valid: mile, 5k, 10k, 15k, half_marathon, marathon",
            )

        # Parse race time
        try:
            race_time_seconds = parse_time_string(race_time)
        except ValueError as e:
            return VDOTError(
                error_type="invalid_input", message=f"Invalid race time '{race_time}': {e}"
            )

        # Calculate VDOT
        vdot_result = core_calculate_vdot(race_dist, race_time_seconds)

        # Adjust confidence based on race date if provided
        if race_date:
            from datetime import date as dt_date

            try:
                race_dt = dt_date.fromisoformat(race_date)
                today = dt_date.today()
                days_ago = (today - race_dt).days

                if days_ago <= 14:
                    vdot_result.confidence = ConfidenceLevel.HIGH
                elif days_ago <= 42:  # 6 weeks
                    vdot_result.confidence = ConfidenceLevel.MEDIUM
                else:
                    vdot_result.confidence = ConfidenceLevel.LOW
            except ValueError:
                # Invalid date format - keep default confidence
                pass

        return vdot_result

    except ValueError as e:
        return VDOTError(error_type="calculation_failed", message=f"VDOT calculation failed: {e}")
    except Exception as e:
        return VDOTError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def get_training_paces(
    vdot: int,
    unit: str = "min_per_km",
) -> Union[TrainingPaces, VDOTError]:
    """
    Get training pace zones from VDOT.

    Args:
        vdot: VDOT value (30-85)
        unit: Pace unit ("min_per_km" or "min_per_mile")

    Returns:
        TrainingPaces on success, VDOTError on failure

    Examples:
        >>> get_training_paces(48)
        TrainingPaces(vdot=48, easy_pace_range=(306, 330), ...)

        >>> get_training_paces(55, unit="min_per_mile")
        TrainingPaces(vdot=55, unit="min_per_mile", ...)
    """
    try:
        # Validate VDOT range
        if vdot < 30 or vdot > 85:
            return VDOTError(
                error_type="out_of_range", message=f"VDOT must be between 30 and 85, got {vdot}"
            )

        # Validate unit
        try:
            pace_unit = PaceUnit(unit.lower())
        except ValueError:
            return VDOTError(
                error_type="invalid_input",
                message=f"Invalid unit '{unit}'. Valid: min_per_km, min_per_mile",
            )

        # Calculate paces
        paces = core_calculate_paces(vdot, pace_unit)
        return paces

    except ValueError as e:
        return VDOTError(error_type="calculation_failed", message=f"Pace calculation failed: {e}")
    except Exception as e:
        return VDOTError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def predict_race_times(
    race_distance: str,
    race_time: str,
) -> Union[RaceEquivalents, VDOTError]:
    """
    Predict equivalent race times for other distances.

    Args:
        race_distance: Source race distance ("mile", "5k", "10k", "15k", "half_marathon", "marathon")
        race_time: Source race time ("MM:SS" or "HH:MM:SS")

    Returns:
        RaceEquivalents with predictions for all distances on success, VDOTError on failure

    Examples:
        >>> predict_race_times("10k", "42:30")
        RaceEquivalents(vdot=48, predictions={"5k": "20:15", "half_marathon": "1:32:45", ...})
    """
    try:
        # Validate and convert race distance
        try:
            race_dist = RaceDistance(race_distance.lower())
        except ValueError:
            return VDOTError(
                error_type="invalid_input",
                message=f"Invalid race distance '{race_distance}'. Valid: mile, 5k, 10k, 15k, half_marathon, marathon",
            )

        # Parse race time
        try:
            race_time_seconds = parse_time_string(race_time)
        except ValueError as e:
            return VDOTError(
                error_type="invalid_input", message=f"Invalid race time '{race_time}': {e}"
            )

        # Calculate equivalents
        equivalents = core_calculate_equivalents(race_dist, race_time_seconds)
        return equivalents

    except ValueError as e:
        return VDOTError(error_type="calculation_failed", message=f"Race prediction failed: {e}")
    except Exception as e:
        return VDOTError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def apply_six_second_rule_paces(mile_time: str) -> Union[SixSecondRulePaces, VDOTError]:
    """
    Apply six-second rule for novice runners.

    Use when runner has no recent race but has a mile time.
    Rule: R-pace = mile pace, I-pace = R + 6s/400m, T-pace = I + 6s/400m
    (Adjustment: 7-8 seconds for VDOT 40-50 range)

    Args:
        mile_time: Mile time as string ("M:SS")

    Returns:
        SixSecondRulePaces on success, VDOTError on failure

    Examples:
        >>> apply_six_second_rule_paces("6:00")
        SixSecondRulePaces(r_pace_400m=90, i_pace_400m=96, t_pace_400m=102, ...)
    """
    try:
        # Parse mile time
        try:
            mile_time_seconds = parse_time_string(mile_time)
        except ValueError as e:
            return VDOTError(
                error_type="invalid_input", message=f"Invalid mile time '{mile_time}': {e}"
            )

        # Apply six-second rule
        result = core_six_second_rule(mile_time_seconds)
        return result

    except ValueError as e:
        return VDOTError(
            error_type="calculation_failed", message=f"Six-second rule calculation failed: {e}"
        )
    except Exception as e:
        return VDOTError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def adjust_pace_for_environment(
    base_pace: str,
    condition_type: str,
    severity: float,
) -> Union[PaceAdjustment, VDOTError]:
    """
    Adjust pace for environmental conditions.

    Args:
        base_pace: Base pace as string ("M:SS" per km)
        condition_type: Condition type ("altitude", "heat", "humidity", "hills")
        severity: Severity value (altitude in ft, temp in °C, humidity %, grade %)

    Returns:
        PaceAdjustment on success, VDOTError on failure

    Examples:
        >>> adjust_pace_for_environment("5:00", "altitude", 7000.0)
        PaceAdjustment(adjusted_pace_sec_per_km=330, reason="Altitude effect...", ...)

        >>> adjust_pace_for_environment("4:30", "heat", 30.0)
        PaceAdjustment(adjusted_pace_sec_per_km=288, reason="Heat stress...", ...)
    """
    try:
        # Parse base pace
        try:
            base_pace_seconds = parse_time_string(base_pace)
        except ValueError as e:
            return VDOTError(error_type="invalid_input", message=f"Invalid pace '{base_pace}': {e}")

        # Validate condition type
        try:
            cond_type = ConditionType(condition_type.lower())
        except ValueError:
            return VDOTError(
                error_type="invalid_input",
                message=f"Invalid condition '{condition_type}'. Valid: altitude, heat, humidity, hills",
            )

        # Apply adjustment
        adjustment = core_adjust_pace(base_pace_seconds, cond_type, severity)
        return adjustment

    except ValueError as e:
        return VDOTError(error_type="calculation_failed", message=f"Pace adjustment failed: {e}")
    except Exception as e:
        return VDOTError(error_type="calculation_failed", message=f"Unexpected error: {e}")


def estimate_current_vdot(
    lookback_days: int = 28,
) -> Union[VDOTEstimate, VDOTError]:
    """
    Estimate current VDOT from recent workout paces.

    Analyzes tempo and interval workouts from the last N days to estimate
    current fitness level. This provides a way to compare current fitness
    against historical PBs for progression/regression analysis.

    Detection logic:
    - Tempo workouts: Average pace significantly faster than easy pace
    - Interval workouts: workout_type or keywords in title/description

    Args:
        lookback_days: Number of days to look back (default: 28)

    Returns:
        VDOTEstimate with current VDOT estimate and supporting data

        VDOTError on failure

    Example:
        >>> estimate = estimate_current_vdot(lookback_days=28)
        >>> if isinstance(estimate, VDOTError):
        ...     print(f"Error: {estimate.message}")
        ... else:
        ...     print(f"Current VDOT estimate: {estimate.estimated_vdot} ({estimate.confidence})")
    """
    from datetime import date as dt_date, timedelta
    from pathlib import Path
    from statistics import median

    from sports_coach_engine.core.paths import get_activities_dir
    from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
    from sports_coach_engine.schemas.activity import NormalizedActivity
    from sports_coach_engine.core.vdot.tables import VDOT_TABLE

    try:
        # Load activities
        repo = RepositoryIO()
        activities_dir = get_activities_dir()
        activity_files = list(Path(activities_dir).rglob("*.yaml"))

        if not activity_files:
            return VDOTError(
                error_type="not_found",
                message="No activities found. Run 'sce sync' to import activities from Strava.",
            )

        # Calculate cutoff date
        cutoff_date = dt_date.today() - timedelta(days=lookback_days)

        # Load and filter activities
        activities: list[NormalizedActivity] = []
        for activity_file in activity_files:
            result = repo.read_yaml(str(activity_file), NormalizedActivity, ReadOptions())
            if isinstance(result, NormalizedActivity):
                # Filter by date and sport type
                activity_date = result.date
                if activity_date >= cutoff_date and result.sport_type.lower() == "run":
                    activities.append(result)

        if not activities:
            return VDOTError(
                error_type="not_found",
                message=f"No running activities found in the last {lookback_days} days.",
            )

        # Detect quality workouts (tempo, interval)
        quality_keywords = ["tempo", "threshold", "interval", "track", "speed", "workout"]
        quality_workouts: list[WorkoutPaceData] = []

        for activity in activities:
            # Check for workout keywords
            title = (activity.name or "").lower()
            description = (activity.description or "").lower()
            has_quality_keyword = any(keyword in title or keyword in description for keyword in quality_keywords)

            # Calculate average pace (sec per km)
            if activity.distance_km > 0 and activity.duration_seconds > 0:
                avg_pace_sec_per_km = int(activity.duration_seconds / activity.distance_km)

                # Only consider paces faster than 6:00/km (360 sec/km) as quality efforts
                if has_quality_keyword and avg_pace_sec_per_km < 360:
                    # Find implied VDOT from pace
                    implied_vdot = _find_vdot_from_pace(avg_pace_sec_per_km, "threshold")

                    if implied_vdot:
                        workout_data = WorkoutPaceData(
                            date=activity.date.isoformat(),
                            workout_type="tempo" if "tempo" in title or "threshold" in title else "interval",
                            pace_sec_per_km=avg_pace_sec_per_km,
                            implied_vdot=implied_vdot,
                        )
                        quality_workouts.append(workout_data)

        if not quality_workouts:
            # Fallback to race history when no recent quality workouts
            from sports_coach_engine.api.profile import get_profile, ProfileError

            profile_result = get_profile()
            if isinstance(profile_result, ProfileError):
                return VDOTError(
                    error_type="not_found",
                    message=f"No quality workouts (tempo/interval) found in the last {lookback_days} days. "
                    "Try running a tempo or interval workout first.",
                )

            profile = profile_result
            if profile.race_history:
                # Find most recent race with VDOT and date
                races_with_dates = [
                    (race, race.date)
                    for race in profile.race_history
                    if race.vdot and race.date
                ]

                if races_with_dates:
                    # Sort by date descending (most recent first)
                    races_with_dates.sort(key=lambda x: x[1], reverse=True)
                    most_recent_race, race_date_str = races_with_dates[0]

                    # Calculate age of race
                    race_date = dt_date.fromisoformat(race_date_str)
                    days_since_race = (dt_date.today() - race_date).days
                    months_since_race = days_since_race / 30.44

                    # Apply decay based on age
                    base_vdot = most_recent_race.vdot
                    if months_since_race < 3:
                        decay_factor = 1.0
                        confidence = ConfidenceLevel.HIGH
                    elif months_since_race < 6:
                        decay_factor = 0.97  # 3% decay
                        confidence = ConfidenceLevel.MEDIUM
                    else:
                        # For races 6+ months old, apply progressive decay
                        # 7% at 6 months, up to 15% at 24+ months
                        decay_pct = min(7 + (months_since_race - 6) * 0.5, 15)
                        decay_factor = 1.0 - (decay_pct / 100)
                        confidence = ConfidenceLevel.LOW

                    estimated_vdot = int(round(base_vdot * decay_factor))

                    # Clamp to valid VDOT range
                    estimated_vdot = max(30, min(85, estimated_vdot))

                    return VDOTEstimate(
                        estimated_vdot=estimated_vdot,
                        confidence=confidence,
                        source=f"race_history ({most_recent_race.distance} @ {most_recent_race.time}, {int(months_since_race)} months ago)",
                        supporting_data=[
                            WorkoutPaceData(
                                date=race_date_str,
                                workout_type="race",
                                pace_sec_per_km=0,  # Not applicable for race history
                                implied_vdot=estimated_vdot,
                            )
                        ],
                    )

            # No quality workouts and no race history
            return VDOTError(
                error_type="not_found",
                message=f"No quality workouts (tempo/interval) found in the last {lookback_days} days "
                "and no race history available. Try running a tempo or interval workout first, "
                "or add race results to your profile.",
            )

        # Calculate median VDOT
        vdots = [w.implied_vdot for w in quality_workouts]
        estimated_vdot = int(median(vdots))

        # Determine confidence based on number of data points
        if len(quality_workouts) >= 3:
            confidence = ConfidenceLevel.HIGH
        elif len(quality_workouts) >= 2:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

        # Determine source description
        workout_types = [w.workout_type for w in quality_workouts]
        if "tempo" in workout_types:
            source = "tempo_workouts"
        else:
            source = "interval_workouts"

        return VDOTEstimate(
            estimated_vdot=estimated_vdot,
            confidence=confidence,
            source=source,
            supporting_data=quality_workouts,
        )

    except Exception as e:
        return VDOTError(error_type="calculation_failed", message=f"VDOT estimation failed: {e}")


def _find_vdot_from_pace(pace_sec_per_km: int, pace_type: str = "threshold") -> Optional[int]:
    """
    Find VDOT that corresponds to a given pace.

    Args:
        pace_sec_per_km: Pace in seconds per km
        pace_type: Type of pace ("threshold", "interval", "easy")

    Returns:
        VDOT value, or None if pace is out of range
    """
    from sports_coach_engine.core.vdot.tables import VDOT_TABLE

    # Map pace type to table fields
    pace_field_map = {
        "threshold": ("threshold_min_sec_per_km", "threshold_max_sec_per_km"),
        "interval": ("interval_min_sec_per_km", "interval_max_sec_per_km"),
        "easy": ("easy_min_sec_per_km", "easy_max_sec_per_km"),
    }

    if pace_type not in pace_field_map:
        return None

    min_field, max_field = pace_field_map[pace_type]

    # Find VDOT where pace falls within the range
    for entry in VDOT_TABLE:
        min_pace = getattr(entry, min_field)
        max_pace = getattr(entry, max_field)

        # Check if pace falls within this VDOT's range (with some tolerance)
        if min_pace - 5 <= pace_sec_per_km <= max_pace + 5:
            return entry.vdot

    return None
