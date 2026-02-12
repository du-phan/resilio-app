"""Training continuity detection and VDOT decay calculation.

This module implements break-based VDOT decay following Daniels' Table 9.2 (Return-to-Running),
replacing the flawed time-based decay approach. Decay is tied to actual training breaks, not
elapsed time since race.

Key Principle:
- Continuous training preserves fitness
- Time alone doesn't cause decay; training breaks do
- Multi-sport athletes: CTL stability during breaks reduces decay
"""

from datetime import date, timedelta
from typing import Optional, List
from statistics import median

from resilio.schemas.vdot import (
    BreakAnalysis,
    BreakPeriod,
    VDOTDecayResult,
    ConfidenceLevel,
)
from resilio.schemas.activity import NormalizedActivity
from resilio.utils.dates import get_week_boundaries


def group_by_training_week(
    activities: List[NormalizedActivity],
    start_date: date,
    end_date: date
) -> dict[date, List[NormalizedActivity]]:
    """
    Group activities by training week (Monday-Sunday).

    Args:
        activities: List of activities to group
        start_date: Analysis start date
        end_date: Analysis end date

    Returns:
        Dict mapping week start (Monday) to list of activities in that week
    """
    weeks = {}

    # Find the Monday on or before start_date
    days_since_monday = start_date.weekday()
    current_monday = start_date - timedelta(days=days_since_monday)

    # Iterate through all weeks
    while current_monday <= end_date:
        week_start, week_end = get_week_boundaries(current_monday)

        # Filter activities in this week
        week_activities = [
            a for a in activities
            if week_start <= a.date <= week_end
        ]

        weeks[week_start] = week_activities
        current_monday += timedelta(days=7)

    return weeks


def detect_training_breaks(
    activities: List[NormalizedActivity],
    race_date: date,
    lookback_months: int = 18
) -> BreakAnalysis:
    """
    Detect training breaks (consecutive weeks with no runs) since race.

    Uses Monday-Sunday training week structure. A "break" is consecutive weeks
    with 0 runs. An "active week" has ≥1 run.

    Args:
        activities: All activities (pre-filtered to runs only)
        race_date: Race date to analyze from
        lookback_months: Months to look back from today

    Returns:
        BreakAnalysis with continuity metrics and break periods
    """
    from datetime import date as dt_date

    today = dt_date.today()
    analysis_start = max(race_date, today - timedelta(days=lookback_months * 30))

    # Filter to runs only (should already be filtered, but be explicit)
    runs = [
        a for a in activities
        if a.sport_type.lower() in ["run", "trail_run", "virtual_run"]
        and analysis_start <= a.date <= today
    ]

    # Group by training week
    weeks = group_by_training_week(runs, analysis_start, today)

    # Count active weeks (≥1 run)
    active_weeks = sum(1 for week_activities in weeks.values() if len(week_activities) > 0)
    total_weeks = len(weeks)
    continuity_score = active_weeks / total_weeks if total_weeks > 0 else 0.0

    # Identify break periods (consecutive inactive weeks)
    break_periods: List[BreakPeriod] = []
    sorted_weeks = sorted(weeks.keys())

    break_start = None
    for week_start in sorted_weeks:
        week_activities = weeks[week_start]

        if len(week_activities) == 0:
            # Inactive week
            if break_start is None:
                break_start = week_start
        else:
            # Active week - close any open break
            if break_start is not None:
                week_end = week_start - timedelta(days=1)  # Day before this active week
                days = (week_end - break_start).days + 1

                break_periods.append(BreakPeriod(
                    start_date=break_start,
                    end_date=week_end,
                    days=days
                ))
                break_start = None

    # Close final break if analysis ends during inactive period
    if break_start is not None:
        week_end = today
        days = (week_end - break_start).days + 1
        break_periods.append(BreakPeriod(
            start_date=break_start,
            end_date=week_end,
            days=days
        ))

    # Find longest break
    longest_break_days = max((bp.days for bp in break_periods), default=0)

    return BreakAnalysis(
        active_weeks=active_weeks,
        total_weeks=total_weeks,
        break_periods=break_periods,
        longest_break_days=longest_break_days,
        continuity_score=continuity_score
    )


def _calculate_short_break_decay(days: int) -> float:
    """
    Calculate decay percentage for short breaks (6-28 days).

    Based on Daniels' Table 9.2 (Return-to-Running).

    Args:
        days: Break duration in days

    Returns:
        Decay percentage (0-7%)
    """
    if days < 6:
        return 0.0
    elif days <= 14:
        # 6-14 days: 1-3% decay
        return 1.0 + ((days - 6) / 8) * 2.0  # Linear 1% → 3%
    elif days <= 21:
        # 15-21 days: 3-5% decay
        return 3.0 + ((days - 14) / 7) * 2.0  # Linear 3% → 5%
    elif days <= 28:
        # 22-28 days: 5-7% decay
        return 5.0 + ((days - 21) / 7) * 2.0  # Linear 5% → 7%
    else:
        return 7.0


def _calculate_long_break_decay(days: int) -> float:
    """
    Calculate decay percentage for long breaks (28+ days).

    Based on Daniels' Table 9.2, extended for very long breaks.

    Args:
        days: Break duration in days

    Returns:
        Decay percentage (8-20%)
    """
    if days <= 28:
        return 7.0
    elif days <= 56:  # 4-8 weeks
        # 8-12% decay
        return 8.0 + ((days - 28) / 28) * 4.0  # Linear 8% → 12%
    elif days <= 84:  # 8-12 weeks
        # 12-16% decay
        return 12.0 + ((days - 56) / 28) * 4.0  # Linear 12% → 16%
    else:  # 12+ weeks
        # 16-20% decay (capped)
        return min(16.0 + ((days - 84) / 28) * 2.0, 20.0)


def _calculate_cross_training_adjustment(
    break_days: int,
    ctl_at_race: Optional[float],
    ctl_current: Optional[float]
) -> float:
    """
    Calculate decay reduction if CTL remained stable during break (cross-training).

    Args:
        break_days: Duration of break
        ctl_at_race: CTL at race time (if available)
        ctl_current: Current CTL

    Returns:
        Decay percentage reduction (0-5%)
    """
    if ctl_at_race is None or ctl_current is None:
        return 0.0

    # Check if CTL remained stable (±10%)
    ctl_ratio = ctl_current / ctl_at_race if ctl_at_race > 0 else 0.0
    if not (0.9 <= ctl_ratio <= 1.1):
        return 0.0  # CTL dropped or spiked too much

    # Apply adjustment based on break duration
    if break_days < 6:
        return 0.0
    elif break_days <= 14:
        return 0.5
    elif break_days <= 28:
        return 1.5
    elif break_days <= 56:
        return 3.0
    else:
        return 5.0


def calculate_vdot_decay(
    base_vdot: float,
    race_date: date,
    break_analysis: BreakAnalysis,
    ctl_at_race: Optional[float] = None,
    ctl_current: Optional[float] = None
) -> VDOTDecayResult:
    """
    Calculate VDOT decay using training continuity awareness.

    Three pathways:
    1. High continuity (≥75% active weeks): Minimal time-based decay
    2. Short break (<28 days): Break-based decay (Daniels Table 9.2)
    3. Long break (≥28 days): Progressive decay with multi-sport adjustment

    Args:
        base_vdot: Original race VDOT
        race_date: Race date
        break_analysis: Training continuity analysis
        ctl_at_race: CTL at race time (for multi-sport adjustment)
        ctl_current: Current CTL (for multi-sport adjustment)

    Returns:
        VDOTDecayResult with decayed VDOT and metadata
    """
    from datetime import date as dt_date

    today = dt_date.today()
    days_since_race = (today - race_date).days
    months_since_race = days_since_race / 30.44

    # Pathway 1: High continuity - minimal decay
    if break_analysis.continuity_score >= 0.75:
        if months_since_race < 3:
            decay_pct = 0.0
        elif months_since_race < 6:
            decay_pct = 1.0
        elif months_since_race < 12:
            decay_pct = 2.0
        else:
            decay_pct = 3.0 + (months_since_race - 12) * 0.25

        decay_pct = min(decay_pct, 10.0)  # Cap at 10%
        confidence = ConfidenceLevel.MEDIUM
        reason = f"High training continuity ({break_analysis.continuity_score:.0%} active weeks) - minimal decay"

    # Pathway 2: Short break - Daniels Table 9.2
    elif break_analysis.longest_break_days < 28:
        decay_pct = _calculate_short_break_decay(break_analysis.longest_break_days)
        confidence = ConfidenceLevel.MEDIUM
        reason = f"Short break ({break_analysis.longest_break_days} days) - Daniels Table 9.2 decay"

    # Pathway 3: Long break - progressive with multi-sport adjustment
    else:
        decay_pct = _calculate_long_break_decay(break_analysis.longest_break_days)

        # Apply cross-training adjustment if CTL stable
        adjustment = _calculate_cross_training_adjustment(
            break_analysis.longest_break_days,
            ctl_at_race,
            ctl_current
        )

        if adjustment > 0:
            decay_pct -= adjustment
            decay_pct = max(0.0, decay_pct)  # Don't go negative
            confidence = ConfidenceLevel.LOW
            reason = f"Long break ({break_analysis.longest_break_days} days) with CTL stability - adjusted decay"
        else:
            confidence = ConfidenceLevel.LOW
            reason = f"Long break ({break_analysis.longest_break_days} days) - progressive decay"

    # Apply decay
    decay_factor = 1.0 - (decay_pct / 100.0)
    decayed_vdot = int(round(base_vdot * decay_factor))

    # Clamp to valid range
    decayed_vdot = max(30, min(85, decayed_vdot))

    return VDOTDecayResult(
        base_vdot=base_vdot,
        decayed_vdot=decayed_vdot,
        decay_percentage=decay_pct,
        decay_factor=decay_factor,
        confidence=confidence,
        reason=reason,
        break_analysis=break_analysis
    )
