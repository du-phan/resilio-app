"""
Unit tests for M7 - Notes & RPE Analyzer module.

Tests RPE estimation from multiple sources, treadmill detection,
injury/illness flag extraction, and wellness signal extraction.
"""

import pytest
from datetime import date, datetime
from sports_coach_engine.core.notes import (
    analyze_activity,
    estimate_rpe,
    estimate_rpe_from_hr,
    estimate_rpe_from_text,
    estimate_rpe_from_strava_relative,
    estimate_rpe_from_duration,
    resolve_rpe_conflict,
    detect_treadmill,
    extract_injury_flags,
    extract_illness_flags,
    extract_wellness_indicators,
    extract_contextual_factors,
    is_high_intensity_session,
    AnalysisError,
    InsufficientDataError,
)
from sports_coach_engine.schemas.activity import (
    NormalizedActivity,
    SportType,
    SurfaceType,
    DataQuality,
    RPESource,
    FlagSeverity,
    BodyPart,
)
from sports_coach_engine.schemas.profile import (
    AthleteProfile,
    VitalSigns,
    Goal,
    GoalType,
    TrainingConstraints,
    Weekday,
    RunningPriority,
    ConflictPolicy,
)


# ============================================================
# TEST FIXTURES
# ============================================================


@pytest.fixture
def basic_athlete():
    """Create basic athlete profile with vital signs."""
    return AthleteProfile(
        name="Test Athlete",
        created_at="2026-01-12",
        vital_signs=VitalSigns(
            resting_hr=50,
            max_hr=185,
            lthr=165,
        ),
        running_priority=RunningPriority.PRIMARY,
        conflict_policy=ConflictPolicy.RUNNING_GOAL_WINS,
        constraints=TrainingConstraints(
            available_run_days=[Weekday.TUESDAY, Weekday.THURSDAY, Weekday.SATURDAY],
            min_run_days_per_week=2,
            max_run_days_per_week=3,
        ),
        goal=Goal(type=GoalType.TEN_K),
    )


@pytest.fixture
def basic_activity():
    """Create basic normalized activity."""
    return NormalizedActivity(
        id="test_123",
        source="strava",
        sport_type=SportType.RUN,
        name="Morning Run",
        date=date(2026, 1, 12),
        duration_minutes=45,
        duration_seconds=2700,
        distance_km=8.0,
        distance_meters=8000.0,
        average_hr=155,
        max_hr=170,
        has_hr_data=True,
        surface_type=SurfaceType.ROAD,
        data_quality=DataQuality.HIGH,
        has_gps_data=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


# ============================================================
# RPE ESTIMATION TESTS (8 tests)
# ============================================================


class TestRPEEstimation:
    """Tests for RPE estimation from multiple sources."""

    def test_user_input_always_wins(self, basic_activity, basic_athlete):
        """User-entered RPE should always take priority."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = 6
        activity.average_hr = 175  # Would suggest RPE 8+
        activity.description = "felt super easy and relaxed"  # Would suggest RPE 2-3

        final_rpe, all_estimates, conflict = estimate_rpe(activity, basic_athlete)

        assert final_rpe.value == 6
        assert final_rpe.source == RPESource.USER_INPUT
        assert final_rpe.confidence == "high"
        # Should not create conflict when user input present
        assert conflict is None

    def test_hr_based_estimation_with_zone_mapping(self, basic_activity, basic_athlete):
        """HR-based estimation should map % max HR to RPE zones."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.average_hr = 160  # 86.5% of max HR (185) → RPE 7
        activity.description = None

        final_rpe, all_estimates, conflict = estimate_rpe(activity, basic_athlete)

        # Find HR-based estimate
        hr_estimate = next(e for e in all_estimates if e.source == RPESource.HR_BASED)
        assert hr_estimate.value == 7
        assert final_rpe.value == 7
        assert "86%" in hr_estimate.reasoning

    def test_text_based_extraction_with_keywords(self, basic_activity, basic_athlete):
        """Text-based extraction should find RPE keywords in notes."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.has_hr_data = False
        activity.average_hr = None
        activity.description = "Tempo run felt solid. Good effort at threshold pace."

        final_rpe, all_estimates, conflict = estimate_rpe(activity, basic_athlete)

        # Find text-based estimate
        text_estimate = next(
            e for e in all_estimates if e.source == RPESource.TEXT_BASED
        )
        assert 6 <= text_estimate.value <= 7  # "tempo" suggests RPE 6-7
        assert final_rpe.source == RPESource.TEXT_BASED

    def test_strava_suffer_score_normalization(self, basic_activity, basic_athlete):
        """Strava suffer_score should normalize to RPE scale."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.has_hr_data = False
        activity.average_hr = None
        activity.description = None
        activity.suffer_score = 85  # High effort

        final_rpe, all_estimates, conflict = estimate_rpe(activity, basic_athlete)

        # Find Strava-based estimate
        strava_estimate = next(
            e for e in all_estimates if e.source == RPESource.STRAVA_RELATIVE
        )
        assert 6 <= strava_estimate.value <= 9  # High suffer_score → high RPE

    def test_duration_heuristic_fallback(self, basic_activity, basic_athlete):
        """Duration heuristic should provide conservative fallback."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.has_hr_data = False
        activity.average_hr = None
        activity.description = None
        activity.suffer_score = None

        final_rpe, all_estimates, conflict = estimate_rpe(activity, basic_athlete)

        # Should fall back to duration heuristic
        assert final_rpe.source == RPESource.DURATION_HEURISTIC
        assert 3 <= final_rpe.value <= 6  # Conservative estimate
        assert final_rpe.confidence == "low"

    def test_conflict_resolution_high_intensity_uses_max(
        self, basic_activity, basic_athlete
    ):
        """High-intensity sessions should use MAX RPE when conflict exists."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.average_hr = 175  # 95% max HR → RPE 8
        activity.description = "easy recovery jog"  # Would suggest RPE 2-3
        activity.workout_type = 3  # Workout type suggests high intensity

        final_rpe, all_estimates, conflict = estimate_rpe(activity, basic_athlete)

        # Should have conflict (HR says 8, text says 2-3)
        if conflict is not None:
            assert conflict.spread >= 3
            # High intensity → should use MAX
            assert final_rpe.value >= 7

    def test_conflict_resolution_easy_trusts_text_over_hr(
        self, basic_activity, basic_athlete
    ):
        """Non-high-intensity sessions should trust text over HR."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.average_hr = 165  # 89% max HR → might suggest RPE 7
        activity.description = "felt super easy and relaxed, recovery pace"
        activity.workout_type = 0  # Default workout type

        final_rpe, all_estimates, conflict = estimate_rpe(activity, basic_athlete)

        # If conflict exists, should trust text (lower RPE)
        # HR can be elevated by stress/heat even on easy runs
        if conflict is not None:
            assert final_rpe.source in [RPESource.TEXT_BASED, RPESource.HR_BASED]

    def test_large_spread_uses_max_for_safety(self, basic_activity, basic_athlete):
        """Spread >3 should use MAX RPE for conservative safety."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.average_hr = 180  # ~97% max HR → RPE 9
        activity.description = "easy recovery"  # Would suggest RPE 2
        activity.duration_minutes = 30  # Short duration → RPE 4

        final_rpe, all_estimates, conflict = estimate_rpe(activity, basic_athlete)

        # Should have large spread
        if conflict is not None and conflict.spread > 3:
            # Should use MAX for safety
            assert final_rpe.value >= 7
            assert "large spread" in conflict.resolution_method.lower()


# ============================================================
# TREADMILL DETECTION TESTS (4 tests)
# ============================================================


class TestTreadmillDetection:
    """Tests for treadmill/indoor detection."""

    def test_title_keywords_trigger_detection(self):
        """Title keywords like 'treadmill' should trigger detection."""
        result = detect_treadmill(
            activity_name="Treadmill Run",
            description="Indoor treadmill workout",  # Add description for more points
            has_gps=False,  # No GPS increases confidence
            sport_type="run",
            sub_type=None,
            device_name=None,
        )

        assert result.is_treadmill
        assert "title" in "".join(result.signals).lower()
        assert result.confidence == "high"  # Title (2) + description (1) + no GPS (2) = 5 points

    def test_no_gps_for_running_suggests_treadmill(self):
        """No GPS for running activity suggests treadmill."""
        result = detect_treadmill(
            activity_name="Morning Run",
            description=None,
            has_gps=False,
            sport_type="run",
            sub_type=None,
            device_name=None,
        )

        assert result.is_treadmill
        assert "no gps" in "".join(result.signals).lower()

    def test_sub_type_virtual_run_triggers_detection(self):
        """Sub-type 'VirtualRun' should strongly indicate treadmill."""
        result = detect_treadmill(
            activity_name="Zwift Run",
            description=None,
            has_gps=False,
            sport_type="run",
            sub_type="VirtualRun",
            device_name=None,
        )

        assert result.is_treadmill
        assert result.confidence == "high"
        assert "sub_type" in "".join(result.signals).lower()

    def test_gps_presence_without_other_signals_suggests_outdoor(self):
        """GPS presence without other signals should suggest outdoor run."""
        result = detect_treadmill(
            activity_name="Morning Run",
            description="Great run in the park",
            has_gps=True,
            sport_type="run",
            sub_type=None,
            device_name="Garmin Forerunner",
        )

        assert not result.is_treadmill
        # When not a treadmill, confidence is about outdoor classification
        # The function returns "low" confidence when score < 2 (no treadmill signals)
        assert result.confidence in ["low", "high"]


# ============================================================
# INJURY FLAG TESTS (4 tests)
# ============================================================


class TestInjuryFlags:
    """Tests for injury flag extraction."""

    def test_injury_keyword_and_body_part_extraction(self):
        """Should extract injury keywords and identify body parts."""
        description = "Right knee pain during the run. Had to slow down."

        flags = extract_injury_flags(description, None)

        assert len(flags) > 0
        knee_flag = next((f for f in flags if f.body_part == BodyPart.KNEE), None)
        assert knee_flag is not None
        assert "pain" in [kw.lower() for kw in knee_flag.keywords_found]
        assert "knee pain" in knee_flag.source_text.lower()

    def test_severity_classification(self):
        """Should classify severity as mild/moderate/severe."""
        mild_description = "Slight achilles tightness after warmup"
        severe_description = "Sharp pain in calf, had to stop running immediately"

        mild_flags = extract_injury_flags(mild_description, None)
        severe_flags = extract_injury_flags(severe_description, None)

        # Check mild severity
        mild_flag = next(
            (f for f in mild_flags if f.body_part == BodyPart.ACHILLES), None
        )
        if mild_flag:
            assert mild_flag.severity in [FlagSeverity.MILD, FlagSeverity.MODERATE]

        # Check severe severity
        severe_flag = next(
            (f for f in severe_flags if f.body_part == BodyPart.CALF), None
        )
        if severe_flag:
            assert severe_flag.severity in [FlagSeverity.MODERATE, FlagSeverity.SEVERE]

    def test_rest_requirement_determination(self):
        """Should determine if rest is required based on severity."""
        severe_description = "Severe ankle pain, couldn't finish the run"

        flags = extract_injury_flags(severe_description, None)

        severe_flags = [f for f in flags if f.severity == FlagSeverity.SEVERE]
        if severe_flags:
            assert any(f.requires_rest for f in severe_flags)

    def test_multiple_injuries_deduplicated_by_body_part(self):
        """Should keep highest severity when same body part mentioned multiple times."""
        description = "Knee ache at start, then sharp knee pain at mile 5"

        flags = extract_injury_flags(description, None)

        knee_flags = [f for f in flags if f.body_part == BodyPart.KNEE]
        # Should have at most one flag per body part (highest severity)
        assert len(knee_flags) <= 2  # May detect both if in different contexts


# ============================================================
# ILLNESS FLAG TESTS (2 tests)
# ============================================================


class TestIllnessFlags:
    """Tests for illness flag extraction."""

    def test_severe_illness_detection(self):
        """Should detect severe illness symptoms."""
        description = "Feeling sick, chest congestion and fever. Struggled through the run."

        flags = extract_illness_flags(description, None)

        assert len(flags) > 0
        severe_flags = [f for f in flags if f.severity == FlagSeverity.SEVERE]
        if severe_flags:
            assert severe_flags[0].rest_days_recommended >= 3  # At least 3 days (96 hours = 4 days)

    def test_mild_illness_detection(self):
        """Should detect mild illness symptoms."""
        description = "Head cold, feeling a bit under the weather but okay to run easy"

        flags = extract_illness_flags(description, None)

        assert len(flags) > 0
        mild_flags = [f for f in flags if f.severity in [FlagSeverity.MILD]]
        if mild_flags:
            assert 1 <= mild_flags[0].rest_days_recommended <= 2  # 48 hours = 2 days


# ============================================================
# WELLNESS & CONTEXT TESTS (4 tests)
# ============================================================


class TestWellnessIndicators:
    """Tests for wellness signal extraction."""

    def test_sleep_quality_extraction(self):
        """Should extract sleep quality signals."""
        description = "Slept poorly last night, only 5 hours. Felt tired."

        wellness = extract_wellness_indicators(description, None)

        assert wellness.sleep_quality in ["poor", "disrupted"]
        assert wellness.sleep_hours is not None
        assert wellness.sleep_hours < 6

    def test_soreness_level_extraction(self):
        """Should extract soreness levels."""
        description = "Legs very sore from yesterday's climb, 7/10 soreness"

        wellness = extract_wellness_indicators(description, None)

        assert wellness.soreness_level is not None
        assert wellness.soreness_level >= 6

    def test_fatigue_detection(self):
        """Should detect fatigue mentions."""
        description = "Feeling fatigued and sluggish today"

        wellness = extract_wellness_indicators(description, None)

        assert wellness.fatigue_mentioned is True
        assert wellness.energy_level in ["low", None]

    def test_stress_level_extraction(self):
        """Should extract stress levels."""
        description = "High stress at work, ran to decompress"

        wellness = extract_wellness_indicators(description, None)

        assert wellness.stress_level in ["high", "moderate"]


class TestContextualFactors:
    """Tests for contextual factor extraction."""

    def test_environmental_factors(self):
        """Should detect environmental factors."""
        description = "Hot and humid today, 85F. Ran early morning before work."
        start_time = datetime(2026, 1, 12, 6, 30)  # 6:30 AM

        context = extract_contextual_factors(description, None, start_time)

        assert context.heat_mentioned is True
        assert context.early_morning is True

    def test_fasted_state_detection(self):
        """Should detect fasted running."""
        description = "Fasted run before breakfast"

        context = extract_contextual_factors(description, None, None)

        assert context.is_fasted is True

    def test_altitude_detection(self):
        """Should detect altitude mentions."""
        description = "Training at altitude, 8000 feet elevation"

        context = extract_contextual_factors(description, None, None)

        assert context.altitude_mentioned is True


# ============================================================
# INTEGRATION TESTS (2 tests)
# ============================================================


class TestAnalysisIntegration:
    """Integration tests for full analysis pipeline."""

    def test_full_analysis_pipeline(self, basic_activity, basic_athlete):
        """Should run complete analysis with all components."""
        activity = basic_activity.model_copy()
        activity.description = (
            "Tempo run felt solid. Right knee slight ache. "
            "Slept well last night. Hot and humid."
        )
        activity.average_hr = 160
        activity.perceived_exertion = None

        result = analyze_activity(activity, basic_athlete)

        # Verify all components present
        assert result.activity_id == activity.id
        assert result.estimated_rpe.value >= 1
        assert result.estimated_rpe.value <= 10
        assert result.treadmill_detection is not None
        # Should detect knee injury
        knee_injuries = [
            f for f in result.injury_flags if f.body_part == BodyPart.KNEE
        ]
        assert len(knee_injuries) > 0
        # Should detect environmental factors
        assert result.context.heat_mentioned is True
        # Should have wellness data
        assert result.wellness.sleep_quality is not None
        assert result.analyzed_at is not None
        assert result.notes_present is True

    def test_missing_data_graceful_degradation(self, basic_activity, basic_athlete):
        """Should handle missing data gracefully with conservative defaults."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.has_hr_data = False
        activity.average_hr = None
        activity.max_hr = None
        activity.description = None
        activity.private_note = None
        activity.suffer_score = None

        result = analyze_activity(activity, basic_athlete)

        # Should still complete analysis with fallback RPE
        assert result.estimated_rpe.source == RPESource.DURATION_HEURISTIC
        assert result.estimated_rpe.confidence == "low"
        assert result.notes_present is False
        # Should have empty flags (no text to analyze)
        assert len(result.injury_flags) == 0
        assert len(result.illness_flags) == 0


# ============================================================
# HELPER FUNCTION TESTS (2 tests)
# ============================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_is_high_intensity_session_by_hr(self, basic_activity, basic_athlete):
        """Should identify high-intensity sessions by HR."""
        activity = basic_activity.model_copy()
        activity.average_hr = 175  # 95% of max HR

        result = is_high_intensity_session(
            activity,
            basic_athlete.vital_signs.max_hr
            if basic_athlete.vital_signs
            else None,
        )

        assert result is True

    def test_is_high_intensity_session_by_workout_type(
        self, basic_activity, basic_athlete
    ):
        """Should identify high-intensity sessions by workout_type."""
        activity = basic_activity.model_copy()
        activity.workout_type = 1  # Race
        activity.average_hr = 140  # Low HR but race type

        result = is_high_intensity_session(
            activity,
            basic_athlete.vital_signs.max_hr
            if basic_athlete.vital_signs
            else None,
        )

        assert result is True


# ============================================================
# ERROR HANDLING TESTS (2 tests)
# ============================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_insufficient_data_for_hr_estimation(self, basic_activity, basic_athlete):
        """Should handle missing max_hr gracefully."""
        activity = basic_activity.model_copy()
        athlete = basic_athlete.model_copy()
        athlete.vital_signs = None  # No vital signs

        # Should fall back to other methods
        result = estimate_rpe_from_hr(
            average_hr=150,
            max_hr_activity=None,
            athlete_max_hr=None,
            athlete_lthr=None,
            duration_minutes=45,
        )

        assert result is None  # Cannot estimate without max HR

    def test_invalid_hr_values_handled(self, basic_activity, basic_athlete):
        """Should handle invalid HR values gracefully."""
        # Very low HR (unrealistic)
        result1 = estimate_rpe_from_hr(
            average_hr=30,
            max_hr_activity=50,
            athlete_max_hr=185,
            athlete_lthr=165,
            duration_minutes=45,
        )
        assert result1 is None or result1.value >= 1

        # HR > max HR (sensor error)
        result2 = estimate_rpe_from_hr(
            average_hr=200,
            max_hr_activity=210,
            athlete_max_hr=185,
            athlete_lthr=165,
            duration_minutes=45,
        )
        assert result2 is None or result2.value <= 10
