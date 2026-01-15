"""
VDOT module - Training pace calculations based on Jack Daniels' Running Formula.

This module provides computational tools for:
- Calculating VDOT from race performances
- Generating training pace zones (E/M/T/I/R)
- Predicting equivalent race times
- Applying environmental pace adjustments
- Six-second rule for novice runners

Key exports:
    - calculate_vdot: Race time → VDOT
    - calculate_training_paces: VDOT → E/M/T/I/R paces
    - calculate_race_equivalents: Race time → predicted times for all distances
    - apply_six_second_rule: Mile time → estimated training paces
    - adjust_pace_for_conditions: Apply environmental adjustments
"""

from sports_coach_engine.core.vdot.calculator import (
    calculate_vdot,
    calculate_training_paces,
    calculate_race_equivalents,
    apply_six_second_rule,
    parse_time_string,
    format_time_seconds,
)

from sports_coach_engine.core.vdot.adjustments import (
    adjust_pace_for_conditions,
    adjust_pace_for_altitude,
    adjust_pace_for_heat,
    adjust_pace_for_hills,
)

from sports_coach_engine.core.vdot.tables import (
    VDOT_TABLE,
    VDOT_BY_VALUE,
    get_vdot_entry,
)

__all__ = [
    # Calculator functions
    "calculate_vdot",
    "calculate_training_paces",
    "calculate_race_equivalents",
    "apply_six_second_rule",
    "parse_time_string",
    "format_time_seconds",
    # Adjustment functions
    "adjust_pace_for_conditions",
    "adjust_pace_for_altitude",
    "adjust_pace_for_heat",
    "adjust_pace_for_hills",
    # Table access
    "VDOT_TABLE",
    "VDOT_BY_VALUE",
    "get_vdot_entry",
]
