"""Small multi-sport helpers for running-specific plan guardrails."""

from collections.abc import Iterable

from resilio.schemas.plan import WorkoutPrescription


def running_workouts(
    workouts: Iterable[WorkoutPrescription],
) -> list[WorkoutPrescription]:
    """Return only workouts contributing to prescribed running volume."""
    return [workout for workout in workouts if workout.sport == "run"]
