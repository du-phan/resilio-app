"""Focused workout placement lifecycle tests."""

from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from resilio.core.planning.adherence_evidence import (
    AppliedWorkoutAuthority,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.association_identity import (
    fulfillment_association_sha256,
)
from resilio.core.workout_fulfillment.remote_unpairing import (
    reconcile_actionable_unpair_operations,
)
from resilio.core.workout_fulfillment.repository import (
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.core.workout_fulfillment.service import WorkoutFulfillmentService
from resilio.core.workout_publication.authority_matching import (
    publication_record_matches_current_workout_authority,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.publication_deletions import (
    load_publication_deletion_manifest,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.integrations.intervals_icu.errors import IntervalsTransportError
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    FulfillmentActivityEvidenceRevision,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from tests.unit.run_publication_workflow_support import (
    HarnessRunWeekSynchronizationService,
    _after_latest_publication_verification,
    _authoritative,
    _confirmed_fulfillment,
    _provider_paired_fulfillment,
    _save_fulfillment_activity,
    _targetless_run,
)
from tests.unit.test_workout_publication import FakeClient


def test_early_confirmed_fulfillment_places_owned_event_on_execution_day_and_pairs(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("early-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_early",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_early",
        workout_identity=workout.identity,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        workout_prescription_sha256=canonical_data_sha256(workout.prescription),
        activity_performance_evidence_sha256=activity_evidence_sha256,
        schedule_timezone="Europe/Paris",
        scheduled_local_date=date(2026, 8, 11),
        execution_local_date=date(2026, 8, 10),
        schedule_offset_days=-1,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale="The conversational run fulfilled the approved easy-run intent.",
            confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_early": fulfillment}),
    )

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert [item.status for item in report.items] == ["updated"]
    assert report.items[0].occurrence_date == date(2026, 8, 11)
    assert report.items[0].provider_occurrence_date == date(2026, 8, 10)
    assert report.items[0].remote_pairing_status == "paired"
    assert client.activity_pairing_updates == [("i_act_early", event_id)]
    assert event_id in client.events
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    manifest = load_manifest(repo)
    assert "early-run" in manifest.workouts
    assert manifest.workouts["early-run"].occurrence_date == date(2026, 8, 11)
    assert manifest.workouts["early-run"].provider_start_date_local == "2026-08-10T00:00:00"
    assert manifest.historical_fulfillment_event_retirements == []

    repeated = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert [item.status for item in repeated.items] == ["noop"]
    assert repeated.items[0].provider_occurrence_date == date(2026, 8, 10)
    assert repeated.items[0].remote_pairing_status == "pairing_noop"
    assert client.upserts == 2
    assert client.activity_pairing_updates == [("i_act_early", event_id)]


def test_late_confirmed_fulfillment_places_owned_event_on_execution_day_and_pairs(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("late-run", date(2026, 8, 10)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_late",
        execution_date=date(2026, 8, 11),
    )
    client.activities["i_act_late"] = ActivityDTO(
        id="i_act_late",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 11, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 11, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
    )
    fulfillment = _confirmed_fulfillment(
        workout,
        local_activity_id="act_late",
        execution_date=date(2026, 8, 11),
        activity_performance_sha256=activity_evidence_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_late": fulfillment}),
    )

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert [item.status for item in report.items] == ["updated"]
    assert report.items[0].remote_pairing_status == "paired"
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"
    stored = load_manifest(repo).workouts["late-run"]
    assert stored.occurrence_date == date(2026, 8, 10)
    assert stored.provider_start_date_local == "2026-08-11T00:00:00"


def test_activity_evidence_revision_rebases_fulfillment_placement_then_revokes(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("corrected-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    original_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_corrected",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_act_corrected"] = ActivityDTO(
        id="i_act_corrected",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
        paired_event_id=event_id,
    )
    original = _provider_paired_fulfillment(
        workout,
        local_activity_id="act_corrected",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=original_sha256,
        event_id=event_id,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={original.local_activity_id: original}),
    )
    placed = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert not placed.partial
    paired = load_fulfillment_manifest(repo).fulfillments[original.local_activity_id]

    replacement_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_corrected",
        execution_date=date(2026, 8, 11),
    )
    client.activities["i_act_corrected"] = client.get_activity("i_act_corrected").model_copy(
        update={
            "start_date": datetime(2026, 8, 11, 5, tzinfo=timezone.utc),
            "start_date_local": datetime(2026, 8, 11, 7),
            "paired_event_id": event_id,
        }
    )
    revised = WorkoutFulfillmentRecord.model_validate(
        {
            **paired.model_dump(mode="python"),
            "activity_performance_evidence_sha256": replacement_sha256,
            "execution_local_date": date(2026, 8, 11),
            "schedule_offset_days": 0,
            "activity_evidence_revisions": [
                FulfillmentActivityEvidenceRevision(
                    previous_activity_performance_evidence_sha256=original_sha256,
                    replacement_activity_performance_evidence_sha256=(replacement_sha256),
                    previous_execution_local_date=date(2026, 8, 10),
                    replacement_execution_local_date=date(2026, 8, 11),
                    observed_at_utc=datetime(2026, 8, 11, 8, tzinfo=timezone.utc),
                )
            ],
        }
    )
    assert fulfillment_association_sha256(revised) == (fulfillment_association_sha256(paired))
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={revised.local_activity_id: revised}),
    )

    rebased = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert not rebased.partial, [
        (item.status, item.error_type, item.message, item.remote_pairing_status)
        for item in rebased.items
    ]
    assert rebased.items[0].provider_occurrence_date == date(2026, 8, 11)
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"
    placement = load_manifest(repo).workout_provider_occurrence_placements["corrected-run"]
    assert placement.calendar_source == "approved_schedule"
    assert placement.fulfillment_override is not None
    assert placement.fulfillment_override.execution_local_date == date(2026, 8, 11)

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id="act_corrected",
        local_workout_id="corrected-run",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the corrected association.",
        coaching_rationale="The athlete clarified that this was not the workout.",
        revoked_at_utc=_after_latest_publication_verification(repo, "corrected-run"),
    )
    revoked = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert not revoked.partial
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"
    assert (
        load_manifest(repo)
        .workout_provider_occurrence_placements["corrected-run"]
        .fulfillment_override
        is None
    )


def test_revoked_early_fulfillment_restores_then_allows_a_new_manual_drag(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("revoked-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_revoked",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = _confirmed_fulfillment(
        workout,
        local_activity_id="act_revoked",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_evidence_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_revoked": fulfillment}),
    )
    placed = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert not placed.partial
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id="act_revoked",
        local_workout_id="revoked-run",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete clarified that this run was not the workout.",
        revoked_at_utc=datetime(2026, 8, 10, 12, tzinfo=timezone.utc),
    )
    restored = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not restored.partial
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"
    assert client.get_activity("i_act_revoked").paired_event_id is None
    assert load_manifest(repo).workouts["revoked-run"].occurrence_date == date(2026, 8, 11)

    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    adopted = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    repeated = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert [item.status for item in adopted.items] == ["recovered"]
    assert [item.status for item in repeated.items] == ["noop"]
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    assert client.upserts == 3


def test_revocation_preserves_an_earlier_independent_calendar_drag(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("drag-before-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    client.events[event_id] = client.events[event_id].model_copy(
        update={"start_date_local": "2026-08-10T00:00:00"}
    )
    adopted = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert [item.status for item in adopted.items] == ["recovered"]
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_drag_before_run",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = _confirmed_fulfillment(
        workout,
        local_activity_id="act_drag_before_run",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    paired = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert paired.items[0].remote_pairing_status == "paired"

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id="act_drag_before_run",
        local_workout_id="drag-before-run",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete clarified that this run was not the workout.",
        revoked_at_utc=_after_latest_publication_verification(
            repo,
            "drag-before-run",
        ),
    )
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not reconciled.partial
    assert [item.status for item in reconciled.items] == ["noop"]
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"


def test_verified_global_unpair_still_restores_revoked_execution_placement(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("reaper-first", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    assert event_id is not None
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_reaper_first",
        execution_date=date(2026, 8, 10),
    )
    client.activities["i_act_reaper_first"] = ActivityDTO(
        id="i_act_reaper_first",
        type="Run",
        name="Completed run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
    )
    fulfillment = _confirmed_fulfillment(
        workout,
        local_activity_id="act_reaper_first",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    placed = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert placed.items[0].remote_pairing_status == "paired"

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id="act_reaper_first",
        local_workout_id="reaper-first",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete clarified that this run was not the workout.",
        revoked_at_utc=_after_latest_publication_verification(repo, "reaper-first"),
    )
    unpaired = reconcile_actionable_unpair_operations(repo, client)

    assert [result.status for result in unpaired.results] == ["unpaired"]
    assert client.get_activity("i_act_reaper_first").paired_event_id is None
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"

    restored = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not restored.partial
    assert [item.status for item in restored.items] == ["updated"]
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"


def test_revoked_late_fulfillment_restores_past_owned_event_to_scheduled_day(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("revoked-late", date(2026, 8, 10)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_revoked_late",
        execution_date=date(2026, 8, 11),
    )
    client.activities["i_act_revoked_late"] = ActivityDTO(
        id="i_act_revoked_late",
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
                "act_revoked_late": _confirmed_fulfillment(
                    workout,
                    local_activity_id="act_revoked_late",
                    execution_date=date(2026, 8, 11),
                    activity_performance_sha256=activity_sha256,
                )
            }
        ),
    )
    placed = service.reconcile_week(1, as_of_date=date(2026, 8, 11))
    assert not placed.partial
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id="act_revoked_late",
        local_workout_id="revoked-late",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete clarified that this run was not the workout.",
        revoked_at_utc=_after_latest_publication_verification(repo, "revoked-late"),
    )
    restored = service.reconcile_week(1, as_of_date=date(2026, 8, 11))

    assert not restored.partial
    assert [item.status for item in restored.items] == ["updated"]
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    assert client.get_activity("i_act_revoked_late").paired_event_id is None


def test_stale_publication_converges_before_native_pairing(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    original = _authoritative(_targetless_run("updated-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the athlete-approved revised easy-run purpose."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_updated",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = _confirmed_fulfillment(
        revised,
        local_activity_id="act_updated",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_updated": fulfillment}),
    )
    service.workouts = [revised]

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert [item.status for item in report.items] == ["updated"]
    assert report.items[0].remote_pairing_status == "paired"
    assert client.activity_pairing_updates == [("i_act_updated", event_id)]
    stored = load_manifest(repo).workouts["updated-run"]
    assert stored.workout_prescription_sha256 == canonical_data_sha256(revised.prescription)


def test_dual_published_pending_recovery_converges_before_native_pairing(
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
    original = _authoritative(_targetless_run("recovery-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    revised = replace(
        original,
        prescription=original.prescription.model_copy(
            update={"purpose": "Use the approved crash-recovery prescription."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_recovery",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = _confirmed_fulfillment(
        revised,
        local_activity_id="act_recovery",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_recovery": fulfillment}),
    )
    service.workouts = [revised]
    client.interrupt_next_upsert = True

    interrupted = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    interrupted_manifest = load_manifest(repo)

    assert interrupted.partial
    assert "recovery-run" in interrupted_manifest.workouts
    assert "recovery-run" in interrupted_manifest.pending
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    assert (
        interrupted_manifest.pending["recovery-run"].provider_start_date_local
        == "2026-08-10T00:00:00"
    )

    recovered = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not recovered.partial
    assert recovered.items[0].remote_pairing_status == "paired"
    assert client.activity_pairing_updates == [("i_act_recovery", event_id)]
    assert "recovery-run" not in load_manifest(repo).pending
    assert (
        load_manifest(repo).workouts["recovery-run"].provider_start_date_local
        == "2026-08-10T00:00:00"
    )


def test_fulfillment_confirmation_after_interrupted_create_recovers_then_places(
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
    workout = _authoritative(_targetless_run("confirm-after-crash", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    client.interrupt_next_upsert = True

    interrupted = service.reconcile_week(1, as_of_date=date(2026, 8, 9))

    assert interrupted.partial
    assert load_manifest(repo).workouts == {}
    assert set(load_manifest(repo).pending) == {"confirm-after-crash"}
    event_id = next(iter(client.events))
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"

    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_confirm_after_crash",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = _confirmed_fulfillment(
        workout,
        local_activity_id="act_confirm_after_crash",
        execution_date=date(2026, 8, 10),
        activity_performance_sha256=activity_sha256,
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_confirm_after_crash": fulfillment}),
    )

    recovered = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not recovered.partial
    assert recovered.items[0].remote_pairing_status == "paired"
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    assert load_manifest(repo).pending == {}
    assert load_publication_deletion_manifest(repo).operations == {}


def test_revoked_pending_only_execution_placement_restores_current_workout(
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
    workout = _authoritative(_targetless_run("pending-current", date(2026, 8, 11)))
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_pending_current",
        execution_date=date(2026, 8, 10),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            fulfillments={
                "act_pending_current": _confirmed_fulfillment(
                    workout,
                    local_activity_id="act_pending_current",
                    execution_date=date(2026, 8, 10),
                    activity_performance_sha256=activity_sha256,
                )
            }
        ),
    )
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    interrupted = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert interrupted.partial
    event_id = next(iter(client.events))
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id="act_pending_current",
        local_workout_id="pending-current",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete clarified that this run was not the workout.",
        revoked_at_utc=datetime(2026, 8, 10, 12, tzinfo=timezone.utc),
    )
    restored = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not restored.partial
    assert [item.status for item in restored.items] == ["updated"]
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"
    assert load_manifest(repo).pending == {}


def test_pending_only_remote_drift_has_token_and_requires_exact_restore(
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
    workout = _authoritative(_targetless_run("pending-drift", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    interrupted = service.reconcile_week(1, as_of_date=date(2026, 8, 9))
    assert interrupted.partial
    event_id = next(iter(client.events))
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-14T00:00:00",
            "description": "Athlete edited this interrupted publication.",
        }
    )

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not blocked.reconciliation_safe
    assert client.upserts == 1
    assert blocked.items[0].error_type == "remote_drift"
    drift_token = blocked.items[0].drift_resolution_token_sha256
    assert drift_token is not None

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 10),
        confirmed_drift_target_tokens=[drift_token],
        athlete_confirmation_reference=(
            "Athlete confirmed restoring the exact interrupted publication."
        ),
    )

    assert not restored.partial
    assert client.upserts == 2
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"
    assert load_manifest(repo).pending == {}


def test_pending_only_remote_outside_authoritative_week_is_discovered_as_drift(
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
    workout = _authoritative(_targetless_run("pending-outside", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 9)).partial
    event_id = next(iter(client.events))
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-17T00:00:00",
            "description": "Athlete moved this event outside its training week.",
        }
    )

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not blocked.reconciliation_safe
    assert blocked.items[0].error_type == "remote_drift"
    assert blocked.items[0].drift_resolution_token_sha256 is not None
    assert client.upserts == 1
    assert client.events[event_id].start_date_local == "2026-08-17T00:00:00"
    assert client.events[event_id].description == (
        "Athlete moved this event outside its training week."
    )


def test_revoked_interrupted_placement_restores_confirmed_third_state_drift(
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
                    "placement response was lost",
                    operation="upsert_event",
                )
            return stored

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = InterruptedUpdateClient()
    workout = _authoritative(_targetless_run("dual-drift", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_dual_drift",
        execution_date=date(2026, 8, 10),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            fulfillments={
                "act_dual_drift": _confirmed_fulfillment(
                    workout,
                    local_activity_id="act_dual_drift",
                    execution_date=date(2026, 8, 10),
                    activity_performance_sha256=activity_sha256,
                )
            }
        ),
    )
    client.interrupt_next_upsert = True
    assert service.reconcile_week(1, as_of_date=date(2026, 8, 10)).partial
    assert set(load_manifest(repo).workouts) == {"dual-drift"}
    assert set(load_manifest(repo).pending) == {"dual-drift"}

    WorkoutFulfillmentService(repo).revoke(
        local_activity_id="act_dual_drift",
        local_workout_id="dual-drift",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete clarified that this run was not the workout.",
        revoked_at_utc=_after_latest_publication_verification(repo, "dual-drift"),
    )
    client.events[event_id] = client.events[event_id].model_copy(
        update={
            "start_date_local": "2026-08-14T00:00:00",
            "description": "Athlete edited this interrupted placement.",
        }
    )
    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    token = blocked.items[0].drift_resolution_token_sha256
    assert token is not None

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 10),
        confirmed_drift_target_tokens=[token],
        athlete_confirmation_reference=(
            "Athlete confirmed restoring the exact interrupted placement."
        ),
    )

    assert not restored.partial
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"
    assert load_manifest(repo).pending == {}


def test_publication_rejects_a_frankenstein_retained_authority_snapshot(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    original = _authoritative(_targetless_run("mixed-lineage", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [original])
    service.reconcile_week(1, as_of_date=date(2026, 8, 9))
    publication = load_manifest(repo).workouts["mixed-lineage"]
    mismatched_retained_authority = AppliedWorkoutAuthority(
        applied_week_approval_id=original.applied_week_approval_id,
        applied_running_workouts_sha256=original.applied_running_workouts_sha256,
        workout_prescription_sha256="f" * 64,
        schedule_timezone=original.schedule_timezone,
        scheduled_local_date=original.prescription.date,
    )
    current = replace(
        original,
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="2" * 64,
        applied_authority_history=(mismatched_retained_authority,),
    )

    assert not publication_record_matches_current_workout_authority(
        publication,
        current,
    )


def test_removed_native_pair_blocks_ordinary_reconcile_until_exact_resolution(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("drifted-pair", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    activity_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_pair_drift",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_pair_drift",
        workout_identity=workout.identity,
        applied_week_approval_id=workout.applied_week_approval_id,
        applied_running_workouts_sha256=workout.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(workout.prescription),
        activity_performance_evidence_sha256=activity_sha256,
        schedule_timezone=workout.schedule_timezone,
        scheduled_local_date=workout.prescription.date,
        execution_local_date=date(2026, 8, 10),
        schedule_offset_days=-1,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed this exact association.",
            coaching_rationale="The athlete identified this as the approved easy workout.",
            confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_pair_drift": fulfillment}),
    )
    paired = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert paired.items[0].remote_pairing_status == "paired"
    client.activities["i_act_pair_drift"] = client.activities["i_act_pair_drift"].model_copy(
        update={"paired_event_id": None}
    )

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not blocked.reconciliation_safe
    assert blocked.items[0].remote_pairing_blocker_code == ("resilio_requested_pair_removed")
    drift_token = blocked.items[0].pairing_drift_token_sha256
    assert drift_token is not None
    assert client.activity_pairing_updates == [("i_act_pair_drift", event_id)]

    original_pairing_projection = service._with_remote_pairing_status

    def interrupt_after_pairing_projection(report, *, workouts, mutate):
        projected = original_pairing_projection(
            report,
            workouts=workouts,
            mutate=mutate,
        )
        if mutate:
            raise KeyboardInterrupt("simulated interruption after durable pairing")
        return projected

    monkeypatch.setattr(
        service,
        "_with_remote_pairing_status",
        interrupt_after_pairing_projection,
    )
    with pytest.raises(KeyboardInterrupt, match="durable pairing"):
        service.resolve_pairing_drift_week(
            1,
            as_of_date=date(2026, 8, 10),
            athlete_confirmation_reference=(
                "Athlete confirmed restoring this exact removed native pair."
            ),
            confirmed_pairing_drift_tokens=[drift_token],
        )
    assert len(load_fulfillment_manifest(repo).remote_pairing_drift_resolutions) == 1

    assert client.activities["i_act_pair_drift"].paired_event_id == event_id
    monkeypatch.setattr(
        service,
        "_with_remote_pairing_status",
        original_pairing_projection,
    )
    resolved = service.resolve_pairing_drift_week(
        1,
        as_of_date=date(2026, 8, 10),
        athlete_confirmation_reference=(
            "Athlete confirmed restoring this exact removed native pair."
        ),
        confirmed_pairing_drift_tokens=[drift_token],
    )

    assert resolved.operation == "resolve_pairing_drift"
    assert resolved.items[0].remote_pairing_status == "pairing_noop"
    assert client.activity_pairing_updates == [
        ("i_act_pair_drift", event_id),
        ("i_act_pair_drift", event_id),
    ]


@pytest.mark.parametrize("execution_date", [date(2026, 8, 11), date(2026, 8, 12)])
def test_on_schedule_or_late_fulfillment_places_owned_event_on_execution_day(
    tmp_path,
    monkeypatch,
    execution_date: date,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("preserved-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    offset_days = (execution_date - date(2026, 8, 11)).days
    activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_preserved",
        execution_date=execution_date,
    )
    client.activities["i_act_preserved"] = ActivityDTO(
        id="i_act_preserved",
        type="Run",
        name="Completed run",
        start_date=datetime(
            execution_date.year,
            execution_date.month,
            execution_date.day,
            5,
            tzinfo=timezone.utc,
        ),
        start_date_local=datetime(
            execution_date.year,
            execution_date.month,
            execution_date.day,
            7,
        ),
        elapsed_time=1800,
        moving_time=1800,
        source="GARMIN_CONNECT",
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_preserved",
        workout_identity=workout.identity,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        workout_prescription_sha256=canonical_data_sha256(workout.prescription),
        activity_performance_evidence_sha256=activity_evidence_sha256,
        schedule_timezone="Europe/Paris",
        scheduled_local_date=date(2026, 8, 11),
        execution_local_date=execution_date,
        schedule_offset_days=offset_days,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale="The conversational run fulfilled the approved easy-run intent.",
            confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_preserved": fulfillment}),
    )

    report = service.reconcile_week(1, as_of_date=execution_date)

    expected_status = "noop" if offset_days == 0 else "updated"
    assert [item.status for item in report.items] == [expected_status]
    assert report.items[0].remote_pairing_status == "paired"
    assert event_id in client.events
    assert client.events[event_id].start_date_local == (f"{execution_date.isoformat()}T00:00:00")
    assert load_manifest(repo).historical_fulfillment_event_retirements == []


def test_drifted_fulfilled_event_requires_restore_before_native_pairing(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("drifted-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_drifted",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_drifted",
        workout_identity=workout.identity,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        workout_prescription_sha256=canonical_data_sha256(workout.prescription),
        activity_performance_evidence_sha256=activity_evidence_sha256,
        schedule_timezone="Europe/Paris",
        scheduled_local_date=date(2026, 8, 11),
        execution_local_date=date(2026, 8, 10),
        schedule_offset_days=-1,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale="The conversational run fulfilled the approved easy-run intent.",
            confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_drifted": fulfillment}),
    )
    client.events[event_id] = client.events[event_id].model_copy(
        update={"description": "Athlete edited this event in Intervals.icu"}
    )

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert not blocked.reconciliation_safe
    assert event_id in client.events
    assert client.events[event_id].start_date_local == "2026-08-11T00:00:00"
    drift_token = next(
        item.drift_resolution_token_sha256
        for item in blocked.items
        if item.error_type == "remote_drift"
    )
    assert drift_token is not None

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 10),
        confirmed_drift_target_tokens=[drift_token],
        athlete_confirmation_reference=(
            "Athlete explicitly confirmed restoring the edited fulfilled event."
        ),
    )

    assert restored.operation == "restore_local"
    assert [item.status for item in restored.items] == ["updated"]
    assert restored.items[0].remote_pairing_status == "paired"
    assert event_id in client.events
    assert client.events[event_id].start_date_local == "2026-08-10T00:00:00"
    assert load_manifest(repo).drift_resolutions[-1].strategy == "restore_local"
