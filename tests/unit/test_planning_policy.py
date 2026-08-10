"""Deterministic enforcement of approved weekly planning policy."""

from datetime import date, datetime, time, timezone

import pytest

from resilio.core.planning.policy import (
    WeekPolicyError,
    validate_populated_week,
)
from resilio.schemas.planning.constraints import (
    AthleteManagedSportExpectation,
    PlanningConstraintsSnapshot,
)
from resilio.schemas.planning.plans import RaceMacroPlan
from resilio.schemas.planning.weeks import WeekPlan
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.profile import (
    BalancedTrainingPriority,
    FlexibleWeeklyParticipation,
    RecurringWeeklyParticipation,
    RunSameDayPermission,
    Weekday,
)


def _workout(
    workout_id: str,
    *,
    day: int,
    distance_meters: float | None,
    duration_seconds: int,
    workout_type: str = "easy",
    low_seconds: int | None = None,
    high_seconds: int = 0,
    start_time_local: time = time(7),
) -> RunningWorkoutPrescription:
    low = duration_seconds - high_seconds if low_seconds is None else low_seconds
    structured_workout = {
        "sport": "run",
        "steps": [
            {
                "kind": "steady",
                "duration": {"unit": "seconds", "value": duration_seconds},
                "intensity": "active",
                "cue": "Follow the approved session intent.",
            }
        ],
    }
    return RunningWorkoutPrescription(
        id=workout_id,
        date=date(2026, 7, day),
        start_time_local=start_time_local,
        workout_type=workout_type,
        planned_duration_seconds=duration_seconds,
        planned_distance_meters=distance_meters,
        planned_low_intensity_duration_seconds=low,
        planned_moderate_intensity_duration_seconds=(duration_seconds - low - high_seconds),
        planned_high_intensity_duration_seconds=high_seconds,
        target_rpe_1_to_10=3,
        purpose="Provide a deterministic policy-test session.",
        structured_workout=structured_workout,
    )


def _week(
    *,
    workouts: list[RunningWorkoutPrescription] | None = None,
    fitzgerald: bool = False,
) -> WeekPlan:
    return WeekPlan(
        week_number=1,
        phase="base",
        start_date=date(2026, 7, 27),
        end_date=date(2026, 8, 2),
        target_run_volume_meters=10_000,
        workout_structure_hints={
            "quality": {
                "maximum_sessions": 1,
                "types": ["intervals"],
            },
            "long_run": {
                "emphasis": "easy",
                "minimum_weekly_run_volume_percent": 35,
                "maximum_weekly_run_volume_percent": 45,
                "target_distance_meters": 4_000,
            },
            "intensity_distribution": (
                {
                    "methodology": "fitzgerald_80_20",
                    "minimum_low_intensity_time_percent": 80,
                }
                if fitzgerald
                else None
            ),
        },
        running_workouts=workouts or [],
    )


def _valid_runs() -> list[RunningWorkoutPrescription]:
    return [
        _workout(
            "w_easy_a",
            day=28,
            distance_meters=3_000,
            duration_seconds=1_800,
        ),
        _workout(
            "w_intervals",
            day=30,
            distance_meters=3_000,
            duration_seconds=1_800,
            workout_type="intervals",
            low_seconds=1_200,
            high_seconds=600,
        ),
        _workout(
            "w_long",
            day=31,
            distance_meters=4_000,
            duration_seconds=2_400,
            workout_type="long_run",
        ),
    ]


def _plan(
    skeleton: WeekPlan,
    *,
    constraints: PlanningConstraintsSnapshot | None = None,
    methodology: str = "daniels",
) -> RaceMacroPlan:
    return RaceMacroPlan(
        id="plan_policy",
        plan_revision_id="plan_revision_0123456789abcdef",
        vdot_approval_id="vdot_approval_0123456789abcdef",
        planning_context_reference={
            "artifact_type": "macro_planning_context",
            "artifact_sha256": "c" * 64,
        },
        planning_inputs_sha256="a" * 64,
        created_at_utc=datetime(2026, 7, 25, tzinfo=timezone.utc),
        planning_rationale=(
            "The policy fixture binds its macro choices to explicit athlete "
            "constraints and an approved performance baseline."
        ),
        adaptation_decisions=[
            {
                "decision_type": "methodology_selection",
                "evidence_ids": ["profile.current_constraints"],
                "observed_facts": (
                    "The athlete goal and weekly availability are explicit in "
                    "the planning evidence fixture."
                ),
                "planning_change": (
                    "Use one controlled methodology for this complete policy " "validation horizon."
                ),
                "affected_week_numbers": [1],
            },
            {
                "decision_type": "starting_volume",
                "evidence_ids": ["profile.current_constraints"],
                "observed_facts": (
                    "The athlete evidence supports the exact opening-week "
                    "frequency and running-volume fixture."
                ),
                "planning_change": (
                    "Begin at ten thousand planned running meters and preserve "
                    "the explicit session constraints."
                ),
                "affected_week_numbers": [1],
            },
        ],
        goal={
            "type": "10k",
            "target_date": date(2026, 8, 2),
            "target_time": "00:45:00",
        },
        methodology={
            "identifier": methodology,
            "source_document": (
                "docs/training_books/80_20_matt_fitzgerald.md"
                if methodology == "fitzgerald_80_20"
                else "docs/training_books/daniels_running_formula.md"
            ),
            "source_revision_sha256": "b" * 64,
            "source_edition": "fourth_edition_conceptual_reference",
            "source_summary_version": "2026-07-30",
            "source_verification_scope": "conceptual_summary_only",
            "planning_authority": "coach_designed_conceptually_informed",
            "executable_policy_version": "coach_planning_policy_v1",
            "selection_rationale": (
                "The athlete's exact schedule and goal support this controlled "
                "methodology selection."
            ),
        },
        weeks=[skeleton],
        baseline_vdot=45,
        constraints_snapshot=constraints
        or PlanningConstraintsSnapshot(
            minimum_run_days_per_week=2,
            maximum_run_days_per_week=4,
            maximum_session_duration_seconds=5_400,
            training_priority=BalancedTrainingPriority(),
            training_timezone="Europe/Paris",
        ),
    )


def test_valid_week_satisfies_frequency_quality_and_long_run_policy() -> None:
    skeleton = _week()
    plan = _plan(skeleton)
    populated = _week(workouts=_valid_runs())

    validate_populated_week(plan, populated)


def test_policy_reports_stable_availability_duration_and_quality_violations() -> None:
    skeleton = _week()
    plan = _plan(
        skeleton,
        constraints=PlanningConstraintsSnapshot(
            unavailable_run_days=["tuesday"],
            minimum_run_days_per_week=2,
            maximum_run_days_per_week=4,
            maximum_session_duration_seconds=1_500,
            training_priority=BalancedTrainingPriority(),
            training_timezone="Europe/Paris",
        ),
    )
    runs = _valid_runs()
    runs[1] = runs[1].model_copy(update={"workout_type": "tempo"})
    populated = _week(workouts=runs)

    with pytest.raises(WeekPolicyError) as caught:
        validate_populated_week(plan, populated)

    codes = [item.code for item in caught.value.violations]
    assert codes == sorted(codes)
    assert "run_scheduled_on_unavailable_day" in codes
    assert "session_duration_above_maximum" in codes
    assert "quality_session_type_not_approved" in codes


def test_fitzgerald_policy_rejects_all_high_week() -> None:
    skeleton = _week(fitzgerald=True)
    plan = _plan(skeleton, methodology="fitzgerald_80_20")
    runs = [
        workout.model_copy(
            update={
                "planned_low_intensity_duration_seconds": 0,
                "planned_moderate_intensity_duration_seconds": 0,
                "planned_high_intensity_duration_seconds": (workout.planned_duration_seconds),
            }
        )
        for workout in _valid_runs()
    ]
    populated = _week(workouts=runs, fitzgerald=True)

    with pytest.raises(
        WeekPolicyError,
        match="fitzgerald_low_intensity_below_minimum",
    ):
        validate_populated_week(plan, populated)


def test_recurring_athlete_managed_sport_can_prohibit_same_day_running() -> None:
    constraints = PlanningConstraintsSnapshot(
        minimum_run_days_per_week=2,
        maximum_run_days_per_week=4,
        maximum_session_duration_seconds=5_400,
        athlete_managed_sport_expectations=[
            AthleteManagedSportExpectation(
                sport_name="crossfit",
                participation_pattern=RecurringWeeklyParticipation(
                    weekdays=[Weekday.TUESDAY],
                    run_same_day_permission=RunSameDayPermission.PROHIBITED,
                ),
                typical_session_duration_seconds=3_600,
                athlete_reported_typical_intensity="moderate",
            )
        ],
        training_priority=BalancedTrainingPriority(),
        training_timezone="Europe/Paris",
    )
    skeleton = _week()
    plan = _plan(skeleton, constraints=constraints)
    populated = _week(workouts=_valid_runs())

    with pytest.raises(
        WeekPolicyError,
        match="run_on_prohibited_recurring_sport_day",
    ):
        validate_populated_week(plan, populated)


def test_flexible_athlete_managed_sport_does_not_invent_run_blackout_days() -> None:
    constraints = PlanningConstraintsSnapshot(
        minimum_run_days_per_week=2,
        maximum_run_days_per_week=4,
        maximum_session_duration_seconds=5_400,
        athlete_managed_sport_expectations=[
            AthleteManagedSportExpectation(
                sport_name="climb",
                participation_pattern=FlexibleWeeklyParticipation(
                    expected_sessions_per_week=3,
                ),
                typical_session_duration_seconds=5_400,
                athlete_reported_typical_intensity="moderate_to_hard",
            )
        ],
        training_priority=BalancedTrainingPriority(),
        training_timezone="Europe/Paris",
    )
    skeleton = _week()
    plan = _plan(skeleton, constraints=constraints)

    validate_populated_week(plan, _week(workouts=_valid_runs()))


def test_race_week_can_explicitly_omit_a_long_run() -> None:
    race = _workout(
        "goal_race",
        day=31,
        distance_meters=10_000,
        duration_seconds=2_700,
        workout_type="race",
    ).model_copy(update={"date": date(2026, 8, 2)})
    race_week = _week(workouts=[race])
    race_week.workout_structure_hints.long_run = None
    race_week.workout_structure_hints.quality.types = ["race_pace"]
    plan = _plan(
        race_week.model_copy(update={"running_workouts": []}),
        constraints=PlanningConstraintsSnapshot(
            minimum_run_days_per_week=1,
            maximum_run_days_per_week=4,
            maximum_session_duration_seconds=5_400,
            training_priority=BalancedTrainingPriority(),
            training_timezone="Europe/Paris",
        ),
    )

    validate_populated_week(plan, race_week)


def test_policy_rejects_sessions_that_overlap_across_midnight() -> None:
    runs = _valid_runs()
    runs[0] = runs[0].model_copy(
        update={
            "date": date(2026, 7, 28),
            "start_time_local": time(23, 45),
        }
    )
    runs[1] = runs[1].model_copy(
        update={
            "date": date(2026, 7, 29),
            "start_time_local": time(0),
        }
    )
    populated = _week(workouts=runs)
    plan = _plan(populated.model_copy(update={"running_workouts": []}))

    with pytest.raises(WeekPolicyError, match="sessions_overlap"):
        validate_populated_week(plan, populated)
