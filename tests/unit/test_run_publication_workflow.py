"""Run-only capability, preference, and approved-week publication tests."""

from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from resilio.api import week_application as week_application_api
from resilio.api.publication import PublicationError
from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.locking import OperationLock, OperationLockError
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.planning.constants import PLAN_MUTATION_LOCK_PATH
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import (
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.core.workout_publication import retained_authority as retained_authority_module
from resilio.core.workout_publication.capabilities import (
    get_run_synchronization_capabilities,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.manifest import save_manifest as save_publication_manifest
from resilio.core.workout_publication.naming import provider_workout_names
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.core.workout_publication.preferences import (
    load_run_synchronization_preferences,
    save_run_synchronization_preferences,
)
from resilio.core.workout_publication.retained_authority import (
    retained_pending_publication_authorities,
)
from resilio.core.workout_publication.week_service import RunWeekSynchronizationService
from resilio.integrations.intervals_icu.activity_fingerprint import (
    performance_evidence_fingerprint,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.integrations.intervals_icu.errors import IntervalsTransportError
from resilio.schemas.activity import ActivityOrigin, ActivityOriginKind
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    RunWeekSynchronizationReport,
    RunWorkoutSynchronizationPreferences,
)
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from tests.factories import make_activity
from tests.unit.test_workout_publication import FakeClient


def _authoritative(workout: RunningWorkoutPrescription) -> AuthoritativeWorkout:
    return AuthoritativeWorkout(
        identity=PlanWorkoutIdentity(
            plan_id="plan_publication_test",
            plan_revision_id="plan_revision_1111111111111111",
            week_number=1,
            local_workout_id=workout.id,
        ),
        prescription=workout,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        schedule_timezone="Europe/Paris",
    )


def _targetless_run(workout_id: str, occurrence: date) -> RunningWorkoutPrescription:
    return RunningWorkoutPrescription.model_validate(
        {
            "id": workout_id,
            "date": occurrence,
            "sport": "run",
            "workout_type": "easy",
            "planned_duration_seconds": 600,
            "planned_distance_meters": 1_500,
            "planned_low_intensity_duration_seconds": 600,
            "planned_moderate_intensity_duration_seconds": 0,
            "planned_high_intensity_duration_seconds": 0,
            "target_rpe_1_to_10": 3,
            "purpose": "Easy conversational running.",
            "structured_workout": {
                "sport": "run",
                "steps": [
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 600},
                        "intensity": "active",
                        "cue": "Keep the effort conversational.",
                    }
                ],
            },
        }
    )


def _save_fulfillment_activity(
    repo: RepositoryIO,
    *,
    local_activity_id: str,
    execution_date: date,
) -> str:
    activity = make_activity(id=local_activity_id, date=execution_date)
    activity = activity.model_copy(
        update={
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.HISTORICAL_IMPORT,
                intervals_icu_activity_id=f"i_{local_activity_id}",
            ),
            "audit": activity.audit.model_copy(
                update={
                    "performance_evidence_sha256": performance_evidence_fingerprint(
                        ActivityDTO(
                            id=f"i_{local_activity_id}",
                            type="Run",
                            name="Completed run",
                            start_date=datetime(
                                2026,
                                8,
                                10,
                                5,
                                tzinfo=timezone.utc,
                            ),
                            start_date_local=datetime(2026, 8, 10, 7),
                            elapsed_time=1800,
                            moving_time=1800,
                            source="GARMIN_CONNECT",
                        ),
                        activity.occurrence.timezone,
                    ),
                    "provider_snapshot_sha256": "f" * 64,
                    "canonical_mapping_version": 9,
                }
            ),
        }
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    return activity_performance_evidence_sha256(activity)


def _confirmed_fulfillment(
    workout: AuthoritativeWorkout,
    *,
    local_activity_id: str,
    execution_date: date,
    activity_performance_sha256: str,
) -> WorkoutFulfillmentRecord:
    return WorkoutFulfillmentRecord(
        local_activity_id=local_activity_id,
        workout_identity=workout.identity,
        applied_week_approval_id=workout.applied_week_approval_id,
        applied_running_workouts_sha256=workout.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(workout.prescription),
        activity_performance_evidence_sha256=activity_performance_sha256,
        schedule_timezone=workout.schedule_timezone,
        scheduled_local_date=workout.prescription.date,
        execution_local_date=execution_date,
        schedule_offset_days=(execution_date - workout.prescription.date).days,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the exact association.",
            coaching_rationale=(
                "The athlete identified this run as the approved workout execution."
            ),
            confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )


def _pace_targeted_run(
    workout_id: str,
    occurrence: date,
) -> RunningWorkoutPrescription:
    payload = _targetless_run(workout_id, occurrence).model_dump(mode="json")
    payload["structured_workout"] = {
        "sport": "run",
        "steps": [
            {
                "kind": "steady",
                "duration": {"unit": "seconds", "value": 600},
                "target": {
                    "mode": "pace",
                    "unit": "seconds_per_kilometer",
                    "minimum": 330,
                    "maximum": 360,
                },
                "intensity": "active",
            }
        ],
    }
    return RunningWorkoutPrescription.model_validate(payload)


class HarnessRunWeekSynchronizationService(RunWeekSynchronizationService):
    def __init__(self, repo, client, workouts):
        super().__init__(repo, client)
        self.workouts = workouts

    def _load_authoritative_week_unlocked(self, week_number):
        assert week_number == 1
        return self.workouts


def test_missing_preferences_are_safely_disabled_and_enabled_state_round_trips(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()

    assert load_run_synchronization_preferences(repo).run_synchronization_mode == "disabled"

    preferences = RunWorkoutSynchronizationPreferences(
        run_synchronization_mode="after_weekly_apply",
        athlete_confirmation_reference="Athlete approved automatic run publication.",
        confirmed_at_utc=datetime(2026, 8, 2, 10, tzinfo=timezone.utc),
    )
    save_run_synchronization_preferences(repo, preferences)

    assert load_run_synchronization_preferences(repo) == preferences


def test_unrelated_pending_intent_does_not_affect_current_week_authority(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    current = _authoritative(_targetless_run("current-run", date(2026, 8, 11)))
    unrelated_identity = PlanWorkoutIdentity(
        plan_id="plan_old",
        plan_revision_id="plan_revision_2222222222222222",
        week_number=3,
        local_workout_id="unrelated-run",
    )
    pending = PendingWorkoutPublication(
        workout_identity=unrelated_identity,
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="2" * 64,
        workout_prescription_sha256="3" * 64,
        schedule_timezone="Europe/Paris",
        uid="unrelated-owned-uid",
        external_id="resilio:v1:workout:unrelated-run",
        publication_fingerprint_sha256="4" * 64,
        rendered_workout_sha256="5" * 64,
        sport_settings_version_sha256="6" * 64,
        sport="run",
        occurrence_date=date(2026, 7, 20),
        provider_start_date_local="2026-07-20T00:00:00",
        prepared_at_utc=datetime(2026, 7, 19, 8, tzinfo=timezone.utc),
    )
    save_publication_manifest(
        repo,
        PublicationManifest(pending={"unrelated-run": pending}),
    )
    monkeypatch.setattr(
        retained_authority_module,
        "required_planning_state_unlocked",
        lambda _repo: SimpleNamespace(
            active_plan=SimpleNamespace(applied_week_revisions=[])
        ),
    )

    authorities, _ = retained_pending_publication_authorities(repo, [current])

    assert set(authorities) == {"current-run"}


def test_apply_week_automatically_reconciles_enabled_run_synchronization(
    monkeypatch,
) -> None:
    preferences = RunWorkoutSynchronizationPreferences(
        run_synchronization_mode="after_weekly_apply",
        athlete_confirmation_reference="Athlete approved automatic synchronization.",
        confirmed_at_utc=datetime(2026, 8, 2, 10, tzinfo=timezone.utc),
    )
    report = RunWeekSynchronizationReport.model_construct(
        reconciliation_safe=True,
        partial=False,
    )
    monkeypatch.setattr(
        week_application_api,
        "load_week_application",
        lambda _path: SimpleNamespace(week_number=1),
    )
    monkeypatch.setattr(
        week_application_api,
        "apply_approved_week",
        lambda _repo, _path: SimpleNamespace(
            id="plan-1",
            plan_revision_id="revision-1",
            weeks=[SimpleNamespace(week_number=1)],
        ),
    )
    monkeypatch.setattr(
        week_application_api,
        "applied_running_workouts_sha256",
        lambda _week: "a" * 64,
    )
    monkeypatch.setattr(
        week_application_api,
        "load_run_synchronization_preferences",
        lambda _repo: preferences,
    )
    reconciled_weeks = []
    monkeypatch.setattr(
        week_application_api,
        "reconcile_week_run_workouts",
        lambda week_number: reconciled_weeks.append(week_number) or report,
    )

    result = week_application_api.apply_week_file(Path("approved-week.json"))

    assert result.local_application_status == "applied"
    assert result.run_synchronization_status == "synchronized"
    assert result.run_synchronization_report is report
    assert reconciled_weeks == [1]


def test_apply_week_reports_sync_failure_without_hiding_local_commit(monkeypatch) -> None:
    preferences = RunWorkoutSynchronizationPreferences(
        run_synchronization_mode="after_weekly_apply",
        athlete_confirmation_reference="Athlete approved automatic synchronization.",
        confirmed_at_utc=datetime(2026, 8, 2, 10, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        week_application_api,
        "load_week_application",
        lambda _path: SimpleNamespace(week_number=1),
    )
    monkeypatch.setattr(
        week_application_api,
        "apply_approved_week",
        lambda _repo, _path: SimpleNamespace(
            id="plan-1",
            plan_revision_id="revision-1",
            weeks=[SimpleNamespace(week_number=1)],
        ),
    )
    monkeypatch.setattr(
        week_application_api,
        "applied_running_workouts_sha256",
        lambda _week: "a" * 64,
    )
    monkeypatch.setattr(
        week_application_api,
        "load_run_synchronization_preferences",
        lambda _repo: preferences,
    )
    monkeypatch.setattr(
        week_application_api,
        "reconcile_week_run_workouts",
        lambda _week_number: PublicationError("transport", "provider unavailable"),
    )

    result = week_application_api.apply_week_file(Path("approved-week.json"))

    assert result.local_application_status == "applied"
    assert result.run_synchronization_status == "failed"
    assert result.run_synchronization_error.error_type == "transport"


def test_apply_week_does_not_contact_provider_when_synchronization_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        week_application_api,
        "load_week_application",
        lambda _path: SimpleNamespace(week_number=1),
    )
    monkeypatch.setattr(
        week_application_api,
        "apply_approved_week",
        lambda _repo, _path: SimpleNamespace(
            id="plan-1",
            plan_revision_id="revision-1",
            weeks=[SimpleNamespace(week_number=1)],
        ),
    )
    monkeypatch.setattr(
        week_application_api,
        "applied_running_workouts_sha256",
        lambda _week: "a" * 64,
    )
    monkeypatch.setattr(
        week_application_api,
        "load_run_synchronization_preferences",
        lambda _repo: RunWorkoutSynchronizationPreferences(),
    )
    monkeypatch.setattr(
        week_application_api,
        "reconcile_week_run_workouts",
        lambda _week_number: (_ for _ in ()).throw(
            AssertionError("disabled synchronization contacted the provider")
        ),
    )

    result = week_application_api.apply_week_file(Path("approved-week.json"))

    assert result.local_application_status == "applied"
    assert result.run_synchronization_status == "disabled"


def test_capabilities_separate_calendar_and_garmin_target_readiness() -> None:
    client = FakeClient(threshold_speed_meters_per_second=None)
    client.settings[0] = client.settings[0].model_copy(
        update={"lthr": 176, "max_hr": 195, "hr_zones": [142, 158, 176, 195]}
    )

    capabilities = get_run_synchronization_capabilities(client)

    assert capabilities.intervals_calendar_ready
    assert capabilities.garmin_forwarding_eligible
    assert capabilities.targetless_workouts_ready
    assert capabilities.absolute_heart_rate_targets_ready
    assert capabilities.percent_lthr_targets_ready
    assert capabilities.percent_max_heart_rate_targets_ready
    assert not capabilities.pace_targets_ready
    assert capabilities.threshold_pace_seconds_per_kilometer is None
    assert "run_threshold_pace_missing" in capabilities.limitations


def test_capabilities_report_exact_heart_rate_target_dependencies() -> None:
    client = FakeClient()
    client.settings[0] = client.settings[0].model_copy(
        update={"lthr": None, "max_hr": None, "hr_zones": []}
    )

    capabilities = get_run_synchronization_capabilities(client)

    assert capabilities.absolute_heart_rate_targets_ready
    assert not capabilities.percent_lthr_targets_ready
    assert not capabilities.percent_max_heart_rate_targets_ready
    assert "run_lactate_threshold_heart_rate_missing" in capabilities.limitations
    assert "run_maximum_heart_rate_missing" in capabilities.limitations


def test_week_publication_holds_exact_plan_authority_during_remote_mutation(
    tmp_path,
    monkeypatch,
) -> None:
    repo_holder = {}

    class LockProbeClient(FakeClient):
        plan_lock_was_held = False

        def upsert_event(self, event, *, athlete_id=None):
            repo = repo_holder["repo"]
            with pytest.raises(OperationLockError):
                with OperationLock(
                    repo.resolve_path(PLAN_MUTATION_LOCK_PATH),
                    "concurrent_plan_mutation",
                ):
                    pass
            self.plan_lock_was_held = True
            return super().upsert_event(event, athlete_id=athlete_id)

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    repo_holder["repo"] = repo
    client = LockProbeClient()
    service = HarnessRunWeekSynchronizationService(
        repo,
        client,
        [_authoritative(_targetless_run("run-1", date(2026, 8, 6)))],
    )

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 2))

    assert [item.status for item in report.items] == ["created"]
    assert client.plan_lock_was_held


def test_week_status_blocks_every_mutation_when_one_run_is_invalid(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient(threshold_speed_meters_per_second=None)
    pace_targeted = _pace_targeted_run("pace-run", date(2026, 8, 8))
    service = HarnessRunWeekSynchronizationService(
        repo,
        client,
        [
            _authoritative(_targetless_run("ready-run", date(2026, 8, 6))),
            _authoritative(pace_targeted),
        ],
    )

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 2))

    assert not report.reconciliation_safe
    assert report.partial
    assert [item.status for item in report.items] == ["ready", "error"]
    assert client.upserts == 0
    assert client.events == {}


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


def test_early_confirmed_fulfillment_pairs_activity_and_preserves_owned_event(
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

    assert [item.status for item in report.items] == ["noop"]
    assert report.items[0].remote_pairing_status == "paired"
    assert client.activity_pairing_updates == [("i_act_early", event_id)]
    assert event_id in client.events
    manifest = load_manifest(repo)
    assert "early-run" in manifest.workouts
    assert manifest.historical_fulfillment_event_retirements == []


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
    assert stored.workout_prescription_sha256 == canonical_data_sha256(
        revised.prescription
    )


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

    recovered = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not recovered.partial
    assert recovered.items[0].remote_pairing_status == "paired"
    assert client.activity_pairing_updates == [("i_act_recovery", event_id)]
    assert "recovery-run" not in load_manifest(repo).pending


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
    assert load_manifest(repo).pending == {}


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
    client.activities["i_act_pair_drift"] = client.activities[
        "i_act_pair_drift"
    ].model_copy(update={"paired_event_id": None})

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert not blocked.reconciliation_safe
    assert blocked.items[0].remote_pairing_blocker_code == (
        "resilio_requested_pair_removed"
    )
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
    assert len(
        load_fulfillment_manifest(repo).remote_pairing_drift_resolutions
    ) == 1

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
def test_on_schedule_or_late_fulfillment_preserves_owned_event(
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

    assert [item.status for item in report.items] == ["noop"]
    assert report.items[0].remote_pairing_status == "paired"
    assert event_id in client.events
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
    assert load_manifest(repo).drift_resolutions[-1].strategy == "restore_local"


def test_week_revision_reconciles_retained_and_revised_publications(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    initial = _authoritative(_targetless_run("revision-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [initial])
    service.reconcile_week(1, as_of_date=date(2026, 8, 9))
    retained = replace(
        initial,
        applied_week_approval_id="week_approval_1111111111111111",
        applied_running_workouts_sha256="a" * 64,
    )
    service.workouts = [retained]

    retained_report = service.reconcile_week(1, as_of_date=date(2026, 8, 9))

    assert [item.status for item in retained_report.items] == ["noop"]
    retained_publication = load_manifest(repo).workouts["revision-run"]
    assert retained_publication.applied_week_approval_id == retained.applied_week_approval_id
    assert (
        retained_publication.applied_running_workouts_sha256
        == retained.applied_running_workouts_sha256
    )

    revised = replace(
        retained,
        prescription=retained.prescription.model_copy(
            update={"purpose": "Use the intentionally revised easy-run purpose."}
        ),
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    service.workouts = [revised]

    revised_report = service.reconcile_week(1, as_of_date=date(2026, 8, 9))

    assert [item.status for item in revised_report.items] == ["updated"]
    revised_publication = load_manifest(repo).workouts["revision-run"]
    assert revised_publication.applied_week_approval_id == revised.applied_week_approval_id


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


def test_status_preserves_typed_provider_errors(
    tmp_path,
    monkeypatch,
) -> None:
    class TransportFailureClient(FakeClient):
        def list_events(self, _oldest, _newest, *, athlete_id=None):
            raise IntervalsTransportError(
                "provider unavailable",
                operation="list_events",
            )

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    service = HarnessRunWeekSynchronizationService(
        repo,
        TransportFailureClient(),
        [_authoritative(_targetless_run("run-1", date(2026, 8, 6)))],
    )

    report = service.status_week(1, as_of_date=date(2026, 8, 2))

    assert report.items[0].error_type == "transport"


def test_remote_drift_in_one_run_blocks_every_week_mutation(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    protected = _authoritative(_targetless_run("protected-run", date(2026, 8, 8)))
    service = HarnessRunWeekSynchronizationService(repo, client, [protected])
    first = service.reconcile_week(1, as_of_date=date(2026, 8, 2))
    event_id = first.items[0].event_id
    client.events[event_id] = client.events[event_id].model_copy(
        update={"description": "changed outside Resilio"}
    )
    service.workouts = [
        _authoritative(_targetless_run("new-run", date(2026, 8, 6))),
        protected,
    ]

    blocked = service.reconcile_week(1, as_of_date=date(2026, 8, 2))

    assert not blocked.reconciliation_safe
    assert client.upserts == 1
    assert all(
        event.external_id != "resilio:v1:workout:new-run" for event in client.events.values()
    )


def test_explicit_restore_local_resolution_updates_owned_drift_in_place(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("run-1", date(2026, 8, 8)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    created = service.reconcile_week(1, as_of_date=date(2026, 8, 2))
    event_id = created.items[0].event_id
    client.events[event_id] = client.events[event_id].model_copy(
        update={"description": "Athlete edited this in Intervals.icu"}
    )
    drift_status = service.status_week(1, as_of_date=date(2026, 8, 2))
    drift_token = next(
        item.drift_resolution_token_sha256
        for item in drift_status.items
        if item.error_type == "remote_drift"
    )
    assert drift_token is not None

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 2),
        athlete_confirmation_reference="Athlete explicitly selected restore-local.",
        confirmed_drift_target_tokens=[drift_token],
    )

    assert restored.operation == "restore_local"
    assert restored.reconciliation_safe
    assert [item.status for item in restored.items] == ["updated"]
    assert len(client.events) == 1
    assert client.events[event_id].description.startswith("Easy conversational running.")
    manifest = load_manifest(repo)
    assert manifest.drift_resolutions[-1].strategy == "restore_local"


def test_restore_local_never_overwrites_new_drift_on_an_unconfirmed_sibling(
    tmp_path,
    monkeypatch,
) -> None:
    from resilio.core.workout_publication import week_service as week_service_module

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    first = _authoritative(_targetless_run("run-1", date(2026, 8, 8)))
    second = _authoritative(_targetless_run("run-2", date(2026, 8, 9)))
    service = HarnessRunWeekSynchronizationService(repo, client, [first, second])
    created = service.reconcile_week(1, as_of_date=date(2026, 8, 2))
    event_ids = {item.local_workout_id: item.event_id for item in created.items}
    first_event_id = event_ids["run-1"]
    second_event_id = event_ids["run-2"]
    assert first_event_id is not None and second_event_id is not None
    client.events[first_event_id] = client.events[first_event_id].model_copy(
        update={"description": "Athlete reviewed this drift."}
    )
    drift_status = service.status_week(1, as_of_date=date(2026, 8, 2))
    drift_token = next(
        item.drift_resolution_token_sha256
        for item in drift_status.items
        if item.local_workout_id == "run-1"
    )
    assert drift_token is not None
    original_confirmation = week_service_module.confirm_publication_drift_targets

    def confirm_then_drift_sibling(*args, **kwargs):
        confirmed = original_confirmation(*args, **kwargs)
        client.events[second_event_id] = client.events[second_event_id].model_copy(
            update={"description": "Unreviewed concurrent sibling drift."}
        )
        return confirmed

    monkeypatch.setattr(
        week_service_module,
        "confirm_publication_drift_targets",
        confirm_then_drift_sibling,
    )
    upserts_before_resolution = client.upserts

    result = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 2),
        athlete_confirmation_reference="Athlete confirmed only the reviewed target.",
        confirmed_drift_target_tokens=[drift_token],
    )

    assert not result.reconciliation_safe
    assert client.upserts == upserts_before_resolution
    assert client.events[first_event_id].description == "Athlete reviewed this drift."
    assert client.events[second_event_id].description == "Unreviewed concurrent sibling drift."


def test_restore_local_requires_actual_owned_remote_drift(tmp_path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("run-1", date(2026, 8, 8)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    service.reconcile_week(1, as_of_date=date(2026, 8, 2))

    with pytest.raises(PublicationSafetyError, match="no owned remote drift"):
        service.restore_local_week(
            1,
            as_of_date=date(2026, 8, 2),
            athlete_confirmation_reference="Athlete selected restore-local.",
            confirmed_drift_target_tokens=[],
        )

    assert load_manifest(repo).drift_resolutions == []
