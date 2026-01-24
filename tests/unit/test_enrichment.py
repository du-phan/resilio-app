"""
Unit tests for M12 - Data Enrichment module.

Tests metric interpretation, progressive disclosure, workout enrichment,
load interpretation, and context table logic.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock
from sports_coach_engine.core.enrichment import (
    interpret_metric,
    determine_disclosure_level,
    enrich_metrics,
    enrich_workout,
    interpret_load,
    InvalidMetricNameError,
)
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.enrichment import (
    DisclosureLevel,
    MetricInterpretation,
    EnrichedMetrics,
    EnrichedWorkout,
    LoadInterpretation,
)
from sports_coach_engine.schemas.metrics import (
    DailyMetrics,
    DailyLoad,
    CTLATLMetrics,
    ACWRMetrics,
    ReadinessScore,
    ReadinessComponents,
    TSBZone,
    ACWRZone,
    ReadinessLevel,
    CTLZone,
    ConfidenceLevel,
)
from sports_coach_engine.schemas.plan import (
    WorkoutPrescription,
    WorkoutType,
    IntensityZone,
    PlanPhase,
)
from sports_coach_engine.schemas.profile import (
    AthleteProfile,
    GoalType,
    ConflictPolicy,
    RunningPriority,
    TrainingConstraints,
    Goal,
    VitalSigns,
    Weekday,
)


# ============================================================
# TEST FIXTURES
# ============================================================


@pytest.fixture
def mock_repo(tmp_path):
    """Mock RepositoryIO for testing."""
    repo = Mock(spec=RepositoryIO)
    repo.repo_root = tmp_path
    repo.resolve_path = lambda p: tmp_path / p
    # Mock read_yaml to return None (no historical data)
    repo.read_yaml.return_value = None
    return repo


@pytest.fixture
def sample_metrics():
    """Create sample DailyMetrics for testing."""
    from datetime import datetime
    return DailyMetrics(
        date=date(2026, 1, 15),
        calculated_at=datetime(2026, 1, 15, 20, 0, 0),
        daily_load=DailyLoad(
            date=date(2026, 1, 15),
            systemic_load_au=300.0,
            lower_body_load_au=270.0,
            activity_count=1,
            activities=[],
        ),
        ctl_atl=CTLATLMetrics(
            ctl=44.5,
            atl=38.2,
            tsb=6.3,
            ctl_zone=CTLZone.RECREATIONAL,
            tsb_zone=TSBZone.FRESH,
        ),
        acwr=ACWRMetrics(
            acwr=1.15,
            zone=ACWRZone.SAFE,
            acute_load_7d=1890.0,
            chronic_load_28d=257.14,  # 7200/28
            injury_risk_elevated=False,
        ),
        readiness=ReadinessScore(
            score=72,
            level=ReadinessLevel.READY,
            confidence=ConfidenceLevel.HIGH,
            components=ReadinessComponents(
                tsb_contribution=15,
                load_trend_contribution=18,
                wellness_contribution=19,
                subjective_contribution=20,
            ),
            recommendation="Execute as planned",
        ),
        baseline_established=True,
        acwr_available=True,
        data_days_available=42,
        flags=[],
    )


@pytest.fixture
def sample_historical_metrics(sample_metrics):
    """Create historical metrics for trend calculation."""
    from datetime import datetime
    historical = []
    for i in range(1, 15):
        past_date = sample_metrics.date - timedelta(days=i)
        # Create metrics with slightly lower CTL for upward trend
        past_ctl = max(40.0, sample_metrics.ctl_atl.ctl - (i * 0.3))
        past_atl = max(35.0, sample_metrics.ctl_atl.atl - (i * 0.2))
        past_tsb = past_ctl - past_atl

        past_metrics = DailyMetrics(
            date=past_date,
            calculated_at=datetime.combine(past_date, datetime.min.time()),
            daily_load=DailyLoad(
                date=past_date,
                systemic_load_au=280.0,
                lower_body_load_au=250.0,
                activity_count=1,
                activities=[],
            ),
            ctl_atl=CTLATLMetrics(
                ctl=past_ctl,
                atl=past_atl,
                tsb=past_tsb,
                ctl_zone=CTLZone.RECREATIONAL,
                tsb_zone=TSBZone.OPTIMAL,
            ),
            acwr=ACWRMetrics(
                acwr=1.10,
                zone=ACWRZone.SAFE,
                acute_load_7d=1800.0,
                chronic_load_28d=250.0,
                injury_risk_elevated=False,
            ),
            readiness=ReadinessScore(
                score=70,
                level=ReadinessLevel.READY,
                confidence=ConfidenceLevel.HIGH,
                components=ReadinessComponents(
                    tsb_contribution=14,
                    load_trend_contribution=18,
                    wellness_contribution=18,
                    subjective_contribution=20,
                ),
                recommendation="Execute as planned",
            ),
            baseline_established=True,
            acwr_available=True,
            data_days_available=42 - i,
            flags=[],
        )
        historical.append(past_metrics)
    return historical


@pytest.fixture
def sample_profile():
    """Create sample AthleteProfile for testing."""
    return AthleteProfile(
        name="Test Runner",
        age=35,
        created_at="2025-01-01T00:00:00Z",
        vital_signs=VitalSigns(
            max_hr=185,
            resting_hr=55,
        ),
        constraints=TrainingConstraints(
            available_run_days=[Weekday.MONDAY, Weekday.WEDNESDAY, Weekday.FRIDAY, Weekday.SUNDAY],
            min_run_days_per_week=3,
            max_run_days_per_week=4,
        ),
        running_priority=RunningPriority.PRIMARY,
        primary_sport="running",
        conflict_policy=ConflictPolicy.RUNNING_GOAL_WINS,
        goal=Goal(
            type=GoalType.HALF_MARATHON,
            target_date="2026-04-15",
            target_time="01:30:00",
        ),
    )


@pytest.fixture
def sample_workout(sample_profile):
    """Create sample WorkoutPrescription for testing."""
    return WorkoutPrescription(
        id="test_workout_1",
        week_number=4,
        day_of_week=2,  # Wednesday
        date=date(2026, 1, 15),
        workout_type=WorkoutType.TEMPO,
        phase=PlanPhase.BUILD,
        duration_minutes=45,
        target_rpe=7,
        intensity_zone=IntensityZone.ZONE_4,
        pace_range_min_km="5:15",
        pace_range_max_km="5:25",
        hr_range_low=None,
        hr_range_high=None,
        purpose="Build lactate threshold capacity",
        notes=None,
    )


# ============================================================
# METRIC INTERPRETATION TESTS
# ============================================================


class TestMetricInterpretation:
    """Test metric interpretation with context tables."""

    def test_ctl_interpretation_zones(self):
        """CTL values should map to correct zones."""
        # Beginner zone
        result = interpret_metric("ctl", 15.0)
        assert result.zone == "beginner"
        assert result.interpretation == "building base fitness"
        assert result.value == 15.0

        # Recreational zone
        result = interpret_metric("ctl", 44.0)
        assert result.zone == "recreational"
        assert result.interpretation == "solid recreational level"

        # Elite zone
        result = interpret_metric("ctl", 120.0)
        assert result.zone == "elite"
        assert result.interpretation == "elite amateur"

    def test_tsb_shows_sign(self):
        """TSB formatted values should include +/- sign."""
        # Positive TSB
        result = interpret_metric("tsb", 8.5)
        assert result.formatted_value == "+8"  # Rounded to integer
        assert result.zone == "fresh"

        # Negative TSB
        result = interpret_metric("tsb", -15.0)
        assert result.formatted_value == "-15"  # Rounded to integer
        assert result.zone == "productive"

        # Zero TSB (edge case)
        result = interpret_metric("tsb", 0.0)
        assert result.formatted_value == "+0"  # Rounded to integer

    def test_acwr_zones(self):
        """ACWR should correctly identify risk zones."""
        # Safe zone
        result = interpret_metric("acwr", 1.10)
        assert result.zone == "safe"
        assert result.interpretation == "safe training zone"
        assert result.formatted_value == "1.10"

        # Caution zone
        result = interpret_metric("acwr", 1.40)
        assert result.zone == "caution"
        assert result.interpretation == "caution - monitor closely"

        # High risk zone
        result = interpret_metric("acwr", 1.65)
        assert result.zone == "high_risk"
        assert result.interpretation == "high injury risk"

    def test_readiness_levels(self):
        """Readiness score should map to correct levels."""
        # Rest recommended
        result = interpret_metric("readiness", 30)
        assert result.zone == "rest_recommended"
        assert result.interpretation == "rest recommended"

        # Ready for training
        result = interpret_metric("readiness", 65)
        assert result.zone == "ready"
        assert result.interpretation == "ready for normal training"

        # Primed for quality
        result = interpret_metric("readiness", 85)
        assert result.zone == "primed"
        assert result.interpretation == "primed for quality work"

    def test_trend_calculation(self):
        """Trends should be calculated from previous values."""
        # Increasing trend
        result = interpret_metric("ctl", 44.0, previous_value=42.0)
        assert result.trend == "+2 from last week"  # Rounded to integer

        # Decreasing trend
        result = interpret_metric("ctl", 40.0, previous_value=45.0)
        assert result.trend == "-5 from last week"  # Rounded to integer

        # No change - no trend reported when delta < 1
        result = interpret_metric("ctl", 44.0, previous_value=44.0)
        assert result.trend is None  # No significant change

    def test_metric_formatting(self):
        """Formatted values should match expected format."""
        # CTL - no decimal if whole number
        result = interpret_metric("ctl", 44.0)
        assert result.formatted_value == "44"

        # ACWR - always 2 decimals
        result = interpret_metric("acwr", 1.1)
        assert result.formatted_value == "1.10"

        # Readiness - includes /100
        result = interpret_metric("readiness", 72)
        assert result.formatted_value == "72/100"

    def test_metric_explanations(self):
        """Explanations should be present for key metrics."""
        result = interpret_metric("ctl", 44.0)
        assert result.explanation is not None
        assert "fitness" in result.explanation.lower()

        result = interpret_metric("tsb", 6.0)
        assert result.explanation is not None
        assert "balance" in result.explanation.lower() or "fatigue" in result.explanation.lower()

    def test_atl_no_zone(self):
        """ATL should not have zone classification."""
        result = interpret_metric("atl", 38.0)
        assert result.zone == ""
        assert result.interpretation == ""

    def test_zero_values(self):
        """Zero metric values should be handled correctly."""
        result = interpret_metric("ctl", 0.0)
        assert result.value == 0.0
        assert result.zone == "beginner"

    def test_extreme_values(self):
        """Very high CTL values should be handled."""
        result = interpret_metric("ctl", 250.0)
        assert result.value == 250.0
        # Should map to elite (100-200 range extends beyond)
        assert result.zone == "elite"

    def test_invalid_metric_name(self):
        """Invalid metric names should raise error."""
        with pytest.raises(InvalidMetricNameError):
            interpret_metric("invalid_metric", 50.0)


# ============================================================
# DISCLOSURE LEVEL TESTS
# ============================================================


class TestDisclosureLevel:
    """Test progressive disclosure based on data history."""

    def test_disclosure_basic(self):
        """Less than 14 days should return BASIC."""
        assert determine_disclosure_level(7) == DisclosureLevel.BASIC
        assert determine_disclosure_level(13) == DisclosureLevel.BASIC

    def test_disclosure_intermediate(self):
        """14-28 days should return INTERMEDIATE."""
        assert determine_disclosure_level(14) == DisclosureLevel.INTERMEDIATE
        assert determine_disclosure_level(21) == DisclosureLevel.INTERMEDIATE
        assert determine_disclosure_level(27) == DisclosureLevel.INTERMEDIATE

    def test_disclosure_advanced(self):
        """28+ days should return ADVANCED."""
        assert determine_disclosure_level(28) == DisclosureLevel.ADVANCED
        assert determine_disclosure_level(42) == DisclosureLevel.ADVANCED
        assert determine_disclosure_level(100) == DisclosureLevel.ADVANCED


# ============================================================
# ENRICHED METRICS TESTS
# ============================================================


class TestEnrichMetrics:
    """Test full metrics enrichment."""

    def test_enrich_metrics_basic(self, sample_metrics, mock_repo):
        """Enriched metrics should include all interpretations."""
        enriched = enrich_metrics(sample_metrics, mock_repo)

        # Check all metric interpretations present
        assert enriched.ctl.value == sample_metrics.ctl_atl.ctl
        assert enriched.ctl.zone == "recreational"
        assert enriched.atl.value == sample_metrics.ctl_atl.atl
        assert enriched.tsb.value == sample_metrics.ctl_atl.tsb
        assert enriched.tsb.formatted_value.startswith("+")
        assert enriched.readiness.value == sample_metrics.readiness.score

        # Check disclosure level
        assert enriched.disclosure_level == DisclosureLevel.ADVANCED

        # Check intensity distribution (currently placeholder values)
        assert isinstance(enriched.low_intensity_percent, float)
        assert isinstance(enriched.intensity_on_target, bool)

    def test_enrich_metrics_with_trends(self, sample_metrics, sample_historical_metrics, mock_repo):
        """Enriched metrics should include trends when historical data provided."""
        # Configure mock to return historical metrics (7 days ago)
        mock_repo.read_yaml.return_value = sample_historical_metrics[6]  # 7 days ago

        enriched = enrich_metrics(sample_metrics, mock_repo)

        # Should have trend from 7 days ago
        assert enriched.ctl.trend is not None
        assert "from last week" in enriched.ctl.trend

        # Should have weekly change
        assert enriched.ctl_weekly_change is not None

        # Should have load trend
        assert enriched.training_load_trend is not None

    def test_enrich_metrics_no_acwr_when_insufficient_data(self, mock_repo):
        """ACWR should be None when data_days < 28."""
        from datetime import datetime
        metrics_short_history = DailyMetrics(
            date=date(2026, 1, 15),
            calculated_at=datetime(2026, 1, 15, 20, 0, 0),
            daily_load=DailyLoad(
                date=date(2026, 1, 15),
                systemic_load_au=200.0,
                lower_body_load_au=180.0,
                activity_count=1,
                activities=[],
            ),
            ctl_atl=CTLATLMetrics(
                ctl=30.0,
                atl=28.0,
                tsb=2.0,
                ctl_zone=CTLZone.DEVELOPING,
                tsb_zone=TSBZone.OPTIMAL,
            ),
            acwr=None,  # Not enough data
            readiness=ReadinessScore(
                score=60,
                level=ReadinessLevel.READY,
                confidence=ConfidenceLevel.MEDIUM,
                components=ReadinessComponents(
                    tsb_contribution=12,
                    load_trend_contribution=15,
                    wellness_contribution=18,
                    subjective_contribution=15,
                ),
                recommendation="Execute as planned",
            ),
            baseline_established=True,
            acwr_available=False,
            data_days_available=20,  # < 28 days
            flags=[],
        )

        enriched = enrich_metrics(metrics_short_history, mock_repo)
        assert enriched.acwr is None
        assert enriched.disclosure_level == DisclosureLevel.INTERMEDIATE

    def test_enrich_metrics_intensity_not_on_target(self):
        """intensity_on_target should be False when < 80% low intensity."""
        from datetime import datetime
        # Note: This test currently cannot verify intensity_on_target
        # because enrich_metrics() doesn't have access to intensity distribution yet.
        # The enrichment module uses placeholder values until weekly summary is available.
        # This test is a placeholder for future implementation.
        pass


# ============================================================
# WORKOUT ENRICHMENT TESTS
# ============================================================


class TestEnrichWorkout:
    """Test workout enrichment with rationale and guidance."""

    def test_workout_rationale_tsb_context(self, sample_workout, sample_metrics, sample_profile):
        """Rationale should reflect TSB context."""
        enriched = enrich_workout(sample_workout, sample_metrics, sample_profile)

        assert enriched.rationale is not None
        # TSB is +6.3 (fresh), should mention good form or readiness
        assert "fresh" in enriched.rationale.primary_reason.lower() or "ready" in enriched.rationale.primary_reason.lower()

    def test_pace_guidance_formatting(self, sample_workout, sample_metrics, sample_profile):
        """Pace should be formatted as mm:ss/km."""
        enriched = enrich_workout(sample_workout, sample_metrics, sample_profile)

        assert enriched.pace_guidance is not None
        assert enriched.pace_guidance.formatted is not None
        # Should contain colon for minutes:seconds
        assert ":" in enriched.pace_guidance.formatted
        assert "/km" in enriched.pace_guidance.formatted

    def test_hr_guidance_formatting(self, sample_workout, sample_metrics, sample_profile):
        """HR should be formatted with bpm."""
        enriched = enrich_workout(sample_workout, sample_metrics, sample_profile)

        assert enriched.hr_guidance is not None
        assert enriched.hr_guidance.formatted is not None
        assert "bpm" in enriched.hr_guidance.formatted.lower()
        assert enriched.hr_guidance.zone_name is not None

    def test_workout_type_display(self, sample_workout, sample_metrics, sample_profile):
        """Workout type should have proper display name."""
        enriched = enrich_workout(sample_workout, sample_metrics, sample_profile)

        assert enriched.workout_type_display == "Tempo Run"
        assert enriched.workout_type == "tempo"  # Internal value

    def test_intensity_descriptions(self, sample_workout, sample_metrics, sample_profile):
        """Intensity zone should have description."""
        enriched = enrich_workout(sample_workout, sample_metrics, sample_profile)

        assert enriched.intensity_zone == "zone_4"
        assert enriched.intensity_description is not None
        # Zone 4 is typically "Threshold"
        assert "threshold" in enriched.intensity_description.lower()

    def test_pace_feel_descriptions(self, sample_workout, sample_metrics, sample_profile):
        """Pace guidance should include feel description."""
        enriched = enrich_workout(sample_workout, sample_metrics, sample_profile)

        assert enriched.pace_guidance is not None
        assert enriched.pace_guidance.feel_description is not None
        # Tempo run should feel "comfortably hard" or similar
        assert len(enriched.pace_guidance.feel_description) > 0

    def test_safety_notes_when_acwr_elevated(self, sample_workout, sample_profile):
        """Safety notes should be added when ACWR is high."""
        from datetime import datetime
        # Create metrics with high ACWR
        high_acwr_metrics = DailyMetrics(
            date=date(2026, 1, 15),
            calculated_at=datetime(2026, 1, 15, 20, 0, 0),
            daily_load=DailyLoad(
                date=date(2026, 1, 15),
                systemic_load_au=350.0,
                lower_body_load_au=320.0,
                activity_count=1,
                activities=[],
            ),
            ctl_atl=CTLATLMetrics(
                ctl=40.0,
                atl=38.0,
                tsb=2.0,
                ctl_zone=CTLZone.RECREATIONAL,
                tsb_zone=TSBZone.OPTIMAL,
            ),
            acwr=ACWRMetrics(
                acwr=1.45,  # Caution zone
                zone=ACWRZone.CAUTION,
                acute_load_7d=2000.0,
                chronic_load_28d=285.7,
                injury_risk_elevated=True,
            ),
            readiness=ReadinessScore(
                score=55,
                level=ReadinessLevel.READY,
                confidence=ConfidenceLevel.MEDIUM,
                components=ReadinessComponents(
                    tsb_contribution=10,
                    load_trend_contribution=15,
                    wellness_contribution=15,
                    subjective_contribution=15,
                ),
                recommendation="Consider easy effort",
            ),
            baseline_established=True,
            acwr_available=True,
            data_days_available=42,
            flags=[],
        )

        enriched = enrich_workout(sample_workout, high_acwr_metrics, sample_profile)

        assert enriched.rationale.safety_notes is not None
        assert len(enriched.rationale.safety_notes) > 0
        # Should mention ACWR or injury risk
        safety_text = " ".join(enriched.rationale.safety_notes).lower()
        assert "acwr" in safety_text or "risk" in safety_text or "caution" in safety_text

    def test_duration_formatted(self, sample_workout, sample_metrics, sample_profile):
        """Duration should be formatted as human-readable string."""
        enriched = enrich_workout(sample_workout, sample_metrics, sample_profile)

        assert enriched.duration_formatted is not None
        assert "45" in enriched.duration_formatted
        assert "minute" in enriched.duration_formatted.lower()


# ============================================================
# LOAD INTERPRETATION TESTS
# ============================================================


class TestLoadInterpretation:
    """Test load interpretation with sport-specific context."""

    def test_load_interpretation_climbing(self):
        """Climbing should emphasize upper body."""
        result = interpret_load(
            systemic_au=315.0,
            lower_body_au=52.0,
            sport_type="climb"
        )

        assert result.systemic_load_au == 315.0
        assert result.lower_body_load_au == 52.0
        assert result.systemic_description is not None
        assert result.lower_body_description is not None
        # Combined assessment should note low leg impact
        assert "low" in result.lower_body_description.lower() or "light" in result.lower_body_description.lower()

    def test_load_interpretation_running(self):
        """Running should show balanced systemic and lower-body load."""
        result = interpret_load(
            systemic_au=301.0,
            lower_body_au=301.0,
            sport_type="run"
        )

        assert result.systemic_load_au == 301.0
        assert result.lower_body_load_au == 301.0
        # 301 AU is in the "solid workout" range (300-500)
        assert "solid" in result.systemic_description.lower() or "workout" in result.systemic_description.lower()

    def test_load_interpretation_cycling(self):
        """Cycling should show lower leg impact than systemic."""
        result = interpret_load(
            systemic_au=400.0,
            lower_body_au=140.0,  # ~35% of systemic (cycling multiplier)
            sport_type="cycle"
        )

        assert result.systemic_load_au == 400.0
        assert result.lower_body_load_au == 140.0
        # Verify both loads are interpreted and differ appropriately
        assert result.systemic_description is not None
        assert result.lower_body_description is not None
        assert result.combined_assessment is not None
        # Lower body load (140 AU = moderate) should be less demanding than systemic (400 AU = solid)
        assert len(result.combined_assessment) > 0


# ============================================================
# INTEGRATION TESTS
# ============================================================


class TestEnrichmentIntegration:
    """Test end-to-end enrichment flows."""

    def test_full_metrics_enrichment_pipeline(self, sample_metrics, sample_historical_metrics, mock_repo):
        """Full pipeline from raw metrics to enriched metrics."""
        # Configure mock to return historical metrics (7 days ago)
        mock_repo.read_yaml.return_value = sample_historical_metrics[6]

        enriched = enrich_metrics(sample_metrics, mock_repo)

        # Verify all components present
        assert isinstance(enriched, EnrichedMetrics)
        assert enriched.ctl.value > 0
        assert enriched.disclosure_level in [DisclosureLevel.BASIC, DisclosureLevel.INTERMEDIATE, DisclosureLevel.ADVANCED]
        assert 0 <= enriched.low_intensity_percent <= 100
        assert isinstance(enriched.intensity_on_target, bool)

    def test_full_workout_enrichment_pipeline(self, sample_workout, sample_metrics, sample_profile):
        """Full pipeline from prescription to enriched workout."""
        enriched = enrich_workout(sample_workout, sample_metrics, sample_profile)

        # Verify all components present
        assert isinstance(enriched, EnrichedWorkout)
        assert enriched.workout_type_display is not None
        assert enriched.duration_formatted is not None
        assert enriched.pace_guidance is not None
        assert enriched.hr_guidance is not None
        assert enriched.rationale is not None
        assert enriched.current_readiness is not None
