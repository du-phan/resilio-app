"""End-to-end baseline-assessment planning, review, and VDOT evidence."""

import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.approval_evidence import verify_vdot_approval
from resilio.core.planning.artifacts import (
    archive_path,
    canonical_data_sha256,
    canonical_json_bytes,
    evidence_path,
    load_all_closed_plan_archives,
    load_evidence_artifact,
    model_sha256,
)
from resilio.core.planning.assessment_context import (
    create_assessment_planning_context,
)
from resilio.core.planning.assessment_evidence import (
    load_verified_closed_assessment_review,
)
from resilio.core.planning.assessment_review import (
    close_assessment_from_review,
    create_assessment_review,
    list_assessment_result_candidates,
)
from resilio.core.planning.assessment_vdot import (
    create_vdot_proposal_from_assessment,
)
from resilio.core.planning.integrity import plan_skeleton_sha256
from resilio.core.planning.macro_context import create_macro_planning_context
from resilio.core.planning.service import (
    PlanOperationError,
    apply_approved_week,
    approve_current_plan,
    approve_vdot_proposal,
    approve_week_application,
    create_assessment_plan,
    load_approved_workouts_for_date_range,
    load_planning_aggregate,
)
from resilio.core.planning.state_repository import persist_planning_state
from resilio.core.planning.weekly_context import create_week_planning_context
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.migration import (
    WorkoutFulfillmentMigrationError,
    migrate_workout_fulfillment_state,
)
from resilio.core.workout_fulfillment.repository import save_fulfillment_manifest
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.schemas.assessment import TemporaryScheduleConstraint
from resilio.schemas.plan_history import EvidenceArtifactReference
from resilio.schemas.planning.drafts import AssessmentPlanDraft
from resilio.schemas.planning_evidence import (
    AssessmentPlanningContext,
    BaselineAssessmentReview,
    MacroPlanningContext,
)
from resilio.schemas.profile import (
    AthleteManagedSport,
    AthleteManagedSportFirstPriority,
    AthleteProfile,
    FlexibleWeeklyParticipation,
    Goal,
    GoalType,
    TrainingConstraints,
)
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    PublishedWorkout,
)
from resilio.schemas.workout_fulfillment import (
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from tests.factories import make_activity


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RepositoryIO:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repository = RepositoryIO()
    ProfileRepository(repository).create(
        AthleteProfile(
            athlete_name="Alex",
            created_on=date(2026, 8, 1),
            training_timezone="Europe/Paris",
            constraints=TrainingConstraints(
                minimum_run_days_per_week=2,
                maximum_run_days_per_week=3,
            ),
            athlete_managed_sports=[
                AthleteManagedSport(
                    sport_name="climb",
                    participation_pattern=FlexibleWeeklyParticipation(
                        expected_sessions_per_week=3,
                    ),
                    typical_session_duration_minutes=90,
                    athlete_reported_typical_intensity="moderate_to_hard",
                )
            ],
            training_priority=AthleteManagedSportFirstPriority(sport_name="climb"),
            goal=Goal(
                type=GoalType.HALF_MARATHON,
                target_date=date(2026, 11, 14),
            ),
        )
    )
    return repository


def _assessment_draft(
    context: AssessmentPlanningContext,
    context_sha256: str,
) -> AssessmentPlanDraft:
    latest_week_id = f"recent_week.{context.recent_detailed_weeks[-1].week_start.isoformat()}"
    return AssessmentPlanDraft.model_validate(
        {
            "planning_context_reference": {
                "artifact_type": "assessment_planning_context",
                "artifact_sha256": context_sha256,
            },
            "planning_rationale": (
                "A cautious two-week return restores running exposure before one "
                "athlete-approved five-kilometre benchmark."
            ),
            "adaptation_decisions": [
                {
                    "decision_type": "starting_volume",
                    "evidence_ids": [latest_week_id],
                    "observed_facts": (
                        "The latest synchronized week contains no current running "
                        "load after the athlete's recorded interruption."
                    ),
                    "planning_change": (
                        "Start with two short easy runs and progress without "
                        "exceeding three weekly runs."
                    ),
                    "affected_week_numbers": [1, 2, 3],
                },
                {
                    "decision_type": "athlete_managed_sport_accommodation",
                    "evidence_ids": [
                        "profile.current_constraints",
                    ],
                    "observed_facts": (
                        "The holiday shortens the benchmark week while climbing "
                        "remains the athlete's primary sport."
                    ),
                    "planning_change": (
                        "Leave climbing athlete-managed and preserve enough run "
                        "recovery space for its expected weekly exposure."
                    ),
                    "affected_week_numbers": [3],
                },
                {
                    "decision_type": "benchmark_scheduling",
                    "evidence_ids": [
                        "profile.current_constraints",
                        "assessment.temporary_schedule_constraints",
                    ],
                    "observed_facts": (
                        "The athlete is unavailable from Friday 21 through Monday "
                        "24 August and keeps climbing days flexible."
                    ),
                    "planning_change": (
                        "Prefer Thursday 20 August with fallback from Tuesday 18 "
                        "through Thursday 20 August."
                    ),
                    "affected_week_numbers": [3],
                },
            ],
            "assessment_reasons": ["post_inactivity_baseline"],
            "benchmark_intent": {
                "race_distance": "5k",
                "preferred_date": "2026-08-20",
                "fallback_window_start": "2026-08-18",
                "fallback_window_end": "2026-08-20",
            },
            "temporary_schedule_constraints": [
                constraint.model_dump(mode="json")
                for constraint in context.temporary_schedule_constraints
            ],
            "weeks": [
                {
                    "week_number": number,
                    "phase": "base" if number < 3 else "assessment",
                    "start_date": start,
                    "end_date": end,
                    "target_run_volume_meters": volume,
                    "workout_structure_hints": {
                        "quality": {
                            "maximum_sessions": 0 if number < 3 else 1,
                            "types": [] if number < 3 else ["benchmark"],
                        },
                        "long_run": None,
                        "intensity_distribution": None,
                    },
                    "running_workouts": [],
                }
                for number, start, end, volume in (
                    (1, "2026-08-03", "2026-08-09", 8_000),
                    (2, "2026-08-10", "2026-08-16", 10_000),
                    (3, "2026-08-17", "2026-08-23", 12_000),
                )
            ],
        }
    )


def _benchmark_week(*, start_time_local: time | None) -> dict[str, object]:
    return {
        "schema_version": 2,
        "week_number": 3,
        "adjustment_rationale": (
            "Keep one easy aerobic run before the benchmark and leave the holiday "
            "period completely free of planned sessions."
        ),
        "running_workouts": [
            {
                "id": "w_assessment_easy",
                "date": "2026-08-18",
                "start_time_local": None,
                "sport": "run",
                "workout_type": "easy",
                "planned_duration_seconds": 1_800,
                "planned_distance_meters": 5_000,
                "planned_low_intensity_duration_seconds": 1_800,
                "planned_moderate_intensity_duration_seconds": 0,
                "planned_high_intensity_duration_seconds": 0,
                "target_rpe_1_to_10": 3,
                "purpose": "Easy return run before the benchmark.",
                "structured_workout": {
                    "sport": "run",
                    "steps": [
                        {
                            "kind": "steady",
                            "duration": {"unit": "seconds", "value": 1_800},
                            "intensity": "active",
                            "cue": "Keep the effort conversational.",
                        }
                    ],
                },
            },
            {
                "id": "w_assessment_5k",
                "date": "2026-08-20",
                "start_time_local": (
                    start_time_local.isoformat() if start_time_local is not None else None
                ),
                "sport": "run",
                "workout_type": "benchmark",
                "planned_duration_seconds": 3_000,
                "planned_distance_meters": 7_000,
                "planned_low_intensity_duration_seconds": 1_200,
                "planned_moderate_intensity_duration_seconds": 0,
                "planned_high_intensity_duration_seconds": 1_800,
                "target_rpe_1_to_10": 9,
                "purpose": "Five-kilometre baseline benchmark.",
                "structured_workout": {
                    "sport": "run",
                    "steps": [
                        {
                            "kind": "steady",
                            "duration": {"unit": "seconds", "value": 600},
                            "intensity": "warmup",
                        },
                        {
                            "kind": "timed_distance",
                            "distance_meters": 5_000,
                            "nominal_seconds": 1_800,
                            "cue": "Run a controlled best sustainable effort.",
                        },
                        {
                            "kind": "steady",
                            "duration": {"unit": "seconds", "value": 600},
                            "intensity": "cooldown",
                        },
                    ],
                },
            },
        ],
    }


def _apply_week(
    repo: RepositoryIO,
    path: Path,
    payload: dict[str, object],
    *,
    approved_at_utc: datetime,
    applied_at_utc: datetime,
) -> None:
    context_reference = create_week_planning_context(
        repo,
        week_number=3,
        evidence_as_of_date=approved_at_utc.date(),
        history_week_count=2,
        generated_at_utc=approved_at_utc - timedelta(minutes=1),
        current_local_date=approved_at_utc.date(),
    )
    bound_payload = {
        **payload,
        "planning_context_reference": context_reference.model_dump(mode="json"),
        "other_sport_considerations": [
            {
                "sport_name": "climb",
                "recent_activity_ids": [],
                "effects_on_running_plan": ["recovery_spacing"],
                "rationale": (
                    "Expected athlete-managed climbing exposure requires recovery "
                    "space around the exact running sessions."
                ),
                "uncertainty_or_limitation": (
                    "Climbing days remain self-scheduled and are not yet observed."
                ),
            }
        ],
    }
    path.write_text(json.dumps(bound_payload))
    approve_week_application(repo, path, approved_at_utc=approved_at_utc)
    apply_approved_week(repo, path, applied_at_utc=applied_at_utc)


def _record_owned_completion(
    repo: RepositoryIO,
    plan: object,
) -> None:
    benchmark = next(
        workout
        for week in plan.weeks
        for workout in week.running_workouts
        if workout.id == "w_assessment_5k"
    )
    identity = {
        "plan_id": plan.id,
        "plan_revision_id": plan.plan_revision_id,
        "week_number": 3,
        "local_workout_id": benchmark.id,
    }
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_plan is not None
    applied_revision = next(
        revision
        for revision in state.active_plan.applied_week_revisions
        if revision.active and revision.week_number == 3
    )
    save_manifest(
        repo,
        PublicationManifest(
            workouts={
                benchmark.id: PublishedWorkout(
                    workout_identity=identity,
                    applied_week_approval_id=applied_revision.approval_id,
                    applied_running_workouts_sha256=(
                        applied_revision.applied_running_workouts_sha256
                    ),
                    workout_prescription_sha256=canonical_data_sha256(benchmark),
                    schedule_timezone=applied_revision.schedule_timezone,
                    event_id=42,
                    requested_uid="requested-assessment-uid",
                    uid="assessment-uid",
                    external_id="resilio:v1:workout:w_assessment_5k",
                    publication_fingerprint_sha256="1" * 64,
                    rendered_workout_sha256="2" * 64,
                    sport_settings_version_sha256="3" * 64,
                    provider_event_fingerprint_sha256="4" * 64,
                    sport="run",
                    occurrence_date=date(2026, 8, 20),
                    approved_start_time_local=time(7),
                    provider_start_date_local="2026-08-20T07:00:00",
                    garmin_forwarding_status="eligible_unverified",
                    verified_at_utc=datetime(2026, 8, 19, 8, tzinfo=timezone.utc),
                )
            }
        ),
    )
    activity = make_activity(
        id="benchmark_activity",
        date=date(2026, 8, 20),
        duration_seconds=2_400,
        moving_seconds=2_350,
        distance_meters=7_050,
        segments=[
            {
                "index": 1,
                "name": "5K benchmark",
                "origin_kind": "intervals_icu_interval",
                "elapsed_seconds": 1_500,
                "moving_seconds": 1_495,
                "distance_meters": 5_000,
                "start_time_utc": "2026-08-20T05:10:00Z",
                "start_time_local": "2026-08-20T07:10:00+02:00",
                "interval_kind": "work",
            }
        ],
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    publication = load_manifest(repo).workouts[benchmark.id]
    save_fulfillment_manifest(
        repo,
        WorkoutFulfillmentManifest(
            fulfillments={
                activity.local_activity_id: WorkoutFulfillmentRecord(
                    local_activity_id=activity.local_activity_id,
                    workout_identity=identity,
                    applied_week_approval_id=publication.applied_week_approval_id,
                    applied_running_workouts_sha256=(publication.applied_running_workouts_sha256),
                    workout_prescription_sha256=(publication.workout_prescription_sha256),
                    activity_performance_evidence_sha256=(
                        activity_performance_evidence_sha256(activity)
                    ),
                    schedule_timezone=publication.schedule_timezone,
                    scheduled_local_date=publication.occurrence_date,
                    execution_local_date=activity.occurrence.local_date,
                    schedule_offset_days=0,
                    provider_pair=ProviderPairedFulfillmentEvidence(
                        event_id=publication.event_id,
                        observed_at_utc=datetime(2026, 8, 20, 8, tzinfo=timezone.utc),
                    ),
                    recorded_at_utc=datetime(2026, 8, 20, 8, tzinfo=timezone.utc),
                )
            }
        ),
    )


def test_assessment_context_contract_rejects_evidence_from_after_generation(
    repo: RepositoryIO,
) -> None:
    reference = create_assessment_planning_context(
        repo,
        evidence_as_of_date=date(2026, 8, 2),
        intended_plan_start_date=date(2026, 8, 3),
        assessment_reasons=["post_inactivity_baseline"],
        generated_at_utc=datetime(2026, 8, 2, 8, tzinfo=timezone.utc),
        current_local_date=date(2026, 8, 2),
    )
    context = load_evidence_artifact(repo, reference, AssessmentPlanningContext)
    payload = context.model_dump(mode="json")
    payload["generated_at_utc"] = "2026-08-01T08:00:00Z"

    with pytest.raises(ValidationError, match="postdate context generation"):
        AssessmentPlanningContext.model_validate(payload)


def test_assessment_lifecycle_supports_timed_replacement_segment_review_and_vdot(
    repo: RepositoryIO,
    tmp_path: Path,
) -> None:
    context_reference = create_assessment_planning_context(
        repo,
        evidence_as_of_date=date(2026, 8, 2),
        intended_plan_start_date=date(2026, 8, 3),
        assessment_reasons=["post_inactivity_baseline"],
        temporary_schedule_constraints=[
            TemporaryScheduleConstraint(
                unavailable_start_date=date(2026, 8, 21),
                unavailable_end_date=date(2026, 8, 24),
                reason="The athlete is away for the complete four-day holiday.",
                athlete_confirmation_reference=(
                    "Athlete confirmed 21-24 August 2026 as unavailable."
                ),
            )
        ],
        generated_at_utc=datetime(2026, 8, 2, 8, tzinfo=timezone.utc),
        current_local_date=date(2026, 8, 2),
    )
    context = load_evidence_artifact(
        repo,
        context_reference,
        AssessmentPlanningContext,
    )
    assert context.temporary_schedule_constraints[0].unavailable_end_date == date(2026, 8, 24)
    assert any(
        pointer.evidence_id == "assessment.temporary_schedule_constraints"
        for pointer in context.evidence_index
    )
    plan = create_assessment_plan(
        repo,
        _assessment_draft(context, context_reference.artifact_sha256),
        created_at_utc=datetime(2026, 8, 2, 9, tzinfo=timezone.utc),
    )
    approve_current_plan(
        repo,
        approved_at_utc=datetime(2026, 8, 2, 10, tzinfo=timezone.utc),
    )

    week_path = tmp_path / "assessment-week-3.json"
    _apply_week(
        repo,
        week_path,
        _benchmark_week(start_time_local=None),
        approved_at_utc=datetime(2026, 8, 16, 8, tzinfo=timezone.utc),
        applied_at_utc=datetime(2026, 8, 16, 9, tzinfo=timezone.utc),
    )
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_plan is not None
    date_only = next(
        workout
        for workout in state.active_plan.plan.weeks[2].running_workouts
        if workout.id == "w_assessment_5k"
    )
    assert date_only.start_time_local is None
    authoritative = load_approved_workouts_for_date_range(
        repo,
        window_start=date(2026, 8, 17),
        window_end=date(2026, 8, 23),
    )
    assert authoritative.status == "available"
    assert len(authoritative.workouts) == 2

    _apply_week(
        repo,
        week_path,
        _benchmark_week(start_time_local=time(7)),
        approved_at_utc=datetime(2026, 8, 17, 6, tzinfo=timezone.utc),
        applied_at_utc=datetime(2026, 8, 17, 6, 5, tzinfo=timezone.utc),
    )
    state = load_planning_aggregate(repo)
    assert state is not None and state.active_plan is not None
    plan = state.active_plan.plan
    assert len(state.active_plan.applied_week_revisions) == 2
    assert sum(revision.active for revision in state.active_plan.applied_week_revisions) == 1

    _record_owned_completion(repo, plan)
    candidates = list_assessment_result_candidates(repo)
    assert [candidate.candidate_id for candidate in candidates] == [
        "activity:benchmark_activity",
        "segment:benchmark_activity:1",
    ]
    review_reference = create_assessment_review(
        repo,
        candidate_id="segment:benchmark_activity:1",
        evidence_as_of_date=date(2026, 8, 20),
        official_distance_confirmation_reference=(
            "Athlete confirmed segment 1 represents the complete five-kilometre test."
        ),
        athlete_confirmation_reference=(
            "Athlete selected canonical segment 1 as the assessment result."
        ),
        review_summary=(
            "The exact owned five-kilometre segment is the athlete-confirmed "
            "baseline result after the gradual return block."
        ),
        generated_at_utc=datetime(2026, 8, 20, 18, tzinfo=timezone.utc),
    )
    review = load_evidence_artifact(
        repo,
        review_reference,
        BaselineAssessmentReview,
    )
    assert review.result.result_kind == "exact_segment"
    assert review.result.elapsed_time_seconds == 1_500

    manifest = load_manifest(repo)
    manifest.pending["future_owned_workout"] = PendingWorkoutPublication(
        workout_identity={
            "plan_id": plan.id,
            "plan_revision_id": plan.plan_revision_id,
            "week_number": 3,
            "local_workout_id": "future_owned_workout",
        },
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="7" * 64,
        workout_prescription_sha256="8" * 64,
        schedule_timezone="Europe/Paris",
        uid="future-owned-uid",
        external_id="resilio:v1:workout:future_owned_workout",
        publication_fingerprint_sha256="4" * 64,
        rendered_workout_sha256="5" * 64,
        sport_settings_version_sha256="6" * 64,
        sport="run",
        occurrence_date=date(2026, 8, 21),
        approved_start_time_local=time(7),
        provider_start_date_local="2026-08-21T07:00:00",
        prepared_at_utc=datetime(2026, 8, 20, 18, 30, tzinfo=timezone.utc),
    )
    save_manifest(repo, manifest)
    with pytest.raises(PlanOperationError, match="future owned"):
        close_assessment_from_review(
            repo,
            assessment_review_reference=review_reference,
            reason=("The athlete completed and confirmed the planned baseline benchmark."),
            athlete_confirmation_reference=(
                "Athlete approved closing the completed baseline assessment."
            ),
            closed_at_utc=datetime(2026, 8, 20, 19, tzinfo=timezone.utc),
        )
    manifest.pending.clear()
    save_manifest(repo, manifest)

    closed_state = close_assessment_from_review(
        repo,
        assessment_review_reference=review_reference,
        reason=("The athlete completed and confirmed the planned baseline benchmark."),
        athlete_confirmation_reference=(
            "Athlete approved closing the completed baseline assessment."
        ),
        closed_at_utc=datetime(2026, 8, 20, 19, tzinfo=timezone.utc),
    )
    assert closed_state.active_plan is None
    assert len(closed_state.closed_plan_references) == 1

    proposal = create_vdot_proposal_from_assessment(
        repo,
        review_sha256=review_reference.artifact_sha256,
        generated_at_utc=datetime(2026, 8, 21, 8, tzinfo=timezone.utc),
    )
    assert proposal.evidence_type == "owned_baseline_assessment"
    proposal_path = tmp_path / "assessment-vdot.json"
    proposal_path.write_text(proposal.model_dump_json(indent=2))
    approved_state = approve_vdot_proposal(
        repo,
        proposal_path,
        approved_at_utc=datetime(2026, 8, 21, 9, tzinfo=timezone.utc),
    )
    assert approved_state.active_vdot_approval is not None
    assert approved_state.active_vdot_approval.evidence_type == "owned_baseline_assessment"

    archive = load_all_closed_plan_archives(
        repo,
        approved_state.closed_plan_references,
    )[0]
    archived_plan = archive.active_plan_snapshot.plan
    current_context_reference = archived_plan.planning_context_reference
    current_context_path = repo.resolve_path(evidence_path(current_context_reference))
    legacy_context_payload = json.loads(current_context_path.read_text())
    for weekly_context in legacy_context_payload["recent_detailed_weeks"]:
        weekly_context.pop("schema_version")
        adherence = weekly_context["adherence"]
        adherence.pop("schema_version")
        adherence["verified_completed_workout_count"] = adherence.pop("due_fulfilled_workout_count")
        adherence["due_unmatched_workout_count"] = adherence.pop("due_unfulfilled_workout_count")
        adherence.pop("fulfilled_workout_count")
        adherence.pop("fulfilled_early_workout_count")
        adherence.pop("fulfilled_late_workout_count")
    legacy_context_bytes = (
        json.dumps(
            legacy_context_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode()
    legacy_context_reference = EvidenceArtifactReference(
        artifact_type="assessment_planning_context",
        artifact_sha256=hashlib.sha256(legacy_context_bytes).hexdigest(),
    )
    legacy_context_path = repo.resolve_path(evidence_path(legacy_context_reference))
    legacy_context_path.write_bytes(legacy_context_bytes)
    current_context_path.unlink()

    legacy_plan = archived_plan.model_copy(
        update={"planning_context_reference": legacy_context_reference}
    )
    legacy_active_plan = archive.active_plan_snapshot.model_copy(
        update={
            "plan": legacy_plan,
            "plan_approval": archive.active_plan_snapshot.plan_approval.model_copy(
                update={"plan_skeleton_sha256": plan_skeleton_sha256(legacy_plan)}
            ),
        }
    )
    legacy_review = review.model_copy(
        update={"active_plan_sha256": canonical_data_sha256(legacy_active_plan)}
    )
    legacy_review_bytes = canonical_json_bytes(legacy_review)
    legacy_review_reference = EvidenceArtifactReference(
        artifact_type="assessment_review",
        artifact_sha256=hashlib.sha256(legacy_review_bytes).hexdigest(),
    )
    legacy_review_path = repo.resolve_path(evidence_path(legacy_review_reference))
    legacy_review_path.write_bytes(legacy_review_bytes)
    repo.resolve_path(evidence_path(review_reference)).unlink()
    legacy_archive = archive.model_copy(
        update={
            "active_plan_snapshot": legacy_active_plan,
            "closure": archive.closure.model_copy(
                update={
                    "assessment_review_artifact_sha256": (legacy_review_reference.artifact_sha256)
                }
            ),
        }
    )
    repo.resolve_path(archive_path(archived_plan.id)).write_bytes(
        canonical_json_bytes(legacy_archive)
    )

    approved_vdot = approved_state.active_vdot_approval
    assert approved_vdot is not None
    legacy_vdot_evidence = approved_vdot.proposal_snapshot.evidence.model_copy(
        update={"assessment_review_sha256": legacy_review_reference.artifact_sha256}
    )
    legacy_vdot_proposal = approved_vdot.proposal_snapshot.model_copy(
        update={"evidence": legacy_vdot_evidence}
    )
    legacy_vdot_bytes = legacy_vdot_proposal.model_dump_json(indent=2).encode()
    proposal_path.write_bytes(legacy_vdot_bytes)
    legacy_vdot_approval = approved_vdot.model_copy(
        update={
            "proposal_file_sha256": hashlib.sha256(legacy_vdot_bytes).hexdigest(),
            "proposal_snapshot": legacy_vdot_proposal,
        }
    )
    legacy_state = approved_state.model_copy(
        update={
            "vdot_approvals": [legacy_vdot_approval],
            "closed_plan_references": [
                approved_state.closed_plan_references[0].model_copy(
                    update={"archive_sha256": model_sha256(legacy_archive)}
                )
            ],
        }
    )

    orphan_review = legacy_review.model_copy(
        update={
            "review_summary": (
                "This byte-distinct assessment review is intentionally not owned by the "
                "closed assessment archive."
            )
        }
    )
    orphan_review_bytes = canonical_json_bytes(orphan_review)
    orphan_review_reference = EvidenceArtifactReference(
        artifact_type="assessment_review",
        artifact_sha256=hashlib.sha256(orphan_review_bytes).hexdigest(),
    )
    repo.resolve_path(evidence_path(orphan_review_reference)).write_bytes(orphan_review_bytes)
    orphan_evidence = legacy_vdot_evidence.model_copy(
        update={"assessment_review_sha256": orphan_review_reference.artifact_sha256}
    )
    orphan_proposal = legacy_vdot_proposal.model_copy(update={"evidence": orphan_evidence})
    orphan_proposal_bytes = orphan_proposal.model_dump_json(indent=2).encode()
    proposal_path.write_bytes(orphan_proposal_bytes)
    orphan_approval = legacy_vdot_approval.model_copy(
        update={
            "proposal_file_sha256": hashlib.sha256(orphan_proposal_bytes).hexdigest(),
            "proposal_snapshot": orphan_proposal,
        }
    )
    persist_planning_state(
        repo,
        legacy_state.model_copy(update={"vdot_approvals": [orphan_approval]}),
    )
    with pytest.raises(
        WorkoutFulfillmentMigrationError,
        match="does not belong to a closed assessment archive",
    ):
        migrate_workout_fulfillment_state(repo, apply=False)

    mismatched_result = legacy_vdot_evidence.result.model_copy(
        update={"performance_evidence_sha256": "0" * 64}
    )
    mismatched_evidence = legacy_vdot_evidence.model_copy(update={"result": mismatched_result})
    mismatched_proposal = legacy_vdot_proposal.model_copy(update={"evidence": mismatched_evidence})
    mismatched_proposal_bytes = mismatched_proposal.model_dump_json(indent=2).encode()
    proposal_path.write_bytes(mismatched_proposal_bytes)
    mismatched_approval = legacy_vdot_approval.model_copy(
        update={
            "proposal_file_sha256": hashlib.sha256(mismatched_proposal_bytes).hexdigest(),
            "proposal_snapshot": mismatched_proposal,
        }
    )
    persist_planning_state(
        repo,
        legacy_state.model_copy(update={"vdot_approvals": [mismatched_approval]}),
    )
    with pytest.raises(
        WorkoutFulfillmentMigrationError,
        match="VDOT assessment evidence differs from its referenced review",
    ):
        migrate_workout_fulfillment_state(repo, apply=False)

    proposal_path.write_bytes(legacy_vdot_bytes)
    persist_planning_state(repo, legacy_state)

    activity_archive = ActivityArchive(repo.resolve_path("data/activities"))
    benchmark_activity = activity_archive.load("benchmark_activity")
    assert benchmark_activity is not None
    activity_archive.write(
        benchmark_activity.model_copy(
            update={"distance_meters": benchmark_activity.distance_meters + 10}
        )
    )
    with pytest.raises(
        WorkoutFulfillmentMigrationError,
        match="Assessment result source is invalid",
    ):
        migrate_workout_fulfillment_state(repo, apply=False)
    activity_archive.write(benchmark_activity)

    migration = migrate_workout_fulfillment_state(repo, apply=True)
    migrated_state = load_planning_aggregate(repo)

    assert migration.applied
    assert migrated_state is not None
    migrated_vdot_approval = migrated_state.active_vdot_approval
    verify_vdot_approval(repo, migrated_vdot_approval)
    migrated_review_sha256 = (
        migrated_vdot_approval.proposal_snapshot.evidence.assessment_review_sha256
    )
    load_verified_closed_assessment_review(
        repo,
        review_sha256=migrated_review_sha256,
    )
    repeated_migration = migrate_workout_fulfillment_state(repo, apply=True)
    assert not repeated_migration.changes_required
    assert not repeated_migration.applied

    macro_context_reference = create_macro_planning_context(
        repo,
        evidence_as_of_date=date(2026, 8, 23),
        intended_plan_start_date=date(2026, 8, 24),
        generated_at_utc=datetime(2026, 8, 23, 20, tzinfo=timezone.utc),
        current_local_date=date(2026, 8, 23),
    )
    macro_context = load_evidence_artifact(
        repo,
        macro_context_reference,
        MacroPlanningContext,
    )
    assert macro_context.historical_assessment_summaries[0].result == review.result
    assert any(
        pointer.evidence_id.startswith("assessment_result.")
        for pointer in macro_context.evidence_index
    )
