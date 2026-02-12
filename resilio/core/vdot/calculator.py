"""
VDOT calculator - Core VDOT calculation logic.

Implements VDOT (V-dot-O2-max) calculations based on race performance and
training pace generation based on Jack Daniels' methodology.
"""

from typing import Tuple, Optional
from datetime import timedelta

from resilio.schemas.vdot import (
    RaceDistance,
    VDOTResult,
    TrainingPaces,
    RaceEquivalents,
    SixSecondRulePaces,
    ConfidenceLevel,
    PaceUnit,
)
from resilio.core.vdot.tables import (
    VDOT_TABLE,
    VDOT_BY_VALUE,
    get_nearest_vdot_values,
    linear_interpolate,
)


# ============================================================
# RACE DISTANCE CONVERSIONS
# ============================================================


RACE_DISTANCE_KM: dict[RaceDistance, float] = {
    RaceDistance.MILE: 1.609344,
    RaceDistance.FIVE_K: 5.0,
    RaceDistance.TEN_K: 10.0,
    RaceDistance.FIFTEEN_K: 15.0,
    RaceDistance.HALF_MARATHON: 21.0975,
    RaceDistance.MARATHON: 42.195,
}


# ============================================================
# VDOT CALCULATION FROM RACE PERFORMANCE
# ============================================================


def calculate_vdot(race_distance: RaceDistance, race_time_seconds: int) -> VDOTResult:
    """Calculate VDOT from race performance.

    Uses lookup table with linear interpolation to find the VDOT value
    corresponding to a race time.

    Args:
        race_distance: Race distance (mile, 5K, 10K, half, marathon)
        race_time_seconds: Race time in seconds

    Returns:
        VDOTResult with calculated VDOT and metadata

    Raises:
        ValueError: If race time is invalid or out of reasonable range
    """
    if race_time_seconds <= 0:
        raise ValueError(f"Race time must be positive, got {race_time_seconds}")

    # Get field name for this distance in table
    field_map = {
        RaceDistance.MILE: "mile_seconds",
        RaceDistance.FIVE_K: "five_k_seconds",
        RaceDistance.TEN_K: "ten_k_seconds",
        RaceDistance.FIFTEEN_K: "fifteen_k_seconds",
        RaceDistance.HALF_MARATHON: "half_marathon_seconds",
        RaceDistance.MARATHON: "marathon_seconds",
    }

    field_name = field_map.get(race_distance)
    if not field_name:
        raise ValueError(f"Unsupported race distance: {race_distance}")

    # Find the two closest VDOT entries by race time
    best_vdot = None
    min_diff = float("inf")

    for entry in VDOT_TABLE:
        time_value = getattr(entry, field_name, None)
        if time_value is None:
            continue

        diff = abs(time_value - race_time_seconds)
        if diff < min_diff:
            min_diff = diff
            best_vdot = entry.vdot

    if best_vdot is None:
        raise ValueError(f"Could not find VDOT for {race_distance.value} @ {race_time_seconds}s")

    # For more accurate results, interpolate between two nearest VDOTs
    # if race time falls between two table entries
    vdot_lower, vdot_upper = get_nearest_vdot_values(best_vdot)

    entry_lower = VDOT_BY_VALUE[vdot_lower]
    entry_upper = VDOT_BY_VALUE[vdot_upper]

    time_lower = getattr(entry_lower, field_name)
    time_upper = getattr(entry_upper, field_name)

    # Check if we need interpolation
    if time_lower and time_upper and time_lower != time_upper:
        # Interpolate VDOT based on race time
        vdot_interpolated = linear_interpolate(
            race_time_seconds,
            time_lower,
            time_upper,
            vdot_lower,
            vdot_upper,
        )
        # Round to nearest integer
        vdot_final = max(30, min(85, round(vdot_interpolated)))
    else:
        vdot_final = best_vdot

    # Format race time
    formatted_time = format_time_seconds(race_time_seconds)

    return VDOTResult(
        vdot=vdot_final,
        source_race=race_distance,
        source_time_seconds=race_time_seconds,
        source_time_formatted=formatted_time,
        confidence=ConfidenceLevel.HIGH,  # Default high, caller can adjust
    )


# ============================================================
# TRAINING PACE CALCULATION
# ============================================================


def calculate_training_paces(vdot: int, unit: PaceUnit = PaceUnit.MIN_PER_KM) -> TrainingPaces:
    """Calculate all training pace zones from VDOT.

    Args:
        vdot: VDOT value (30-85)
        unit: Pace unit (min/km or min/mile)

    Returns:
        TrainingPaces with all pace zones

    Raises:
        ValueError: If VDOT is out of valid range
    """
    if vdot < 30 or vdot > 85:
        raise ValueError(f"VDOT must be between 30 and 85, got {vdot}")

    # Check if exact entry exists
    if vdot in VDOT_BY_VALUE:
        entry = VDOT_BY_VALUE[vdot]
    else:
        # Interpolate between two nearest VDOTs
        vdot_lower, vdot_upper = get_nearest_vdot_values(vdot)
        entry_lower = VDOT_BY_VALUE[vdot_lower]
        entry_upper = VDOT_BY_VALUE[vdot_upper]

        # Interpolate all pace fields
        entry_data = {}
        for field in [
            "easy_min_sec_per_km",
            "easy_max_sec_per_km",
            "marathon_min_sec_per_km",
            "marathon_max_sec_per_km",
            "threshold_min_sec_per_km",
            "threshold_max_sec_per_km",
            "interval_min_sec_per_km",
            "interval_max_sec_per_km",
            "repetition_min_sec_per_km",
            "repetition_max_sec_per_km",
        ]:
            val_lower = getattr(entry_lower, field)
            val_upper = getattr(entry_upper, field)
            entry_data[field] = round(
                linear_interpolate(vdot, vdot_lower, vdot_upper, val_lower, val_upper)
            )

        # Create a minimal entry object for pace extraction
        from resilio.schemas.vdot import VDOTTableEntry

        entry = VDOTTableEntry(vdot=vdot, **entry_data)

    return TrainingPaces(
        vdot=vdot,
        unit=unit,
        easy_pace_range=(entry.easy_min_sec_per_km, entry.easy_max_sec_per_km),
        marathon_pace_range=(entry.marathon_min_sec_per_km, entry.marathon_max_sec_per_km),
        threshold_pace_range=(entry.threshold_min_sec_per_km, entry.threshold_max_sec_per_km),
        interval_pace_range=(entry.interval_min_sec_per_km, entry.interval_max_sec_per_km),
        repetition_pace_range=(entry.repetition_min_sec_per_km, entry.repetition_max_sec_per_km),
    )


# ============================================================
# RACE TIME PREDICTIONS
# ============================================================


def calculate_race_equivalents(
    race_distance: RaceDistance, race_time_seconds: int
) -> RaceEquivalents:
    """Predict equivalent race times for other distances.

    First calculates VDOT from input race, then uses that VDOT to
    predict times for all other distances.

    Args:
        race_distance: Source race distance
        race_time_seconds: Source race time in seconds

    Returns:
        RaceEquivalents with predictions for all distances
    """
    # Calculate VDOT from race performance
    vdot_result = calculate_vdot(race_distance, race_time_seconds)
    vdot = vdot_result.vdot

    # Get or interpolate table entry
    if vdot in VDOT_BY_VALUE:
        entry = VDOT_BY_VALUE[vdot]
    else:
        vdot_lower, vdot_upper = get_nearest_vdot_values(vdot)
        entry_lower = VDOT_BY_VALUE[vdot_lower]
        entry_upper = VDOT_BY_VALUE[vdot_upper]

        # Interpolate race times
        entry_data = {"vdot": vdot}
        for dist in RaceDistance:
            field_map = {
                RaceDistance.MILE: "mile_seconds",
                RaceDistance.FIVE_K: "five_k_seconds",
                RaceDistance.TEN_K: "ten_k_seconds",
                RaceDistance.FIFTEEN_K: "fifteen_k_seconds",
                RaceDistance.HALF_MARATHON: "half_marathon_seconds",
                RaceDistance.MARATHON: "marathon_seconds",
            }
            field = field_map[dist]
            val_lower = getattr(entry_lower, field, None)
            val_upper = getattr(entry_upper, field, None)
            if val_lower and val_upper:
                entry_data[field] = round(
                    linear_interpolate(vdot, vdot_lower, vdot_upper, val_lower, val_upper)
                )

        # Fill in missing pace fields (required by VDOTTableEntry)
        for field in [
            "easy_min_sec_per_km",
            "easy_max_sec_per_km",
            "marathon_min_sec_per_km",
            "marathon_max_sec_per_km",
            "threshold_min_sec_per_km",
            "threshold_max_sec_per_km",
            "interval_min_sec_per_km",
            "interval_max_sec_per_km",
            "repetition_min_sec_per_km",
            "repetition_max_sec_per_km",
        ]:
            val_lower = getattr(entry_lower, field)
            val_upper = getattr(entry_upper, field)
            entry_data[field] = round(
                linear_interpolate(vdot, vdot_lower, vdot_upper, val_lower, val_upper)
            )

        from resilio.schemas.vdot import VDOTTableEntry

        entry = VDOTTableEntry(**entry_data)

    # Build predictions dictionary
    predictions = {}
    for dist in RaceDistance:
        field_map = {
            RaceDistance.MILE: "mile_seconds",
            RaceDistance.FIVE_K: "five_k_seconds",
            RaceDistance.TEN_K: "ten_k_seconds",
            RaceDistance.FIFTEEN_K: "fifteen_k_seconds",
            RaceDistance.HALF_MARATHON: "half_marathon_seconds",
            RaceDistance.MARATHON: "marathon_seconds",
        }
        time_val = getattr(entry, field_map[dist], None)
        if time_val:
            predictions[dist] = format_time_seconds(time_val)

    return RaceEquivalents(
        vdot=vdot,
        source_race=race_distance,
        source_time_formatted=vdot_result.source_time_formatted,
        confidence=vdot_result.confidence,
        predictions=predictions,
    )


# ============================================================
# SIX-SECOND RULE (FOR NOVICES)
# ============================================================


def apply_six_second_rule(mile_time_seconds: int) -> SixSecondRulePaces:
    """Apply 6-second rule for novice runners without recent race times.

    Rule: R-pace = mile pace, I-pace = R + 6s/400m, T-pace = I + 6s/400m
    Note: Use 7-8 seconds for VDOT 40-50 range.

    Args:
        mile_time_seconds: Mile race time in seconds

    Returns:
        SixSecondRulePaces with estimated training paces
    """
    if mile_time_seconds <= 0:
        raise ValueError("Mile time must be positive")

    # Calculate R-pace (mile pace = 400m pace × 4)
    # Mile = 1609m ≈ 4 × 400m
    r_pace_400m = mile_time_seconds // 4

    # Estimate VDOT range from mile time to determine adjustment
    # Quick lookup to estimate VDOT
    try:
        vdot_result = calculate_vdot(RaceDistance.MILE, mile_time_seconds)
        vdot_est = vdot_result.vdot
    except Exception:
        vdot_est = 45  # Default mid-range

    # Determine adjustment (6, 7, or 8 seconds)
    if 40 <= vdot_est <= 50:
        adjustment = 7  # Use 7 for VDOT 40-50 range
    elif vdot_est < 40:
        adjustment = 8  # Use 8 for slower runners
    else:
        adjustment = 6  # Use 6 for faster runners

    i_pace_400m = r_pace_400m + adjustment
    t_pace_400m = i_pace_400m + adjustment

    # Estimate VDOT range
    vdot_min = max(30, vdot_est - 2)
    vdot_max = min(85, vdot_est + 2)

    return SixSecondRulePaces(
        source_mile_time_seconds=mile_time_seconds,
        source_mile_time_formatted=format_time_seconds(mile_time_seconds),
        r_pace_400m=r_pace_400m,
        i_pace_400m=i_pace_400m,
        t_pace_400m=t_pace_400m,
        adjustment_seconds=adjustment,
        estimated_vdot_range=(vdot_min, vdot_max),
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def format_time_seconds(seconds: int) -> str:
    """Format time in seconds to HH:MM:SS or MM:SS string.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string

    Examples:
        >>> format_time_seconds(150)
        '2:30'
        >>> format_time_seconds(3665)
        '1:01:05'
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def parse_time_string(time_str: str) -> int:
    """Parse time string (HH:MM:SS or MM:SS) to seconds.

    Args:
        time_str: Time string in format "MM:SS" or "HH:MM:SS"

    Returns:
        Time in seconds

    Raises:
        ValueError: If time string is invalid

    Examples:
        >>> parse_time_string("2:30")
        150
        >>> parse_time_string("1:01:05")
        3665
    """
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 2:
            # MM:SS
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        elif len(parts) == 3:
            # HH:MM:SS
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        else:
            raise ValueError(f"Invalid time format: {time_str}")
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid time string '{time_str}': {e}")
