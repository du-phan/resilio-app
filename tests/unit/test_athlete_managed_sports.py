from datetime import date

import pytest
from pydantic import ValidationError

from resilio.schemas.planning.applications import WeekApplication
from resilio.schemas.planning.constraints import (
    AthleteManagedSportExpectation,
    PlanningConstraintsSnapshot,
)
from resilio.schemas.profile import (
    AthleteManagedSport,
    AthleteManagedSportFirstPriority,
    AthleteProfile,
    BalancedTrainingPriority,
    FlexibleWeeklyParticipation,
    RecurringWeeklyParticipation,
    RunSameDayPermission,
    TrainingConstraints,
    TypicalIntensity,
    Weekday,
)


def _profile(
    *,
    sports: list[AthleteManagedSport],
    training_priority: object | None = None,
) -> AthleteProfile:
    return AthleteProfile(
        athlete_name="Athlete",
        created_on=date(2026, 8, 9),
        training_timezone="Europe/Paris",
        constraints=TrainingConstraints(
            minimum_run_days_per_week=1,
            maximum_run_days_per_week=3,
        ),
        athlete_managed_sports=sports,
        training_priority=training_priority or BalancedTrainingPriority(),
    )


def test_flexible_sport_is_future_context_without_scheduled_days() -> None:
    sport = AthleteManagedSport(
        sport_name="climb",
        participation_pattern=FlexibleWeeklyParticipation(
            expected_sessions_per_week=3,
        ),
        typical_session_duration_minutes=90,
        athlete_reported_typical_intensity=TypicalIntensity.MODERATE_TO_HARD,
    )

    profile = _profile(
        sports=[sport],
        training_priority=AthleteManagedSportFirstPriority(sport_name="climb"),
    )

    assert profile.athlete_managed_sports[0].participation_pattern.kind == "flexible_weekly"
    assert not hasattr(
        profile.athlete_managed_sports[0].participation_pattern,
        "weekdays",
    )


def test_recurring_sport_rejects_duplicate_weekdays() -> None:
    with pytest.raises(ValidationError, match="weekdays must be unique"):
        RecurringWeeklyParticipation(
            weekdays=[Weekday.MONDAY, Weekday.MONDAY],
            run_same_day_permission=RunSameDayPermission.PROHIBITED,
        )


def test_active_managed_sport_rejects_pause_metadata() -> None:
    with pytest.raises(ValidationError, match="active athlete-managed sport"):
        AthleteManagedSport(
            sport_name="climb",
            participation_pattern=FlexibleWeeklyParticipation(
                expected_sessions_per_week=2,
            ),
            active=True,
            pause_reason="off_season",
            paused_on=date(2026, 8, 10),
        )


def test_inactive_managed_sport_requires_pause_date() -> None:
    with pytest.raises(ValidationError, match="require a paused_on date"):
        AthleteManagedSport(
            sport_name="climb",
            participation_pattern=FlexibleWeeklyParticipation(
                expected_sessions_per_week=2,
            ),
            active=False,
            pause_reason="off_season",
        )


def test_other_sport_first_priority_must_reference_active_managed_sport() -> None:
    with pytest.raises(ValidationError, match="must reference an active athlete-managed sport"):
        _profile(
            sports=[],
            training_priority=AthleteManagedSportFirstPriority(sport_name="climb"),
        )


def test_week_application_rejects_non_running_workout_payload() -> None:
    with pytest.raises(ValidationError):
        WeekApplication.model_validate(
            {
                "schema_version": 2,
                "week_number": 1,
                "running_workouts": [
                    {
                        "id": "climb-1",
                        "date": "2026-08-10",
                        "sport": "climb",
                        "workout_type": "easy",
                        "planned_duration_seconds": 3600,
                        "planned_distance_meters": 1000,
                        "planned_low_intensity_duration_seconds": 3600,
                        "planned_moderate_intensity_duration_seconds": 0,
                        "planned_high_intensity_duration_seconds": 0,
                        "target_rpe_1_to_10": 4,
                        "purpose": "Must be rejected before publication.",
                        "structured_workout": None,
                    }
                ],
                "adjustment_rationale": (
                    "Only running prescriptions can enter the weekly application lifecycle."
                ),
            }
        )


def test_planning_expectation_rejects_running_sport() -> None:
    with pytest.raises(ValidationError, match="cannot reference running"):
        AthleteManagedSportExpectation(
            sport_name="trail_run",
            participation_pattern=FlexibleWeeklyParticipation(
                expected_sessions_per_week=1,
            ),
            typical_session_duration_seconds=3_600,
            athlete_reported_typical_intensity=TypicalIntensity.EASY,
        )


def test_planning_priority_must_reference_projected_managed_sport() -> None:
    with pytest.raises(ValidationError, match="must reference an expected sport"):
        PlanningConstraintsSnapshot(
            minimum_run_days_per_week=1,
            maximum_run_days_per_week=3,
            athlete_managed_sport_expectations=[],
            training_priority=AthleteManagedSportFirstPriority(sport_name="climb"),
            training_timezone="Europe/Paris",
        )
