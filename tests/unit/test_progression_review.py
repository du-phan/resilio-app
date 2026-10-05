"""Review integrity and freshness at real planning mutation boundaries."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from resilio.core.planning.artifacts import import_evidence_artifact, load_evidence_artifact
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.progression_authoring import assess_progression, bind_progression_review
from resilio.core.planning.service import approve_week_application, load_planning_aggregate
from resilio.schemas.coaching import WeekPlanningContext
from resilio.schemas.planning.applications import WeekApplication
from tests.progression_helpers import bind_test_candidate
from tests.unit import test_planning_lifecycle as lifecycle

AT = datetime(2026, 7, 26, 13, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    return lifecycle.repo.__wrapped__(tmp_path, monkeypatch)


def candidate(repo, tmp_path):
    lifecycle._create_approved_macro(repo, tmp_path)
    path = tmp_path / "candidate.json"
    lifecycle._write_application(path, repo=repo)
    return path


def replace_context(repo, path, mutate):
    application = WeekApplication.model_validate_json(path.read_bytes())
    context = load_evidence_artifact(
        repo, application.planning_context_reference, WeekPlanningContext
    )
    mutate(context)
    reference = import_evidence_artifact(repo, context, artifact_type="week_planning_context")
    path.write_text(
        application.model_copy(update={"planning_context_reference": reference}).model_dump_json()
    )


def test_week_requires_review_and_preserves_state_on_rejection(repo, tmp_path):
    path = candidate(repo, tmp_path)
    replace_context(repo, path, lambda context: setattr(context, "progression", None))
    before = load_planning_aggregate(repo)
    with pytest.raises(PlanOperationError, match="progression review is required"):
        approve_week_application(repo, path, approved_at_utc=AT)
    assert load_planning_aggregate(repo) == before


@pytest.mark.parametrize("change", ["purpose", "duration", "rationale", "date"])
def test_full_candidate_changes_invalidate_review(repo, tmp_path, change):
    path = candidate(repo, tmp_path)
    payload = json.loads(path.read_bytes())
    if change == "purpose":
        payload["running_workouts"][0]["purpose"] += " Revised purpose."
    elif change == "duration":
        workout = payload["running_workouts"][0]
        workout["planned_duration_seconds"] += 30
        workout["planned_low_intensity_duration_seconds"] += 30
        workout["structured_workout"]["steps"][0]["duration"]["value"] += 30
    elif change == "rationale":
        payload["adjustment_rationale"] += " Revised coaching rationale."
    else:
        payload["running_workouts"][0]["date"] = "2026-07-29"
    path.write_text(json.dumps(payload))
    with pytest.raises(PlanOperationError, match="another complete candidate"):
        approve_week_application(repo, path, approved_at_utc=AT)


def test_forged_numerical_facts_fail_even_with_valid_artifact_and_source_hashes(repo, tmp_path):
    path = candidate(repo, tmp_path)

    def forge(context):
        context.progression.assessment.sessions[0].longest_recorded_distance_meters = 12345

    replace_context(repo, path, forge)
    with pytest.raises(PlanOperationError, match="facts changed or do not match"):
        approve_week_application(repo, path, approved_at_utc=AT)


def test_local_day_rollover_requires_new_review_but_keeps_original_context_chronology(
    repo, tmp_path
):
    path = candidate(repo, tmp_path)
    tomorrow = datetime(2026, 7, 26, 22, 30, tzinfo=timezone.utc)  # July 27 in Paris.
    with pytest.raises(PlanOperationError, match="operation's local date"):
        approve_week_application(repo, path, approved_at_utc=tomorrow)
    bind_test_candidate(repo, path, kind="week", at=tomorrow)
    application = WeekApplication.model_validate_json(path.read_bytes())
    context = load_evidence_artifact(
        repo, application.planning_context_reference, WeekPlanningContext
    )
    assert context.evidence_as_of_date.isoformat() == "2026-07-26"
    assert context.progression.assessment.evidence.as_of_date.isoformat() == "2026-07-27"
    approve_week_application(repo, path, approved_at_utc=tomorrow)


def test_binder_rejects_stale_base_context_before_writing(repo, tmp_path):
    from datetime import date

    from resilio.core.activity_sync.archive import ActivityArchive
    from tests.factories import make_activity

    path = candidate(repo, tmp_path)
    ActivityArchive(repo.resolve_path("data/activities")).write(
        make_activity(
            id="new-older-evidence",
            date=date(2026, 7, 20),
            distance_meters=8000,
        )
    )
    application = WeekApplication.model_validate_json(path.read_bytes())
    context = load_evidence_artifact(
        repo, application.planning_context_reference, WeekPlanningContext
    )
    review_path = tmp_path / "review.json"
    review_path.write_text(context.progression.review.model_dump_json())
    output = tmp_path / "final.json"
    with pytest.raises(PlanOperationError, match="Training evidence changed"):
        bind_progression_review(repo, path, review_path, output, kind="week", evaluated_at_utc=AT)
    assert not output.exists()


def test_review_decisions_and_frequency_are_enforced(repo, tmp_path):
    path = candidate(repo, tmp_path)
    application = WeekApplication.model_validate_json(path.read_bytes())
    context = load_evidence_artifact(
        repo, application.planning_context_reference, WeekPlanningContext
    )
    review = context.progression.review.model_dump(mode="json")
    review["judgments"][0]["decision"] = "conditional"
    review["judgments"][0]["future_prerequisites"] = [
        "Comfortable prior completion is not yet observed."
    ]
    review_path = tmp_path / "conditional.json"
    review_path.write_text(json.dumps(review))
    output = tmp_path / "final.json"
    result = bind_progression_review(
        repo, path, review_path, output, kind="week", evaluated_at_utc=AT
    )
    assert result["status"] == "revision_required" and not output.exists()
    review["judgments"][0]["intended_running_day_count"] = 7
    review_path.write_text(json.dumps(review))
    with pytest.raises(PlanOperationError, match="athlete-confirmed constraints"):
        bind_progression_review(repo, path, review_path, output, kind="week", evaluated_at_utc=AT)


def test_review_output_is_private_and_exclusive(repo, tmp_path):
    path = candidate(repo, tmp_path)
    assessment = assess_progression(repo, path, kind="week", evaluated_at_utc=AT)
    application = WeekApplication.model_validate_json(path.read_bytes())
    context = load_evidence_artifact(
        repo, application.planning_context_reference, WeekPlanningContext
    )
    review_path = tmp_path / "review.json"
    review_path.write_text(context.progression.review.model_dump_json())
    output = repo.resolve_path("data/plans/proposals/new/final.json")
    bind_progression_review(repo, path, review_path, output, kind="week", evaluated_at_utc=AT)
    assert output.stat().st_mode & 0o777 == 0o600
    assert output.parent.stat().st_mode & 0o777 == 0o700
    assert assessment.evidence_sha256 == context.progression.review.evidence_sha256
    with pytest.raises(PlanOperationError, match="new output path"):
        bind_progression_review(repo, path, review_path, output, kind="week", evaluated_at_utc=AT)


def test_race_backed_vdot_survives_all_progression_lock_boundaries(repo, tmp_path):
    from datetime import date

    from resilio.core.activity_sync.archive import ActivityArchive
    from resilio.core.planning.macro_context import create_macro_planning_context
    from resilio.core.planning.service import (
        apply_approved_week,
        approve_current_plan,
        approve_vdot_proposal,
        create_macro_plan,
    )
    from resilio.schemas.activity import ActivityAudit
    from tests.factories import make_activity

    race = make_activity(
        id="race-vdot", date=date(2026, 7, 20), duration_seconds=2700, distance_meters=10000
    )
    race.audit = ActivityAudit(
        imported_at_utc=datetime(2026, 7, 20, 10, tzinfo=timezone.utc),
        provider_snapshot_sha256="a" * 64,
        performance_evidence_sha256="b" * 64,
        canonical_mapping_version=9,
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(race)
    proposal_path = lifecycle._write_vdot_proposal(tmp_path)
    payload = json.loads(proposal_path.read_text())
    payload["evidence"] = {
        "evidence_type": "race_performance",
        "race_distance": "10k",
        "elapsed_time_seconds": 2700,
        "performance_date": "2026-07-20",
        "performance_timezone": "UTC",
        "source_local_activity_id": race.local_activity_id,
        "source_performance_evidence_sha256": "b" * 64,
        "measured_distance_meters": 10000,
        "official_distance_confirmation_reference": (
            "Synthetic athlete confirms official 10 km race distance."
        ),
    }
    proposal_path.write_text(json.dumps(payload))
    state = approve_vdot_proposal(
        repo, proposal_path, approved_at_utc=datetime(2026, 7, 25, 9, tzinfo=timezone.utc)
    )
    create_macro_planning_context(
        repo,
        evidence_as_of_date=date(2026, 7, 26),
        intended_plan_start_date=date(2026, 7, 27),
        generated_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
        current_local_date=date(2026, 7, 26),
    )
    create_macro_plan(
        repo,
        lifecycle._draft(state.active_vdot_approval_id),
        created_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    approve_current_plan(repo, approved_at_utc=datetime(2026, 7, 26, 12, tzinfo=timezone.utc))
    path = tmp_path / "race-backed-week.json"
    lifecycle._write_application(path, repo=repo)
    approve_week_application(repo, path, approved_at_utc=AT)
    apply_approved_week(repo, path, applied_at_utc=datetime(2026, 7, 26, 14, tzinfo=timezone.utc))


def test_relative_output_path_uses_private_exclusive_creation(repo, tmp_path):
    path = candidate(repo, tmp_path)
    application = WeekApplication.model_validate_json(path.read_bytes())
    context = load_evidence_artifact(
        repo, application.planning_context_reference, WeekPlanningContext
    )
    review_path = tmp_path / "relative-review.json"
    review_path.write_text(context.progression.review.model_dump_json())
    output = Path("data/plans/proposals/relative-reviewed.json")
    result = bind_progression_review(
        repo, path, review_path, output, kind="week", evaluated_at_utc=AT
    )
    assert result["status"] == "review_bound"
    assert output.stat().st_mode & 0o777 == 0o600


def test_initial_macro_approval_reproves_original_twelve_week_source(repo, tmp_path):
    from datetime import date

    from resilio.core.activity_sync.archive import ActivityArchive
    from resilio.core.planning.service import approve_current_plan, create_macro_plan
    from tests.factories import make_activity

    draft = lifecycle._draft(lifecycle._approve_vdot(repo, tmp_path))
    create_macro_plan(repo, draft, created_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc))
    ActivityArchive(repo.resolve_path("data/activities")).write(
        make_activity(
            id="outside-six-week-review",
            date=date(2026, 6, 1),
            distance_meters=8000,
        )
    )
    before = load_planning_aggregate(repo)
    with pytest.raises(PlanOperationError, match="Macro-planning training evidence changed"):
        approve_current_plan(repo, approved_at_utc=AT)
    assert load_planning_aggregate(repo) == before


def test_stale_unapproved_macro_can_be_discarded_rebound_and_recreated(repo, tmp_path):
    from resilio.core.planning.plan_proposal import discard_unapproved_current_plan
    from resilio.core.planning.service import approve_current_plan, create_macro_plan
    from resilio.schemas.macro_plan_draft import MacroPlanDraft

    draft = lifecycle._draft(lifecycle._approve_vdot(repo, tmp_path))
    original = create_macro_plan(
        repo, draft, created_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc)
    )
    tomorrow = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)
    with pytest.raises(PlanOperationError, match="operation's local date"):
        approve_current_plan(repo, approved_at_utc=tomorrow)
    discard_unapproved_current_plan(repo, expected_plan_revision_id=original.plan_revision_id)
    path = tmp_path / "rebound-macro.json"
    path.write_text(draft.model_dump_json())
    bind_test_candidate(repo, path, kind="macro", at=tomorrow)
    recreated = create_macro_plan(
        repo, MacroPlanDraft.model_validate_json(path.read_bytes()), created_at_utc=tomorrow
    )
    assert recreated.plan_revision_id != original.plan_revision_id
    assert recreated.weeks == original.weeks
    approve_current_plan(repo, approved_at_utc=tomorrow)


@pytest.mark.parametrize("operation", ["approve", "apply"])
def test_week_consent_binds_the_same_bytes_that_are_parsed(repo, tmp_path, monkeypatch, operation):
    import hashlib

    from resilio.core.planning.weekly_service import apply_approved_week

    path = candidate(repo, tmp_path)
    original_bytes = path.read_bytes()
    approve_week_application(repo, path, approved_at_utc=AT)
    payload = json.loads(original_bytes)
    payload["adjustment_rationale"] += " Different reviewed coaching recommendation."
    path.write_text(json.dumps(payload))
    bind_test_candidate(repo, path, kind="week", at=AT)
    revised_bytes = path.read_bytes()
    before = load_planning_aggregate(repo)
    if operation == "approve":
        path.write_bytes(original_bytes)
    read_bytes = Path.read_bytes
    read_text = Path.read_text

    def swap_after_read(reader, file_path, *args, **kwargs):
        result = reader(file_path, *args, **kwargs)
        if file_path == path:
            path.write_bytes(revised_bytes if operation == "approve" else original_bytes)
        return result

    monkeypatch.setattr(
        Path, "read_bytes", lambda file_path: swap_after_read(read_bytes, file_path)
    )
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda file_path, *a, **kw: swap_after_read(read_text, file_path, *a, **kw),
    )
    if operation == "approve":
        state = approve_week_application(repo, path, approved_at_utc=AT)
        assert (
            state.active_plan.pending_weekly_approval.approved_file_sha256
            == hashlib.sha256(original_bytes).hexdigest()
        )
    else:
        with pytest.raises(PlanOperationError, match="changed after approval"):
            apply_approved_week(repo, path, applied_at_utc=AT)
        assert load_planning_aggregate(repo) == before


def test_week_approval_rejects_symlink_before_path_resolution(repo, tmp_path):
    path = candidate(repo, tmp_path)
    link = tmp_path / "linked-week.json"
    link.symlink_to(path)
    before = load_planning_aggregate(repo)
    with pytest.raises(PlanOperationError, match="symlink"):
        approve_week_application(repo, link, approved_at_utc=AT)
    assert load_planning_aggregate(repo) == before


def test_macro_binding_rejects_a_future_base_context_before_writes(repo, tmp_path):
    from resilio.schemas.planning_evidence import MacroPlanningContext

    draft = lifecycle._draft(lifecycle._approve_vdot(repo, tmp_path))
    context = load_evidence_artifact(repo, draft.planning_context_reference, MacroPlanningContext)
    review_path = tmp_path / "macro-review.json"
    review_path.write_text(context.progression.review.model_dump_json())
    context.generated_at_utc = datetime(2026, 7, 26, 14, tzinfo=timezone.utc)
    reference = import_evidence_artifact(repo, context, artifact_type="macro_planning_context")
    draft.planning_context_reference = reference
    path = tmp_path / "macro.json"
    path.write_text(draft.model_dump_json())
    output = tmp_path / "future-bound.json"
    with pytest.raises(PlanOperationError, match="cannot postdate review binding"):
        bind_progression_review(repo, path, review_path, output, kind="macro", evaluated_at_utc=AT)
    assert not output.exists()
