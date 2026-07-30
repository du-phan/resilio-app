"""Daniels–Gilbert VDOT race-performance equations.

The coefficients are from Daniels and Gilbert, *Oxygen Power: Performance
Tables for Distance Runners* (1979). Resilio deliberately does not manufacture
E/M/T/I/R training paces: those are edition-specific source-table facts, not
outputs that can be safely reconstructed from the race equation alone.
"""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal

from resilio.schemas.vdot import (
    RaceDistance,
    RaceEquivalents,
    VDOTResult,
)

MINIMUM_SUPPORTED_VDOT = 30.0
MAXIMUM_SUPPORTED_VDOT = 85.0

RACE_DISTANCE_METERS: dict[RaceDistance, float] = {
    RaceDistance.MILE: 1_609.344,
    RaceDistance.FIVE_K: 5_000.0,
    RaceDistance.TEN_K: 10_000.0,
    RaceDistance.HALF_MARATHON: 21_097.5,
    RaceDistance.MARATHON: 42_195.0,
}


class VDOTCalculationRangeError(ValueError):
    """Race performance produces a VDOT outside Resilio's supported range."""


def calculate_raw_vdot(
    race_distance: RaceDistance,
    race_time_seconds: int,
) -> float:
    """Return unrounded VDOT from exact distance and elapsed race time."""
    if race_time_seconds <= 0:
        raise ValueError(f"Race time must be positive, got {race_time_seconds}")
    try:
        distance_meters = RACE_DISTANCE_METERS[race_distance]
    except KeyError as exc:
        raise ValueError(f"Unsupported race distance: {race_distance}") from exc

    elapsed_minutes = race_time_seconds / 60
    velocity_meters_per_minute = distance_meters / elapsed_minutes
    oxygen_cost_ml_per_kg_per_minute = (
        -4.60 + 0.182258 * velocity_meters_per_minute + 0.000104 * velocity_meters_per_minute**2
    )
    sustainable_fraction = (
        0.8
        + 0.1894393 * math.exp(-0.012778 * elapsed_minutes)
        + 0.2989558 * math.exp(-0.1932605 * elapsed_minutes)
    )
    raw_vdot = oxygen_cost_ml_per_kg_per_minute / sustainable_fraction
    if not MINIMUM_SUPPORTED_VDOT <= raw_vdot <= MAXIMUM_SUPPORTED_VDOT:
        raise VDOTCalculationRangeError(
            f"{race_distance.value} time {race_time_seconds}s produces "
            f"VDOT {raw_vdot:.2f}, outside the supported range "
            f"{MINIMUM_SUPPORTED_VDOT:.0f}-{MAXIMUM_SUPPORTED_VDOT:.0f}"
        )
    return raw_vdot


def _rounded_vdot(raw_vdot: float) -> int:
    return int(
        Decimal(str(raw_vdot)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def calculate_vdot(
    race_distance: RaceDistance,
    race_time_seconds: int,
) -> VDOTResult:
    """Calculate a precise and integer-display VDOT from a race."""
    raw_vdot = calculate_raw_vdot(race_distance, race_time_seconds)
    return VDOTResult(
        vdot=_rounded_vdot(raw_vdot),
        vdot_raw=raw_vdot,
        source_race=race_distance,
        source_time_seconds=race_time_seconds,
        source_time_formatted=format_time_seconds(race_time_seconds),
    )


def _race_time_for_vdot_seconds(
    race_distance: RaceDistance,
    target_vdot: float,
) -> int:
    """Invert the monotonic race equation with deterministic bisection."""
    distance_meters = RACE_DISTANCE_METERS[race_distance]

    def unconstrained_vdot(elapsed_seconds: float) -> float:
        elapsed_minutes = elapsed_seconds / 60
        velocity_meters_per_minute = distance_meters / elapsed_minutes
        oxygen_cost = (
            -4.60 + 0.182258 * velocity_meters_per_minute + 0.000104 * velocity_meters_per_minute**2
        )
        sustainable_fraction = (
            0.8
            + 0.1894393 * math.exp(-0.012778 * elapsed_minutes)
            + 0.2989558 * math.exp(-0.1932605 * elapsed_minutes)
        )
        return oxygen_cost / sustainable_fraction

    faster_seconds = 60.0
    slower_seconds = 86_400.0
    if (
        unconstrained_vdot(faster_seconds) < target_vdot
        or unconstrained_vdot(slower_seconds) > target_vdot
    ):
        raise VDOTCalculationRangeError(
            f"Could not bracket {race_distance.value} at VDOT " f"{target_vdot:.2f}"
        )
    for _ in range(100):
        midpoint_seconds = (faster_seconds + slower_seconds) / 2
        if unconstrained_vdot(midpoint_seconds) > target_vdot:
            faster_seconds = midpoint_seconds
        else:
            slower_seconds = midpoint_seconds
    return int(
        Decimal(str((faster_seconds + slower_seconds) / 2)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def calculate_race_equivalents(
    race_distance: RaceDistance,
    race_time_seconds: int,
) -> RaceEquivalents:
    """Predict equation-equivalent performances without table interpolation."""
    result = calculate_vdot(race_distance, race_time_seconds)
    predictions = {
        distance: format_time_seconds(
            race_time_seconds
            if distance == race_distance
            else _race_time_for_vdot_seconds(distance, result.vdot_raw)
        )
        for distance in RaceDistance
    }
    return RaceEquivalents(
        vdot=result.vdot,
        vdot_raw=result.vdot_raw,
        source_race=race_distance,
        source_time_formatted=result.source_time_formatted,
        predictions=predictions,
    )


def format_time_seconds(seconds: int) -> str:
    """Format positive elapsed seconds as MM:SS or HH:MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes}:{remaining_seconds:02d}"


def parse_time_string(time_string: str) -> int:
    """Parse strict MM:SS or HH:MM:SS elapsed time."""
    if not isinstance(time_string, str):
        raise ValueError("Time must be a string")
    normalized = time_string.strip()
    if not re.fullmatch(r"\d+:\d{2}(?::\d{2})?", normalized):
        raise ValueError(f"Invalid time string {time_string!r}; use MM:SS or HH:MM:SS")
    parts = [int(part) for part in normalized.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        if seconds >= 60:
            raise ValueError("Seconds must be between 00 and 59")
        total_seconds = minutes * 60 + seconds
    else:
        hours, minutes, seconds = parts
        if minutes >= 60 or seconds >= 60:
            raise ValueError("Minutes and seconds must be between 00 and 59")
        total_seconds = hours * 3_600 + minutes * 60 + seconds
    if total_seconds <= 0:
        raise ValueError("Time must be positive")
    return total_seconds
