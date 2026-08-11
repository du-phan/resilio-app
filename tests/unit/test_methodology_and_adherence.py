"""Plan-methodology and verified adherence contracts."""

from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.coaching_context.adherence import build_adherence_context
from resilio.core.methodology import (
    MethodologyRegistryError,
    resolve_methodology_choice,
    verify_methodology_selection,
)
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.schemas.activity import (
    ActivityAudit,
    ActivityDuration,
    ActivityOccurrence,
    ActivityOrigin,
    ActivityOriginKind,
    CanonicalActivity,
)
from resilio.schemas.methodology import (
    MethodologyChoice,
    TrainingMethodology,
)
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription, WorkoutType
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    ProviderPairedFulfillmentEvidence,
    UnresolvedFulfillmentConflict,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _authoritative(workout: RunningWorkoutPrescription) -> AuthoritativeWorkout:
    return AuthoritativeWorkout(
        identity=PlanWorkoutIdentity(
            plan_id="plan_test",
            plan_revision_id="plan_revision_1111111111111111",
            week_number=1,
            local_workout_id=workout.id,
        ),
        prescription=workout,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        schedule_timezone="Europe/Paris",
    )


def _workout(
    workout_id: str,
    workout_date: date,
    workout_type: WorkoutType,
) -> RunningWorkoutPrescription:
    return RunningWorkoutPrescription(
        id=workout_id,
        date=workout_date,
        workout_type=workout_type,
        planned_duration_seconds=3_600,
        planned_distance_meters=10_000,
        planned_low_intensity_duration_seconds=(
            3_600 if workout_type in {WorkoutType.EASY, WorkoutType.LONG_RUN} else 0
        ),
        planned_moderate_intensity_duration_seconds=0,
        planned_high_intensity_duration_seconds=(
            3_600
            if workout_type in {WorkoutType.INTERVALS, WorkoutType.STRIDES, WorkoutType.RACE}
            else 0
        ),
        target_rpe_1_to_10=5,
        purpose="Test the planned training stimulus.",
        structured_workout={
            "sport": "run",
            "steps": [
                {
                    "kind": "steady",
                    "duration": {"unit": "seconds", "value": 3_600},
                    "intensity": "active",
                    "cue": "Follow the approved session intent.",
                }
            ],
        },
    )


def _activity(activity_id: str, activity_date: date) -> CanonicalActivity:
    intervals_activity_id = activity_id.removeprefix("act_i_")
    return CanonicalActivity(
        local_activity_id=activity_id,
        sport="run",
        source_sport_type="Run",
        name="Run",
        occurrence=ActivityOccurrence(
            local_date=activity_date,
            start_time_local=datetime.combine(
                activity_date,
                datetime.min.time(),
                tzinfo=ZoneInfo("Europe/Paris"),
            ),
        ),
        duration=ActivityDuration(
            elapsed_seconds=3_600,
            moving_seconds=3_600,
        ),
        origin=ActivityOrigin(
            kind=ActivityOriginKind.INTERVALS_ICU,
            intervals_icu_activity_id=intervals_activity_id,
        ),
        audit=ActivityAudit(
            imported_at_utc=datetime(2026, 7, 30, tzinfo=timezone.utc),
        ),
    )


def test_methodology_selection_is_resolved_from_controlled_source(
    tmp_path,
) -> None:
    source = tmp_path / "docs/training_books/daniels_running_formula.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(
        (PROJECT_ROOT / "docs/training_books/daniels_running_formula.md").read_bytes()
    )
    choice = MethodologyChoice(
        identifier=TrainingMethodology.DANIELS,
        selection_rationale="Matches the athlete's race-distance and frequency constraints.",
    )
    selection = resolve_methodology_choice(tmp_path, choice)

    assert selection.identifier == TrainingMethodology.DANIELS
    assert selection.source_document == ("docs/training_books/daniels_running_formula.md")
    assert selection.source_verification_scope == "conceptual_summary_only"
    assert selection.planning_authority == "coach_designed_conceptually_informed"
    assert selection.executable_policy_version == "coach_planning_policy_v1"
    verify_methodology_selection(tmp_path, selection)

    source.write_text("Changed source revision\n")
    with pytest.raises(MethodologyRegistryError, match="controlled registry"):
        verify_methodology_selection(tmp_path, selection)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_document", "docs/training_books/other.md"),
        ("source_revision_sha256", "a" * 64),
        ("selection_rationale", "vague"),
    ],
)
def test_methodology_selection_rejects_untraceable_evidence(
    field: str,
    value: str,
) -> None:
    payload = {
        "identifier": "daniels",
        "selection_rationale": (
            "Selected because the athlete's available run frequency and race goal "
            "match this methodology."
        ),
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        MethodologyChoice.model_validate(payload)


def test_run_workout_requires_distance_and_exact_intensity_seconds() -> None:
    payload = _workout(
        "w_valid",
        date(2026, 7, 28),
        WorkoutType.EASY,
    ).model_dump(mode="json")
    payload["planned_distance_meters"] = None
    with pytest.raises(ValidationError, match="planned_distance_meters"):
        RunningWorkoutPrescription.model_validate(payload)

    payload["planned_distance_meters"] = 10_000
    payload["planned_low_intensity_duration_seconds"] = 3_599
    with pytest.raises(ValidationError, match="must sum"):
        RunningWorkoutPrescription.model_validate(payload)


def test_weekly_prescription_rejects_non_running_sport() -> None:
    payload = _workout(
        "w_run",
        date(2026, 7, 28),
        WorkoutType.EASY,
    ).model_dump(mode="json")
    payload["sport"] = "cycle"
    payload["structured_workout"]["sport"] = "cycle"

    with pytest.raises(ValidationError, match="Input should be 'run'"):
        RunningWorkoutPrescription.model_validate(payload)
    with pytest.raises(ValueError):
        WorkoutType("rest")


def test_only_exact_completion_ownership_counts_as_adherence() -> None:
    workout = _workout("w_quality", date(2026, 7, 28), WorkoutType.INTERVALS)
    activity = _activity("act_i_completed", date(2026, 7, 28))
    manifest = WorkoutFulfillmentManifest(
        fulfillments={
            activity.local_activity_id: WorkoutFulfillmentRecord(
                local_activity_id=activity.local_activity_id,
                workout_identity=_authoritative(workout).identity,
                applied_week_approval_id="week_approval_0123456789abcdef",
                applied_running_workouts_sha256="1" * 64,
                workout_prescription_sha256=canonical_data_sha256(workout),
                activity_performance_evidence_sha256=(
                    activity_performance_evidence_sha256(activity)
                ),
                schedule_timezone="Europe/Paris",
                scheduled_local_date=date(2026, 7, 28),
                execution_local_date=date(2026, 7, 28),
                schedule_offset_days=0,
                provider_pair=ProviderPairedFulfillmentEvidence(
                    event_id=42,
                    observed_at_utc=datetime(2026, 7, 29, tzinfo=timezone.utc),
                ),
                recorded_at_utc=datetime(2026, 7, 29, tzinfo=timezone.utc),
            )
        }
    )

    context = build_adherence_context(
        workouts=[_authoritative(workout)],
        activities=[activity],
        fulfillment_manifest=manifest,
        as_of_date=date(2026, 7, 30),
    )

    assert context.due_workout_count == 1
    assert context.fulfilled_workout_count == 1
    assert context.due_fulfilled_workout_count == 1
    assert context.due_unfulfilled_workout_count == 0
    assert context.workouts[0].fulfillment_status == "fulfilled_on_schedule"
    assert context.workouts[0].fulfillment_basis == "provider_paired"
    assert context.workouts[0].matched_local_activity_id == "act_i_completed"
    assert context.due_planned_high_intensity_duration_seconds == 3_600


def test_same_day_activity_without_owned_pairing_remains_unmatched() -> None:
    workout = _workout("w_easy", date(2026, 7, 28), WorkoutType.EASY)
    activity = _activity("act_i_same_day", date(2026, 7, 28))

    context = build_adherence_context(
        workouts=[_authoritative(workout)],
        activities=[activity],
        fulfillment_manifest=WorkoutFulfillmentManifest(),
        as_of_date=date(2026, 7, 30),
    )

    assert context.fulfilled_workout_count == 0
    assert context.due_unfulfilled_workout_count == 1
    assert context.workouts[0].matched_local_activity_id is None
    assert context.due_planned_low_intensity_duration_seconds == 3_600


def test_adherence_rejects_fulfillment_after_activity_performance_changes() -> None:
    workout = _workout("w_easy", date(2026, 7, 28), WorkoutType.EASY)
    authoritative = _authoritative(workout)
    activity = _activity("act_i_changed", date(2026, 7, 28))
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=authoritative.identity,
        applied_week_approval_id=authoritative.applied_week_approval_id,
        applied_running_workouts_sha256=authoritative.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(workout),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=authoritative.schedule_timezone,
        scheduled_local_date=workout.date,
        execution_local_date=workout.date,
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            event_id=42,
            observed_at_utc=datetime(2026, 7, 29, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )
    changed_activity = activity.model_copy(
        update={"distance_meters": (activity.distance_meters or 0) + 100}
    )

    with pytest.raises(ValueError, match="performance evidence changed"):
        build_adherence_context(
            workouts=[authoritative],
            activities=[changed_activity],
            fulfillment_manifest=WorkoutFulfillmentManifest(
                fulfillments={activity.local_activity_id: fulfillment}
            ),
            as_of_date=date(2026, 7, 30),
        )


def test_adherence_rejects_fulfillment_with_a_provider_contradiction() -> None:
    workout = _workout("w_conflicted", date(2026, 7, 28), WorkoutType.EASY)
    authoritative = _authoritative(workout)
    activity = _activity("act_i_conflicted", date(2026, 7, 28))
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=authoritative.identity,
        applied_week_approval_id=authoritative.applied_week_approval_id,
        applied_running_workouts_sha256=authoritative.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(workout),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=authoritative.schedule_timezone,
        scheduled_local_date=workout.date,
        execution_local_date=workout.date,
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            event_id=42,
            observed_at_utc=datetime(2026, 7, 29, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )
    manifest = WorkoutFulfillmentManifest(
        fulfillments={activity.local_activity_id: fulfillment},
        unresolved_fulfillment_conflicts={
            activity.local_activity_id: UnresolvedFulfillmentConflict(
                local_activity_id=activity.local_activity_id,
                rule="paired_event_removed",
                observed_at_utc=datetime(2026, 7, 30, tzinfo=timezone.utc),
            )
        },
    )

    with pytest.raises(ValueError, match="unresolved synchronized conflict"):
        build_adherence_context(
            workouts=[authoritative],
            activities=[activity],
            fulfillment_manifest=manifest,
            as_of_date=date(2026, 7, 30),
        )


def test_future_workout_is_not_treated_as_due() -> None:
    workout = _workout("w_future", date(2026, 8, 1), WorkoutType.LONG_RUN)

    context = build_adherence_context(
        workouts=[_authoritative(workout)],
        activities=[],
        fulfillment_manifest=WorkoutFulfillmentManifest(),
        as_of_date=date(2026, 7, 30),
    )

    assert context.planned_workout_count == 1
    assert context.due_workout_count == 0
    assert context.due_unfulfilled_workout_count == 0
    assert context.workouts[0].is_due is False


def test_early_fulfilled_future_workout_is_not_outstanding() -> None:
    workout = _workout("w_early", date(2026, 7, 28), WorkoutType.EASY)
    authoritative = _authoritative(workout)
    activity = _activity("act_i_early", date(2026, 7, 27))
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=authoritative.identity,
        applied_week_approval_id=authoritative.applied_week_approval_id,
        applied_running_workouts_sha256=(authoritative.applied_running_workouts_sha256),
        workout_prescription_sha256=canonical_data_sha256(workout),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=authoritative.schedule_timezone,
        scheduled_local_date=date(2026, 7, 28),
        execution_local_date=date(2026, 7, 27),
        schedule_offset_days=-1,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the proposed association.",
            coaching_rationale=(
                "The athlete explicitly confirmed the exact approved easy-run intent."
            ),
            confirmed_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
    )

    context = build_adherence_context(
        workouts=[authoritative],
        activities=[activity],
        fulfillment_manifest=WorkoutFulfillmentManifest(
            fulfillments={activity.local_activity_id: fulfillment}
        ),
        as_of_date=date(2026, 7, 27),
    )

    assert context.due_workout_count == 0
    assert context.fulfilled_workout_count == 1
    assert context.fulfilled_early_workout_count == 1
    assert context.workouts[0].fulfillment_status == "fulfilled_early"
    assert context.workouts[0].is_outstanding is False
