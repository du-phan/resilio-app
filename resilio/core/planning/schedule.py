"""Resolve athlete-local workout schedules to unambiguous UTC instants."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from resilio.schemas.plan import WorkoutPrescription


class WorkoutScheduleError(ValueError):
    """A prescribed local start cannot identify exactly one instant."""


def scheduled_start_utc(
    workout: WorkoutPrescription,
    *,
    training_timezone: str,
) -> datetime:
    """Return the unique UTC instant represented by one local workout start."""
    if workout.start_time_local is None:
        raise WorkoutScheduleError("workout has no local start time")
    try:
        zone = ZoneInfo(training_timezone)
    except ZoneInfoNotFoundError as exc:
        raise WorkoutScheduleError("training timezone is not recognized") from exc
    wall_time = datetime.combine(workout.date, workout.start_time_local)
    candidates = {
        aware.astimezone(timezone.utc)
        for fold in (0, 1)
        if (aware := wall_time.replace(tzinfo=zone, fold=fold))
        .astimezone(timezone.utc)
        .astimezone(zone)
        .replace(tzinfo=None)
        == wall_time
    }
    if not candidates:
        raise WorkoutScheduleError(
            "local workout start does not exist because of a daylight-saving transition"
        )
    if len(candidates) > 1:
        raise WorkoutScheduleError(
            "local workout start is ambiguous because of a daylight-saving transition"
        )
    return candidates.pop()
