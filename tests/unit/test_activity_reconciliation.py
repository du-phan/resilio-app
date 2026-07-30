"""Provider-native evidence must survive every reconciliation path."""

from datetime import datetime, timezone

from resilio.core.activity_sync.activity_merge import merge_external_activity
from resilio.core.activity_sync.reconciliation import reconcile_activity
from resilio.integrations.intervals_icu.activity_mapper import map_activity
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.schemas.reconciliation import ReconciliationAction
from tests.factories import make_activity


def _provider_activity(*, decoupling_percent: float | None) -> ActivityDTO:
    return ActivityDTO.model_validate(
        {
            "id": "i-native-reconciliation",
            "type": "Run",
            "name": "Aerobic run",
            "start_date": "2026-07-28T05:00:00Z",
            "start_date_local": "2026-07-28T07:00:00+02:00",
            "timezone": "Europe/Paris",
            "elapsed_time": 3600,
            "moving_time": 3500,
            "distance": 10_000,
            "decoupling": decoupling_percent,
        }
    )


def test_changed_link_refreshes_provider_native_analysis() -> None:
    imported_at_utc = datetime(2026, 7, 28, tzinfo=timezone.utc)
    existing = map_activity(
        _provider_activity(decoupling_percent=None),
        imported_at_utc=imported_at_utc,
    )
    refreshed = map_activity(
        _provider_activity(decoupling_percent=2.5),
        imported_at_utc=imported_at_utc,
    )

    decision = reconcile_activity(refreshed, [existing])

    assert decision.action == ReconciliationAction.UPDATE
    assert decision.activity is not None
    assert decision.activity.native_analysis is not None
    assert decision.activity.native_analysis.aerobic_decoupling is not None
    assert decision.activity.native_analysis.aerobic_decoupling.value_percent == 2.5


def test_historical_merge_recomputes_completeness_from_final_facts() -> None:
    existing = make_activity(
        id="historical",
        average_hr=145,
        max_hr=170,
        has_gps_data=True,
    )
    external = map_activity(
        _provider_activity(decoupling_percent=None),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    merged = merge_external_activity(existing, external)

    assert merged.heart_rate is not None
    assert merged.data_completeness.has_heart_rate_data
    assert merged.classification.has_gps_data
    assert merged.data_completeness.has_location_stream


def test_historical_merge_preserves_provider_location_evidence() -> None:
    existing = make_activity(
        id="historical-without-gps",
        has_gps_data=False,
    )
    external_dto = _provider_activity(decoupling_percent=None)
    external = map_activity(
        external_dto.model_copy(update={"stream_types": ["latlng"]}),
        imported_at_utc=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    merged = merge_external_activity(existing, external)

    assert merged.classification.has_gps_data
    assert merged.data_completeness.has_location_stream
