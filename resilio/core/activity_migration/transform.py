"""Pure legacy-dictionary to canonical-v2 transformation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from resilio.integrations.intervals_icu.activity_mapper import historical_local_id
from resilio.schemas.activity import (
    ActivityAudit,
    ActivityClassification,
    ActivityDevice,
    ActivityDuration,
    ActivityNotes,
    ActivityOccurrence,
    ActivityOrigin,
    ActivityOriginKind,
    ActivitySegment,
    CanonicalActivity,
    DataQuality,
    HeartRateMeasurements,
    LoadCalculation,
    PerceivedEffort,
    PerceivedEffortSource,
    RecordingProvider,
    SegmentOriginKind,
    SportType,
    SurfaceType,
)


def _aware(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("legacy timestamp is missing an offset")
    return parsed


def _heart_rate(average: Any, maximum: Any) -> Optional[HeartRateMeasurements]:
    if average is None and maximum is None:
        return None
    return HeartRateMeasurements(
        average_beats_per_minute=average,
        maximum_beats_per_minute=maximum,
    )


def _surface(value: Any) -> SurfaceType:
    try:
        return SurfaceType(str(value or "unknown"))
    except ValueError:
        return SurfaceType.UNKNOWN


def _quality(value: Any) -> DataQuality:
    try:
        return DataQuality(str(value or "medium"))
    except ValueError:
        return DataQuality.MEDIUM


def _segment(raw: dict[str, Any], index: int) -> ActivitySegment:
    start_utc = _aware(raw.get("start_date"))
    start_local = _aware(raw.get("start_date_local"))
    elapsed = int(raw.get("elapsed_time_seconds") or 0)
    moving = int(raw.get("moving_time_seconds") or elapsed)
    # Three verified historical segments differ by one second because the
    # upstream source rounded moving and elapsed duration independently.
    moving = min(moving, elapsed)
    return ActivitySegment(
        index=int(raw.get("lap_index") or index),
        name=raw.get("name"),
        origin_kind=SegmentOriginKind.HISTORICAL_SEGMENT,
        elapsed_seconds=elapsed,
        moving_seconds=moving,
        distance_meters=float(raw.get("distance_meters") or 0.0),
        start_time_utc=start_utc.astimezone(timezone.utc) if start_utc else None,
        start_time_local=start_local,
        average_speed_meters_per_second=raw.get("average_speed_mps"),
        maximum_speed_meters_per_second=raw.get("max_speed_mps"),
        heart_rate=_heart_rate(raw.get("average_hr"), raw.get("max_hr")),
        elevation_gain_meters=raw.get("total_elevation_gain_meters"),
    )


def transform_activity(raw: dict[str, Any]) -> CanonicalActivity:
    """Transform one already-validated v1 dictionary without external I/O."""
    schema = raw.get("schema_metadata")
    if not isinstance(schema, dict) or schema.get("schema_type") != "activity":
        raise ValueError("source record is not a supported activity archive record")

    legacy_id = raw.get("id")
    if not isinstance(legacy_id, str) or not legacy_id:
        raise ValueError("source activity id is missing")
    local_id = historical_local_id(legacy_id)

    sport = SportType(str(raw["sport_type"]))
    local_date = raw["date"]
    start = _aware(raw.get("start_time"))
    duration_seconds = int(raw.get("duration_seconds") or 0)
    if duration_seconds <= 0:
        raise ValueError("source activity duration must be positive")

    imported_at = (
        _aware(raw.get("synced_at"))
        or _aware(raw.get("updated_at"))
        or _aware(raw.get("created_at"))
    )
    if imported_at is None:
        imported_at = datetime.combine(local_date, datetime.min.time(), tzinfo=timezone.utc)

    perceived_effort = None
    explicit_rpe = raw.get("perceived_exertion")
    calculated = raw.get("calculated") or {}
    if explicit_rpe is not None:
        perceived_effort = PerceivedEffort(
            value=int(explicit_rpe),
            source=PerceivedEffortSource.ATHLETE,
        )
    elif raw.get("suffer_score") is not None and calculated.get("estimated_rpe"):
        perceived_effort = PerceivedEffort(
            value=int(calculated["estimated_rpe"]),
            source=PerceivedEffortSource.HISTORICAL_RELATIVE_EFFORT,
        )

    calculated_load = None
    if calculated:
        calculated_load = LoadCalculation(
            activity_id=local_id,
            duration_seconds=duration_seconds,
            estimated_rpe=int(calculated["estimated_rpe"]),
            sport=str(sport.value),
            surface=calculated.get("surface_type"),
            base_effort_au=calculated["base_effort_au"],
            systemic_multiplier=calculated["systemic_multiplier"],
            lower_body_multiplier=calculated["lower_body_multiplier"],
            adjustments=calculated.get("multiplier_adjustments") or [],
            systemic_load_au=calculated["systemic_load_au"],
            lower_body_load_au=calculated["lower_body_load_au"],
            session_type=calculated["session_type"],
        )

    source_type = str(raw.get("sub_type") or raw.get("sport_type"))
    provider = (
        RecordingProvider.MANUAL
        if str(raw.get("source", "")).lower() == "manual"
        else RecordingProvider.UNKNOWN
    )

    return CanonicalActivity(
        local_activity_id=local_id,
        sport=sport,
        source_sport_type=source_type,
        source_sport_subtype=raw.get("sub_type"),
        name=str(raw.get("name") or source_type),
        occurrence=ActivityOccurrence(
            local_date=local_date,
            start_time_utc=start.astimezone(timezone.utc) if start else None,
            start_time_local=start,
            timezone=None,
        ),
        duration=ActivityDuration(
            elapsed_seconds=duration_seconds,
            moving_seconds=duration_seconds,
        ),
        distance_meters=(
            raw.get("distance_meters")
            if raw.get("distance_meters") is not None
            else (
                float(raw["distance_km"]) * 1000
                if raw.get("distance_km") is not None
                else None
            )
        ),
        elevation_gain_meters=raw.get("elevation_gain_m"),
        heart_rate=_heart_rate(raw.get("average_hr"), raw.get("max_hr")),
        notes=ActivityNotes(
            description=raw.get("description"),
            private_note=raw.get("private_note"),
        ),
        perceived_effort=perceived_effort,
        device=ActivityDevice(gear_external_id=raw.get("gear_id")),
        classification=ActivityClassification(
            surface=_surface(raw.get("surface_type")),
            data_quality=_quality(raw.get("data_quality")),
            has_gps_data=bool(raw.get("has_gps_data")),
        ),
        segments=[
            _segment(item, index)
            for index, item in enumerate(raw.get("laps") or [], start=1)
        ],
        origin=ActivityOrigin(
            kind=ActivityOriginKind.HISTORICAL_IMPORT,
            recording_provider=provider,
        ),
        audit=ActivityAudit(imported_at_utc=imported_at),
        calculated_load=calculated_load,
    )
