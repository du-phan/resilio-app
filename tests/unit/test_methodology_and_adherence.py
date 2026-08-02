"""Plan-methodology and verified adherence contracts."""

from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from resilio.core.coaching_context.adherence import build_adherence_context
from resilio.core.methodology import (
    MethodologyRegistryError,
    resolve_methodology_choice,
    verify_methodology_selection,
)
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
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
from resilio.schemas.plan import WorkoutPrescription, WorkoutType
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import (
    WorkoutCompletionManifest,
    WorkoutCompletionMatch,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _authoritative(workout: WorkoutPrescription) -> AuthoritativeWorkout:
    return AuthoritativeWorkout(
        identity=PlanWorkoutIdentity(
            plan_id="plan_test",
            plan_revision_id="plan_revision_1111111111111111",
            week_number=1,
            local_workout_id=workout.id,
        ),
        prescription=workout,
    )


def _workout(
    workout_id: str,
    workout_date: date,
    workout_type: WorkoutType,
) -> WorkoutPrescription:
    return WorkoutPrescription(
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
        WorkoutPrescription.model_validate(payload)

    payload["planned_distance_meters"] = 10_000
    payload["planned_low_intensity_duration_seconds"] = 3_599
    with pytest.raises(ValidationError, match="must sum"):
        WorkoutPrescription.model_validate(payload)


def test_cycle_workout_may_be_duration_defined_without_fake_distance() -> None:
    workout = WorkoutPrescription(
        id="w_cycle",
        date=date(2026, 7, 28),
        sport="cycle",
        workout_type="easy",
        planned_duration_seconds=3_600,
        planned_distance_meters=None,
        planned_low_intensity_duration_seconds=3_600,
        planned_moderate_intensity_duration_seconds=0,
        planned_high_intensity_duration_seconds=0,
        target_rpe_1_to_10=3,
        purpose="Preserve aerobic exposure without inventing cycling distance.",
    )

    assert workout.planned_distance_meters is None
    with pytest.raises(ValueError):
        WorkoutType("rest")


def test_only_exact_completion_ownership_counts_as_adherence() -> None:
    workout = _workout("w_quality", date(2026, 7, 28), WorkoutType.INTERVALS)
    activity = _activity("act_i_completed", date(2026, 7, 28))
    manifest = WorkoutCompletionManifest(
        matches={
            activity.local_activity_id: WorkoutCompletionMatch(
                local_activity_id=activity.local_activity_id,
                workout_identity=_authoritative(workout).identity,
                match_method="paired_event_id",
                matched_at_utc=datetime(2026, 7, 29, tzinfo=timezone.utc),
            )
        }
    )

    context = build_adherence_context(
        workouts=[_authoritative(workout)],
        activities=[activity],
        completion_manifest=manifest,
        as_of_date=date(2026, 7, 30),
    )

    assert context.due_workout_count == 1
    assert context.verified_completed_workout_count == 1
    assert context.due_unmatched_workout_count == 0
    assert context.workouts[0].matched_local_activity_id == "act_i_completed"
    assert context.due_planned_high_intensity_duration_seconds == 3_600


def test_same_day_activity_without_owned_pairing_remains_unmatched() -> None:
    workout = _workout("w_easy", date(2026, 7, 28), WorkoutType.EASY)
    activity = _activity("act_i_same_day", date(2026, 7, 28))

    context = build_adherence_context(
        workouts=[_authoritative(workout)],
        activities=[activity],
        completion_manifest=WorkoutCompletionManifest(),
        as_of_date=date(2026, 7, 30),
    )

    assert context.verified_completed_workout_count == 0
    assert context.due_unmatched_workout_count == 1
    assert context.workouts[0].matched_local_activity_id is None
    assert context.due_planned_low_intensity_duration_seconds == 3_600


def test_future_workout_is_not_treated_as_due() -> None:
    workout = _workout("w_future", date(2026, 8, 1), WorkoutType.LONG_RUN)

    context = build_adherence_context(
        workouts=[_authoritative(workout)],
        activities=[],
        completion_manifest=WorkoutCompletionManifest(),
        as_of_date=date(2026, 7, 30),
    )

    assert context.planned_workout_count == 1
    assert context.due_workout_count == 0
    assert context.due_unmatched_workout_count == 0
    assert context.workouts[0].is_due is False
