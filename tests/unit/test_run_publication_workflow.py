"""Run-only capability, preference, and approved-week publication tests."""

from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from resilio.api import week_application as week_application_api
from resilio.api.publication import PublicationError
from resilio.core.locking import OperationLock, OperationLockError
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.constants import PLAN_MUTATION_LOCK_PATH
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.capabilities import (
    get_run_synchronization_capabilities,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.core.workout_publication.preferences import (
    load_run_synchronization_preferences,
    save_run_synchronization_preferences,
)
from resilio.core.workout_publication.week_service import RunWeekSynchronizationService
from resilio.integrations.intervals_icu.errors import IntervalsTransportError
from resilio.schemas.plan import WorkoutPrescription
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import (
    RunWeekSynchronizationReport,
    RunWorkoutSynchronizationPreferences,
)
from tests.unit.test_workout_publication import FakeClient


def _authoritative(workout: WorkoutPrescription) -> AuthoritativeWorkout:
    return AuthoritativeWorkout(
        identity=PlanWorkoutIdentity(
            plan_id="plan_publication_test",
            plan_revision_id="plan_revision_1111111111111111",
            week_number=1,
            local_workout_id=workout.id,
        ),
        prescription=workout,
    )


def _targetless_run(workout_id: str, occurrence: date) -> WorkoutPrescription:
    return WorkoutPrescription.model_validate(
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


def _climb(workout_id: str, occurrence: date) -> WorkoutPrescription:
    return WorkoutPrescription.model_validate(
        {
            "id": workout_id,
            "date": occurrence,
            "sport": "climb",
            "workout_type": "easy",
            "planned_duration_seconds": 3_600,
            "planned_low_intensity_duration_seconds": 600,
            "planned_moderate_intensity_duration_seconds": 2_400,
            "planned_high_intensity_duration_seconds": 600,
            "target_rpe_1_to_10": 5,
            "purpose": "Preserve the normal bouldering commitment.",
        }
    )


def _pace_targeted_run(workout_id: str, occurrence: date) -> WorkoutPrescription:
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
    return WorkoutPrescription.model_validate(payload)


class HarnessRunWeekSynchronizationService(RunWeekSynchronizationService):
    def __init__(self, repo, client, workouts):
        super().__init__(repo, client)
        self.workouts = workouts

    def _load_authoritative_week_unlocked(self, week_number):
        assert week_number == 1
        return self.workouts

    def _completed_workout_identities(self):
        return set()


def test_missing_preferences_are_safely_disabled_and_enabled_state_round_trips(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()

    assert (
        load_run_synchronization_preferences(repo).run_synchronization_mode
        == "disabled"
    )

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
        "applied_workout_sha256",
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
        "applied_workout_sha256",
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
        "applied_workout_sha256",
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


def test_week_status_and_reconciliation_ignore_non_running_workouts(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    workouts = [
        _authoritative(_targetless_run("run-1", date(2026, 8, 6))),
        _authoritative(_climb("climb-1", date(2026, 8, 5))),
    ]
    service = HarnessRunWeekSynchronizationService(repo, client, workouts)

    status = service.status_week(1, as_of_date=date(2026, 8, 2))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 8, 2))

    assert status.reconciliation_safe
    assert status.run_workouts_considered == 1
    assert status.ignored_non_run_workouts == 1
    assert [item.status for item in status.items] == ["ready"]
    assert [item.status for item in reconciled.items] == ["created"]
    assert len(client.events) == 1
    assert next(iter(client.events.values())).type == "Run"


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

    service.workouts = [
        _authoritative(_targetless_run("replacement-run", date(2026, 8, 6)))
    ]
    replacement = service.reconcile_week(1, as_of_date=date(2026, 8, 2))

    assert [item.status for item in replacement.items] == ["created", "deleted"]
    assert old_event_id not in client.events
    assert len(client.events) == 1


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
    old_event_id = service.reconcile_week(
        1,
        as_of_date=date(2026, 8, 2),
    ).items[0].event_id

    service.workouts = [
        _authoritative(_targetless_run("current-past-run", date(2026, 8, 3)))
    ]
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
    service.workouts = [
        _authoritative(_targetless_run("replacement-run", date(2026, 8, 8)))
    ]

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
    service.workouts = [
        _authoritative(_targetless_run("replacement-run", date(2026, 8, 8)))
    ]

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
    service.workouts = [
        _authoritative(_targetless_run("replacement-run", date(2026, 8, 8)))
    ]
    service._completed_workout_identities = lambda: {
        (
            completed.identity.plan_id,
            completed.identity.plan_revision_id,
            completed.identity.week_number,
            completed.identity.local_workout_id,
        )
    }

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
        event.external_id != "resilio:v1:workout:new-run"
        for event in client.events.values()
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

    restored = service.restore_local_week(
        1,
        as_of_date=date(2026, 8, 2),
        athlete_confirmation_reference="Athlete explicitly selected restore-local.",
    )

    assert restored.operation == "restore_local"
    assert restored.reconciliation_safe
    assert [item.status for item in restored.items] == ["updated"]
    assert len(client.events) == 1
    assert client.events[event_id].description.startswith("Easy conversational running.")
    manifest = load_manifest(repo)
    assert manifest.drift_resolutions[-1].strategy == "restore_local"


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
        )

    assert load_manifest(repo).drift_resolutions == []
