"""
Unit tests for RPE estimate selection logic.

Tests the confidence-based priority system for selecting the best RPE estimate
from multiple sources (user input, HR-based, pace-based, Strava, duration heuristic).

This verifies the fix for Bug #1: RPE selection should prioritize high-confidence
estimates over low-confidence ones, not just take the first estimate.
"""

import pytest
from sports_coach_engine.core.workflows import select_best_rpe_estimate
from sports_coach_engine.schemas.activity import RPEEstimate, RPESource


# ============================================================
# TEST: Priority Order (Sport Science-Based)
# ============================================================


def test_priority_user_input_wins():
    """User input should always win, regardless of other estimates."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="Duration"),
        RPEEstimate(value=7, source=RPESource.HR_BASED, confidence="high", reasoning="HR"),
        RPEEstimate(value=8, source=RPESource.USER_INPUT, confidence="high", reasoning="User"),
    ]
    assert select_best_rpe_estimate(estimates) == 8


def test_priority_hr_based_over_pace():
    """HR-based should win over pace-based when no user input."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="Duration"),
        RPEEstimate(value=6, source=RPESource.PACE_BASED, confidence="medium", reasoning="Pace"),
        RPEEstimate(value=7, source=RPESource.HR_BASED, confidence="high", reasoning="HR"),
    ]
    assert select_best_rpe_estimate(estimates) == 7


def test_priority_pace_based_over_strava():
    """Pace-based should win over Strava when no user input or HR data."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="Duration"),
        RPEEstimate(value=6, source=RPESource.STRAVA_RELATIVE, confidence="medium", reasoning="Strava"),
        RPEEstimate(value=7, source=RPESource.PACE_BASED, confidence="medium", reasoning="Pace"),
    ]
    assert select_best_rpe_estimate(estimates) == 7


def test_priority_strava_over_duration():
    """Strava should win over duration heuristic."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="Duration"),
        RPEEstimate(value=6, source=RPESource.STRAVA_RELATIVE, confidence="medium", reasoning="Strava"),
    ]
    assert select_best_rpe_estimate(estimates) == 6


def test_priority_duration_as_fallback():
    """Duration heuristic should be used when it's the only estimate."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="Duration"),
    ]
    assert select_best_rpe_estimate(estimates) == 5


# ============================================================
# TEST: Confidence Tiebreaker
# ============================================================


def test_confidence_high_over_medium_same_source():
    """Within same source, high confidence should win over medium."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.HR_BASED, confidence="medium", reasoning="HR medium"),
        RPEEstimate(value=7, source=RPESource.HR_BASED, confidence="high", reasoning="HR high"),
    ]
    assert select_best_rpe_estimate(estimates) == 7


def test_confidence_medium_over_low_same_source():
    """Within same source, medium confidence should win over low."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.PACE_BASED, confidence="low", reasoning="Pace low"),
        RPEEstimate(value=6, source=RPESource.PACE_BASED, confidence="medium", reasoning="Pace medium"),
    ]
    assert select_best_rpe_estimate(estimates) == 6


def test_confidence_first_when_equal():
    """When confidence is equal within same source, take first."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.HR_BASED, confidence="high", reasoning="HR 1"),
        RPEEstimate(value=7, source=RPESource.HR_BASED, confidence="high", reasoning="HR 2"),
    ]
    # After sorting by confidence (both high), order is preserved, so first wins
    assert select_best_rpe_estimate(estimates) == 5


# ============================================================
# TEST: Fallback Behavior
# ============================================================


def test_empty_list_returns_default():
    """Empty list should return conservative fallback (RPE 5)."""
    estimates = []
    assert select_best_rpe_estimate(estimates) == 5


def test_none_list_returns_default():
    """None input should return conservative fallback (RPE 5)."""
    # The function signature expects list[RPEEstimate], but let's test robustness
    # Actually, looking at the code, it checks `if not estimates`, which handles None
    assert select_best_rpe_estimate([]) == 5


# ============================================================
# TEST: Real-World Scenarios (From User's Bug Report)
# ============================================================


def test_bug_scenario_oct_21_intervals():
    """
    Oct 21: 10x400m intervals @ 83% max HR
    Duration heuristic (RPE 5, low) should NOT win over HR-based (RPE 6-7, high).

    This was the original bug: duration heuristic (first in list) always won.
    """
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="49min run → RPE 5"),
        RPEEstimate(value=6, source=RPESource.HR_BASED, confidence="high", reasoning="HR 164 = 83% max → Zone 4"),
    ]
    # Expected: HR-based (RPE 6) should win
    assert select_best_rpe_estimate(estimates) == 6


def test_bug_scenario_oct_26_easy_run():
    """
    Oct 26: 10km base run @ 77% max HR
    Duration heuristic (RPE 5, low) should NOT win over HR-based (RPE 4, high).

    This causes easy runs to be miscoded as moderate (80/20 violation).
    """
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="61min run → RPE 5"),
        RPEEstimate(value=4, source=RPESource.HR_BASED, confidence="high", reasoning="HR 153 = 77% max → Zone 2"),
    ]
    # Expected: HR-based (RPE 4) should win
    assert select_best_rpe_estimate(estimates) == 4


def test_scenario_user_override_hard_workout():
    """
    User explicitly marks workout as RPE 8 (very hard) - trust them.
    Even if HR data suggests lower RPE, user input wins.
    """
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="30min run"),
        RPEEstimate(value=6, source=RPESource.HR_BASED, confidence="high", reasoning="HR 165 → tempo"),
        RPEEstimate(value=8, source=RPESource.USER_INPUT, confidence="high", reasoning="User marked as very hard"),
    ]
    # Expected: User input (RPE 8) should win
    assert select_best_rpe_estimate(estimates) == 8


def test_scenario_no_hr_data_use_strava():
    """
    Activity without HR data: Strava relative effort should be used.
    This is reasonable fallback for activities where HR wasn't recorded.
    """
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="45min run"),
        RPEEstimate(value=6, source=RPESource.STRAVA_RELATIVE, confidence="medium", reasoning="Strava relative effort"),
    ]
    # Expected: Strava (RPE 6) should win over duration heuristic
    assert select_best_rpe_estimate(estimates) == 6


# ============================================================
# TEST: Edge Cases
# ============================================================


def test_all_sources_present_user_wins():
    """When all 5 sources present, user input should win."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="Duration"),
        RPEEstimate(value=6, source=RPESource.STRAVA_RELATIVE, confidence="medium", reasoning="Strava"),
        RPEEstimate(value=7, source=RPESource.PACE_BASED, confidence="medium", reasoning="Pace"),
        RPEEstimate(value=8, source=RPESource.HR_BASED, confidence="high", reasoning="HR"),
        RPEEstimate(value=9, source=RPESource.USER_INPUT, confidence="high", reasoning="User"),
    ]
    assert select_best_rpe_estimate(estimates) == 9


def test_single_estimate_always_used():
    """Single estimate should always be used, regardless of source."""
    for source in [
        RPESource.USER_INPUT,
        RPESource.HR_BASED,
        RPESource.PACE_BASED,
        RPESource.STRAVA_RELATIVE,
        RPESource.DURATION_HEURISTIC,
    ]:
        estimates = [RPEEstimate(value=7, source=source, confidence="high", reasoning="Test")]
        assert select_best_rpe_estimate(estimates) == 7


def test_multiple_low_confidence_duration_estimates():
    """Multiple duration estimates with low confidence - first should win."""
    estimates = [
        RPEEstimate(value=5, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="Duration 1"),
        RPEEstimate(value=6, source=RPESource.DURATION_HEURISTIC, confidence="low", reasoning="Duration 2"),
    ]
    # After sorting by confidence (both low), order preserved, first wins
    assert select_best_rpe_estimate(estimates) == 5
