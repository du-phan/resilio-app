"""Focused workout publication retirement tests."""

from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from resilio.core.planning.adherence_evidence import (
    AppliedWorkoutAuthority,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import (
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.core.workout_fulfillment.service import WorkoutFulfillmentService
from resilio.core.workout_publication import preparation as preparation_module
from resilio.core.workout_publication import (
    publication_deletion_recovery as deletion_recovery_module,
)
from resilio.core.workout_publication import week_service as week_service_module
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.naming import provider_workout_names
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    external_id_for,
    uid_for,
)
from resilio.core.workout_publication.publication_deletion_drift import (
    resolve_publication_deletion_drifts,
)
from resilio.core.workout_publication.publication_deletions import (
    activate_publication_deletion_monitoring,
    assert_publication_deletion_integrity,
    load_publication_deletion_manifest,
    publication_deletion_operation_id,
    reconcile_publication_deletion_operations,
    save_publication_deletion_manifest,
    stage_pending_publication_deletion,
)
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthorities,
    RetainedPublicationAuthority,
)
from resilio.core.workout_publication.semantics import (
    expected_workout_semantics,
    workout_semantics_sha256,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.integrations.intervals_icu.errors import IntervalsTransportError
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.publication_operations import (
    PendingPublicationDeletionOperation,
    PublicationDeletionDriftResolution,
    PublicationDeletionManifest,
)
from resilio.schemas.workout_fulfillment import (
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from tests.unit.run_publication_workflow_support import (
    HarnessRunWeekSynchronizationService,
    _after_latest_publication_verification,
    _authoritative,
    _confirmed_fulfillment,
    _pace_targeted_run,
    _provider_paired_fulfillment,
    _retain_test_authorities,
    _save_fulfillment_activity,
    _targetless_run,
)
from tests.unit.test_workout_publication import FakeClient


def _edit_first_remote_step(event):
    assert event.workout_doc is not None
    first_step = event.workout_doc.steps[0]
    changed_doc = event.workout_doc.model_copy(
        update={
            "steps": [
                first_step.model_copy(update={"duration_seconds": first_step.duration_seconds + 1}),
                *event.workout_doc.steps[1:],
            ]
        }
    )
    return event.model_copy(update={"workout_doc": changed_doc})


def test_published_retirement_fresh_reads_after_destructive_intent(
    tmp_path,
    monkeypatch,
) -> None:
    class RacingRetirementClient(FakeClient):
        race_get_calls = 0
        race_enabled = False

        def get_event(self, event_id, *, athlete_id=None):
            if self.race_enabled:
                self.race_get_calls += 1
                if self.race_get_calls == 2:
                    self.events[event_id] = _edit_first_remote_step(self.events[event_id])
            return super().get_event(event_id, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = RacingRetirementClient()
    workout = _authoritative(_targetless_run("published-race", date(2026, 8, 11)))
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
    client.race_enabled = True

    with pytest.raises(RemoteWorkoutDriftError, match="immediately before"):
        service.retirement_service.retire_published(
            workout.identity.local_workout_id,
            authoritative_workout=workout,
            provider_name=provider_workout_names([workout.prescription])[
                workout.identity.local_workout_id
            ],
        )

    assert event_id in client.events


def test_published_retirement_rejects_a_different_event_point_read(
    tmp_path,
    monkeypatch,
) -> None:
    class WrongEventIdentityClient(FakeClient):
        return_wrong_identity = False
        deleted_event_ids: list[int] = []

        def get_event(self, event_id, *, athlete_id=None):
            remote = super().get_event(event_id, athlete_id=athlete_id)
            return (
                remote.model_copy(update={"id": event_id + 1})
                if self.return_wrong_identity
                else remote
            )

        def delete_event(self, event_id, *, athlete_id=None):
            self.deleted_event_ids.append(event_id)
            return super().delete_event(event_id, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = WrongEventIdentityClient()
    workout = _authoritative(_targetless_run("wrong-event-read", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.return_wrong_identity = True

    with pytest.raises(PublicationSafetyError, match="readback identity"):
        service.retirement_service.retire_published(
            workout.identity.local_workout_id,
            authoritative_workout=workout,
            provider_name=provider_workout_names([workout.prescription])[
                workout.identity.local_workout_id
            ],
        )

    assert client.deleted_event_ids == []
    assert event_id in client.events


def test_pending_retirement_fresh_reads_after_tombstone_staging(
    tmp_path,
    monkeypatch,
) -> None:
    class RacingPendingClient(FakeClient):
        interrupt_create = True
        race_get_calls = 0
        race_enabled = False

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_create:
                self.interrupt_create = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

        def get_event(self, event_id, *, athlete_id=None):
            if self.race_enabled:
                self.race_get_calls += 1
                if self.race_get_calls == 2:
                    self.events[event_id] = _edit_first_remote_step(self.events[event_id])
            return super().get_event(event_id, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = RacingPendingClient()
    workout = _authoritative(_targetless_run("pending-retire-race", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    client.race_enabled = True

    with pytest.raises(RemoteWorkoutDriftError, match="immediately before"):
        service.retirement_service.retire_published(
            workout.identity.local_workout_id,
            authoritative_workout=workout,
            provider_name=provider_workout_names([workout.prescription])[
                workout.identity.local_workout_id
            ],
        )

    assert event_id in client.events
    assert len(load_publication_deletion_manifest(repo).operations) == 1


def test_replacement_week_deletes_only_stale_future_owned_run(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    old = _authoritative(_targetless_run("old-run", date(2026, 8, 6)))
    service = HarnessRunWeekSynchronizationService(repo, client, [old])
    first = service.reconcile_week(1, as_of_date=date(2026, 8, 2))
    old_event_id = first.items[0].event_id

    service.workouts = [_authoritative(_targetless_run("replacement-run", date(2026, 8, 6)))]
    replacement = service.reconcile_week(1, as_of_date=date(2026, 8, 2))

    assert [item.status for item in replacement.items] == ["created", "deleted"]
    assert old_event_id not in client.events
    assert len(client.events) == 1


def test_replacement_deletes_removed_past_workout_dragged_to_future_same_week(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("removed-moved-future", date(2026, 8, 3)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-07T00:00:00"}
    )
    replacement = _authoritative(_targetless_run("replacement-after-move", date(2026, 8, 9)))
    service.workouts = [replacement]
    _retain_test_authorities(monkeypatch, removed, replacement)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert report.reconciliation_safe
    assert not report.partial
    assert [item.status for item in report.items] == ["created", "deleted"]
    assert report.items[1].provider_occurrence_date == date(2026, 8, 7)
    assert event_id not in client.events
    assert "removed-moved-future" not in load_manifest(repo).workouts


def test_replacement_preserves_removed_future_workout_dragged_to_past(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("removed-moved-past", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-03T00:00:00"}
    )
    replacement = _authoritative(_targetless_run("replacement-after-past-move", date(2026, 8, 9)))
    service.workouts = [replacement]
    _retain_test_authorities(monkeypatch, removed, replacement)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert report.reconciliation_safe
    assert not report.partial
    assert [item.status for item in report.items] == ["created", "skipped_past"]
    assert report.items[1].provider_occurrence_date == date(2026, 8, 3)
    assert event_id in client.events
    assert "removed-moved-past" in load_manifest(repo).workouts


def test_replacement_rechecks_a_future_deletion_that_moves_to_past(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("moved-after-status", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    service.workouts = [_authoritative(_targetless_run("replacement-after-race", date(2026, 8, 9)))]
    _retain_test_authorities(monkeypatch, removed, *service.workouts)
    reconcile_verified_status = service._reconcile_status

    def move_remote_after_status(status, **kwargs):
        client.events[event_id] = client.events[event_id].model_copy(
            update={"start_date_local": "2026-08-03T00:00:00"}
        )
        return reconcile_verified_status(status, **kwargs)

    monkeypatch.setattr(service, "_reconcile_status", move_remote_after_status)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert report.reconciliation_safe
    assert not report.partial
    assert [item.status for item in report.items] == ["created", "skipped_past"]
    assert report.items[1].provider_occurrence_date == date(2026, 8, 3)
    assert event_id in client.events


def test_removed_past_workout_dragged_with_content_change_blocks_replacement(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("removed-edited-drag", date(2026, 8, 3)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-07T00:00:00",
            "description": "Athlete changed this obsolete workout's content.",
        }
    )
    service.workouts = [_authoritative(_targetless_run("blocked-replacement", date(2026, 8, 9)))]

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert not report.reconciliation_safe
    assert report.partial
    assert [item.status for item in report.items] == ["ready", "error"]
    assert report.items[1].error_type == "remote_drift"
    assert client.upserts == 1
    assert event_id in client.events


def test_confirmed_past_published_drift_restores_local_content_and_converges(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("restore-past", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    expected_description = client.events[event_id].description
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-03T00:00:00",
            "description": "Athlete accidentally changed the workout content.",
        }
    )
    replacement = _authoritative(_targetless_run("replacement-after-restore", date(2026, 8, 9)))
    service.workouts = [replacement]
    _retain_test_authorities(monkeypatch, removed, replacement)
    status = service.status_week(1, as_of_date=date(2026, 8, 4))
    token = status.items[-1].drift_resolution_token_sha256
    assert token is not None

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 4),
        athlete_confirmation_reference=(
            "Athlete confirmed restoring this exact stale workout target."
        ),
        confirmed_drift_target_tokens=[token],
    )
    repeated = service.status_week(1, as_of_date=date(2026, 8, 4))

    assert restored.reconciliation_safe, restored.model_dump(mode="json")
    assert [item.status for item in restored.items] == ["created", "updated"]
    assert client.events[event_id].description == expected_description
    assert client.events[event_id].start_date_local == "2026-08-03T00:00:00"
    assert repeated.reconciliation_safe, repeated.model_dump(mode="json")
    assert repeated.items[-1].status == "skipped_past"
    assert repeated.items[-1].drift_resolution_token_sha256 is None
    manifest = load_manifest(repo)
    assert "restore-past" in manifest.workouts
    assert "restore-past" not in manifest.pending


def test_confirmed_past_restore_recovers_after_a_lost_update_response(
    tmp_path,
    monkeypatch,
) -> None:
    class LostRestoreResponseClient(FakeClient):
        lose_target_uid = None

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.lose_target_uid == event.uid:
                self.lose_target_uid = None
                raise IntervalsTransportError(
                    "restore response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = LostRestoreResponseClient()
    removed = _authoritative(_targetless_run("restore-after-crash", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    expected_description = client.events[event_id].description
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-03T00:00:00",
            "description": "Athlete accidentally changed the workout content.",
        }
    )
    replacement = _authoritative(
        _targetless_run("replacement-after-restore-crash", date(2026, 8, 9))
    )
    service.workouts = [replacement]
    removed_authority = RetainedPublicationAuthority(
        workout=removed,
        provider_name=provider_workout_names([removed.prescription])[
            removed.identity.local_workout_id
        ],
    )
    replacement_authority = RetainedPublicationAuthority(
        workout=replacement,
        provider_name=provider_workout_names([replacement.prescription])[
            replacement.identity.local_workout_id
        ],
    )
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            removed.identity.local_workout_id: RetainedPublicationAuthorities(
                published=removed_authority,
                pending=removed_authority,
            ),
            replacement.identity.local_workout_id: RetainedPublicationAuthorities(
                published=replacement_authority,
            ),
        },
    )
    status = service.status_week(1, as_of_date=date(2026, 8, 4))
    token = status.items[-1].drift_resolution_token_sha256
    assert token is not None
    client.lose_target_uid = client.events[event_id].uid

    interrupted = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 4),
        athlete_confirmation_reference=(
            "Athlete confirmed restoring this exact stale workout target."
        ),
        confirmed_drift_target_tokens=[token],
    )
    staged_manifest = load_manifest(repo)

    assert interrupted.partial
    assert "restore-after-crash" in staged_manifest.pending
    assert client.events[event_id].description == expected_description
    assert client.events[event_id].start_date_local == "2026-08-03T00:00:00"

    recovered = service.reconcile_week(1, as_of_date=date(2026, 8, 4))
    manifest = load_manifest(repo)

    assert recovered.reconciliation_safe, [
        (item.local_workout_id, item.error_type, item.message) for item in recovered.items
    ]
    assert recovered.items[-1].status == "skipped_past"
    assert "restore-after-crash" not in manifest.pending
    assert manifest.workouts["restore-after-crash"].event_id == event_id


def test_replacement_rechecks_a_past_stale_event_that_moves_back_to_future(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("future-after-status", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-03T00:00:00"}
    )
    replacement = _authoritative(
        _targetless_run("replacement-after-inverse-race", date(2026, 8, 9))
    )
    service.workouts = [replacement]
    _retain_test_authorities(monkeypatch, removed, replacement)
    reconcile_verified_status = service._reconcile_status

    def move_remote_after_status(status, **kwargs):
        client.events[event_id] = client.events[event_id].model_copy(
            update={"start_date_local": "2026-08-07T00:00:00"}
        )
        return reconcile_verified_status(status, **kwargs)

    monkeypatch.setattr(service, "_reconcile_status", move_remote_after_status)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert not report.partial
    assert [item.status for item in report.items] == ["created", "deleted"]
    assert event_id not in client.events


def test_stale_pace_workout_deletion_does_not_require_current_pace_settings(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_pace_targeted_run("removed-pace", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.settings[0] = client.settings[0].model_copy(
        update={"threshold_pace": None, "pace_zones": []}
    )
    replacement = _authoritative(
        _targetless_run("replacement-without-pace-settings", date(2026, 8, 9))
    )
    service.workouts = [replacement]
    _retain_test_authorities(monkeypatch, removed, replacement)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert not report.partial
    assert [item.status for item in report.items] == ["created", "deleted"]
    assert event_id not in client.events


def test_removed_date_only_drag_with_missing_step_semantics_blocks_deletion(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("removed-semantic-drift", date(2026, 8, 3)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-07T00:00:00",
            "workout_doc": None,
        }
    )
    replacement = _authoritative(
        _targetless_run("replacement-after-semantic-drift", date(2026, 8, 9))
    )
    service.workouts = [replacement]
    _retain_test_authorities(monkeypatch, removed, replacement)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert not report.reconciliation_safe
    assert report.partial
    assert [item.status for item in report.items] == ["ready", "error"]
    assert report.items[1].error_type == "remote_drift"
    assert client.upserts == 1
    assert event_id in client.events


def test_removed_unchanged_date_with_missing_step_semantics_blocks_deletion(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("removed-unchanged-semantic-drift", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(update={"workout_doc": None})
    replacement = _authoritative(
        _targetless_run("replacement-after-unchanged-drift", date(2026, 8, 9))
    )
    service.workouts = [replacement]
    _retain_test_authorities(monkeypatch, removed, replacement)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert not report.reconciliation_safe
    assert report.partial
    assert [item.status for item in report.items] == ["ready", "error"]
    assert report.items[1].error_type == "remote_drift"
    assert client.upserts == 1
    assert event_id in client.events


def test_removed_event_semantic_recheck_blocks_mutation_time_drift(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("removed-mutation-semantic-drift", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    replacement = _authoritative(
        _targetless_run("replacement-before-mutation-drift", date(2026, 8, 9))
    )
    service.workouts = [replacement]
    _retain_test_authorities(monkeypatch, removed, replacement)
    reconcile_verified_status = service._reconcile_status

    def remove_semantics_after_status(status, **kwargs):
        client.events[event_id] = client.events[event_id].model_copy(update={"workout_doc": None})
        return reconcile_verified_status(status, **kwargs)

    monkeypatch.setattr(service, "_reconcile_status", remove_semantics_after_status)

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert not report.reconciliation_safe
    assert report.partial
    assert [item.status for item in report.items] == ["created", "error"]
    assert report.items[1].error_type == "remote_drift"
    assert event_id in client.events


def test_published_retirement_fresh_read_follows_semantic_provider_calls(
    tmp_path,
    monkeypatch,
) -> None:
    class SemanticRaceClient(FakeClient):
        race_enabled = False
        athlete_reads = 0
        target_event_id = None

        def get_athlete(self):
            athlete = super().get_athlete()
            if self.race_enabled:
                self.athlete_reads += 1
                if self.athlete_reads == 3:
                    assert self.target_event_id is not None
                    self.events[self.target_event_id] = self.events[
                        self.target_event_id
                    ].model_copy(
                        update={"description": "Athlete changed the event during validation."}
                    )
            return athlete

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = SemanticRaceClient()
    workout = _authoritative(_targetless_run("published-delete-race", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.target_event_id = event_id
    client.race_enabled = True

    with pytest.raises(RemoteWorkoutDriftError, match="immediately before"):
        service.retirement_service.retire_published(
            workout.identity.local_workout_id,
            authoritative_workout=workout,
            provider_name=provider_workout_names([workout.prescription])[
                workout.identity.local_workout_id
            ],
        )

    assert event_id in client.events


def test_pending_retirement_fresh_read_follows_semantic_provider_calls(
    tmp_path,
    monkeypatch,
) -> None:
    class SemanticRaceClient(FakeClient):
        lose_next_response = True
        race_enabled = False
        athlete_reads = 0
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

        def get_athlete(self):
            athlete = super().get_athlete()
            if self.race_enabled:
                self.athlete_reads += 1
                if self.athlete_reads == 3:
                    assert self.target_event_id is not None
                    self.events[self.target_event_id] = self.events[
                        self.target_event_id
                    ].model_copy(
                        update={"description": "Athlete changed the event during validation."}
                    )
            return athlete

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = SemanticRaceClient()
    workout = _authoritative(_targetless_run("pending-delete-race", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 2)).partial
    event_id = next(iter(client.events))
    client.target_event_id = event_id
    client.race_enabled = True

    with pytest.raises(RemoteWorkoutDriftError, match="immediately before"):
        service.retirement_service.retire_published(
            workout.identity.local_workout_id,
            authoritative_workout=workout,
            provider_name=provider_workout_names([workout.prescription])[
                workout.identity.local_workout_id
            ],
        )

    assert event_id in client.events


def test_future_pending_retirement_accepts_a_provider_rewritten_uid(
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
    workout = _authoritative(_targetless_run("pending-server-uid", date(2026, 8, 14)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))

    retired = service.retirement_service.retire_published(
        workout.identity.local_workout_id,
        authoritative_workout=workout,
        provider_name=provider_workout_names([workout.prescription])[
            workout.identity.local_workout_id
        ],
        as_of_date=date(2026, 8, 10),
    )

    assert retired.action == "deleted"
    assert retired.event_id == event_id
    assert retired.uid == "server-assigned-uid"
    assert client.events == {}


def test_removed_future_workout_moved_past_with_content_change_is_drift(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("past-edited-drag", date(2026, 8, 7)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-03T00:00:00",
            "description": "Athlete changed this past workout's content.",
        }
    )
    service.workouts = [
        _authoritative(_targetless_run("replacement-after-past-edit", date(2026, 8, 9)))
    ]

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 4))

    assert not report.reconciliation_safe
    assert report.partial
    assert [item.status for item in report.items] == ["ready", "error"]
    assert report.items[1].error_type == "remote_drift"
    assert client.upserts == 1
    assert event_id in client.events


def test_replacement_deletes_revoked_late_placement_still_on_current_day(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    original = _authoritative(_targetless_run("late-stale", date(2026, 8, 10)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_late_stale",
        execution_date=date(2026, 8, 11),
    )
    client.activities["i_act_late_stale"] = ActivityDTO(
        id="i_act_late_stale",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 11, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 11, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            fulfillments={
                "act_late_stale": _confirmed_fulfillment(
                    original,
                    local_activity_id="act_late_stale",
                    execution_date=date(2026, 8, 11),
                    activity_performance_sha256=activity_sha256,
                )
            }
        ),
    )
    assert not service.reconcile_week(1, as_of_date=date(2026, 8, 11)).partial

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id="act_late_stale",
        local_workout_id="late-stale",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete clarified that this run was not the workout.",
        revoked_at_utc=_after_latest_publication_verification(repo, "late-stale"),
    )
    service.workouts = [_authoritative(_targetless_run("replacement-run", date(2026, 8, 15)))]
    replacement = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert not replacement.partial
    assert [item.status for item in replacement.items] == ["created", "deleted"]
    assert event_id not in client.events
    assert "late-stale" not in load_manifest(repo).workouts


def test_removed_dual_state_retires_the_exact_remote_pending_revision(
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
    original = _authoritative(_targetless_run("stale-dual", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the exact interrupted pending revision."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.interrupt_next_upsert = True
    interrupted = service.reconcile_week(1, as_of_date=date(2026, 8, 9))
    assert interrupted.partial
    assert set(load_manifest(repo).workouts) == {"stale-dual"}
    assert set(load_manifest(repo).pending) == {"stale-dual"}

    replacement = _authoritative(_targetless_run("replacement-after-dual", date(2026, 8, 12)))
    service.workouts = [replacement]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            "stale-dual": RetainedPublicationAuthorities(
                published=RetainedPublicationAuthority(
                    workout=original,
                    provider_name=provider_workout_names([original.prescription])["stale-dual"],
                ),
                pending=RetainedPublicationAuthority(
                    workout=revised,
                    provider_name=provider_workout_names([revised.prescription])["stale-dual"],
                ),
            )
        },
    )

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 9))

    assert not reconciled.partial, [
        (item.status, item.error_type, item.message) for item in reconciled.items
    ]
    assert [item.status for item in reconciled.items] == ["created", "deleted"]
    assert event_id not in client.events


def test_revoked_pending_only_execution_placement_is_deleted_after_replacement(
    tmp_path,
    monkeypatch,
) -> None:
    class InterruptedCreateClient(FakeClient):
        interrupt_next_upsert = False

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
    fulfilled = _authoritative(_targetless_run("pending-placed", date(2026, 8, 11)))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_pending_placed",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = _confirmed_fulfillment(
        fulfilled,
        local_activity_id="act_pending_placed",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_pending_placed": fulfillment}),
    )
    service = HarnessRunWeekSynchronizationService(repo, client, [fulfilled])
    client.interrupt_next_upsert = True

    interrupted = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert interrupted.partial
    pending_manifest = load_manifest(repo)
    assert pending_manifest.workouts == {}
    pending = pending_manifest.pending["pending-placed"]
    assert pending.occurrence_date == date(2026, 8, 11)
    assert pending.provider_start_date_local == "2026-08-10T00:00:00"
    assert next(iter(client.events.values())).start_date_local == ("2026-08-10T00:00:00")

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id="act_pending_placed",
        local_workout_id="pending-placed",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete clarified that this was not the workout.",
        revoked_at_utc=datetime(2026, 8, 10, 12, tzinfo=timezone.utc),
    )
    replacement = _authoritative(_targetless_run("replacement-after-pending", date(2026, 8, 15)))
    service.workouts = [replacement]
    pending_provider_name = provider_workout_names([fulfilled.prescription])[
        fulfilled.identity.local_workout_id
    ]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            fulfilled.identity.local_workout_id: RetainedPublicationAuthorities(
                pending=RetainedPublicationAuthority(
                    workout=fulfilled,
                    provider_name=pending_provider_name,
                )
            )
        },
    )
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not reconciled.partial, [
        (item.status, item.error_type, item.message) for item in reconciled.items
    ]
    assert [item.status for item in reconciled.items] == ["created", "deleted"]
    assert reconciled.items[1].occurrence_date == date(2026, 8, 11)
    assert reconciled.items[1].provider_occurrence_date == date(2026, 8, 10)
    assert set(client.events) == {reconciled.items[0].event_id}
    assert set(load_manifest(repo).pending) == {"pending-placed"}
    assert len(load_publication_deletion_manifest(repo).operations) == 1


@pytest.mark.parametrize(
    ("as_of_date", "expected_status", "event_remains"),
    [
        (date(2026, 8, 9), "deleted", False),
        (date(2026, 8, 12), "updated", True),
    ],
)
def test_renderer_evolution_stale_pending_can_be_confirmed_and_reconciled(
    tmp_path,
    monkeypatch,
    as_of_date: date,
    expected_status: str,
    event_remains: bool,
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
    stale = _authoritative(_pace_targeted_run("renderer-stale", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [stale])
    current_renderer = preparation_module.render_structured_workout

    def legacy_renderer(steps):
        return current_renderer(steps).replace(" Pace", "")

    monkeypatch.setattr(preparation_module, "render_structured_workout", legacy_renderer)
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    stale_event_id = next(iter(client.events))

    monkeypatch.setattr(
        preparation_module,
        "render_structured_workout",
        current_renderer,
    )
    replacement = _authoritative(
        _targetless_run("replacement-after-renderer", date(2026, 8, 12))
    )
    service.workouts = [replacement]
    stale_provider_name = provider_workout_names([stale.prescription])[
        stale.identity.local_workout_id
    ]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            stale.identity.local_workout_id: RetainedPublicationAuthorities(
                pending=RetainedPublicationAuthority(
                    workout=stale,
                    provider_name=stale_provider_name,
                )
            )
        },
    )

    status = service.status_week(1, as_of_date=as_of_date)
    stale_status = next(
        item for item in status.items if item.local_workout_id == stale.identity.local_workout_id
    )

    assert not status.reconciliation_safe
    assert stale_status.error_type == "remote_drift"
    assert stale_status.drift_resolution_token_sha256 is not None

    restored = service.restore_local_week(
        1,
        as_of_date=as_of_date,
        athlete_confirmation_reference=(
            "Athlete confirmed retiring the exact stale malformed workout."
        ),
        confirmed_drift_target_tokens=[stale_status.drift_resolution_token_sha256],
    )

    assert restored.reconciliation_safe
    stale_result = next(
        item for item in restored.items if item.local_workout_id == stale.identity.local_workout_id
    )
    assert stale_result.status == expected_status
    assert (stale_event_id in client.events) is event_remains
    manifest = load_manifest(repo)
    if event_remains:
        assert stale.identity.local_workout_id in manifest.workouts
        assert stale.identity.local_workout_id not in manifest.pending
        corrected_description = client.events[stale_event_id].description or ""
        assert " Pace" in corrected_description
    else:
        assert stale.identity.local_workout_id in manifest.pending
        deletion_operations = load_publication_deletion_manifest(repo).operations.values()
        assert any(
            operation.pending_publication.workout_identity.local_workout_id
            == stale.identity.local_workout_id
            and operation.state == "monitoring"
            for operation in deletion_operations
        )


@pytest.mark.parametrize("unsupported_legacy_shape", ["fractional_pace", "nested_repeat"])
@pytest.mark.parametrize(
    "reconciliation_date",
    [
        date(2026, 8, 9),
        date(2026, 8, 12),
    ],
)
def test_unsupported_legacy_pending_has_safe_temporal_reconciliation(
    tmp_path,
    monkeypatch,
    unsupported_legacy_shape: str,
    reconciliation_date: date,
) -> None:
    class InterruptedCreateClient(FakeClient):
        interrupt_next_upsert = True
        omit_listed_events = False

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.interrupt_next_upsert:
                self.interrupt_next_upsert = False
                raise IntervalsTransportError(
                    "create response was lost",
                    operation="upsert_event",
                )
            return stored

        def list_events(self, oldest, newest, *, athlete_id=None):
            if self.omit_listed_events:
                return []
            return super().list_events(oldest, newest, athlete_id=athlete_id)

    payload = _pace_targeted_run("unsupported-legacy", date(2026, 8, 11)).model_dump(
        mode="json"
    )
    if unsupported_legacy_shape == "fractional_pace":
        target = payload["structured_workout"]["steps"][0]["target"]
        target["minimum"] = 330.4
        target["maximum"] = 360.4
    else:
        steady_step = payload["structured_workout"]["steps"][0]
        payload["structured_workout"]["steps"] = [
            {
                "kind": "repeat",
                "repetitions": 2,
                "steps": [
                    {
                        "kind": "repeat",
                        "repetitions": 2,
                        "steps": [steady_step],
                    }
                ],
            }
        ]
        payload["planned_duration_seconds"] = 2_400
        payload["planned_low_intensity_duration_seconds"] = 2_400
    stale = _authoritative(RunningWorkoutPrescription.model_validate(payload))

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedCreateClient()
    service = HarnessRunWeekSynchronizationService(repo, client, [stale])
    current_renderer = preparation_module.render_structured_workout
    monkeypatch.setattr(
        preparation_module,
        "render_structured_workout",
        lambda _steps: "- Legacy workout 10m 5:30-6:00/km Pace intensity=active",
    )
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    stale_event_id = next(iter(client.events))

    monkeypatch.setattr(preparation_module, "render_structured_workout", current_renderer)
    service.workouts = [
        _authoritative(_targetless_run("replacement-after-unsupported", date(2026, 8, 12)))
    ]
    provider_name = provider_workout_names([stale.prescription])[
        stale.identity.local_workout_id
    ]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            stale.identity.local_workout_id: RetainedPublicationAuthorities(
                pending=RetainedPublicationAuthority(
                    workout=stale,
                    provider_name=provider_name,
                )
            )
        },
    )

    future_status = service.status_week(1, as_of_date=date(2026, 8, 9))
    future_stale_status = next(
        item
        for item in future_status.items
        if item.local_workout_id == stale.identity.local_workout_id
    )
    assert future_stale_status.error_type == "remote_drift"
    assert future_stale_status.drift_resolution_token_sha256 is not None

    if reconciliation_date > stale.prescription.date:
        client.omit_listed_events = True
        past_status = service.status_week(1, as_of_date=reconciliation_date)
        past_stale_status = next(
            item
            for item in past_status.items
            if item.local_workout_id == stale.identity.local_workout_id
        )
        assert past_stale_status.error_type == "publication_safety"
        assert past_stale_status.drift_resolution_token_sha256 is None

    restored = service.restore_local_week(
        1,
        as_of_date=reconciliation_date,
        athlete_confirmation_reference=(
            "Athlete confirmed retiring the exact unsupported legacy workout."
        ),
        confirmed_drift_target_tokens=[future_stale_status.drift_resolution_token_sha256],
    )

    if reconciliation_date > stale.prescription.date:
        stale_result = next(
            item
            for item in restored.items
            if item.local_workout_id == stale.identity.local_workout_id
        )
        assert restored.partial
        assert stale_result.error_type == "publication_safety"
        assert stale_event_id in client.events
        assert stale.identity.local_workout_id in load_manifest(repo).pending
        assert load_publication_deletion_manifest(repo).operations == {}
        client.omit_listed_events = False
        rediscovered_status = service.status_week(1, as_of_date=reconciliation_date)
        rediscovered_stale_status = next(
            item
            for item in rediscovered_status.items
            if item.local_workout_id == stale.identity.local_workout_id
        )
        assert rediscovered_stale_status.error_type == "publication_safety"
        assert rediscovered_stale_status.drift_resolution_token_sha256 is None
    else:
        assert restored.reconciliation_safe
        assert stale_event_id not in client.events


def test_renderer_superseded_pending_rejects_non_deterministic_identity(
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
    stale = _authoritative(_targetless_run("identity-stale", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [stale])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    stale_event_id = next(iter(client.events))

    corrupt_local_workout_id = "different-owned-workout"
    corrupt_external_id = external_id_for(corrupt_local_workout_id)
    corrupt_uid = uid_for(corrupt_local_workout_id)
    manifest = load_manifest(repo)
    manifest.pending[stale.identity.local_workout_id] = manifest.pending[
        stale.identity.local_workout_id
    ].model_copy(
        update={
            "external_id": corrupt_external_id,
            "uid": corrupt_uid,
        }
    )
    save_manifest(repo, manifest)
    client.events[stale_event_id] = client.events[stale_event_id].model_copy(
        update={
            "external_id": corrupt_external_id,
            "uid": corrupt_uid,
        }
    )
    service.workouts = [
        _authoritative(_targetless_run("replacement-after-corrupt", date(2026, 8, 12)))
    ]
    provider_name = provider_workout_names([stale.prescription])[
        stale.identity.local_workout_id
    ]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            stale.identity.local_workout_id: RetainedPublicationAuthorities(
                pending=RetainedPublicationAuthority(
                    workout=stale,
                    provider_name=provider_name,
                )
            )
        },
    )

    status = service.status_week(1, as_of_date=date(2026, 8, 9))
    stale_status = next(
        item for item in status.items if item.local_workout_id == stale.identity.local_workout_id
    )

    assert stale_status.error_type == "publication_safety"
    assert stale_status.drift_resolution_token_sha256 is None
    assert stale_event_id in client.events


def test_revoked_pending_provider_pair_is_unpaired_after_exact_recovery(
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
    workout = _authoritative(_targetless_run("revoked-pending-pair", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="revoked_pending_pair_activity",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_revoked_pending_pair_activity"] = ActivityDTO(
        id="i_revoked_pending_pair_activity",
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
        local_activity_id="revoked_pending_pair_activity",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id=fulfillment.local_activity_id,
        local_workout_id=workout.identity.local_workout_id,
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete revoked the exact association.",
        coaching_rationale="The completed activity did not fulfill this workout.",
        revoked_at_utc=datetime(2026, 8, 10, 12, tzinfo=timezone.utc),
    )
    operation = next(iter(load_fulfillment_manifest(repo).remote_pairing_operations.values()))
    assert operation.action == "unpair"
    assert operation.publication_provider_event_fingerprint_sha256 is None

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert reconciled.reconciliation_safe, reconciled.model_dump(mode="json")
    assert [item.status for item in reconciled.items] == ["recovered"]
    assert reconciled.items[0].remote_pairing_status == "unpaired"
    assert client.activities["i_revoked_pending_pair_activity"].paired_event_id is None
    assert load_manifest(repo).workouts["revoked-pending-pair"].event_id == event_id


def test_stale_deletion_accepts_exact_pending_remote_bytes_from_interrupted_update(
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
    original = _authoritative(_targetless_run("stale-recovery", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the pending crash-recovery prescription."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.interrupt_next_upsert = True

    interrupted = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert interrupted.partial
    assert set(load_manifest(repo).workouts) == {"stale-recovery"}
    assert set(load_manifest(repo).pending) == {"stale-recovery"}

    provider_name = provider_workout_names([revised.prescription])["stale-recovery"]
    service.retirement_service.verify(
        "stale-recovery",
        restore_local=False,
        authoritative_workout=revised,
        provider_name=provider_name,
    )
    deleted = service.retirement_service.retire_published(
        "stale-recovery",
        authoritative_workout=revised,
        provider_name=provider_name,
    )

    assert deleted.action == "deleted"
    assert event_id not in client.events
    assert load_manifest(repo).workouts == {}
    assert set(load_manifest(repo).pending) == {"stale-recovery"}
    assert len(load_publication_deletion_manifest(repo).operations) == 1


def test_ambiguous_desired_create_retries_after_its_scheduled_date(
    tmp_path,
    monkeypatch,
) -> None:
    class InitiallyAmbiguousClient(FakeClient):
        ambiguous = True
        lost_event = None

        def upsert_event(self, event, *, athlete_id=None):
            if self.ambiguous:
                self.ambiguous = False
                self.lost_event = event
                raise IntervalsTransportError(
                    "create outcome is unknown",
                    operation="upsert_event",
                )
            return super().upsert_event(event, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InitiallyAmbiguousClient()
    workout = _authoritative(_targetless_run("past-pending", date(2026, 8, 10)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])

    assert service.reconcile_week(1, as_of_date=date(2026, 8, 10)).partial
    assert set(load_manifest(repo).pending) == {"past-pending"}

    retried = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert not retried.partial
    assert [item.status for item in retried.items] == ["created"]
    assert load_manifest(repo).pending == {}
    assert set(load_manifest(repo).workouts) == {"past-pending"}


def test_replacement_tombstones_a_removed_past_pending_intent(
    tmp_path,
    monkeypatch,
) -> None:
    class InitiallyAmbiguousClient(FakeClient):
        ambiguous = True
        lost_event = None

        def upsert_event(self, event, *, athlete_id=None):
            if self.ambiguous:
                self.ambiguous = False
                self.lost_event = event
                raise IntervalsTransportError(
                    "create outcome is unknown",
                    operation="upsert_event",
                )
            return super().upsert_event(event, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InitiallyAmbiguousClient()
    removed = _authoritative(_targetless_run("removed-past", date(2026, 8, 10)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])

    assert service.reconcile_week(1, as_of_date=date(2026, 8, 10)).partial
    assert set(load_manifest(repo).pending) == {"removed-past"}

    replacement = _authoritative(_targetless_run("replacement-run", date(2026, 8, 12)))
    service.workouts = [replacement]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            removed.identity.local_workout_id: RetainedPublicationAuthorities(
                published=RetainedPublicationAuthority(
                    workout=removed,
                    provider_name=provider_workout_names([removed.prescription])[
                        removed.identity.local_workout_id
                    ],
                ),
                pending=RetainedPublicationAuthority(
                    workout=removed,
                    provider_name=provider_workout_names([removed.prescription])[
                        removed.identity.local_workout_id
                    ],
                ),
            )
        },
    )
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert not reconciled.partial, reconciled.model_dump(mode="json")
    assert [item.status for item in reconciled.items] == [
        "created",
        "deletion_monitoring",
    ]
    assert set(load_manifest(repo).pending) == {"removed-past"}
    deletion_manifest = load_publication_deletion_manifest(repo)
    operation = next(iter(deletion_manifest.operations.values()))
    assert operation.pending_publication.workout_identity == removed.identity
    assert operation.state == "monitoring"
    assert client.lost_event is not None
    late_event_id = FakeClient.upsert_event(client, client.lost_event).id

    week_status = service.status_week(1, as_of_date=date(2026, 8, 11))
    week_first = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert week_status.reconciliation_safe, week_status.model_dump(mode="json")
    assert [item.status for item in week_status.items] == ["ready"]
    assert week_first.reconciliation_safe, week_first.model_dump(mode="json")
    assert [item.status for item in week_first.items] == ["noop"]
    assert late_event_id in client.events
    assert set(load_manifest(repo).pending) == {"removed-past"}
    reaper = reconcile_publication_deletion_operations(repo, client)
    assert [item.status for item in reaper.items] == ["deleted"]
    assert late_event_id not in client.events


def test_materialized_pending_dragged_to_past_is_recovered_and_preserved(
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
    removed = _authoritative(_targetless_run("past-pending-drag", date(2026, 8, 14)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    old_event_id = next(iter(client.events))
    client.events[old_event_id] = client.events[old_event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    replacement = _authoritative(
        _targetless_run("replacement-after-pending-drag", date(2026, 8, 15))
    )
    service.workouts = [replacement]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            removed.identity.local_workout_id: RetainedPublicationAuthorities(
                published=RetainedPublicationAuthority(
                    workout=removed,
                    provider_name=provider_workout_names([removed.prescription])[
                        removed.identity.local_workout_id
                    ],
                ),
                pending=RetainedPublicationAuthority(
                    workout=removed,
                    provider_name=provider_workout_names([removed.prescription])[
                        removed.identity.local_workout_id
                    ],
                ),
            )
        },
    )

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert reconciled.reconciliation_safe, reconciled.model_dump(mode="json")
    assert [item.status for item in reconciled.items] == ["created", "skipped_past"]
    manifest = load_manifest(repo)
    assert "past-pending-drag" in manifest.workouts
    assert "past-pending-drag" not in manifest.pending
    placement = manifest.workout_provider_occurrence_placements["past-pending-drag"]
    assert placement.calendar_source == "provider_calendar"
    assert placement.calendar_occurrence_date == date(2026, 8, 10)
    assert load_publication_deletion_manifest(repo).operations == {}
    assert reconcile_publication_deletion_operations(repo, client).items == []
    assert old_event_id in client.events


def test_edited_materialized_pending_dragged_to_past_remains_drift(
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
    removed = _authoritative(_targetless_run("edited-pending-drag", date(2026, 8, 14)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    old_event_id = next(iter(client.events))
    client.events[old_event_id] = client.events[old_event_id].model_copy(
        update={
            "start_date_local": "2026-08-10T00:00:00",
            "description": "Athlete edited the pending workout.",
        }
    )
    service.workouts = [
        _authoritative(_targetless_run("replacement-after-edit", date(2026, 8, 15)))
    ]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            removed.identity.local_workout_id: RetainedPublicationAuthorities(
                pending=RetainedPublicationAuthority(
                    workout=removed,
                    provider_name=provider_workout_names([removed.prescription])[
                        removed.identity.local_workout_id
                    ],
                )
            )
        },
    )

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert not blocked.reconciliation_safe
    assert blocked.items[-1].error_type == "remote_drift"
    assert client.upserts == 1
    assert old_event_id in client.events


def test_confirmed_past_pending_drift_restores_intent_and_converges(
    tmp_path,
    monkeypatch,
) -> None:
    class LostCreateResponseClient(FakeClient):
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
    client = LostCreateResponseClient()
    removed = _authoritative(_targetless_run("restore-pending", date(2026, 8, 14)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    expected_description = client.events[event_id].description
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-10T00:00:00",
            "description": "Athlete accidentally changed the pending workout.",
        }
    )
    replacement = _authoritative(
        _targetless_run("replacement-after-pending-restore", date(2026, 8, 15))
    )
    service.workouts = [replacement]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            removed.identity.local_workout_id: RetainedPublicationAuthorities(
                published=RetainedPublicationAuthority(
                    workout=removed,
                    provider_name=provider_workout_names([removed.prescription])[
                        removed.identity.local_workout_id
                    ],
                ),
                pending=RetainedPublicationAuthority(
                    workout=removed,
                    provider_name=provider_workout_names([removed.prescription])[
                        removed.identity.local_workout_id
                    ],
                ),
            )
        },
    )
    status = service.status_week(1, as_of_date=date(2026, 8, 11))
    token = status.items[-1].drift_resolution_token_sha256
    assert token is not None

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 11),
        athlete_confirmation_reference=(
            "Athlete confirmed restoring this exact pending workout target."
        ),
        confirmed_drift_target_tokens=[token],
    )
    repeated = service.status_week(1, as_of_date=date(2026, 8, 11))

    assert restored.reconciliation_safe, restored.model_dump(mode="json")
    assert [item.status for item in restored.items] == ["created", "updated"]
    assert client.events[event_id].description == expected_description
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    assert repeated.reconciliation_safe, repeated.model_dump(mode="json")
    assert repeated.items[-1].status == "skipped_past"
    manifest = load_manifest(repo)
    assert "restore-pending" in manifest.workouts
    assert "restore-pending" not in manifest.pending
    assert manifest.workouts["restore-pending"].requested_uid == uid_for("restore-pending")
    assert manifest.workouts["restore-pending"].uid == "server-assigned-uid"


def test_materialized_past_pending_update_replaces_prior_record_without_tombstone(
    tmp_path,
    monkeypatch,
) -> None:
    class LostUpdateResponseClient(FakeClient):
        lose_next_update = False

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.lose_next_update:
                self.lose_next_update = False
                raise IntervalsTransportError(
                    "update response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = LostUpdateResponseClient()
    original = _authoritative(_targetless_run("past-materialized-update", date(2026, 8, 10)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    old_event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    assert old_event_id is not None
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the materialized revised workout."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.lose_next_update = True
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    replacement = _authoritative(
        _targetless_run("replacement-after-materialized-update", date(2026, 8, 12))
    )
    service.workouts = [replacement]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            original.identity.local_workout_id: RetainedPublicationAuthorities(
                published=RetainedPublicationAuthority(
                    workout=original,
                    provider_name=provider_workout_names([original.prescription])[
                        original.identity.local_workout_id
                    ],
                ),
                pending=RetainedPublicationAuthority(
                    workout=revised,
                    provider_name=provider_workout_names([revised.prescription])[
                        revised.identity.local_workout_id
                    ],
                ),
            )
        },
    )

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert reconciled.reconciliation_safe, reconciled.model_dump(mode="json")
    assert [item.status for item in reconciled.items] == ["created", "skipped_past"]
    manifest = load_manifest(repo)
    assert manifest.workouts["past-materialized-update"].workout_prescription_sha256 == (
        canonical_data_sha256(revised.prescription)
    )
    assert "past-materialized-update" not in manifest.pending
    assert load_publication_deletion_manifest(repo).operations == {}
    assert reconcile_publication_deletion_operations(repo, client).items == []
    assert old_event_id in client.events


def test_dual_state_deletion_reaps_an_update_that_materializes_late(
    tmp_path,
    monkeypatch,
) -> None:
    class DelayedUpdateClient(FakeClient):
        delay_next_upsert = False
        delayed_event = None

        def upsert_event(self, event, *, athlete_id=None):
            if self.delay_next_upsert:
                self.delay_next_upsert = False
                self.delayed_event = event
                raise IntervalsTransportError(
                    "update outcome is unknown",
                    operation="upsert_event",
                )
            return super().upsert_event(event, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = DelayedUpdateClient()
    original = _authoritative(_targetless_run("late-update", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    old_event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the delayed update prescription."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.delay_next_upsert = True

    assert service.reconcile_week(1, as_of_date=date(2026, 8, 10)).partial
    assert set(load_manifest(repo).workouts) == {"late-update"}
    assert set(load_manifest(repo).pending) == {"late-update"}

    manifest = load_manifest(repo)
    assert original.prescription.structured_workout is not None
    assert revised.prescription.structured_workout is not None
    staged = stage_pending_publication_deletion(
        repo,
        manifest.pending["late-update"],
        previous=manifest.workouts["late-update"],
        pending_step_semantics_sha256=workout_semantics_sha256(
            expected_workout_semantics(revised.prescription.structured_workout.steps)
        ),
        previous_step_semantics_sha256=workout_semantics_sha256(
            expected_workout_semantics(original.prescription.structured_workout.steps)
        ),
    )
    assert staged.state == "staged"

    recovered = reconcile_publication_deletion_operations(repo, client)

    assert [(item.status, item.event_id) for item in recovered.items] == [("deleted", old_event_id)]
    assert old_event_id not in client.events
    assert load_manifest(repo).workouts == {}
    assert set(load_manifest(repo).pending) == {"late-update"}
    operation = next(iter(load_publication_deletion_manifest(repo).operations.values()))
    assert operation.state == "monitoring"

    repeated = service.retirement_service.retire_published(
        "late-update",
        authoritative_workout=revised,
        provider_name=provider_workout_names([revised.prescription])["late-update"],
    )
    assert repeated.action == "deletion_monitoring"
    assert len(load_publication_deletion_manifest(repo).operations) == 1

    assert client.delayed_event is not None
    late_event_id = FakeClient.upsert_event(client, client.delayed_event).id
    report = reconcile_publication_deletion_operations(repo, client)

    assert report.reconciliation_safe
    assert [(item.status, item.event_id) for item in report.items] == [("deleted", late_event_id)]
    assert client.events == {}


def test_legacy_staged_dual_tombstone_accepts_migrated_active_metadata(
    tmp_path,
    monkeypatch,
) -> None:
    class LostUpdateResponseClient(FakeClient):
        lose_next_update = False

        def upsert_event(self, event, *, athlete_id=None):
            stored = super().upsert_event(event, athlete_id=athlete_id)
            if self.lose_next_update:
                self.lose_next_update = False
                raise IntervalsTransportError(
                    "update response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = LostUpdateResponseClient()
    original = _authoritative(_targetless_run("legacy-dual", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    service.reconcile_week(1, as_of_date=date(2026, 8, 9))
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the revised exact prescription."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.lose_next_update = True
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 10)).partial
    manifest = load_manifest(repo)
    current_pending = manifest.pending["legacy-dual"]
    current_previous = manifest.workouts["legacy-dual"]
    assert current_pending.garmin_forwarding_eligible is not None
    assert current_previous.provider_step_semantics_sha256 is not None
    legacy_pending = current_pending.model_copy(update={"garmin_forwarding_eligible": None})
    legacy_previous = current_previous.model_copy(update={"provider_step_semantics_sha256": None})
    operation_id = publication_deletion_operation_id(
        legacy_pending,
        legacy_previous,
    )
    save_publication_deletion_manifest(
        repo,
        PublicationDeletionManifest(
            operations={
                operation_id: PendingPublicationDeletionOperation(
                    operation_id=operation_id,
                    pending_publication=legacy_pending,
                    previous_publication=legacy_previous,
                    requested_at_utc=datetime(2026, 8, 10, 9, tzinfo=timezone.utc),
                )
            }
        ),
    )

    assert_publication_deletion_integrity(repo)
    operation = next(iter(load_publication_deletion_manifest(repo).operations.values()))
    activate_publication_deletion_monitoring(
        repo,
        operation,
        monitored_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )

    migrated = load_manifest(repo)
    assert migrated.workouts == {}
    assert set(migrated.pending) == {"legacy-dual"}


def test_past_published_event_is_preserved_while_future_pending_update_is_monitored(
    tmp_path,
    monkeypatch,
) -> None:
    class DelayedUpdateClient(FakeClient):
        delay_next_upsert = False
        delayed_event = None
        hidden_event_ids: set[int] = set()

        def list_events(self, oldest, newest, *, athlete_id=None):
            return [
                event
                for event in super().list_events(
                    oldest,
                    newest,
                    athlete_id=athlete_id,
                )
                if event.id not in self.hidden_event_ids
            ]

        def upsert_event(self, event, *, athlete_id=None):
            if self.delay_next_upsert:
                self.delay_next_upsert = False
                self.delayed_event = event
                raise IntervalsTransportError(
                    "future update outcome is unknown",
                    operation="upsert_event",
                )
            return super().upsert_event(event, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = DelayedUpdateClient()
    original = _authoritative(_targetless_run("past-with-pending", date(2026, 8, 10)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    old_event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    assert old_event_id is not None
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={
                "date": date(2026, 8, 12),
                "purpose": "Use the delayed future prescription.",
            }
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.delay_next_upsert = True
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    replacement = _authoritative(_targetless_run("replacement-after-past", date(2026, 8, 13)))
    service.workouts = [replacement]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            "past-with-pending": RetainedPublicationAuthorities(
                published=RetainedPublicationAuthority(
                    workout=original,
                    provider_name=provider_workout_names([original.prescription])[
                        "past-with-pending"
                    ],
                ),
                pending=RetainedPublicationAuthority(
                    workout=revised,
                    provider_name=provider_workout_names([revised.prescription])[
                        "past-with-pending"
                    ],
                ),
            )
        },
    )

    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert not reconciled.partial, reconciled.model_dump(mode="json")
    assert [item.status for item in reconciled.items] == [
        "created",
        "skipped_past",
    ]
    assert old_event_id in client.events
    operation = next(iter(load_publication_deletion_manifest(repo).operations.values()))
    assert operation.state == "monitoring"
    assert operation.preserve_previous_publication
    assert client.delayed_event is not None
    monitoring = reconcile_publication_deletion_operations(repo, client)
    assert [(item.status, item.event_id) for item in monitoring.items] == [
        ("deletion_monitoring", None)
    ]
    assert monitoring.items[0].provider_occurrence_date == date(2026, 8, 10)
    assert old_event_id in client.events

    lost_target_token = "c" * 64
    deletion_manifest = load_publication_deletion_manifest(repo)
    deletion_manifest.drift_resolutions.append(
        PublicationDeletionDriftResolution(
            operation_id=operation.operation_id,
            event_id=999,
            observed_remote_fingerprint_sha256="d" * 64,
            drift_resolution_token_sha256=lost_target_token,
            athlete_confirmation_reference=(
                "Athlete confirmed the exact late target before it disappeared."
            ),
            confirmed_at_utc=operation.requested_at_utc,
        )
    )
    save_publication_deletion_manifest(repo, deletion_manifest)
    client.hidden_event_ids.add(old_event_id)
    lost_target = resolve_publication_deletion_drifts(
        repo,
        client,
        confirmed_drift_tokens=[lost_target_token],
        athlete_confirmation_reference=(
            "Athlete confirmed the exact late target before it disappeared."
        ),
    )
    client.hidden_event_ids.clear()

    assert lost_target.reconciliation_safe
    assert lost_target.items[0].status == "deletion_monitoring"
    assert lost_target.items[0].provider_occurrence_date == date(2026, 8, 10)

    client.events[old_event_id] = client.events[old_event_id].model_copy(
        update=client.delayed_event.model_dump(
            mode="python",
            exclude={"category", "id"},
        )
    )
    pending_remote = client.events[old_event_id]
    assert pending_remote.workout_doc is not None
    original_workout_doc = pending_remote.workout_doc
    first_step = original_workout_doc.steps[0]
    client.events[old_event_id] = pending_remote.model_copy(
        update={
            "workout_doc": original_workout_doc.model_copy(
                update={
                    "steps": [
                        first_step.model_copy(
                            update={"duration_seconds": first_step.duration_seconds + 1}
                        ),
                        *original_workout_doc.steps[1:],
                    ]
                }
            )
        }
    )
    blocked = reconcile_publication_deletion_operations(repo, client)
    assert blocked.partial
    assert blocked.items[0].error_type == "remote_drift"
    assert old_event_id in client.events
    drift_token = blocked.items[0].drift_resolution_token_sha256
    assert drift_token is not None
    reaped = resolve_publication_deletion_drifts(
        repo,
        client,
        confirmed_drift_tokens=[drift_token],
        athlete_confirmation_reference=(
            "Athlete confirmed deleting the exact changed obsolete workout."
        ),
    )

    assert reaped.reconciliation_safe
    assert [(item.status, item.event_id) for item in reaped.items] == [("deleted", old_event_id)]
    assert old_event_id not in client.events
    assert "past-with-pending" not in load_manifest(repo).workouts


def test_reaper_repairs_local_ownership_after_delete_save_interruption(
    tmp_path,
    monkeypatch,
) -> None:
    class DelayedUpdateClient(FakeClient):
        delay_next_upsert = False
        delayed_event = None

        def upsert_event(self, event, *, athlete_id=None):
            if self.delay_next_upsert:
                self.delay_next_upsert = False
                self.delayed_event = event
                raise IntervalsTransportError(
                    "future update outcome is unknown",
                    operation="upsert_event",
                )
            return super().upsert_event(event, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = DelayedUpdateClient()
    original = _authoritative(_targetless_run("delete-save-recovery", date(2026, 8, 10)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    old_event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    assert old_event_id is not None
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={
                "date": date(2026, 8, 12),
                "purpose": "Use the delayed future prescription.",
            }
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.delay_next_upsert = True
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    service.workouts = [
        _authoritative(_targetless_run("replacement-after-save-loss", date(2026, 8, 13)))
    ]
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _workouts: {
            original.identity.local_workout_id: RetainedPublicationAuthorities(
                published=RetainedPublicationAuthority(
                    workout=original,
                    provider_name=provider_workout_names([original.prescription])[
                        original.identity.local_workout_id
                    ],
                ),
                pending=RetainedPublicationAuthority(
                    workout=revised,
                    provider_name=provider_workout_names([revised.prescription])[
                        revised.identity.local_workout_id
                    ],
                ),
            )
        },
    )
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 11)).reconciliation_safe
    assert client.delayed_event is not None
    client.events[old_event_id] = client.events[old_event_id].model_copy(
        update=client.delayed_event.model_dump(
            mode="python",
            exclude={"category", "id"},
        )
    )
    real_save_manifest = deletion_recovery_module.save_manifest
    save_attempts = 0

    def interrupt_first_cleanup(*args, **kwargs):
        nonlocal save_attempts
        save_attempts += 1
        if save_attempts == 1:
            raise OSError("local save interrupted after provider deletion")
        return real_save_manifest(*args, **kwargs)

    monkeypatch.setattr(
        deletion_recovery_module,
        "save_manifest",
        interrupt_first_cleanup,
    )

    interrupted = reconcile_publication_deletion_operations(repo, client)
    assert interrupted.partial
    assert old_event_id not in client.events
    assert "delete-save-recovery" in load_manifest(repo).workouts

    recovered = reconcile_publication_deletion_operations(repo, client)

    assert recovered.reconciliation_safe
    assert [item.status for item in recovered.items] == ["deletion_monitoring"]
    assert "delete-save-recovery" not in load_manifest(repo).workouts


def test_stale_deletion_rejects_remote_bytes_matching_neither_published_nor_pending(
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
    original = _authoritative(_targetless_run("drifted-recovery", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the pending crash-recovery prescription."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]
    client.interrupt_next_upsert = True
    service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    client.events[event_id] = client.events[event_id].model_copy(
        update={"description": "Unowned third-state edit"}
    )
    provider_name = provider_workout_names([revised.prescription])["drifted-recovery"]

    with pytest.raises(PublicationSafetyError, match="neither published nor pending"):
        service.retirement_service.verify(
            "drifted-recovery",
            restore_local=False,
            authoritative_workout=revised,
            provider_name=provider_name,
        )

    assert event_id in client.events


def test_retained_approval_revision_still_preflights_a_removed_native_pair(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    original = _authoritative(_targetless_run("retained-pair", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_retained_pair",
        execution_date=date(2026, 8, 11),
    )
    client.activities["i_act_retained_pair"] = ActivityDTO(
        id="i_act_retained_pair",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 11, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 11, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
    )
    fulfillment = _confirmed_fulfillment(
        original,
        local_activity_id="act_retained_pair",
        execution_date=date(2026, 8, 11),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    paired = service.reconcile_week(1, as_of_date=date(2026, 8, 11))
    assert paired.items[0].remote_pairing_status == "paired"
    client.activities["i_act_retained_pair"] = client.activities["i_act_retained_pair"].model_copy(
        update={"paired_event_id": None}
    )
    retained_authority = AppliedWorkoutAuthority(
        applied_week_approval_id=original.applied_week_approval_id,
        applied_running_workouts_sha256=original.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(original.prescription),
        schedule_timezone=original.schedule_timezone,
        scheduled_local_date=original.prescription.date,
    )
    service.workouts = [
        replace(
            original,
            applied_week_approval_id="week_approval_2222222222222222",
            applied_running_workouts_sha256="2" * 64,
            applied_authority_history=(retained_authority,),
        )
    ]

    status = service.status_week(1, as_of_date=date(2026, 8, 11))

    assert not status.reconciliation_safe
    assert status.partial
    assert status.items[0].remote_pairing_status == "pairing_blocked"
    assert status.items[0].remote_pairing_blocker_code == ("resilio_requested_pair_removed")
    assert status.items[0].pairing_drift_token_sha256 is not None


def test_replacement_deletes_a_stale_future_run_when_current_runs_are_past(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    old = _authoritative(_targetless_run("old-future-run", date(2026, 8, 8)))
    service = HarnessRunWeekSynchronizationService(repo, client, [old])
    old_event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 2),
        )
        .items[0]
        .event_id
    )

    service.workouts = [_authoritative(_targetless_run("current-past-run", date(2026, 8, 3)))]
    replacement = service.reconcile_week(1, as_of_date=date(2026, 8, 6))

    assert [item.status for item in replacement.items] == ["skipped_past", "deleted"]
    assert old_event_id not in client.events


def test_stale_remote_drift_blocks_every_replacement_mutation(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    old = _authoritative(_targetless_run("old-run", date(2026, 8, 8)))
    service = HarnessRunWeekSynchronizationService(repo, client, [old])
    first = service.reconcile_week(1, as_of_date=date(2026, 8, 2))
    old_event_id = first.items[0].event_id
    client.events[old_event_id] = client.events[old_event_id].model_copy(
        update={"description": "Athlete edited this event in Intervals.icu"}
    )
    service.workouts = [_authoritative(_targetless_run("replacement-run", date(2026, 8, 8)))]

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 2))

    assert not blocked.reconciliation_safe
    assert client.upserts == 1
    assert old_event_id in client.events
    assert all(
        event.external_id != "resilio:v1:workout:replacement-run"
        for event in client.events.values()
    )


def test_exact_stale_deletion_drift_token_can_authorize_replacement(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    removed = _authoritative(_targetless_run("stale-confirmed", date(2026, 8, 8)))
    service = HarnessRunWeekSynchronizationService(repo, client, [removed])
    old_event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 2),
        )
        .items[0]
        .event_id
    )
    assert old_event_id is not None
    client.events[old_event_id] = client.events[old_event_id].model_copy(
        update={"description": "Athlete confirmed removing this changed event."}
    )
    replacement = _authoritative(
        _targetless_run("replacement-after-confirmation", date(2026, 8, 9))
    )
    service.workouts = [replacement]
    _retain_test_authorities(monkeypatch, removed, replacement)
    status = service.status_week(1, as_of_date=date(2026, 8, 4))
    stale_item = next(item for item in status.items if item.local_workout_id == "stale-confirmed")
    assert stale_item.drift_resolution_token_sha256 is not None

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 4),
        athlete_confirmation_reference=(
            "Athlete confirmed replacing the exact displayed stale event."
        ),
        confirmed_drift_target_tokens=[stale_item.drift_resolution_token_sha256],
    )

    assert restored.reconciliation_safe, restored.model_dump(mode="json")
    assert [item.status for item in restored.items] == ["created", "deleted"]
    assert old_event_id not in client.events


def test_stale_delete_failure_returns_a_typed_partial_report(
    tmp_path,
    monkeypatch,
) -> None:
    class DeleteFailureClient(FakeClient):
        fail_deletes = False

        def delete_event(self, event_id, *, athlete_id=None):
            if self.fail_deletes:
                raise IntervalsTransportError(
                    "provider unavailable",
                    operation="delete_event",
                )
            return super().delete_event(event_id, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = DeleteFailureClient()
    old = _authoritative(_targetless_run("old-run", date(2026, 8, 8)))
    service = HarnessRunWeekSynchronizationService(repo, client, [old])
    service.reconcile_week(1, as_of_date=date(2026, 8, 2))
    client.fail_deletes = True
    service.workouts = [_authoritative(_targetless_run("replacement-run", date(2026, 8, 8)))]

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 2))

    assert report.partial
    assert [item.status for item in report.items] == ["created", "error"]
    assert report.items[-1].error_type == "transport"


def test_replacement_preserves_a_completed_owned_run_on_the_current_date(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    completed = _authoritative(_targetless_run("completed-run", date(2026, 8, 6)))
    service = HarnessRunWeekSynchronizationService(repo, client, [completed])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 2)).items[0].event_id
    publication = load_manifest(repo).workouts["completed-run"]
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_completed",
        workout_identity=completed.identity,
        applied_week_approval_id=completed.applied_week_approval_id,
        applied_running_workouts_sha256=completed.applied_running_workouts_sha256,
        workout_prescription_sha256=publication.workout_prescription_sha256,
        activity_performance_evidence_sha256="3" * 64,
        schedule_timezone=completed.schedule_timezone,
        scheduled_local_date=date(2026, 8, 6),
        execution_local_date=date(2026, 8, 6),
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            event_id=event_id,
            provenance="provider_observed",
            observed_at_utc=datetime(2026, 8, 6, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 6, 10, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    service.workouts = [_authoritative(_targetless_run("replacement-run", date(2026, 8, 8)))]

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 6))

    assert [item.status for item in report.items] == ["created"]
    assert event_id in client.events
    assert "completed-run" in load_manifest(repo).workouts
