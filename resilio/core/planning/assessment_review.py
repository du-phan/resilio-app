"""Owned benchmark selection, review, and closure for baseline assessments."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    canonical_data_sha256,
    import_evidence_artifact,
    load_evidence_artifact,
    save_closed_plan_archive,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.source_state import coaching_evidence_source_sha256
from resilio.core.planning.state_repository import (
    persist_planning_state,
    required_planning_state_unlocked,
)
from resilio.core.planning.workout_evidence import load_publishable_workouts_unlocked
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.evidence import assert_fulfillment_is_usable
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.locking import coordinated_publication_plan_lock
from resilio.core.workout_publication.manifest import load_manifest
from resilio.schemas.activity import ActivityStatus, CanonicalActivity, is_running_sport
from resilio.schemas.approvals import ClosedPlanArchive, PlanningState
from resilio.schemas.plan_history import (
    AssessmentClosure,
    DedicatedActivityAssessmentResult,
    EvidenceArtifactReference,
    ExactSegmentAssessmentResult,
    PlanWorkoutIdentity,
)
from resilio.schemas.planning.plans import BaselineAssessmentPlan
from resilio.schemas.planning.workouts import WorkoutType
from resilio.schemas.planning_evidence import (
    AssessmentResultCandidate,
    BaselineAssessmentReview,
)


def _validated_timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PlanOperationError("Assessment-review timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def _active_assessment_plan(state: PlanningState) -> BaselineAssessmentPlan:
    if state.active_plan is None or not isinstance(
        state.active_plan.plan,
        BaselineAssessmentPlan,
    ):
        raise PlanOperationError("One active baseline-assessment plan is required")
    if state.active_plan.plan_approval is None:
        raise PlanOperationError("The baseline-assessment plan is not approved")
    return state.active_plan.plan


def _benchmark_identity(
    repo: RepositoryIO,
    state: PlanningState,
) -> PlanWorkoutIdentity:
    plan = _active_assessment_plan(state)
    benchmarks = [
        workout
        for workout in load_publishable_workouts_unlocked(repo, state)
        if workout.prescription.workout_type == WorkoutType.BENCHMARK.value
    ]
    if len(benchmarks) != 1:
        raise PlanOperationError(
            "Assessment result selection requires exactly one applied benchmark workout"
        )
    benchmark = benchmarks[0]
    if benchmark.identity.plan_id != plan.id:
        raise PlanOperationError("Applied benchmark belongs to another plan")
    return benchmark.identity


def _paired_activity(
    repo: RepositoryIO,
    benchmark_identity: PlanWorkoutIdentity,
) -> CanonicalActivity:
    publication = load_manifest(repo).workouts.get(benchmark_identity.local_workout_id)
    if publication is None or publication.workout_identity != benchmark_identity:
        raise PlanOperationError(
            "Benchmark fulfillment lacks its ownership-proven publication record"
        )
    fulfillment_manifest = load_fulfillment_manifest(repo)
    matching_records = [
        record
        for record in fulfillment_manifest.fulfillments.values()
        if record.workout_identity == benchmark_identity
        and record.independent_provider_pair_supports_event(publication.event_id)
    ]
    if len(matching_records) != 1:
        raise PlanOperationError(
            "Benchmark result requires one ownership-paired fulfillment activity"
        )
    fulfillment = matching_records[0]
    activity = ActivityArchive(repo.resolve_path("data/activities")).load(
        fulfillment.local_activity_id
    )
    if activity is None or activity.status != ActivityStatus.ACTIVE:
        raise PlanOperationError("Paired benchmark activity is absent or inactive")
    if not is_running_sport(activity.sport):
        raise PlanOperationError("Paired benchmark activity must be a running activity")
    if activity.occurrence.timezone is None:
        raise PlanOperationError("Paired benchmark activity requires a source timezone")
    try:
        assert_fulfillment_is_usable(fulfillment, activity, fulfillment_manifest)
    except ValueError as exc:
        raise PlanOperationError(str(exc)) from exc
    return activity


def list_assessment_result_candidates(
    repo: RepositoryIO,
) -> list[AssessmentResultCandidate]:
    """List explicit whole-activity and canonical-segment result selections."""
    with coordinated_plan_lock(repo, "assessment_result_candidates"):
        return _list_assessment_result_candidates_unlocked(
            repo,
            required_planning_state_unlocked(repo),
        )


def _list_assessment_result_candidates_unlocked(
    repo: RepositoryIO,
    state: PlanningState,
) -> list[AssessmentResultCandidate]:
    plan = _active_assessment_plan(state)
    identity = _benchmark_identity(repo, state)
    activity = _paired_activity(repo, identity)
    performance_timezone = activity.occurrence.timezone
    assert performance_timezone is not None
    candidates: list[AssessmentResultCandidate] = []
    if activity.distance_meters is not None:
        candidates.append(
            AssessmentResultCandidate(
                candidate_id=f"activity:{activity.local_activity_id}",
                result_kind="dedicated_activity",
                performance_date=activity.occurrence.local_date,
                measured_distance_meters=activity.distance_meters,
                elapsed_time_seconds=activity.duration.elapsed_seconds,
                workout_identity=identity,
                local_activity_id=activity.local_activity_id,
                performance_evidence_sha256=(activity_performance_evidence_sha256(activity)),
                race_distance=plan.benchmark_intent.race_distance,
                performance_timezone=performance_timezone,
            )
        )
    for segment in activity.segments:
        if segment.distance_meters is None:
            continue
        performance_date = (
            segment.start_time_local.date()
            if segment.start_time_local is not None
            else activity.occurrence.local_date
        )
        candidates.append(
            AssessmentResultCandidate(
                candidate_id=(f"segment:{activity.local_activity_id}:{segment.index}"),
                result_kind="exact_segment",
                performance_date=performance_date,
                measured_distance_meters=segment.distance_meters,
                elapsed_time_seconds=segment.elapsed_seconds,
                segment_index=segment.index,
                segment_start_time_utc=segment.start_time_utc,
                segment_start_time_local=segment.start_time_local,
                workout_identity=identity,
                local_activity_id=activity.local_activity_id,
                performance_evidence_sha256=(activity_performance_evidence_sha256(activity)),
                race_distance=plan.benchmark_intent.race_distance,
                performance_timezone=performance_timezone,
            )
        )
    if not candidates:
        raise PlanOperationError(
            "Paired benchmark activity has no measured whole-activity or segment distance"
        )
    return candidates


def _confirmed_result(
    candidate: AssessmentResultCandidate,
    *,
    official_distance_confirmation_reference: str,
    athlete_confirmation_reference: str,
) -> DedicatedActivityAssessmentResult | ExactSegmentAssessmentResult:
    payload = {
        **candidate.model_dump(
            mode="python",
            exclude={
                "candidate_id",
                "segment_index",
                "segment_start_time_utc",
                "segment_start_time_local",
            },
        ),
        "official_distance_confirmation_reference": (official_distance_confirmation_reference),
        "athlete_confirmation_reference": athlete_confirmation_reference,
    }
    if candidate.result_kind == "dedicated_activity":
        return DedicatedActivityAssessmentResult.model_validate(payload)
    return ExactSegmentAssessmentResult.model_validate(
        {
            **payload,
            "segment_index": candidate.segment_index,
            "segment_start_time_utc": candidate.segment_start_time_utc,
            "segment_start_time_local": candidate.segment_start_time_local,
        }
    )


def create_assessment_review(
    repo: RepositoryIO,
    *,
    candidate_id: str,
    evidence_as_of_date: date,
    official_distance_confirmation_reference: str,
    athlete_confirmation_reference: str,
    review_summary: str,
    generated_at_utc: datetime | None = None,
) -> EvidenceArtifactReference:
    """Persist one athlete-confirmed candidate as immutable assessment evidence."""
    with coordinated_plan_lock(repo, "create_assessment_review"):
        state = required_planning_state_unlocked(repo)
        plan = _active_assessment_plan(state)
        candidates = _list_assessment_result_candidates_unlocked(repo, state)
        matching = [candidate for candidate in candidates if candidate.candidate_id == candidate_id]
        if len(matching) != 1:
            raise PlanOperationError("Candidate ID does not identify one current result")
        candidate = matching[0]
        result = _confirmed_result(
            candidate,
            official_distance_confirmation_reference=(official_distance_confirmation_reference),
            athlete_confirmation_reference=athlete_confirmation_reference,
        )
        generation_timestamp = _validated_timestamp(generated_at_utc)
        generation_local_date = generation_timestamp.astimezone(
            ZoneInfo(plan.constraints_snapshot.training_timezone)
        ).date()
        if evidence_as_of_date < result.performance_date:
            raise PlanOperationError("Assessment evidence date cannot predate the result")
        if evidence_as_of_date > generation_local_date:
            raise PlanOperationError("Assessment evidence date cannot postdate review generation")
        source_state_sha256 = coaching_evidence_source_sha256(
            repo,
            evidence_as_of_date=evidence_as_of_date,
            evidence_window_start=plan.start_date,
        )
        assert state.active_plan is not None
        review = BaselineAssessmentReview(
            plan_id=plan.id,
            plan_revision_id=plan.plan_revision_id,
            plan_start_date=plan.start_date,
            planned_end_date=plan.end_date,
            evidence_as_of_date=evidence_as_of_date,
            generated_at_utc=generation_timestamp,
            active_plan_sha256=canonical_data_sha256(state.active_plan),
            benchmark_intent=plan.benchmark_intent,
            benchmark_workout_identity=candidate.workout_identity,
            result=result,
            review_summary=review_summary,
            source_state_sha256=source_state_sha256,
        )
        return import_evidence_artifact(
            repo,
            review,
            artifact_type="assessment_review",
        )


def close_assessment_from_review(
    repo: RepositoryIO,
    *,
    assessment_review_reference: EvidenceArtifactReference,
    reason: str,
    athlete_confirmation_reference: str,
    closed_at_utc: datetime | None = None,
) -> PlanningState:
    """Archive the assessment only when its review still proves current evidence."""
    if assessment_review_reference.artifact_type != "assessment_review":
        raise PlanOperationError("Assessment closure requires an assessment-review reference")
    with coordinated_publication_plan_lock(repo, "close_assessment"):
        state = required_planning_state_unlocked(repo)
        plan = _active_assessment_plan(state)
        assert state.active_plan is not None
        try:
            review = load_evidence_artifact(
                repo,
                assessment_review_reference,
                BaselineAssessmentReview,
            )
        except PlanningArtifactError as exc:
            raise PlanOperationError(str(exc)) from exc
        if (
            review.plan_id != plan.id
            or review.plan_revision_id != plan.plan_revision_id
            or review.active_plan_sha256 != canonical_data_sha256(state.active_plan)
        ):
            raise PlanOperationError("Assessment changed after its immutable review")
        if review.source_state_sha256 != coaching_evidence_source_sha256(
            repo,
            evidence_as_of_date=review.evidence_as_of_date,
            evidence_window_start=plan.start_date,
        ):
            raise PlanOperationError("Assessment evidence changed after review")
        closure_timestamp = _validated_timestamp(closed_at_utc)
        closed_local_date = closure_timestamp.astimezone(
            ZoneInfo(plan.constraints_snapshot.training_timezone)
        ).date()
        if review.result.performance_date > closed_local_date:
            raise PlanOperationError("Assessment closure cannot predate its benchmark result")
        publication_manifest = load_manifest(repo)
        future_owned_ids = sorted(
            local_workout_id
            for local_workout_id, publication in publication_manifest.workouts.items()
            if publication.workout_identity.plan_id == plan.id
            and publication.workout_identity.plan_revision_id == plan.plan_revision_id
            and publication.occurrence_date > review.result.performance_date
        )
        future_pending_ids = sorted(
            local_workout_id
            for local_workout_id, publication in publication_manifest.pending.items()
            if publication.workout_identity.plan_id == plan.id
            and publication.workout_identity.plan_revision_id == plan.plan_revision_id
            and publication.occurrence_date > review.result.performance_date
        )
        if future_owned_ids or future_pending_ids:
            raise PlanOperationError(
                "Delete future owned assessment events before closure: "
                f"{future_owned_ids + future_pending_ids}"
            )
        closure = AssessmentClosure(
            effective_end_date=review.result.performance_date,
            reason=reason,
            athlete_confirmation_reference=athlete_confirmation_reference,
            assessment_review_artifact_sha256=(assessment_review_reference.artifact_sha256),
            closed_at_utc=closure_timestamp,
        )
        try:
            reference = save_closed_plan_archive(
                repo,
                ClosedPlanArchive(
                    active_plan_snapshot=state.active_plan,
                    closure=closure,
                ),
            )
        except PlanningArtifactError as exc:
            raise PlanOperationError(str(exc)) from exc
        return persist_planning_state(
            repo,
            state.model_copy(
                update={
                    "active_plan": None,
                    "closed_plan_references": [
                        *state.closed_plan_references,
                        reference,
                    ],
                }
            ),
        )
