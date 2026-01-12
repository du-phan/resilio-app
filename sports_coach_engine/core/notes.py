"""
M7 - Notes & RPE Analyzer

Extract RPE, wellness signals, injury flags from activity notes.
"""

from typing import Any


def analyze_notes(activity: dict) -> Any:
    """Analyze activity notes for RPE, wellness, and flags."""
    raise NotImplementedError("Notes analysis not implemented yet")


def estimate_rpe(activity: dict) -> int:
    """Estimate RPE from HR data or activity characteristics."""
    raise NotImplementedError("RPE estimation not implemented yet")
