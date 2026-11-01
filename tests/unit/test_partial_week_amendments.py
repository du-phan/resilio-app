"""Upcoming revisions preserve elapsed and exactly fulfilled prescriptions."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from resilio.canonical import canonical_data_sha256
from resilio.core.activity_sync.evidence_identity import activity_performance_evidence_sha256
from resilio.core.planning.service import (
    PlanOperationError,
    apply_approved_week,
    approve_week_application,
    load_approved_workouts_for_date_range,
    load_planning_aggregate,
)
from resilio.core.planning.weekly_context import create_week_planning_context
from resilio.core.planning.weekly_service import validate_week_application
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import save_fulfillment_manifest
from resilio.core.workout_publication.week_service import RunWeekSynchronizationService
from resilio.schemas.workout_fulfillment import (
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from tests.progression_helpers import bind_test_candidate
from tests.unit import test_macro_amendments as amendments
from tests.unit import test_planning_lifecycle as lifecycle
from tests.unit.test_workout_publication import FakeClient

MIDWEEK = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    return lifecycle.repo.__wrapped__(tmp_path, monkeypatch)


def _replacement(repo: RepositoryIO, tmp_path: Path, *, at=MIDWEEK) -> Path:
    payload = json.loads((tmp_path / "week.json").read_text())
    payload["running_workouts"][-1]["planned_distance_meters"] = 5_000
    payload["running_workouts"][-1]["structured_workout"]["steps"][0]["duration"] = {
        "unit": "meters",
        "value": 5_000,
        "nominal_seconds": 2_400,
    }
    reference = create_week_planning_context(
        repo,
        week_number=1,
        evidence_as_of_date=at.date(),
        history_week_count=2,
        generated_at_utc=at,
        current_local_date=at.date(),
    )
    payload["planning_context_reference"] = reference.model_dump(mode="json")
    path = tmp_path / "partial-week-replacement.json"
    path.write_text(json.dumps(payload))
    bind_test_candidate(repo, path, kind="week", at=at)
    return path


def _amend_midweek(repo: RepositoryIO, tmp_path: Path):
    return amendments._apply(repo, amendments._proposal(repo, tmp_path, at=MIDWEEK), at=MIDWEEK)


def test_partial_week_revision_preserves_history_and_remote_identity(repo, tmp_path):
    lifecycle._apply_test_week(repo, tmp_path)
    original = load_planning_aggregate(repo)
    client = FakeClient()
    publication = RunWeekSynchronizationService(repo, client)
    publication.reconcile_week(1, as_of_date=date(2026, 7, 27))
    remote_before = dict(client.events)

    _amend_midweek(repo, tmp_path)
    path = _replacement(repo, tmp_path)
    approve_week_application(repo, path, approved_at_utc=MIDWEEK + timedelta(minutes=1))
    apply_approved_week(repo, path, applied_at_utc=MIDWEEK + timedelta(minutes=2))

    state = load_planning_aggregate(repo)
    assert original.active_plan is not None and state.active_plan is not None
    assert state.active_plan.plan.weeks[0].running_workouts[0] == (
        original.active_plan.plan.weeks[0].running_workouts[0]
    )
    history = load_approved_workouts_for_date_range(
        repo, window_start=date(2026, 7, 28), window_end=date(2026, 7, 28)
    )
    assert history.status == "available" and len(history.workouts) == 1
    assert history.workouts[0].applied_week_approval_id == (
        original.active_plan.applied_week_revisions[0].approval_id
    )
    result = publication.reconcile_week(1, as_of_date=date(2026, 7, 29))
    assert result.reconciliation_safe and not result.partial
    assert set(client.events) == set(remote_before)
    assert not any(item.status == "created" for item in result.items)
    elapsed = next(
        event for event in remote_before.values() if event.start_date_local.startswith("2026-07-28")
    )
    assert client.events[elapsed.id] == elapsed
    revised_long = next(
        event for event in client.events.values() if event.start_date_local.startswith("2026-08-01")
    )
    assert revised_long.workout_doc.steps[0].distance_meters == 5_000


@pytest.mark.parametrize("change", ["purpose", "remove", "identity", "date", "distance"])
def test_partial_week_replacement_rejects_changes_to_elapsed_run(repo, tmp_path, change):
    lifecycle._apply_test_week(repo, tmp_path)
    _amend_midweek(repo, tmp_path)
    path = _replacement(repo, tmp_path)
    payload = json.loads(path.read_text())
    first = payload["running_workouts"][0]
    if change == "remove":
        payload["running_workouts"].pop(0)
    elif change == "identity":
        first["id"] = "new_past_workout"
    elif change == "date":
        first["date"] = "2026-07-29"
    elif change == "distance":
        first["planned_distance_meters"] += 100
    else:
        first["purpose"] = "Rewrite the historical missed-run intent."
    path.write_text(json.dumps(payload))
    before = load_planning_aggregate(repo)
    with pytest.raises(PlanOperationError, match="elapsed workout"):
        approve_week_application(repo, path, approved_at_utc=MIDWEEK + timedelta(minutes=1))
    assert load_planning_aggregate(repo) == before


def test_validation_cannot_add_a_backdated_run(repo, tmp_path, monkeypatch):
    lifecycle._apply_test_week(repo, tmp_path)
    _amend_midweek(repo, tmp_path)
    path = _replacement(repo, tmp_path)
    payload = json.loads(path.read_text())
    added = dict(payload["running_workouts"][1])
    added.update(id="invented_elapsed_run", date="2026-07-27")
    payload["running_workouts"].append(added)
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(
        "resilio.core.planning.weekly_service.validated_utc_timestamp", lambda _: MIDWEEK
    )
    with pytest.raises(PlanOperationError, match="backdated"):
        validate_week_application(repo, path)


def test_application_rechecks_a_workout_that_elapsed_after_approval(repo, tmp_path):
    lifecycle._apply_test_week(repo, tmp_path)
    _amend_midweek(repo, tmp_path)
    path = _replacement(repo, tmp_path)
    payload = json.loads(path.read_text())
    payload["running_workouts"][1]["purpose"] = "Change tomorrow's supporting run."
    path.write_text(json.dumps(payload))
    bind_test_candidate(repo, path, kind="week", at=MIDWEEK)
    approve_week_application(repo, path, approved_at_utc=MIDWEEK + timedelta(minutes=1))
    after_deadline = datetime(2026, 7, 30, 6, tzinfo=timezone.utc)
    before = load_planning_aggregate(repo)
    with pytest.raises(PlanOperationError, match="backdated"):
        apply_approved_week(repo, path, applied_at_utc=after_deadline)
    assert load_planning_aggregate(repo) == before


def _record_early_fulfillment(repo: RepositoryIO, index: int = 1) -> WorkoutFulfillmentRecord:
    state = load_planning_aggregate(repo)
    revision = state.active_plan.applied_week_revisions[-1]
    workout = revision.applied_week_snapshot.running_workouts[index]
    activity = lifecycle.make_activity(
        id="early_completed_run",
        date=date(2026, 7, 29),
        start_time=MIDWEEK - timedelta(hours=2),
        distance_meters=3_000,
    )
    lifecycle.ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    record = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity={
            "plan_id": revision.plan_id,
            "plan_revision_id": revision.plan_revision_id,
            "week_number": revision.week_number,
            "local_workout_id": workout.id,
        },
        applied_week_approval_id=revision.approval_id,
        applied_running_workouts_sha256=revision.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(workout),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=revision.schedule_timezone,
        scheduled_local_date=workout.date,
        execution_local_date=date(2026, 7, 29),
        schedule_offset_days=(date(2026, 7, 29) - workout.date).days,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed", event_id=42, observed_at_utc=MIDWEEK
        ),
        recorded_at_utc=MIDWEEK,
    )
    save_fulfillment_manifest(
        repo, WorkoutFulfillmentManifest(fulfillments={record.local_activity_id: record})
    )
    return record


def test_early_fulfillment_is_preserved_after_macro_retirement(repo, tmp_path):
    lifecycle._apply_test_week(repo, tmp_path)
    _record_early_fulfillment(repo)
    _amend_midweek(repo, tmp_path)
    path = _replacement(repo, tmp_path)
    approve_week_application(repo, path, approved_at_utc=MIDWEEK + timedelta(minutes=1))
    apply_approved_week(repo, path, applied_at_utc=MIDWEEK + timedelta(minutes=2))


@pytest.mark.parametrize("change", ["purpose", "remove"])
def test_inactive_early_fulfillment_cannot_be_changed(repo, tmp_path, change):
    lifecycle._apply_test_week(repo, tmp_path)
    _record_early_fulfillment(repo)
    _amend_midweek(repo, tmp_path)
    path = _replacement(repo, tmp_path)
    payload = json.loads(path.read_text())
    if change == "remove":
        payload["running_workouts"].pop(1)
    else:
        payload["running_workouts"][1]["purpose"] = "Alter a run already completed early."
    path.write_text(json.dumps(payload))
    before = load_planning_aggregate(repo)
    with pytest.raises(PlanOperationError, match="fulfilled workout"):
        approve_week_application(repo, path, approved_at_utc=MIDWEEK + timedelta(minutes=1))
    assert load_planning_aggregate(repo) == before


@pytest.mark.parametrize(
    "field",
    ["applied_week_approval_id", "applied_running_workouts_sha256", "schedule_timezone"],
)
def test_fulfillment_requires_one_complete_retained_authority(repo, tmp_path, field):
    lifecycle._apply_test_week(repo, tmp_path)
    record = _record_early_fulfillment(repo)
    _amend_midweek(repo, tmp_path)
    path = _replacement(repo, tmp_path)
    values = record.model_dump(mode="python")
    values[field] = {
        "applied_week_approval_id": "week_approval_" + "f" * 16,
        "applied_running_workouts_sha256": "f" * 64,
        "schedule_timezone": "America/New_York",
    }[field]
    changed = WorkoutFulfillmentRecord.model_validate(values)
    save_fulfillment_manifest(
        repo, WorkoutFulfillmentManifest(fulfillments={changed.local_activity_id: changed})
    )
    with pytest.raises(PlanOperationError, match="retained applied-week authority"):
        approve_week_application(repo, path, approved_at_utc=MIDWEEK + timedelta(minutes=1))


def test_latest_prescription_revised_before_its_deadline_becomes_protected(repo, tmp_path):
    lifecycle._apply_test_week(repo, tmp_path)
    path = tmp_path / "early-replacement.json"
    payload = json.loads((tmp_path / "week.json").read_text())
    payload["running_workouts"][0]["purpose"] = "Revised while this run was still upcoming."
    path.write_text(json.dumps(payload))
    at = datetime(2026, 7, 26, 15, tzinfo=timezone.utc)
    bind_test_candidate(repo, path, kind="week", at=at)
    approve_week_application(repo, path, approved_at_utc=at + timedelta(minutes=1))
    apply_approved_week(repo, path, applied_at_utc=at + timedelta(minutes=2))
    # The original Tuesday content was retired before its deadline. Preserve
    # the later approved Tuesday content without freezing both old versions.
    (tmp_path / "week.json").write_text(json.dumps(payload))
    _amend_midweek(repo, tmp_path)
    replacement = _replacement(repo, tmp_path)
    approve_week_application(repo, replacement, approved_at_utc=MIDWEEK + timedelta(minutes=1))
    apply_approved_week(repo, replacement, applied_at_utc=MIDWEEK + timedelta(minutes=2))
