"""Canonical v2 and external mapping regression tests."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from resilio.integrations.intervals_icu.activity_mapper import (
    external_fingerprint,
    local_id_for_external,
    map_activity,
    map_sport,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.integrations.intervals_icu.errors import UnsupportedSportError
from resilio.schemas.activity import (
    ActivityOriginKind,
    ActivityStatus,
    CanonicalActivity,
    SportType,
)


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

    assert activity.perceived_effort is not None
    assert activity.perceived_effort.value == 7
    assert activity.perceived_effort.source == "athlete"
    assert external_fingerprint(_external(icu_rpe=7)) != external_fingerprint(
        _external(icu_rpe=6)
    )


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
        ("Crossfit", SportType.CROSSFIT),
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


def test_retired_transport_label_is_not_persisted_as_a_device() -> None:
    activity = map_activity(
        _external(device_name="Stra" + "vaGPX"),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.device.name is None


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
    assert activity.audit.external_fingerprint_sha256


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
    assert activity.cadence.average_revolutions_per_minute == 88
    assert activity.cadence.maximum_revolutions_per_minute == 112


def test_absent_completion_pairing_does_not_change_existing_fingerprint() -> None:
    without_pairing = _external()
    explicit_null = _external(paired_event_id=None)
    paired = _external(paired_event_id=42)

    assert external_fingerprint(without_pairing) == external_fingerprint(
        explicit_null
    )
    assert external_fingerprint(paired) != external_fingerprint(without_pairing)


def test_literal_schema_alias_round_trips_and_legacy_shape_is_refused() -> None:
    activity = map_activity(
        _external(),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    payload = activity.model_dump(mode="json", by_alias=True)

    assert "_schema" in payload
    assert "schema_info" not in payload
    assert payload["_schema"] == {"name": "resilio.activity", "version": 2}
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
    assert activity.start_time.utcoffset().total_seconds() == 7200


def test_naive_dst_fold_is_resolved_from_authoritative_utc_start() -> None:
    activity = map_activity(
        _external(
            start_date="2026-10-25T01:30:00Z",
            start_date_local="2026-10-25T02:30:00",
            timezone="Europe/Paris",
        ),
        imported_at_utc=datetime(2026, 10, 25, tzinfo=timezone.utc),
    )

    assert activity.start_time.fold == 1
    assert activity.start_time.utcoffset() == timedelta(hours=1)
    assert activity.start_time.astimezone(timezone.utc) == datetime(
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
