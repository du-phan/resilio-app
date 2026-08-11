from datetime import date, datetime, timezone

import pytest

from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    FulfillmentActivityEvidenceRevision,
    HistoricalLegacyWorkoutFulfillment,
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)


def _identity(local_workout_id: str = "w_easy") -> PlanWorkoutIdentity:
    return PlanWorkoutIdentity(
        plan_id="plan_example",
        plan_revision_id="plan_revision_0123456789abcdef",
        week_number=1,
        local_workout_id=local_workout_id,
    )


def _record(
    *,
    local_activity_id: str = "act_example",
    local_workout_id: str = "w_easy",
) -> WorkoutFulfillmentRecord:
    return WorkoutFulfillmentRecord(
        local_activity_id=local_activity_id,
        workout_identity=_identity(local_workout_id),
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        workout_prescription_sha256="2" * 64,
        activity_performance_evidence_sha256="3" * 64,
        schedule_timezone="Europe/Paris",
        scheduled_local_date=date(2026, 8, 11),
        execution_local_date=date(2026, 8, 10),
        schedule_offset_days=-1,
        provider_pair=None,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the exact early run.",
            coaching_rationale="The athlete identified this activity as the approved easy run.",
            confirmed_at_utc=datetime(2026, 8, 10, 13, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 13, tzinfo=timezone.utc),
    )


def test_fulfillment_requires_exact_date_offset() -> None:
    payload = _record().model_dump(mode="python")
    payload["schedule_offset_days"] = 0
    with pytest.raises(ValueError, match="schedule_offset_days"):
        WorkoutFulfillmentRecord.model_validate(payload)


def test_fulfillment_requires_provider_or_athlete_evidence() -> None:
    with pytest.raises(ValueError, match="at least one evidence source"):
        WorkoutFulfillmentRecord.model_validate(
            _record().model_dump(
                mode="python",
                exclude={"provider_pair", "athlete_confirmation"},
            )
        )


def test_provider_pair_can_enrich_an_athlete_confirmed_record() -> None:
    record = _record().model_copy(
        update={
            "provider_pair": ProviderPairedFulfillmentEvidence(
                event_id=42,
                observed_at_utc=datetime(2026, 8, 11, 8, tzinfo=timezone.utc),
            )
        }
    )

    assert record.fulfillment_basis == "provider_paired_and_athlete_confirmed"


def test_activity_evidence_revision_chain_must_end_at_current_evidence() -> None:
    payload = _record().model_dump(mode="python")
    payload["activity_performance_evidence_sha256"] = "6" * 64
    payload["activity_evidence_revisions"] = [
        FulfillmentActivityEvidenceRevision(
            previous_activity_performance_evidence_sha256="3" * 64,
            replacement_activity_performance_evidence_sha256="5" * 64,
            previous_execution_local_date=date(2026, 8, 10),
            replacement_execution_local_date=date(2026, 8, 10),
            observed_at_utc=datetime(2026, 8, 10, 14, tzinfo=timezone.utc),
        )
    ]

    with pytest.raises(ValueError, match="end at current activity evidence"):
        WorkoutFulfillmentRecord.model_validate(payload)


def test_activity_evidence_revision_chain_rejects_noop_and_out_of_order_entries() -> None:
    base_revision = {
        "previous_activity_performance_evidence_sha256": "3" * 64,
        "replacement_activity_performance_evidence_sha256": "5" * 64,
        "previous_execution_local_date": date(2026, 8, 10),
        "replacement_execution_local_date": date(2026, 8, 10),
        "observed_at_utc": datetime(2026, 8, 10, 14, tzinfo=timezone.utc),
    }
    payload = _record().model_dump(mode="python")
    payload["activity_performance_evidence_sha256"] = "5" * 64
    payload["activity_evidence_revisions"] = [
        {**base_revision, "replacement_activity_performance_evidence_sha256": "3" * 64}
    ]
    with pytest.raises(ValueError, match="must change evidence or execution date"):
        WorkoutFulfillmentRecord.model_validate(payload)

    payload["activity_performance_evidence_sha256"] = "6" * 64
    payload["activity_evidence_revisions"] = [
        base_revision,
        {
            **base_revision,
            "previous_activity_performance_evidence_sha256": "4" * 64,
            "replacement_activity_performance_evidence_sha256": "6" * 64,
            "observed_at_utc": datetime(2026, 8, 10, 15, tzinfo=timezone.utc),
        },
    ]
    with pytest.raises(ValueError, match="continuous"):
        WorkoutFulfillmentRecord.model_validate(payload)


def test_activity_revisions_cannot_expand_athlete_confirmation_to_another_week() -> None:
    payload = _record().model_dump(mode="python")
    payload["activity_performance_evidence_sha256"] = "5" * 64
    payload["execution_local_date"] = date(2026, 8, 17)
    payload["schedule_offset_days"] = 6
    payload["activity_evidence_revisions"] = [
        FulfillmentActivityEvidenceRevision(
            previous_activity_performance_evidence_sha256="3" * 64,
            replacement_activity_performance_evidence_sha256="5" * 64,
            previous_execution_local_date=date(2026, 8, 10),
            replacement_execution_local_date=date(2026, 8, 17),
            observed_at_utc=datetime(2026, 8, 17, 14, tzinfo=timezone.utc),
        )
    ]

    with pytest.raises(ValueError, match="one training week"):
        WorkoutFulfillmentRecord.model_validate(payload)


def test_manifest_rejects_activity_or_workout_reuse() -> None:
    first = _record()
    reused_workout = _record(local_activity_id="act_other")
    reused_activity = _record(local_workout_id="w_other")

    with pytest.raises(ValueError, match="workout cannot fulfill multiple activities"):
        WorkoutFulfillmentManifest(
            fulfillments={
                first.local_activity_id: first,
                reused_workout.local_activity_id: reused_workout,
            }
        )
    with pytest.raises(ValueError, match="manifest key must match"):
        WorkoutFulfillmentManifest(
            fulfillments={
                first.local_activity_id: first,
                "wrong_key": reused_activity,
            }
        )


def test_manifest_rejects_workout_reuse_across_active_and_historical_records() -> None:
    active = _record()
    historical = HistoricalLegacyWorkoutFulfillment(
        local_activity_id="act_historical",
        workout_identity=active.workout_identity,
        activity_performance_evidence_sha256="3" * 64,
        scheduled_local_date=date(2026, 8, 10),
        execution_local_date=date(2026, 8, 10),
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            event_id=42,
            observed_at_utc=datetime(2026, 8, 10, 14, tzinfo=timezone.utc),
        ),
        matched_at_utc=datetime(2026, 8, 10, 14, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="workout cannot fulfill multiple activities"):
        WorkoutFulfillmentManifest(
            fulfillments={active.local_activity_id: active},
            historical_legacy_fulfillments={historical.local_activity_id: historical},
        )
