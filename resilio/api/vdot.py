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

from resilio.schemas.vdot import (
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
    EasyPaceData,
    BreakAnalysis,
    VDOTDecayResult,
    PaceAnalysisResult,
)
from resilio.core.vdot import (
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
    Estimate current VDOT with training continuity awareness.

    Algorithm:
    1. Check for recent race (<90 days) → HIGH confidence
    2. If race >90 days:
       a. Detect training breaks
       b. Apply continuity-aware decay
       c. Validate with recent pace data
       d. Adjust upward if pace data suggests higher fitness
    3. No race: Use pace analysis only (quality workouts → easy runs → error)

    Args:
        lookback_days: Number of days to look back for pace analysis (default: 28)

    Returns:
        VDOTEstimate with current VDOT estimate and supporting data
        VDOTError on failure

    Example:
        >>> estimate = estimate_current_vdot(lookback_days=90)
        >>> if isinstance(estimate, VDOTError):
        ...     print(f"Error: {estimate.message}")
        ... else:
        ...     print(f"Current VDOT: {estimate.estimated_vdot} ({estimate.confidence})")
        ...     print(f"Source: {estimate.source}")
    """
    from datetime import date as dt_date, timedelta
    from pathlib import Path
    from statistics import median

    from resilio.core.paths import get_activities_dir
    from resilio.core.repository import RepositoryIO, ReadOptions
    from resilio.schemas.activity import NormalizedActivity
    from resilio.core.vdot.continuity import detect_training_breaks, calculate_vdot_decay
    from resilio.core.vdot.pace_analysis import analyze_recent_paces
    from resilio.api.profile import get_profile, ProfileError
    from resilio.api.metrics import get_current_metrics, MetricsError

    try:
        # Load activities
        repo = RepositoryIO()
        activities_dir = get_activities_dir()
        activity_files = list(Path(activities_dir).rglob("*.yaml"))

        if not activity_files:
            return VDOTError(
                error_type="not_found",
                message="No activities found. Run 'resilio sync' to import activities from Strava.",
            )

        # Load all activities (we need full history for break detection)
        all_activities: list[NormalizedActivity] = []
        for activity_file in activity_files:
            result = repo.read_yaml(str(activity_file), NormalizedActivity, ReadOptions())
            if isinstance(result, NormalizedActivity):
                if result.sport_type.lower() in ["run", "trail_run", "virtual_run"]:
                    all_activities.append(result)

        if not all_activities:
            return VDOTError(
                error_type="not_found",
                message="No running activities found. Run 'resilio sync' to import activities.",
            )

        # Get profile (for max_hr and race history)
        profile_result = get_profile()
        if isinstance(profile_result, ProfileError):
            return VDOTError(
                error_type="not_found",
                message="Profile not found. Run 'resilio profile create' to create your profile.",
            )
        profile = profile_result

        # Get max_hr for HR-based easy pace detection
        max_hr = None
        vital_signs = getattr(profile, "vital_signs", None)
        candidate_max_hr = getattr(vital_signs, "max_hr", None) if vital_signs else None
        if isinstance(candidate_max_hr, (int, float)) and candidate_max_hr > 0:
            max_hr = int(candidate_max_hr)

        # Step 1: Check for recent PB (<90 days)
        if profile.personal_bests:
            pbs_with_dates = [
                (dist, pb)
                for dist, pb in profile.personal_bests.items()
                if pb.vdot and pb.date
            ]

            if pbs_with_dates:
                # Sort by date descending (most recent first)
                pbs_with_dates.sort(key=lambda x: x[1].date, reverse=True)
                most_recent_dist, most_recent_pb = pbs_with_dates[0]
                race_date = dt_date.fromisoformat(most_recent_pb.date)
                days_since_race = (dt_date.today() - race_date).days

                # Recent PB path (<90 days)
                if days_since_race < 90:
                    return VDOTEstimate(
                        estimated_vdot=int(most_recent_pb.vdot),
                        confidence=ConfidenceLevel.HIGH,
                        source=f"recent_pb ({most_recent_dist} @ {most_recent_pb.time}, {days_since_race} days ago)",
                        supporting_data=[]
                    )

                # Step 2: PB >90 days - apply continuity-aware decay
                # Detect training breaks
                break_analysis = detect_training_breaks(
                    all_activities,
                    race_date,
                    lookback_months=18
                )

                # Get CTL for multi-sport adjustment
                ctl_current = None
                metrics_result = get_current_metrics()
                if not isinstance(metrics_result, MetricsError):
                    ctl_current = metrics_result.ctl.value if hasattr(metrics_result, 'ctl') else None

                # Calculate decay
                decay_result = calculate_vdot_decay(
                    base_vdot=most_recent_pb.vdot,
                    race_date=race_date,
                    break_analysis=break_analysis,
                    ctl_at_race=None,  # TODO: Implement historical CTL estimation
                    ctl_current=ctl_current
                )

                # Step 2c: Validate with recent pace data
                pace_analysis = analyze_recent_paces(
                    all_activities,
                    lookback_days=lookback_days,
                    max_hr=max_hr
                )

                # Adjust upward if pace data suggests higher fitness
                if pace_analysis.implied_vdot_range:
                    pace_min, pace_max = pace_analysis.implied_vdot_range

                    # If decayed VDOT significantly lower than pace suggests
                    if decay_result.decayed_vdot < pace_min - 2:
                        adjusted_vdot = int((decay_result.decayed_vdot + pace_min) / 2)
                        confidence = ConfidenceLevel.MEDIUM
                        source = f"race_decay_adjusted ({break_analysis.continuity_score:.0%} continuity, {len(pace_analysis.quality_workouts + pace_analysis.easy_runs)} pace data points)"
                    else:
                        adjusted_vdot = decay_result.decayed_vdot
                        confidence = decay_result.confidence
                        source = f"race_decay ({break_analysis.continuity_score:.0%} continuity, {int(days_since_race/30.44)} months old)"
                else:
                    adjusted_vdot = decay_result.decayed_vdot
                    confidence = decay_result.confidence
                    source = f"race_decay ({break_analysis.continuity_score:.0%} continuity, {int(days_since_race/30.44)} months old)"

                return VDOTEstimate(
                    estimated_vdot=adjusted_vdot,
                    confidence=confidence,
                    source=source,
                    supporting_data=pace_analysis.quality_workouts  # Convert easy_runs if needed
                )

        # Step 3: No race - use pace analysis only
        pace_analysis = analyze_recent_paces(
            all_activities,
            lookback_days=lookback_days,
            max_hr=max_hr
        )

        # Quality workouts (best signal)
        if pace_analysis.quality_workouts:
            vdots = [w.implied_vdot for w in pace_analysis.quality_workouts]
            estimated_vdot = int(median(vdots))
            confidence = ConfidenceLevel.MEDIUM if len(vdots) >= 3 else ConfidenceLevel.LOW
            source = f"quality_workouts ({len(vdots)} workouts)"

            return VDOTEstimate(
                estimated_vdot=estimated_vdot,
                confidence=confidence,
                source=source,
                supporting_data=pace_analysis.quality_workouts
            )

        # Easy runs (secondary signal)
        if pace_analysis.easy_runs:
            vdots = [e.implied_vdot for e in pace_analysis.easy_runs]
            estimated_vdot = int(median(vdots))
            confidence = ConfidenceLevel.LOW
            source = f"easy_pace_analysis ({len(vdots)} easy runs, HR-detected)"

            # Convert EasyPaceData to WorkoutPaceData for supporting_data
            supporting_data = [
                WorkoutPaceData(
                    date=er.date,
                    workout_type="easy",
                    pace_sec_per_km=er.pace_sec_per_km,
                    implied_vdot=er.implied_vdot
                )
                for er in pace_analysis.easy_runs
            ]

            return VDOTEstimate(
                estimated_vdot=estimated_vdot,
                confidence=confidence,
                source=source,
                supporting_data=supporting_data
            )

        # No data available - require baseline establishment
        return VDOTError(
            error_type="not_found",
            message=(
                "Insufficient data for VDOT estimation. To establish your baseline:\n\n"
                "1. Add a PB: 'resilio profile set-pb --distance 10k --time MM:SS --date YYYY-MM-DD'\n"
                "2. OR run quality workouts with keywords (tempo, threshold, interval)\n"
                "3. OR run easy runs consistently (requires max HR in profile for detection)\n\n"
                "Why no CTL-based estimate? CTL measures training volume, not pace capability.\n"
                "We need actual pace data (PBs or workouts) to estimate your VDOT accurately."
            )
        )

    except Exception as e:
        return VDOTError(error_type="calculation_failed", message=f"VDOT estimation failed: {e}")


# Moved to resilio.core.vdot.pace_analysis
