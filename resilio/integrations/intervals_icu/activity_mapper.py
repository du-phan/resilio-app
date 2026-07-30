"""Pure external-activity to canonical-domain mapping."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from resilio.integrations.intervals_icu.activity_fingerprint import (
    CANONICAL_MAPPING_VERSION,
    external_fingerprint,
    ordered_intervals,
)
from resilio.integrations.intervals_icu.dto import (
    ActivityDTO,
    IntervalDTO,
)
from resilio.integrations.intervals_icu.errors import UnsupportedSportError
from resilio.integrations.intervals_icu.native_analysis_mapper import (
    map_native_activity_analysis,
    map_native_analysis_applicability,
)
from resilio.integrations.intervals_icu.zone_mapper import (
    map_analysis_thresholds,
    map_zone_time_distributions,
)
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
    AerobicLoad,
    AerobicLoadCalculationMethod,
    CadenceMeasurements,
    CanonicalActivity,
    DataCompleteness,
    DataQuality,
    HeartRateMeasurements,
    IntervalKind,
    NativeDecouplingObservation,
    PowerMeasurements,
    RecordingProvider,
    SegmentOriginKind,
    SportType,
    SubjectiveEffortProvenance,
    SubjectiveSessionEffort,
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
    "Rowing": SportType.ROW,
    "VirtualRow": SportType.ROW,
    "Canoeing": SportType.PADDLE,
    "Kayaking": SportType.PADDLE,
    "StandUpPaddling": SportType.PADDLE,
    "AlpineSki": SportType.SKI,
    "BackcountrySki": SportType.SKI,
    "NordicSki": SportType.SKI,
    "RollerSki": SportType.SKI,
    "VirtualSki": SportType.SKI,
    "IceSkate": SportType.SKATE,
    "InlineSkate": SportType.SKATE,
    "Kitesurf": SportType.WATER_SPORT,
    "Sail": SportType.WATER_SPORT,
    "Surfing": SportType.WATER_SPORT,
    "WaterSport": SportType.WATER_SPORT,
    "Windsurf": SportType.WATER_SPORT,
    "Snowboard": SportType.SNOW_SPORT,
    "Snowshoe": SportType.SNOW_SPORT,
    "Soccer": SportType.TEAM_SPORT,
    "Hockey": SportType.TEAM_SPORT,
    "Rugby": SportType.TEAM_SPORT,
    "Badminton": SportType.RACQUET_SPORT,
    "Padel": SportType.RACQUET_SPORT,
    "Pickleball": SportType.RACQUET_SPORT,
    "Racquetball": SportType.RACQUET_SPORT,
    "Squash": SportType.RACQUET_SPORT,
    "TableTennis": SportType.RACQUET_SPORT,
    "Tennis": SportType.RACQUET_SPORT,
    "Elliptical": SportType.CARDIO_MACHINE,
    "StairStepper": SportType.CARDIO_MACHINE,
    "Wheelchair": SportType.WHEELCHAIR,
    "Golf": SportType.GOLF,
    "Crossfit": SportType.CROSSFIT,
    "HighIntensityIntervalTraining": (
        SportType.HIGH_INTENSITY_INTERVAL_TRAINING
    ),
    "Pilates": SportType.PILATES,
    "Skateboard": SportType.SKATEBOARD,
    "Transition": SportType.TRANSITION,
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


def _heart_rate(
    average: Optional[float],
    maximum: Optional[float],
) -> Optional[HeartRateMeasurements]:
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
) -> Optional[PowerMeasurements]:
    if average is None and maximum is None and weighted is None:
        return None
    return PowerMeasurements(
        average_watts=average,
        maximum_watts=maximum,
        weighted_average_watts=weighted,
    )


def _cadence(
    average: Optional[float],
    maximum: Optional[float],
) -> Optional[CadenceMeasurements]:
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
    return SurfaceType.UNKNOWN


def _map_segment(
    interval: IntervalDTO,
    activity: ActivityDTO,
    index: int,
    local_start: datetime,
) -> ActivitySegment:
    segment_start_utc = local_start.astimezone(timezone.utc) + timedelta(
        seconds=interval.start_time
    )
    return ActivitySegment(
        index=index,
        name=interval.label,
        origin_kind=SegmentOriginKind.INTERVALS_ICU_INTERVAL,
        elapsed_seconds=interval.elapsed_time,
        moving_seconds=interval.moving_time,
        distance_meters=interval.distance,
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
        interval_kind=_interval_kind(interval.type),
        relative_intensity_percent=interval.intensity,
        aerobic_load_points=interval.training_load,
        decoupling=(
            NativeDecouplingObservation(
                value_percent=interval.decoupling,
                aggregation_scope="provider_interval",
            )
            if interval.decoupling is not None
            else None
        ),
    )


def _interval_kind(value: Optional[str]) -> IntervalKind:
    normalized = (value or "").upper()
    if normalized == "WORK":
        return IntervalKind.WORK
    if normalized == "RECOVERY":
        return IntervalKind.RECOVERY
    return IntervalKind.OTHER


_LOAD_COMPONENTS = {
    "POWER": ("power_load", AerobicLoadCalculationMethod.POWER),
    "HR": ("hr_load", AerobicLoadCalculationMethod.HEART_RATE),
    "PACE": ("pace_load", AerobicLoadCalculationMethod.PACE),
}


def _aerobic_load_method(activity: ActivityDTO) -> AerobicLoadCalculationMethod:
    if activity.icu_training_load_edited:
        return AerobicLoadCalculationMethod.MANUAL
    for token in (activity.load_order or "").split("_"):
        component = _LOAD_COMPONENTS.get(token.upper())
        if component is None:
            continue
        field_name, method = component
        component_value = getattr(activity, field_name)
        if component_value is None:
            continue
        if component_value == activity.icu_training_load:
            return method
        return AerobicLoadCalculationMethod.PROVIDER_UNKNOWN
    return AerobicLoadCalculationMethod.PROVIDER_UNKNOWN


def _aerobic_load(activity: ActivityDTO) -> Optional[AerobicLoad]:
    if activity.icu_training_load is None:
        return None
    return AerobicLoad(
        aerobic_load_points=activity.icu_training_load,
        calculation_method=_aerobic_load_method(activity),
        power_load_points=activity.power_load,
        heart_rate_load_points=activity.hr_load,
        pace_load_points=activity.pace_load,
        relative_intensity_percent=activity.icu_intensity,
        heart_rate_load_type=activity.hr_load_type,
        pace_load_type=activity.pace_load_type,
        provider_edited=activity.icu_training_load_edited,
    )


def _subjective_effort(
    activity: ActivityDTO,
) -> Optional[SubjectiveSessionEffort]:
    external_rpe = activity.icu_rpe if activity.icu_rpe is not None else activity.perceived_exertion
    if external_rpe is None or external_rpe < 1:
        return None
    return SubjectiveSessionEffort(
        rpe_1_to_10=external_rpe,
        session_rpe_load_au=activity.session_rpe,
        session_rpe_duration_basis=(
            "provider_defined" if activity.session_rpe is not None else None
        ),
        provenance=SubjectiveEffortProvenance.INTERVALS_ACTIVITY_FIELD,
        is_athlete_confirmed=False,
    )


def _has_location_stream(activity: ActivityDTO) -> bool:
    normalized = {item.casefold() for item in activity.stream_types}
    return bool(
        normalized.intersection(
            {"latlng", "latitude", "longitude", "lat", "lng"},
        )
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
            raise ValueError("start_date_local is inconsistent with start_date and timezone")
        if (
            supplied.tzinfo is not None
            and supplied.utcoffset() is not None
            and supplied.utcoffset() != resolved.utcoffset()
        ):
            raise ValueError("start_date_local offset is inconsistent with the timezone")
        return resolved
    if supplied.tzinfo is None or supplied.utcoffset() is None:
        raise ValueError("naive start_date_local requires an activity or athlete timezone")
    if supplied.astimezone(timezone.utc) != utc_start:
        raise ValueError("start_date_local is inconsistent with start_date")
    return supplied


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
    has_sensor_data = any(
        value is not None
        for value in (
            activity.average_heartrate,
            activity.max_heartrate,
            activity.average_cadence,
            activity.icu_average_watts,
        )
    )
    has_location_stream = _has_location_stream(activity)
    aerobic_load = _aerobic_load(activity)
    zone_distributions = map_zone_time_distributions(activity)
    native_analysis = map_native_activity_analysis(activity)
    return CanonicalActivity(
        local_activity_id=local_id_for_external(activity.id),
        sport=sport,
        source_sport_type=activity.type,
        source_sport_subtype=activity.sub_type,
        name=activity.name,
        occurrence=ActivityOccurrence(
            local_date=local_start.date(),
            start_time_utc=local_start.astimezone(timezone.utc),
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
        aerobic_load=aerobic_load,
        native_analysis=native_analysis,
        native_analysis_applicability=(map_native_analysis_applicability(activity)),
        subjective_effort=_subjective_effort(activity),
        analysis_thresholds=map_analysis_thresholds(activity),
        zone_time_distributions=zone_distributions,
        data_completeness=DataCompleteness(
            has_location_stream=has_location_stream,
            has_heart_rate_data=activity.average_heartrate is not None
            or activity.max_heartrate is not None,
            has_power_data=activity.icu_average_watts is not None
            or activity.icu_weighted_avg_watts is not None,
            has_cadence_data=activity.average_cadence is not None,
            has_interval_data=bool(activity.icu_intervals),
            has_native_aerobic_load=aerobic_load is not None,
            has_zone_time_data=bool(zone_distributions),
            has_native_activity_analysis=native_analysis is not None,
        ),
        device=ActivityDevice(name=activity.device_name),
        classification=ActivityClassification(
            surface=_surface(sport),
            data_quality=(
                DataQuality.HIGH if has_location_stream and has_sensor_data else DataQuality.MEDIUM
            ),
            has_gps_data=has_location_stream,
        ),
        segments=[
            _map_segment(interval, activity, index, local_start)
            for index, interval in enumerate(
                ordered_intervals(activity),
                start=1,
            )
        ],
        origin=ActivityOrigin(
            kind=ActivityOriginKind.INTERVALS_ICU,
            recording_provider=_recording_provider(activity.source),
            source_recording_provider=activity.source,
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
            canonical_mapping_version=CANONICAL_MAPPING_VERSION,
        ),
    )
