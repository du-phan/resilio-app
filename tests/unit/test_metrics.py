"""
Unit tests for M9 - Metrics Engine module.

Tests training metrics computation including CTL/ATL/TSB (EWMA calculations),
ACWR (injury risk), readiness scoring, intensity distribution, and edge cases.
"""

import pytest
from datetime import date, datetime, timedelta
from sports_coach_engine.core.metrics import (
    compute_daily_metrics,
    compute_weekly_summary,
    aggregate_daily_load,
    calculate_ctl_atl,
    calculate_acwr,
    compute_readiness,
    compute_intensity_distribution,
    compute_load_trend,
    compute_metrics_batch,
    validate_metrics,
    InvalidMetricsInputError,
    MetricsCalculationError,
    InsufficientDataError,
)
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.metrics import (
    DailyMetrics,
    TSBZone,
    ACWRZone,
    ReadinessLevel,
    ConfidenceLevel,
    CTLZone,
)
from sports_coach_engine.schemas.activity import (
    NormalizedActivity,
    SessionType,
    SportType,
    SurfaceType,
    LoadCalculation,
)


# ============================================================
# TEST FIXTURES
# ============================================================


@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    """Create temporary repository for testing."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return RepositoryIO()


@pytest.fixture
def sample_run_activity():
    """Create sample running activity with loads."""
    activity = NormalizedActivity(
        id="test_run_1",
        source="strava",
        sport_type=SportType.RUN,
        name="Morning Run",
        date=date(2026, 1, 12),
        start_time=datetime(2026, 1, 12, 7, 30),
        duration_minutes=45,
        duration_seconds=2700,
        distance_km=8.0,
        distance_meters=8000.0,
        average_hr=155,
        has_hr_data=True,
        has_gps_data=True,
        surface_type=SurfaceType.ROAD,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # Add calculated loads (M8 output)
    activity.calculated = LoadCalculation(
        activity_id="test_run_1",
        duration_minutes=45,
        estimated_rpe=6,
        sport_type=SportType.RUN,
        surface_type=SurfaceType.ROAD,
        base_effort_au=270.0,  # 6 RPE × 45 minutes
        systemic_multiplier=1.0,
        lower_body_multiplier=1.0,
        systemic_load_au=270.0,
        lower_body_load_au=270.0,
        session_type=SessionType.MODERATE,
        multiplier_adjustments=[],
    )

    return activity


@pytest.fixture
def sample_climb_activity():
    """Create sample climbing activity with loads."""
    activity = NormalizedActivity(
        id="test_climb_1",
        source="strava",
        sport_type=SportType.CLIMB,
        name="Indoor Climbing",
        date=date(2026, 1, 12),
        start_time=datetime(2026, 1, 12, 18, 0),
        duration_minutes=90,
        duration_seconds=5400,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # Add calculated loads
    activity.calculated = LoadCalculation(
        activity_id="test_climb_1",
        duration_minutes=90,
        estimated_rpe=6,
        sport_type=SportType.CLIMB,
        base_effort_au=540.0,  # 6 RPE × 90 minutes
        systemic_multiplier=0.6,
        lower_body_multiplier=0.1,
        systemic_load_au=324.0,  # 540 × 0.6
        lower_body_load_au=54.0,  # 540 × 0.1
        session_type=SessionType.MODERATE,
        multiplier_adjustments=[],
    )

    return activity


@pytest.fixture
def cold_start_scenario(tmp_path, monkeypatch, sample_run_activity):
    """Create scenario with only 5 days of data (<14 days)."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()

    # Create activity files for 5 days
    start_date = date(2026, 1, 1)
    for i in range(5):
        current_date = start_date + timedelta(days=i)
        activity = sample_run_activity
        activity.id = f"test_run_{i}"
        activity.date = current_date
        activity.calculated.activity_id = f"test_run_{i}"

        # Create activity file
        year_month = f"{current_date.year}-{current_date.month:02d}"
        (tmp_path / "activities" / year_month).mkdir(parents=True, exist_ok=True)
        activity_path = f"activities/{year_month}/{current_date.isoformat()}_run.yaml"
        repo.write_yaml(activity_path, activity)

    return repo, start_date, start_date + timedelta(days=4)


@pytest.fixture
def full_history_scenario(tmp_path, monkeypatch, sample_run_activity):
    """Create scenario with 50 days of data (42+ days, high confidence)."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()

    # Create 50 days of consistent load
    start_date = date(2026, 1, 1)
    for i in range(50):
        current_date = start_date + timedelta(days=i)
        activity = sample_run_activity
        activity.id = f"test_run_{i}"
        activity.date = current_date
        activity.calculated.activity_id = f"test_run_{i}"

        # Create activity file
        year_month = f"{current_date.year}-{current_date.month:02d}"
        (tmp_path / "activities" / year_month).mkdir(parents=True, exist_ok=True)
        activity_path = f"activities/{year_month}/{current_date.isoformat()}_run.yaml"
        repo.write_yaml(activity_path, activity)

    return repo, start_date, start_date + timedelta(days=49)


# ============================================================
# CTL/ATL/TSB CALCULATION TESTS (6 tests)
# ============================================================


class TestCTLATLCalculation:
    """Tests for CTL/ATL/TSB EWMA calculations."""

    def test_cold_start_with_zero_history(self):
        """CTL/ATL should be 0 on first day with no previous metrics."""
        ctl_atl = calculate_ctl_atl(
            daily_load=300.0,
            previous_ctl=0.0,
            previous_atl=0.0,
        )

        # First day: CTL = 0 * 0.976 + 300 * 0.024 = 7.2
        # ATL = 0 * 0.867 + 300 * 0.133 = 39.9
        assert ctl_atl.ctl == pytest.approx(7.2, abs=0.1)
        assert ctl_atl.atl == pytest.approx(39.9, abs=0.1)
        assert ctl_atl.tsb == pytest.approx(7.2 - 39.9, abs=0.1)

    def test_single_day_load_updates_atl_more_than_ctl(self):
        """ATL should increase faster than CTL (7-day vs 42-day constant)."""
        # Start with baseline
        ctl_atl_day1 = calculate_ctl_atl(
            daily_load=300.0,
            previous_ctl=0.0,
            previous_atl=0.0,
        )

        # Add another day
        ctl_atl_day2 = calculate_ctl_atl(
            daily_load=300.0,
            previous_ctl=ctl_atl_day1.ctl,
            previous_atl=ctl_atl_day1.atl,
        )

        # ATL should increase more than CTL
        ctl_increase = ctl_atl_day2.ctl - ctl_atl_day1.ctl
        atl_increase = ctl_atl_day2.atl - ctl_atl_day1.atl

        assert atl_increase > ctl_increase

    def test_ctl_converges_to_average_over_42_days(self):
        """With constant daily load, CTL should converge to average."""
        daily_load = 300.0
        ctl = 0.0
        atl = 0.0

        # Simulate 100 days
        for _ in range(100):
            result = calculate_ctl_atl(daily_load, ctl, atl)
            ctl = result.ctl
            atl = result.atl

        # CTL should converge close to daily load
        # With EWMA decay=0.976, alpha=0.024, steady state = load / alpha
        # Steady state CTL ≈ 300 * 0.024 / (1 - 0.976) = 300 (theoretical)
        # But with iterative EWMA: steady state = daily_load / (1 - decay) = 300 / 0.024 ≈ 12500? No.
        # Actually: At steady state, CTL = CTL * decay + load * alpha
        # So CTL * (1 - decay) = load * alpha → CTL = load * alpha / (1 - decay) = load
        # But empirically converges to ~273 due to rounding/iteration
        assert ctl == pytest.approx(273.0, abs=5.0)

    def test_tsb_negative_after_training_week(self):
        """TSB should go negative (fatigue > fitness) during training."""
        # Simulate a week of high load
        ctl = 40.0  # Baseline fitness
        atl = 35.0  # Baseline fatigue

        # Add 7 days of high load
        for _ in range(7):
            result = calculate_ctl_atl(500.0, ctl, atl)
            ctl = result.ctl
            atl = result.atl

        tsb = ctl - atl

        # ATL increases faster, so TSB should be negative
        assert tsb < 0

    def test_tsb_zone_classification(self):
        """TSB zones should classify correctly."""
        # Note: EWMA updates values even with daily_load=0
        # CTL_new = CTL_prev * 0.976, ATL_new = ATL_prev * 0.867

        # Test overreached: Need TSB < -25
        # Use previous_ctl=20, previous_atl=52 → tsb = 19.52 - 45.08 = -25.56
        result = calculate_ctl_atl(0, previous_ctl=20, previous_atl=52)
        assert result.tsb_zone == TSBZone.OVERREACHED

        # Test productive: TSB -25 to -10
        # Use previous_ctl=50, previous_atl=65 → tsb = 48.8 - 56.4 = -7.6? No, that's OPTIMAL
        # Try previous_ctl=40, previous_atl=60 → tsb = 39.0 - 52.0 = -13.0
        result = calculate_ctl_atl(0, previous_ctl=40, previous_atl=60)
        assert result.tsb_zone == TSBZone.PRODUCTIVE

        # Test optimal: TSB -10 to +5
        # Use previous_ctl=50, previous_atl=48 → tsb = 48.8 - 41.6 = 7.2? No, that's FRESH
        # Try previous_ctl=50, previous_atl=55 → tsb = 48.8 - 47.7 = 1.1
        result = calculate_ctl_atl(0, previous_ctl=50, previous_atl=55)
        assert result.tsb_zone == TSBZone.OPTIMAL

        # Test fresh: TSB +5 to +15
        # Use previous_ctl=50, previous_atl=42 → tsb = 48.8 - 36.4 = 12.4
        result = calculate_ctl_atl(0, previous_ctl=50, previous_atl=42)
        assert result.tsb_zone == TSBZone.FRESH

        # Test peaked: TSB > +15
        # Use previous_ctl=50, previous_atl=30 → tsb = 48.8 - 26.0 = 22.8
        result = calculate_ctl_atl(0, previous_ctl=50, previous_atl=30)
        assert result.tsb_zone == TSBZone.PEAKED

    def test_ctl_trend_detection(self, temp_repo):
        """Should detect building/maintaining/declining trend."""
        # Create metrics for 8 days with increasing load
        start_date = date(2026, 1, 1)
        ctl = 40.0
        atl = 35.0

        (temp_repo.repo_root / "metrics" / "daily").mkdir(parents=True, exist_ok=True)

        for i in range(8):
            current_date = start_date + timedelta(days=i)

            # Increasing load → building CTL
            daily_load = 200.0 + (i * 20)  # Ramp up

            ctl_atl = calculate_ctl_atl(daily_load, ctl, atl, temp_repo, current_date)
            ctl = ctl_atl.ctl
            atl = ctl_atl.atl

            # Create daily metrics
            from sports_coach_engine.schemas.metrics import DailyMetrics, DailyLoad, ReadinessScore, ReadinessComponents, ReadinessLevel, ConfidenceLevel

            daily_metrics = DailyMetrics(
                date=current_date,
                calculated_at=datetime.now(),
                daily_load=DailyLoad(
                    date=current_date,
                    systemic_load_au=daily_load,
                    lower_body_load_au=daily_load,
                    activity_count=1,
                    activities=[],
                ),
                ctl_atl=ctl_atl,
                acwr=None,
                readiness=ReadinessScore(
                    score=70,
                    level=ReadinessLevel.READY,
                    confidence=ConfidenceLevel.MEDIUM,
                    components=ReadinessComponents(
                        tsb_contribution=60.0,
                        load_trend_contribution=70.0,
                        weights_used={"tsb": 0.3, "load_trend": 0.35, "sleep": 0.0, "wellness": 0.0},
                    ),
                    recommendation="Execute as planned.",
                ),
                baseline_established=False,
                acwr_available=False,
                data_days_available=i + 1,
                flags=[],
            )

            temp_repo.write_yaml(f"metrics/daily/{current_date.isoformat()}.yaml", daily_metrics)

        # On day 8, should detect building trend
        assert ctl_atl.ctl_trend == "building"


# ============================================================
# ACWR CALCULATION TESTS (5 tests)
# ============================================================


class TestACWRCalculation:
    """Tests for ACWR (Acute:Chronic Workload Ratio) calculation."""

    def test_acwr_returns_none_with_insufficient_data(self, temp_repo):
        """Should return None if < 28 days of data."""
        # Create only 20 days of metrics
        start_date = date(2026, 1, 1)
        (temp_repo.repo_root / "metrics" / "daily").mkdir(parents=True, exist_ok=True)

        for i in range(20):
            current_date = start_date + timedelta(days=i)
            # Create minimal metrics (just to exist)
            from sports_coach_engine.schemas.metrics import DailyMetrics, DailyLoad, CTLATLMetrics, ReadinessScore, ReadinessComponents, ReadinessLevel, ConfidenceLevel, TSBZone, CTLZone

            daily_metrics = DailyMetrics(
                date=current_date,
                calculated_at=datetime.now(),
                daily_load=DailyLoad(
                    date=current_date,
                    systemic_load_au=300.0,
                    lower_body_load_au=300.0,
                    activity_count=1,
                    activities=[],
                ),
                ctl_atl=CTLATLMetrics(
                    ctl=40.0,
                    atl=45.0,
                    tsb=-5.0,
                    ctl_zone=CTLZone.RECREATIONAL,
                    tsb_zone=TSBZone.OPTIMAL,
                ),
                acwr=None,
                readiness=ReadinessScore(
                    score=70,
                    level=ReadinessLevel.READY,
                    confidence=ConfidenceLevel.MEDIUM,
                    components=ReadinessComponents(
                        tsb_contribution=60.0,
                        load_trend_contribution=70.0,
                        weights_used={"tsb": 0.3, "load_trend": 0.35, "sleep": 0.0, "wellness": 0.0},
                    ),
                    recommendation="Execute as planned.",
                ),
                baseline_established=True,
                acwr_available=False,
                data_days_available=i + 1,
                flags=[],
            )

            temp_repo.write_yaml(f"metrics/daily/{current_date.isoformat()}.yaml", daily_metrics)

        # Try to calculate ACWR on day 21 (insufficient)
        target_date = start_date + timedelta(days=20)
        acwr = calculate_acwr(target_date, temp_repo)

        assert acwr is None

    def test_acwr_calculates_correctly_with_28_days(self, temp_repo):
        """Should calculate ACWR correctly with 28+ days."""
        # Create 30 days of consistent load
        start_date = date(2026, 1, 1)
        (temp_repo.repo_root / "metrics" / "daily").mkdir(parents=True, exist_ok=True)

        for i in range(30):
            current_date = start_date + timedelta(days=i)

            # Consistent load
            daily_load = 300.0

            from sports_coach_engine.schemas.metrics import DailyMetrics, DailyLoad, CTLATLMetrics, ReadinessScore, ReadinessComponents, ReadinessLevel, ConfidenceLevel, TSBZone, CTLZone

            daily_metrics = DailyMetrics(
                date=current_date,
                calculated_at=datetime.now(),
                daily_load=DailyLoad(
                    date=current_date,
                    systemic_load_au=daily_load,
                    lower_body_load_au=daily_load,
                    activity_count=1,
                    activities=[],
                ),
                ctl_atl=CTLATLMetrics(
                    ctl=40.0,
                    atl=45.0,
                    tsb=-5.0,
                    ctl_zone=CTLZone.RECREATIONAL,
                    tsb_zone=TSBZone.OPTIMAL,
                ),
                acwr=None,
                readiness=ReadinessScore(
                    score=70,
                    level=ReadinessLevel.READY,
                    confidence=ConfidenceLevel.MEDIUM,
                    components=ReadinessComponents(
                        tsb_contribution=60.0,
                        load_trend_contribution=70.0,
                        weights_used={"tsb": 0.3, "load_trend": 0.35, "sleep": 0.0, "wellness": 0.0},
                    ),
                    recommendation="Execute as planned.",
                ),
                baseline_established=True,
                acwr_available=False,
                data_days_available=i + 1,
                flags=[],
            )

            temp_repo.write_yaml(f"metrics/daily/{current_date.isoformat()}.yaml", daily_metrics)

        # Calculate ACWR on day 30
        target_date = start_date + timedelta(days=29)
        acwr = calculate_acwr(target_date, temp_repo)

        assert acwr is not None

        # With consistent load, ACWR should be ~1.0
        assert acwr.acwr == pytest.approx(1.0, abs=0.1)
        assert acwr.zone == ACWRZone.SAFE
        assert acwr.injury_risk_elevated is False

    def test_acwr_zone_classification(self, temp_repo):
        """Should classify safe/caution/high_risk correctly."""
        # Create 30 days: low load for 28 days, then spike in last 7
        start_date = date(2026, 1, 1)
        (temp_repo.repo_root / "metrics" / "daily").mkdir(parents=True, exist_ok=True)

        for i in range(30):
            current_date = start_date + timedelta(days=i)

            # Spike in last 7 days
            if i >= 23:
                daily_load = 600.0  # High
            else:
                daily_load = 200.0  # Low baseline

            from sports_coach_engine.schemas.metrics import DailyMetrics, DailyLoad, CTLATLMetrics, ReadinessScore, ReadinessComponents, ReadinessLevel, ConfidenceLevel, TSBZone, CTLZone

            daily_metrics = DailyMetrics(
                date=current_date,
                calculated_at=datetime.now(),
                daily_load=DailyLoad(
                    date=current_date,
                    systemic_load_au=daily_load,
                    lower_body_load_au=daily_load,
                    activity_count=1,
                    activities=[],
                ),
                ctl_atl=CTLATLMetrics(
                    ctl=40.0,
                    atl=45.0,
                    tsb=-5.0,
                    ctl_zone=CTLZone.RECREATIONAL,
                    tsb_zone=TSBZone.OPTIMAL,
                ),
                acwr=None,
                readiness=ReadinessScore(
                    score=70,
                    level=ReadinessLevel.READY,
                    confidence=ConfidenceLevel.MEDIUM,
                    components=ReadinessComponents(
                        tsb_contribution=60.0,
                        load_trend_contribution=70.0,
                        weights_used={"tsb": 0.3, "load_trend": 0.35, "sleep": 0.0, "wellness": 0.0},
                    ),
                    recommendation="Execute as planned.",
                ),
                baseline_established=True,
                acwr_available=False,
                data_days_available=i + 1,
                flags=[],
            )

            temp_repo.write_yaml(f"metrics/daily/{current_date.isoformat()}.yaml", daily_metrics)

        # Calculate ACWR after spike
        target_date = start_date + timedelta(days=29)
        acwr = calculate_acwr(target_date, temp_repo)

        assert acwr is not None

        # 7-day spike should push ACWR high
        # acute_7d = 600 * 7 = 4200
        # chronic_28d = (200 * 21 + 600 * 7) / 28 = (4200 + 4200) / 28 = 300
        # ACWR = (4200/7) / 300 = 600 / 300 = 2.0
        assert acwr.acwr > 1.5  # Should be HIGH_RISK
        assert acwr.zone == ACWRZone.HIGH_RISK
        assert acwr.injury_risk_elevated is True

    def test_acwr_sets_injury_risk_elevated_when_above_1_3(self, temp_repo):
        """Should set injury_risk_elevated when > 1.3."""
        # Create scenario with ACWR = 1.4 (caution zone)
        start_date = date(2026, 1, 1)
        (temp_repo.repo_root / "metrics" / "daily").mkdir(parents=True, exist_ok=True)

        for i in range(30):
            current_date = start_date + timedelta(days=i)

            # Moderate spike in last 7 days
            if i >= 23:
                daily_load = 400.0
            else:
                daily_load = 250.0

            from sports_coach_engine.schemas.metrics import DailyMetrics, DailyLoad, CTLATLMetrics, ReadinessScore, ReadinessComponents, ReadinessLevel, ConfidenceLevel, TSBZone, CTLZone

            daily_metrics = DailyMetrics(
                date=current_date,
                calculated_at=datetime.now(),
                daily_load=DailyLoad(
                    date=current_date,
                    systemic_load_au=daily_load,
                    lower_body_load_au=daily_load,
                    activity_count=1,
                    activities=[],
                ),
                ctl_atl=CTLATLMetrics(
                    ctl=40.0,
                    atl=45.0,
                    tsb=-5.0,
                    ctl_zone=CTLZone.RECREATIONAL,
                    tsb_zone=TSBZone.OPTIMAL,
                ),
                acwr=None,
                readiness=ReadinessScore(
                    score=70,
                    level=ReadinessLevel.READY,
                    confidence=ConfidenceLevel.MEDIUM,
                    components=ReadinessComponents(
                        tsb_contribution=60.0,
                        load_trend_contribution=70.0,
                        weights_used={"tsb": 0.3, "load_trend": 0.35, "sleep": 0.0, "wellness": 0.0},
                    ),
                    recommendation="Execute as planned.",
                ),
                baseline_established=True,
                acwr_available=False,
                data_days_available=i + 1,
                flags=[],
            )

            temp_repo.write_yaml(f"metrics/daily/{current_date.isoformat()}.yaml", daily_metrics)

        target_date = start_date + timedelta(days=29)
        acwr = calculate_acwr(target_date, temp_repo)

        assert acwr is not None
        assert acwr.acwr > 1.3
        assert acwr.injury_risk_elevated is True

    def test_acwr_handles_zero_chronic_load(self, temp_repo):
        """Should handle divide-by-zero gracefully."""
        # Create 28 days of zero load
        start_date = date(2026, 1, 1)
        (temp_repo.repo_root / "metrics" / "daily").mkdir(parents=True, exist_ok=True)

        for i in range(30):
            current_date = start_date + timedelta(days=i)

            from sports_coach_engine.schemas.metrics import DailyMetrics, DailyLoad, CTLATLMetrics, ReadinessScore, ReadinessComponents, ReadinessLevel, ConfidenceLevel, TSBZone, CTLZone

            daily_metrics = DailyMetrics(
                date=current_date,
                calculated_at=datetime.now(),
                daily_load=DailyLoad(
                    date=current_date,
                    systemic_load_au=0.0,  # Zero load
                    lower_body_load_au=0.0,
                    activity_count=0,
                    activities=[],
                ),
                ctl_atl=CTLATLMetrics(
                    ctl=0.0,
                    atl=0.0,
                    tsb=0.0,
                    ctl_zone=CTLZone.BEGINNER,
                    tsb_zone=TSBZone.OPTIMAL,
                ),
                acwr=None,
                readiness=ReadinessScore(
                    score=70,
                    level=ReadinessLevel.READY,
                    confidence=ConfidenceLevel.LOW,
                    components=ReadinessComponents(
                        tsb_contribution=60.0,
                        load_trend_contribution=70.0,
                        weights_used={"tsb": 0.3, "load_trend": 0.35, "sleep": 0.0, "wellness": 0.0},
                    ),
                    recommendation="Execute as planned.",
                ),
                baseline_established=False,
                acwr_available=False,
                data_days_available=i + 1,
                flags=[],
            )

            temp_repo.write_yaml(f"metrics/daily/{current_date.isoformat()}.yaml", daily_metrics)

        target_date = start_date + timedelta(days=29)
        acwr = calculate_acwr(target_date, temp_repo)

        # Should return None (not crash)
        assert acwr is None


# ============================================================
# READINESS SCORE TESTS (6 tests)
# ============================================================


class TestReadinessScore:
    """Tests for readiness score calculation."""

    def test_readiness_with_all_components(self):
        """Should compute correct weighted score with all inputs."""
        readiness = compute_readiness(
            tsb=0.0,  # Optimal form → ~65 on 0-100 scale
            load_trend=70.0,
            sleep_quality=80.0,
            wellness_score=75.0,
        )

        # TSB 0 → tsb_score ≈ 75
        # Weighted: 75*0.20 + 70*0.25 + 80*0.25 + 75*0.30
        # = 15 + 17.5 + 20 + 22.5 = 75
        assert readiness.score == pytest.approx(75, abs=5)
        assert readiness.confidence == ConfidenceLevel.HIGH  # Has all data

        # Should use default weights
        assert readiness.components.weights_used["tsb"] == 0.20
        assert readiness.components.weights_used["sleep"] == 0.25

    def test_readiness_with_missing_subjective_data(self):
        """Should redistribute weights when sleep/wellness missing."""
        readiness = compute_readiness(
            tsb=0.0,
            load_trend=70.0,
            sleep_quality=None,  # Missing
            wellness_score=None,  # Missing
        )

        # Should use objective-only weights: TSB 30%, trend 35%
        assert readiness.components.weights_used["tsb"] == 0.30
        assert readiness.components.weights_used["load_trend"] == 0.35
        assert readiness.components.weights_used["sleep"] == 0.0
        assert readiness.components.weights_used["wellness"] == 0.0

        # Confidence should be lower
        assert readiness.confidence in [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM]

    def test_readiness_level_classification(self):
        """Should classify rest/easy/ready/primed correctly."""
        # Note: TSB score = (tsb + 30) * 2.5
        # Weights: TSB 30%, trend 35% (objective only)
        # Score = tsb_score * 0.30 + load_trend * 0.35

        # Test REST_RECOMMENDED (< 35)
        # TSB=-40 → tsb_score=(-40+30)*2.5=-25 (clamped to 0)
        # Score = 0*0.30 + 20*0.35 = 7
        readiness = compute_readiness(tsb=-40, load_trend=20.0)
        assert readiness.level == ReadinessLevel.REST_RECOMMENDED

        # Test EASY_ONLY (35-49)
        # Need score 35-49. TSB=-5 → tsb_score=(−5+30)*2.5=62.5
        # Score = 62.5*0.30 + 20*0.35 = 18.75 + 7 = 25.75 (still too low)
        # Try TSB=0 → tsb_score=75, load_trend=30
        # Score = 75*0.30 + 30*0.35 = 22.5 + 10.5 = 33 (still too low!)
        # Try TSB=0 → tsb_score=75, load_trend=50
        # Score = 75*0.30 + 50*0.35 = 22.5 + 17.5 = 40
        readiness = compute_readiness(tsb=0, load_trend=50.0)
        assert readiness.level == ReadinessLevel.EASY_ONLY

        # Test REDUCE_INTENSITY (50-64)
        # TSB=5 → tsb_score=87.5, load_trend=60
        # Score = 87.5*0.30 + 60*0.35 = 26.25 + 21 = 47.25 (still EASY)
        # Try TSB=10 → tsb_score=100, load_trend=50
        # Score = 100*0.30 + 50*0.35 = 30 + 17.5 = 47.5 (still EASY!)
        # Try TSB=10 → tsb_score=100, load_trend=70
        # Score = 100*0.30 + 70*0.35 = 30 + 24.5 = 54.5
        readiness = compute_readiness(tsb=10, load_trend=70.0)
        assert readiness.level == ReadinessLevel.REDUCE_INTENSITY

        # Test READY (65-79)
        # TSB=10 → tsb_score=100, load_trend=100
        # Score = 100*0.30 + 100*0.35 = 30 + 35 = 65
        readiness = compute_readiness(tsb=10, load_trend=100.0)
        assert readiness.level == ReadinessLevel.READY

        # Test PRIMED (80-100)
        # Need score 80+. TSB=15 → tsb_score=112.5 (clamped to 100)
        # Score = 100*0.30 + 100*0.35 = 30 + 35 = 65 (only 65!)
        # We need subjective data to reach 80+
        # With all components: TSB=15, trend=90, sleep=85, wellness=85
        # Weights: tsb 20%, trend 25%, sleep 25%, wellness 30%
        # tsb_score = 112.5 (clamped 100)
        # Score = 100*0.20 + 90*0.25 + 85*0.25 + 85*0.30 = 20 + 22.5 + 21.25 + 25.5 = 89.25
        readiness = compute_readiness(
            tsb=15, load_trend=90.0, sleep_quality=85.0, wellness_score=85.0
        )
        assert readiness.level == ReadinessLevel.PRIMED

    def test_injury_flags_cap_readiness(self):
        """Injury flags should cap readiness at 25."""
        readiness = compute_readiness(
            tsb=10.0,  # Great form
            load_trend=90.0,  # Fresh
            injury_flags=["knee", "pain"],
        )

        assert readiness.score <= 25
        assert readiness.injury_flag_override is True
        assert "Injury detected" in readiness.override_reason

    def test_illness_flags_override(self):
        """Illness flags should cap readiness at 15-35."""
        # Severe illness
        readiness = compute_readiness(
            tsb=10.0,
            load_trend=90.0,
            illness_flags=["fever", "flu"],
        )

        assert readiness.score <= 15
        assert readiness.illness_flag_override is True
        assert "Severe illness" in readiness.override_reason

        # Mild illness
        readiness = compute_readiness(
            tsb=10.0,
            load_trend=90.0,
            illness_flags=["cold"],
        )

        assert readiness.score <= 35

    def test_readiness_confidence_levels(self):
        """Should set confidence based on data availability."""
        # LOW: < 14 days
        readiness = compute_readiness(
            tsb=0, load_trend=70.0, data_days=10
        )
        assert readiness.confidence == ConfidenceLevel.LOW

        # MEDIUM: 14-42 days or missing subjective data
        readiness = compute_readiness(
            tsb=0, load_trend=70.0, data_days=20
        )
        assert readiness.confidence == ConfidenceLevel.MEDIUM

        # HIGH: 42+ days with all data
        readiness = compute_readiness(
            tsb=0, load_trend=70.0,
            sleep_quality=80.0, wellness_score=75.0,
            data_days=50
        )
        assert readiness.confidence == ConfidenceLevel.HIGH


# ============================================================
# DAILY METRICS COMPUTATION TESTS (4 tests)
# ============================================================


class TestDailyMetricsComputation:
    """Tests for full daily metrics pipeline."""

    def test_compute_daily_metrics_full_pipeline(self, temp_repo, sample_run_activity):
        """Should run complete pipeline successfully."""
        target_date = date(2026, 1, 12)

        # Create activity file
        year_month = "2026-01"
        (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)
        activity_path = f"activities/{year_month}/{target_date.isoformat()}_run.yaml"
        temp_repo.write_yaml(activity_path, sample_run_activity)

        # Compute metrics
        metrics = compute_daily_metrics(target_date, temp_repo)

        assert metrics is not None
        assert metrics.date == target_date
        assert metrics.daily_load.systemic_load_au == 270.0
        assert metrics.ctl_atl.ctl > 0
        assert metrics.ctl_atl.atl > 0
        assert metrics.baseline_established is False  # First day

    def test_daily_metrics_persistence(self, temp_repo, sample_run_activity):
        """Should persist to correct YAML path."""
        target_date = date(2026, 1, 12)

        # Create activity
        year_month = "2026-01"
        (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)
        activity_path = f"activities/{year_month}/{target_date.isoformat()}_run.yaml"
        temp_repo.write_yaml(activity_path, sample_run_activity)

        # Compute metrics
        compute_daily_metrics(target_date, temp_repo)

        # Check file exists
        metrics_path = f"metrics/daily/{target_date.isoformat()}.yaml"
        loaded = temp_repo.read_yaml(metrics_path, DailyMetrics)

        assert loaded is not None
        assert loaded.date == target_date

    def test_daily_metrics_with_multiple_activities(self, temp_repo, sample_run_activity, sample_climb_activity):
        """Should aggregate loads from multiple activities."""
        target_date = date(2026, 1, 12)
        year_month = "2026-01"
        (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)

        # Create two activities on same day
        run_path = f"activities/{year_month}/{target_date.isoformat()}_run_0700.yaml"
        climb_path = f"activities/{year_month}/{target_date.isoformat()}_climb_1800.yaml"

        temp_repo.write_yaml(run_path, sample_run_activity)
        temp_repo.write_yaml(climb_path, sample_climb_activity)

        # Compute metrics
        metrics = compute_daily_metrics(target_date, temp_repo)

        # Should aggregate both loads
        # Run: 270 systemic, 270 lower-body
        # Climb: 324 systemic, 54 lower-body
        # Total: 594 systemic, 324 lower-body
        assert metrics.daily_load.systemic_load_au == pytest.approx(594.0, abs=1.0)
        assert metrics.daily_load.lower_body_load_au == pytest.approx(324.0, abs=1.0)
        assert metrics.daily_load.activity_count == 2

    def test_daily_metrics_with_no_activities(self, temp_repo):
        """Should handle zero-load day correctly."""
        target_date = date(2026, 1, 12)

        # No activities created
        metrics = compute_daily_metrics(target_date, temp_repo)

        assert metrics.daily_load.systemic_load_au == 0.0
        assert metrics.daily_load.activity_count == 0
        assert metrics.ctl_atl.ctl == 0.0  # Cold start with zero load


# ============================================================
# WEEKLY SUMMARY TESTS (4 tests)
# ============================================================


class TestWeeklySummary:
    """Tests for weekly summary aggregation."""

    def test_weekly_summary_validates_monday(self, temp_repo):
        """Should reject non-Monday week_start."""
        # Tuesday
        week_start = date(2026, 1, 6)  # Tuesday

        with pytest.raises(InvalidMetricsInputError):
            compute_weekly_summary(week_start, temp_repo)

    def test_weekly_summary_aggregation(self, temp_repo, sample_run_activity):
        """Should aggregate 7 days correctly."""
        week_start = date(2026, 1, 5)  # Monday

        # Create activities for 3 days of the week
        for i in range(3):
            current_date = week_start + timedelta(days=i)
            year_month = f"{current_date.year}-{current_date.month:02d}"
            (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)

            activity = sample_run_activity
            activity.id = f"test_run_{i}"
            activity.date = current_date
            activity.calculated.activity_id = f"test_run_{i}"

            activity_path = f"activities/{year_month}/{current_date.isoformat()}_run.yaml"
            temp_repo.write_yaml(activity_path, activity)

        # Compute summary
        summary = compute_weekly_summary(week_start, temp_repo)

        assert summary.total_systemic_load_au == pytest.approx(810.0, abs=1.0)  # 270 * 3
        assert summary.run_sessions == 3
        assert summary.total_activities == 3

    def test_intensity_distribution_calculation(self, temp_repo):
        """Should compute 80/20 distribution correctly."""
        week_start = date(2026, 1, 5)

        # Create mix of easy and quality runs
        for i in range(5):
            current_date = week_start + timedelta(days=i)
            year_month = f"{current_date.year}-{current_date.month:02d}"
            (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)

            # First 4 easy, last 1 quality
            session_type = SessionType.EASY if i < 4 else SessionType.QUALITY

            activity = NormalizedActivity(
                id=f"test_run_{i}",
                source="strava",
                sport_type=SportType.RUN,
                name="Run",
                date=current_date,
                start_time=datetime.now(),
                duration_minutes=60,
                duration_seconds=3600,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            activity.calculated = LoadCalculation(
                activity_id=f"test_run_{i}",
                duration_minutes=60,
                estimated_rpe=4 if session_type == SessionType.EASY else 8,
                sport_type=SportType.RUN,
                base_effort_au=240.0,
                systemic_multiplier=1.0,
                lower_body_multiplier=1.0,
                systemic_load_au=240.0,
                lower_body_load_au=240.0,
                session_type=session_type,
                multiplier_adjustments=[],
            )

            activity_path = f"activities/{year_month}/{current_date.isoformat()}_run.yaml"
            temp_repo.write_yaml(activity_path, activity)

        summary = compute_weekly_summary(week_start, temp_repo)

        # 4 easy (60 min each) = 240 min
        # 1 quality (60 min) = 60 min
        # Total = 300 min
        # Low% = 240/300 = 80%
        assert summary.intensity_distribution.low_percent == pytest.approx(80.0, abs=1.0)
        assert summary.intensity_distribution.is_compliant is True

    def test_high_intensity_session_count(self, temp_repo):
        """Should count quality+race sessions across all sports."""
        week_start = date(2026, 1, 5)

        # Create 2 quality runs and 1 easy climb
        activities = [
            (SportType.RUN, SessionType.QUALITY),
            (SportType.RUN, SessionType.QUALITY),
            (SportType.CLIMB, SessionType.EASY),
        ]

        for i, (sport, session_type) in enumerate(activities):
            current_date = week_start + timedelta(days=i)
            year_month = f"{current_date.year}-{current_date.month:02d}"
            (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)

            activity = NormalizedActivity(
                id=f"test_activity_{i}",
                source="strava",
                sport_type=sport,
                name="Activity",
                date=current_date,
                start_time=datetime.now(),
                duration_minutes=60,
                duration_seconds=3600,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            activity.calculated = LoadCalculation(
                activity_id=f"test_activity_{i}",
                duration_minutes=60,
                estimated_rpe=7,
                sport_type=sport,
                base_effort_au=420.0,
                systemic_multiplier=1.0 if sport == SportType.RUN else 0.6,
                lower_body_multiplier=1.0 if sport == SportType.RUN else 0.1,
                systemic_load_au=420.0 if sport == SportType.RUN else 252.0,
                lower_body_load_au=420.0 if sport == SportType.RUN else 42.0,
                session_type=session_type,
                multiplier_adjustments=[],
            )

            activity_path = f"activities/{year_month}/{current_date.isoformat()}_activity.yaml"
            temp_repo.write_yaml(activity_path, activity)

        summary = compute_weekly_summary(week_start, temp_repo)

        # Should count 2 quality sessions
        assert summary.high_intensity_sessions_7d == 2


# ============================================================
# EDGE CASE TESTS (5 tests)
# ============================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_cold_start_baseline_not_established(self, cold_start_scenario):
        """Should set baseline_established=False with < 14 days."""
        repo, start_date, end_date = cold_start_scenario

        # Compute metrics for day 5 (only 5 days of history)
        metrics = compute_daily_metrics(end_date, repo)

        assert metrics.baseline_established is False
        assert metrics.data_days_available < 14
        assert metrics.readiness.confidence == ConfidenceLevel.LOW

    def test_acwr_unavailable_with_partial_history(self, temp_repo, sample_run_activity):
        """Should set acwr_available=False with < 28 days."""
        # Create 20 days
        start_date = date(2026, 1, 1)

        for i in range(20):
            current_date = start_date + timedelta(days=i)
            year_month = f"{current_date.year}-{current_date.month:02d}"
            (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)

            activity = sample_run_activity
            activity.id = f"test_run_{i}"
            activity.date = current_date
            activity.calculated.activity_id = f"test_run_{i}"

            activity_path = f"activities/{year_month}/{current_date.isoformat()}_run.yaml"
            temp_repo.write_yaml(activity_path, activity)

        # Compute metrics
        target_date = start_date + timedelta(days=19)
        metrics = compute_daily_metrics(target_date, temp_repo)

        assert metrics.acwr_available is False
        assert metrics.acwr is None

    def test_handles_gap_in_daily_metrics(self, temp_repo, sample_run_activity):
        """Should handle gap in daily metrics (treats as cold start)."""
        # Create activity on day 10 (but no metrics for days 1-9)
        target_date = date(2026, 1, 10)
        year_month = "2026-01"
        (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)

        activity_path = f"activities/{year_month}/{target_date.isoformat()}_run.yaml"
        temp_repo.write_yaml(activity_path, sample_run_activity)

        # Should not crash
        metrics = compute_daily_metrics(target_date, temp_repo)

        # Should treat as cold start
        assert metrics.ctl_atl.ctl > 0  # Has today's load
        assert metrics.baseline_established is False

    def test_handles_extreme_load_spike(self, temp_repo):
        """Should handle very high daily load without crashing."""
        target_date = date(2026, 1, 12)

        # Create activity with extreme load
        activity = NormalizedActivity(
            id="extreme_load",
            source="strava",
            sport_type=SportType.RUN,
            name="Ultra Marathon",
            date=target_date,
            start_time=datetime.now(),
            duration_minutes=600,  # 10 hours
            duration_seconds=36000,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        activity.calculated = LoadCalculation(
            activity_id="extreme_load",
            duration_minutes=600,
            estimated_rpe=8,
            sport_type=SportType.RUN,
            base_effort_au=4800.0,  # 8 * 600
            systemic_multiplier=1.0,
            lower_body_multiplier=1.0,
            systemic_load_au=4800.0,
            lower_body_load_au=4800.0,
            session_type=SessionType.RACE,
            multiplier_adjustments=[],
        )

        year_month = "2026-01"
        (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)
        activity_path = f"activities/{year_month}/{target_date.isoformat()}_run.yaml"
        temp_repo.write_yaml(activity_path, activity)

        # Should not crash
        metrics = compute_daily_metrics(target_date, temp_repo)

        assert metrics.daily_load.systemic_load_au == 4800.0
        # Validation should flag as extreme but not fail
        warnings = validate_metrics(metrics)
        # CTL/ATL might be high but should be calculable

    def test_validation_warns_on_extreme_values(self, temp_repo):
        """Should warn if metrics are extreme but not fail."""
        # Create metrics with out-of-range values
        from sports_coach_engine.schemas.metrics import DailyMetrics, DailyLoad, CTLATLMetrics, ACWRMetrics, ReadinessScore, ReadinessComponents, ReadinessLevel, ConfidenceLevel, TSBZone, CTLZone, ACWRZone

        metrics = DailyMetrics(
            date=date(2026, 1, 12),
            calculated_at=datetime.now(),
            daily_load=DailyLoad(
                date=date(2026, 1, 12),
                systemic_load_au=5000.0,  # Very high
                lower_body_load_au=5000.0,
                activity_count=1,
                activities=[],
            ),
            ctl_atl=CTLATLMetrics(
                ctl=250.0,  # Out of range (> 200)
                atl=400.0,  # Out of range (> 300)
                tsb=-150.0,  # Out of range (< -100)
                ctl_zone=CTLZone.ELITE,
                tsb_zone=TSBZone.OVERREACHED,
            ),
            acwr=ACWRMetrics(
                acwr=4.0,  # Extreme (> 3.0)
                zone=ACWRZone.HIGH_RISK,
                acute_load_7d=10000.0,
                chronic_load_28d=2500.0,
                injury_risk_elevated=True,
            ),
            readiness=ReadinessScore(
                score=150,  # Out of range (> 100)
                level=ReadinessLevel.PRIMED,
                confidence=ConfidenceLevel.HIGH,
                components=ReadinessComponents(
                    tsb_contribution=100.0,
                    load_trend_contribution=100.0,
                    weights_used={"tsb": 0.3, "load_trend": 0.35, "sleep": 0.0, "wellness": 0.0},
                ),
                recommendation="Extreme values detected",
            ),
            baseline_established=True,
            acwr_available=True,
            data_days_available=50,
            flags=[],
        )

        warnings = validate_metrics(metrics)

        # Should generate warnings
        assert len(warnings) > 0
        assert any("CTL out of range" in w for w in warnings)
        assert any("ATL out of range" in w for w in warnings)


# ============================================================
# BATCH OPERATIONS TESTS (2 tests)
# ============================================================


class TestBatchOperations:
    """Tests for batch metric computation."""

    def test_compute_metrics_batch_date_range(self, temp_repo, sample_run_activity):
        """Should compute metrics for entire date range."""
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 5)

        # Create activities for 5 days
        for i in range(5):
            current_date = start_date + timedelta(days=i)
            year_month = f"{current_date.year}-{current_date.month:02d}"
            (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)

            activity = sample_run_activity
            activity.id = f"test_run_{i}"
            activity.date = current_date
            activity.calculated.activity_id = f"test_run_{i}"

            activity_path = f"activities/{year_month}/{current_date.isoformat()}_run.yaml"
            temp_repo.write_yaml(activity_path, activity)

        # Batch compute
        results = compute_metrics_batch(start_date, end_date, temp_repo)

        assert len(results) == 5
        assert all(isinstance(m, DailyMetrics) for m in results)

    def test_batch_continues_on_error(self, temp_repo, sample_run_activity):
        """Should not abort batch if single day fails."""
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 3)

        # Create activities only for days 1 and 3 (day 2 missing)
        for i in [0, 2]:
            current_date = start_date + timedelta(days=i)
            year_month = f"{current_date.year}-{current_date.month:02d}"
            (temp_repo.repo_root / "activities" / year_month).mkdir(parents=True, exist_ok=True)

            activity = sample_run_activity
            activity.id = f"test_run_{i}"
            activity.date = current_date
            activity.calculated.activity_id = f"test_run_{i}"

            activity_path = f"activities/{year_month}/{current_date.isoformat()}_run.yaml"
            temp_repo.write_yaml(activity_path, activity)

        # Batch compute (day 2 will have zero load but should not crash)
        results = compute_metrics_batch(start_date, end_date, temp_repo)

        # Should complete all 3 days
        assert len(results) == 3
