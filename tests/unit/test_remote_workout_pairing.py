from datetime import date, datetime, timezone

import pytest

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.remote_pairing import (
    WorkoutPairingReconciliationService,
)
from resilio.core.workout_fulfillment.remote_unpairing import (
    WorkoutUnpairingReconciliationService,
    stage_remote_unpairing,
)
from resilio.core.workout_fulfillment.repository import (
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.integrations.intervals_icu.activity_fingerprint import (
    performance_evidence_fingerprint,
)
from resilio.integrations.intervals_icu.activity_pairing import (
    activity_pairing_guard_sha256,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.schemas.activity import ActivityOrigin, ActivityOriginKind
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.publication import PublishedWorkout
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    FulfillmentActivityEvidenceRevision,
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
    WorkoutFulfillmentRevocation,
)
from tests.factories import make_activity


def _workout() -> RunningWorkoutPrescription:
    return RunningWorkoutPrescription.model_validate(
        {
            "id": "easy-run",
            "date": "2026-08-11",
            "sport": "run",
            "workout_type": "easy",
            "planned_duration_seconds": 1800,
            "planned_distance_meters": 5000,
            "planned_low_intensity_duration_seconds": 1800,
            "planned_moderate_intensity_duration_seconds": 0,
            "planned_high_intensity_duration_seconds": 0,
            "target_rpe_1_to_10": 3,
            "purpose": "Easy conversational running.",
            "structured_workout": {
                "sport": "run",
                "steps": [
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 1800},
                        "intensity": "active",
                    }
                ],
            },
        }
    )


def _authority() -> AuthoritativeWorkout:
    workout = _workout()
    return AuthoritativeWorkout(
        identity=PlanWorkoutIdentity(
            plan_id="plan_pairing",
            plan_revision_id="plan_revision_0123456789abcdef",
            week_number=1,
            local_workout_id=workout.id,
        ),
        prescription=workout,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        schedule_timezone="Europe/Paris",
    )


def _activity(repo: RepositoryIO, execution_date: date):
    base = make_activity(
        id="act_i_pairing",
        date=execution_date,
        distance_meters=5500,
    )
    activity = base.model_copy(
        update={
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.INTERVALS_ICU,
                intervals_icu_activity_id="i123",
            ),
            "audit": base.audit.model_copy(
                update={
                    "performance_evidence_sha256": (
                        performance_evidence_fingerprint(
                            _remote_activity(),
                            base.occurrence.timezone,
                        )
                    ),
                    "provider_snapshot_sha256": "f" * 64,
                    "canonical_mapping_version": 9,
                }
            ),
        }
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    return activity


def _fulfillment(activity, authority: AuthoritativeWorkout) -> WorkoutFulfillmentRecord:
    execution_date = activity.occurrence.local_date
    return WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=authority.prescription.date,
        execution_local_date=execution_date,
        schedule_offset_days=(execution_date - authority.prescription.date).days,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="2" * 64,
            athlete_confirmation_reference="Athlete confirmed the exact association.",
            coaching_rationale="The athlete identified this run as the approved easy workout.",
            confirmed_at_utc=datetime(2026, 8, 10, 6, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 6, tzinfo=timezone.utc),
    )


def _publication(authority: AuthoritativeWorkout) -> PublishedWorkout:
    return PublishedWorkout(
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        schedule_timezone=authority.schedule_timezone,
        event_id=42,
        requested_uid="resilio-owned-uid",
        uid="resilio-owned-uid",
        external_id="resilio:v1:workout:easy-run",
        publication_fingerprint_sha256="3" * 64,
        rendered_workout_sha256="4" * 64,
        sport_settings_version_sha256="5" * 64,
        provider_event_fingerprint_sha256="6" * 64,
        provider_step_semantics_sha256="7" * 64,
        sport="run",
        occurrence_date=authority.prescription.date,
        provider_start_date_local="2026-08-11T00:00:00",
        garmin_forwarding_status="not_configured",
        verified_at_utc=datetime(2026, 8, 10, 7, tzinfo=timezone.utc),
    )


def _remote_activity(*, paired_event_id: int | None = None, source: str = "GARMIN_CONNECT"):
    return ActivityDTO(
        id="i123",
        type="Run",
        name="Easy run",
        start_date=datetime(2026, 8, 10, 5, tzinfo=timezone.utc),
        start_date_local=datetime(2026, 8, 10, 7),
        elapsed_time=2220,
        moving_time=2200,
        distance=5500,
        source=source,
        paired_event_id=paired_event_id,
    )


class PairingClient:
    def __init__(self, activity: ActivityDTO):
        self.activity = activity
        self.update_payloads: list[int | None] = []

    def get_activity(self, activity_id: str, *, intervals: bool = True) -> ActivityDTO:
        assert activity_id == self.activity.id
        assert intervals is True
        return self.activity

    def update_activity_pairing(self, activity_id, pairing):
        assert activity_id == self.activity.id
        self.update_payloads.append(pairing.paired_event_id)
        self.activity = self.activity.model_copy(
            update={"paired_event_id": pairing.paired_event_id}
        )
        return self.activity


class GuardChangingFailedPairingClient(PairingClient):
    """Simulate one ambiguous write that changes only a non-performance field."""

    def __init__(self, activity: ActivityDTO, *, apply_pair_before_failure: bool):
        super().__init__(activity)
        self.apply_pair_before_failure = apply_pair_before_failure

    def update_activity_pairing(self, activity_id, pairing):
        if not self.update_payloads:
            self.update_payloads.append(pairing.paired_event_id)
            updates = {"name": "Edited remotely"}
            if self.apply_pair_before_failure:
                updates["paired_event_id"] = pairing.paired_event_id
            self.activity = self.activity.model_copy(update=updates)
            raise OSError("ambiguous provider transport failure")
        return super().update_activity_pairing(activity_id, pairing)


class FailedBeforeWritePairingClient(PairingClient):
    """Simulate a process-safe intent persisted before an unsubmitted write."""

    def update_activity_pairing(self, activity_id, pairing):
        if not self.update_payloads:
            self.update_payloads.append(pairing.paired_event_id)
            raise OSError("provider request was not submitted")
        return super().update_activity_pairing(activity_id, pairing)


class ReadbackFailedAfterPairingClient(PairingClient):
    """Apply one pair, then lose its first verification readback."""

    fail_next_readback = False

    def get_activity(self, activity_id: str, *, intervals: bool = True) -> ActivityDTO:
        if self.fail_next_readback:
            self.fail_next_readback = False
            raise OSError("pairing readback transport failure")
        return super().get_activity(activity_id, intervals=intervals)

    def update_activity_pairing(self, activity_id, pairing):
        updated = super().update_activity_pairing(activity_id, pairing)
        self.fail_next_readback = True
        return updated


class GuardChangingFailedUnpairingClient(PairingClient):
    """Simulate an ambiguous unpair after an unrelated remote field edit."""

    def update_activity_pairing(self, activity_id, pairing):
        if not self.update_payloads:
            self.update_payloads.append(pairing.paired_event_id)
            self.activity = self.activity.model_copy(update={"name": "Edited remotely"})
            raise OSError("ambiguous provider transport failure")
        return super().update_activity_pairing(activity_id, pairing)


@pytest.mark.parametrize(
    "execution_date",
    [date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12)],
)
def test_reconcile_pairs_all_execution_timings_without_deleting_intent(
    tmp_path,
    monkeypatch,
    execution_date: date,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, execution_date)
    fulfillment = _fulfillment(activity, authority)
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )
    client = PairingClient(_remote_activity())

    result = WorkoutPairingReconciliationService(repo, client).reconcile_pairing(
        authority=authority,
        publication=_publication(authority),
        fulfillment=fulfillment,
        activity=activity,
    )

    assert result.status == "paired"
    assert client.update_payloads == [42]
    stored = load_fulfillment_manifest(repo)
    assert stored.fulfillments[activity.local_activity_id].provider_pair is not None
    assert (
        stored.fulfillments[activity.local_activity_id].provider_pair.provenance
        == "resilio_requested"
    )
    assert list(stored.remote_pairing_operations.values())[0].state == "verified"


def test_existing_exact_pair_is_idempotent_and_keeps_external_provenance(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    fulfillment = _fulfillment(activity, authority)
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )
    client = PairingClient(_remote_activity(paired_event_id=42))

    result = WorkoutPairingReconciliationService(repo, client).reconcile_pairing(
        authority=authority,
        publication=_publication(authority),
        fulfillment=fulfillment,
        activity=activity,
    )

    assert result.status == "pairing_noop"
    assert client.update_payloads == []
    stored = load_fulfillment_manifest(repo).fulfillments[activity.local_activity_id]
    assert stored.provider_pair is not None
    assert stored.provider_pair.provenance == "provider_observed"
    assert load_fulfillment_manifest(repo).remote_pairing_operations == {}


def test_missing_provider_observed_pair_is_not_restored_without_athlete_authority(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    fulfillment = _fulfillment(activity, authority).model_copy(
        update={
            "athlete_confirmation": None,
            "provider_pair": ProviderPairedFulfillmentEvidence(
                event_id=42,
                provenance="provider_observed",
                observed_at_utc=datetime(2026, 8, 10, 7, tzinfo=timezone.utc),
            ),
        }
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )
    client = PairingClient(_remote_activity())

    result = WorkoutPairingReconciliationService(repo, client).reconcile_pairing(
        authority=authority,
        publication=_publication(authority),
        fulfillment=fulfillment,
        activity=activity,
    )

    assert result.status == "pairing_blocked"
    assert result.blocker_code == "provider_observed_pair_missing"
    assert client.update_payloads == []
    assert load_fulfillment_manifest(repo).remote_pairing_operations == {}


@pytest.mark.parametrize("method_name", ["inspect_pairing", "reconcile_pairing"])
def test_provider_pair_evidence_must_match_the_exact_publication_event(
    tmp_path,
    monkeypatch,
    method_name: str,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    fulfillment = _fulfillment(activity, authority).model_copy(
        update={
            "provider_pair": ProviderPairedFulfillmentEvidence(
                event_id=99,
                provenance="provider_observed",
                observed_at_utc=datetime(2026, 8, 10, 7, tzinfo=timezone.utc),
            )
        }
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )
    service = WorkoutPairingReconciliationService(
        repo,
        PairingClient(_remote_activity(paired_event_id=42)),
    )

    with pytest.raises(ValueError, match="provider-pair event does not match"):
        getattr(service, method_name)(
            authority=authority,
            publication=_publication(authority),
            fulfillment=fulfillment,
            activity=activity,
        )


@pytest.mark.parametrize("method_name", ["inspect_pairing", "reconcile_pairing"])
def test_pairing_rejects_a_different_activity_point_read(
    tmp_path,
    monkeypatch,
    method_name: str,
) -> None:
    class WrongActivityIdentityClient(PairingClient):
        def get_activity(self, activity_id: str, *, intervals: bool = True):
            assert activity_id == "i123"
            assert intervals is True
            return self.activity.model_copy(update={"id": "i999"})

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    fulfillment = _fulfillment(activity, authority)
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )
    service = WorkoutPairingReconciliationService(
        repo,
        WrongActivityIdentityClient(_remote_activity()),
    )

    with pytest.raises(ValueError, match="readback identity"):
        getattr(service, method_name)(
            authority=authority,
            publication=_publication(authority),
            fulfillment=fulfillment,
            activity=activity,
        )


def test_provider_only_pair_to_a_different_event_reports_the_exact_conflict(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    fulfillment = _fulfillment(activity, authority).model_copy(
        update={
            "athlete_confirmation": None,
            "provider_pair": ProviderPairedFulfillmentEvidence(
                event_id=42,
                provenance="provider_observed",
                observed_at_utc=datetime(2026, 8, 10, 7, tzinfo=timezone.utc),
            ),
        }
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )

    result = WorkoutPairingReconciliationService(
        repo,
        PairingClient(_remote_activity(paired_event_id=99)),
    ).inspect_pairing(
        authority=authority,
        publication=_publication(authority),
        fulfillment=fulfillment,
        activity=activity,
    )

    assert result.status == "pairing_blocked"
    assert result.blocker_code == "activity_paired_to_different_event"


def test_unknown_provider_fields_are_part_of_the_pairing_write_guard() -> None:
    original = ActivityDTO.model_validate(
        {**_remote_activity().model_dump(mode="json"), "provider_new_field": "v1"}
    )
    changed = ActivityDTO.model_validate(
        {**_remote_activity().model_dump(mode="json"), "provider_new_field": "v2"}
    )

    assert original.model_extra == {"provider_new_field": "v1"}
    assert activity_pairing_guard_sha256(original) != activity_pairing_guard_sha256(changed)


@pytest.mark.parametrize(
    (
        "apply_pair_before_failure",
        "expected_final_status",
        "expected_update_payloads",
        "expected_provenance",
    ),
    [
        (False, "paired", [42, 42], "resilio_requested"),
        (True, "pairing_noop", [42], "pair_origin_ambiguous"),
    ],
)
def test_pending_pair_guard_drift_requires_exact_confirmation_before_retry(
    tmp_path,
    monkeypatch,
    apply_pair_before_failure: bool,
    expected_final_status: str,
    expected_update_payloads: list[int],
    expected_provenance: str,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    fulfillment = _fulfillment(activity, authority)
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )
    client = GuardChangingFailedPairingClient(
        _remote_activity(),
        apply_pair_before_failure=apply_pair_before_failure,
    )
    service = WorkoutPairingReconciliationService(repo, client)
    publication = _publication(authority)

    failed = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=fulfillment,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
    )
    blocked = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=fulfillment,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 9, tzinfo=timezone.utc),
    )

    assert failed.blocker_code == "provider_pairing_request_failed"
    assert blocked.blocker_code == "provider_activity_changed_during_pairing"
    assert blocked.pairing_drift_token_sha256 is not None
    assert client.update_payloads == [42]

    service.confirm_pairing_drift(
        operation_id=blocked.operation_id,
        supplied_pairing_drift_token_sha256=blocked.pairing_drift_token_sha256,
        athlete_confirmation_reference="Athlete authorized retrying this exact pair.",
        confirmed_at_utc=datetime(2026, 8, 10, 9, 30, tzinfo=timezone.utc),
    )
    paired = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=fulfillment,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )

    assert paired.status == expected_final_status
    assert client.update_payloads == expected_update_payloads
    stored = load_fulfillment_manifest(repo).fulfillments[activity.local_activity_id]
    assert stored.provider_pair is not None
    assert stored.provider_pair.provenance == expected_provenance


def test_unsubmitted_intent_never_becomes_independent_provider_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    fulfillment = _fulfillment(activity, authority)
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )
    client = FailedBeforeWritePairingClient(_remote_activity())
    service = WorkoutPairingReconciliationService(repo, client)
    publication = _publication(authority)

    first = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=fulfillment,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
    )
    client.activity = client.activity.model_copy(update={"paired_event_id": 42})
    recovered = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=fulfillment,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 9, tzinfo=timezone.utc),
    )
    stored = load_fulfillment_manifest(repo).fulfillments[activity.local_activity_id]

    assert first.blocker_code == "provider_pairing_request_failed"
    assert recovered.status == "pairing_noop"
    assert stored.provider_pair is not None
    assert stored.provider_pair.provenance == "pair_origin_ambiguous"
    assert not stored.independent_provider_pair_supports_event(42)

    client.activity = client.activity.model_copy(update={"paired_event_id": None})
    inspected = service.inspect_pairing(
        authority=authority,
        publication=publication,
        fulfillment=stored,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    removed = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=stored,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    assert removed.blocker_code == "ambiguous_pair_removed"
    assert removed.pairing_drift_token_sha256 is not None
    assert inspected.pairing_drift_token_sha256 == removed.pairing_drift_token_sha256
    assert client.update_payloads == [42]

    service.confirm_pairing_drift(
        operation_id=removed.operation_id,
        supplied_pairing_drift_token_sha256=removed.pairing_drift_token_sha256,
        athlete_confirmation_reference=(
            "Athlete confirmed restoring this exact ambiguous native pair."
        ),
        confirmed_at_utc=datetime(2026, 8, 10, 10, 30, tzinfo=timezone.utc),
    )
    restored = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=stored,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 11, tzinfo=timezone.utc),
    )

    assert restored.status == "paired"
    assert client.update_payloads == [42, 42]
    final = load_fulfillment_manifest(repo).fulfillments[activity.local_activity_id]
    assert final.provider_pair is not None
    assert final.provider_pair.provenance == "resilio_requested"


def test_submitted_pair_survives_a_continuous_activity_evidence_revision(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    original_activity = _activity(repo, date(2026, 8, 10))
    original_fulfillment = _fulfillment(original_activity, authority)
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            fulfillments={original_activity.local_activity_id: original_fulfillment}
        ),
    )
    client = ReadbackFailedAfterPairingClient(_remote_activity())
    service = WorkoutPairingReconciliationService(repo, client)
    publication = _publication(authority)

    interrupted = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=original_fulfillment,
        activity=original_activity,
        now_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
    )
    assert interrupted.blocker_code == "provider_pairing_readback_failed"
    pending_operation = next(
        iter(load_fulfillment_manifest(repo).remote_pairing_operations.values())
    )
    assert pending_operation.provider_write_submitted_at_utc is not None
    assert client.activity.paired_event_id == publication.event_id

    corrected_remote = client.activity.model_copy(
        update={
            "start_date": datetime(2026, 8, 11, 5, tzinfo=timezone.utc),
            "start_date_local": datetime(2026, 8, 11, 7),
        }
    )
    corrected_base = make_activity(
        id=original_activity.local_activity_id,
        date=date(2026, 8, 11),
        distance_meters=5500,
    )
    corrected_activity = corrected_base.model_copy(
        update={
            "origin": original_activity.origin,
            "audit": corrected_base.audit.model_copy(
                update={
                    "performance_evidence_sha256": performance_evidence_fingerprint(
                        corrected_remote,
                        corrected_base.occurrence.timezone,
                    ),
                    "provider_snapshot_sha256": "e" * 64,
                    "canonical_mapping_version": 9,
                }
            ),
        }
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(corrected_activity)
    corrected_sha256 = activity_performance_evidence_sha256(corrected_activity)
    revised_fulfillment = WorkoutFulfillmentRecord.model_validate(
        {
            **original_fulfillment.model_dump(mode="python"),
            "activity_performance_evidence_sha256": corrected_sha256,
            "execution_local_date": date(2026, 8, 11),
            "schedule_offset_days": 0,
            "provider_pair": ProviderPairedFulfillmentEvidence(
                event_id=publication.event_id,
                provenance="resilio_requested",
                observed_at_utc=datetime(2026, 8, 11, 8, tzinfo=timezone.utc),
            ),
            "activity_evidence_revisions": [
                FulfillmentActivityEvidenceRevision(
                    previous_activity_performance_evidence_sha256=(
                        original_fulfillment.activity_performance_evidence_sha256
                    ),
                    replacement_activity_performance_evidence_sha256=(corrected_sha256),
                    previous_execution_local_date=date(2026, 8, 10),
                    replacement_execution_local_date=date(2026, 8, 11),
                    observed_at_utc=datetime(2026, 8, 11, 8, tzinfo=timezone.utc),
                )
            ],
        }
    )
    manifest = load_fulfillment_manifest(repo)
    manifest.fulfillments[revised_fulfillment.local_activity_id] = revised_fulfillment
    save_fulfillment_manifest(repo, manifest)
    client.activity = corrected_remote

    recovered = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=revised_fulfillment,
        activity=corrected_activity,
        now_utc=datetime(2026, 8, 11, 9, tzinfo=timezone.utc),
    )

    assert recovered.status == "pairing_noop"
    stored_operation = load_fulfillment_manifest(repo).remote_pairing_operations[
        pending_operation.operation_id
    ]
    assert stored_operation.state == "verified"
    assert client.update_payloads == [publication.event_id]


def test_different_existing_pair_and_strava_source_fail_without_mutation(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    fulfillment = _fulfillment(activity, authority)
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )
    publication = _publication(authority)

    for remote in (
        _remote_activity(paired_event_id=99),
        _remote_activity(source="STRAVA"),
    ):
        matching_activity = activity.model_copy(
            update={
                "audit": activity.audit.model_copy(
                    update={
                        "performance_evidence_sha256": (
                            performance_evidence_fingerprint(
                                remote,
                                activity.occurrence.timezone,
                            )
                        )
                    }
                )
            }
        )
        matching_fulfillment = _fulfillment(matching_activity, authority)
        save_fulfillment_manifest(
            repo,
            WorkoutFulfillmentManifest(
                fulfillments={matching_activity.local_activity_id: matching_fulfillment}
            ),
        )
        client = PairingClient(remote)
        result = WorkoutPairingReconciliationService(repo, client).reconcile_pairing(
            authority=authority,
            publication=publication,
            fulfillment=matching_fulfillment,
            activity=matching_activity,
        )
        assert result.status == "pairing_blocked"
        assert client.update_payloads == []


def test_revocation_stages_and_reconciles_exact_native_unpair(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    original = _fulfillment(activity, authority).model_copy(
        update={
            "provider_pair": ProviderPairedFulfillmentEvidence(
                event_id=42,
                provenance="resilio_requested",
                observed_at_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
            )
        }
    )
    revocation = WorkoutFulfillmentRevocation(
        revocation_id="fulfillment_revocation_0123456789abcdef",
        fulfillment=original,
        intervals_icu_activity_id="i123",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete confirmed this activity did not fulfill the workout.",
        revoked_at_utc=datetime(2026, 8, 10, 9, tzinfo=timezone.utc),
    )
    manifest = WorkoutFulfillmentManifest(revoked_fulfillments=[revocation])
    service = WorkoutPairingReconciliationService(
        repo,
        PairingClient(_remote_activity(paired_event_id=42)),
    )
    operation = stage_remote_unpairing(
        manifest=manifest,
        publication=_publication(authority),
        revocation=revocation,
        activity=activity,
    )
    save_fulfillment_manifest(repo, manifest)

    unpairing_service = WorkoutUnpairingReconciliationService(repo, service.client)
    result = unpairing_service.reconcile(operation)

    assert result.status == "unpaired"
    assert service.client.update_payloads == [None]
    assert (
        load_fulfillment_manifest(repo).remote_pairing_operations[operation.operation_id].state
        == "verified"
    )


def test_revoked_unpair_rebases_nonperformance_guard_without_losing_authority(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    original = _fulfillment(activity, authority).model_copy(
        update={
            "provider_pair": ProviderPairedFulfillmentEvidence(
                event_id=42,
                provenance="resilio_requested",
                observed_at_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
            )
        }
    )
    revocation = WorkoutFulfillmentRevocation(
        revocation_id="fulfillment_revocation_0123456789abcdef",
        fulfillment=original,
        intervals_icu_activity_id="i123",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew the exact association.",
        coaching_rationale="The athlete confirmed this activity did not fulfill the workout.",
        revoked_at_utc=datetime(2026, 8, 10, 9, tzinfo=timezone.utc),
    )
    manifest = WorkoutFulfillmentManifest(revoked_fulfillments=[revocation])
    operation = stage_remote_unpairing(
        manifest=manifest,
        publication=_publication(authority),
        revocation=revocation,
        activity=activity,
    )
    save_fulfillment_manifest(repo, manifest)
    client = GuardChangingFailedUnpairingClient(_remote_activity(paired_event_id=42))
    service = WorkoutUnpairingReconciliationService(repo, client)

    failed = service.reconcile(
        operation,
        now_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    pending = load_fulfillment_manifest(repo).remote_pairing_operations[operation.operation_id]
    recovered = service.reconcile(
        pending,
        now_utc=datetime(2026, 8, 10, 11, tzinfo=timezone.utc),
    )

    assert failed.blocker_code == "provider_unpairing_request_failed"
    assert recovered.status == "unpaired"
    assert client.update_payloads == [None, None]


def test_removed_resilio_pair_requires_exact_athlete_confirmed_drift_resolution(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    authority = _authority()
    activity = _activity(repo, date(2026, 8, 10))
    fulfillment = _fulfillment(activity, authority)
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={activity.local_activity_id: fulfillment}),
    )
    client = PairingClient(_remote_activity())
    service = WorkoutPairingReconciliationService(repo, client)
    publication = _publication(authority)
    first = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=fulfillment,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
    )
    stored_fulfillment = load_fulfillment_manifest(repo).fulfillments[activity.local_activity_id]
    client.activity = client.activity.model_copy(update={"paired_event_id": None})

    blocked = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=stored_fulfillment,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 9, tzinfo=timezone.utc),
    )

    assert first.status == "paired"
    assert blocked.status == "pairing_blocked"
    assert blocked.blocker_code == "resilio_requested_pair_removed"
    assert blocked.pairing_drift_token_sha256 is not None
    assert client.update_payloads == [42]

    service.confirm_pairing_drift(
        operation_id=blocked.operation_id,
        supplied_pairing_drift_token_sha256=blocked.pairing_drift_token_sha256,
        athlete_confirmation_reference="Athlete confirmed restoring this exact removed pair.",
        confirmed_at_utc=datetime(2026, 8, 10, 9, 30, tzinfo=timezone.utc),
    )
    restored = service.reconcile_pairing(
        authority=authority,
        publication=publication,
        fulfillment=stored_fulfillment,
        activity=activity,
        now_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )

    assert restored.status == "paired"
    assert client.update_payloads == [42, 42]
