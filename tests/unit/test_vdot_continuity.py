"""
Unit tests for VDOT continuity module - Training break detection and decay calculation.

Tests break detection, continuity scoring, and Daniels' Table 9.2 decay logic.
"""

import pytest
from datetime import date, datetime, timedelta

from sports_coach_engine.core.vdot.continuity import (
    detect_training_breaks,
    calculate_vdot_decay,
    _calculate_short_break_decay,
    _calculate_long_break_decay,
    _calculate_cross_training_adjustment,
)
from sports_coach_engine.schemas.vdot import ConfidenceLevel
from sports_coach_engine.schemas.activity import NormalizedActivity


def create_run(activity_date: date, sport_type: str = "run") -> NormalizedActivity:
    """Helper to create a minimal run activity."""
    return NormalizedActivity(
        id=f"test_{activity_date.isoformat()}",
        source="manual",
        date=activity_date,
        sport_type=sport_type,
        name="Run",
        duration_minutes=30,
        duration_seconds=1800,
        distance_km=5.0,
        elevation_gain_m=0,
        average_hr=None,
        trainer=False,
        manual=False,
        description=None,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


class TestBreakDetection:
    """Tests for training break detection."""

    def test_high_continuity_no_breaks(self):
        """Consistent training (no breaks) should have high continuity score."""
        race_date = date(2026, 1, 1)
        today = date(2026, 2, 4)

        # Create activities: 3 runs per week for 5 weeks
        activities = []
        current = race_date
        while current <= today:
            if current.weekday() in [0, 2, 4]:  # Mon, Wed, Fri
                activities.append(create_run(current))
            current += timedelta(days=1)

        result = detect_training_breaks(activities, race_date, lookback_months=2)

        assert result.continuity_score >= 0.75
        assert result.longest_break_days == 0
        assert len(result.break_periods) == 0

    def test_single_week_break(self):
        """Single week break in the middle should be detected."""
        today = date(2026, 2, 4)
        race_date = date(2026, 1, 6)  # Day of first run

        # Week 1 (Jan 5-11): 3 runs
        # Week 2 (Jan 12-18): 0 runs (BREAK)
        # Week 3 (Jan 19-25): 3 runs
        # Week 4+ (Jan 26-Feb 4): continuing runs
        activities = [
            create_run(date(2026, 1, 6)),  # Week 1
            create_run(date(2026, 1, 8)),
            create_run(date(2026, 1, 10)),
            # Week 2: no runs (BREAK)
            create_run(date(2026, 1, 20)),  # Week 3
            create_run(date(2026, 1, 22)),
            create_run(date(2026, 1, 24)),
            create_run(date(2026, 2, 2)),  # Week 4 - to avoid break after
            create_run(date(2026, 2, 4)),  # Today
        ]

        result = detect_training_breaks(activities, race_date, lookback_months=2)

        assert result.continuity_score < 1.0  # Not perfect continuity
        # Should have 1 break period (week 2)
        assert len(result.break_periods) >= 1
        assert result.longest_break_days <= 14  # At most 1-2 weeks

    def test_multiple_breaks(self):
        """Multiple breaks should all be detected, longest identified."""
        today = date(2026, 2, 4)
        race_date = date(2026, 1, 6)  # Day of first run

        activities = [
            create_run(date(2026, 1, 6)),  # Week 1
            create_run(date(2026, 1, 8)),
            # Week 2: BREAK (~1 week)
            create_run(date(2026, 1, 20)),  # Week 3
            create_run(date(2026, 1, 22)),
            # Weeks 4: BREAK (~1-2 weeks to today)
            create_run(date(2026, 2, 4)),  # Today - end with activity
        ]

        result = detect_training_breaks(activities, race_date, lookback_months=2)

        # Should detect at least the significant breaks
        assert len(result.break_periods) >= 1
        # Longest break should be reasonable (not months)
        assert result.longest_break_days <= 21  # At most 3 weeks


class TestDecayCalculations:
    """Tests for decay percentage calculations."""

    def test_short_break_decay_6_days(self):
        """6-day break should have ~1% decay."""
        decay = _calculate_short_break_decay(6)
        assert 0.5 <= decay <= 1.5

    def test_short_break_decay_14_days(self):
        """14-day break should have ~3% decay."""
        decay = _calculate_short_break_decay(14)
        assert 2.5 <= decay <= 3.5

    def test_short_break_decay_28_days(self):
        """28-day break should have ~7% decay."""
        decay = _calculate_short_break_decay(28)
        assert 6.5 <= decay <= 7.5

    def test_long_break_decay_56_days(self):
        """56-day break (8 weeks) should have 10-12% decay."""
        decay = _calculate_long_break_decay(56)
        assert 10.0 <= decay <= 12.5

    def test_long_break_decay_84_days(self):
        """84-day break (12 weeks) should have 14-16% decay."""
        decay = _calculate_long_break_decay(84)
        assert 14.0 <= decay <= 16.5

    def test_long_break_decay_capped_at_20(self):
        """Very long breaks should cap at 20% decay."""
        decay = _calculate_long_break_decay(365)  # 1 year
        assert decay <= 20.0

    def test_cross_training_adjustment_stable_ctl(self):
        """Stable CTL during break should reduce decay."""
        adjustment = _calculate_cross_training_adjustment(
            break_days=56,
            ctl_at_race=45.0,
            ctl_current=44.0  # Within 10%
        )
        assert adjustment > 0  # Should get reduction

    def test_cross_training_adjustment_dropped_ctl(self):
        """Dropped CTL should not reduce decay."""
        adjustment = _calculate_cross_training_adjustment(
            break_days=56,
            ctl_at_race=45.0,
            ctl_current=30.0  # Dropped >10%
        )
        assert adjustment == 0.0  # No reduction


class TestVDOTDecayResult:
    """Tests for complete VDOT decay calculation."""

    def test_high_continuity_minimal_decay(self):
        """High continuity (≥75% active weeks) should have minimal decay."""
        from sports_coach_engine.schemas.vdot import BreakAnalysis

        race_date = date(2025, 6, 1)  # 8 months ago

        # Mock high continuity
        break_analysis = BreakAnalysis(
            active_weeks=24,
            total_weeks=30,
            break_periods=[],
            longest_break_days=0,
            continuity_score=0.8  # 80% active
        )

        result = calculate_vdot_decay(
            base_vdot=38.0,
            race_date=race_date,
            break_analysis=break_analysis
        )

        # Should have minimal decay (<5%)
        assert result.decayed_vdot >= 36  # ~5% max decay
        assert result.decay_percentage < 5.0
        assert result.confidence == ConfidenceLevel.MEDIUM
        assert "high" in result.reason.lower() and "continuity" in result.reason.lower()

    def test_short_break_daniels_decay(self):
        """Short break (<28 days) should use Daniels Table 9.2."""
        from sports_coach_engine.schemas.vdot import BreakAnalysis, BreakPeriod

        race_date = date(2025, 12, 1)  # 2 months ago

        # 14-day break with moderate continuity
        break_analysis = BreakAnalysis(
            active_weeks=5,
            total_weeks=8,
            break_periods=[
                BreakPeriod(
                    start_date=date(2025, 12, 15),
                    end_date=date(2025, 12, 28),
                    days=14
                )
            ],
            longest_break_days=14,
            continuity_score=0.625  # Below 0.75 threshold
        )

        result = calculate_vdot_decay(
            base_vdot=38.0,
            race_date=race_date,
            break_analysis=break_analysis
        )

        # 14-day break should have ~3% decay
        assert result.decay_percentage >= 2.5
        assert result.decay_percentage <= 3.5
        assert "short break" in result.reason.lower()
        assert "daniels" in result.reason.lower()

    def test_long_break_with_ctl_adjustment(self):
        """Long break with stable CTL should get decay reduction."""
        from sports_coach_engine.schemas.vdot import BreakAnalysis, BreakPeriod

        race_date = date(2025, 10, 1)  # 4 months ago

        # 60-day break
        break_analysis = BreakAnalysis(
            active_weeks=8,
            total_weeks=16,
            break_periods=[
                BreakPeriod(
                    start_date=date(2025, 11, 1),
                    end_date=date(2025, 12, 30),
                    days=60
                )
            ],
            longest_break_days=60,
            continuity_score=0.5
        )

        # Calculate with and without CTL stability
        result_no_ctl = calculate_vdot_decay(
            base_vdot=38.0,
            race_date=race_date,
            break_analysis=break_analysis,
            ctl_at_race=None,
            ctl_current=None
        )

        result_with_ctl = calculate_vdot_decay(
            base_vdot=38.0,
            race_date=race_date,
            break_analysis=break_analysis,
            ctl_at_race=45.0,
            ctl_current=44.0  # Stable
        )

        # With CTL stability should have less decay
        assert result_with_ctl.decay_percentage < result_no_ctl.decay_percentage
        assert "ctl stability" in result_with_ctl.reason.lower()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_vdot_clamped_to_valid_range(self):
        """Decayed VDOT should be clamped to 30-85 range."""
        from sports_coach_engine.schemas.vdot import BreakAnalysis, BreakPeriod

        race_date = date(2024, 1, 1)  # 2 years ago

        # Very long break
        break_analysis = BreakAnalysis(
            active_weeks=2,
            total_weeks=100,
            break_periods=[
                BreakPeriod(
                    start_date=date(2024, 2, 1),
                    end_date=date(2026, 2, 1),
                    days=730
                )
            ],
            longest_break_days=730,
            continuity_score=0.02
        )

        result = calculate_vdot_decay(
            base_vdot=35.0,
            race_date=race_date,
            break_analysis=break_analysis
        )

        # Should be clamped to minimum 30
        assert result.decayed_vdot >= 30
        assert result.decayed_vdot <= 85

    def test_no_activities_after_race(self):
        """No activities after race should detect as complete break."""
        race_date = date(2025, 1, 1)
        activities = []  # No runs after race

        result = detect_training_breaks(activities, race_date, lookback_months=2)

        # Should detect complete break (all weeks inactive)
        assert result.continuity_score == 0.0
        assert result.active_weeks == 0
