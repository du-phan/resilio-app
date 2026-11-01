"""Explicit removal keeps missed-run history and survives interrupted writes."""

from datetime import date, datetime, timezone

import pytest

from resilio.core.planning.service import load_planning_aggregate
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.core.workout_publication.week_service import RunWeekSynchronizationService
from tests.unit import test_planning_lifecycle as lifecycle
from tests.unit.test_workout_publication import FakeClient

REMOVAL_TIME = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
CONFIRMATION = "Athlete asked to remove the missed Tuesday run from the calendar."


@pytest.fixture
def setup(tmp_path, monkeypatch):
    repo = lifecycle.repo.__wrapped__(tmp_path, monkeypatch)
    lifecycle._apply_test_week(repo, tmp_path)
    client = FakeClient()
    client.list_activities = lambda oldest, newest: []
    from resilio.integrations.intervals_icu.dto import ActivityPairingSummaryDTO

    def pairings(oldest, newest):
        return [
            ActivityPairingSummaryDTO(
                **summary.model_dump(),
                paired_event_id=client.get_activity(summary.id).paired_event_id,
            )
            for summary in client.list_activities(oldest, newest)
        ]

    client.list_activity_pairings = pairings
    service = RunWeekSynchronizationService(repo, client)
    service.reconcile_week(1, as_of_date=date(2026, 7, 27))
    return repo, client, service


def _remove(repo, client, workout_id="w_easy_1", at=REMOVAL_TIME, confirmation=CONFIRMATION):
    from resilio.core.workout_publication.missed_calendar_removal import (
        remove_missed_calendar_workout,
    )

    return remove_missed_calendar_workout(
        repo,
        client,
        local_workout_id=workout_id,
        athlete_confirmation_reference=confirmation,
        requested_at_utc=at,
    )


def test_removal_keeps_history_and_sync_does_not_recreate_it(setup):
    repo, client, service = setup
    before = load_planning_aggregate(repo)
    original = load_manifest(repo).workouts["w_easy_1"]
    future_events = {key: value for key, value in client.events.items() if key != original.event_id}
    removal = _remove(repo, client)
    assert removal.completed_at_utc is not None
    assert original.event_id not in client.events
    assert "w_easy_1" not in load_manifest(repo).workouts
    assert load_planning_aggregate(repo) == before
    report = service.reconcile_week(1, as_of_date=date(2026, 7, 29))
    assert report.reconciliation_safe and not report.partial
    assert client.events == future_events
    assert next(item for item in report.items if item.local_workout_id == "w_easy_1").status == (
        "removed_missed"
    )
    assert _remove(repo, client) == removal


@pytest.mark.parametrize("failure", ["future", "no_confirmation", "unowned", "drift"])
def test_removal_rejects_unsafe_targets_without_mutating_provider(setup, failure):
    repo, client, _ = setup
    workout_id = "w_easy_2" if failure == "future" else "w_easy_1"
    if failure in {"unowned", "drift"}:
        publication = load_manifest(repo).workouts[workout_id]
        event = client.events[publication.event_id]
        changes = {"external_id": "athlete_owned"} if failure == "unowned" else {"name": "Changed"}
        client.events[event.id] = event.model_copy(update=changes)
    events_before = dict(client.events)
    with pytest.raises(PublicationSafetyError):
        _remove(
            repo,
            client,
            workout_id,
            confirmation="" if failure == "no_confirmation" else CONFIRMATION,
        )
    assert client.events == events_before


@pytest.mark.parametrize("crash_point", ["before_delete", "after_delete", "after_cleanup"])
def test_interrupted_removal_is_retriable_and_blocks_recreation(setup, monkeypatch, crash_point):
    repo, client, service = setup
    from resilio.core.workout_publication import missed_calendar_removal as removal_module

    original_delete = client.delete_event
    original_save = removal_module.save_removal_manifest
    failed = False

    def delete(event_id, *, athlete_id=None):
        nonlocal failed
        if not failed and crash_point == "before_delete":
            failed = True
            raise OSError("Simulated interruption before deletion")
        original_delete(event_id, athlete_id=athlete_id)
        if not failed and crash_point == "after_delete":
            failed = True
            raise OSError("Simulated interruption after deletion")

    def save(repository, manifest):
        nonlocal failed
        completed = any(record.completed_at_utc for record in manifest.removals.values())
        if not failed and crash_point == "after_cleanup" and completed:
            failed = True
            raise OSError("Simulated interruption after publication cleanup")
        return original_save(repository, manifest)

    monkeypatch.setattr(client, "delete_event", delete)
    monkeypatch.setattr(removal_module, "save_removal_manifest", save)
    with pytest.raises(OSError):
        _remove(repo, client)
    with pytest.raises(PublicationSafetyError, match="pending"):
        service.reconcile_week(1, as_of_date=date(2026, 7, 29))
    assert _remove(repo, client).completed_at_utc is not None
    report = service.reconcile_week(1, as_of_date=date(2026, 7, 29))
    assert report.reconciliation_safe


def test_removal_rejects_pending_publication_update(setup):
    repo, client, _ = setup
    from resilio.schemas.publication import PendingWorkoutPublication

    manifest = load_manifest(repo)
    published = manifest.workouts["w_easy_1"]
    fields = PendingWorkoutPublication.model_fields
    values = {key: value for key, value in published.model_dump().items() if key in fields}
    values["uid"] = published.requested_uid
    values["prepared_at_utc"] = REMOVAL_TIME
    manifest.pending["w_easy_1"] = PendingWorkoutPublication.model_validate(values)
    manifest.pending_provider_occurrence_placements[
        "w_easy_1"
    ] = manifest.workout_provider_occurrence_placements["w_easy_1"]
    save_manifest(repo, manifest)
    with pytest.raises(PublicationSafetyError, match="pending"):
        _remove(repo, client)


def test_removal_rechecks_local_fulfillment_after_interruption(setup, monkeypatch):
    repo, client, _ = setup
    original_delete = client.delete_event
    monkeypatch.setattr(
        client,
        "delete_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("Interrupted")),
    )
    with pytest.raises(OSError):
        _remove(repo, client)
    from tests.unit.test_partial_week_amendments import _record_early_fulfillment

    _record_early_fulfillment(repo, index=0)
    monkeypatch.setattr(client, "delete_event", original_delete)
    with pytest.raises(PublicationSafetyError, match="fulfilled"):
        _remove(repo, client)
    assert load_manifest(repo).workouts["w_easy_1"].event_id in client.events


def test_native_pair_prevents_removal_even_when_local_sync_has_no_fulfillment(setup):
    repo, client, _ = setup
    from resilio.integrations.intervals_icu.dto import ActivitySummaryDTO

    event_id = load_manifest(repo).workouts["w_easy_1"].event_id
    client.activities["paired_run"] = client.get_activity("paired_run").model_copy(
        update={"paired_event_id": event_id}
    )
    client.list_activities = lambda oldest, newest: [
        ActivitySummaryDTO(id="paired_run", type="Run", start_date_local="2026-07-28T07:00:00")
    ]
    with pytest.raises(PublicationSafetyError, match="provider-paired"):
        _remove(repo, client)
    assert event_id in client.events


def test_native_pair_added_at_final_delete_guard_blocks_removal(setup):
    repo, client, _ = setup
    from resilio.integrations.intervals_icu.dto import ActivitySummaryDTO

    event_id = load_manifest(repo).workouts["w_easy_1"].event_id
    summary = ActivitySummaryDTO(id="late_pair", type="Run", start_date_local="2026-07-28T07:00:00")
    reads = 0

    def activities(oldest, newest):
        nonlocal reads
        reads += 1
        if reads >= 3:
            client.activities[summary.id] = client.get_activity(summary.id).model_copy(
                update={"paired_event_id": event_id}
            )
        return [summary]

    client.list_activities = activities
    with pytest.raises(PublicationSafetyError, match="provider-paired"):
        _remove(repo, client)
    assert event_id in client.events


def test_native_pair_on_preceding_weekend_blocks_calendar_removal(setup):
    repo, client, _ = setup
    from resilio.integrations.intervals_icu.dto import ActivitySummaryDTO

    event_id = load_manifest(repo).workouts["w_easy_1"].event_id
    summary = ActivitySummaryDTO(
        id="sunday_pair", type="Run", start_date_local="2026-07-26T07:00:00"
    )
    client.activities[summary.id] = client.get_activity(summary.id).model_copy(
        update={"paired_event_id": event_id}
    )
    client.list_activities = (
        lambda oldest, newest: [summary] if oldest <= date(2026, 7, 26) <= newest else []
    )
    with pytest.raises(PublicationSafetyError, match="provider-paired"):
        _remove(repo, client)
    assert event_id in client.events


def test_native_pair_appearing_during_final_fresh_event_read_blocks_removal(setup, monkeypatch):
    repo, client, _ = setup
    from resilio.integrations.intervals_icu.dto import ActivitySummaryDTO

    event_id = load_manifest(repo).workouts["w_easy_1"].event_id
    summary = ActivitySummaryDTO(
        id="fresh_read_pair", type="Run", start_date_local="2026-07-28T07:00:00"
    )
    client.list_activities = lambda oldest, newest: [summary]
    original_get = client.get_event
    reads = 0

    def get(event_id, *, athlete_id=None):
        nonlocal reads
        reads += 1
        result = original_get(event_id, athlete_id=athlete_id)
        if reads == 3:
            client.activities[summary.id] = client.get_activity(summary.id).model_copy(
                update={"paired_event_id": event_id}
            )
        return result

    monkeypatch.setattr(client, "get_event", get)
    with pytest.raises(PublicationSafetyError, match="provider-paired"):
        _remove(repo, client)
    assert event_id in client.events


def test_pairing_read_splits_capped_ranges_without_declaring_them_complete(setup):
    repo, client, _ = setup
    from resilio.integrations.intervals_icu.dto import ActivityPairingSummaryDTO

    event_id = load_manifest(repo).workouts["w_easy_1"].event_id
    paired_date = date(2026, 7, 1)
    paired = ActivityPairingSummaryDTO(
        id="older", type="Run", start_date_local=paired_date.isoformat(), paired_event_id=event_id
    )
    unpaired = ActivityPairingSummaryDTO(id="unpaired", type="Run", start_date_local="2026-07-28")
    queries = []

    def pairings(oldest, newest):
        queries.append((oldest, newest))
        if oldest == date.min and newest == date(2026, 7, 29):
            return [unpaired] * 1000
        return [paired] if oldest <= paired_date <= newest else []

    client.list_activity_pairings = pairings
    with pytest.raises(PublicationSafetyError, match="provider-paired"):
        _remove(repo, client)
    assert len(queries) > 1 and event_id in client.events


def test_single_day_saturated_pairing_read_blocks_deletion(setup):
    repo, client, _ = setup
    from resilio.integrations.intervals_icu.dto import ActivityPairingSummaryDTO

    unpaired = ActivityPairingSummaryDTO(id="unpaired", type="Run", start_date_local="2026-07-28")
    client.list_activity_pairings = lambda oldest, newest: [unpaired] * 1000
    with pytest.raises(PublicationSafetyError, match="Single-day"):
        _remove(repo, client)
    assert load_manifest(repo).workouts["w_easy_1"].event_id in client.events


def test_drift_after_removal_intent_blocks_retry(setup, monkeypatch):
    repo, client, _ = setup
    original_delete = client.delete_event
    monkeypatch.setattr(
        client,
        "delete_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("Interrupted")),
    )
    with pytest.raises(OSError):
        _remove(repo, client)
    event_id = load_manifest(repo).workouts["w_easy_1"].event_id
    client.events[event_id] = client.events[event_id].model_copy(
        update={"name": "Athlete changed it"}
    )
    monkeypatch.setattr(client, "delete_event", original_delete)
    with pytest.raises(PublicationSafetyError):
        _remove(repo, client)
    assert event_id in client.events
