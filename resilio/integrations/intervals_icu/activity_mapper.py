"""Pure external-activity to canonical-domain mapping."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from resilio.integrations.intervals_icu.dto import ActivityDTO, IntervalDTO
from resilio.integrations.intervals_icu.errors import UnsupportedSportError
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
    CadenceMeasurements,
    CanonicalActivity,
    DataQuality,
    HeartRateMeasurements,
    PerceivedEffort,
    PerceivedEffortSource,
    PowerMeasurements,
    RecordingProvider,
    SegmentOriginKind,
    SportType,
    SurfaceType,
)

RUN_MAPPING = {
    "Run": SportType.RUN,
    "TrailRun": SportType.TRAIL_RUN,
    "VirtualRun": SportType.TREADMILL_RUN,
    "TrackRun": SportType.TRACK_RUN,
}
RIDE_TYPES = {
    "Ride",
    "VirtualRide",
    "GravelRide",
    "MountainBikeRide",
    "TrackRide",
    "Cyclocross",
    "EBikeRide",
    "EMountainBikeRide",
    "Handcycle",
    "Velomobile",
}
DIRECT_MAPPING = {
    "RockClimbing": SportType.CLIMB,
    "Bouldering": SportType.CLIMB,
    "Yoga": SportType.YOGA,
    "WeightTraining": SportType.STRENGTH,
    "StrengthTraining": SportType.STRENGTH,
    "Hike": SportType.HIKE,
    "Walk": SportType.WALK,
    "Swim": SportType.SWIM,
    "OpenWaterSwim": SportType.SWIM,
    "Crossfit": SportType.CROSSFIT,
    "Other": SportType.OTHER,
    "Workout": SportType.OTHER,
}


def map_sport(source_type: str) -> SportType:
    """Map a known external type; never silently collapse unknown values."""
    if source_type in RUN_MAPPING:
        return RUN_MAPPING[source_type]
    if source_type in RIDE_TYPES:
        return SportType.CYCLE
    if source_type in DIRECT_MAPPING:
        return DIRECT_MAPPING[source_type]
    raise UnsupportedSportError(
        f"Unsupported activity type {source_type!r}",
        operation="map_activity_sport",
    )


def local_id_for_external(external_id: str) -> str:
    digest = hashlib.sha256(f"intervals-icu\0{external_id}".encode()).hexdigest()[:24]
    return f"act_i_{digest}"


def historical_local_id(legacy_id: str) -> str:
    digest = hashlib.sha256(f"historical-import-v2\0{legacy_id}".encode()).hexdigest()[:24]
    return f"act_h_{digest}"


def _recording_provider(source: Optional[str]) -> RecordingProvider:
    normalized = (source or "").upper()
    if normalized == "GARMIN_CONNECT":
        return RecordingProvider.GARMIN
    if normalized == "WAHOO":
        return RecordingProvider.WAHOO
    if normalized == "MANUAL":
        return RecordingProvider.MANUAL
    if normalized == "UPLOAD":
        return RecordingProvider.UPLOAD
    if normalized:
        return RecordingProvider.OTHER
    return RecordingProvider.UNKNOWN


def _device_name(name: Optional[str]) -> Optional[str]:
    """Keep physical device labels, not retired transport/source labels."""
    retired_provider = ("stra" + "va").casefold()
    if name and retired_provider in name.casefold():
        return None
    return name


def _heart_rate(average: Optional[float], maximum: Optional[float]):
    if average is None and maximum is None:
        return None
    return HeartRateMeasurements(
        average_beats_per_minute=average,
        maximum_beats_per_minute=maximum,
    )


def _power(
    average: Optional[float],
    maximum: Optional[float],
    weighted: Optional[float],
):
    if average is None and maximum is None and weighted is None:
        return None
    return PowerMeasurements(
        average_watts=average,
        maximum_watts=maximum,
        weighted_average_watts=weighted,
    )


def _cadence(average: Optional[float], maximum: Optional[float]):
    if average is None and maximum is None:
        return None
    return CadenceMeasurements(
        average_revolutions_per_minute=average,
        maximum_revolutions_per_minute=maximum,
    )


def _surface(sport: SportType) -> SurfaceType:
    if sport == SportType.TRAIL_RUN:
        return SurfaceType.TRAIL
    if sport == SportType.TRACK_RUN:
        return SurfaceType.TRACK
    if sport == SportType.TREADMILL_RUN:
        return SurfaceType.TREADMILL
    if sport == SportType.RUN:
        return SurfaceType.ROAD
    return SurfaceType.UNKNOWN


def _map_segment(
    interval: IntervalDTO,
    activity: ActivityDTO,
    index: int,
    local_start: datetime,
) -> ActivitySegment:
    moving = interval.moving_time if interval.moving_time is not None else interval.elapsed_time
    segment_start_utc = activity.start_date + timedelta(
        seconds=interval.start_time
    )
    return ActivitySegment(
        index=index,
        name=interval.label,
        origin_kind=SegmentOriginKind.INTERVALS_ICU_INTERVAL,
        elapsed_seconds=interval.elapsed_time,
        moving_seconds=moving,
        distance_meters=interval.distance or 0.0,
        start_time_utc=segment_start_utc,
        start_time_local=segment_start_utc.astimezone(local_start.tzinfo),
        average_speed_meters_per_second=interval.average_speed,
        maximum_speed_meters_per_second=interval.max_speed,
        heart_rate=_heart_rate(interval.average_heartrate, interval.max_heartrate),
        elevation_gain_meters=interval.total_elevation_gain,
        power=_power(
            interval.average_watts,
            interval.max_watts,
            interval.weighted_average_watts,
        ),
        cadence=_cadence(interval.average_cadence, interval.max_cadence),
    )


def _resolve_local_start(
    activity: ActivityDTO,
    timezone_name: Optional[str],
) -> datetime:
    """Bind wall time to the authoritative UTC instant, including DST fold."""
    supplied = activity.start_date_local
    utc_start = activity.start_date.astimezone(timezone.utc)
    if timezone_name:
        resolved = utc_start.astimezone(ZoneInfo(timezone_name))
        if resolved.replace(tzinfo=None) != supplied.replace(tzinfo=None):
            raise ValueError(
                "start_date_local is inconsistent with start_date and timezone"
            )
        if (
            supplied.tzinfo is not None
            and supplied.utcoffset() is not None
            and supplied.utcoffset() != resolved.utcoffset()
        ):
            raise ValueError(
                "start_date_local offset is inconsistent with the timezone"
            )
        return resolved
    if supplied.tzinfo is None or supplied.utcoffset() is None:
        raise ValueError(
            "naive start_date_local requires an activity or athlete timezone"
        )
    if supplied.astimezone(timezone.utc) != utc_start:
        raise ValueError("start_date_local is inconsistent with start_date")
    return supplied


def external_fingerprint(
    activity: ActivityDTO,
    default_timezone: Optional[str] = None,
) -> str:
    """Hash only canonical external facts, independent of response ordering."""
    payload = {
        "id": activity.id,
        "type": activity.type,
        "sub_type": activity.sub_type,
        "name": activity.name,
        "description": activity.description,
        "start_date": activity.start_date.isoformat(),
        "start_date_local": activity.start_date_local.isoformat(),
        "timezone": activity.timezone,
        "default_timezone": default_timezone if not activity.timezone else None,
        "elapsed_time": activity.elapsed_time,
        "moving_time": activity.moving_time,
        "distance": activity.distance,
        "total_elevation_gain": activity.total_elevation_gain,
        "average_heartrate": activity.average_heartrate,
        "max_heartrate": activity.max_heartrate,
        "average_cadence": activity.average_cadence,
        "icu_average_watts": activity.icu_average_watts,
        "p_max": activity.p_max,
        "icu_weighted_avg_watts": activity.icu_weighted_avg_watts,
        "perceived_exertion": activity.perceived_exertion,
        "icu_rpe": activity.icu_rpe,
        "device_name": activity.device_name,
        "external_id": activity.external_id,
        "file_type": activity.file_type,
        "source": activity.source,
        "created": activity.created.isoformat() if activity.created else None,
        "icu_sync_date": (
            activity.icu_sync_date.isoformat() if activity.icu_sync_date else None
        ),
        "intervals": [
            interval.model_dump(mode="json", exclude_none=False)
            for interval in sorted(activity.icu_intervals, key=lambda item: item.id)
        ],
    }
    if activity.paired_event_id is not None:
        payload["paired_event_id"] = activity.paired_event_id
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def map_activity(
    activity: ActivityDTO,
    *,
    imported_at_utc: Optional[datetime] = None,
    default_timezone: Optional[str] = None,
) -> CanonicalActivity:
    """Convert a validated DTO into the final canonical domain record."""
    imported_at = imported_at_utc or datetime.now(timezone.utc)
    if imported_at.tzinfo is None:
        raise ValueError("imported_at_utc must be timezone-aware")

    sport = map_sport(activity.type)
    timezone_name = activity.timezone or default_timezone
    local_start = _resolve_local_start(activity, timezone_name)
    external_rpe = (
        activity.icu_rpe
        if activity.icu_rpe is not None
        else activity.perceived_exertion
    )
    rpe_value = (
        round(external_rpe)
        if external_rpe is not None and external_rpe >= 1
        else None
    )
    has_sensor_data = any(
        value is not None
        for value in (
            activity.average_heartrate,
            activity.max_heartrate,
            activity.average_cadence,
            activity.icu_average_watts,
        )
    )
    has_gps = bool(activity.distance and activity.distance > 0)

    return CanonicalActivity(
        local_activity_id=local_id_for_external(activity.id),
        sport=sport,
        source_sport_type=activity.type,
        source_sport_subtype=activity.sub_type,
        name=activity.name,
        occurrence=ActivityOccurrence(
            local_date=local_start.date(),
            start_time_utc=activity.start_date.astimezone(timezone.utc),
            start_time_local=local_start,
            timezone=timezone_name,
        ),
        duration=ActivityDuration(
            elapsed_seconds=activity.elapsed_time,
            moving_seconds=activity.moving_time,
        ),
        distance_meters=activity.distance,
        elevation_gain_meters=activity.total_elevation_gain,
        heart_rate=_heart_rate(activity.average_heartrate, activity.max_heartrate),
        power=_power(
            activity.icu_average_watts,
            activity.p_max,
            activity.icu_weighted_avg_watts,
        ),
        cadence=_cadence(activity.average_cadence, activity.max_cadence),
        notes=ActivityNotes(description=activity.description),
        perceived_effort=(
            PerceivedEffort(value=rpe_value, source=PerceivedEffortSource.ATHLETE)
            if rpe_value is not None
            else None
        ),
        device=ActivityDevice(name=_device_name(activity.device_name)),
        classification=ActivityClassification(
            surface=_surface(sport),
            data_quality=DataQuality.HIGH if has_gps and has_sensor_data else DataQuality.MEDIUM,
            has_gps_data=has_gps,
        ),
        segments=[
            _map_segment(interval, activity, index, local_start)
            for index, interval in enumerate(activity.icu_intervals, start=1)
        ],
        origin=ActivityOrigin(
            kind=ActivityOriginKind.INTERVALS_ICU,
            recording_provider=_recording_provider(activity.source),
            intervals_icu_activity_id=activity.id,
            upstream_external_id=activity.external_id,
        ),
        audit=ActivityAudit(
            imported_at_utc=imported_at,
            external_created_at_utc=activity.created,
            external_sync_at_utc=activity.icu_sync_date,
            external_fingerprint_sha256=external_fingerprint(
                activity,
                default_timezone,
            ),
        ),
    )
