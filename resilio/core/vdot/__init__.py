"""Strict Daniels–Gilbert race-performance calculations."""

from resilio.core.vdot.calculator import (
    VDOTCalculationRangeError,
    calculate_race_equivalents,
    calculate_raw_vdot,
    calculate_vdot,
    format_time_seconds,
    parse_time_string,
)

__all__ = [
    "VDOTCalculationRangeError",
    "calculate_raw_vdot",
    "calculate_race_equivalents",
    "calculate_vdot",
    "format_time_seconds",
    "parse_time_string",
]
