"""Planning-state v4 lifecycle, evidence, and revision-bound behavior."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import resilio.core.profile.repository as profile_repository_module
from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.coaching_context import build_week_planning_context
from resilio.core.planning.approval_evidence import (
    ApprovalEvidenceError,
    verify_vdot_approval,
)
from resilio.core.planning.artifacts import load_evidence_artifact
from resilio.core.planning.cycle_review import (
    confirmed_goal_outcome,
    create_cycle_review,
)
from resilio.core.planning.integrity import applied_workout_sha256, sha256_file
from resilio.core.planning.macro_context import create_macro_planning_context
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.service import (
    PlanOperationError,
    apply_approved_week,
    approve_current_plan,
    approve_vdot_proposal,
    approve_week_application,
    close_current_plan_from_review,
    create_macro_plan,
    discard_unapproved_current_plan,
    load_approved_workouts_for_date_range,
    load_current_plan,
    load_planning_aggregate,
    load_publishable_workout,
)
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.core.state import save_planning_state
from resilio.core.sync_state import write_sync_state
from resilio.core.workout_publication.completions import save_completion_manifest
from resilio.core.workout_publication.week_service import RunWeekSynchronizationService
from resilio.schemas.approvals import (
    AppliedWeekRevision,
    PlanningState,
)
from resilio.schemas.macro_plan_draft import MacroPlanDraft
from resilio.schemas.plan_history import GoalOutcome, PlanClosureDisposition
from resilio.schemas.planning_evidence import PlanCycleReview
from resilio.schemas.profile import (
    AthleteProfile,
    ConflictPolicy,
    Goal,
    GoalType,
    PBEntry,
    RunningPriority,
    TrainingConstraints,
)
from resilio.schemas.publication import WorkoutCompletionManifest, WorkoutCompletionMatch
from resilio.schemas.sync import ActivityCoverageWindow, ActivitySyncState
from tests.factories import make_activity
from tests.unit.test_workout_publication import FakeClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _hints() -> dict:
    return {
        "quality": {"maximum_sessions": 1, "types": ["tempo"]},
        "long_run": {
            "emphasis": "easy",
            "minimum_weekly_run_volume_percent": 35,
            "maximum_weekly_run_volume_percent": 45,
        },
        "intensity_distribution": None,
    }


def _draft(vdot_approval_id: str) -> MacroPlanDraft:
    context_paths = sorted(
        Path("data/plans/evidence/macro_planning_context").glob("*.json"),
        key=lambda path: path.stat().st_mtime_ns,
    )
    assert context_paths
    context_path = context_paths[-1]
    context_sha256 = context_path.stem
    context_payload = json.loads(context_path.read_text())
    required_renewal_evidence_ids = [
        context_payload["evidence_index"][-1]["evidence_id"],
    ]
    historical_summaries = context_payload["historical_plan_summaries"]
    if historical_summaries:
        latest_plan_id = max(
            historical_summaries,
            key=lambda summary: (
                summary["effective_end_date"],
                summary["plan_id"],
            ),
        )["plan_id"]
        required_renewal_evidence_ids.extend(
            [
                f"closed_plan.{latest_plan_id}.summary",
                f"goal_outcome.{latest_plan_id}",
            ]
        )
    return MacroPlanDraft.model_validate(
        {
            "goal": {
                "type": "10k",
                "target_date": "2026-08-02",
                "target_time": "00:45:00",
            },
            "methodology": {
                "identifier": "daniels",
                "selection_rationale": (
                    "The athlete's four-day schedule and current 10K goal "
                    "fit Daniels progression and pace vocabulary."
                ),
            },
            "weeks": [
                {
                    "week_number": 1,
                    "phase": "base",
                    "start_date": "2026-07-27",
                    "end_date": "2026-08-02",
                    "target_run_volume_meters": 10_000,
                    "workout_structure_hints": _hints(),
                    "workouts": [],
                }
            ],
            "vdot_approval_id": vdot_approval_id,
            "planning_context_reference": {
                "artifact_type": "macro_planning_context",
                "artifact_sha256": context_sha256,
            },
            "planning_rationale": (
                "The plan starts from athlete-confirmed availability, approved "
                "VDOT evidence, and the exact recent training evidence context."
            ),
            "adaptation_decisions": [
                {
                    "decision_type": "methodology_selection",
                    "evidence_ids": [
                        "profile.current_constraints",
                        f"vdot.{vdot_approval_id}",
                    ],
                    "observed_facts": (
                        "The athlete has a current 10K goal and four available "
                        "running days with a verified performance baseline."
                    ),
                    "planning_change": (
                        "Use Daniels as the single conceptual methodology for "
                        "the complete macro-plan horizon."
                    ),
                    "affected_week_numbers": [1],
                },
                {
                    "decision_type": "starting_volume",
                    "evidence_ids": [
                        "profile.current_constraints",
                        *required_renewal_evidence_ids,
                    ],
                    "observed_facts": (
                        "The athlete-confirmed constraints permit two to four "
                        "weekly runs without additional sport commitments."
                    ),
                    "planning_change": (
                        "Start with ten thousand planned running meters in the "
                        "opening week and review exact execution evidence."
                    ),
                    "affected_week_numbers": [1],
                },
            ],
        }
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RepositoryIO:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repository = RepositoryIO()
    methodology_source = tmp_path / "docs/training_books/daniels_running_formula.md"
    methodology_source.parent.mkdir(parents=True)
    methodology_source.write_bytes(
        (PROJECT_ROOT / "docs/training_books/daniels_running_formula.md").read_bytes()
    )
    ProfileRepository(repository).create(
        AthleteProfile(
            athlete_name="Alex",
            created_on=date(2026, 7, 20),
            training_timezone="Europe/Paris",
            personal_bests_by_distance={
                "10k": PBEntry(
                    elapsed_time_seconds=2_700,
                    performance_date=date(2026, 7, 20),
                    vdot=45,
                )
            },
            constraints=TrainingConstraints(
                minimum_run_days_per_week=2,
                maximum_run_days_per_week=4,
            ),
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.ASK_EACH_TIME,
            goal=Goal(
                type=GoalType.TEN_K,
                target_date=date(2026, 8, 2),
                target_finish_time_seconds=2_700,
            ),
        )
    )
    return repository


def _write_vdot_proposal(tmp_path: Path) -> Path:
    proposal_path = tmp_path / "vdot-45.json"
    proposal_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "proposed_vdot": 45,
                "evidence": {
                    "evidence_type": "personal_best",
                    "race_distance": "10k",
                    "elapsed_time_seconds": 2700,
                    "performance_date": "2026-07-20",
                    "performance_timezone": "Europe/Paris",
                },
                "evidence_summary": (
                    "Recent measured race performance supports this integer baseline."
                ),
                "generated_at_utc": "2026-07-25T08:00:00Z",
            }
        )
    )
    return proposal_path


def _approve_vdot(repo: RepositoryIO, tmp_path: Path) -> str:
    proposal_path = _write_vdot_proposal(tmp_path)
    state = approve_vdot_proposal(
        repo,
        proposal_path,
        approved_at_utc=datetime(2026, 7, 25, 9, tzinfo=timezone.utc),
    )
    assert state.active_vdot_approval is not None
    create_macro_planning_context(
        repo,
        evidence_as_of_date=date(2026, 7, 26),
        intended_plan_start_date=date(2026, 7, 27),
        generated_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
        current_local_date=date(2026, 7, 26),
    )
    return state.active_vdot_approval.approval_id


def test_vdot_proposal_cannot_be_approved_before_it_was_generated(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    proposal_path = _write_vdot_proposal(tmp_path)

    with pytest.raises(PlanOperationError, match="generated after"):
        approve_vdot_proposal(
            repo,
            proposal_path,
            approved_at_utc=datetime(2026, 7, 24, 9, tzinfo=timezone.utc),
        )


def test_macro_plan_cannot_predate_its_vdot_approval(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)

    with pytest.raises(PlanOperationError, match="predate.*VDOT approval"):
        create_macro_plan(
            repo,
            _draft(approval_id),
            created_at_utc=datetime(2026, 7, 25, 8, tzinfo=timezone.utc),
        )


def test_macro_context_cannot_claim_evidence_from_after_generation(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    proposal_path = _write_vdot_proposal(tmp_path)
    approve_vdot_proposal(
        repo,
        proposal_path,
        approved_at_utc=datetime(2026, 7, 25, 9, tzinfo=timezone.utc),
    )

    with pytest.raises(PlanOperationError, match="postdate context generation"):
        create_macro_planning_context(
            repo,
            evidence_as_of_date=date(2026, 7, 26),
            intended_plan_start_date=date(2026, 7, 27),
            generated_at_utc=datetime(2026, 7, 25, 10, tzinfo=timezone.utc),
            current_local_date=date(2026, 7, 26),
        )


def _write_application(path: Path, *, purpose: str = "Aerobic support") -> None:
    def targetless_structure(duration_seconds: int) -> dict[str, object]:
        return {
            "sport": "run",
            "steps": [
                {
                    "kind": "steady",
                    "duration": {"unit": "seconds", "value": duration_seconds},
                    "intensity": "active",
                    "cue": "Keep the approved easy effort.",
                }
            ],
        }

    path.write_text(
        json.dumps(
            {
                "week_number": 1,
                "adjustment_rationale": (
                    "The opening week preserves three distinct run days while "
                    "keeping every prescribed minute deliberately low intensity."
                ),
                "workouts": [
                    {
                        "id": "w_easy_1",
                        "date": "2026-07-28",
                        "start_time_local": "07:00:00",
                        "sport": "run",
                        "workout_type": "easy",
                        "planned_duration_seconds": 1_800,
                        "planned_distance_meters": 3_000,
                        "planned_low_intensity_duration_seconds": 1_800,
                        "planned_moderate_intensity_duration_seconds": 0,
                        "planned_high_intensity_duration_seconds": 0,
                        "target_rpe_1_to_10": 3,
                        "purpose": purpose,
                        "structured_workout": targetless_structure(1_800),
                    },
                    {
                        "id": "w_easy_2",
                        "date": "2026-07-30",
                        "start_time_local": "07:00:00",
                        "sport": "run",
                        "workout_type": "easy",
                        "planned_duration_seconds": 1_800,
                        "planned_distance_meters": 3_000,
                        "planned_low_intensity_duration_seconds": 1_800,
                        "planned_moderate_intensity_duration_seconds": 0,
                        "planned_high_intensity_duration_seconds": 0,
                        "target_rpe_1_to_10": 3,
                        "purpose": "Maintain easy aerobic frequency.",
                        "structured_workout": targetless_structure(1_800),
                    },
                    {
                        "id": "w_long_1",
                        "date": "2026-08-01",
                        "start_time_local": "08:00:00",
                        "sport": "run",
                        "workout_type": "long_run",
                        "planned_duration_seconds": 2_400,
                        "planned_distance_meters": 4_000,
                        "planned_low_intensity_duration_seconds": 2_400,
                        "planned_moderate_intensity_duration_seconds": 0,
                        "planned_high_intensity_duration_seconds": 0,
                        "target_rpe_1_to_10": 3,
                        "purpose": "Complete the approved weekly long-run share.",
                        "structured_workout": targetless_structure(2_400),
                    },
                ],
            }
        )
    )


def _create_approved_macro(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    create_macro_plan(
        repo,
        _draft(approval_id),
        created_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    approve_current_plan(
        repo,
        approved_at_utc=datetime(2026, 7, 26, 12, tzinfo=timezone.utc),
    )


def _apply_test_week(repo: RepositoryIO, tmp_path: Path) -> None:
    _create_approved_macro(repo, tmp_path)
    payload_path = tmp_path / "week.json"
    _write_application(payload_path)
    approve_week_application(
        repo,
        payload_path,
        approved_at_utc=datetime(2026, 7, 26, 13, tzinfo=timezone.utc),
    )
    apply_approved_week(
        repo,
        payload_path,
        applied_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )


def test_exact_applied_week_is_the_end_to_end_publication_authority(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    client = FakeClient()
    service = RunWeekSynchronizationService(repo, client)

    status = service.status_week(1, as_of_date=date(2026, 7, 27))
    reconciled = service.reconcile_week(1, as_of_date=date(2026, 7, 27))

    assert status.reconciliation_safe
    assert status.run_workouts_considered == 3
    assert [item.status for item in reconciled.items] == [
        "created",
        "created",
        "created",
    ]
    assert len(client.events) == 3


def _close_test_plan(
    repo: RepositoryIO,
    *,
    effective_end_date: date = date(2026, 8, 2),
    evidence_as_of_date: date = date(2026, 8, 2),
    closed_at_utc: datetime = datetime(
        2026,
        8,
        2,
        23,
        tzinfo=timezone.utc,
    ),
    disposition: PlanClosureDisposition = (PlanClosureDisposition.COMPLETED_HORIZON),
) -> PlanningState:
    reference = create_cycle_review(
        repo,
        effective_end_date=effective_end_date,
        evidence_as_of_date=evidence_as_of_date,
        goal_outcome=GoalOutcome(
            status="did_not_start",
            athlete_confirmation_reference=(
                "Athlete confirmed that they did not start the target event."
            ),
        ),
        generated_at_utc=closed_at_utc,
    )
    return close_current_plan_from_review(
        repo,
        cycle_review_reference=reference,
        disposition=disposition,
        reason=(
            "The athlete reviewed the complete cycle evidence and requested "
            "that this exact plan revision be closed."
        ),
        athlete_confirmation_reference=(
            "Athlete confirmed the goal outcome and requested a new plan."
        ),
        closed_at_utc=closed_at_utc,
    )


@pytest.mark.parametrize(
    ("activity_date", "sport", "expected_message"),
    [
        (
            date(2026, 7, 26),
            "run",
            "outside the effective plan cycle",
        ),
        (
            date(2026, 8, 2),
            "cycle",
            "canonical running activity",
        ),
    ],
)
def test_cycle_review_rejects_unqualified_goal_activity(
    repo: RepositoryIO,
    tmp_path: Path,
    activity_date: date,
    sport: str,
    expected_message: str,
) -> None:
    _create_approved_macro(repo, tmp_path)
    activity = make_activity(
        id=f"goal-{sport}-{activity_date.isoformat()}",
        date=activity_date,
        sport=sport,
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    outcome = confirmed_goal_outcome(
        repo,
        status="completed",
        local_activity_id=activity.local_activity_id,
        athlete_confirmation_reference=(
            "Athlete confirmed this exact activity as their goal event."
        ),
    )

    with pytest.raises(PlanOperationError, match=expected_message):
        create_cycle_review(
            repo,
            effective_end_date=date(2026, 8, 2),
            evidence_as_of_date=date(2026, 8, 2),
            goal_outcome=outcome,
            generated_at_utc=datetime(
                2026,
                8,
                2,
                20,
                tzinfo=timezone.utc,
            ),
        )


def test_cycle_review_retains_goal_performance_for_future_planning(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    activity = make_activity(
        id="goal-race-completed",
        date=date(2026, 8, 2),
        sport="run",
        distance_meters=10_000,
        duration_seconds=2_655,
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    outcome = confirmed_goal_outcome(
        repo,
        status="completed",
        local_activity_id=activity.local_activity_id,
        athlete_confirmation_reference=(
            "Athlete confirmed this exact recording as their completed target race."
        ),
    )
    reference = create_cycle_review(
        repo,
        effective_end_date=date(2026, 8, 2),
        evidence_as_of_date=date(2026, 8, 2),
        goal_outcome=outcome,
        generated_at_utc=datetime(2026, 8, 2, 20, tzinfo=timezone.utc),
    )

    review = load_evidence_artifact(repo, reference, PlanCycleReview)

    assert review.goal_activity is not None
    assert review.goal_activity.distance_km == 10
    assert review.goal_activity.elapsed_duration_seconds == 2_655
    assert any(
        "source coverage" in limitation.lower() for limitation in review.evidence_limitations
    )


def test_plan_closure_rejects_training_evidence_changed_after_review(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    reference = create_cycle_review(
        repo,
        effective_end_date=date(2026, 8, 2),
        evidence_as_of_date=date(2026, 8, 2),
        goal_outcome=GoalOutcome(
            status="did_not_start",
            athlete_confirmation_reference=(
                "Athlete confirmed that they did not start the target event."
            ),
        ),
        generated_at_utc=datetime(2026, 8, 2, 20, tzinfo=timezone.utc),
    )
    write_sync_state(
        repo,
        ActivitySyncState(
            last_successful_incremental_at_utc=datetime(
                2026,
                8,
                2,
                18,
                tzinfo=timezone.utc,
            ),
            complete_activity_windows=[
                ActivityCoverageWindow(
                    start_date=date(2026, 7, 27),
                    end_date=date(2026, 8, 2),
                )
            ],
        ),
    )

    with pytest.raises(
        PlanOperationError,
        match="Training evidence changed after cycle review",
    ):
        close_current_plan_from_review(
            repo,
            cycle_review_reference=reference,
            disposition=PlanClosureDisposition.COMPLETED_HORIZON,
            reason=("The athlete reviewed the full plan horizon and requested closure."),
            athlete_confirmation_reference=(
                "Athlete confirmed the review and requested plan closure."
            ),
            closed_at_utc=datetime(2026, 8, 2, 21, tzinfo=timezone.utc),
        )


def test_plan_closure_rejects_active_plan_changed_after_review(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    reference = create_cycle_review(
        repo,
        effective_end_date=date(2026, 8, 2),
        evidence_as_of_date=date(2026, 8, 2),
        goal_outcome=GoalOutcome(
            status="did_not_start",
            athlete_confirmation_reference=(
                "Athlete confirmed that they did not start the target event."
            ),
        ),
        generated_at_utc=datetime(2026, 8, 2, 20, tzinfo=timezone.utc),
    )
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_plan is not None
    changed_week = state.active_plan.plan.weeks[0].model_copy(
        update={"target_run_volume_meters": 9_000}
    )
    changed_plan = state.active_plan.plan.model_copy(update={"weeks": [changed_week]})
    error = save_planning_state(
        state.model_copy(
            update={"active_plan": state.active_plan.model_copy(update={"plan": changed_plan})}
        ),
        repo,
    )
    assert error is None

    with pytest.raises(
        PlanOperationError,
        match="Active plan changed after cycle review",
    ):
        close_current_plan_from_review(
            repo,
            cycle_review_reference=reference,
            disposition=PlanClosureDisposition.COMPLETED_HORIZON,
            reason=("The athlete reviewed the full plan horizon and requested closure."),
            athlete_confirmation_reference=(
                "Athlete confirmed the review and requested plan closure."
            ),
            closed_at_utc=datetime(2026, 8, 2, 21, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    ("effective_end_date", "evidence_as_of_date", "generated_at_utc", "message"),
    [
        (
            date(2026, 7, 25),
            date(2026, 7, 25),
            datetime(2026, 7, 26, 12, tzinfo=timezone.utc),
            "predate plan creation",
        ),
        (
            date(2026, 8, 2),
            date(2026, 8, 2),
            datetime(2026, 7, 31, 12, tzinfo=timezone.utc),
            "postdate review generation",
        ),
    ],
)
def test_cycle_review_rejects_impossible_evidence_dates(
    repo: RepositoryIO,
    tmp_path: Path,
    effective_end_date: date,
    evidence_as_of_date: date,
    generated_at_utc: datetime,
    message: str,
) -> None:
    _create_approved_macro(repo, tmp_path)

    with pytest.raises(PlanOperationError, match=message):
        create_cycle_review(
            repo,
            effective_end_date=effective_end_date,
            evidence_as_of_date=evidence_as_of_date,
            goal_outcome=GoalOutcome(
                status="did_not_start",
                athlete_confirmation_reference=(
                    "Athlete confirmed that they did not start the target event."
                ),
            ),
            generated_at_utc=generated_at_utc,
        )


def test_plan_approval_cannot_predate_plan_creation(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    create_macro_plan(
        repo,
        _draft(approval_id),
        created_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )

    with pytest.raises(PlanOperationError, match="predate.*plan creation"):
        approve_current_plan(
            repo,
            approved_at_utc=datetime(2026, 7, 25, 23, tzinfo=timezone.utc),
        )


def test_week_approval_cannot_predate_plan_approval(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    payload_path = tmp_path / "backdated-week-approval.json"
    _write_application(payload_path)

    with pytest.raises(PlanOperationError, match="predate.*plan approval"):
        approve_week_application(
            repo,
            payload_path,
            approved_at_utc=datetime(2026, 7, 26, 11, tzinfo=timezone.utc),
        )


def test_week_application_cannot_predate_week_approval(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    payload_path = tmp_path / "backdated-week-application.json"
    _write_application(payload_path)
    approve_week_application(
        repo,
        payload_path,
        approved_at_utc=datetime(2026, 7, 26, 13, tzinfo=timezone.utc),
    )

    with pytest.raises(PlanOperationError, match="predate.*weekly approval"):
        apply_approved_week(
            repo,
            payload_path,
            applied_at_utc=datetime(2026, 7, 26, 12, 59, tzinfo=timezone.utc),
        )


def test_create_macro_plan_persists_v5_aggregate(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    created = create_macro_plan(
        repo,
        _draft(approval_id),
        created_at_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )

    loaded = load_current_plan(repo)
    state = load_planning_aggregate(repo)

    assert loaded == created
    assert state is not None
    assert state.active_plan is not None
    assert state.active_plan.plan == created
    assert state.schema_version == 5
    assert loaded.schema_info.version == 4
    assert loaded.vdot_approval_id == approval_id
    assert loaded.baseline_vdot == 45


def test_unapproved_plan_is_typed_as_unavailable_adherence(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    create_macro_plan(repo, _draft(approval_id))

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "unavailable"
    assert evidence.reason == "overlapping_plan_is_not_approved"


def test_macro_creation_requires_exact_approved_vdot_file(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    proposal_path = tmp_path / "vdot-45.json"
    proposal_path.write_text(proposal_path.read_text().replace("45", "46", 1))

    with pytest.raises(PlanOperationError, match="changed after approval"):
        create_macro_plan(repo, _draft(approval_id))


def test_macro_creation_rejects_training_evidence_changed_after_context(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    write_sync_state(
        repo,
        ActivitySyncState(
            last_successful_incremental_at_utc=datetime(
                2026,
                7,
                26,
                8,
                tzinfo=timezone.utc,
            ),
            complete_activity_windows=[
                ActivityCoverageWindow(
                    start_date=date(2026, 4, 1),
                    end_date=date(2026, 7, 26),
                )
            ],
        ),
    )

    with pytest.raises(
        PlanOperationError,
        match="training evidence changed after context creation",
    ):
        create_macro_plan(repo, _draft(approval_id))


def test_macro_plan_must_cite_recent_training_evidence(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    draft = _draft(approval_id)
    decisions_without_training_evidence = [
        decision.model_copy(
            update={
                "evidence_ids": [
                    evidence_id
                    for evidence_id in decision.evidence_ids
                    if not evidence_id.startswith(("recent_week.", "closed_plan.", "goal_outcome."))
                ]
            }
        )
        for decision in draft.adaptation_decisions
    ]

    with pytest.raises(
        PlanOperationError,
        match="required renewal evidence",
    ):
        create_macro_plan(
            repo,
            draft.model_copy(update={"adaptation_decisions": decisions_without_training_evidence}),
        )


def test_renewal_macro_plan_must_cite_latest_plan_and_goal_outcome(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    _close_test_plan(
        repo,
        effective_end_date=date(2026, 7, 26),
        evidence_as_of_date=date(2026, 7, 26),
        closed_at_utc=datetime(2026, 7, 26, 23, tzinfo=timezone.utc),
        disposition=PlanClosureDisposition.NEVER_STARTED,
    )
    create_macro_planning_context(
        repo,
        evidence_as_of_date=date(2026, 7, 26),
        intended_plan_start_date=date(2026, 7, 27),
        generated_at_utc=datetime(2026, 7, 26, 23, 30, tzinfo=timezone.utc),
        current_local_date=date(2026, 7, 26),
    )
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_vdot_approval is not None
    draft = _draft(state.active_vdot_approval.approval_id)
    decisions_without_plan_history = [
        decision.model_copy(
            update={
                "evidence_ids": [
                    evidence_id
                    for evidence_id in decision.evidence_ids
                    if not evidence_id.startswith(("closed_plan.", "goal_outcome."))
                ]
            }
        )
        for decision in draft.adaptation_decisions
    ]

    with pytest.raises(
        PlanOperationError,
        match="required renewal evidence",
    ):
        create_macro_plan(
            repo,
            draft.model_copy(update={"adaptation_decisions": decisions_without_plan_history}),
        )


def test_vdot_approval_recomputes_structured_race_evidence(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    proposal_path = tmp_path / "invalid-race-vdot.json"
    proposal_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "proposed_vdot": 85,
                "evidence": {
                    "evidence_type": "race_performance",
                    "race_distance": "10k",
                    "elapsed_time_seconds": 7_200,
                    "performance_date": "2026-07-20",
                    "performance_timezone": "Europe/Paris",
                    "source_local_activity_id": "act_i_slow_10k",
                    "source_external_fingerprint_sha256": "a" * 64,
                    "measured_distance_meters": 10_000,
                    "official_distance_confirmation_reference": (
                        "Athlete confirmed this synchronized effort as an official 10K."
                    ),
                },
                "evidence_summary": ("The structured performance must determine the proposal."),
                "generated_at_utc": "2026-07-25T08:00:00Z",
            }
        )
    )

    with pytest.raises(PlanOperationError, match="cannot produce an approved VDOT"):
        approve_vdot_proposal(repo, proposal_path)


def test_vdot_approval_verifier_rejects_missing_hash_and_semantic_drift(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _approve_vdot(repo, tmp_path)
    state = load_planning_aggregate(repo)
    assert state is not None
    assert state.active_vdot_approval is not None
    approval = state.active_vdot_approval
    proposal_path = Path(approval.proposal_file)

    original = proposal_path.read_text()
    proposal_path.unlink()
    with pytest.raises(ApprovalEvidenceError, match="could not be read"):
        verify_vdot_approval(repo, approval)

    proposal_path.write_text(original.replace("45", "46", 1))
    with pytest.raises(ApprovalEvidenceError, match="changed after approval"):
        verify_vdot_approval(repo, approval)

    semantically_mismatched = approval.model_copy(
        update={"proposal_file_sha256": sha256_file(proposal_path)}
    )
    with pytest.raises(
        ApprovalEvidenceError,
        match="structured performance evidence",
    ):
        verify_vdot_approval(repo, semantically_mismatched)


def test_vdot_approval_verifier_rejects_approval_before_proposal(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _approve_vdot(repo, tmp_path)
    state = load_planning_aggregate(repo)
    assert state is not None
    assert state.active_vdot_approval is not None
    impossible_approval = state.active_vdot_approval.model_copy(
        update={
            "approved_at_utc": datetime(
                2026,
                7,
                25,
                7,
                59,
                tzinfo=timezone.utc,
            )
        }
    )

    with pytest.raises(ApprovalEvidenceError, match="predates.*proposal"):
        verify_vdot_approval(repo, impossible_approval)


def test_planning_state_rejects_plan_created_before_vdot_approval(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    plan = create_macro_plan(repo, _draft(approval_id))
    state = load_planning_aggregate(repo)
    assert state is not None

    with pytest.raises(ValidationError, match="plan creation cannot predate"):
        PlanningState.model_validate(
            state.model_copy(
                update={
                    "active_plan": state.active_plan.model_copy(
                        update={
                            "plan": plan.model_copy(
                                update={
                                    "created_at_utc": datetime(
                                        2026,
                                        7,
                                        25,
                                        8,
                                        59,
                                        tzinfo=timezone.utc,
                                    )
                                }
                            )
                        }
                    ),
                }
            ).model_dump(mode="python")
        )


def test_week_application_requires_macro_and_week_approval(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    create_macro_plan(repo, _draft(approval_id))
    payload_path = tmp_path / "week.json"
    _write_application(payload_path)

    with pytest.raises(PlanOperationError, match="approval is missing"):
        apply_approved_week(repo, payload_path)


def test_planning_relevant_profile_update_durably_invalidates_plan(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    create_macro_plan(repo, _draft(approval_id))

    profile_repository = ProfileRepository(repo)
    current_profile = profile_repository.load()
    assert current_profile is not None
    updated_constraints = current_profile.constraints.model_copy(
        update={"maximum_run_days_per_week": 3}
    )
    profile_repository.update({"constraints": updated_constraints.model_dump(mode="json")})

    state = load_planning_aggregate(repo)
    assert state is not None
    assert state.active_plan is not None
    assert state.active_plan.invalidated_at_utc is not None
    assert "constraints" in (state.active_plan.invalidation_reason or "")


def test_profile_update_rolls_back_when_plan_invalidation_cannot_persist(
    repo: RepositoryIO,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    create_macro_plan(repo, _draft(approval_id))
    profile_repository = ProfileRepository(repo)
    original_profile = profile_repository.load()
    original_state = load_planning_aggregate(repo)
    assert original_profile is not None
    assert original_state is not None

    def fail_plan_persistence(*_args: object, **_kwargs: object) -> PlanningState:
        raise PlanOperationError("simulated plan persistence failure")

    monkeypatch.setattr(
        profile_repository_module,
        "persist_planning_state",
        fail_plan_persistence,
    )
    with pytest.raises(OSError, match="profile update was rolled back"):
        profile_repository.update(
            {
                "constraints": original_profile.constraints.model_copy(
                    update={"maximum_run_days_per_week": 3}
                ).model_dump(mode="json")
            }
        )

    assert profile_repository.load() == original_profile
    assert load_planning_aggregate(repo) == original_state


def test_interrupted_profile_plan_transition_recovers_previous_state(
    repo: RepositoryIO,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    create_macro_plan(repo, _draft(approval_id))
    profile_repository = ProfileRepository(repo)
    original_profile = profile_repository.load()
    original_state = load_planning_aggregate(repo)
    assert original_profile is not None
    assert original_state is not None
    original_persist = profile_repository_module.persist_planning_state

    def simulate_process_stop(*_args: object, **_kwargs: object) -> PlanningState:
        raise SystemExit("simulated process stop")

    monkeypatch.setattr(
        profile_repository_module,
        "persist_planning_state",
        simulate_process_stop,
    )
    with pytest.raises(SystemExit, match="simulated process stop"):
        profile_repository.update(
            {
                "constraints": original_profile.constraints.model_copy(
                    update={"maximum_run_days_per_week": 3}
                ).model_dump(mode="json")
            }
        )
    monkeypatch.setattr(
        profile_repository_module,
        "persist_planning_state",
        original_persist,
    )

    assert ProfileRepository(repo).load() == original_profile
    assert load_planning_aggregate(repo) == original_state


def test_pair_readers_fail_closed_while_profile_plan_writer_holds_lock(
    repo: RepositoryIO,
) -> None:
    with coordinated_plan_lock(repo, "test_profile_plan_writer"):
        with pytest.raises(OSError, match="temporarily unavailable"):
            ProfileRepository(repo).load()
        with pytest.raises(
            PlanOperationError,
            match="temporarily unavailable",
        ):
            load_planning_aggregate(repo)


def test_week_approval_cannot_cross_macro_plan_revisions(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    payload_path = tmp_path / "week.json"
    _write_application(payload_path)
    approve_week_application(
        repo,
        payload_path,
        approved_at_utc=datetime(2026, 7, 26, 13, tzinfo=timezone.utc),
    )
    plan_a = load_current_plan(repo)
    assert plan_a is not None

    _close_test_plan(
        repo,
        effective_end_date=date(2026, 7, 26),
        evidence_as_of_date=date(2026, 7, 26),
        closed_at_utc=datetime(2026, 7, 26, 23, tzinfo=timezone.utc),
        disposition=PlanClosureDisposition.NEVER_STARTED,
    )
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_vdot_approval is not None
    create_macro_planning_context(
        repo,
        evidence_as_of_date=date(2026, 7, 26),
        intended_plan_start_date=date(2026, 7, 27),
        generated_at_utc=datetime(2026, 7, 26, 23, 30, tzinfo=timezone.utc),
        current_local_date=date(2026, 7, 26),
    )
    plan_b = create_macro_plan(
        repo,
        _draft(state.active_vdot_approval.approval_id),
    )
    assert plan_b.plan_revision_id != plan_a.plan_revision_id

    with pytest.raises(PlanOperationError, match="approval is missing"):
        apply_approved_week(repo, payload_path)


def test_week_application_rejects_post_approval_mutation(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    payload_path = tmp_path / "week.json"
    _write_application(payload_path)
    approve_week_application(repo, payload_path)
    _write_application(payload_path, purpose="Changed after approval")

    with pytest.raises(PlanOperationError, match="changed after approval"):
        apply_approved_week(repo, payload_path)


def test_exact_approved_week_is_applied_and_audit_is_retained(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    payload_path = tmp_path / "week.json"
    _write_application(payload_path)
    approve_week_application(
        repo,
        payload_path,
        approved_at_utc=datetime(2026, 7, 26, 13, tzinfo=timezone.utc),
    )

    plan = apply_approved_week(
        repo,
        payload_path,
        applied_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )

    assert [workout.id for workout in plan.weeks[0].workouts] == [
        "w_easy_1",
        "w_easy_2",
        "w_long_1",
    ]
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_plan is not None
    assert state.active_plan.pending_weekly_approval is None
    assert len(state.active_plan.applied_week_revisions) == 1
    assert state.active_plan.applied_week_revisions[0].active is True

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )
    assert evidence.status == "available"
    assert [workout.prescription.id for workout in evidence.workouts] == [
        "w_easy_1",
        "w_easy_2",
        "w_long_1",
    ]


def test_closed_revision_remains_authoritative_for_historical_adherence(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    _close_test_plan(repo)

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "available"
    assert [workout.prescription.id for workout in evidence.workouts] == [
        "w_easy_1",
        "w_easy_2",
        "w_long_1",
    ]


def test_early_closure_excludes_workouts_after_effective_plan_end(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    _close_test_plan(
        repo,
        effective_end_date=date(2026, 7, 29),
        evidence_as_of_date=date(2026, 7, 29),
        closed_at_utc=datetime(2026, 8, 1, 23, tzinfo=timezone.utc),
        disposition=PlanClosureDisposition.STOPPED_EARLY,
    )

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "available"
    assert [workout.prescription.id for workout in evidence.workouts] == ["w_easy_1"]


def test_closed_revision_tampering_makes_adherence_unavailable(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    closed_state = _close_test_plan(repo)
    reference = closed_state.closed_plan_references[0]
    archive_path = repo.resolve_path(f"data/plans/archive/{reference.plan_id}.json")
    archive_path.write_text(
        archive_path.read_text().replace(
            "Aerobic support",
            "Content changed after archival",
        )
    )

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "unavailable"
    assert evidence.reason is not None
    assert "changed after closure" in evidence.reason


def test_planning_aggregate_rejects_orphaned_historical_vdot_approval(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    _close_test_plan(repo)
    proposal_path = _write_vdot_proposal(tmp_path)
    state = approve_vdot_proposal(
        repo,
        proposal_path,
        approved_at_utc=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )
    assert state.active_vdot_approval is not None
    error = save_planning_state(
        state.model_copy(update={"vdot_approvals": [state.active_vdot_approval]}),
        repo,
    )
    assert error is None

    with pytest.raises(
        PlanOperationError,
        match="historical VDOT approval",
    ):
        load_planning_aggregate(repo)


def test_week_replacement_preserves_original_historical_authority(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    replacement_path = tmp_path / "week-replacement.json"
    _write_application(replacement_path, purpose="Replacement purpose")
    approve_week_application(
        repo,
        replacement_path,
        approved_at_utc=datetime(2026, 7, 29, 12, tzinfo=timezone.utc),
    )
    apply_approved_week(
        repo,
        replacement_path,
        applied_at_utc=datetime(2026, 7, 29, 13, tzinfo=timezone.utc),
    )

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "available"
    assert [workout.prescription.id for workout in evidence.workouts] == [
        "w_easy_1",
        "w_easy_2",
        "w_long_1",
    ]
    assert evidence.workouts[0].prescription.purpose == "Aerobic support"


def test_application_after_scheduled_instant_is_not_retroactive(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    payload_path = tmp_path / "late-week.json"
    _write_application(payload_path)
    approve_week_application(
        repo,
        payload_path,
        approved_at_utc=datetime(2026, 7, 28, 7, tzinfo=timezone.utc),
    )
    apply_approved_week(
        repo,
        payload_path,
        applied_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
    )

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "available"
    assert [workout.prescription.id for workout in evidence.workouts] == [
        "w_easy_2",
        "w_long_1",
    ]


def test_future_week_planning_context_separates_target_from_evidence(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "activities").mkdir(parents=True)
    _create_approved_macro(repo, tmp_path)

    context = build_week_planning_context(
        repo,
        week_number=1,
        evidence_as_of_date=date(2026, 7, 26),
        history_week_count=2,
        current_local_date=date(2026, 7, 30),
    )

    assert context.target_week.start_date == date(2026, 7, 27)
    assert context.evidence_as_of_date == date(2026, 7, 26)
    assert context.recent_history.evidence_window_end == date(2026, 7, 26)
    assert context.recent_history.target_week_end == date(2026, 7, 26)
    assert context.target_week.target_week_skeleton_sha256

    with pytest.raises(ValueError, match="cannot be in the future"):
        build_week_planning_context(
            repo,
            week_number=1,
            evidence_as_of_date=date(2026, 7, 31),
            history_week_count=2,
            current_local_date=date(2026, 7, 30),
        )


def test_planning_context_supports_an_exact_applied_week_revision(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)

    context = build_week_planning_context(
        repo,
        week_number=1,
        evidence_as_of_date=date(2026, 7, 26),
        history_week_count=2,
        current_local_date=date(2026, 7, 30),
    )

    assert context.target_week.week_number == 1
    assert context.target_week.target_run_volume_meters == 10_000


def test_exact_applied_workouts_remain_readable_after_policy_evolves(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_plan is not None

    active_plan = state.active_plan
    current_week = active_plan.plan.weeks[0]
    earlier_week = current_week.model_copy(
        update={
            "workouts": [
                workout.model_copy(update={"structured_workout": None})
                for workout in current_week.workouts
            ]
        }
    )
    active_revision = active_plan.applied_week_revisions[0].model_copy(
        update={
            "applied_workout_sha256": applied_workout_sha256(earlier_week),
            "applied_week_snapshot": earlier_week,
        }
    )
    earlier_plan = active_plan.plan.model_copy(update={"weeks": [earlier_week]})
    error = save_planning_state(
        state.model_copy(
            update={
                "active_plan": active_plan.model_copy(
                    update={
                        "plan": earlier_plan,
                        "applied_week_revisions": [active_revision],
                    }
                )
            }
        ),
        repo,
    )
    assert error is None

    assert load_publishable_workout(repo, "w_easy_1").prescription.id == "w_easy_1"


def test_publication_requires_unchanged_applied_workout_bytes(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    payload_path = tmp_path / "week.json"
    _write_application(payload_path)
    approve_week_application(repo, payload_path)

    with pytest.raises(PlanOperationError, match="does not identify"):
        load_publishable_workout(repo, "w_easy_1")

    apply_approved_week(repo, payload_path)
    assert (
        load_publishable_workout(
            repo,
            "w_easy_1",
        ).prescription.id
        == "w_easy_1"
    )

    state = load_planning_aggregate(repo)
    assert state is not None and state.active_plan is not None
    current_week = state.active_plan.plan.weeks[0]
    changed_workout = current_week.workouts[0].model_copy(
        update={"purpose": "Changed after application"}
    )
    changed_week = current_week.model_copy(
        update={
            "workouts": [
                changed_workout,
                *current_week.workouts[1:],
            ]
        }
    )
    changed_plan = state.active_plan.plan.model_copy(update={"weeks": [changed_week]})
    error = save_planning_state(
        state.model_copy(
            update={"active_plan": state.active_plan.model_copy(update={"plan": changed_plan})}
        ),
        repo,
    )
    assert error is None

    with pytest.raises(PlanOperationError, match="changed after"):
        load_publishable_workout(repo, "w_easy_1")


def test_applied_week_audit_rejects_naive_timestamp(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    state = load_planning_aggregate(repo)
    assert state is not None
    assert state.active_plan is not None
    payload = state.active_plan.applied_week_revisions[0].model_dump(mode="python")
    payload["applied_at_utc"] = datetime(2026, 7, 27)

    with pytest.raises(ValidationError, match="timezone-aware"):
        AppliedWeekRevision.model_validate(payload)


def test_applied_week_audit_rejects_unknown_schedule_timezone(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    state = load_planning_aggregate(repo)
    assert state is not None
    assert state.active_plan is not None
    payload = state.active_plan.applied_week_revisions[0].model_dump(mode="python")
    payload["schedule_timezone"] = "Paris local time"

    with pytest.raises(ValidationError, match="recognized IANA timezone"):
        AppliedWeekRevision.model_validate(payload)


def test_plan_invalidation_metadata_must_be_complete(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    create_macro_plan(repo, _draft(approval_id))
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_plan is not None
    with pytest.raises(ValidationError, match="requires timestamp and reason"):
        PlanningState.model_validate(
            state.model_copy(
                update={
                    "active_plan": state.active_plan.model_copy(
                        update={
                            "invalidated_at_utc": datetime(
                                2026,
                                7,
                                27,
                                tzinfo=timezone.utc,
                            ),
                        }
                    )
                }
            ).model_dump(mode="python")
        )


def test_only_an_unapproved_unapplied_plan_proposal_can_be_discarded(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    first_plan = create_macro_plan(repo, _draft(approval_id))

    discarded_state = discard_unapproved_current_plan(
        repo,
        expected_plan_revision_id=first_plan.plan_revision_id,
    )

    assert discarded_state.active_plan is None
    replacement_plan = create_macro_plan(repo, _draft(approval_id))
    assert replacement_plan.id != first_plan.id
    approve_current_plan(
        repo,
        approved_at_utc=replacement_plan.created_at_utc,
    )

    with pytest.raises(PlanOperationError, match="approved plan"):
        discard_unapproved_current_plan(
            repo,
            expected_plan_revision_id=replacement_plan.plan_revision_id,
        )


def test_unapproved_plan_with_completion_ownership_cannot_be_discarded(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    plan = create_macro_plan(repo, _draft(approval_id))
    save_completion_manifest(
        repo,
        WorkoutCompletionManifest(
            matches={
                "owned_activity": WorkoutCompletionMatch(
                    local_activity_id="owned_activity",
                    workout_identity={
                        "plan_id": plan.id,
                        "plan_revision_id": plan.plan_revision_id,
                        "week_number": 1,
                        "local_workout_id": "owned_workout",
                    },
                    match_method="paired_event_id",
                    matched_at_utc=datetime(2026, 7, 27, tzinfo=timezone.utc),
                )
            }
        ),
    )

    with pytest.raises(PlanOperationError, match="ownership records exist"):
        discard_unapproved_current_plan(
            repo,
            expected_plan_revision_id=plan.plan_revision_id,
        )
