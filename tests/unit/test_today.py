from datetime import date

from resilio.cli.commands.today import _project_day_workouts
from resilio.schemas.coaching import PlannedWorkoutContext
from resilio.schemas.plan_history import PlanWorkoutIdentity


def _planned_workout(
    local_workout_id: str,
    *,
    is_outstanding: bool,
    fulfillment_status: str,
) -> PlannedWorkoutContext:
    return PlannedWorkoutContext.model_validate(
        {
            "workout_identity": PlanWorkoutIdentity(
                plan_id="plan_today",
                plan_revision_id="plan_revision_1111111111111111",
                week_number=1,
                local_workout_id=local_workout_id,
            ),
            "local_workout_id": local_workout_id,
            "occurrence_date": date(2026, 8, 11),
            "sport": "run",
            "workout_type": "easy",
            "planned_duration_seconds": 2_400,
            "planned_distance_meters": 5_000,
            "is_due": True,
            "is_outstanding": is_outstanding,
            "fulfillment_status": fulfillment_status,
            "fulfillment_basis": ("athlete_confirmed" if not is_outstanding else None),
            "execution_local_date": (date(2026, 8, 10) if not is_outstanding else None),
            "schedule_offset_days": -1 if not is_outstanding else None,
            "matched_local_activity_id": (
                "activity-fulfilled-early" if not is_outstanding else None
            ),
        }
    )


def test_day_projection_separates_early_fulfillment_from_outstanding_plan() -> None:
    early = _planned_workout(
        "fulfilled-early",
        is_outstanding=False,
        fulfillment_status="fulfilled_early",
    )
    outstanding = _planned_workout(
        "still-outstanding",
        is_outstanding=True,
        fulfillment_status="unfulfilled",
    )

    projection = _project_day_workouts(
        [early, outstanding],
        target_date=date(2026, 8, 11),
    )

    assert projection["scheduled_outstanding_workouts"] == [outstanding]
    assert projection["scheduled_fulfilled_workouts"] == [early]
    assert projection["executed_planned_workouts"] == []

    execution_projection = _project_day_workouts(
        [early, outstanding],
        target_date=date(2026, 8, 10),
    )

    assert execution_projection["scheduled_outstanding_workouts"] == []
    assert execution_projection["scheduled_fulfilled_workouts"] == []
    assert execution_projection["executed_planned_workouts"] == [early]
