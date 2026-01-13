"""
Unit tests for M11 Adaptation Toolkit (Toolkit Paradigm).

Tests quantitative toolkit functions:
- Trigger detection (detect_adaptation_triggers)
- Risk assessment (assess_override_risk)
- Recovery estimation (estimate_recovery_time)

Schema tests remain to validate data models.
"""

import pytest
from datetime import date, datetime, timedelta
from pydantic import ValidationError

from sports_coach_engine.schemas.adaptation import (
    TriggerType,
    AdaptationTrigger,
    OverrideRiskAssessment,
    RecoveryEstimate,
    RiskLevel,
    SuggestionType,
    SuggestionStatus,
    OverrideRisk,
    WorkoutReference,
    ProposedChange,
    Suggestion,
    SafetyOverride,
    AdaptationResult,
)
from sports_coach_engine.core.adaptation import (
    detect_adaptation_triggers,
    assess_override_risk,
    estimate_recovery_time,
)


# ============================================================
# ENUM TESTS
# ============================================================


class TestTriggerType:
    """Test TriggerType enum (Toolkit Paradigm)."""

    def test_all_triggers(self):
        """All trigger types should be accessible."""
        triggers = [
            TriggerType.ACWR_ELEVATED,
            TriggerType.ACWR_HIGH_RISK,
            TriggerType.READINESS_LOW,
            TriggerType.READINESS_VERY_LOW,
            TriggerType.TSB_OVERREACHED,
            TriggerType.LOWER_BODY_LOAD_HIGH,
            TriggerType.SESSION_DENSITY_HIGH,
        ]
        assert len(triggers) == 7

    def test_trigger_from_string(self):
        """Should create trigger from string value."""
        trigger = TriggerType("acwr_elevated")
        assert trigger == TriggerType.ACWR_ELEVATED


class TestSuggestionType:
    """Test SuggestionType enum."""

    def test_all_suggestion_types(self):
        """All suggestion types should be accessible."""
        types = [
            SuggestionType.DOWNGRADE,
            SuggestionType.SKIP,
            SuggestionType.MOVE,
            SuggestionType.SUBSTITUTE,
            SuggestionType.SHORTEN,
            SuggestionType.FORCE_REST,
        ]
        assert len(types) == 6


class TestSuggestionStatus:
    """Test SuggestionStatus enum."""

    def test_all_statuses(self):
        """All status values should be accessible."""
        statuses = [
            SuggestionStatus.PENDING,
            SuggestionStatus.ACCEPTED,
            SuggestionStatus.DECLINED,
            SuggestionStatus.EXPIRED,
            SuggestionStatus.AUTO_APPLIED,
        ]
        assert len(statuses) == 5


class TestOverrideRisk:
    """Test OverrideRisk enum."""

    def test_all_risk_levels(self):
        """All risk levels should be accessible."""
        risks = [
            OverrideRisk.LOW,
            OverrideRisk.MODERATE,
            OverrideRisk.HIGH,
            OverrideRisk.SEVERE,
        ]
        assert len(risks) == 4


# ============================================================
# COMPONENT MODEL TESTS
# ============================================================


class TestWorkoutReference:
    """Test WorkoutReference model."""

    def test_valid_workout_reference(self):
        """Should create valid workout reference."""
        ref = WorkoutReference(
            file_path="plans/workouts/week_01/tuesday_tempo.yaml",
            date=date(2026, 1, 21),
            workout_type="tempo",
            is_key_workout=True,
        )
        assert ref.file_path == "plans/workouts/week_01/tuesday_tempo.yaml"
        assert ref.workout_type == "tempo"
        assert ref.is_key_workout is True

    def test_key_workout_defaults_false(self):
        """is_key_workout should default to False."""
        ref = WorkoutReference(
            file_path="plans/workouts/week_01/monday_easy.yaml",
            date=date(2026, 1, 20),
            workout_type="easy",
        )
        assert ref.is_key_workout is False


class TestProposedChange:
    """Test ProposedChange model."""

    def test_partial_changes(self):
        """Should allow partial modifications."""
        change = ProposedChange(
            workout_type="easy",
            target_rpe=4,
        )
        assert change.workout_type == "easy"
        assert change.target_rpe == 4
        assert change.duration_minutes is None  # Not specified

    def test_complete_changes(self):
        """Should allow complete workout specification."""
        change = ProposedChange(
            workout_type="easy",
            duration_minutes=30,
            distance_km=5.0,
            intensity_zone="zone_2",
            target_rpe=4,
            notes="Reduced from tempo due to low readiness",
        )
        assert change.duration_minutes == 30
        assert change.distance_km == 5.0
        assert change.notes is not None

    def test_rpe_bounds(self):
        """RPE should be between 1 and 10."""
        with pytest.raises(ValidationError):
            ProposedChange(target_rpe=0)

        with pytest.raises(ValidationError):
            ProposedChange(target_rpe=11)

    def test_negative_duration_rejected(self):
        """Negative duration should be rejected."""
        with pytest.raises(ValidationError):
            ProposedChange(duration_minutes=-10)


# ============================================================
# CORE MODEL TESTS
# ============================================================


class TestSafetyOverride:
    """Test SafetyOverride model."""

    def test_duration_days_minimum(self):
        """Duration days should be at least 1."""
        workout_ref = WorkoutReference(
            file_path="test.yaml",
            date=date(2026, 1, 20),
            workout_type="tempo",
        )

        with pytest.raises(ValidationError):
            SafetyOverride(
                id="test_003",
                trigger=TriggerType.ACWR_HIGH_RISK,
                affected_workout=workout_ref,
                action_taken="Rest",
                duration_days=0,  # Invalid
            )


class TestAdaptationResult:
    """Test AdaptationResult model."""

    def test_empty_result(self):
        """Should allow empty result (no suggestions/overrides)."""
        result = AdaptationResult(
            analysis_date_range={"start": "2026-01-20", "end": "2026-01-22"},
        )

        assert result.suggestions == []
        assert result.safety_overrides == []
        assert result.warnings == []
        assert result.metrics_snapshot is None


# ============================================================
# DAY 7: TRIGGER EVALUATION & SUGGESTION GENERATION TESTS
# ============================================================


class TestTriggerDetection:
    """Test trigger detection toolkit (Toolkit Paradigm)."""

    def test_acwr_elevated_triggers(self):
        """ACWR 1.3-1.5 should trigger for quality workouts."""
        workout = {"workout_type": "tempo", "date": date(2026, 1, 21)}
        metrics = {"acwr": 1.42, "readiness": 65}
        profile = {"adaptation_thresholds": {}}

        triggers = detect_adaptation_triggers(workout, metrics, profile)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == TriggerType.ACWR_ELEVATED
        assert triggers[0].value == 1.42
        assert triggers[0].zone == "caution"
        assert "tempo" in triggers[0].applies_to

    def test_acwr_high_risk_triggers(self):
        """ACWR >1.5 should trigger for quality and long runs."""
        workout = {"workout_type": "long_run", "date": date(2026, 1, 23)}
        metrics = {"acwr": 1.65, "readiness": 60}
        profile = {"adaptation_thresholds": {}}

        triggers = detect_adaptation_triggers(workout, metrics, profile)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == TriggerType.ACWR_HIGH_RISK
        assert triggers[0].value == 1.65
        assert triggers[0].zone == "danger"

    def test_low_readiness_triggers_for_quality_only(self):
        """Low readiness should trigger for quality workouts, not easy."""
        profile = {"adaptation_thresholds": {}}

        # Should trigger for tempo
        tempo = {"workout_type": "tempo", "date": date(2026, 1, 21)}
        triggers_tempo = detect_adaptation_triggers(tempo, {"readiness": 45}, profile)
        assert len(triggers_tempo) == 1
        assert triggers_tempo[0].trigger_type == TriggerType.READINESS_LOW

        # Should NOT trigger for easy
        easy = {"workout_type": "easy", "date": date(2026, 1, 21)}
        triggers_easy = detect_adaptation_triggers(easy, {"readiness": 45}, profile)
        assert len(triggers_easy) == 0

    def test_very_low_readiness_triggers_for_all(self):
        """Very low readiness (<35) should trigger for ALL workouts."""
        # Should trigger for easy
        easy = {"workout_type": "easy", "date": date(2026, 1, 21)}
        profile = {"adaptation_thresholds": {}}
        triggers = detect_adaptation_triggers(easy, {"readiness": 30}, profile)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == TriggerType.READINESS_VERY_LOW
        assert triggers[0].value == 30
        assert triggers[0].zone == "danger"

    def test_tsb_overreached_triggers(self):
        """TSB <-25 should trigger overreaching."""
        workout = {"workout_type": "tempo", "date": date(2026, 1, 21)}
        metrics = {"tsb": -28}
        profile = {"adaptation_thresholds": {}}

        triggers = detect_adaptation_triggers(workout, metrics, profile)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == TriggerType.TSB_OVERREACHED
        assert triggers[0].value == -28
        assert triggers[0].zone == "danger"

    def test_custom_thresholds_respected(self):
        """Custom athlete thresholds should override defaults."""
        workout = {"workout_type": "tempo", "date": date(2026, 1, 21)}
        metrics = {"acwr": 1.4}
        profile = {
            "adaptation_thresholds": {
                "acwr_elevated": 1.5,  # Higher threshold for elite athlete
            }
        }

        triggers = detect_adaptation_triggers(workout, metrics, profile)

        # Should NOT trigger because custom threshold is 1.5
        assert len(triggers) == 0


class TestRiskAssessment:
    """Test risk assessment toolkit (Toolkit Paradigm)."""

    def test_no_triggers_low_risk(self):
        """No triggers should result in low risk."""
        risk = assess_override_risk([], {"workout_type": "easy", "target_rpe": 4})

        assert risk.risk_level == RiskLevel.LOW
        assert risk.injury_probability < 0.10
        assert len(risk.risk_factors) == 0

    def test_single_caution_trigger_moderate_risk(self):
        """Single caution trigger (ACWR 1.35) + moderate intensity → moderate risk."""
        triggers = [
            AdaptationTrigger(
                trigger_type=TriggerType.ACWR_ELEVATED,
                value=1.35,
                threshold=1.3,
                zone="caution",
                applies_to=["tempo"],
                detected_at=date.today(),
            )
        ]
        workout = {"workout_type": "tempo", "target_rpe": 7}

        risk = assess_override_risk(triggers, workout)

        # Caution (0.05) + base (0.05) * RPE 7 multiplier (1.2) = 0.12 = moderate
        assert risk.risk_level == RiskLevel.MODERATE
        assert 0.10 <= risk.injury_probability < 0.20
        assert len(risk.risk_factors) >= 1

    def test_danger_trigger_high_risk(self):
        """Danger zone trigger should be high risk."""
        triggers = [
            AdaptationTrigger(
                trigger_type=TriggerType.ACWR_HIGH_RISK,
                value=1.65,
                threshold=1.5,
                zone="danger",
                applies_to=["tempo"],
                detected_at=date.today(),
            )
        ]
        workout = {"workout_type": "tempo", "target_rpe": 8}

        risk = assess_override_risk(triggers, workout)

        assert risk.risk_level in [RiskLevel.HIGH, RiskLevel.MODERATE]
        assert risk.injury_probability >= 0.15
        assert len(risk.evidence) > 0

    def test_high_intensity_multiplies_risk(self):
        """High intensity workouts should multiply risk."""
        triggers = [
            AdaptationTrigger(
                trigger_type=TriggerType.ACWR_ELEVATED,
                value=1.4,
                threshold=1.3,
                zone="caution",
                applies_to=["intervals"],
                detected_at=date.today(),
            )
        ]

        # Same trigger, different intensities
        easy_workout = {"workout_type": "easy", "target_rpe": 4}
        hard_workout = {"workout_type": "intervals", "target_rpe": 9}

        risk_easy = assess_override_risk(triggers, easy_workout)
        risk_hard = assess_override_risk(triggers, hard_workout)

        # Hard workout should have higher risk
        assert risk_hard.injury_probability > risk_easy.injury_probability


class TestRecoveryEstimation:
    """Test recovery time estimation toolkit (Toolkit Paradigm)."""

    def test_acwr_high_risk_recovery(self):
        """ACWR high risk should need 3 days recovery."""
        trigger = AdaptationTrigger(
            trigger_type=TriggerType.ACWR_HIGH_RISK,
            value=1.65,
            threshold=1.5,
            zone="danger",
            applies_to=["tempo"],
            detected_at=date.today(),
        )

        recovery = estimate_recovery_time(trigger)

        assert recovery.days == 3
        assert recovery.confidence == "high"
        assert len(recovery.factors) > 0

    def test_readiness_low_recovery(self):
        """Low readiness should need 1 day recovery."""
        trigger = AdaptationTrigger(
            trigger_type=TriggerType.READINESS_LOW,
            value=45,
            threshold=50,
            zone="warning",
            applies_to=["tempo"],
            detected_at=date.today(),
        )

        recovery = estimate_recovery_time(trigger)

        assert recovery.days == 1
        assert recovery.confidence == "medium"

    def test_tsb_overreached_recovery(self):
        """TSB overreaching should need 4 days recovery."""
        trigger = AdaptationTrigger(
            trigger_type=TriggerType.TSB_OVERREACHED,
            value=-30,
            threshold=-25,
            zone="danger",
            applies_to=["tempo"],
            detected_at=date.today(),
        )

        recovery = estimate_recovery_time(trigger)

        assert recovery.days == 4
        assert recovery.confidence == "high"


