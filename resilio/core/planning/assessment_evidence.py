"""Re-prove immutable assessment reviews and their canonical result sources."""

from __future__ import annotations

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    canonical_data_sha256,
    load_all_closed_plan_archives,
    load_evidence_artifact,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.state_repository import load_planning_aggregate_unlocked
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.evidence import assert_fulfillment_is_usable
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.manifest import load_manifest
from resilio.schemas.activity import ActivityStatus
from resilio.schemas.approvals import OwnedBaselineAssessmentVDOTEvidence
from resilio.schemas.plan_history import (
    AssessmentClosure,
    DedicatedActivityAssessmentResult,
    EvidenceArtifactReference,
    ExactSegmentAssessmentResult,
)
from resilio.schemas.planning.plans import BaselineAssessmentPlan
from resilio.schemas.planning_evidence import BaselineAssessmentReview
from resilio.schemas.publication import PublicationManifest
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentManifest


def load_verified_closed_assessment_review(
    repo: RepositoryIO,
    *,
    review_sha256: str,
) -> BaselineAssessmentReview:
    """Load one review and prove archive, fulfillment, and canonical activity facts."""
    reference = EvidenceArtifactReference(
        artifact_type="assessment_review",
        artifact_sha256=review_sha256,
    )
    try:
        review = load_evidence_artifact(
            repo,
            reference,
            BaselineAssessmentReview,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    state = load_planning_aggregate_unlocked(repo)
    if state is None:
        raise PlanOperationError("Planning state is required for assessment evidence")
    try:
        archives = load_all_closed_plan_archives(repo, state.closed_plan_references)
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    matching_archives = [
        archive
        for archive in archives
        if archive.active_plan_snapshot.plan.id == review.plan_id
        and archive.active_plan_snapshot.plan.plan_revision_id == review.plan_revision_id
    ]
    if len(matching_archives) != 1:
        raise PlanOperationError("Assessment review does not identify one closed plan archive")
    archive = matching_archives[0]
    plan = archive.active_plan_snapshot.plan
    closure = archive.closure
    if not isinstance(plan, BaselineAssessmentPlan) or not isinstance(
        closure,
        AssessmentClosure,
    ):
        raise PlanOperationError("Assessment review is not owned by a closed assessment plan")
    if (
        closure.assessment_review_artifact_sha256 != review_sha256
        or closure.effective_end_date != review.result.performance_date
        or review.active_plan_sha256 != canonical_data_sha256(archive.active_plan_snapshot)
        or review.benchmark_intent != plan.benchmark_intent
    ):
        raise PlanOperationError("Closed assessment archive does not match its review")
    verify_assessment_result_source(
        repo,
        review,
        publication_manifest=load_manifest(repo),
        fulfillment_manifest=load_fulfillment_manifest(repo),
    )
    return review


def verify_assessment_result_source(
    repo: RepositoryIO,
    review: BaselineAssessmentReview,
    *,
    publication_manifest: PublicationManifest,
    fulfillment_manifest: WorkoutFulfillmentManifest,
) -> None:
    """Prove the exact publication, fulfillment, and performance result source."""
    result = review.result
    publication = publication_manifest.workouts.get(result.workout_identity.local_workout_id)
    if publication is None or publication.workout_identity != result.workout_identity:
        raise PlanOperationError("Assessment result lacks its ownership-proven publication")
    fulfillment = fulfillment_manifest.fulfillments.get(result.local_activity_id)
    if (
        fulfillment is None
        or not fulfillment.provider_pair_supports_event(publication.event_id)
        or fulfillment.workout_identity != result.workout_identity
    ):
        raise PlanOperationError("Assessment result lacks its exact ownership-paired fulfillment")
    activity = ActivityArchive(repo.resolve_path("data/activities")).load(result.local_activity_id)
    if activity is None or activity.status != ActivityStatus.ACTIVE:
        raise PlanOperationError("Assessment result activity is absent or inactive")
    try:
        assert_fulfillment_is_usable(fulfillment, activity, fulfillment_manifest)
    except ValueError as exc:
        raise PlanOperationError(str(exc)) from exc
    if activity_performance_evidence_sha256(activity) != result.performance_evidence_sha256:
        raise PlanOperationError("Assessment result performance evidence changed")
    if isinstance(result, DedicatedActivityAssessmentResult):
        if (
            activity.distance_meters is None
            or abs(activity.distance_meters - result.measured_distance_meters) > 0.01
            or activity.duration.elapsed_seconds != result.elapsed_time_seconds
            or activity.occurrence.local_date != result.performance_date
            or activity.occurrence.timezone != result.performance_timezone
        ):
            raise PlanOperationError("Dedicated assessment activity no longer matches its result")
        return
    assert isinstance(result, ExactSegmentAssessmentResult)
    segments = [segment for segment in activity.segments if segment.index == result.segment_index]
    if len(segments) != 1:
        raise PlanOperationError("Assessment result segment identity is absent or ambiguous")
    segment = segments[0]
    if (
        segment.distance_meters is None
        or abs(segment.distance_meters - result.measured_distance_meters) > 0.01
        or segment.elapsed_seconds != result.elapsed_time_seconds
        or segment.start_time_utc != result.segment_start_time_utc
        or segment.start_time_local != result.segment_start_time_local
    ):
        raise PlanOperationError("Assessment result segment no longer matches its review")


def verify_owned_assessment_vdot_evidence(
    repo: RepositoryIO,
    evidence: OwnedBaselineAssessmentVDOTEvidence,
) -> BaselineAssessmentReview:
    """Prove a VDOT evidence payload is copied from one closed assessment review."""
    review = load_verified_closed_assessment_review(
        repo,
        review_sha256=evidence.assessment_review_sha256,
    )
    if review.result != evidence.result:
        raise PlanOperationError("VDOT assessment evidence differs from its immutable review")
    return review
