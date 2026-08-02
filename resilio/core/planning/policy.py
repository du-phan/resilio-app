"""Deterministic cross-object policy for exact weekly applications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from resilio.core.planning.schedule import (
    WorkoutScheduleError,
    scheduled_start_utc,
)
from resilio.schemas.activity import RUNNING_SPORT_VALUES
from resilio.schemas.plan import (
    BaselineAssessmentPlan,
    TrainingPlan,
    WeekPlan,
    WorkoutPrescription,
    WorkoutType,
)
from resilio.schemas.vdot import RaceDistance

PLANNING_POLICY_VERSION: Literal[
    "coach_planning_policy_v1"
] = "coach_planning_policy_v1"

QUALITY_ROLE_BY_WORKOUT_TYPE = {
    WorkoutType.TEMPO.value: "tempo",
    WorkoutType.INTERVALS.value: "intervals",
    WorkoutType.HILLS.value: "hills",
    WorkoutType.RACE_PACE.value: "race_pace",
    WorkoutType.FARTLEK.value: "fartlek",
    WorkoutType.STRIDES.value: "strides_only",
    WorkoutType.RACE.value: "race_pace",
    WorkoutType.BENCHMARK.value: "benchmark",
}


@dataclass(frozen=True, order=True)
class WeekPolicyViolation:
    code: str
    json_path: str
    message: str


class WeekPolicyError(RuntimeError):
    """One exact week violates its approved plan and profile policy."""

    def __init__(self, violations: list[WeekPolicyViolation]):
        self.violations = sorted(violations)
        rendered = "; ".join(
            f"{item.code} at {item.json_path}: {item.message}" for item in self.violations
        )
        super().__init__(rendered)


def _weekday(workout_date: date) -> str:
    return workout_date.strftime("%A").casefold()


def _append(
    violations: list[WeekPolicyViolation],
    *,
    code: str,
    path: str,
    message: str,
) -> None:
    violations.append(
        WeekPolicyViolation(
            code=code,
            json_path=path,
            message=message,
        )
    )


def validate_populated_week(plan: TrainingPlan, week: WeekPlan) -> None:
    """Fail with stable violations when exact workouts break approved policy."""
    violations: list[WeekPolicyViolation] = []
    constraints = plan.constraints_snapshot
    run_workouts = [
        workout
        for workout in week.workouts
        if str(workout.sport) in RUNNING_SPORT_VALUES
    ]
    run_dates = {workout.date for workout in run_workouts}

    if len(run_dates) < constraints.minimum_run_days_per_week:
        _append(
            violations,
            code="run_frequency_below_minimum",
            path="workouts",
            message=(
                f"{len(run_dates)} run days is below the approved minimum "
                f"{constraints.minimum_run_days_per_week}"
            ),
        )
    if len(run_dates) > constraints.maximum_run_days_per_week:
        _append(
            violations,
            code="run_frequency_above_maximum",
            path="workouts",
            message=(
                f"{len(run_dates)} run days exceeds the approved maximum "
                f"{constraints.maximum_run_days_per_week}"
            ),
        )

    unavailable_run_days = set(constraints.unavailable_run_days)
    for index, workout in enumerate(week.workouts):
        path = f"workouts[{index}]"
        if (
            str(workout.sport) in RUNNING_SPORT_VALUES
            and workout.structured_workout is None
        ):
            _append(
                violations,
                code="run_structured_workout_missing",
                path=f"{path}.structured_workout",
                message="running workouts require a typed structured prescription",
            )
        if (
            constraints.maximum_session_duration_seconds is not None
            and workout.planned_duration_seconds > constraints.maximum_session_duration_seconds
        ):
            _append(
                violations,
                code="session_duration_above_maximum",
                path=f"{path}.planned_duration_seconds",
                message="session exceeds the athlete-confirmed duration limit",
            )
        if (
            str(workout.sport) in RUNNING_SPORT_VALUES
            and _weekday(workout.date) in unavailable_run_days
        ):
            _append(
                violations,
                code="run_scheduled_on_unavailable_day",
                path=f"{path}.date",
                message="run is scheduled on an athlete-unavailable run day",
            )

    for run_date in sorted(run_dates):
        same_day_count = sum(workout.date == run_date for workout in run_workouts)
        if same_day_count > 1:
            _append(
                violations,
                code="multiple_runs_on_one_day",
                path="workouts",
                message=f"{same_day_count} runs are scheduled on {run_date}",
            )

    _validate_other_sports(plan, week, violations)
    _validate_session_overlaps(plan, week, violations)
    _validate_quality_hints(week, violations)
    _validate_long_run(week, run_workouts, violations)
    _validate_fitzgerald_distribution(week, run_workouts, violations)
    if isinstance(plan, BaselineAssessmentPlan):
        _validate_temporary_schedule(plan, week, violations)
        _validate_assessment_benchmark(plan, week, violations)
    if violations:
        raise WeekPolicyError(violations)


def _validate_temporary_schedule(
    plan: BaselineAssessmentPlan,
    week: WeekPlan,
    violations: list[WeekPolicyViolation],
) -> None:
    for index, workout in enumerate(week.workouts):
        if any(
            constraint.contains(workout.date)
            for constraint in plan.temporary_schedule_constraints
        ):
            _append(
                violations,
                code="workout_on_temporary_unavailable_date",
                path=f"workouts[{index}].date",
                message="workout is scheduled during athlete-confirmed unavailability",
            )


def _validate_other_sports(
    plan: TrainingPlan,
    week: WeekPlan,
    violations: list[WeekPolicyViolation],
) -> None:
    commitments = {
        commitment.sport_name: commitment
        for commitment in plan.constraints_snapshot.active_other_sports
    }
    planned_other_sports: dict[
        str,
        list[tuple[int, WorkoutPrescription]],
    ] = {}
    for index, workout in enumerate(week.workouts):
        sport = str(workout.sport)
        if sport in RUNNING_SPORT_VALUES:
            continue
        planned_other_sports.setdefault(sport, []).append((index, workout))

    for sport_name, commitment in commitments.items():
        sessions = planned_other_sports.get(sport_name, [])
        required_sessions_per_week = commitment.sessions_per_week
        if isinstance(plan, BaselineAssessmentPlan):
            overrides = [
                override
                for override in plan.temporary_other_sport_commitment_overrides
                if override.week_start_date == week.start_date
                and override.sport_name == sport_name
            ]
            if overrides:
                required_sessions_per_week = overrides[0].sessions_per_week
        if len(sessions) != required_sessions_per_week:
            _append(
                violations,
                code="other_sport_session_count_mismatch",
                path="workouts",
                message=(
                    f"{sport_name} has {len(sessions)} sessions; the "
                    f"approved plan requires "
                    f"{required_sessions_per_week}"
                ),
            )
        unavailable_days = set(commitment.unavailable_days)
        for index, workout in sessions:
            if _weekday(workout.date) in unavailable_days:
                _append(
                    violations,
                    code="other_sport_scheduled_on_unavailable_day",
                    path=f"workouts[{index}].date",
                    message=(f"{sport_name} is scheduled on an unavailable day"),
                )

    for sport_name in sorted(set(planned_other_sports) - set(commitments)):
        _append(
            violations,
            code="unconfirmed_other_sport_session",
            path="workouts",
            message=(f"{sport_name} is not an active athlete-confirmed commitment"),
        )


def _validate_session_overlaps(
    plan: TrainingPlan,
    week: WeekPlan,
    violations: list[WeekPolicyViolation],
) -> None:
    scheduled: list[tuple[int, WorkoutPrescription, datetime]] = []
    for index, workout in enumerate(week.workouts):
        if workout.start_time_local is None:
            continue
        try:
            start_utc = scheduled_start_utc(
                workout,
                training_timezone=plan.constraints_snapshot.training_timezone,
            )
        except WorkoutScheduleError as exc:
            _append(
                violations,
                code="invalid_local_start_time",
                path=f"workouts[{index}].start_time_local",
                message=str(exc),
            )
            continue
        scheduled.append((index, workout, start_utc))
    for left_position, (left_index, left, left_start) in enumerate(scheduled):
        left_end = left_start + timedelta(seconds=left.planned_duration_seconds)
        for right_index, right, right_start in scheduled[left_position + 1 :]:
            right_end = right_start + timedelta(seconds=right.planned_duration_seconds)
            if max(left_start, right_start) < min(left_end, right_end):
                _append(
                    violations,
                    code="sessions_overlap",
                    path=f"workouts[{right_index}].start_time_local",
                    message=(
                        f"session overlaps workouts[{left_index}] across "
                        f"{left.date} to {right.date}"
                    ),
                )


def _validate_quality_hints(
    week: WeekPlan,
    violations: list[WeekPolicyViolation],
) -> None:
    hints = week.workout_structure_hints.quality
    allowed = set(hints.types)
    quality = [
        (index, QUALITY_ROLE_BY_WORKOUT_TYPE.get(str(workout.workout_type)))
        for index, workout in enumerate(week.workouts)
        if str(workout.sport) in RUNNING_SPORT_VALUES
        and str(workout.workout_type) in QUALITY_ROLE_BY_WORKOUT_TYPE
    ]
    if len(quality) > hints.maximum_sessions:
        _append(
            violations,
            code="quality_session_count_above_maximum",
            path="workouts",
            message=(
                f"{len(quality)} quality sessions exceeds the approved maximum "
                f"{hints.maximum_sessions}"
            ),
        )
    for index, role in quality:
        if role not in allowed:
            _append(
                violations,
                code="quality_session_type_not_approved",
                path=f"workouts[{index}].workout_type",
                message=f"quality role {role!r} is not in the macro hints",
            )


def _validate_long_run(
    week: WeekPlan,
    run_workouts: list[WorkoutPrescription],
    violations: list[WeekPolicyViolation],
) -> None:
    long_runs = [
        (index, workout)
        for index, workout in enumerate(week.workouts)
        if str(workout.sport) in RUNNING_SPORT_VALUES
        and workout.workout_type == WorkoutType.LONG_RUN.value
    ]
    hints = week.workout_structure_hints.long_run
    if hints is None:
        if long_runs:
            _append(
                violations,
                code="long_run_not_approved",
                path="workouts",
                message="the macro week explicitly approves zero long runs",
            )
        return
    if len(long_runs) != 1:
        _append(
            violations,
            code="long_run_count_not_one",
            path="workouts",
            message=f"expected exactly one long run, found {len(long_runs)}",
        )
        return
    index, long_run = long_runs[0]
    assert long_run.planned_distance_meters is not None
    share_percent = (
        Decimal(str(long_run.planned_distance_meters))
        * Decimal("100")
        / Decimal(str(week.target_run_volume_meters))
    )
    if share_percent < Decimal(str(hints.minimum_weekly_run_volume_percent)):
        _append(
            violations,
            code="long_run_share_below_minimum",
            path=f"workouts[{index}].planned_distance_meters",
            message="long-run share is below the approved macro range",
        )
    if share_percent > Decimal(str(hints.maximum_weekly_run_volume_percent)):
        _append(
            violations,
            code="long_run_share_above_maximum",
            path=f"workouts[{index}].planned_distance_meters",
            message="long-run share exceeds the approved macro range",
        )
    if (
        hints.target_distance_meters is not None
        and abs(long_run.planned_distance_meters - hints.target_distance_meters) > 1
    ):
        _append(
            violations,
            code="long_run_target_distance_mismatch",
            path=f"workouts[{index}].planned_distance_meters",
            message="long-run distance differs from the approved exact target",
        )


def _validate_fitzgerald_distribution(
    week: WeekPlan,
    run_workouts: list[WorkoutPrescription],
    violations: list[WeekPolicyViolation],
) -> None:
    distribution = week.workout_structure_hints.intensity_distribution
    if distribution is None:
        return
    total_seconds = sum(workout.planned_duration_seconds for workout in run_workouts)
    low_seconds = sum(workout.planned_low_intensity_duration_seconds for workout in run_workouts)
    if total_seconds == 0:
        _append(
            violations,
            code="fitzgerald_distribution_has_no_run_time",
            path="workouts",
            message="Fitzgerald intensity distribution requires planned run time",
        )
        return
    required_percent = Decimal(str(distribution.minimum_low_intensity_time_percent))
    if Decimal(low_seconds * 100) < Decimal(total_seconds) * required_percent:
        _append(
            violations,
            code="fitzgerald_low_intensity_below_minimum",
            path="workouts",
            message="planned low-intensity run time is below the macro minimum",
        )


def _validate_assessment_benchmark(
    plan: BaselineAssessmentPlan,
    week: WeekPlan,
    violations: list[WeekPolicyViolation],
) -> None:
    intent = plan.benchmark_intent
    contains_window = week.start_date <= intent.fallback_window_start <= week.end_date
    benchmarks = [
        (index, workout)
        for index, workout in enumerate(week.workouts)
        if workout.workout_type == WorkoutType.BENCHMARK.value
    ]
    if not contains_window:
        if benchmarks:
            _append(
                violations,
                code="benchmark_outside_assessment_week",
                path="workouts",
                message="benchmark is outside the approved fallback-window week",
            )
        return
    if len(benchmarks) != 1:
        _append(
            violations,
            code="benchmark_count_not_one",
            path="workouts",
            message=f"assessment week requires exactly one benchmark, found {len(benchmarks)}",
        )
        return
    index, benchmark = benchmarks[0]
    if not intent.fallback_window_start <= benchmark.date <= intent.fallback_window_end:
        _append(
            violations,
            code="benchmark_outside_fallback_window",
            path=f"workouts[{index}].date",
            message="benchmark date is outside the athlete-approved fallback window",
        )
    assert benchmark.structured_workout is not None
    timed_step = benchmark.structured_workout.timed_distance_steps()[0]
    expected_distance_meters = RaceDistance(intent.race_distance).distance_meters
    if abs(timed_step.distance_meters - expected_distance_meters) > 0.01:
        _append(
            violations,
            code="benchmark_distance_mismatch",
            path=f"workouts[{index}].structured_workout",
            message="timed-distance step differs from the approved benchmark distance",
        )
