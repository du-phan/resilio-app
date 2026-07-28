"""Small provider-neutral factories shared by domain tests."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from typing import Any

from resilio.schemas.activity import (
    ActivityAudit,
    ActivityClassification,
    ActivityDevice,
    ActivityDuration,
    ActivityNotes,
    ActivityOccurrence,
    ActivityOrigin,
    ActivityOriginKind,
    CanonicalActivity,
    DataQuality,
    HeartRateMeasurements,
    RecordingProvider,
    SportType,
    SurfaceType,
)


def make_activity(**values: Any) -> CanonicalActivity:
    """Build a valid v2 historical activity with concise test inputs."""
    activity_date = values.pop("date", date(2026, 1, 12))
    activity_id = str(values.pop("id", values.pop("local_activity_id", "test_activity")))
    activity_id = re.sub(r"[^A-Za-z0-9._:-]", "_", activity_id)
    sport = values.pop("sport_type", values.pop("sport", SportType.RUN))
    if isinstance(sport, SportType):
        sport = sport.value

    elapsed = int(
        values.pop(
            "duration_seconds",
            int(values.pop("duration_minutes", 45)) * 60,
        )
    )
    values.pop("duration_minutes", None)
    moving = int(values.pop("moving_seconds", max(elapsed, 0)))

    start = values.pop("start_time", None)
    if start is None:
        start = datetime.combine(activity_date, time(hour=7), tzinfo=timezone.utc)
    elif start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if start.date() != activity_date:
        start = datetime.combine(activity_date, start.timetz())

    source = values.pop("source", "historical_import")
    provider = values.pop(
        "recording_provider",
        (
            RecordingProvider.MANUAL
            if source == "manual"
            else RecordingProvider.UPLOAD
        ),
    )
    surface = values.pop("surface_type", SurfaceType.UNKNOWN)
    quality = values.pop("data_quality", DataQuality.MEDIUM)
    description = values.pop("description", None)
    private_note = values.pop("private_note", None)
    average_hr = values.pop("average_hr", None)
    maximum_hr = values.pop("max_hr", None)
    distance_meters = values.pop("distance_meters", None)
    distance_km = values.pop("distance_km", None)
    if distance_meters is None and distance_km is not None:
        distance_meters = float(distance_km) * 1000

    elevation = values.pop(
        "elevation_gain_meters",
        values.pop("elevation_gain_m", None),
    )
    workout_type = values.pop("workout_type", None)
    source_subtype = values.pop("source_sport_subtype", None)
    if workout_type == 1:
        source_subtype = "race"

    calculated = values.pop("calculated", values.pop("calculated_load", None))
    created = values.pop("created_at", datetime.now(timezone.utc))
    updated = values.pop("updated_at", created)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    # Legacy test-only convenience inputs that are now derived or unavailable.
    for ignored in (
        "distance_km",
        "has_hr_data",
        "surface_type_confidence",
        "trainer",
        "manual",
    ):
        values.pop(ignored, None)

    activity = CanonicalActivity(
        local_activity_id=activity_id,
        sport=sport,
        source_sport_type=str(sport),
        source_sport_subtype=source_subtype,
        name=values.pop("name", "Test activity"),
        occurrence=ActivityOccurrence(
            local_date=activity_date,
            start_time_utc=start.astimezone(timezone.utc),
            start_time_local=start,
            timezone="UTC",
        ),
        duration=ActivityDuration(
            elapsed_seconds=elapsed,
            moving_seconds=moving,
        ),
        distance_meters=distance_meters,
        elevation_gain_meters=elevation,
        heart_rate=(
            HeartRateMeasurements(
                average_beats_per_minute=average_hr,
                maximum_beats_per_minute=maximum_hr,
            )
            if average_hr is not None or maximum_hr is not None
            else None
        ),
        notes=ActivityNotes(
            description=description,
            private_note=private_note,
        ),
        device=ActivityDevice(),
        classification=ActivityClassification(
            surface=surface,
            data_quality=quality,
            has_gps_data=bool(values.pop("has_gps_data", False)),
        ),
        origin=ActivityOrigin(
            kind=ActivityOriginKind.HISTORICAL_IMPORT,
            recording_provider=provider,
        ),
        audit=ActivityAudit(
            imported_at_utc=created,
            external_sync_at_utc=updated,
        ),
        calculated_load=calculated,
        **values,
    )
    return activity


def move_activity(
    activity: CanonicalActivity,
    *,
    local_activity_id: str,
    local_date: date,
    systemic_load_au: float | None = None,
) -> CanonicalActivity:
    """Clone an activity onto another date while keeping v2 invariants."""
    start = activity.start_time or datetime.combine(
        activity.date,
        time(hour=7),
        tzinfo=timezone.utc,
    )
    moved_start = datetime.combine(local_date, start.timetz())
    calculated = activity.calculated_load
    if calculated is not None:
        load_updates: dict[str, Any] = {"activity_id": local_activity_id}
        if systemic_load_au is not None:
            load_updates["systemic_load_au"] = systemic_load_au
            load_updates["lower_body_load_au"] = systemic_load_au
        calculated = calculated.model_copy(update=load_updates)
    return activity.model_copy(
        update={
            "local_activity_id": local_activity_id,
            "occurrence": activity.occurrence.model_copy(
                update={
                    "local_date": local_date,
                    "start_time_local": moved_start,
                    "start_time_utc": moved_start.astimezone(timezone.utc),
                }
            ),
            "calculated_load": calculated,
        }
    )
