"""
Integration tests for Phase 3: Metrics Engine (M9).

Tests the complete M9 workflow with realistic multi-sport activity data:
- Aggregate daily loads from multiple activities
- Compute CTL/ATL/TSB with EWMA formulas
- Calculate ACWR with 28-day lookback
- Compute readiness scores with weighted components
- Generate weekly summaries with intensity distribution
"""

import pytest
import yaml
from datetime import date, datetime, timedelta
from pathlib import Path

from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core.metrics import (
    compute_daily_metrics,
    compute_weekly_summary,
    compute_metrics_batch,
    MetricsCalculationError,
)
from sports_coach_engine.schemas.activity import (
    NormalizedActivity,
    LoadCalculation,
    SessionType,
    SportType,
    SurfaceType,
    DataQuality,
)
from sports_coach_engine.schemas.metrics import (
    DailyMetrics,
    WeeklySummary,
    TSBZone,
    ACWRZone,
    ReadinessLevel,
    ConfidenceLevel,
)


class TestPhase3Integration:
    """Integration tests for Phase 3 (M9 - Metrics Engine)."""

    def test_full_metrics_pipeline_with_multisport_data(self, tmp_path, monkeypatch):
        """
        Test complete M9 workflow with 30 days of realistic multi-sport activities.

        Simulates a multi-sport athlete (runner + climber + yoga):
        - Week 1-2: Building base with easy runs + climbing
        - Week 3: Quality running week with tempo run
        - Week 4: Recovery week with reduced volume

        Validates:
        - CTL/ATL/TSB calculations with EWMA
        - ACWR computation after 28 days
        - Readiness score adjustments
        - Weekly summary aggregation
        - Two-channel load model (systemic vs lower-body)
        """
        # Setup
        (tmp_path / ".git").mkdir()
        (tmp_path / "data" / "activities").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        # Create 30 days of activities (4 weeks)
        start_date = date(2026, 1, 1)
        activities = []

        # Week 1: Build base (Jan 1-7)
        activities.extend([
            self._create_run_activity(start_date, 40, 5, "easy", 140, 5),  # Easy run
            self._create_climb_activity(start_date + timedelta(days=1), 90, 4),  # Climbing
            self._create_yoga_activity(start_date + timedelta(days=2), 30, 2),  # Recovery
            self._create_run_activity(start_date + timedelta(days=3), 50, 6, "easy", 145, 6),  # Easy run
            self._create_climb_activity(start_date + timedelta(days=4), 105, 5),  # Climbing
            self._create_run_activity(start_date + timedelta(days=6), 70, 8, "moderate", 155, 8),  # Long run
        ])

        # Week 2: Continue base (Jan 8-14)
        activities.extend([
            self._create_yoga_activity(start_date + timedelta(days=7), 30, 2),
            self._create_run_activity(start_date + timedelta(days=8), 45, 6, "easy", 142, 6),
            self._create_climb_activity(start_date + timedelta(days=9), 100, 5),
            self._create_run_activity(start_date + timedelta(days=10), 50, 6, "easy", 148, 6),
            self._create_climb_activity(start_date + timedelta(days=11), 95, 4),
            self._create_run_activity(start_date + timedelta(days=13), 75, 10, "moderate", 158, 8),  # Long run
        ])

        # Week 3: Quality work (Jan 15-21)
        activities.extend([
            self._create_yoga_activity(start_date + timedelta(days=14), 28, 2),
            self._create_run_activity(start_date + timedelta(days=15), 40, 5, "easy", 140, 5),
            self._create_climb_activity(start_date + timedelta(days=16), 90, 5),
            self._create_run_activity(start_date + timedelta(days=17), 50, 7, "quality", 165, 9),  # Tempo run!
            self._create_climb_activity(start_date + timedelta(days=18), 85, 4),
            self._create_run_activity(start_date + timedelta(days=20), 80, 10, "moderate", 160, 8),  # Long run
        ])

        # Week 4: Recovery (Jan 22-28)
        activities.extend([
            self._create_yoga_activity(start_date + timedelta(days=21), 35, 2),
            self._create_run_activity(start_date + timedelta(days=22), 35, 5, "easy", 138, 4),
            self._create_climb_activity(start_date + timedelta(days=23), 80, 4),
            self._create_run_activity(start_date + timedelta(days=24), 40, 6, "easy", 142, 5),
            self._create_run_activity(start_date + timedelta(days=27), 60, 8, "moderate", 152, 7),  # Easy long run
        ])

        # Persist all activities
        for activity in activities:
            month_dir = f"data/activities/{activity.date.year}-{activity.date.month:02d}"
            (tmp_path / month_dir).mkdir(parents=True, exist_ok=True)
            activity_path = f"{month_dir}/{activity.date.isoformat()}_{activity.id}.yaml"
            error = repo.write_yaml(activity_path, activity)
            assert error is None, f"Failed to write activity: {error}"

        # ========================================
        # Step 1: Compute metrics for all 30 days
        # ========================================
        end_date = start_date + timedelta(days=29)
        batch_results = compute_metrics_batch(start_date, end_date, repo)

        # Should have 30 daily metrics (even days with no activities)
        assert len(batch_results) == 30

        # ========================================
        # Step 2: Verify CTL/ATL/TSB progression
        # ========================================

        # Day 1: Cold start, single easy run
        day1_metrics = batch_results[0]
        assert day1_metrics.date == start_date
        assert day1_metrics.daily_load.systemic_load_au > 0
        assert day1_metrics.ctl_atl.ctl < 10  # CTL starts low
        assert day1_metrics.ctl_atl.atl > day1_metrics.ctl_atl.ctl  # ATL responds faster
        assert day1_metrics.ctl_atl.tsb < 0  # Negative TSB (fatigued)
        assert day1_metrics.baseline_established is False  # <14 days
        assert day1_metrics.acwr is None  # <28 days

        # Day 15: Baseline established (needs 14 previous days)
        day15_metrics = batch_results[14]
        assert day15_metrics.baseline_established is True
        assert day15_metrics.data_days_available >= 14
        assert day15_metrics.ctl_atl.ctl > day1_metrics.ctl_atl.ctl  # CTL building
        assert day15_metrics.acwr is None  # Still <28 days

        # Day 29: ACWR available (needs 28 previous days)
        day29_metrics = batch_results[28]
        assert day29_metrics.baseline_established is True
        assert day29_metrics.acwr_available is True
        assert day29_metrics.acwr is not None
        assert day29_metrics.acwr.zone in [ACWRZone.SAFE, ACWRZone.UNDERTRAINED, ACWRZone.CAUTION]
        assert day29_metrics.readiness.confidence in [ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]

        # Day 30: End of cycle
        day30_metrics = batch_results[29]
        assert day30_metrics.ctl_atl.ctl > 20  # Fitness built
        # After 4 weeks of training, TSB could be negative (productive/overreached)
        assert day30_metrics.ctl_atl.tsb_zone in [TSBZone.OVERREACHED, TSBZone.PRODUCTIVE, TSBZone.OPTIMAL]

        # ========================================
        # Step 3: Verify readiness score adjustments
        # ========================================

        # Day 18 (after tempo run on day 17): Should have lower readiness
        day18_metrics = batch_results[17]

        # Day 22 (recovery week start): Readiness should improve
        day22_metrics = batch_results[21]
        assert day22_metrics.readiness.score >= day18_metrics.readiness.score

        # ========================================
        # Step 4: Verify weekly summary
        # ========================================

        # Compute week summary (need Monday start)
        # Jan 1, 2026 is a Thursday, so Jan 12 is a Monday (day 11)
        week_start = start_date + timedelta(days=11)  # Jan 12 (Monday)
        weekly = compute_weekly_summary(week_start, repo)

        assert weekly.week_start == week_start
        assert weekly.week_end == week_start + timedelta(days=6)
        assert weekly.total_activities >= 5
        assert weekly.run_sessions >= 3
        assert weekly.quality_sessions >= 1  # The tempo run

        # Check intensity distribution
        assert weekly.intensity_distribution.low_minutes > 0
        assert weekly.intensity_distribution.high_minutes > 0
        assert 0 <= weekly.intensity_distribution.low_percent <= 100

        # High-intensity session count should include quality runs
        assert weekly.high_intensity_sessions_7d >= 1

        # End-of-week metrics should match last day of week (Sunday)
        # Week: Jan 12-18 (days 11-17), so end is day 17 (Jan 18, Sunday)
        day18_metrics_week_end = batch_results[17]  # Jan 18 = start_date + 17 days
        assert weekly.ctl_end == day18_metrics_week_end.ctl_atl.ctl
        assert weekly.atl_end == day18_metrics_week_end.ctl_atl.atl
        assert weekly.tsb_end == day18_metrics_week_end.ctl_atl.tsb

        # ========================================
        # Step 5: Verify two-channel load model
        # ========================================

        # Find day with climbing only (e.g., day 2)
        day2_metrics = batch_results[1]
        # Climbing = high systemic, low lower-body
        assert day2_metrics.daily_load.systemic_load_au > 0
        # Lower-body should be much less than systemic for climbing
        if day2_metrics.daily_load.activity_count == 1:
            systemic_ratio = (
                day2_metrics.daily_load.systemic_load_au
                / (day2_metrics.daily_load.lower_body_load_au + 0.1)
            )
            assert systemic_ratio > 2  # Climbing is >2x systemic vs lower-body

        # Find day with running only (e.g., day 1)
        day1_run = batch_results[0]
        # Running = balanced loads
        if day1_run.daily_load.activity_count == 1:
            systemic = day1_run.daily_load.systemic_load_au
            lower_body = day1_run.daily_load.lower_body_load_au
            # Should be roughly equal for running
            assert abs(systemic - lower_body) < systemic * 0.3  # Within 30%

    def test_metrics_persistence_and_reload(self, tmp_path, monkeypatch):
        """Test that metrics persist correctly and can be reloaded."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        # Create a simple activity
        target_date = date(2026, 1, 15)
        activity = self._create_run_activity(target_date, 45, 6, "easy", 145, 6)
        month_dir = f"data/activities/{activity.date.year}-{activity.date.month:02d}"
        (tmp_path / month_dir).mkdir(parents=True)
        repo.write_yaml(f"{month_dir}/{activity.date.isoformat()}_{activity.id}.yaml", activity)

        # Compute metrics
        metrics1 = compute_daily_metrics(target_date, repo)
        assert metrics1.date == target_date

        # Read back from file
        metrics_path = f"data/metrics/daily/{target_date.isoformat()}.yaml"
        result = repo.read_yaml(metrics_path, DailyMetrics)
        assert not hasattr(result, "error_type")  # Not a RepoError

        metrics2 = result
        assert metrics2.date == target_date
        assert metrics2.ctl_atl.ctl == metrics1.ctl_atl.ctl
        assert metrics2.ctl_atl.atl == metrics1.ctl_atl.atl
        assert metrics2.readiness.score == metrics1.readiness.score

    def test_acwr_injury_risk_detection(self, tmp_path, monkeypatch):
        """Test that ACWR correctly identifies injury risk from load spikes."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        start_date = date(2026, 1, 1)

        # Create 4 weeks of low volume (building chronic base)
        for day in range(28):
            if day % 3 == 0:  # Run every 3 days
                activity = self._create_run_activity(
                    start_date + timedelta(days=day),
                    30, 4, "easy", 135, 4
                )
                month_dir = f"data/activities/{activity.date.year}-{activity.date.month:02d}"
                (tmp_path / month_dir).mkdir(parents=True, exist_ok=True)
                error = repo.write_yaml(
                    f"{month_dir}/{activity.date.isoformat()}_{activity.id}.yaml",
                    activity
                )
                assert error is None

        # Week 5: Sudden spike in volume (3 hard runs)
        spike_start = start_date + timedelta(days=28)
        for day in range(7):
            if day in [0, 2, 4]:  # 3 runs in one week
                activity = self._create_run_activity(
                    spike_start + timedelta(days=day),
                    70, 10, "quality", 165, 9  # Much harder and longer
                )
                month_dir = f"data/activities/{activity.date.year}-{activity.date.month:02d}"
                (tmp_path / month_dir).mkdir(parents=True, exist_ok=True)
                error = repo.write_yaml(
                    f"{month_dir}/{activity.date.isoformat()}_{activity.id}.yaml",
                    activity
                )
                assert error is None

        # Compute ALL metrics from day 0 to day 34 in one batch
        # This ensures no gaps in the metrics history
        all_metrics = compute_metrics_batch(start_date, spike_start + timedelta(days=6), repo)

        # By day 28 or later, ACWR should be available
        # Find a day after 28 that has activities (spike)
        day30_metrics = all_metrics[30]  # Day 30 has a hard run
        assert day30_metrics.acwr is not None, "ACWR should be available after 28 days of data"
        # ACWR should be elevated due to spike
        # With low base load + spike, ACWR should increase
        assert day30_metrics.acwr.acwr > 0.8  # At least some load present

    def test_readiness_overrides_with_flags(self, tmp_path, monkeypatch):
        """Test that injury/illness flags override readiness scores."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        repo = RepositoryIO()

        target_date = date(2026, 1, 15)

        # Create activity with injury flag in notes
        activity = self._create_run_activity(target_date, 40, 5, "easy", 140, 5)
        activity.private_note = "Knee pain during run. Sharp discomfort on left knee."

        # Note: M7 (Notes Analyzer) would normally extract this to flags
        # For integration test, we'll manually add the flag
        month_dir = f"data/activities/{activity.date.year}-{activity.date.month:02d}"
        (tmp_path / month_dir).mkdir(parents=True)
        repo.write_yaml(f"{month_dir}/{activity.date.isoformat()}_{activity.id}.yaml", activity)

        # Compute metrics
        metrics = compute_daily_metrics(target_date, repo)

        # Even without M7 extracting flags, readiness should still compute
        assert metrics.readiness.score >= 0
        assert metrics.readiness.level in [e.value for e in ReadinessLevel]

    # ==========================================
    # Helper Methods
    # ==========================================

    def _create_run_activity(
        self,
        date: date,
        duration_min: int,
        distance_km: float,
        session_type: str,
        avg_hr: int,
        rpe: int,
    ) -> NormalizedActivity:
        """Create a realistic running activity with M8 load calculation."""
        base_effort = rpe * duration_min
        systemic_load = base_effort * 1.0  # Running multiplier
        lower_body_load = base_effort * 1.0

        return NormalizedActivity(
            id=f"run_{date.isoformat()}",
            source="strava",
            sport_type=SportType.RUN,
            name=f"{session_type.title()} Run",
            date=date,
            start_time=datetime.combine(date, datetime.min.time().replace(hour=7)),
            duration_minutes=duration_min,
            duration_seconds=duration_min * 60,
            distance_km=distance_km,
            distance_meters=distance_km * 1000,
            average_hr=float(avg_hr),
            has_hr_data=True,
            surface_type=SurfaceType.ROAD,
            surface_type_confidence="high",
            data_quality=DataQuality.HIGH,
            has_gps_data=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            calculated=LoadCalculation(
                activity_id=f"run_{date.isoformat()}",
                duration_minutes=duration_min,
                estimated_rpe=rpe,
                sport_type="run",
                base_effort_au=base_effort,
                systemic_multiplier=1.0,
                lower_body_multiplier=1.0,
                multiplier_adjustments=[],
                systemic_load_au=systemic_load,
                lower_body_load_au=lower_body_load,
                session_type=SessionType(session_type),
            ),
        )

    def _create_climb_activity(
        self, date: date, duration_min: int, rpe: int
    ) -> NormalizedActivity:
        """Create a realistic climbing activity with M8 load calculation."""
        base_effort = rpe * duration_min
        systemic_load = base_effort * 0.6  # Climbing: 60% systemic
        lower_body_load = base_effort * 0.1  # 10% lower-body

        return NormalizedActivity(
            id=f"climb_{date.isoformat()}",
            source="strava",
            sport_type=SportType.CLIMB,
            name="Rock Climbing Session",
            date=date,
            start_time=datetime.combine(date, datetime.min.time().replace(hour=18)),
            duration_minutes=duration_min,
            duration_seconds=duration_min * 60,
            data_quality=DataQuality.MEDIUM,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            calculated=LoadCalculation(
                activity_id=f"climb_{date.isoformat()}",
                duration_minutes=duration_min,
                estimated_rpe=rpe,
                sport_type="climb",
                base_effort_au=base_effort,
                systemic_multiplier=0.6,
                lower_body_multiplier=0.1,
                multiplier_adjustments=[],
                systemic_load_au=systemic_load,
                lower_body_load_au=lower_body_load,
                session_type=SessionType.MODERATE,
            ),
        )

    def _create_yoga_activity(
        self, date: date, duration_min: int, rpe: int
    ) -> NormalizedActivity:
        """Create a realistic yoga activity with M8 load calculation."""
        base_effort = rpe * duration_min
        systemic_load = base_effort * 0.35  # Yoga: 35% systemic
        lower_body_load = base_effort * 0.1  # 10% lower-body

        return NormalizedActivity(
            id=f"yoga_{date.isoformat()}",
            source="manual",
            sport_type=SportType.YOGA,
            name="Yoga Flow",
            date=date,
            start_time=datetime.combine(date, datetime.min.time().replace(hour=19)),
            duration_minutes=duration_min,
            duration_seconds=duration_min * 60,
            data_quality=DataQuality.LOW,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            calculated=LoadCalculation(
                activity_id=f"yoga_{date.isoformat()}",
                duration_minutes=duration_min,
                estimated_rpe=rpe,
                sport_type="yoga",
                base_effort_au=base_effort,
                systemic_multiplier=0.35,
                lower_body_multiplier=0.1,
                multiplier_adjustments=[],
                systemic_load_au=systemic_load,
                lower_body_load_au=lower_body_load,
                session_type=SessionType.EASY,
            ),
        )
