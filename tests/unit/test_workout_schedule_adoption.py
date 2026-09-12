"""Focused workout schedule adoption tests."""

from dataclasses import replace
from datetime import date, datetime, time, timezone

import pytest

from resilio.core.planning.adherence_evidence import (
    AppliedWorkoutAuthority,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import (
    save_fulfillment_manifest,
)
from resilio.core.workout_publication import pending_recovery as pending_recovery_module
from resilio.core.workout_publication import preparation as preparation_module
from resilio.core.workout_publication import week_verification as week_verification_module
from resilio.core.workout_publication.execution_placement import (
    assert_fulfillment_pair_matches_remote_placement,
    resolve_provider_occurrence_placements,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.naming import provider_workout_names
from resilio.core.workout_publication.policy import uid_for
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthority,
)
from resilio.core.workout_publication.semantics import provider_workout_semantics
from resilio.core.workout_publication.service import PublicationSafetyError
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.integrations.intervals_icu.errors import IntervalsTransportError
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentManifest,
)
from tests.unit.run_publication_workflow_support import (
    HarnessRunWeekSynchronizationService,
    _authoritative,
    _confirmed_fulfillment,
    _provider_paired_fulfillment,
    _save_fulfillment_activity,
    _targetless_run,
)
from tests.unit.test_workout_publication import (
    FakeClient,
    WorkoutPublicationService,
)


def _with_edited_first_step(event):
    assert event.workout_doc is not None
    first_step = event.workout_doc.steps[0]
    return event.model_copy(
        update={
            "workout_doc": event.workout_doc.model_copy(
                update={
                    "steps": [
                        first_step.model_copy(
                            update={"duration_seconds": first_step.duration_seconds + 1}
                        ),
                        *event.workout_doc.steps[1:],
                    ]
                }
            )
        }
    )


def test_remote_step_edit_blocks_a_new_local_content_revision(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    original = _authoritative(_targetless_run("semantic-drift", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    assert event_id is not None
    client.events[event_id] = _with_edited_first_step(client.events[event_id])
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the newly approved local content."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]

    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not status.reconciliation_safe
    assert status.items[0].error_type == "remote_drift"
    assert status.items[0].drift_resolution_token_sha256 is not None
    assert reconciled.partial
    assert reconciled.items[0].error_type == "remote_drift"
    assert client.upserts == 1


def test_pending_identity_is_fresh_read_before_recovery(
    tmp_path,
    monkeypatch,
) -> None:
    class RacingListClient(FakeClient):
        interrupt_create = True
        mutate_after_next_list = False

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_create:
                self.interrupt_create = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

        def list_events(self, oldest, newest, *, athlete_id=None):
            listed = super().list_events(oldest, newest, athlete_id=athlete_id)
            if self.mutate_after_next_list and listed:
                self.mutate_after_next_list = False
                remote = listed[0]
                self.events[remote.id] = _with_edited_first_step(remote)
            return listed

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = RacingListClient()
    service = WorkoutPublicationService(repo, client)
    workout = _targetless_run("pending-list-race", date(2026, 8, 11))
    with pytest.raises(IntervalsTransportError):
        service.publish(workout)
    client.mutate_after_next_list = True

    with pytest.raises(PublicationSafetyError):
        service.publish(workout)

    assert client.upserts == 1


def test_existing_upsert_rechecks_remote_after_durable_pending_staging(
    tmp_path,
    monkeypatch,
) -> None:
    class RacingUpsertClient(FakeClient):
        race_enabled = False
        race_get_calls = 0

        def get_event(self, event_id, *, athlete_id=None):
            remote = super().get_event(event_id, athlete_id=athlete_id)
            if self.race_enabled:
                self.race_get_calls += 1
                if self.race_get_calls == 3:
                    edited = _with_edited_first_step(remote).model_copy(
                        update={"description": "Athlete edited this workout remotely."}
                    )
                    self.events[event_id] = edited
            return remote

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = RacingUpsertClient()
    original = _authoritative(_targetless_run("upsert-race", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    assert event_id is not None
    service.workouts = [
        replace(
            original,
            prescription=original.prescription.model_copy(
                update={"purpose": "Use the revised approved workout."}
            ),
            applied_week_approval_id="week_approval_2222222222222222",
            applied_running_workouts_sha256="b" * 64,
        )
    ]
    reconcile_verified_status = service._reconcile_status

    def enable_race_after_status(status, **kwargs):
        client.race_enabled = True
        return reconcile_verified_status(status, **kwargs)

    monkeypatch.setattr(service, "_reconcile_status", enable_race_after_status)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert report.partial
    assert report.items[0].error_type == "remote_drift"
    assert client.upserts == 1
    assert client.events[event_id].description == ("Athlete edited this workout remotely.")


def test_fulfilled_update_rechecks_event_after_activity_pair_preflight(
    tmp_path,
    monkeypatch,
) -> None:
    class EventRaceClient(FakeClient):
        mutate_event_on_activity_read = False

        def get_activity(self, activity_id, *, intervals=True):
            activity = super().get_activity(activity_id, intervals=intervals)
            if self.mutate_event_on_activity_read:
                self.mutate_event_on_activity_read = False
                event_id = activity.paired_event_id
                assert event_id is not None
                self.events[event_id] = self.events[event_id].model_copy(
                    update={"description": "Athlete changed the event during preflight."}
                )
            return activity

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = EventRaceClient()
    original = _authoritative(_targetless_run("paired-upsert-race", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    assert event_id is not None
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="paired_upsert_race_activity",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_paired_upsert_race_activity"] = ActivityDTO(
        id="i_paired_upsert_race_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id,
    )
    fulfillment = _provider_paired_fulfillment(
        original,
        local_activity_id="paired_upsert_race_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    placement = resolve_provider_occurrence_placements(
        repo,
        [original],
    ).placements_by_local_workout_id[original.identity.local_workout_id]
    client.mutate_event_on_activity_read = True

    with pytest.raises(PublicationSafetyError, match="immediately before"):
        service.workout_service._publish(
            original,
            provider_occurrence_date=date(2026, 8, 10),
            provider_occurrence_placement=placement,
            provider_name=provider_workout_names([original.prescription])[
                original.identity.local_workout_id
            ],
        )

    assert client.upserts == 1
    assert client.events[event_id].description == ("Athlete changed the event during preflight.")


def test_same_week_date_only_drag_is_adopted_without_rewriting_remote_event(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("dragged-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    stored_after_status = load_manifest(repo).workouts["dragged-run"]
    assert stored_after_status.provider_start_date_local == "2026-08-11T00:00:00"
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    repeated = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert status.reconciliation_safe
    assert status.items[0].provider_occurrence_date == date(2026, 8, 10)
    assert [item.status for item in reconciled.items] == ["recovered"]
    assert reconciled.items[0].occurrence_date == date(2026, 8, 11)
    assert reconciled.items[0].provider_occurrence_date == date(2026, 8, 10)
    assert [item.status for item in repeated.items] == ["noop"]
    assert client.upserts == 1
    stored = load_manifest(repo).workouts["dragged-run"]
    assert stored.occurrence_date == date(2026, 8, 11)
    assert stored.provider_start_date_local == "2026-08-10T00:00:00"


@pytest.mark.parametrize(
    ("approved_date", "invalid_dragged_date"),
    [
        (date(2026, 3, 24), date(2026, 3, 29)),
        (date(2026, 10, 20), date(2026, 10, 25)),
    ],
)
def test_same_week_drag_rejects_dst_gap_and_fold_wall_times(
    tmp_path,
    monkeypatch,
    approved_date: date,
    invalid_dragged_date: date,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(
        _targetless_run("dst-boundary-drag", approved_date).model_copy(
            update={"start_time_local": time(2, 30)}
        )
    )
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = (
        service.reconcile_week(
            1,
            as_of_date=approved_date,
        )
        .items[0]
        .event_id
    )
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": (f"{invalid_dragged_date.isoformat()}T02:30:00")}
    )

    status = service.status_week(1, as_of_date=approved_date)

    assert not status.reconciliation_safe
    assert status.items[0].error_type == "remote_drift"
    placement = load_manifest(repo).workout_provider_occurrence_placements["dst-boundary-drag"]
    assert placement.calendar_source == "approved_schedule"
    assert placement.calendar_occurrence_date == approved_date


def test_pending_only_same_week_drag_is_recovered_without_remote_rewrite(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedCreateClient(FakeClient):
        interrupt_next_upsert = True

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedCreateClient()
    workout = _authoritative(_targetless_run("pending-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    interrupted = service.reconcile_week(1, as_of_date=date(2026, 8, 9))
    assert interrupted.partial
    event_id = next(iter(client.events))
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert status.reconciliation_safe
    assert status.items[0].provider_occurrence_date == date(2026, 8, 10)
    assert [item.status for item in reconciled.items] == ["recovered"]
    assert client.upserts == 1
    placement = load_manifest(repo).workout_provider_occurrence_placements["pending-drag"]
    assert placement.calendar_source == "provider_calendar"
    assert placement.calendar_occurrence_date == date(2026, 8, 10)


def test_future_pending_restore_reuses_a_provider_rewritten_uid(
    tmp_path,
    monkeypatch,
) -> None:
    class ServerUidLostResponseClient(FakeClient):
        lose_next_response = True

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.lose_next_response:
                self.lose_next_response = False
                stored = stored.model_copy(update={"uid": "server-assigned-uid"})
                self.events[stored.id] = stored
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = ServerUidLostResponseClient()
    workout = _authoritative(_targetless_run("future-server-uid", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    expected_description = client.events[event_id].description
    client.events[event_id] = client.events[event_id].model_copy(
        update={"description": "Athlete accidentally edited the workout."}
    )
    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    token = status.items[0].drift_resolution_token_sha256
    assert token is not None

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 10),
        athlete_confirmation_reference=(
            "Athlete confirmed restoring the exact future pending workout."
        ),
        confirmed_drift_target_tokens=[token],
    )

    assert restored.reconciliation_safe
    assert [item.status for item in restored.items] == ["updated"]
    assert client.upserts == 2
    assert list(client.events) == [event_id]
    assert client.events[event_id].description == expected_description
    manifest = load_manifest(repo)
    assert manifest.workouts["future-server-uid"].event_id == event_id
    assert manifest.workouts["future-server-uid"].uid == "server-assigned-uid"
    assert manifest.workouts["future-server-uid"].requested_uid == uid_for("future-server-uid")


def test_renderer_evolution_pending_drift_can_be_confirmed_and_replaced(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedCreateClient(FakeClient):
        interrupt_next_upsert = True

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedCreateClient()
    workout_payload = _targetless_run(
        "renderer-evolution",
        date(2026, 8, 11),
    ).model_dump(mode="json")
    workout_payload["workout_type"] = "tempo"
    workout_payload["planned_duration_seconds"] = 2_400
    workout_payload["planned_distance_meters"] = 5_000
    workout_payload["planned_low_intensity_duration_seconds"] = 1_440
    workout_payload["planned_moderate_intensity_duration_seconds"] = 0
    workout_payload["planned_high_intensity_duration_seconds"] = 960
    workout_payload["structured_workout"] = {
        "sport": "run",
        "steps": [
            {
                "kind": "steady",
                "duration": {"unit": "seconds", "value": 600},
                "intensity": "warmup",
            },
            {
                "kind": "repeat",
                "repetitions": 2,
                "steps": [
                    {
                        "kind": "steady",
                        "duration": {
                            "unit": "meters",
                            "value": 1_500,
                            "nominal_seconds": 480,
                        },
                        "target": {
                            "mode": "pace",
                            "unit": "seconds_per_kilometer",
                            "minimum": 310,
                            "maximum": 320,
                        },
                        "intensity": "interval",
                    },
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 120},
                        "intensity": "recovery",
                    },
                ],
            },
            {
                "kind": "steady",
                "duration": {"unit": "seconds", "value": 600},
                "intensity": "cooldown",
            },
        ],
    }
    workout = _authoritative(RunningWorkoutPrescription.model_validate(workout_payload))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    current_renderer = preparation_module.render_structured_workout

    def legacy_renderer(steps):
        return current_renderer(steps).replace("\n\n", "\n").replace(" Pace", "")

    monkeypatch.setattr(preparation_module, "render_structured_workout", legacy_renderer)
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    malformed_document = client.events[event_id].workout_doc
    assert malformed_document is not None
    assert len(provider_workout_semantics(malformed_document)) == 4

    monkeypatch.setattr(
        preparation_module,
        "render_structured_workout",
        current_renderer,
    )
    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    token = status.items[0].drift_resolution_token_sha256

    assert not status.reconciliation_safe
    assert status.items[0].error_type == "remote_drift"
    assert token is not None

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 10),
        athlete_confirmation_reference=(
            "Athlete confirmed replacing the malformed pending workout."
        ),
        confirmed_drift_target_tokens=[token],
    )

    assert restored.reconciliation_safe
    assert [item.status for item in restored.items] == ["updated"]
    assert client.upserts == 2
    assert list(client.events) == [event_id]
    repaired_document = client.events[event_id].workout_doc
    assert repaired_document is not None
    assert len(provider_workout_semantics(repaired_document)) == 6
    manifest = load_manifest(repo)
    assert "renderer-evolution" not in manifest.pending
    assert manifest.workouts["renderer-evolution"].event_id == event_id
    final_status = service.status_week(1, as_of_date=date(2026, 8, 10))
    assert final_status.reconciliation_safe
    assert [item.status for item in final_status.items] == ["ready"]


def test_pending_only_provider_pair_is_bound_during_recovery(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedCreateClient(FakeClient):
        interrupt_next_upsert = True

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedCreateClient()
    workout = _authoritative(_targetless_run("pending-pair", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="pending_pair_activity",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_pending_pair_activity"] = ActivityDTO(
        id="i_pending_pair_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id,
    )
    fulfillment = _provider_paired_fulfillment(
        workout,
        local_activity_id="pending_pair_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert status.reconciliation_safe
    assert reconciled.reconciliation_safe
    assert [item.status for item in reconciled.items] == ["updated"]
    assert load_manifest(repo).workouts["pending-pair"].event_id == event_id
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"


def test_pending_recovery_rechecks_event_after_pairing_preflight(
    tmp_path,
    monkeypatch,
) -> None:
    class EventRaceClient(FakeClient):
        lose_next_response = True
        race_enabled = False
        pair_reads = 0
        target_event_id = None

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.lose_next_response:
                self.lose_next_response = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

        def get_activity(self, activity_id, *, intervals=True):
            if self.race_enabled:
                self.pair_reads += 1
                if self.pair_reads == 3:
                    assert self.target_event_id is not None
                    self.events[self.target_event_id] = self.events[
                        self.target_event_id
                    ].model_copy(
                        update={
                            "description": ("Athlete changed the event during pairing preflight.")
                        }
                    )
            return super().get_activity(activity_id, intervals=intervals)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = EventRaceClient()
    workout = _authoritative(_targetless_run("pending-event-race", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="pending_pair_event_race_activity",
        execution_date=date(2026, 8, 11),
    )
    client.activities["i_pending_pair_event_race_activity"] = ActivityDTO(
        id="i_pending_pair_event_race_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 11, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 11, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id,
    )
    fulfillment = _provider_paired_fulfillment(
        workout,
        local_activity_id="pending_pair_event_race_activity",
        execution_date=date(2026, 8, 11),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    client.target_event_id = event_id
    client.race_enabled = True

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not reconciled.reconciliation_safe
    assert reconciled.partial
    assert reconciled.items[0].error_type == "remote_drift"
    manifest = load_manifest(repo)
    assert manifest.workouts == {}
    assert set(manifest.pending) == {"pending-event-race"}
    assert client.upserts == 1


def test_publication_preflight_rejects_a_different_activity_point_read(
    tmp_path,
    monkeypatch,
) -> None:
    class WrongActivityIdentityClient(FakeClient):
        def get_activity(self, activity_id, *, intervals=True):
            remote = super().get_activity(activity_id, intervals=intervals)
            return remote.model_copy(update={"id": f"wrong-{activity_id}"})

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = WrongActivityIdentityClient()
    workout = _authoritative(_targetless_run("wrong-activity-read", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="wrong_activity_read",
        execution_date=date(2026, 8, 11),
    )
    client.activities["i_wrong_activity_read"] = ActivityDTO(
        id="i_wrong_activity_read",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 11, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 11, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id,
    )
    fulfillment = _provider_paired_fulfillment(
        workout,
        local_activity_id="wrong_activity_read",
        execution_date=date(2026, 8, 11),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    placement = resolve_provider_occurrence_placements(
        repo,
        [workout],
    ).placements_by_local_workout_id[workout.identity.local_workout_id]

    with pytest.raises(PublicationSafetyError, match="readback identity"):
        assert_fulfillment_pair_matches_remote_placement(
            repo,
            client,
            placement,
            client.events[event_id],
        )


def test_missing_pending_provider_pair_blocks_before_publication_recovery(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedCreateClient(FakeClient):
        interrupt_next_upsert = True

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedCreateClient()
    workout = _authoritative(_targetless_run("missing-pending-pair", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="missing_pending_pair_activity",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_missing_pending_pair_activity"] = ActivityDTO(
        id="i_missing_pending_pair_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=None,
    )
    fulfillment = _provider_paired_fulfillment(
        workout,
        local_activity_id="missing_pending_pair_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not status.reconciliation_safe
    assert status.items[0].remote_pairing_status == "pairing_blocked"
    assert status.items[0].remote_pairing_blocker_code == ("provider_observed_pair_missing")
    assert not reconciled.reconciliation_safe
    assert client.upserts == 1
    assert load_manifest(repo).workouts == {}
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"


def test_pending_provider_pair_is_rechecked_immediately_before_recovery(
    tmp_path,
    monkeypatch,
) -> None:
    class PairRaceClient(FakeClient):
        lose_next_response = True
        race_enabled = False
        pair_reads = 0

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.lose_next_response:
                self.lose_next_response = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

        def get_activity(self, activity_id, *, intervals=True):
            if self.race_enabled:
                self.pair_reads += 1
                if self.pair_reads == 3:
                    self.activities[activity_id] = self.activities[activity_id].model_copy(
                        update={"paired_event_id": None}
                    )
            return super().get_activity(activity_id, intervals=intervals)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = PairRaceClient()
    workout = _authoritative(_targetless_run("pending-pair-race", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="pending_pair_race_activity",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_pending_pair_race_activity"] = ActivityDTO(
        id="i_pending_pair_race_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id,
    )
    fulfillment = _provider_paired_fulfillment(
        workout,
        local_activity_id="pending_pair_race_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    client.race_enabled = True

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not reconciled.reconciliation_safe
    assert reconciled.items[0].status == "error"
    assert client.upserts == 1
    assert load_manifest(repo).workouts == {}
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"


def test_pending_athlete_fulfillment_blocks_a_different_live_pair(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedCreateClient(FakeClient):
        interrupt_next_upsert = True

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedCreateClient()
    workout = _authoritative(_targetless_run("pending-pair-conflict", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="pending_pair_conflict_activity",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_pending_pair_conflict_activity"] = ActivityDTO(
        id="i_pending_pair_conflict_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id + 999,
    )
    fulfillment = _confirmed_fulfillment(
        workout,
        local_activity_id="pending_pair_conflict_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not reconciled.reconciliation_safe
    assert reconciled.items[0].remote_pairing_status == "pairing_blocked"
    assert reconciled.items[0].remote_pairing_blocker_code == ("activity_paired_to_different_event")
    assert client.upserts == 1
    assert load_manifest(repo).workouts == {}
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"


def test_pending_dual_evidence_can_restore_a_missing_native_pair(
    tmp_path,
    monkeypatch,
) -> None:
    class LostCreateResponseClient(FakeClient):
        lose_next_response = True

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.lose_next_response:
                self.lose_next_response = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = LostCreateResponseClient()
    workout = _authoritative(_targetless_run("pending-dual-pair", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="pending_dual_pair_activity",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_pending_dual_pair_activity"] = ActivityDTO(
        id="i_pending_dual_pair_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=None,
    )
    provider_fulfillment = _provider_paired_fulfillment(
        workout,
        local_activity_id="pending_dual_pair_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    athlete_fulfillment = _confirmed_fulfillment(
        workout,
        local_activity_id="pending_dual_pair_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    fulfillment = provider_fulfillment.model_copy(
        update={"athlete_confirmation": athlete_fulfillment.athlete_confirmation}
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert reconciled.reconciliation_safe, reconciled.model_dump(mode="json")
    assert reconciled.items[0].remote_pairing_status == "paired"
    assert client.activities["i_pending_dual_pair_activity"].paired_event_id == event_id


def test_pending_athlete_fulfillment_from_strava_blocks_before_recovery(
    tmp_path,
    monkeypatch,
) -> None:
    class LostCreateResponseClient(FakeClient):
        lose_next_response = True

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.lose_next_response:
                self.lose_next_response = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = LostCreateResponseClient()
    workout = _authoritative(_targetless_run("pending-strava", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="pending_strava_activity",
        execution_date=date(2026, 8, 10),
        source_recording_provider="STRAVA",
    )
    client.activities["i_pending_strava_activity"] = ActivityDTO(
        id="i_pending_strava_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="STRAVA",
        paired_event_id=None,
    )
    fulfillment = _confirmed_fulfillment(
        workout,
        local_activity_id="pending_strava_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not status.reconciliation_safe
    assert status.items[0].remote_pairing_blocker_code == ("activity_source_is_not_mutable")
    assert not reconciled.reconciliation_safe
    assert client.upserts == 1
    assert load_manifest(repo).workouts == {}
    assert event_id in client.events


def test_unpublished_athlete_fulfillment_from_strava_blocks_before_create(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("unpublished-strava", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="unpublished_strava_activity",
        execution_date=date(2026, 8, 10),
        source_recording_provider="STRAVA",
    )
    client.activities["i_unpublished_strava_activity"] = ActivityDTO(
        id="i_unpublished_strava_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="STRAVA",
        paired_event_id=None,
    )
    fulfillment = _confirmed_fulfillment(
        workout,
        local_activity_id="unpublished_strava_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not status.reconciliation_safe
    assert status.items[0].remote_pairing_blocker_code == ("activity_source_is_not_mutable")
    assert not reconciled.reconciliation_safe
    assert client.upserts == 0
    assert client.events == {}


def test_pending_only_drag_changed_after_status_is_not_rewritten_from_stale_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedCreateClient(FakeClient):
        interrupt_next_upsert = True

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedCreateClient()
    workout = _authoritative(_targetless_run("pending-race", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    reconcile_verified_status = service._reconcile_status

    def change_remote_after_status(status, **kwargs):
        client.events[event_id] = client.events[event_id].model_copy(
            update={"start_date_local": "2026-08-11T00:00:00"}
        )
        return reconcile_verified_status(status, **kwargs)

    monkeypatch.setattr(service, "_reconcile_status", change_remote_after_status)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert report.partial
    assert not report.reconciliation_safe
    assert report.items[0].status == "error"
    assert report.items[0].error_type == "remote_drift"
    assert client.upserts == 1
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"


def test_dual_state_pending_same_week_drag_recovers_without_another_remote_write(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedUpdateClient(FakeClient):
        interrupt_next_upsert = False

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "update response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedUpdateClient()
    original = _authoritative(_targetless_run("dual-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the exact interrupted revised purpose."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.interrupt_next_upsert = True
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not reconciled.partial
    assert [item.status for item in reconciled.items] == ["recovered"]
    assert client.upserts == 2
    assert "dual-drag" not in load_manifest(repo).pending
    assert load_manifest(repo).workout_provider_occurrence_placements[
        "dual-drag"
    ].calendar_occurrence_date == date(2026, 8, 10)


def test_dual_state_pending_drag_changed_after_status_is_not_rewritten(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedUpdateClient(FakeClient):
        interrupt_next_upsert = False

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "update response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedUpdateClient()
    original = _authoritative(_targetless_run("dual-race", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the exact interrupted revised purpose."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.interrupt_next_upsert = True
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    reconcile_verified_status = service._reconcile_status

    def change_remote_after_status(status, **kwargs):
        client.events[event_id] = client.events[event_id].model_copy(
            update={"start_date_local": "2026-08-11T00:00:00"}
        )
        return reconcile_verified_status(status, **kwargs)

    monkeypatch.setattr(service, "_reconcile_status", change_remote_after_status)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert report.partial
    assert not report.reconciliation_safe
    assert report.items[0].status == "error"
    assert report.items[0].error_type == "remote_drift"
    assert client.upserts == 2
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"


def test_dual_state_old_published_drag_is_adopted_for_revised_pending_content(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedBeforeUpdateClient(FakeClient):
        interrupt_next_upsert = False

        def upsert_event(self, event, *, athlete_id=None):
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "update was not submitted",
                    operation="upsert_event",
                )
            return super().upsert_event(event, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedBeforeUpdateClient()
    original = _authoritative(_targetless_run("old-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the approved revised content."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.interrupt_next_upsert = True
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    monkeypatch.setattr(
        week_verification_module,
        "retained_publication_authority",
        lambda _repo, _record: RetainedPublicationAuthority(
            workout=original,
            provider_name=provider_workout_names([original.prescription])["old-drag"],
        ),
    )
    monkeypatch.setattr(
        pending_recovery_module,
        "retained_publication_authority",
        lambda _repo, _record: RetainedPublicationAuthority(
            workout=original,
            provider_name=provider_workout_names([original.prescription])["old-drag"],
        ),
    )

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not report.partial, report.model_dump(mode="json")
    assert [item.status for item in report.items] == ["updated"]
    assert client.upserts == 2
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    assert "approved revised content" in (client.events[event_id].description or "")
    placement = load_manifest(repo).workout_provider_occurrence_placements["old-drag"]
    assert placement.calendar_source == "provider_calendar"
    assert placement.calendar_occurrence_date == date(2026, 8, 10)


def test_revised_pending_provider_date_survives_ambiguous_update_restart(
    tmp_path,
    monkeypatch,
) -> None:
    class TwiceInterruptedUpdateClient(FakeClient):
        interruption: str | None = None

        def upsert_event(self, event, *, athlete_id=None):
            if self.interruption == "before":
                self.interruption = None
                raise IntervalsTransportError(
                    "update was not submitted",
                    operation="upsert_event",
                )
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interruption == "after":
                self.interruption = None
                raise IntervalsTransportError(
                    "update response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = TwiceInterruptedUpdateClient()
    original = _authoritative(_targetless_run("restart-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the approved revised restart content."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.interruption = "before"
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    retained = RetainedPublicationAuthority(
        workout=original,
        provider_name=provider_workout_names([original.prescription])["restart-drag"],
    )
    monkeypatch.setattr(
        week_verification_module,
        "retained_publication_authority",
        lambda _repo, _record: retained,
    )
    monkeypatch.setattr(
        pending_recovery_module,
        "retained_publication_authority",
        lambda _repo, _record: retained,
    )
    client.interruption = "after"
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 10)).partial
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    pending_placement = load_manifest(repo).pending_provider_occurrence_placements["restart-drag"]
    assert pending_placement.calendar_source == "provider_calendar"
    assert pending_placement.calendar_occurrence_date == date(2026, 8, 10)

    recovered = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not recovered.partial, recovered.model_dump(mode="json")
    assert [item.status for item in recovered.items] == ["recovered"]
    assert client.upserts == 2
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"


def test_adopted_provider_date_survives_a_content_only_approval_revision(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    original = _authoritative(_targetless_run("retained-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    assert not service.reconcile_week(1, as_of_date=date(2026, 8, 10)).partial
    retained_authority = AppliedWorkoutAuthority(
        applied_week_approval_id=original.applied_week_approval_id,
        applied_running_workouts_sha256=original.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(original.prescription),
        schedule_timezone=original.schedule_timezone,
        scheduled_local_date=original.prescription.date,
    )
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the newly approved content on the retained day."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
        applied_authority_history=(retained_authority,),
    )
    service.workouts = [revised]

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not report.partial, report.model_dump(mode="json")
    assert [item.status for item in report.items] == ["updated"]
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    placement = load_manifest(repo).workout_provider_occurrence_placements["retained-drag"]
    assert placement.calendar_source == "provider_calendar"
    assert placement.calendar_occurrence_date == date(2026, 8, 10)


def test_exact_prior_content_drag_is_adopted_with_a_local_content_revision(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    original = _authoritative(_targetless_run("revision-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    prior_authority = AppliedWorkoutAuthority(
        applied_week_approval_id=original.applied_week_approval_id,
        applied_running_workouts_sha256=original.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(original.prescription),
        schedule_timezone=original.schedule_timezone,
        scheduled_local_date=original.prescription.date,
    )
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the approved revision on the dragged day."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
        applied_authority_history=(prior_authority,),
    )
    service.workouts = [revised]
    retained = RetainedPublicationAuthority(
        workout=original,
        provider_name=provider_workout_names([original.prescription])["revision-drag"],
    )
    monkeypatch.setattr(
        week_verification_module,
        "retained_publication_authority",
        lambda _repo, _record: retained,
    )
    monkeypatch.setattr(
        pending_recovery_module,
        "retained_publication_authority",
        lambda _repo, _record: retained,
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert status.reconciliation_safe
    assert status.items[0].provider_occurrence_date == date(2026, 8, 10)
    assert [item.status for item in reconciled.items] == ["updated"]
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    assert client.upserts == 2


def test_new_approved_date_replaces_an_older_provider_calendar_placement(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    original = _authoritative(_targetless_run("revised-date", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    assert event_id is not None
    prior_authority = AppliedWorkoutAuthority(
        applied_week_approval_id=original.applied_week_approval_id,
        applied_running_workouts_sha256=original.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(original.prescription),
        schedule_timezone=original.schedule_timezone,
        scheduled_local_date=original.prescription.date,
    )
    revised = replace(
        original,
        prescription=original.prescription.model_copy(update={"date": date(2026, 8, 12)}),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
        applied_authority_history=(prior_authority,),
    )
    service.workouts = [revised]

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert reconciled.reconciliation_safe
    assert [item.status for item in reconciled.items] == ["updated"]
    assert client.events[event_id].start_date_local == "2026-08-12T00:00:00"
    manifest = load_manifest(repo)
    assert manifest.workouts["revised-date"].occurrence_date == date(2026, 8, 12)
    placement = manifest.workout_provider_occurrence_placements["revised-date"]
    assert placement.calendar_source == "approved_schedule"
    assert placement.calendar_occurrence_date == date(2026, 8, 12)


def test_published_past_workout_dragged_later_in_week_is_still_adopted(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("past-drag", date(2026, 8, 10)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-14T00:00:00"}
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 11))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert status.reconciliation_safe
    assert [item.status for item in status.items] == ["ready"]
    assert status.run_workouts_requiring_reconciliation == 1
    assert status.items[0].provider_occurrence_date == date(2026, 8, 14)
    assert [item.status for item in reconciled.items] == ["recovered"]
    assert reconciled.items[0].occurrence_date == date(2026, 8, 10)
    assert reconciled.items[0].provider_occurrence_date == date(2026, 8, 14)
    assert client.upserts == 1


def test_concurrent_remote_change_after_drag_verification_is_unsafe(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("concurrent-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    reconcile_verified_status = service._reconcile_status

    def change_remote_after_status(status, **kwargs):
        client.events[event_id] = client.events[event_id].model_copy(
            update={"start_date_local": "2026-08-12T00:00:00"}
        )
        return reconcile_verified_status(status, **kwargs)

    monkeypatch.setattr(service, "_reconcile_status", change_remote_after_status)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert report.partial
    assert not report.reconciliation_safe
    assert report.items[0].status == "error"
    assert report.items[0].error_type == "remote_drift"
    assert client.upserts == 1


def test_same_week_drag_with_owned_content_change_remains_remote_drift(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("edited-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-10T00:00:00",
            "description": "Athlete changed the prescribed workout content.",
        }
    )

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not blocked.reconciliation_safe
    assert blocked.items[0].error_type == "remote_drift"
    assert blocked.items[0].drift_resolution_token_sha256 is not None
    assert client.upserts == 1
    assert (
        load_manifest(repo).workouts["edited-drag"].provider_start_date_local
        == "2026-08-11T00:00:00"
    )


def test_same_week_drag_that_changes_approved_start_time_remains_remote_drift(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout_payload = _targetless_run(
        "retimed-drag",
        date(2026, 8, 11),
    ).model_dump(mode="python")
    workout_payload["start_time_local"] = "07:00:00"
    workout = _authoritative(RunningWorkoutPrescription.model_validate(workout_payload))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T08:00:00"}
    )

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not blocked.reconciliation_safe
    assert blocked.items[0].error_type == "remote_drift"
    assert blocked.items[0].drift_resolution_token_sha256 is not None
    assert client.upserts == 1


def test_date_only_drag_outside_the_approved_training_week_remains_remote_drift(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("cross-week-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-17T00:00:00"}
    )

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not blocked.reconciliation_safe
    assert blocked.items[0].error_type == "remote_drift"
    assert client.upserts == 1


def test_provider_paired_fulfillment_accepts_an_already_dragged_execution_date(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("paired-drag", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_paired_drag",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_act_paired_drag"] = ActivityDTO(
        id="i_act_paired_drag",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id,
    )
    fulfillment = _provider_paired_fulfillment(
        workout,
        local_activity_id="act_paired_drag",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert report.reconciliation_safe
    assert not report.partial
    assert [item.status for item in report.items] == ["recovered"]
    assert report.items[0].occurrence_date == date(2026, 8, 11)
    assert report.items[0].provider_occurrence_date == date(2026, 8, 10)
    assert report.items[0].remote_pairing_status == "pairing_noop"
    assert client.upserts == 1
    stored = load_manifest(repo).workouts["paired-drag"]
    assert stored.occurrence_date == date(2026, 8, 11)
    assert stored.provider_start_date_local == "2026-08-10T00:00:00"


def test_active_fulfillment_blocks_a_conflicting_later_provider_drag(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("fulfilled-drag", date(2026, 8, 12)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    assert event_id is not None
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="fulfilled_drag_activity",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_fulfilled_drag_activity"] = ActivityDTO(
        id="i_fulfilled_drag_activity",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id,
    )
    fulfillment = _provider_paired_fulfillment(
        workout,
        local_activity_id="fulfilled_drag_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    placed = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert placed.reconciliation_safe
    placement_before = load_manifest(repo).workout_provider_occurrence_placements["fulfilled-drag"]
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-11T00:00:00"}
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 11))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert not status.reconciliation_safe
    assert status.items[0].error_type == "remote_drift"
    assert not reconciled.reconciliation_safe
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"
    assert (
        load_manifest(repo).workout_provider_occurrence_placements["fulfilled-drag"]
        == placement_before
    )


def test_provider_paired_fulfillment_retains_cross_week_execution_date(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("paired-cross-week", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-17T00:00:00"}
    )
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_paired_cross_week",
        execution_date=date(2026, 8, 17),
    )
    client.activities["i_act_paired_cross_week"] = ActivityDTO(
        id="i_act_paired_cross_week",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 17, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 17, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id,
    )
    fulfillment = _provider_paired_fulfillment(
        workout,
        local_activity_id="act_paired_cross_week",
        execution_date=date(2026, 8, 17),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 17))
    repeated = service.reconcile_week(1, as_of_date=date(2026, 8, 17))

    assert [item.status for item in reconciled.items] == ["recovered"]
    assert [item.status for item in repeated.items] == ["noop"]
    assert reconciled.items[0].occurrence_date == date(2026, 8, 11)
    assert reconciled.items[0].provider_occurrence_date == date(2026, 8, 17)
    assert repeated.items[0].remote_pairing_status == "pairing_noop"
    assert client.events[event_id].start_date_local == "2026-08-17T00:00:00"
    assert load_manifest(repo).workouts["paired-cross-week"].occurrence_date == date(
        2026,
        8,
        11,
    )
    assert client.upserts == 1
