"""Idempotence policy for migrated historical provider pairs."""

from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.publication import HistoricalLegacyWorkoutPublication
from resilio.schemas.workout_fulfillment import HistoricalLegacyWorkoutFulfillment


def historical_provider_pair_decision(
    *,
    paired_event_id: int | None,
    activity: CanonicalActivity,
    publications_by_event_id: dict[int, HistoricalLegacyWorkoutPublication],
    fulfillments_by_activity_id: dict[str, HistoricalLegacyWorkoutFulfillment],
) -> tuple[bool, dict[str, str] | None]:
    """Recognize an exact migrated pair or report contradictory historical ownership."""
    fulfillment = fulfillments_by_activity_id.get(activity.local_activity_id)
    publication = (
        publications_by_event_id.get(paired_event_id) if paired_event_id is not None else None
    )
    if fulfillment is not None:
        exact_pair = (
            publication is not None
            and fulfillment.provider_pair.event_id == publication.event_id
            and fulfillment.workout_identity == publication.workout_identity
        )
        if exact_pair:
            return True, None
        return True, {
            "rule": "paired_event_historical_ownership_conflict",
            "local_activity_id": activity.local_activity_id,
            "local_workout_id": fulfillment.workout_identity.local_workout_id,
        }
    if publication is None:
        return False, None
    return True, {
        "rule": "paired_event_historical_ownership_conflict",
        "local_activity_id": activity.local_activity_id,
        "local_workout_id": publication.workout_identity.local_workout_id,
    }
