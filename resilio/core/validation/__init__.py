"""Validation module - interval structure, plan structure, goal feasibility.

This module provides validation functions for:
- Interval workout structure (Daniels methodology compliance)
- Training plan structure (phases, volume, taper)
- Goal feasibility assessment (VDOT and CTL analysis)
"""

from resilio.core.validation.validation import (
    validate_interval_structure,
    validate_plan_structure,
    assess_goal_feasibility,
)

__all__ = [
    "validate_interval_structure",
    "validate_plan_structure",
    "assess_goal_feasibility",
]
