"""Planning-state v3 revision-bound aggregate behavior."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import resilio.core.profile.repository as profile_repository_module
from resilio.core.coaching_context import build_week_planning_context
from resilio.core.planning.approval_evidence import (
    ApprovalEvidenceError,
    verify_vdot_approval,
)
from resilio.core.planning.integrity import macro_skeleton_sha256, sha256_file
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.service import (
    PlanOperationError,
    apply_approved_week,
    approve_current_macro_plan,
    approve_vdot_proposal,
    approve_week_application,
    create_macro_plan,
    load_approved_workouts_for_date_range,
    load_current_plan,
    load_planning_aggregate,
    load_publishable_workout,
    retire_current_plan,
)
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.core.state import save_planning_state
from resilio.schemas.approvals import (
    AppliedWeekRevision,
    PlanningState,
    RetiredPlanRevision,
)
from resilio.schemas.plan import MacroPlanDraft
from resilio.schemas.profile import (
    AthleteProfile,
    ConflictPolicy,
    Goal,
    GoalType,
    PBEntry,
    RunningPriority,
    TrainingConstraints,
)

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
                "schema_version": 1,
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
    assert state.vdot_approval is not None
    return state.vdot_approval.approval_id


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


def _write_application(path: Path, *, purpose: str = "Aerobic support") -> None:
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
    approve_current_macro_plan(
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


def test_macro_approval_cannot_predate_plan_creation(
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
        approve_current_macro_plan(
            repo,
            approved_at_utc=datetime(2026, 7, 25, 23, tzinfo=timezone.utc),
        )


def test_week_approval_cannot_predate_macro_approval(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _create_approved_macro(repo, tmp_path)
    payload_path = tmp_path / "backdated-week-approval.json"
    _write_application(payload_path)

    with pytest.raises(PlanOperationError, match="predate.*macro approval"):
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


def test_create_macro_plan_persists_v3_aggregate(
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
    assert state.current_plan == created
    assert loaded.schema_info.version == 3
    assert loaded.vdot_approval_id == approval_id
    assert loaded.baseline_vdot == 45


def test_unapproved_macro_is_typed_as_unavailable_adherence(
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
    assert evidence.reason == "overlapping_macro_plan_is_not_approved"


def test_macro_creation_requires_exact_approved_vdot_file(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    approval_id = _approve_vdot(repo, tmp_path)
    proposal_path = tmp_path / "vdot-45.json"
    proposal_path.write_text(proposal_path.read_text().replace("45", "46", 1))

    with pytest.raises(PlanOperationError, match="changed after approval"):
        create_macro_plan(repo, _draft(approval_id))


def test_vdot_approval_recomputes_structured_race_evidence(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    proposal_path = tmp_path / "invalid-race-vdot.json"
    proposal_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "proposed_vdot": 85,
                "evidence": {
                    "evidence_type": "race_performance",
                    "race_distance": "10k",
                    "elapsed_time_seconds": 7_200,
                    "performance_date": "2026-07-20",
                    "performance_timezone": "Europe/Paris",
                    "source_local_activity_id": "act_i_slow_10k",
                    "source_external_fingerprint_sha256": "a" * 64,
                },
                "evidence_summary": (
                    "The structured performance must determine the proposal."
                ),
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
    assert state.vdot_approval is not None
    approval = state.vdot_approval
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
    assert state.vdot_approval is not None
    impossible_approval = state.vdot_approval.model_copy(
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
                    "current_plan": plan.model_copy(
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
    assert state.plan_invalidated_at_utc is not None
    assert "constraints" in (state.plan_invalidation_reason or "")


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

    retire_current_plan(
        repo,
        reason="Athlete requested a complete macro plan replacement",
    )
    state = load_planning_aggregate(repo)
    assert state is not None and state.vdot_approval is not None
    plan_b = create_macro_plan(repo, _draft(state.vdot_approval.approval_id))
    assert plan_b.macro_revision_id != plan_a.macro_revision_id

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
    assert state is not None
    assert state.pending_weekly_approval is None
    assert len(state.applied_week_revisions) == 1
    assert state.applied_week_revisions[0].active is True

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )
    assert evidence.status == "available"
    assert [workout.id for workout in evidence.workouts] == [
        "w_easy_1",
        "w_easy_2",
        "w_long_1",
    ]


def test_retired_revision_remains_authoritative_for_historical_adherence(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    retire_current_plan(
        repo,
        reason="The athlete approved a subsequent macro plan revision",
        retired_at_utc=datetime(2026, 8, 2, 23, tzinfo=timezone.utc),
    )

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "available"
    assert [workout.id for workout in evidence.workouts] == [
        "w_easy_1",
        "w_easy_2",
        "w_long_1",
    ]


def test_unpopulated_retired_revision_does_not_hide_current_authority(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    state = load_planning_aggregate(repo)
    assert state is not None
    assert state.current_plan is not None
    assert state.macro_approval is not None
    historical_plan = state.current_plan.model_copy(
        update={
            "id": "plan_historical_empty",
            "macro_revision_id": "macro_revision_1111111111111111",
            "weeks": [state.current_plan.weeks[0].model_copy(update={"workouts": []})],
        }
    )
    historical_macro_approval = state.macro_approval.model_copy(
        update={
            "plan_id": historical_plan.id,
            "macro_revision_id": historical_plan.macro_revision_id,
            "macro_skeleton_sha256": macro_skeleton_sha256(historical_plan),
        }
    )
    historical = RetiredPlanRevision(
        plan=historical_plan,
        macro_approval=historical_macro_approval,
        applied_week_revisions=[],
        retired_at_utc=datetime(2026, 8, 2, 23, tzinfo=timezone.utc),
        retirement_reason="A draft-only historical revision was superseded",
    )
    assert (
        save_planning_state(
            state.model_copy(update={"retired_plan_revisions": [historical]}),
            repo,
        )
        is None
    )

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "available"
    assert len(evidence.workouts) == 3


def test_competing_approved_revisions_make_adherence_unavailable(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    state = load_planning_aggregate(repo)
    assert state is not None
    assert state.current_plan is not None
    assert state.macro_approval is not None
    competing_plan = state.current_plan.model_copy(
        update={
            "id": "plan_competing_history",
            "macro_revision_id": "macro_revision_2222222222222222",
        }
    )
    competing_macro_approval = state.macro_approval.model_copy(
        update={
            "plan_id": competing_plan.id,
            "macro_revision_id": competing_plan.macro_revision_id,
            "macro_skeleton_sha256": macro_skeleton_sha256(competing_plan),
        }
    )
    competing_applied = [
        approval.model_copy(
            update={
                "plan_id": competing_plan.id,
                "macro_revision_id": competing_plan.macro_revision_id,
            }
        )
        for approval in state.applied_week_revisions
    ]
    competing = RetiredPlanRevision(
        plan=competing_plan,
        macro_approval=competing_macro_approval,
        applied_week_revisions=competing_applied,
        retired_at_utc=datetime(2026, 8, 2, 23, tzinfo=timezone.utc),
        retirement_reason="A competing historical authority was preserved",
    )
    assert (
        save_planning_state(
            state.model_copy(update={"retired_plan_revisions": [competing]}),
            repo,
        )
        is None
    )

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "unavailable"
    assert evidence.reason == "competing_approved_plan_authorities"


def test_retired_revision_tampering_makes_adherence_unavailable(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    _apply_test_week(repo, tmp_path)
    retired_state = retire_current_plan(
        repo,
        reason="The athlete approved a subsequent macro plan revision",
        retired_at_utc=datetime(2026, 8, 2, 23, tzinfo=timezone.utc),
    )
    retired = retired_state.retired_plan_revisions[0]
    applied_revision = retired.applied_week_revisions[0]
    original_week = applied_revision.applied_week_snapshot
    changed_workout = original_week.workouts[0].model_copy(
        update={"purpose": "Content changed after application"}
    )
    changed_week = original_week.model_copy(
        update={"workouts": [changed_workout, *original_week.workouts[1:]]}
    )
    changed_applied_revision = applied_revision.model_copy(
        update={"applied_week_snapshot": changed_week}
    )
    changed_retired = retired.model_copy(
        update={"applied_week_revisions": [changed_applied_revision]}
    )
    assert (
        save_planning_state(
            retired_state.model_copy(update={"retired_plan_revisions": [changed_retired]}),
            repo,
        )
        is None
    )

    evidence = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 7, 27),
        window_end=date(2026, 8, 2),
    )

    assert evidence.status == "unavailable"
    assert evidence.reason == "week_1_changed_after_application"


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
    assert [workout.id for workout in evidence.workouts] == [
        "w_easy_1",
        "w_easy_2",
        "w_long_1",
    ]
    assert evidence.workouts[0].purpose == "Aerobic support"


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
    assert [workout.id for workout in evidence.workouts] == [
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
    assert load_publishable_workout(repo, "w_easy_1").id == "w_easy_1"

    state = load_planning_aggregate(repo)
    assert state is not None and state.current_plan is not None
    current_week = state.current_plan.weeks[0]
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
    changed_plan = state.current_plan.model_copy(update={"weeks": [changed_week]})
    error = save_planning_state(
        state.model_copy(update={"current_plan": changed_plan}),
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
    payload = state.applied_week_revisions[0].model_dump(mode="python")
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
    payload = state.applied_week_revisions[0].model_dump(mode="python")
    payload["schedule_timezone"] = "Paris local time"

    with pytest.raises(ValidationError, match="recognized IANA timezone"):
        AppliedWeekRevision.model_validate(payload)


def test_plan_invalidation_metadata_requires_a_current_plan() -> None:
    with pytest.raises(ValidationError, match="requires a current plan"):
        PlanningState(
            plan_invalidated_at_utc=datetime(
                2026,
                7,
                27,
                tzinfo=timezone.utc,
            ),
            plan_invalidation_reason="Planning profile changed materially",
        )
