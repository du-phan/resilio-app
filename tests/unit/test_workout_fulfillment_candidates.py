from datetime import date, datetime, timezone

import pytest

from resilio.core.workout_fulfillment.candidates import (
    FulfillmentWorkoutAuthority,
    build_fulfillment_candidates,
)
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription, WorkoutType
from resilio.schemas.workout_fulfillment import (
    HistoricalLegacyWorkoutFulfillment,
    ProviderPairedFulfillmentEvidence,
    UnresolvedFulfillmentConflict,
    WorkoutFulfillmentManifest,
)
from tests.factories import make_activity


def _workout(
    workout_id: str,
    workout_date: date,
    workout_type: WorkoutType = WorkoutType.EASY,
) -> RunningWorkoutPrescription:
    structured_workout = {
        "sport": "run",
        "steps": [
            {
                "kind": "steady",
                "duration": {"unit": "seconds", "value": 2_400},
                "intensity": "active",
                "cue": "Keep the effort conversational.",
            }
        ],
    }
    if workout_type == WorkoutType.BENCHMARK:
        structured_workout = {
            "sport": "run",
            "steps": [
                {
                    "kind": "timed_distance",
                    "distance_meters": 5_000,
                    "nominal_seconds": 2_400,
                }
            ],
        }
    return RunningWorkoutPrescription(
        id=workout_id,
        date=workout_date,
        workout_type=workout_type,
        planned_duration_seconds=2_400,
        planned_distance_meters=5_000,
        planned_low_intensity_duration_seconds=2_400,
        planned_moderate_intensity_duration_seconds=0,
        planned_high_intensity_duration_seconds=0,
        target_rpe_1_to_10=3,
        purpose="Complete one conversational five-kilometre run.",
        structured_workout=structured_workout,
    )


def _authority(workout: RunningWorkoutPrescription) -> FulfillmentWorkoutAuthority:
    return FulfillmentWorkoutAuthority(
        identity=PlanWorkoutIdentity(
            plan_id="plan_example",
            plan_revision_id="plan_revision_0123456789abcdef",
            week_number=1,
            local_workout_id=workout.id,
        ),
        prescription=workout,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        schedule_timezone="Europe/Paris",
    )


@pytest.mark.parametrize(
    ("activity_date", "scheduled_date", "timing", "offset_days"),
    [
        (date(2026, 8, 10), date(2026, 8, 11), "early", -1),
        (date(2026, 8, 11), date(2026, 8, 11), "on_schedule", 0),
        (date(2026, 8, 12), date(2026, 8, 11), "late", 1),
    ],
)
def test_candidate_reports_factual_schedule_offset(
    activity_date: date,
    scheduled_date: date,
    timing: str,
    offset_days: int,
) -> None:
    activity = make_activity(
        id="act_run",
        date=activity_date,
        start_time=datetime.combine(
            activity_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        ),
        duration_seconds=2_415,
        moving_seconds=2_259,
        distance_meters=5_500.61,
    )

    candidates = build_fulfillment_candidates(
        activity=activity,
        workout_authorities=[_authority(_workout("w_easy", scheduled_date))],
        manifest=WorkoutFulfillmentManifest(),
    )

    assert len(candidates) == 1
    assert candidates[0].timing == timing
    assert candidates[0].schedule_offset_days == offset_days
    assert candidates[0].activity_distance_meters == 5_500.61


def test_candidate_builder_does_not_rank_or_hide_same_week_options() -> None:
    activity = make_activity(id="act_run", date=date(2026, 8, 10))
    authorities = [
        _authority(_workout("w_tuesday", date(2026, 8, 11))),
        _authority(_workout("w_saturday", date(2026, 8, 15))),
    ]

    candidates = build_fulfillment_candidates(
        activity=activity,
        workout_authorities=authorities,
        manifest=WorkoutFulfillmentManifest(),
    )

    assert [candidate.workout_identity.local_workout_id for candidate in candidates] == [
        "w_tuesday",
        "w_saturday",
    ]


def test_candidates_exclude_cross_week_race_and_benchmark_workouts() -> None:
    activity = make_activity(id="act_run", date=date(2026, 8, 16))
    authorities = [
        _authority(_workout("w_next_week", date(2026, 8, 17))),
        _authority(_workout("w_race", date(2026, 8, 16), WorkoutType.RACE)),
        _authority(_workout("w_benchmark", date(2026, 8, 16), WorkoutType.BENCHMARK)),
    ]

    candidates = build_fulfillment_candidates(
        activity=activity,
        workout_authorities=authorities,
        manifest=WorkoutFulfillmentManifest(),
    )

    assert candidates == []


def test_candidates_exclude_activity_owned_by_migrated_historical_pair() -> None:
    activity = make_activity(id="act_legacy", date=date(2026, 8, 10))
    historical_identity = PlanWorkoutIdentity(
        plan_id="plan_historical",
        plan_revision_id="plan_revision_abcdef0123456789",
        week_number=1,
        local_workout_id="w_historical",
    )
    manifest = WorkoutFulfillmentManifest(
        historical_legacy_fulfillments={
            activity.local_activity_id: HistoricalLegacyWorkoutFulfillment(
                local_activity_id=activity.local_activity_id,
                workout_identity=historical_identity,
                activity_performance_evidence_sha256="3" * 64,
                scheduled_local_date=date(2026, 8, 10),
                execution_local_date=date(2026, 8, 10),
                schedule_offset_days=0,
                provider_pair=ProviderPairedFulfillmentEvidence(
                    event_id=42,
                    observed_at_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
                ),
                matched_at_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
            )
        }
    )

    candidates = build_fulfillment_candidates(
        activity=activity,
        workout_authorities=[_authority(_workout("w_current", date(2026, 8, 11)))],
        manifest=manifest,
    )

    assert candidates == []


def test_candidates_exclude_activity_with_unresolved_provider_pair_conflict() -> None:
    activity = make_activity(id="act_conflicted", date=date(2026, 8, 10))
    manifest = WorkoutFulfillmentManifest(
        unresolved_fulfillment_conflicts={
            activity.local_activity_id: UnresolvedFulfillmentConflict(
                local_activity_id=activity.local_activity_id,
                rule="paired_event_is_not_owned",
                provider_event_id_sha256="5" * 64,
                observed_at_utc=datetime(2026, 8, 10, 8, tzinfo=timezone.utc),
            )
        }
    )

    candidates = build_fulfillment_candidates(
        activity=activity,
        workout_authorities=[_authority(_workout("w_current", date(2026, 8, 11)))],
        manifest=manifest,
    )

    assert candidates == []
