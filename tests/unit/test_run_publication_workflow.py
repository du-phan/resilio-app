"""Run-only capability, preference, and approved-week publication tests."""

from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from resilio.api import week_application as week_application_api
from resilio.api.publication import PublicationError
from resilio.core.locking import OperationLock, OperationLockError
from resilio.core.planning.constants import PLAN_MUTATION_LOCK_PATH
from resilio.core.planning.integrity import applied_running_workouts_sha256
from resilio.core.repository import RepositoryIO
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
    retained_publication_authorities,
)
from resilio.integrations.intervals_icu.errors import IntervalsTransportError
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    RunWeekSynchronizationReport,
    RunWorkoutSynchronizationPreferences,
)
from resilio.schemas.publication_placement import ProviderOccurrencePlacement
from tests.unit.run_publication_workflow_support import (
    HarnessRunWeekSynchronizationService,
    _authoritative,
    _pace_targeted_run,
    _targetless_run,
)
from tests.unit.test_workout_publication import FakeClient


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
        PublicationManifest(
            pending={"unrelated-run": pending},
            pending_provider_occurrence_placements={
                "unrelated-run": ProviderOccurrencePlacement.approved_schedule(
                    pending.occurrence_date
                )
            },
        ),
    )
    monkeypatch.setattr(
        retained_authority_module,
        "required_planning_state_unlocked",
        lambda _repo: SimpleNamespace(active_plan=SimpleNamespace(applied_week_revisions=[])),
    )

    authorities = retained_publication_authorities(repo, [current])

    assert authorities == {}


def test_removed_published_workout_recovers_its_exact_applied_authority(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    client = FakeClient()
    prescription = _targetless_run("removed-run", date(2026, 8, 11))
    snapshot = SimpleNamespace(running_workouts=[prescription])
    applied_sha256 = applied_running_workouts_sha256(snapshot)
    removed = replace(
        _authoritative(prescription),
        applied_running_workouts_sha256=applied_sha256,
    )
    HarnessRunWeekSynchronizationService(repo, client, [removed]).reconcile_week(
        1,
        as_of_date=date(2026, 8, 10),
    )
    applied_revision = SimpleNamespace(
        approval_id=removed.applied_week_approval_id,
        plan_id=removed.identity.plan_id,
        plan_revision_id=removed.identity.plan_revision_id,
        week_number=removed.identity.week_number,
        applied_running_workouts_sha256=applied_sha256,
        applied_week_snapshot=snapshot,
        schedule_timezone=removed.schedule_timezone,
    )
    monkeypatch.setattr(
        retained_authority_module,
        "required_planning_state_unlocked",
        lambda _repo: SimpleNamespace(
            active_plan=SimpleNamespace(applied_week_revisions=[applied_revision])
        ),
    )
    replacement = _authoritative(_targetless_run("replacement-run", date(2026, 8, 12)))

    authorities = retained_publication_authorities(repo, [replacement])

    recovered_authority = authorities["removed-run"].published
    assert recovered_authority is not None
    recovered = recovered_authority.workout
    assert recovered.identity == removed.identity
    assert recovered.prescription == removed.prescription
    assert recovered.applied_week_approval_id == removed.applied_week_approval_id
    assert recovered.applied_running_workouts_sha256 == removed.applied_running_workouts_sha256
    assert (
        recovered_authority.provider_name == provider_workout_names([prescription])["removed-run"]
    )


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
