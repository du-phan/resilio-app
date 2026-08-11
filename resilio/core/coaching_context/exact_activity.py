"""Build bounded coaching evidence for one exact completed activity."""

from __future__ import annotations

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.coaching_context.recovery import (
    build_recovery_context,
    latest_wellness,
    training_state,
)
from resilio.core.repository import RepositoryIO
from resilio.core.training_state_repository import load_wellness
from resilio.core.workout_fulfillment.evidence import (
    assert_fulfillment_is_usable,
)
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.integrations.intervals_icu.dto import HeartRateCurveDTO
from resilio.schemas.activity import ActivityStatus
from resilio.schemas.activity_evidence import (
    ExactActivityCoachingEvidence,
    HeartRateCurvePoint,
)


def build_exact_activity_coaching_evidence(
    repo: RepositoryIO,
    *,
    local_activity_id: str,
    provider_heart_rate_curve: HeartRateCurveDTO | None = None,
    provider_heart_rate_curve_requested: bool = False,
) -> ExactActivityCoachingEvidence:
    """Build one exact, read-only activity context from canonical state."""
    activity = ActivityArchive(repo.resolve_path("data/activities")).load(local_activity_id)
    if activity is None or activity.status != ActivityStatus.ACTIVE:
        raise ValueError(f"Active activity {local_activity_id!r} was not found")
    external_activity_id = activity.origin.intervals_icu_activity_id
    if provider_heart_rate_curve is not None and (
        external_activity_id is None or provider_heart_rate_curve.id != external_activity_id
    ):
        raise ValueError("Provider HR curve does not belong to the exact activity")
    wellness = load_wellness(repo)
    latest = latest_wellness(wellness, activity.occurrence.local_date)
    curve_points = (
        [
            HeartRateCurvePoint(
                duration_seconds=duration_seconds,
                heart_rate_beats_per_minute=heart_rate_beats_per_minute,
            )
            for duration_seconds, heart_rate_beats_per_minute in zip(
                provider_heart_rate_curve.secs,
                provider_heart_rate_curve.values,
                strict=True,
            )
        ]
        if provider_heart_rate_curve is not None
        else []
    )
    fulfillment_manifest = load_fulfillment_manifest(repo)
    fulfillment = fulfillment_manifest.fulfillments.get(local_activity_id)
    if fulfillment is not None:
        assert_fulfillment_is_usable(fulfillment, activity, fulfillment_manifest)
    return ExactActivityCoachingEvidence(
        activity=activity,
        performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        workout_fulfillment=fulfillment,
        recovery_context=build_recovery_context(
            wellness,
            as_of_date=activity.occurrence.local_date,
        ),
        training_state=training_state(latest),
        provider_heart_rate_curve_status=(
            "available"
            if provider_heart_rate_curve is not None
            else "unavailable"
            if provider_heart_rate_curve_requested
            else "not_requested"
        ),
        provider_heart_rate_curve=curve_points,
    )
