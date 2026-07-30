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
    DataCompleteness,
    DataQuality,
    HeartRateMeasurements,
    RecordingProvider,
    SportType,
    SurfaceType,
)


def make_activity(**values: Any) -> CanonicalActivity:
    """Build a valid v4 historical activity with concise test inputs."""
    activity_date = values.pop("date", date(2026, 1, 12))
    activity_id = str(values.pop("id", "test_activity"))
    activity_id = re.sub(r"[^A-Za-z0-9._:-]", "_", activity_id)
    sport = values.pop("sport", SportType.RUN)
    if isinstance(sport, SportType):
        sport = sport.value

    elapsed = int(values.pop("duration_seconds", 45 * 60))
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
        (RecordingProvider.MANUAL if source == "manual" else RecordingProvider.UPLOAD),
    )
    surface = values.pop("surface_type", SurfaceType.UNKNOWN)
    quality = values.pop("data_quality", DataQuality.MEDIUM)
    has_gps_data = bool(values.pop("has_gps_data", False))
    description = values.pop("description", None)
    private_note = values.pop("private_note", None)
    average_hr = values.pop("average_hr", None)
    maximum_hr = values.pop("max_hr", None)
    distance_meters = values.pop("distance_meters", None)

    elevation = values.pop("elevation_gain_meters", None)
    source_subtype = values.pop("source_sport_subtype", None)

    created = values.pop("created_at", datetime.now(timezone.utc))
    updated = values.pop("updated_at", created)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    data_completeness = values.pop(
        "data_completeness",
        DataCompleteness(
            has_location_stream=has_gps_data,
            has_heart_rate_data=(average_hr is not None or maximum_hr is not None),
            has_power_data=values.get("power") is not None,
            has_cadence_data=values.get("cadence") is not None,
            has_interval_data=bool(values.get("segments")),
            has_native_aerobic_load=values.get("aerobic_load") is not None,
            has_zone_time_data=bool(values.get("zone_time_distributions")),
            has_native_activity_analysis=(values.get("native_analysis") is not None),
        ),
    )
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
        data_completeness=data_completeness,
        device=ActivityDevice(),
        classification=ActivityClassification(
            surface=surface,
            data_quality=quality,
            has_gps_data=has_gps_data,
        ),
        origin=ActivityOrigin(
            kind=ActivityOriginKind.HISTORICAL_IMPORT,
            recording_provider=provider,
        ),
        audit=ActivityAudit(
            imported_at_utc=created,
            external_sync_at_utc=updated,
        ),
        **values,
    )
    return activity
