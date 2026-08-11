from datetime import date, datetime, timezone

import pytest

from resilio.core.activity_sync.athlete_fulfillment_decisions import (
    athlete_provider_pair_conflict,
)
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.activity_sync.provider_fulfillment import (
    reconcile_provider_fulfillment,
)
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.schemas.activity import SportType
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
    WorkoutFulfillmentRevocation,
)
from tests.factories import make_activity
from tests.unit.test_activity_sync import _publication


def _publication_and_authority():
    publication = _publication()
    prescription = RunningWorkoutPrescription.model_validate(
        {
            "id": publication.workout_identity.local_workout_id,
            "date": publication.occurrence_date,
            "workout_type": "easy",
            "planned_duration_seconds": 2_400,
            "planned_distance_meters": 5_000,
            "planned_low_intensity_duration_seconds": 2_400,
            "planned_moderate_intensity_duration_seconds": 0,
            "planned_high_intensity_duration_seconds": 0,
            "target_rpe_1_to_10": 3,
            "purpose": "Complete one conversational five-kilometre run.",
            "structured_workout": {
                "sport": "run",
                "steps": [
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 2_400},
                        "intensity": "active",
                    }
                ],
            },
        }
    )
    authority = AuthoritativeWorkout(
        identity=publication.workout_identity,
        prescription=prescription,
        applied_week_approval_id=publication.applied_week_approval_id,
        applied_running_workouts_sha256=(publication.applied_running_workouts_sha256),
        schedule_timezone=publication.schedule_timezone,
    )
    return (
        publication.model_copy(
            update={
                "workout_prescription_sha256": canonical_data_sha256(prescription),
            }
        ),
        authority,
    )


def test_provider_pair_refreshes_changed_activity_evidence_idempotently() -> None:
    publication, authority = _publication_and_authority()
    activity = make_activity(
        id="act_paired",
        date=date(2026, 7, 28),
        start_time=datetime(2026, 7, 28, 6, tzinfo=timezone.utc),
        distance_meters=5_000,
    )
    first = reconcile_provider_fulfillment(
        activity=activity,
        paired_event_id=publication.event_id,
        publications_by_event_id={publication.event_id: publication},
        authoritative_workout=authority,
        existing_fulfillment=None,
        observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    )
    assert first.fulfillment is not None
    changed_activity = activity.model_copy(update={"distance_meters": 5_010})

    refreshed = reconcile_provider_fulfillment(
        activity=changed_activity,
        paired_event_id=publication.event_id,
        publications_by_event_id={publication.event_id: publication},
        authoritative_workout=authority,
        existing_fulfillment=first.fulfillment,
        observed_at_utc=datetime(2026, 7, 29, 9, tzinfo=timezone.utc),
    )

    assert refreshed.conflict is None
    assert refreshed.fulfillment is not None
    assert (
        refreshed.fulfillment.activity_performance_evidence_sha256
        != first.fulfillment.activity_performance_evidence_sha256
    )
    unchanged = reconcile_provider_fulfillment(
        activity=changed_activity,
        paired_event_id=publication.event_id,
        publications_by_event_id={publication.event_id: publication},
        authoritative_workout=authority,
        existing_fulfillment=refreshed.fulfillment,
        observed_at_utc=datetime(2026, 7, 30, 9, tzinfo=timezone.utc),
    )
    assert unchanged.fulfillment is None
    assert unchanged.conflict is None


def test_exact_provider_pair_may_cross_a_training_week_boundary() -> None:
    publication, authority = _publication_and_authority()
    activity = make_activity(
        id="act_late_pair",
        date=date(2026, 8, 3),
        start_time=datetime(2026, 8, 3, 6, tzinfo=timezone.utc),
    )

    reconciliation = reconcile_provider_fulfillment(
        activity=activity,
        paired_event_id=publication.event_id,
        publications_by_event_id={publication.event_id: publication},
        authoritative_workout=authority,
        existing_fulfillment=None,
        observed_at_utc=datetime(2026, 8, 3, 9, tzinfo=timezone.utc),
    )

    assert reconciliation.fulfillment is not None
    assert reconciliation.fulfillment.schedule_offset_days == 6
    assert reconciliation.fulfillment.fulfillment_basis == "provider_paired"


@pytest.mark.parametrize(
    "sport",
    [
        SportType.RUN,
        SportType.TRAIL_RUN,
        SportType.TREADMILL_RUN,
        SportType.TRACK_RUN,
    ],
)
def test_exact_provider_pair_accepts_every_running_sport_variant(
    sport: SportType,
) -> None:
    publication, authority = _publication_and_authority()
    activity = make_activity(id=f"act_{sport.value}", sport=sport)

    reconciliation = reconcile_provider_fulfillment(
        activity=activity,
        paired_event_id=publication.event_id,
        publications_by_event_id={publication.event_id: publication},
        authoritative_workout=authority,
        existing_fulfillment=None,
        observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    )

    assert reconciliation.conflict is None
    assert reconciliation.fulfillment is not None


def test_unpaired_activity_correction_preserves_athlete_authority_with_audit() -> None:
    publication, _ = _publication_and_authority()
    activity = make_activity(
        id="act_athlete_confirmed",
        date=date(2026, 7, 28),
        start_time=datetime(2026, 7, 28, 6, tzinfo=timezone.utc),
        distance_meters=5_000,
    )
    existing = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=publication.workout_identity,
        applied_week_approval_id=publication.applied_week_approval_id,
        applied_running_workouts_sha256=publication.applied_running_workouts_sha256,
        workout_prescription_sha256=publication.workout_prescription_sha256,
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=publication.schedule_timezone,
        scheduled_local_date=publication.occurrence_date,
        execution_local_date=publication.occurrence_date,
        schedule_offset_days=0,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale=(
                "The athlete explicitly confirmed the exact approved workout intent."
            ),
            confirmed_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
    )
    changed_activity = activity.model_copy(update={"distance_meters": 5_010})

    refreshed = reconcile_provider_fulfillment(
        activity=changed_activity,
        paired_event_id=None,
        publications_by_event_id={},
        authoritative_workout=None,
        existing_fulfillment=existing,
        observed_at_utc=datetime(2026, 7, 29, 9, tzinfo=timezone.utc),
    )

    assert refreshed.conflict is None
    assert refreshed.fulfillment is not None
    assert refreshed.fulfillment.athlete_confirmation == existing.athlete_confirmation
    assert len(refreshed.fulfillment.activity_evidence_revisions) == 1
    assert (
        refreshed.fulfillment.activity_evidence_revisions[
            0
        ].previous_activity_performance_evidence_sha256
        == existing.activity_performance_evidence_sha256
    )


def test_unpaired_date_correction_cannot_expand_athlete_authority_across_weeks() -> None:
    publication, _ = _publication_and_authority()
    activity = make_activity(
        id="act_corrected_date",
        date=publication.occurrence_date,
        start_time=datetime(2026, 7, 28, 6, tzinfo=timezone.utc),
    )
    existing = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=publication.workout_identity,
        applied_week_approval_id=publication.applied_week_approval_id,
        applied_running_workouts_sha256=publication.applied_running_workouts_sha256,
        workout_prescription_sha256=publication.workout_prescription_sha256,
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=publication.schedule_timezone,
        scheduled_local_date=publication.occurrence_date,
        execution_local_date=publication.occurrence_date,
        schedule_offset_days=0,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale=(
                "The athlete explicitly confirmed the exact approved workout intent."
            ),
            confirmed_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
    )
    corrected_activity = activity.model_copy(
        update={
            "occurrence": activity.occurrence.model_copy(
                update={
                    "local_date": date(2026, 8, 3),
                    "start_time_utc": datetime(2026, 8, 3, 6, tzinfo=timezone.utc),
                }
            )
        }
    )

    refreshed = reconcile_provider_fulfillment(
        activity=corrected_activity,
        paired_event_id=None,
        publications_by_event_id={},
        authoritative_workout=None,
        existing_fulfillment=existing,
        observed_at_utc=datetime(2026, 8, 3, 9, tzinfo=timezone.utc),
    )

    assert refreshed.fulfillment is None
    assert refreshed.conflict == {
        "rule": "fulfilled_activity_training_week_changed",
        "local_activity_id": activity.local_activity_id,
        "local_workout_id": publication.workout_identity.local_workout_id,
    }


def test_provider_only_fulfillment_is_conflicted_when_pair_is_removed() -> None:
    publication, authority = _publication_and_authority()
    activity = make_activity(id="act_pair_removed", date=publication.occurrence_date)
    paired = reconcile_provider_fulfillment(
        activity=activity,
        paired_event_id=publication.event_id,
        publications_by_event_id={publication.event_id: publication},
        authoritative_workout=authority,
        existing_fulfillment=None,
        observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    ).fulfillment
    assert paired is not None

    reconciliation = reconcile_provider_fulfillment(
        activity=activity,
        paired_event_id=None,
        publications_by_event_id={},
        authoritative_workout=None,
        existing_fulfillment=paired,
        observed_at_utc=datetime(2026, 7, 29, 9, tzinfo=timezone.utc),
    )

    assert reconciliation.fulfillment is None
    assert reconciliation.conflict == {
        "rule": "paired_event_removed",
        "local_activity_id": activity.local_activity_id,
        "local_workout_id": publication.workout_identity.local_workout_id,
    }


def test_removed_provider_pair_falls_back_to_same_week_athlete_confirmation() -> None:
    publication, authority = _publication_and_authority()
    activity = make_activity(
        id="act_pair_removed_confirmed",
        date=publication.occurrence_date,
    )
    paired = reconcile_provider_fulfillment(
        activity=activity,
        paired_event_id=publication.event_id,
        publications_by_event_id={publication.event_id: publication},
        authoritative_workout=authority,
        existing_fulfillment=None,
        observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    ).fulfillment
    assert paired is not None
    confirmed = paired.model_copy(
        update={
            "athlete_confirmation": AthleteConfirmedFulfillmentEvidence(
                candidate_sha256="4" * 64,
                athlete_confirmation_reference="Athlete confirmed this exact association.",
                coaching_rationale=(
                    "The athlete independently confirmed the exact approved workout intent."
                ),
                confirmed_at_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc),
            )
        }
    )

    reconciliation = reconcile_provider_fulfillment(
        activity=activity,
        paired_event_id=None,
        publications_by_event_id={},
        authoritative_workout=None,
        existing_fulfillment=confirmed,
        observed_at_utc=datetime(2026, 7, 29, 9, tzinfo=timezone.utc),
    )

    assert reconciliation.conflict is None
    assert reconciliation.fulfillment is not None
    assert reconciliation.fulfillment.provider_pair is None
    assert reconciliation.fulfillment.fulfillment_basis == "athlete_confirmed"
    assert len(reconciliation.fulfillment.withdrawn_provider_pairs) == 1
    assert (
        reconciliation.fulfillment.withdrawn_provider_pairs[0].provider_pair.event_id
        == publication.event_id
    )


def test_revoked_provider_pair_is_suppressed_only_for_the_exact_evidence() -> None:
    publication, authority = _publication_and_authority()
    activity = make_activity(id="act_revoked_pair", date=publication.occurrence_date)
    fulfillment = reconcile_provider_fulfillment(
        activity=activity,
        paired_event_id=publication.event_id,
        publications_by_event_id={publication.event_id: publication},
        authoritative_workout=authority,
        existing_fulfillment=None,
        observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    ).fulfillment
    assert fulfillment is not None
    revocation = WorkoutFulfillmentRevocation(
        revocation_id="fulfillment_revocation_1111111111111111",
        fulfillment=fulfillment,
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew this exact association.",
        coaching_rationale=(
            "The athlete clarified that these exact activity facts did not fulfill it."
        ),
        revoked_at_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc),
    )

    assert (
        athlete_provider_pair_conflict(
            activity=activity,
            publication=publication,
            authoritative_workout=authority,
            manifest=WorkoutFulfillmentManifest(revoked_fulfillments=[revocation]),
        )
        is not None
    )
    assert (
        athlete_provider_pair_conflict(
            activity=activity.model_copy(update={"distance_meters": 5_010}),
            publication=publication,
            authoritative_workout=authority,
            manifest=WorkoutFulfillmentManifest(revoked_fulfillments=[revocation]),
        )
        is None
    )


def test_unpaired_sport_reclassification_is_quarantined_before_fulfillment_update() -> None:
    publication, _ = _publication_and_authority()
    activity = make_activity(
        id="act_reclassified",
        date=publication.occurrence_date,
    )
    existing = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=publication.workout_identity,
        applied_week_approval_id=publication.applied_week_approval_id,
        applied_running_workouts_sha256=publication.applied_running_workouts_sha256,
        workout_prescription_sha256=publication.workout_prescription_sha256,
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=publication.schedule_timezone,
        scheduled_local_date=publication.occurrence_date,
        execution_local_date=publication.occurrence_date,
        schedule_offset_days=0,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale=(
                "The athlete explicitly confirmed the exact approved workout intent."
            ),
            confirmed_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
    )
    reclassified_activity = activity.model_copy(update={"sport": "ride"})

    result = reconcile_provider_fulfillment(
        activity=reclassified_activity,
        paired_event_id=None,
        publications_by_event_id={},
        authoritative_workout=None,
        existing_fulfillment=existing,
        observed_at_utc=datetime(2026, 7, 29, 8, tzinfo=timezone.utc),
    )

    assert result.fulfillment is None
    assert result.conflict == {
        "rule": "fulfilled_activity_sport_changed",
        "local_activity_id": activity.local_activity_id,
    }


def test_provider_pair_enriches_fulfillment_from_retained_week_revision() -> None:
    publication, authority = _publication_and_authority()
    current_publication = publication.model_copy(
        update={
            "applied_week_approval_id": "week_approval_1111111111111111",
            "applied_running_workouts_sha256": "2" * 64,
        }
    )
    activity = make_activity(
        id="act_retained_revision",
        date=current_publication.occurrence_date,
        start_time=datetime(2026, 7, 28, 6, tzinfo=timezone.utc),
    )
    existing = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=current_publication.workout_identity,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        workout_prescription_sha256=(current_publication.workout_prescription_sha256),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=current_publication.schedule_timezone,
        scheduled_local_date=current_publication.occurrence_date,
        execution_local_date=current_publication.occurrence_date,
        schedule_offset_days=0,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale=(
                "The athlete explicitly confirmed the exact approved workout intent."
            ),
            confirmed_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
    )

    reconciliation = reconcile_provider_fulfillment(
        activity=activity,
        paired_event_id=current_publication.event_id,
        publications_by_event_id={current_publication.event_id: current_publication},
        authoritative_workout=authority,
        existing_fulfillment=existing,
        observed_at_utc=datetime(2026, 7, 29, 8, tzinfo=timezone.utc),
    )

    assert reconciliation.conflict is None
    assert reconciliation.fulfillment is not None
    assert reconciliation.fulfillment.provider_pair is not None
    assert reconciliation.fulfillment.applied_week_approval_id == existing.applied_week_approval_id
