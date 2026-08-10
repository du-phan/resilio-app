"""Concise deterministic names for downstream workout lists."""

from __future__ import annotations

from resilio.schemas.planning.workouts import RunningWorkoutPrescription, WorkoutType
from resilio.schemas.structured_workout import (
    RampStep,
    RepeatStep,
    SteadyStep,
    StepDuration,
    StepDurationUnit,
    TimedDistanceStep,
    WorkoutStep,
)

MAX_PROVIDER_WORKOUT_NAME_CHARACTERS = 15


def provider_workout_name(workout: RunningWorkoutPrescription) -> str:
    """Describe reusable workout content without binding the name to its date."""
    workout_type_label = {
        WorkoutType.EASY: "Easy",
        WorkoutType.LONG_RUN: "Long",
        WorkoutType.TEMPO: "Tempo",
        WorkoutType.INTERVALS: "Interval",
        WorkoutType.HILLS: "Hills",
        WorkoutType.RACE_PACE: "RacePace",
        WorkoutType.FARTLEK: "Fartlek",
        WorkoutType.STRIDES: "Strides",
        WorkoutType.RACE: "Race",
        WorkoutType.BENCHMARK: "Test",
    }[workout.workout_type]
    if workout.workout_type == WorkoutType.BENCHMARK:
        content_label = _benchmark_content_label(workout)
        return _bounded_name(f"{content_label}{workout_type_label}")
    repeat_label = _primary_repeat_label(workout)
    content_label = repeat_label or _distance_label(workout.planned_distance_meters)
    return _bounded_name(f"{workout_type_label}{content_label}")


def provider_workout_names(
    workouts: list[RunningWorkoutPrescription],
) -> dict[str, str]:
    """Reuse names for equal structures and disambiguate only true variants."""
    grouped: dict[str, list[RunningWorkoutPrescription]] = {}
    for workout in workouts:
        grouped.setdefault(provider_workout_name(workout), []).append(workout)
    names: dict[str, str] = {}
    for base_name, matches in grouped.items():
        variants: dict[str, list[RunningWorkoutPrescription]] = {}
        for workout in matches:
            variants.setdefault(_structure_signature(workout), []).append(workout)
        if len(variants) == 1:
            for workout in matches:
                names[workout.id] = base_name
            continue
        for index, (_, variant_workouts) in enumerate(sorted(variants.items()), start=1):
            suffix = f"-{index}"
            variant_name = (
                f"{base_name[: MAX_PROVIDER_WORKOUT_NAME_CHARACTERS - len(suffix)]}" f"{suffix}"
            )
            for workout in variant_workouts:
                names[workout.id] = variant_name
    return names


def _benchmark_content_label(workout: RunningWorkoutPrescription) -> str:
    structure = workout.structured_workout
    if structure is None:
        return _distance_label(workout.planned_distance_meters)
    timed_steps = structure.timed_distance_steps()
    if len(timed_steps) != 1:
        return _distance_label(workout.planned_distance_meters)
    return _distance_label(timed_steps[0].distance_meters)


def _primary_repeat_label(workout: RunningWorkoutPrescription) -> str:
    structure = workout.structured_workout
    if structure is None:
        return ""
    candidates: list[tuple[int, str]] = []
    for repeat in _repeat_steps(structure.steps):
        work_steps = [
            step
            for step in repeat.steps
            if isinstance(step, TimedDistanceStep)
            or (
                isinstance(step, (SteadyStep, RampStep))
                and str(step.intensity) in {"active", "interval"}
            )
        ]
        if len(work_steps) == 1:
            duration_label = _step_duration_label(work_steps[0])
            if duration_label:
                work_duration_seconds = _nominal_step_duration_seconds(work_steps[0])
                candidates.append(
                    (
                        repeat.repetitions * work_duration_seconds,
                        f"{repeat.repetitions}x{duration_label}",
                    )
                )
    if not candidates:
        return ""
    return max(candidates, key=lambda candidate: candidate[0])[1]


def _repeat_steps(steps: list[WorkoutStep]) -> list[RepeatStep]:
    repeats: list[RepeatStep] = []
    for step in steps:
        if isinstance(step, RepeatStep):
            repeats.append(step)
            repeats.extend(_repeat_steps(step.steps))
    return repeats


def _step_duration_label(step: WorkoutStep) -> str:
    if isinstance(step, TimedDistanceStep):
        return _distance_label(step.distance_meters)
    if not isinstance(step, (SteadyStep, RampStep)):
        return ""
    return _duration_label(step.duration)


def _nominal_step_duration_seconds(step: WorkoutStep) -> int:
    if isinstance(step, TimedDistanceStep):
        return step.nominal_seconds
    assert isinstance(step, (SteadyStep, RampStep))
    if step.duration.unit == StepDurationUnit.SECONDS:
        assert step.duration.value is not None
        return step.duration.value
    assert step.duration.nominal_seconds is not None
    return step.duration.nominal_seconds


def _duration_label(duration: StepDuration) -> str:
    if duration.unit == StepDurationUnit.UNTIL_LAP_PRESS:
        return "Lap"
    assert duration.value is not None
    if duration.unit == StepDurationUnit.METERS:
        return _distance_label(float(duration.value))
    if duration.value % 60 == 0:
        return f"{duration.value // 60}m"
    return f"{duration.value}s"


def _distance_label(distance_meters: float | None) -> str:
    if distance_meters is None:
        return ""
    if distance_meters >= 1_000:
        return f"{_compact_number(distance_meters / 1_000)}K"
    return f"{_compact_number(distance_meters)}m"


def _compact_number(value: float) -> str:
    return f"{value:.4g}"


def _structure_signature(workout: RunningWorkoutPrescription) -> str:
    structure = workout.structured_workout
    if structure is not None:
        return structure.model_dump_json(exclude_none=False)
    return (
        f"duration={workout.planned_duration_seconds};"
        f"distance={workout.planned_distance_meters}"
    )


def _bounded_name(name: str) -> str:
    return name[:MAX_PROVIDER_WORKOUT_NAME_CHARACTERS].rstrip()
