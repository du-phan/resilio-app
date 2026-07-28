"""Focused validation for explicit weekly workout payloads."""

from dataclasses import dataclass
from datetime import datetime

from resilio.schemas.plan import WorkoutPrescription


@dataclass
class ValidationResult:
    """Detection-only validation outcome."""

    ok: bool
    errors: list[dict]
    warnings: list[dict]


def validate_explicit_workouts(
    week_data: dict,
    tolerance_km: float = 0.5,
) -> ValidationResult:
    """Validate workout fields, dates, running volume, and schedule clashes."""
    errors: list[dict] = []
    warnings: list[dict] = []
    required_fields = [
        "date",
        "sport",
        "day_of_week",
        "workout_type",
        "distance_km",
        "target_rpe",
    ]
    for index, workout in enumerate(week_data.get("workouts", [])):
        missing = [field for field in required_fields if field not in workout]
        if missing:
            errors.append(
                {
                    "type": "missing_fields",
                    "workout_index": index,
                    "fields": missing,
                    "message": f"Workout {index}: Missing required fields {missing}",
                }
            )
            continue
        try:
            WorkoutPrescription.model_validate(
                {
                    **workout,
                    "week_number": workout.get(
                        "week_number",
                        week_data.get("week_number"),
                    ),
                    "phase": workout.get("phase", week_data.get("phase")),
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "type": "invalid_workout",
                    "workout_index": index,
                    "message": f"Workout {index}: Invalid workout data: {exc}",
                }
            )

    try:
        start = datetime.fromisoformat(week_data["start_date"]).date()
        end = datetime.fromisoformat(week_data["end_date"]).date()
        for index, workout in enumerate(week_data.get("workouts", [])):
            if "date" not in workout:
                continue
            workout_date = datetime.fromisoformat(workout["date"]).date()
            if not start <= workout_date <= end:
                errors.append(
                    {
                        "type": "date_out_of_range",
                        "workout_index": index,
                        "date": str(workout_date),
                        "message": (
                            f"Workout {index}: date {workout_date} not in "
                            f"week {start} to {end}"
                        ),
                    }
                )
    except (ValueError, KeyError) as exc:
        errors.append(
            {
                "type": "date_parse_error",
                "message": f"Failed to parse dates: {exc}",
            }
        )

    actual = sum(
        workout.get("distance_km", 0)
        for workout in week_data.get("workouts", [])
        if workout.get("sport") == "run"
    )
    target = week_data.get("target_volume_km", 0)
    difference = abs(actual - target)
    if difference > tolerance_km:
        errors.append(
            {
                "type": "sum_mismatch",
                "severity": "danger",
                "actual_km": actual,
                "target_km": target,
                "diff_km": difference,
                "message": (
                    f"Workouts sum to {actual:.1f}km but target is "
                    f"{target:.1f}km (diff: {difference:.1f}km exceeds "
                    f"tolerance {tolerance_km}km)"
                ),
                "suggestion": (
                    "Adjust workout distances or update target_volume_km to match"
                ),
            }
        )
    elif difference > 0.2:
        warnings.append(
            {
                "type": "sum_mismatch_minor",
                "actual_km": actual,
                "target_km": target,
                "diff_km": difference,
                "message": (
                    f"Workouts sum to {actual:.1f}km, target is "
                    f"{target:.1f}km (diff: {difference:.1f}km, within "
                    "tolerance but noticeable)"
                ),
            }
        )

    days = [
        workout.get("day_of_week")
        for workout in week_data.get("workouts", [])
        if "day_of_week" in workout
    ]
    duplicates = [day for day in set(days) if days.count(day) > 1]
    if duplicates:
        errors.append(
            {
                "type": "duplicate_days",
                "days": duplicates,
                "message": (
                    f"Multiple workouts scheduled on same day(s): {duplicates}"
                ),
            }
        )
    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
    )
