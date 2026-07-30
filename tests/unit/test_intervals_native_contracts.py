"""Intervals-native activity, wellness, and settings contract tests."""

from datetime import date, datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from resilio.integrations.intervals_icu.activity_mapper import (
    external_fingerprint,
    map_activity,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.integrations.intervals_icu.training_state_mapper import (
    map_sport_settings,
    map_wellness,
)
from resilio.schemas.activity import ActivityZoneTime, ZoneTimeDistribution
from tests.unit.test_intervals_icu_client import _config


def _native_activity(**overrides: object) -> ActivityDTO:
    payload: dict[str, object] = {
        "id": "i-native-1",
        "type": "Run",
        "name": "Threshold intervals",
        "start_date": "2026-07-28T05:00:00Z",
        "start_date_local": "2026-07-28T07:00:00+02:00",
        "timezone": "Europe/Paris",
        "elapsed_time": 3600,
        "moving_time": 3540,
        "distance": 10_000.0,
        "stream_types": ["time", "latlng", "heartrate"],
        "icu_training_load": 82,
        "power_load": None,
        "hr_load": 82,
        "pace_load": 79,
        "hr_load_type": "HRSS",
        "pace_load_type": "RUN",
        "load_order": "POWER_HR_PACE",
        "tiz_order": "POWER_HR_PACE",
        "icu_intensity": 91.5,
        "icu_training_load_edited": False,
        "icu_rpe": 7,
        "session_rpe": 420,
        "icu_ftp": 300,
        "lthr": 171,
        "athlete_max_hr": 190,
        "threshold_pace": 4.12,
        "pace_units": "MINS_KM",
        "icu_hr_zones": [135, 151, 163, 171, 177, 183, 190],
        "hr_zone_names": [
            "Recovery",
            "Aerobic",
            "Tempo",
            "SubThreshold",
            "SuperThreshold",
            "Aerobic Capacity",
            "Anaerobic",
        ],
        "icu_hr_zone_times": [
            600,
            0,
            0,
            1800,
            0,
            0,
            0,
        ],
        "decoupling": 3.2,
        "icu_intervals": [
            {
                "id": 1,
                "type": "WORK",
                "start_time": 600,
                "elapsed_time": 480,
                "moving_time": 480,
                "distance": 1600,
                "label": "Threshold",
                "intensity": 99.0,
                "training_load": 13,
                "decoupling": 1.5,
            }
        ],
    }
    payload.update(overrides)
    return ActivityDTO.model_validate(payload)


def test_native_aerobic_load_and_execution_evidence_survive_mapping() -> None:
    activity = map_activity(
        _native_activity(),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.aerobic_load is not None
    assert activity.aerobic_load.aerobic_load_points == 82
    assert activity.aerobic_load.calculation_method == "heart_rate"
    assert activity.aerobic_load.heart_rate_load_points == 82
    assert activity.aerobic_load.pace_load_points == 79
    assert activity.aerobic_load.relative_intensity_percent == 91.5
    assert activity.subjective_effort is not None
    assert activity.subjective_effort.rpe_1_to_10 == 7
    assert activity.subjective_effort.session_rpe_load_au == 420
    assert activity.subjective_effort.session_rpe_duration_basis == "provider_defined"
    assert activity.subjective_effort.provenance == "intervals_activity_field"
    assert activity.subjective_effort.is_athlete_confirmed is False
    assert activity.analysis_thresholds is not None
    assert activity.analysis_thresholds.functional_threshold_power_watts == 300
    assert activity.analysis_thresholds.lactate_threshold_hr_bpm == 171
    assert activity.analysis_thresholds.maximum_hr_bpm == 190
    assert activity.analysis_thresholds.threshold_speed_meters_per_second == 4.12
    assert activity.analysis_thresholds.pace_display_unit == "MINS_KM"
    assert activity.classification.has_gps_data is True
    assert activity.data_completeness.has_location_stream is True
    assert activity.segments[0].interval_kind == "work"
    assert activity.segments[0].relative_intensity_percent == 99
    assert activity.segments[0].aerobic_load_points == 13
    assert activity.segments[0].decoupling is not None
    assert activity.segments[0].decoupling.value_percent == 1.5
    assert activity.segments[0].decoupling.coupling_basis == "provider_unknown"
    assert activity.native_analysis is not None
    assert activity.native_analysis.aerobic_decoupling is not None
    assert activity.native_analysis.aerobic_decoupling.value_percent == 3.2
    assert activity.native_analysis.polarization is None
    assert activity.native_analysis.trimp_load_points is None
    assert activity.zone_time_distributions[0].measurement_method == "heart_rate"
    assert activity.zone_time_distributions[0].zones[3].duration_seconds == 1800
    assert activity.zone_time_distributions[0].zones[3].zone_index == 4
    assert activity.zone_time_distributions[0].zones[3].name == "SubThreshold"
    assert activity.zone_time_distributions[0].zones[3].lower_bound == 163
    assert activity.zone_time_distributions[0].zones[3].upper_bound == 171
    assert activity.zone_time_distributions[0].is_primary_time_in_zones_method
    assert activity.zone_time_distributions[0].analysis_source_moving_duration_seconds == 3540


def test_native_hrr_and_analysis_applicability_survive_mapping() -> None:
    activity = map_activity(
        _native_activity(
            icu_hrr={
                "start_index": 100,
                "end_index": 160,
                "start_time": 3_500,
                "end_time": 3_560,
                "start_bpm": 174,
                "end_bpm": 141,
                "average_watts": 90,
                "hrr": 33,
            },
            icu_ignore_time=False,
            icu_ignore_power=True,
            icu_ignore_hr=False,
            ignore_velocity=True,
            ignore_pace=False,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.native_analysis is not None
    recovery = activity.native_analysis.heart_rate_recovery
    assert recovery is not None
    assert recovery.start_sample_index == 100
    assert recovery.end_offset_seconds == 3_560
    assert recovery.start_heart_rate_bpm == 174
    assert recovery.heart_rate_recovery_bpm == 33
    applicability = activity.native_analysis_applicability
    assert applicability is not None
    assert applicability.exclude_power is True
    assert applicability.exclude_velocity is True
    assert applicability.exclude_heart_rate is False


def test_null_grade_adjusted_pace_selection_remains_unspecified() -> None:
    external = _native_activity(
        use_gap_zone_times=None,
        gap_zone_times=[600, 1_800],
    )

    activity = map_activity(
        external,
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert external.use_gap_zone_times is None
    grade_adjusted = next(
        distribution
        for distribution in activity.zone_time_distributions
        if distribution.measurement_method == "grade_adjusted_pace"
    )
    assert not grade_adjusted.is_primary_time_in_zones_method


def test_primary_zone_method_is_first_available_configured_method() -> None:
    activity = map_activity(
        _native_activity(
            tiz_order="POWER_HR_PACE",
            icu_zone_times=[],
            icu_hr_zone_times=[600, 0, 0, 1800, 0, 0, 0],
            pace_zone_times=[500, 0, 0, 1900],
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    by_method = {
        distribution.measurement_method: distribution
        for distribution in activity.zone_time_distributions
    }
    assert by_method["heart_rate"].is_primary_time_in_zones_method
    assert not by_method["pace"].is_primary_time_in_zones_method


def test_power_zone_objects_preserve_provider_ids_and_exact_name_links() -> None:
    activity = map_activity(
        _native_activity(
            tiz_order="POWER_HR",
            icu_power_zones=[150, 220, 300],
            power_zone_names=["Recovery", "Endurance", "Threshold"],
            icu_zone_times=[
                {"id": "Threshold", "secs": 900},
                {"id": "provider-custom-zone", "secs": 0},
                {"id": "Recovery", "secs": 600},
            ],
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    power = activity.zone_time_distributions[0]
    assert power.measurement_method == "power"
    assert power.is_primary_time_in_zones_method
    assert power.covered_duration_seconds == 1_500
    assert [zone.provider_zone_id for zone in power.zones] == [
        "Recovery",
        "Threshold",
        "provider-custom-zone",
    ]
    assert power.zones[0].zone_index == 1
    assert power.zones[0].lower_bound is None
    assert power.zones[0].upper_bound == 150
    assert power.zones[1].zone_index == 3
    assert power.zones[1].lower_bound == 220
    assert power.zones[1].upper_bound == 300
    assert power.zones[2].zone_index is None
    assert power.zones[2].name is None


def test_power_zone_object_order_does_not_change_fingerprint_or_mapping() -> None:
    zone_times = [
        {"id": "Threshold", "secs": 900},
        {"id": "custom", "secs": 100},
        {"id": "Recovery", "secs": 600},
    ]
    first = _native_activity(
        icu_power_zones=[150, 220, 300],
        power_zone_names=["Recovery", "Endurance", "Threshold"],
        icu_zone_times=zone_times,
    )
    second = _native_activity(
        icu_power_zones=[150, 220, 300],
        power_zone_names=["Recovery", "Endurance", "Threshold"],
        icu_zone_times=list(reversed(zone_times)),
    )

    assert external_fingerprint(first) == external_fingerprint(second)
    first_distribution = map_activity(
        first,
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    ).zone_time_distributions[0]
    second_distribution = map_activity(
        second,
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    ).zone_time_distributions[0]
    assert first_distribution == second_distribution


def test_power_zone_objects_reject_duplicate_provider_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate provider zone IDs"):
        _native_activity(
            icu_zone_times=[
                {"id": "Endurance", "secs": 600},
                {"id": "Endurance", "secs": 900},
            ]
        )


@pytest.mark.parametrize(
    "zone_time",
    [
        {"secs": 600},
        {"id": "", "secs": 600},
        {"id": "Endurance", "secs": -1},
        {"id": "Endurance", "secs": 2_147_483_648},
    ],
)
def test_power_zone_objects_reject_malformed_buckets(
    zone_time: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _native_activity(icu_zone_times=[zone_time])


def test_gap_zone_times_are_primary_when_provider_selects_gap_pace() -> None:
    activity = map_activity(
        _native_activity(
            tiz_order="PACE_HR",
            use_gap_zone_times=True,
            icu_hr_zone_times=[600, 0, 0, 1800, 0, 0, 0],
            pace_zone_times=[1200, 1200],
            gap_zone_times=[1000, 1400],
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    by_method = {
        distribution.measurement_method: distribution
        for distribution in activity.zone_time_distributions
    }
    assert by_method["grade_adjusted_pace"].is_primary_time_in_zones_method
    assert not by_method["pace"].is_primary_time_in_zones_method
    assert not by_method["heart_rate"].is_primary_time_in_zones_method


def test_zone_coverage_preserves_provider_rounding_above_moving_time() -> None:
    activity = map_activity(
        _native_activity(
            moving_time=100,
            elapsed_time=110,
            icu_hr_zone_times=[101],
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    distribution = activity.zone_time_distributions[0]
    assert distribution.analysis_source_moving_duration_seconds == 100
    assert distribution.covered_duration_seconds == 101
    assert distribution.moving_time_coverage_percent == 101


def test_zone_distribution_rejects_contradictory_bucket_total() -> None:
    with pytest.raises(ValidationError, match="sum of zone buckets"):
        ZoneTimeDistribution(
            measurement_method="heart_rate",
            measurement_unit="beats_per_minute",
            zones=[
                ActivityZoneTime(zone_index=1, duration_seconds=50),
                ActivityZoneTime(zone_index=2, duration_seconds=40),
            ],
            covered_duration_seconds=100,
            analysis_source_moving_duration_seconds=100,
            moving_time_coverage_percent=100,
        )


def test_negative_native_polarization_index_is_preserved() -> None:
    activity = map_activity(
        _native_activity(polarization_index=-0.34),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.native_analysis is not None
    assert activity.native_analysis.polarization is not None
    assert activity.native_analysis.polarization.value == -0.34
    assert activity.native_analysis.polarization.evidence_status == "unlinked"
    assert activity.native_analysis.polarization.primary_zone_measurement_method is None


def test_polarization_without_exact_primary_zone_evidence_is_unlinked() -> None:
    activity = map_activity(
        _native_activity(
            polarization_index=0,
            tiz_order=None,
            icu_hr_zone_times=[],
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.native_analysis is not None
    assert activity.native_analysis.polarization is not None
    assert activity.native_analysis.polarization.value == 0
    assert activity.native_analysis.polarization.evidence_status == "unlinked"
    assert activity.native_analysis.polarization.primary_zone_measurement_method is None


def test_provider_maximum_speed_spike_is_preserved_as_source_evidence() -> None:
    activity = map_activity(
        _native_activity(
            icu_intervals=[
                {
                    "id": 1,
                    "type": "OTHER",
                    "start_time": 0,
                    "elapsed_time": 3600,
                    "moving_time": 3500,
                    "average_speed": 5.69,
                    "max_speed": 3953.2302,
                }
            ]
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.segments[0].maximum_speed_meters_per_second == 3953.2302


def test_finite_nonnegative_provider_outliers_remain_source_evidence() -> None:
    activity = map_activity(
        _native_activity(
            distance=10_000_001,
            total_elevation_gain=100_001,
            icu_average_watts=3001,
            icu_weighted_avg_watts=3002,
            p_max=5001,
            average_cadence=301,
            max_cadence=401,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.distance_meters == 10_000_001
    assert activity.elevation_gain_meters == 100_001
    assert activity.power is not None
    assert activity.power.average_watts == 3001
    assert activity.power.weighted_average_watts == 3002
    assert activity.power.maximum_watts == 5001
    assert activity.cadence is not None
    assert activity.cadence.average_revolutions_per_minute == 301
    assert activity.cadence.maximum_revolutions_per_minute == 401


def test_missing_interval_measurements_remain_missing() -> None:
    activity = map_activity(
        _native_activity(
            icu_intervals=[
                {
                    "id": 1,
                    "type": "OTHER",
                    "start_time": 0,
                    "elapsed_time": 600,
                }
            ]
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.segments[0].moving_seconds is None
    assert activity.segments[0].distance_meters is None


def test_missing_native_load_remains_missing() -> None:
    activity = map_activity(
        _native_activity(
            type="RockClimbing",
            distance=None,
            stream_types=[],
            icu_training_load=None,
            power_load=None,
            hr_load=None,
            pace_load=None,
            icu_intensity=None,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.aerobic_load is None
    assert activity.classification.has_gps_data is False


def test_edited_provider_load_is_marked_manual() -> None:
    activity = map_activity(
        _native_activity(
            icu_training_load=100,
            icu_training_load_edited=True,
            hr_load=82,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.aerobic_load is not None
    assert activity.aerobic_load.aerobic_load_points == 100
    assert activity.aerobic_load.calculation_method == "manual"


def test_component_disagreement_is_not_mislabeled() -> None:
    activity = map_activity(
        _native_activity(
            icu_training_load=90,
            hr_load=82,
            pace_load=79,
        ),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert activity.aerobic_load is not None
    assert activity.aerobic_load.calculation_method == "provider_unknown"


def test_provider_reanalysis_fields_change_external_fingerprint() -> None:
    baseline = _native_activity()

    assert external_fingerprint(baseline) != external_fingerprint(
        _native_activity(icu_training_load=83)
    )
    assert external_fingerprint(baseline) != external_fingerprint(
        _native_activity(icu_intensity=92.0)
    )
    assert external_fingerprint(baseline) != external_fingerprint(
        _native_activity(icu_hr_zone_times=[500, 0, 0, 1900, 0, 0, 0])
    )
    assert external_fingerprint(baseline) != external_fingerprint(
        _native_activity(use_gap_zone_times=True)
    )
    assert external_fingerprint(baseline) != external_fingerprint(_native_activity(max_cadence=190))


def test_wellness_endpoint_preserves_native_units_and_missing_values() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/athlete/0/wellness"
        assert request.url.params["oldest"] == "2026-07-27"
        assert request.url.params["newest"] == "2026-07-28"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "2026-07-28",
                    "ctl": 44.5,
                    "atl": 51.25,
                    "rampRate": 2.2,
                    "ctlLoad": 82,
                    "atlLoad": 82,
                    "restingHR": 48,
                    "hrv": 62.4,
                    "hrvSDNN": 71.8,
                    "sleepSecs": 27_000,
                    "readiness": 73,
                    "vo2max": 52.3,
                    "fatigue": 2,
                    "tempRestingHR": False,
                }
            ],
        )

    with IntervalsIcuClient(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as client:
        wellness = client.get_wellness(
            date(2026, 7, 27),
            date(2026, 7, 28),
        )

    day = map_wellness(wellness[0])
    assert day.fitness_load_points == 44.5
    assert day.fatigue_load_points == 51.25
    assert day.form_load_points == -6.75
    assert day.ramp_load_points_per_week == 2.2
    assert day.resting_hr_bpm == 48
    assert day.hrv_rmssd_ms == 62.4
    assert day.hrv_sdnn_ms == 71.8
    assert day.sleep_duration_seconds == 27_000
    assert day.provider_readiness_value == 73
    assert day.vo2_max_ml_per_kg_per_min == 52.3
    assert day.soreness is None


def test_sport_settings_snapshot_is_deterministic_and_complete() -> None:
    source = [
        {
            "id": 1,
            "types": ["Run", "TrailRun"],
            "lthr": 171,
            "max_hr": 190,
            "threshold_pace": 4.12,
            "pace_units": "MINS_KM",
            "hr_zones": [135, 151, 163, 171, 177, 183, 190],
            "hr_zone_names": [
                "Recovery",
                "Aerobic",
                "Tempo",
                "SubThreshold",
                "SuperThreshold",
                "Aerobic Capacity",
                "Anaerobic",
            ],
            "hr_load_type": "HRSS",
            "pace_load_type": "RUN",
            "load_order": "POWER_HR_PACE",
            "tiz_order": "POWER_HR_PACE",
            "workout_order": "POWER_PACE_HR",
            "updated": "2026-07-28T08:00:00Z",
        }
    ]
    snapshot = map_sport_settings(source)

    assert snapshot.settings[0].lactate_threshold_hr_bpm == 171
    assert snapshot.settings[0].threshold_speed_meters_per_second == 4.12
    assert snapshot.settings[0].pace_display_unit == "MINS_KM"
    assert snapshot.settings[0].heart_rate_zone_upper_bounds_bpm[-1] == 190
    assert snapshot.settings[0].load_priority == [
        "power",
        "heart_rate",
        "pace",
    ]
    assert len(snapshot.fingerprint_sha256) == 64
    assert (
        snapshot.fingerprint_sha256 == map_sport_settings(list(reversed(source))).fingerprint_sha256
    )
