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
