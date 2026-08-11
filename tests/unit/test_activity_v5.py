"""Canonical activity v5 and external mapping regression tests."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.integrations.intervals_icu.activity_mapper import (
    local_id_for_external,
    map_activity,
    map_sport,
    performance_evidence_fingerprint,
    provider_snapshot_fingerprint,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO, IntervalDTO
from resilio.integrations.intervals_icu.errors import UnsupportedSportError
from resilio.schemas.activity import (
    ActivityOriginKind,
    ActivitySegment,
    ActivityStatus,
    CanonicalActivity,
    IntervalKind,
    SegmentOriginKind,
    SportType,
)
from tests.factories import make_activity


def _external(**overrides) -> ActivityDTO:
    values = {
        "id": "i123",
        "type": "Run",
        "name": "Morning run",
        "start_date": "2026-07-28T05:00:00Z",
        "start_date_local": "2026-07-28T07:00:00+02:00",
        "timezone": "Europe/Paris",
        "elapsed_time": 2700,
        "moving_time": 2650,
        "distance": 8000.0,
        "total_elevation_gain": 80.0,
        "average_heartrate": 145.0,
        "max_heartrate": 170.0,
        "average_cadence": 86.0,
        "device_name": "Forerunner",
        "external_id": "upstream.fit",
        "source": "GARMIN_CONNECT",
        "created": "2026-07-28T05:50:00Z",
        "icu_sync_date": "2026-07-28T05:51:00Z",
        "icu_intervals": [
            {
                "id": 1,
                "start_time": 0,
                "elapsed_time": 600,
                "moving_time": 590,
                "distance": 1800,
                "label": "Warm up",
            }
        ],
    }
    values.update(overrides)
    return ActivityDTO.model_validate(values)


def test_activity_archive_creates_private_month_and_activity_file(
    tmp_path,
) -> None:
    archive_root = tmp_path / "data/activities"
    archive = ActivityArchive(archive_root)

    stored_path = archive.write(
        make_activity(
            id="private_activity",
            date=datetime(2026, 7, 20).date(),
        )
    )

    assert archive_root.stat().st_mode & 0o777 == 0o700
    assert stored_path.parent.stat().st_mode & 0o777 == 0o700
    assert stored_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("source_type", ["RockClimbing", "Bouldering"])
def test_climbing_variants_share_one_canonical_sport(source_type) -> None:
    activity = map_activity(
        _external(
            id=f"id-{source_type}",
            type=source_type,
            distance=None,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.sport == SportType.CLIMB
    assert activity.source_sport_type == source_type


def test_intervals_rpe_precedes_source_perceived_exertion() -> None:
    activity = map_activity(
        _external(icu_rpe=7, perceived_exertion=4),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.feedback.subjective_effort is not None
    assert activity.feedback.subjective_effort.rpe_1_to_10 == 7
    assert activity.feedback.subjective_effort.is_athlete_confirmed is False
    assert provider_snapshot_fingerprint(_external(icu_rpe=7)) != provider_snapshot_fingerprint(
        _external(icu_rpe=6)
    )


def test_decimal_source_rpe_is_preserved_without_rounding() -> None:
    activity = map_activity(
        _external(icu_rpe=None, perceived_exertion=6.5),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.feedback.subjective_effort is not None
    assert activity.feedback.subjective_effort.rpe_1_to_10 == 6.5


def test_current_mapper_records_v5_and_mapping_version_nine() -> None:
    activity = map_activity(
        _external(),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.schema_info.version == 5
    assert activity.audit.canonical_mapping_version == 9
    assert activity.audit.provider_snapshot_sha256
    assert activity.audit.performance_evidence_sha256


@pytest.mark.parametrize(
    ("source_type", "expected"),
    [
        ("Run", SportType.RUN),
        ("TrailRun", SportType.TRAIL_RUN),
        ("VirtualRun", SportType.TREADMILL_RUN),
        ("TrackRun", SportType.TRACK_RUN),
        ("Ride", SportType.CYCLE),
        ("VirtualRide", SportType.CYCLE),
        ("GravelRide", SportType.CYCLE),
        ("MountainBikeRide", SportType.CYCLE),
        ("TrackRide", SportType.CYCLE),
        ("Cyclocross", SportType.CYCLE),
        ("EBikeRide", SportType.CYCLE),
        ("EMountainBikeRide", SportType.CYCLE),
        ("Handcycle", SportType.CYCLE),
        ("Velomobile", SportType.CYCLE),
        ("RockClimbing", SportType.CLIMB),
        ("Bouldering", SportType.CLIMB),
        ("Yoga", SportType.YOGA),
        ("WeightTraining", SportType.STRENGTH),
        ("StrengthTraining", SportType.STRENGTH),
        ("Hike", SportType.HIKE),
        ("Walk", SportType.WALK),
        ("Swim", SportType.SWIM),
        ("OpenWaterSwim", SportType.SWIM),
        ("Rowing", SportType.ROW),
        ("VirtualRow", SportType.ROW),
        ("Canoeing", SportType.PADDLE),
        ("Kayaking", SportType.PADDLE),
        ("StandUpPaddling", SportType.PADDLE),
        ("AlpineSki", SportType.SKI),
        ("BackcountrySki", SportType.SKI),
        ("NordicSki", SportType.SKI),
        ("RollerSki", SportType.SKI),
        ("VirtualSki", SportType.SKI),
        ("IceSkate", SportType.SKATE),
        ("InlineSkate", SportType.SKATE),
        ("Kitesurf", SportType.WATER_SPORT),
        ("Sail", SportType.WATER_SPORT),
        ("Surfing", SportType.WATER_SPORT),
        ("WaterSport", SportType.WATER_SPORT),
        ("Windsurf", SportType.WATER_SPORT),
        ("Snowboard", SportType.SNOW_SPORT),
        ("Snowshoe", SportType.SNOW_SPORT),
        ("Soccer", SportType.TEAM_SPORT),
        ("Hockey", SportType.TEAM_SPORT),
        ("Rugby", SportType.TEAM_SPORT),
        ("Badminton", SportType.RACQUET_SPORT),
        ("Padel", SportType.RACQUET_SPORT),
        ("Pickleball", SportType.RACQUET_SPORT),
        ("Racquetball", SportType.RACQUET_SPORT),
        ("Squash", SportType.RACQUET_SPORT),
        ("TableTennis", SportType.RACQUET_SPORT),
        ("Tennis", SportType.RACQUET_SPORT),
        ("Elliptical", SportType.CARDIO_MACHINE),
        ("StairStepper", SportType.CARDIO_MACHINE),
        ("Wheelchair", SportType.WHEELCHAIR),
        ("Golf", SportType.GOLF),
        ("Crossfit", SportType.CROSSFIT),
        (
            "HighIntensityIntervalTraining",
            SportType.HIGH_INTENSITY_INTERVAL_TRAINING,
        ),
        ("Pilates", SportType.PILATES),
        ("Skateboard", SportType.SKATEBOARD),
        ("Transition", SportType.TRANSITION),
        ("Other", SportType.OTHER),
        ("Workout", SportType.OTHER),
    ],
)
def test_all_documented_sport_variants_are_explicit(
    source_type,
    expected,
) -> None:
    assert map_sport(source_type) == expected


@pytest.mark.parametrize(
    ("source_type", "expected_surface"),
    [
        ("Run", "unknown"),
        ("TrailRun", "trail"),
        ("TrackRun", "track"),
        ("VirtualRun", "treadmill"),
    ],
)
def test_surface_is_only_classified_from_explicit_source_type(
    source_type,
    expected_surface,
) -> None:
    activity = map_activity(
        _external(type=source_type),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.classification.surface == expected_surface


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("GARMIN_CONNECT", "garmin"),
        ("WAHOO", "wahoo"),
        ("MANUAL", "manual"),
        ("UPLOAD", "upload"),
        ("COROS", "other"),
        (None, "unknown"),
    ],
)
def test_recording_provenance_variants_are_provider_neutral(
    source,
    expected,
) -> None:
    activity = map_activity(
        _external(
            id=f"source-{source}",
            source=source,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.origin.recording_provider == expected
    assert activity.origin.source_recording_provider == source


def test_interval_order_is_permutation_invariant() -> None:
    first = _external(
        icu_intervals=[
            {
                "id": 20,
                "start_time": 600,
                "elapsed_time": 300,
            },
            {
                "id": 10,
                "start_time": 0,
                "elapsed_time": 300,
            },
        ]
    )
    reversed_source = first.model_copy(
        update={"icu_intervals": list(reversed(first.icu_intervals))}
    )
    imported_at = datetime(2026, 7, 28, tzinfo=timezone.utc)

    mapped_first = map_activity(first, imported_at_utc=imported_at)
    mapped_reversed = map_activity(
        reversed_source,
        imported_at_utc=imported_at,
    )

    assert provider_snapshot_fingerprint(first) == provider_snapshot_fingerprint(reversed_source)
    assert mapped_first.model_dump(mode="json") == mapped_reversed.model_dump(mode="json")


def test_physical_device_label_is_preserved_exactly() -> None:
    activity = map_activity(
        _external(device_name="Forerunner 965"),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.device.name == "Forerunner 965"


def test_manual_midnight_is_preserved_exactly() -> None:
    activity = map_activity(
        _external(
            source="MANUAL",
            start_date="2026-07-27T22:00:00Z",
            start_date_local="2026-07-28T00:00:00+02:00",
            device_name=None,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.occurrence.start_time_local.isoformat() == ("2026-07-28T00:00:00+02:00")
    assert activity.occurrence.start_time_utc.isoformat() == ("2026-07-27T22:00:00+00:00")


def test_explicit_manual_time_is_preserved() -> None:
    activity = map_activity(
        _external(
            source="MANUAL",
            start_date="2026-07-28T15:00:00Z",
            start_date_local="2026-07-28T17:00:00+02:00",
            device_name=None,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.occurrence.start_time_local.isoformat() == ("2026-07-28T17:00:00+02:00")
    assert activity.occurrence.start_time_utc.isoformat() == ("2026-07-28T15:00:00+00:00")


def test_manual_yoga_without_distance_maps_cleanly() -> None:
    activity = map_activity(
        _external(
            id="manual-yoga",
            type="Yoga",
            source="MANUAL",
            distance=None,
            total_elevation_gain=None,
            device_name=None,
            icu_intervals=[],
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.sport == SportType.YOGA
    assert activity.distance_meters is None
    assert activity.origin.recording_provider == "manual"


def test_unknown_sport_is_quarantinable_not_other() -> None:
    with pytest.raises(UnsupportedSportError):
        map_sport("NewFutureSport")


def test_mapping_preserves_canonical_sensor_and_segment_facts() -> None:
    activity = map_activity(
        _external(),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.local_activity_id == local_id_for_external("i123")
    assert activity.origin.recording_provider == "garmin"
    assert activity.distance_meters == 8000
    assert activity.heart_rate.average_beats_per_minute == 145
    assert activity.segments[0].origin_kind == "intervals_icu_interval"
    assert activity.audit.provider_snapshot_sha256
    assert activity.audit.performance_evidence_sha256


def test_power_and_cadence_measurements_preserve_explicit_units() -> None:
    activity = map_activity(
        _external(
            icu_average_watts=220,
            p_max=780,
            icu_weighted_avg_watts=235,
            average_cadence=88,
            max_cadence=112,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.power.average_watts == 220
    assert activity.power.maximum_watts == 780
    assert activity.power.weighted_average_watts == 235
    assert activity.cadence.average_cadence_per_minute == 88
    assert activity.cadence.maximum_cadence_per_minute == 112


def test_running_execution_summary_preserves_provider_units_and_model_context() -> None:
    activity = map_activity(
        _external(
            average_speed=2.25,
            max_speed=3.1,
            gap=2.2,
            average_stride=0.78,
            calories=246,
            carbs_ingested=18,
            carbs_used=52,
            compliance=125.0,
            average_temp=18.5,
            icu_weight=63.0,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    summary = activity.execution_summary
    assert summary.average_speed_meters_per_second == 2.25
    assert summary.maximum_speed_meters_per_second == 3.1
    assert summary.gradient_adjusted_speed_meters_per_second == 2.2
    assert summary.average_stride_meters == 0.78
    assert summary.calories_kilocalories == 246
    assert summary.carbohydrates_ingested_grams == 18
    assert summary.provider_estimated_carbohydrates_used_grams == 52
    assert summary.provider_compliance_percent == 125
    assert summary.average_temperature_celsius == 18.5
    assert summary.analysis_weight_kilograms == 63


def test_provider_interval_preserves_coaching_relevant_data_tab_fields() -> None:
    activity = map_activity(
        _external(
            icu_intervals=[
                {
                    "id": 7,
                    "type": "WORK",
                    "start_time": 120,
                    "end_time": 420,
                    "start_index": 100,
                    "end_index": 399,
                    "elapsed_time": 300,
                    "moving_time": 298,
                    "distance": 1_000,
                    "average_speed": 3.3,
                    "min_speed": 2.9,
                    "max_speed": 3.8,
                    "average_heartrate": 160,
                    "min_heartrate": 148,
                    "max_heartrate": 172,
                    "average_cadence": 91,
                    "min_cadence": 86,
                    "max_cadence": 96,
                    "average_gradient": 1.2,
                    "min_altitude": 42,
                    "max_altitude": 51,
                    "average_stride": 1.02,
                    "zone": 4,
                    "joules": 70_000,
                    "joules_above_ftp": 4_200,
                }
            ]
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    interval = activity.segments[0]
    assert interval.source_start_index == 100
    assert interval.source_end_index_exclusive == 399
    assert interval.end_offset_seconds == 420
    assert interval.minimum_speed_meters_per_second == 2.9
    assert interval.heart_rate.minimum_beats_per_minute == 148
    assert interval.cadence.minimum_cadence_per_minute == 86
    assert interval.average_gradient_percent == 1.2
    assert interval.minimum_altitude_meters == 42
    assert interval.maximum_altitude_meters == 51
    assert interval.average_stride_meters == 1.02
    assert interval.provider_zone_index == 4
    assert interval.work_joules == 70_000
    assert interval.work_above_ftp_joules == 4_200


def test_provider_zero_zero_interval_indices_are_treated_as_absent_stream_bounds() -> None:
    """Intervals uses 0/0 when an interval has duration but no sample range."""
    activity = map_activity(
        _external(
            icu_intervals=[
                {
                    "id": 1,
                    "start_time": 0,
                    "elapsed_time": 600,
                    "start_index": 0,
                    "end_index": 0,
                }
            ]
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert len(activity.segments) == 1
    assert activity.segments[0].source_start_index is None
    assert activity.segments[0].source_end_index_exclusive is None


def test_absent_completion_pairing_does_not_change_existing_fingerprint() -> None:
    without_pairing = _external()
    explicit_null = _external(paired_event_id=None)
    paired = _external(paired_event_id=42)

    assert provider_snapshot_fingerprint(without_pairing) == provider_snapshot_fingerprint(
        explicit_null
    )
    assert provider_snapshot_fingerprint(paired) != provider_snapshot_fingerprint(without_pairing)


def test_feedback_changes_do_not_invalidate_performance_evidence() -> None:
    baseline = _external(description="Easy", icu_rpe=3, feel=1)
    revised_feedback = _external(description="Harder than expected", icu_rpe=6, feel=5)

    assert provider_snapshot_fingerprint(baseline) != provider_snapshot_fingerprint(
        revised_feedback
    )
    assert performance_evidence_fingerprint(baseline) == performance_evidence_fingerprint(
        revised_feedback
    )


def test_performance_fact_changes_invalidate_performance_evidence() -> None:
    baseline = _external(distance=8_000, elapsed_time=2_700, moving_time=2_650)
    revised_distance = _external(distance=8_010, elapsed_time=2_700, moving_time=2_650)

    assert performance_evidence_fingerprint(baseline) != performance_evidence_fingerprint(
        revised_distance
    )


def test_provider_interval_changes_invalidate_performance_evidence() -> None:
    baseline_interval = IntervalDTO(
        id=1,
        start_time=0,
        elapsed_time=300,
        moving_time=300,
        distance=1_000,
    )
    revised_interval = baseline_interval.model_copy(update={"distance": 1_010})

    assert performance_evidence_fingerprint(
        _external(icu_intervals=[baseline_interval])
    ) != performance_evidence_fingerprint(_external(icu_intervals=[revised_interval]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "RECOVERY"),
        ("training_load", 19),
        ("intensity", 104),
        ("decoupling", 3.1),
        ("zone", 5),
        ("joules_above_ftp", 9_000),
    ],
)
def test_interval_analysis_overlays_do_not_invalidate_performance_evidence(
    field,
    value,
) -> None:
    baseline = IntervalDTO(
        id=1,
        type="WORK",
        start_time=0,
        elapsed_time=300,
        distance=1_000,
        joules_above_ftp=4_000,
    )
    revised = baseline.model_copy(update={field: value})

    assert performance_evidence_fingerprint(
        _external(icu_intervals=[baseline])
    ) == performance_evidence_fingerprint(_external(icu_intervals=[revised]))


def test_historical_performance_identity_excludes_segment_analysis_overlays() -> None:
    segment = ActivitySegment(
        index=1,
        origin_kind=SegmentOriginKind.HISTORICAL_SEGMENT,
        elapsed_seconds=300,
        distance_meters=1_000,
        interval_kind=IntervalKind.WORK,
        provider_zone_index=4,
        aerobic_load_points=12,
        work_above_ftp_joules=4_000,
    )
    baseline = make_activity(id="historical-performance", segments=[segment])
    revised_analysis = baseline.model_copy(
        update={
            "segments": [
                segment.model_copy(
                    update={
                        "interval_kind": IntervalKind.RECOVERY,
                        "provider_zone_index": 2,
                        "aerobic_load_points": 20,
                        "work_above_ftp_joules": 8_000,
                    }
                )
            ]
        }
    )
    revised_measurement = baseline.model_copy(
        update={"segments": [segment.model_copy(update={"distance_meters": 1_010})]}
    )

    assert activity_performance_evidence_sha256(baseline) == activity_performance_evidence_sha256(
        revised_analysis
    )
    assert activity_performance_evidence_sha256(baseline) != activity_performance_evidence_sha256(
        revised_measurement
    )


def test_literal_schema_alias_round_trips_and_legacy_shape_is_refused() -> None:
    activity = map_activity(
        _external(),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    payload = activity.model_dump(mode="json", by_alias=True)

    assert "_schema" in payload
    assert "schema_info" not in payload
    assert payload["_schema"] == {"name": "resilio.activity", "version": 5}
    assert CanonicalActivity.model_validate(payload) == activity

    with pytest.raises(ValidationError, match="legacy activity schema"):
        CanonicalActivity.model_validate(
            {
                **payload,
                "schema_metadata": {"schema_type": "activity"},
            }
        )


def test_linked_historical_activity_can_be_tombstoned() -> None:
    activity = map_activity(
        _external(),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    payload = activity.model_dump(mode="json", by_alias=True)
    payload["local_activity_id"] = "act_h_0123456789abcdef01234567"
    payload["origin"]["kind"] = ActivityOriginKind.HISTORICAL_IMPORT
    payload["status"] = ActivityStatus.EXTERNAL_DELETED

    tombstone = CanonicalActivity.model_validate(payload)

    assert tombstone.origin.kind == ActivityOriginKind.HISTORICAL_IMPORT
    assert tombstone.origin.intervals_icu_activity_id == "i123"
    assert tombstone.status == ActivityStatus.EXTERNAL_DELETED


def test_unlinked_historical_activity_cannot_be_tombstoned() -> None:
    activity = map_activity(
        _external(),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    payload = activity.model_dump(mode="json", by_alias=True)
    payload["local_activity_id"] = "act_h_0123456789abcdef01234567"
    payload["origin"]["kind"] = ActivityOriginKind.HISTORICAL_IMPORT
    payload["origin"]["intervals_icu_activity_id"] = None
    payload["status"] = ActivityStatus.EXTERNAL_DELETED

    with pytest.raises(ValidationError, match="externally linked"):
        CanonicalActivity.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("elapsed_time", 0),
        ("moving_time", -1),
        ("distance", float("nan")),
    ],
)
def test_external_impossible_measurements_fail_validation(field, value) -> None:
    with pytest.raises(ValidationError):
        _external(**{field: value})


def test_naive_local_wall_time_uses_athlete_timezone() -> None:
    activity = map_activity(
        _external(
            timezone=None,
            start_date_local="2026-07-28T07:00:00",
            has_heartrate=None,
        ),
        default_timezone="Europe/Paris",
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.occurrence.timezone == "Europe/Paris"
    assert activity.occurrence.start_time_local.utcoffset().total_seconds() == 7200


def test_naive_dst_fold_is_resolved_from_authoritative_utc_start() -> None:
    activity = map_activity(
        _external(
            start_date="2026-10-25T01:30:00Z",
            start_date_local="2026-10-25T02:30:00",
            timezone="Europe/Paris",
        ),
        imported_at_utc=datetime(2026, 10, 25, tzinfo=timezone.utc),
    )

    assert activity.occurrence.start_time_local.fold == 1
    assert activity.occurrence.start_time_local.utcoffset() == timedelta(hours=1)
    assert activity.occurrence.start_time_local.astimezone(timezone.utc) == datetime(
        2026,
        10,
        25,
        1,
        30,
        tzinfo=timezone.utc,
    )


def test_nonexistent_or_inconsistent_local_wall_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="inconsistent"):
        map_activity(
            _external(
                start_date="2026-03-29T01:30:00Z",
                start_date_local="2026-03-29T02:30:00",
                timezone="Europe/Paris",
            ),
            imported_at_utc=datetime(2026, 3, 29, tzinfo=timezone.utc),
        )
