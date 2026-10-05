"""Macro amendments preserve temporal authority and provider ownership."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from resilio.core.planning.amendments import apply_macro_amendment, validate_macro_amendment
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.planning.integrity import sha256_file
from resilio.core.planning.service import (
    PlanOperationError,
    apply_approved_week,
    approve_week_application,
    load_approved_workouts_for_date_range,
    load_planning_aggregate,
)
from resilio.core.planning.weekly_context import create_week_planning_context
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.week_service import RunWeekSynchronizationService
from tests.progression_helpers import bind_test_candidate
from tests.unit import test_planning_lifecycle as lifecycle
from tests.unit.test_planning_lifecycle import _apply_test_week, _write_application
from tests.unit.test_workout_publication import FakeClient

AMENDED_AT = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    return lifecycle.repo.__wrapped__(tmp_path, monkeypatch)


def _proposal(repo: RepositoryIO, tmp_path: Path, *, week_number=1, at=AMENDED_AT) -> Path:
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_plan is not None
    reference = create_week_planning_context(
        repo,
        week_number=week_number,
        evidence_as_of_date=at.date(),
        history_week_count=2,
        generated_at_utc=at,
        current_local_date=at.date(),
    )
    week = state.active_plan.plan.weeks[week_number - 1].model_dump(mode="json")
    week["running_workouts"] = []
    week["target_run_volume_meters"] = 11_000
    week["workout_structure_hints"]["long_run"]["maximum_weekly_run_volume_percent"] = 60
    week["workout_structure_hints"]["long_run"]["target_distance_meters"] = 5_000
    path = tmp_path / "amendment.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "expected_active_plan_sha256": canonical_data_sha256(state.active_plan),
                "weeks": [week],
                "planning_context_references": [reference.model_dump(mode="json")],
                "rationale": (
                    "Extend the upcoming easy long run while keeping other sessions and "
                    "intensity unchanged; athlete approved the exact revised weekly target."
                ),
            }
        )
    )
    from tests.progression_helpers import bind_test_candidate

    bind_test_candidate(repo, path, kind="amendment", at=at)
    return path


def _apply(repo: RepositoryIO, path: Path, at: datetime = AMENDED_AT):
    return apply_macro_amendment(
        repo,
        path,
        expected_file_sha256=sha256_file(path),
        athlete_confirmation_reference=(
            "Apply the reviewed macro amendment and preserve " "completed training history."
        ),
        applied_at_utc=at,
    )


def test_amendment_retires_future_week_without_rewriting_original_authority(repo, tmp_path):
    _apply_test_week(repo, tmp_path)
    original = load_planning_aggregate(repo)
    path = _proposal(repo, tmp_path)
    validation = validate_macro_amendment(repo, path, evaluated_at_utc=AMENDED_AT)
    assert validation.retired_week_numbers == [1]
    assert load_planning_aggregate(repo) == original
    result = _apply(repo, path)
    active = result.active_plan
    assert active is not None and original.active_plan is not None
    assert active.plan.id == original.active_plan.plan.id
    assert active.plan.plan_revision_id == original.active_plan.plan.plan_revision_id
    assert active.plan.weeks[0].target_run_volume_meters == 11_000
    assert active.plan.weeks[0].running_workouts == []
    assert not active.applied_week_revisions[0].active
    assert (
        active.applied_week_revisions[0].applied_week_snapshot == original.active_plan.plan.weeks[0]
    )
    assert active.macro_amendments[0].previous_plan == original.active_plan.plan
    assert active.macro_amendments[0].previous_plan_approval == original.active_plan.plan_approval
    assert active.plan_approval.approved_at_utc == AMENDED_AT


@pytest.mark.parametrize(
    "failure", ["stale_state", "file_changed", "past_week", "no_confirmation", "invalid_share"]
)
def test_amendment_failure_preserves_state(repo, tmp_path, failure):
    _apply_test_week(repo, tmp_path)
    path = _proposal(repo, tmp_path)
    state = load_planning_aggregate(repo)
    payload = json.loads(path.read_text())
    digest = sha256_file(path)
    at = AMENDED_AT
    confirmation = "Apply the reviewed macro amendment."
    if failure == "stale_state":
        payload["expected_active_plan_sha256"] = "0" * 64
    elif failure == "past_week":
        at = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
    elif failure == "no_confirmation":
        confirmation = ""
    elif failure == "invalid_share":
        payload["weeks"][0]["workout_structure_hints"]["long_run"]["target_distance_meters"] = 7_000
    else:
        payload["rationale"] += " Changed after review."
    path.write_text(json.dumps(payload))
    if failure != "file_changed":
        digest = sha256_file(path)
    with pytest.raises(PlanOperationError):
        apply_macro_amendment(
            repo,
            path,
            expected_file_sha256=digest,
            athlete_confirmation_reference=confirmation,
            applied_at_utc=at,
        )
    assert load_planning_aggregate(repo) == state


def test_amended_week_republishes_using_retained_provider_ownership(repo, tmp_path):
    _apply_test_week(repo, tmp_path)
    client = FakeClient()
    service = RunWeekSynchronizationService(repo, client)
    before = service.reconcile_week(1, as_of_date=date(2026, 7, 27))
    assert before.reconciliation_safe
    original_remote_ids = set(client.events)
    _apply(repo, _proposal(repo, tmp_path))
    replacement = tmp_path / "replacement.json"
    _write_application(replacement, repo=repo)
    payload = json.loads(replacement.read_text())
    payload["running_workouts"][-1]["planned_distance_meters"] = 5_000
    replacement.write_text(json.dumps(payload))
    from tests.progression_helpers import bind_test_candidate

    bind_test_candidate(repo, replacement, kind="week", at=AMENDED_AT)
    approve_week_application(
        repo, replacement, approved_at_utc=datetime(2026, 7, 27, 13, tzinfo=timezone.utc)
    )
    apply_approved_week(
        repo, replacement, applied_at_utc=datetime(2026, 7, 27, 14, tzinfo=timezone.utc)
    )
    after = service.reconcile_week(1, as_of_date=date(2026, 7, 27))
    assert after.reconciliation_safe and not after.partial
    assert set(client.events) == original_remote_ids
    assert all(item.status != "created" for item in after.items)
    history = load_approved_workouts_for_date_range(
        repo, window_start=date(2026, 7, 27), window_end=date(2026, 8, 2)
    )
    assert history.status == "available"
    assert len(history.workouts) == 3
    assert history.workouts[-1].prescription.planned_distance_meters == 5_000


def test_future_amendment_preserves_completed_week_adherence(repo, tmp_path):
    from resilio.core.planning.service import approve_current_plan, create_macro_plan
    from resilio.schemas.macro_plan_draft import MacroPlanDraft
    from tests.unit.test_planning_lifecycle import _approve_vdot, _draft

    draft = _draft(_approve_vdot(repo, tmp_path)).model_dump(mode="python")
    second = dict(draft["weeks"][0])
    second.update(week_number=2, start_date=date(2026, 8, 3), end_date=date(2026, 8, 9))
    draft["weeks"].append(second)
    draft_path = tmp_path / "two-week-macro.json"
    draft_path.write_text(MacroPlanDraft.model_validate(draft).model_dump_json())
    bind_test_candidate(
        repo, draft_path, kind="macro", at=datetime(2026, 7, 26, tzinfo=timezone.utc)
    )
    draft = json.loads(draft_path.read_text())
    create_macro_plan(
        repo,
        MacroPlanDraft.model_validate(draft),
        created_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    approve_current_plan(repo, approved_at_utc=datetime(2026, 7, 26, 12, tzinfo=timezone.utc))
    original_week = tmp_path / "original-week.json"
    _write_application(original_week, repo=repo)
    approve_week_application(
        repo, original_week, approved_at_utc=datetime(2026, 7, 26, 13, tzinfo=timezone.utc)
    )
    apply_approved_week(
        repo, original_week, applied_at_utc=datetime(2026, 7, 26, 14, tzinfo=timezone.utc)
    )
    original = load_planning_aggregate(repo)
    at = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
    path = _proposal(repo, tmp_path, week_number=2, at=at)
    _apply(repo, path, at=at)
    after = load_planning_aggregate(repo)
    assert after.active_plan.plan.weeks[0] == original.active_plan.plan.weeks[0]
    assert after.active_plan.applied_week_revisions == original.active_plan.applied_week_revisions
    window = load_approved_workouts_for_date_range(
        repo, window_start=date(2026, 7, 27), window_end=date(2026, 8, 2)
    )
    assert window.status == "available" and len(window.workouts) == 3
    assert [w.prescription.planned_distance_meters for w in window.workouts] == [3000, 3000, 4000]


def test_second_amendment_keeps_continuous_approval_chain(repo, tmp_path):
    _apply_test_week(repo, tmp_path)
    _apply(repo, _proposal(repo, tmp_path))
    at = datetime(2026, 7, 27, 13, tzinfo=timezone.utc)
    path = _proposal(repo, tmp_path, at=at)
    payload = json.loads(path.read_text())
    payload["weeks"][0]["target_run_volume_meters"] = 12000
    path.write_text(json.dumps(payload))
    bind_test_candidate(repo, path, kind="amendment", at=at)
    result = _apply(repo, path, at=at)
    first, second = result.active_plan.macro_amendments
    assert second.previous_plan_approval == first.approval
    assert second.approval == result.active_plan.plan_approval
    assert load_planning_aggregate(repo) == result


def test_populated_week_with_elapsed_workout_is_protected(repo, tmp_path):
    _apply_test_week(repo, tmp_path)
    at = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
    path = _proposal(repo, tmp_path, at=at)
    state = load_planning_aggregate(repo)
    with pytest.raises(PlanOperationError, match="elapsed workouts"):
        _apply(repo, path, at=at)
    assert load_planning_aggregate(repo) == state


@pytest.mark.parametrize("field", ["purpose", "notes"])
def test_retained_macro_snapshot_rejects_prescription_and_notes_tampering(repo, tmp_path, field):
    from resilio.core.planning.state_repository import persist_planning_state

    _apply_test_week(repo, tmp_path)
    state = _apply(repo, _proposal(repo, tmp_path))
    prior = state.active_plan.macro_amendments[0].previous_plan
    if field == "purpose":
        prior.weeks[0].running_workouts[0].purpose = "Tampered historical workout prescription."
    else:
        prior.weeks[0].notes = "Tampered historical week notes."
    persist_planning_state(repo, state)
    with pytest.raises(PlanOperationError, match="snapshot changed"):
        load_planning_aggregate(repo)


def test_retired_workout_ids_remain_reserved_to_their_original_week(repo, tmp_path):
    from resilio.core.planning.weekly_service import _validate_workout_ids_are_globally_unique
    from resilio.schemas.planning.weeks import WeekPlan

    _apply_test_week(repo, tmp_path)
    state = _apply(repo, _proposal(repo, tmp_path))
    previous = state.active_plan.macro_amendments[0].previous_plan.weeks[0]
    data = previous.model_dump(mode="python")
    data.update(week_number=2, start_date=date(2026, 8, 3), end_date=date(2026, 8, 9))
    for workout in data["running_workouts"]:
        workout["date"] = date(2026, 8, 4)
        workout["start_time_local"] = None
    populated = WeekPlan.model_validate(data)
    with pytest.raises(PlanOperationError, match="another plan or week"):
        _validate_workout_ids_are_globally_unique(repo, state, populated)


def test_archive_integrity_hashes_stored_bytes_before_materializing_new_defaults(repo, tmp_path):
    import hashlib

    from resilio.core.planning.artifacts import (
        archived_active_plan_sha256,
        load_closed_plan_archive,
    )
    from resilio.schemas.approvals import ClosedPlanArchive
    from resilio.schemas.plan_history import ClosedPlanReference

    _apply_test_week(repo, tmp_path)
    state = load_planning_aggregate(repo)
    active = state.active_plan.model_dump(mode="json", by_alias=True)
    active.pop("macro_amendments")
    closure = {
        "closure_kind": "race_cycle",
        "effective_end_date": "2026-07-27",
        "disposition": "superseded_midcycle",
        "goal_outcome": {
            "status": "did_not_start",
            "athlete_confirmation_reference": "The race has not occurred yet.",
        },
        "closed_at_utc": "2026-07-27T12:00:00Z",
        "reason": "Replace this training cycle after athlete review.",
        "athlete_confirmation_reference": "Close the reviewed training cycle.",
        "cycle_review_artifact_sha256": "a" * 64,
    }
    payload = {"schema_version": 3, "active_plan_snapshot": active, "closure": closure}
    # Validate the persisted document without making added defaults part of its identity.
    ClosedPlanArchive.model_validate(payload)
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()
    archive_path = repo.resolve_path("data/plans/archive/" + active["plan"]["id"] + ".json")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(encoded)
    reference = ClosedPlanReference(
        plan_id=active["plan"]["id"],
        plan_revision_id=active["plan"]["plan_revision_id"],
        archive_sha256=hashlib.sha256(encoded).hexdigest(),
        closed_at_utc=datetime(2026, 7, 27, 12, tzinfo=timezone.utc),
    )
    loaded = load_closed_plan_archive(repo, reference)
    assert loaded.active_plan_snapshot.macro_amendments == []
    assert archived_active_plan_sha256(loaded) == canonical_data_sha256(active)
    from types import SimpleNamespace

    from resilio.core.workout_fulfillment.planning_state_migration import (
        _validate_source_review_binding,
    )
    from resilio.schemas.plan_history import EvidenceArtifactReference

    source_review = {
        "plan_id": active["plan"]["id"],
        "plan_revision_id": active["plan"]["plan_revision_id"],
        "active_plan_sha256": canonical_data_sha256(active),
        "effective_end_date": "2026-07-27",
        "goal_outcome": loaded.closure.goal_outcome.model_dump(mode="json"),
    }
    graph = SimpleNamespace(source_payload=lambda reference: source_review)
    _validate_source_review_binding(
        archive=loaded,
        reference=EvidenceArtifactReference(artifact_type="cycle_review", artifact_sha256="a" * 64),
        graph=graph,
    )


def test_amendment_history_rejects_truncating_its_oldest_record(repo, tmp_path):
    from resilio.core.planning.state_repository import persist_planning_state

    _apply_test_week(repo, tmp_path)
    _apply(repo, _proposal(repo, tmp_path))
    at = datetime(2026, 7, 27, 13, tzinfo=timezone.utc)
    path = _proposal(repo, tmp_path, at=at)
    payload = json.loads(path.read_text())
    payload["weeks"][0]["target_run_volume_meters"] = 12000
    path.write_text(json.dumps(payload))
    bind_test_candidate(repo, path, kind="amendment", at=at)
    state = _apply(repo, path, at=at)
    state.active_plan.macro_amendments.pop(0)
    # Retain no weekly records so their temporal check cannot mask chain truncation.
    state.active_plan.applied_week_revisions = []
    persist_planning_state(repo, state)
    with pytest.raises(PlanOperationError, match="truncated"):
        load_planning_aggregate(repo)


def test_cli_exact_amendment_boundary_applies_without_calendar_mutation(
    repo, tmp_path, monkeypatch
):
    from typer.testing import CliRunner

    import resilio.core.planning.amendments as amendment_module
    from resilio.cli.commands.plan import app

    _apply_test_week(repo, tmp_path)
    path = _proposal(repo, tmp_path)
    monkeypatch.setattr(amendment_module, "validated_utc_timestamp", lambda value: AMENDED_AT)
    runner = CliRunner()
    validation = runner.invoke(app, ["validate-amendment", "--file", str(path)])
    assert validation.exit_code == 0, validation.output
    digest = json.loads(validation.output)["data"]["file_sha256"]
    applied = runner.invoke(
        app,
        [
            "apply-amendment",
            "--file",
            str(path),
            "--sha256",
            digest,
            "--athlete-confirmation",
            "Apply the exact reviewed amendment.",
        ],
    )
    assert applied.exit_code == 0, applied.output
    result = json.loads(applied.output)["data"]
    assert result["local_application_status"] == "applied"
    assert result["workout_synchronization_status"] == "requires_weekly_approval_and_application"


def test_whole_amendment_review_is_shared_across_all_affected_contexts(repo, tmp_path):
    from resilio.core.planning.artifacts import load_evidence_artifact
    from resilio.core.planning.service import approve_current_plan, create_macro_plan
    from resilio.schemas.coaching import WeekPlanningContext
    from resilio.schemas.macro_plan_draft import MacroPlanDraft
    from resilio.schemas.plan_history import EvidenceArtifactReference
    from resilio.schemas.planning.amendments import MacroAmendmentProposal
    from tests.unit.test_planning_lifecycle import _approve_vdot, _draft

    draft = _draft(_approve_vdot(repo, tmp_path)).model_dump(mode="json")
    second = dict(draft["weeks"][0])
    second.update(week_number=2, start_date="2026-08-03", end_date="2026-08-09")
    draft["weeks"].append(second)
    macro_path = tmp_path / "shared-review-macro.json"
    macro_path.write_text(json.dumps(draft))
    bind_test_candidate(
        repo, macro_path, kind="macro", at=datetime(2026, 7, 26, tzinfo=timezone.utc)
    )
    create_macro_plan(
        repo,
        MacroPlanDraft.model_validate_json(macro_path.read_bytes()),
        created_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    approve_current_plan(repo, approved_at_utc=datetime(2026, 7, 26, 12, tzinfo=timezone.utc))
    path = _proposal(repo, tmp_path)
    payload = json.loads(path.read_bytes())
    state = load_planning_aggregate(repo)
    second = state.active_plan.plan.weeks[1].model_dump(mode="json")
    second["target_run_volume_meters"] = 11000
    second["workout_structure_hints"]["long_run"]["target_distance_meters"] = 5000
    second["workout_structure_hints"]["long_run"]["maximum_weekly_run_volume_percent"] = 60
    payload["weeks"].append(second)
    reference = create_week_planning_context(
        repo,
        week_number=2,
        evidence_as_of_date=AMENDED_AT.date(),
        history_week_count=1,
        generated_at_utc=AMENDED_AT,
        current_local_date=AMENDED_AT.date(),
    )
    payload["planning_context_references"].append(reference.model_dump(mode="json"))
    path.write_text(json.dumps(payload))
    bind_test_candidate(repo, path, kind="amendment", at=AMENDED_AT)
    proposal = MacroAmendmentProposal.model_validate_json(path.read_bytes())
    first_context = load_evidence_artifact(
        repo, proposal.planning_context_references[0], WeekPlanningContext
    )
    second_context = load_evidence_artifact(
        repo, proposal.planning_context_references[1], WeekPlanningContext
    )
    assert isinstance(second_context.progression, EvidenceArtifactReference)
    assert second_context.progression == proposal.planning_context_references[0]
    assert len(first_context.progression.assessment.weeks) == 2
    assert second_context.recent_history.requested_week_count == 6
    result = _apply(repo, path)
    assert result.active_plan.macro_amendments[0].affected_week_numbers == [1, 2]
