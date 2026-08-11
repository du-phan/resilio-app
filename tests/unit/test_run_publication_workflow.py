"""Run-only capability, preference, and approved-week publication tests."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
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
from resilio.core.workout_fulfillment.service import WorkoutFulfillmentService
from resilio.core.workout_publication.capabilities import (
    get_run_synchronization_capabilities,
)
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.core.workout_publication.preferences import (
    load_run_synchronization_preferences,
    save_run_synchronization_preferences,
)
from resilio.core.workout_publication.week_selection import (
    week_fulfillment_retirements,
)
from resilio.core.workout_publication.week_service import RunWeekSynchronizationService
from resilio.integrations.intervals_icu.errors import IntervalsTransportError
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.publication import (
    PendingWorkoutPublication,
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
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    return activity_performance_evidence_sha256(activity)


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


def test_early_confirmed_fulfillment_retires_future_owned_event(
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

    assert [item.status for item in report.items] == ["skipped_fulfilled", "retired"]
    assert event_id not in client.events
    manifest = load_manifest(repo)
    assert "early-run" not in manifest.workouts
    assert manifest.retired["early-run"].fulfilling_local_activity_id == "act_early"


def test_fulfillment_retirements_are_scoped_to_the_requested_week(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    requested_workout = _authoritative(_targetless_run("requested-week-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [requested_workout])
    service.reconcile_week(1, as_of_date=date(2026, 8, 9))
    manifest = load_manifest(repo)
    requested_publication = manifest.workouts["requested-week-run"]
    other_identity = PlanWorkoutIdentity(
        plan_id=requested_workout.identity.plan_id,
        plan_revision_id=requested_workout.identity.plan_revision_id,
        week_number=2,
        local_workout_id="other-week-run",
    )
    manifest.workouts["other-week-run"] = requested_publication.model_copy(
        update={
            "workout_identity": other_identity,
            "event_id": requested_publication.event_id + 1,
            "requested_uid": "other-requested-uid",
            "uid": "other-uid",
            "external_id": "resilio:v1:workout:other-week-run",
            "occurrence_date": date(2026, 8, 18),
            "provider_start_date_local": "2026-08-18T00:00:00",
        }
    )
    save_manifest(repo, manifest)
    other_fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_other_week",
        workout_identity=other_identity,
        applied_week_approval_id=requested_workout.applied_week_approval_id,
        applied_running_workouts_sha256=requested_workout.applied_running_workouts_sha256,
        workout_prescription_sha256="2" * 64,
        activity_performance_evidence_sha256="3" * 64,
        schedule_timezone=requested_workout.schedule_timezone,
        scheduled_local_date=date(2026, 8, 18),
        execution_local_date=date(2026, 8, 17),
        schedule_offset_days=-1,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale="The conversational run fulfilled the approved easy-run intent.",
            confirmed_at_utc=datetime(2026, 8, 17, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 17, 10, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            fulfillments={other_fulfillment.local_activity_id: other_fulfillment}
        ),
    )

    retirements = week_fulfillment_retirements(
        repo,
        workouts=[requested_workout],
        as_of_date=date(2026, 8, 10),
    )

    assert retirements == {}


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
            confirmed_at_utc=datetime(2026, 8, 12, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 12, 10, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_preserved": fulfillment}),
    )

    report = service.reconcile_week(1, as_of_date=execution_date)

    assert [item.status for item in report.items] == ["skipped_fulfilled"]
    assert event_id in client.events
    assert load_manifest(repo).retired == {}


def test_drifted_early_fulfillment_requires_separate_retirement_confirmation(
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

    retired = service.retire_fulfilled_week(
        1,
        as_of_date=date(2026, 8, 10),
        confirmed_drift_target_tokens=[drift_token],
        athlete_confirmation_reference=(
            "Athlete explicitly confirmed deleting the edited fulfilled event."
        ),
    )

    assert retired.operation == "retire_fulfilled"
    assert [item.status for item in retired.items] == [
        "skipped_fulfilled",
        "retired",
    ]
    assert event_id not in client.events
    assert load_manifest(repo).drift_resolutions[-1].strategy == "retire_fulfilled"


def test_restore_local_cannot_retire_a_drifted_fulfilled_future_event(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("restore-blocked", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_restore_blocked",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_restore_blocked",
        workout_identity=workout.identity,
        applied_week_approval_id=workout.applied_week_approval_id,
        applied_running_workouts_sha256=workout.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(workout.prescription),
        activity_performance_evidence_sha256=activity_evidence_sha256,
        schedule_timezone=workout.schedule_timezone,
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
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )
    client.events[event_id] = client.events[event_id].model_copy(
        update={"description": "Athlete edited this future event."}
    )
    status = service.status_week(1, as_of_date=date(2026, 8, 10))
    drift_token = status.items[-1].drift_resolution_token_sha256
    assert drift_token is not None

    with pytest.raises(
        PublicationSafetyError,
        match="retire-fulfilled",
    ):
        service.restore_local_week(
            1,
            as_of_date=date(2026, 8, 10),
            athlete_confirmation_reference="Athlete selected restore-local.",
            confirmed_drift_target_tokens=[drift_token],
        )

    assert event_id in client.events
    assert load_manifest(repo).drift_resolutions == []


def test_early_fulfillment_retires_recoverable_pending_remote_identity(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("pending-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_pending",
        execution_date=date(2026, 8, 10),
    )
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    manifest = load_manifest(repo)
    published = manifest.workouts.pop("pending-run")
    manifest.pending["pending-run"] = PendingWorkoutPublication(
        workout_identity=published.workout_identity,
        applied_week_approval_id=published.applied_week_approval_id,
        applied_running_workouts_sha256=published.applied_running_workouts_sha256,
        workout_prescription_sha256=published.workout_prescription_sha256,
        schedule_timezone=published.schedule_timezone,
        uid=published.uid,
        external_id=published.external_id,
        publication_fingerprint_sha256=published.publication_fingerprint_sha256,
        rendered_workout_sha256=published.rendered_workout_sha256,
        sport_settings_version_sha256=published.sport_settings_version_sha256,
        sport=published.sport,
        occurrence_date=published.occurrence_date,
        approved_start_time_local=published.approved_start_time_local,
        provider_start_date_local=published.provider_start_date_local,
        prepared_at_utc=datetime(2026, 8, 9, 10, tzinfo=timezone.utc),
    )
    save_manifest(repo, manifest)
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_pending",
        workout_identity=workout.identity,
        applied_week_approval_id=workout.applied_week_approval_id,
        applied_running_workouts_sha256=workout.applied_running_workouts_sha256,
        workout_prescription_sha256=published.workout_prescription_sha256,
        activity_performance_evidence_sha256=activity_evidence_sha256,
        schedule_timezone=workout.schedule_timezone,
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
        WorkoutFulfillmentManifest(fulfillments={"act_pending": fulfillment}),
    )

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert [item.status for item in report.items] == ["skipped_fulfilled", "retired"]
    assert event_id not in client.events
    retired = load_manifest(repo)
    assert "pending-run" not in retired.pending
    assert retired.retired_pending["pending-run"].remote_event_id == event_id


def test_early_fulfillment_retires_interrupted_update_and_previous_event(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("interrupted-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    event_id = service.reconcile_week(1, as_of_date=date(2026, 8, 9)).items[0].event_id
    manifest = load_manifest(repo)
    published = manifest.workouts["interrupted-run"]
    manifest.pending["interrupted-run"] = PendingWorkoutPublication(
        workout_identity=published.workout_identity,
        applied_week_approval_id=published.applied_week_approval_id,
        applied_running_workouts_sha256=published.applied_running_workouts_sha256,
        workout_prescription_sha256=published.workout_prescription_sha256,
        schedule_timezone=published.schedule_timezone,
        uid=published.uid,
        external_id=published.external_id,
        publication_fingerprint_sha256=published.publication_fingerprint_sha256,
        rendered_workout_sha256=published.rendered_workout_sha256,
        sport_settings_version_sha256=published.sport_settings_version_sha256,
        sport=published.sport,
        occurrence_date=published.occurrence_date,
        approved_start_time_local=published.approved_start_time_local,
        provider_start_date_local=published.provider_start_date_local,
        prepared_at_utc=datetime(2026, 8, 9, 10, tzinfo=timezone.utc),
    )
    save_manifest(repo, manifest)
    activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_interrupted",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_interrupted",
        workout_identity=workout.identity,
        applied_week_approval_id=workout.applied_week_approval_id,
        applied_running_workouts_sha256=workout.applied_running_workouts_sha256,
        workout_prescription_sha256=published.workout_prescription_sha256,
        activity_performance_evidence_sha256=activity_evidence_sha256,
        schedule_timezone=workout.schedule_timezone,
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
        WorkoutFulfillmentManifest(fulfillments={fulfillment.local_activity_id: fulfillment}),
    )

    report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert [item.status for item in report.items] == ["skipped_fulfilled", "retired"]
    assert event_id not in client.events
    retired = load_manifest(repo)
    assert "interrupted-run" not in retired.workouts
    assert "interrupted-run" not in retired.pending
    assert retired.retired["interrupted-run"].provider_deletion_status == "deleted"
    assert retired.retired_pending["interrupted-run"].provider_deletion_status == "no_remote_event"


def test_revoking_early_fulfillment_reopens_and_republishes_retired_workout(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workout = _authoritative(_targetless_run("reopened-run", date(2026, 8, 11)))
    service = HarnessRunWeekSynchronizationService(repo, client, [workout])
    original_event_id = (
        service.reconcile_week(
            1,
            as_of_date=date(2026, 8, 9),
        )
        .items[0]
        .event_id
    )
    publication = load_manifest(repo).workouts["reopened-run"]
    activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_reopened",
        execution_date=date(2026, 8, 10),
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="act_reopened",
        workout_identity=workout.identity,
        applied_week_approval_id=workout.applied_week_approval_id,
        applied_running_workouts_sha256=workout.applied_running_workouts_sha256,
        workout_prescription_sha256=publication.workout_prescription_sha256,
        activity_performance_evidence_sha256=activity_evidence_sha256,
        schedule_timezone=workout.schedule_timezone,
        scheduled_local_date=date(2026, 8, 11),
        execution_local_date=date(2026, 8, 10),
        schedule_offset_days=-1,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the early association.",
            coaching_rationale="The athlete identified this run as the approved easy workout.",
            confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(fulfillments={"act_reopened": fulfillment}),
    )
    retired_report = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert [item.status for item in retired_report.items] == [
        "skipped_fulfilled",
        "retired",
    ]
    assert original_event_id not in client.events
    retirement_recorded_at_utc = load_manifest(repo).retired["reopened-run"].retired_at_utc

    from resilio.core.workout_publication import retirement_reopening

    original_save_manifest = retirement_reopening.save_manifest
    save_attempt_count = 0

    def fail_first_reopening_save(target_repo, manifest):
        nonlocal save_attempt_count
        save_attempt_count += 1
        if save_attempt_count == 1:
            raise OSError("simulated reopening persistence failure")
        return original_save_manifest(target_repo, manifest)

    monkeypatch.setattr(retirement_reopening, "save_manifest", fail_first_reopening_save)
    revocation_arguments = dict(
        local_activity_id="act_reopened",
        local_workout_id="reopened-run",
        reason="activity_deleted",
        athlete_confirmation_reference=(
            "Athlete confirmed the provider activity was deleted and no longer fulfills it."
        ),
        coaching_rationale=(
            "The deleted activity cannot remain evidence for the approved running workout."
        ),
        revoked_at_utc=retirement_recorded_at_utc + timedelta(seconds=1),
    )
    fulfillment_service = WorkoutFulfillmentService(repo)
    with pytest.raises(OSError, match="simulated reopening persistence failure"):
        fulfillment_service.revoke(**revocation_arguments)

    revocation = fulfillment_service.revoke(**revocation_arguments)

    reopened_manifest = load_manifest(repo)
    assert (
        reopened_manifest.retired["reopened-run"].reopened_by_fulfillment_revocation_id
        == revocation.revocation_id
    )
    republished = service.reconcile_week(1, as_of_date=date(2026, 8, 10))
    assert [item.status for item in republished.items] == ["created"]
    assert republished.items[0].event_id != original_event_id
    assert "reopened-run" in load_manifest(repo).workouts

    second_activity_evidence_sha256 = _save_fulfillment_activity(
        repo,
        local_activity_id="act_reopened_second",
        execution_date=date(2026, 8, 10),
    )
    second_fulfillment = fulfillment.model_copy(
        update={
            "local_activity_id": "act_reopened_second",
            "activity_performance_evidence_sha256": (second_activity_evidence_sha256),
            "athlete_confirmation": fulfillment.athlete_confirmation.model_copy(
                update={
                    "candidate_sha256": "5" * 64,
                    "confirmed_at_utc": datetime(
                        2026,
                        8,
                        10,
                        23,
                        30,
                        tzinfo=timezone.utc,
                    ),
                }
            ),
            "recorded_at_utc": datetime(
                2026,
                8,
                10,
                23,
                30,
                tzinfo=timezone.utc,
            ),
        }
    )
    fulfillment_manifest = load_fulfillment_manifest(repo)
    fulfillment_manifest.fulfillments = {second_fulfillment.local_activity_id: second_fulfillment}
    save_fulfillment_manifest(repo, fulfillment_manifest)

    second_retirement = service.reconcile_week(1, as_of_date=date(2026, 8, 10))

    assert [item.status for item in second_retirement.items] == [
        "skipped_fulfilled",
        "retired",
    ]
    twice_retired_manifest = load_manifest(repo)
    assert len(twice_retired_manifest.retirement_history) == 1
    assert (
        twice_retired_manifest.retirement_history[0].reopened_by_fulfillment_revocation_id
        == revocation.revocation_id
    )
    assert (
        twice_retired_manifest.retired["reopened-run"].fulfilling_local_activity_id
        == "act_reopened_second"
    )


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
