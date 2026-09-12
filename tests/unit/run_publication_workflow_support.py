"""Shared fixtures for run-publication workflow tests."""

from datetime import date, datetime, timedelta, timezone

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.adherence_evidence import (
    AuthoritativeWorkout,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication import week_service as week_service_module
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.naming import provider_workout_names
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthorities,
    RetainedPublicationAuthority,
)
from resilio.core.workout_publication.week_service import RunWeekSynchronizationService
from resilio.integrations.intervals_icu.activity_fingerprint import (
    performance_evidence_fingerprint,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.schemas.activity import ActivityOrigin, ActivityOriginKind
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentRecord,
)
from tests.factories import make_activity


def _pace_targeted_run(
    workout_id: str,
    occurrence: date,
) -> RunningWorkoutPrescription:
    payload = _targetless_run(workout_id, occurrence).model_dump(mode="json")
    payload["structured_workout"] = {
        "sport": "run",
        "steps": [
            {
                "kind": "steady",
                "duration": {"unit": "seconds", "value": 600},
                "target": {
                    "mode": "pace",
                    "unit": "seconds_per_kilometer",
                    "minimum": 330,
                    "maximum": 360,
                },
                "intensity": "active",
            }
        ],
    }
    return RunningWorkoutPrescription.model_validate(payload)


def _after_latest_publication_verification(
    repo: RepositoryIO,
    local_workout_id: str,
) -> datetime:
    return load_manifest(repo).workouts[local_workout_id].verified_at_utc + timedelta(
        microseconds=1
    )


def _provider_paired_fulfillment(
    workout: AuthoritativeWorkout,
    *,
    local_activity_id: str,
    execution_date: date,
    activity_performance_sha256: str,
    event_id: int,
) -> WorkoutFulfillmentRecord:
    return WorkoutFulfillmentRecord(
        local_activity_id=local_activity_id,
        workout_identity=workout.identity,
        applied_week_approval_id=workout.applied_week_approval_id,
        applied_running_workouts_sha256=workout.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(workout.prescription),
        activity_performance_evidence_sha256=activity_performance_sha256,
        schedule_timezone=workout.schedule_timezone,
        scheduled_local_date=workout.prescription.date,
        execution_local_date=execution_date,
        schedule_offset_days=(execution_date - workout.prescription.date).days,
        provider_pair=ProviderPairedFulfillmentEvidence(
            event_id=event_id,
            provenance="provider_observed",
            observed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )


def _retain_test_authorities(
    monkeypatch,
    *workouts: AuthoritativeWorkout,
) -> None:
    monkeypatch.setattr(
        week_service_module,
        "retained_publication_authorities",
        lambda _repo, _current_workouts: {
            workout.identity.local_workout_id: RetainedPublicationAuthorities(
                published=RetainedPublicationAuthority(
                    workout=workout,
                    provider_name=provider_workout_names([workout.prescription])[
                        workout.identity.local_workout_id
                    ],
                )
            )
            for workout in workouts
        },
    )


def _targetless_run(workout_id: str, occurrence: date) -> RunningWorkoutPrescription:
    return RunningWorkoutPrescription.model_validate(
        {
            "id": workout_id,
            "date": occurrence,
            "sport": "run",
            "workout_type": "easy",
            "planned_duration_seconds": 600,
            "planned_distance_meters": 1_500,
            "planned_low_intensity_duration_seconds": 600,
            "planned_moderate_intensity_duration_seconds": 0,
            "planned_high_intensity_duration_seconds": 0,
            "target_rpe_1_to_10": 3,
            "purpose": "Easy conversational running.",
            "structured_workout": {
                "sport": "run",
                "steps": [
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 600},
                        "intensity": "active",
                        "cue": "Keep the effort conversational.",
                    }
                ],
            },
        }
    )


def _save_fulfillment_activity(
    repo: RepositoryIO,
    *,
    local_activity_id: str,
    execution_date: date,
    source_recording_provider: str = "GARMIN_CONNECT",
) -> str:
    provider_start_time_utc = datetime(
        execution_date.year,
        execution_date.month,
        execution_date.day,
        5,
        tzinfo=timezone.utc,
    )
    provider_start_time_local = datetime(
        execution_date.year,
        execution_date.month,
        execution_date.day,
        7,
    )
    activity = make_activity(id=local_activity_id, date=execution_date)
    activity = activity.model_copy(
        update={
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.HISTORICAL_IMPORT,
                intervals_icu_activity_id=f"i_{local_activity_id}",
            ),
            "audit": activity.audit.model_copy(
                update={
                    "performance_evidence_sha256": performance_evidence_fingerprint(
                        ActivityDTO(
                            id=f"i_{local_activity_id}",
                            type="Run",
                            name="Completed run",
                            start_date=provider_start_time_utc,
                            start_date_local=provider_start_time_local,
                            elapsed_time=1800,
                            moving_time=1800,
                            source=source_recording_provider,
                        ),
                        activity.occurrence.timezone,
                    ),
                    "provider_snapshot_sha256": "f" * 64,
                    "canonical_mapping_version": 9,
                }
            ),
        }
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    return activity_performance_evidence_sha256(activity)


def _confirmed_fulfillment(
    workout: AuthoritativeWorkout,
    *,
    local_activity_id: str,
    execution_date: date,
    activity_performance_sha256: str,
) -> WorkoutFulfillmentRecord:
    return WorkoutFulfillmentRecord(
        local_activity_id=local_activity_id,
        workout_identity=workout.identity,
        applied_week_approval_id=workout.applied_week_approval_id,
        applied_running_workouts_sha256=workout.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(workout.prescription),
        activity_performance_evidence_sha256=activity_performance_sha256,
        schedule_timezone=workout.schedule_timezone,
        scheduled_local_date=workout.prescription.date,
        execution_local_date=execution_date,
        schedule_offset_days=(execution_date - workout.prescription.date).days,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the exact association.",
            coaching_rationale=(
                "The athlete identified this run as the approved workout execution."
            ),
            confirmed_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 8, 10, 10, tzinfo=timezone.utc),
    )


def _authoritative(workout: RunningWorkoutPrescription) -> AuthoritativeWorkout:
    return AuthoritativeWorkout(
        identity=PlanWorkoutIdentity(
            plan_id="plan_publication_test",
            plan_revision_id="plan_revision_1111111111111111",
            week_number=1,
            local_workout_id=workout.id,
        ),
        prescription=workout,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        schedule_timezone="Europe/Paris",
    )


class HarnessRunWeekSynchronizationService(RunWeekSynchronizationService):
    def __init__(self, repo, client, workouts):
        super().__init__(repo, client)
        self.workouts = workouts

    def _load_authoritative_week_unlocked(self, week_number):
        assert week_number == 1
        return self.workouts
