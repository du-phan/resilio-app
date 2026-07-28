"""Strict overlap and ambiguity tests."""

from datetime import datetime, timedelta, timezone

from resilio.core.activity_sync.reconciliation import reconcile_activity
from resilio.core.load import compute_load
from resilio.integrations.intervals_icu.activity_mapper import map_activity
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.schemas.activity import (
    ActivityAudit,
    ActivityOccurrence,
    ActivityOrigin,
    ActivityOriginKind,
    RecordingProvider,
    SportType,
)
from resilio.schemas.reconciliation import ReconciliationAction
from tests.factories import make_activity


def _external(
    *,
    activity_id: str = "intervals-1",
    start: datetime | None = None,
    duration: int = 3600,
    distance: float | None = 10000,
    name: str = "Morning run",
):
    started = start or datetime(2026, 7, 28, 7, tzinfo=timezone.utc)
    return map_activity(
        ActivityDTO(
            id=activity_id,
            type="Run",
            name=name,
            start_date=started,
            start_date_local=started,
            elapsed_time=duration,
            moving_time=duration,
            distance=distance,
            source="WAHOO",
        ),
        imported_at_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc),
    )


def _historical(**overrides):
    values = {
        "id": "historical-local",
        "sport_type": SportType.RUN,
        "date": datetime(2026, 7, 28, tzinfo=timezone.utc).date(),
        "start_time": datetime(2026, 7, 28, 7, tzinfo=timezone.utc),
        "duration_seconds": 3600,
        "moving_seconds": 3600,
        "distance_meters": 10000,
        "name": "Morning run",
        "recording_provider": RecordingProvider.UNKNOWN,
    }
    values.update(overrides)
    return make_activity(**values)


def test_existing_external_id_updates_late_edit_without_new_record() -> None:
    external = _external()
    linked = _historical().model_copy(
        update={
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.HISTORICAL_IMPORT,
                recording_provider=RecordingProvider.WAHOO,
                intervals_icu_activity_id="intervals-1",
            ),
            "audit": ActivityAudit(
                imported_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
                external_fingerprint_sha256="0" * 64,
            ),
        }
    )

    decision = reconcile_activity(external, [linked])

    assert decision.action == ReconciliationAction.UPDATE
    assert decision.local_activity_id == "historical-local"
    assert decision.rule == "linked_fingerprint_changed"


def test_unique_strong_match_preserves_historical_local_id() -> None:
    decision = reconcile_activity(_external(), [_historical()])

    assert decision.action == ReconciliationAction.LINK
    assert decision.local_activity_id == "historical-local"
    assert decision.activity.origin.intervals_icu_activity_id == "intervals-1"


def test_unique_upstream_id_precedes_composite_matching() -> None:
    external = _external(
        start=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
        duration=5000,
        distance=14000,
    )
    external = external.model_copy(
        update={
            "origin": external.origin.model_copy(
                update={"upstream_external_id": "upstream.fit"}
            )
        }
    )
    historical = _historical().model_copy(
        update={
            "origin": _historical().origin.model_copy(
                update={"upstream_external_id": "upstream.fit"}
            )
        }
    )

    decision = reconcile_activity(external, [historical])

    assert decision.action == ReconciliationAction.LINK
    assert decision.rule == "unique_upstream_external_id"


def test_unique_original_file_hash_precedes_composite_matching() -> None:
    digest = "a" * 64
    external = _external(
        start=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
        duration=5000,
        distance=14000,
    )
    external = external.model_copy(
        update={
            "origin": external.origin.model_copy(
                update={"original_file_sha256": digest}
            )
        }
    )
    historical = _historical().model_copy(
        update={
            "origin": _historical().origin.model_copy(
                update={"original_file_sha256": digest}
            )
        }
    )

    decision = reconcile_activity(external, [historical])

    assert decision.action == ReconciliationAction.LINK
    assert decision.rule == "unique_original_file_sha256"


def test_duplicate_direct_external_references_are_ambiguous() -> None:
    linked = []
    for local_id in ("first", "second"):
        candidate = _historical(id=local_id)
        linked.append(
            candidate.model_copy(
                update={
                    "origin": candidate.origin.model_copy(
                        update={
                            "intervals_icu_activity_id": "intervals-1"
                        }
                    )
                }
            )
        )

    decision = reconcile_activity(_external(), linked)

    assert decision.action == ReconciliationAction.AMBIGUOUS
    assert decision.rule == "duplicate_external_reference"


def test_multiple_same_day_strong_matches_are_ambiguous() -> None:
    first = _historical(id="first")
    second = _historical(id="second", start_time=first.start_time + timedelta(seconds=30))

    decision = reconcile_activity(_external(), [first, second])

    assert decision.action == ReconciliationAction.AMBIGUOUS
    assert decision.candidate_local_ids == ["first", "second"]


def test_review_window_never_auto_merges() -> None:
    candidate = _historical(
        start_time=datetime(2026, 7, 28, 7, 10, tzinfo=timezone.utc),
        duration_seconds=3800,
        moving_seconds=3800,
        distance_meters=10150,
    )

    decision = reconcile_activity(_external(), [candidate])

    assert decision.action == ReconciliationAction.AMBIGUOUS
    assert decision.rule == "review_window_candidates"


def test_incompatible_recording_sources_never_strong_merge() -> None:
    candidate = _historical(
        recording_provider=RecordingProvider.GARMIN,
    )

    decision = reconcile_activity(_external(), [candidate])

    assert decision.action == ReconciliationAction.AMBIGUOUS
    assert decision.rule == "review_window_candidates"


def test_unique_distance_free_manual_activity_matches_exact_title_duration() -> None:
    external = _external(
        duration=3600,
        distance=None,
        name="Evening bouldering",
    )
    external = external.model_copy(update={"sport": SportType.CLIMB.value})
    manual = _historical(
        sport_type=SportType.CLIMB,
        distance_meters=None,
        name="  evening   BOULDERING ",
        recording_provider=RecordingProvider.MANUAL,
    )

    decision = reconcile_activity(external, [manual])

    assert decision.action == ReconciliationAction.LINK
    assert decision.rule == "unique_strong_composite"


def test_historical_match_uses_legacy_wall_time_and_moving_duration() -> None:
    external = _external(
        start=datetime(2026, 7, 28, 5, tzinfo=timezone.utc),
        duration=3900,
    )
    external = external.model_copy(
        update={
            "occurrence": ActivityOccurrence(
                local_date=external.date,
                start_time_utc=external.occurrence.start_time_utc,
                start_time_local=datetime(
                    2026,
                    7,
                    28,
                    7,
                    tzinfo=timezone(timedelta(hours=2)),
                ),
                timezone="Europe/Paris",
            ),
            "duration": external.duration.model_copy(
                update={"moving_seconds": 3600},
            ),
        }
    )
    historical = _historical().model_copy(
        update={
            "occurrence": ActivityOccurrence(
                local_date=external.date,
                start_time_utc=datetime(
                    2026,
                    7,
                    28,
                    7,
                    tzinfo=timezone.utc,
                ),
                start_time_local=datetime(
                    2026,
                    7,
                    28,
                    7,
                    tzinfo=timezone.utc,
                ),
                timezone=None,
            ),
        }
    )
    historical = historical.model_copy(
        update={"calculated_load": compute_load(historical, 5)}
    )

    decision = reconcile_activity(external, [historical])

    assert decision.action == ReconciliationAction.LINK
    assert decision.rule == "unique_strong_composite"
    assert decision.evidence["utc_start_delta_seconds"] == 7200
    assert decision.evidence["historical_wall_start_delta_seconds"] == 0
    assert decision.evidence["historical_duration_delta_seconds"] == 0
    assert decision.activity.occurrence == historical.occurrence
    assert decision.activity.duration == historical.duration
    assert decision.activity.distance_meters == historical.distance_meters
    assert decision.activity.calculated_load == historical.calculated_load


def test_linked_current_external_record_applies_late_edit() -> None:
    original = _external()
    changed = _external(
        start=datetime(2026, 7, 28, 7, 1, tzinfo=timezone.utc),
        duration=3660,
        distance=10100,
        name="Edited upstream title",
    )
    original = original.model_copy(
        update={
            "audit": ActivityAudit(
                imported_at_utc=original.audit.imported_at_utc,
                external_fingerprint_sha256="0" * 64,
            ),
        }
    )

    decision = reconcile_activity(changed, [original])

    assert decision.action == ReconciliationAction.UPDATE
    assert decision.rule == "linked_fingerprint_changed"
    assert decision.activity.name == "Edited upstream title"
    assert decision.activity.occurrence == changed.occurrence
    assert decision.activity.duration == changed.duration
    assert decision.activity.distance_meters == 10100
    assert decision.activity.calculated_load is None


def test_wall_time_alternate_never_applies_to_current_external_records() -> None:
    external = _external(
        start=datetime(2026, 7, 28, 5, tzinfo=timezone.utc),
        duration=3900,
    )
    external = external.model_copy(
        update={
            "occurrence": ActivityOccurrence(
                local_date=external.date,
                start_time_utc=external.occurrence.start_time_utc,
                start_time_local=datetime(
                    2026,
                    7,
                    28,
                    7,
                    tzinfo=timezone(timedelta(hours=2)),
                ),
                timezone="Europe/Paris",
            ),
            "duration": external.duration.model_copy(
                update={"moving_seconds": 3600},
            ),
        }
    )
    current = _historical().model_copy(
        update={
            "occurrence": ActivityOccurrence(
                local_date=external.date,
                start_time_utc=datetime(
                    2026,
                    7,
                    28,
                    7,
                    tzinfo=timezone.utc,
                ),
                start_time_local=datetime(
                    2026,
                    7,
                    28,
                    7,
                    tzinfo=timezone.utc,
                ),
                timezone="UTC",
            ),
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.INTERVALS_ICU,
                recording_provider=RecordingProvider.WAHOO,
                intervals_icu_activity_id="another-current-record",
            ),
        }
    )

    decision = reconcile_activity(external, [current])

    assert decision.action == ReconciliationAction.CREATE


def test_historical_record_without_start_is_held_for_review() -> None:
    historical = _historical(
        duration_seconds=3700,
        moving_seconds=3700,
        distance_meters=10150,
    )
    historical = historical.model_copy(
        update={
            "occurrence": ActivityOccurrence(
                local_date=historical.date,
                start_time_utc=None,
                start_time_local=None,
                timezone=None,
            ),
        }
    )

    decision = reconcile_activity(_external(), [historical])

    assert decision.action == ReconciliationAction.AMBIGUOUS
    assert decision.rule == "review_window_candidates"
    evidence = decision.evidence["historical-local"]
    assert evidence["historical_start_unavailable"] == 1.0


def test_non_candidate_creates_new_record() -> None:
    decision = reconcile_activity(
        _external(),
        [_historical(sport_type=SportType.CLIMB)],
    )

    assert decision.action == ReconciliationAction.CREATE
    assert decision.activity.local_activity_id.startswith("act_i_")
