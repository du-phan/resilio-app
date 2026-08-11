"""Pure Intervals.icu pairing to provider-neutral fulfillment policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.workout_fulfillment.evidence import (
    assert_fulfillment_authority_is_current,
)
from resilio.schemas.activity import CanonicalActivity, is_running_sport
from resilio.schemas.publication import PublishedWorkout
from resilio.schemas.workout_fulfillment import (
    FulfillmentActivityEvidenceRevision,
    ProviderPairedFulfillmentEvidence,
    ProviderPairProvenance,
    WithdrawnProviderPairEvidence,
    WorkoutFulfillmentRecord,
)


@dataclass(frozen=True)
class ProviderFulfillmentReconciliation:
    fulfillment: WorkoutFulfillmentRecord | None = None
    conflict: dict[str, str] | None = None


def _execution_local_date(
    activity: CanonicalActivity,
    *,
    schedule_timezone: str,
) -> date | None:
    if activity.occurrence.start_time_utc is not None:
        return activity.occurrence.start_time_utc.astimezone(ZoneInfo(schedule_timezone)).date()
    if activity.occurrence.timezone == schedule_timezone:
        return activity.occurrence.local_date
    return None


def _reconcile_unpaired_existing(
    *,
    activity: CanonicalActivity,
    existing_fulfillment: WorkoutFulfillmentRecord | None,
    performance_sha256: str,
    observed_at_utc: datetime,
) -> ProviderFulfillmentReconciliation:
    if existing_fulfillment is None:
        return ProviderFulfillmentReconciliation()
    if not is_running_sport(activity.sport):
        return _provider_pair_conflict(
            "fulfilled_activity_sport_changed",
            activity=activity,
        )
    execution_local_date = _execution_local_date(
        activity,
        schedule_timezone=existing_fulfillment.schedule_timezone,
    )
    if execution_local_date is None:
        return ProviderFulfillmentReconciliation(
            conflict={
                "rule": "fulfilled_activity_execution_date_unavailable",
                "local_activity_id": activity.local_activity_id,
                "local_workout_id": (existing_fulfillment.workout_identity.local_workout_id),
            }
        )
    local_workout_id = existing_fulfillment.workout_identity.local_workout_id
    scheduled_week_start = (
        existing_fulfillment.scheduled_local_date
        - date.resolution * existing_fulfillment.scheduled_local_date.weekday()
    )
    execution_week_start = execution_local_date - date.resolution * execution_local_date.weekday()
    if existing_fulfillment.provider_pair is not None:
        if (
            existing_fulfillment.athlete_confirmation is None
            or scheduled_week_start != execution_week_start
        ):
            return ProviderFulfillmentReconciliation(
                conflict={
                    "rule": "paired_event_removed",
                    "local_activity_id": activity.local_activity_id,
                    "local_workout_id": local_workout_id,
                }
            )
        withdrawal = WithdrawnProviderPairEvidence(
            provider_pair=existing_fulfillment.provider_pair,
            reason="provider_pair_removed",
            withdrawn_at_utc=observed_at_utc,
        )
        return _updated_unpaired_fulfillment(
            existing_fulfillment=existing_fulfillment,
            performance_sha256=performance_sha256,
            execution_local_date=execution_local_date,
            observed_at_utc=observed_at_utc,
            provider_pair_withdrawal=withdrawal,
        )
    if scheduled_week_start != execution_week_start:
        return ProviderFulfillmentReconciliation(
            conflict={
                "rule": "fulfilled_activity_training_week_changed",
                "local_activity_id": activity.local_activity_id,
                "local_workout_id": local_workout_id,
            }
        )
    if (
        existing_fulfillment.activity_performance_evidence_sha256 == performance_sha256
        and existing_fulfillment.execution_local_date == execution_local_date
    ):
        return ProviderFulfillmentReconciliation()
    return _updated_unpaired_fulfillment(
        existing_fulfillment=existing_fulfillment,
        performance_sha256=performance_sha256,
        execution_local_date=execution_local_date,
        observed_at_utc=observed_at_utc,
    )


def _updated_unpaired_fulfillment(
    *,
    existing_fulfillment: WorkoutFulfillmentRecord,
    performance_sha256: str,
    execution_local_date: date,
    observed_at_utc: datetime,
    provider_pair_withdrawal: WithdrawnProviderPairEvidence | None = None,
) -> ProviderFulfillmentReconciliation:
    revisions = list(existing_fulfillment.activity_evidence_revisions)
    if (
        existing_fulfillment.activity_performance_evidence_sha256 != performance_sha256
        or existing_fulfillment.execution_local_date != execution_local_date
    ):
        revisions.append(
            FulfillmentActivityEvidenceRevision(
                previous_activity_performance_evidence_sha256=(
                    existing_fulfillment.activity_performance_evidence_sha256
                ),
                replacement_activity_performance_evidence_sha256=performance_sha256,
                previous_execution_local_date=(existing_fulfillment.execution_local_date),
                replacement_execution_local_date=execution_local_date,
                observed_at_utc=observed_at_utc,
            )
        )
    return ProviderFulfillmentReconciliation(
        fulfillment=WorkoutFulfillmentRecord.model_validate(
            {
                **existing_fulfillment.model_dump(mode="python"),
                "activity_performance_evidence_sha256": performance_sha256,
                "execution_local_date": execution_local_date,
                "schedule_offset_days": (
                    execution_local_date - existing_fulfillment.scheduled_local_date
                ).days,
                "provider_pair": None,
                "withdrawn_provider_pairs": [
                    *existing_fulfillment.withdrawn_provider_pairs,
                    *([provider_pair_withdrawal] if provider_pair_withdrawal else []),
                ],
                "activity_evidence_revisions": revisions,
            }
        )
    )


def _provider_pair_conflict(
    rule: str,
    *,
    activity: CanonicalActivity,
    publication: PublishedWorkout | None = None,
) -> ProviderFulfillmentReconciliation:
    conflict = {
        "rule": rule,
        "local_activity_id": activity.local_activity_id,
    }
    if publication is not None:
        conflict["local_workout_id"] = publication.workout_identity.local_workout_id
    return ProviderFulfillmentReconciliation(conflict=conflict)


def _reconcile_existing_provider_pair(
    *,
    activity: CanonicalActivity,
    publication: PublishedWorkout,
    authoritative_workout: AuthoritativeWorkout,
    existing_fulfillment: WorkoutFulfillmentRecord,
    performance_sha256: str,
    execution_local_date: date,
    provider_pair: ProviderPairedFulfillmentEvidence,
    observed_at_utc: datetime,
) -> ProviderFulfillmentReconciliation:
    try:
        assert_fulfillment_authority_is_current(
            existing_fulfillment,
            authoritative_workout,
        )
    except ValueError:
        return _provider_pair_conflict(
            "paired_event_existing_fulfillment_conflict",
            activity=activity,
            publication=publication,
        )
    if existing_fulfillment.provider_pair is not None:
        if existing_fulfillment.provider_pair.event_id != publication.event_id:
            return _provider_pair_conflict(
                "paired_event_existing_provider_pair_conflict",
                activity=activity,
                publication=publication,
            )
        if (
            existing_fulfillment.activity_performance_evidence_sha256 == performance_sha256
            and existing_fulfillment.execution_local_date == execution_local_date
        ):
            return ProviderFulfillmentReconciliation()
        provider_pair = existing_fulfillment.provider_pair
    revisions = list(existing_fulfillment.activity_evidence_revisions)
    if (
        existing_fulfillment.activity_performance_evidence_sha256 != performance_sha256
        or existing_fulfillment.execution_local_date != execution_local_date
    ):
        revisions.append(
            FulfillmentActivityEvidenceRevision(
                previous_activity_performance_evidence_sha256=(
                    existing_fulfillment.activity_performance_evidence_sha256
                ),
                replacement_activity_performance_evidence_sha256=performance_sha256,
                previous_execution_local_date=(existing_fulfillment.execution_local_date),
                replacement_execution_local_date=execution_local_date,
                observed_at_utc=observed_at_utc,
            )
        )
    return ProviderFulfillmentReconciliation(
        fulfillment=WorkoutFulfillmentRecord.model_validate(
            {
                **existing_fulfillment.model_dump(mode="python"),
                "activity_performance_evidence_sha256": performance_sha256,
                "execution_local_date": execution_local_date,
                "schedule_offset_days": (execution_local_date - publication.occurrence_date).days,
                "provider_pair": provider_pair,
                "activity_evidence_revisions": revisions,
            }
        )
    )


def reconcile_provider_fulfillment(
    *,
    activity: CanonicalActivity,
    paired_event_id: Optional[int],
    publications_by_event_id: dict[int, PublishedWorkout],
    authoritative_workout: AuthoritativeWorkout | None,
    existing_fulfillment: WorkoutFulfillmentRecord | None,
    observed_at_utc: datetime,
    provider_pair_provenance: ProviderPairProvenance = "provider_observed",
) -> ProviderFulfillmentReconciliation:
    """Accept only an exact pairing to an ownership-proven published event."""
    publication = publications_by_event_id.get(paired_event_id) if paired_event_id else None
    performance_sha256 = activity_performance_evidence_sha256(activity)
    if paired_event_id is None:
        return _reconcile_unpaired_existing(
            activity=activity,
            existing_fulfillment=existing_fulfillment,
            performance_sha256=performance_sha256,
            observed_at_utc=observed_at_utc,
        )
    if publication is None:
        return _provider_pair_conflict(
            "paired_event_is_not_owned",
            activity=activity,
        )
    if publication.sport != "run" or not is_running_sport(activity.sport):
        return _provider_pair_conflict(
            "paired_event_sport_mismatch",
            activity=activity,
            publication=publication,
        )
    if authoritative_workout is None:
        return _provider_pair_conflict(
            "paired_event_applied_authority_unavailable",
            activity=activity,
            publication=publication,
        )
    authority_matches_publication = (
        authoritative_workout.identity == publication.workout_identity
        and canonical_data_sha256(authoritative_workout.prescription)
        == publication.workout_prescription_sha256
        and authoritative_workout.schedule_timezone == publication.schedule_timezone
        and authoritative_workout.prescription.date == publication.occurrence_date
    )
    if not authority_matches_publication:
        return _provider_pair_conflict(
            "paired_event_historical_authority_conflict",
            activity=activity,
            publication=publication,
        )
    execution_local_date = _execution_local_date(
        activity,
        schedule_timezone=publication.schedule_timezone,
    )
    if execution_local_date is None:
        return _provider_pair_conflict(
            "paired_event_execution_date_unavailable",
            activity=activity,
            publication=publication,
        )
    provider_pair = ProviderPairedFulfillmentEvidence(
        event_id=publication.event_id,
        provenance=provider_pair_provenance,
        observed_at_utc=observed_at_utc,
    )
    if existing_fulfillment is not None:
        return _reconcile_existing_provider_pair(
            activity=activity,
            publication=publication,
            authoritative_workout=authoritative_workout,
            existing_fulfillment=existing_fulfillment,
            performance_sha256=performance_sha256,
            execution_local_date=execution_local_date,
            provider_pair=provider_pair,
            observed_at_utc=observed_at_utc,
        )
    return ProviderFulfillmentReconciliation(
        fulfillment=WorkoutFulfillmentRecord(
            local_activity_id=activity.local_activity_id,
            workout_identity=publication.workout_identity,
            applied_week_approval_id=authoritative_workout.applied_week_approval_id,
            applied_running_workouts_sha256=(authoritative_workout.applied_running_workouts_sha256),
            workout_prescription_sha256=canonical_data_sha256(authoritative_workout.prescription),
            activity_performance_evidence_sha256=performance_sha256,
            schedule_timezone=authoritative_workout.schedule_timezone,
            scheduled_local_date=authoritative_workout.prescription.date,
            execution_local_date=execution_local_date,
            schedule_offset_days=(
                execution_local_date - authoritative_workout.prescription.date
            ).days,
            provider_pair=provider_pair,
            recorded_at_utc=observed_at_utc,
        )
    )
