#!/usr/bin/env python3
"""
Generate complete WorkoutPrescription JSON for training plans.

This utility bridges the gap between plan outlines (markdown/JSON) and complete
WorkoutPrescription objects with all 20+ required fields populated.

Usage:
    # Generate single week
    python generate_workouts.py week \\
      --week-number 1 \\
      --phase base \\
      --start-date 2026-01-19 \\
      --volume 22.0 \\
      --schedule-file week1_outline.json \\
      --vdot 39 \\
      --max-hr 199 \\
      --output /tmp/week1.json

    # Generate full plan (multiple weeks)
    python generate_workouts.py plan \\
      --plan-outline plan_outline.json \\
      --vdot 39 \\
      --max-hr 199 \\
      --output /tmp/full_plan.json
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# Add parent directory to path to import from sports_coach_engine
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sports_coach_engine.core.plan import create_workout
from sports_coach_engine.schemas.plan import (
    PlanPhase,
    WorkoutType,
    IntensityZone,
    WorkoutPrescription,
)


def create_workout_prescription(
    week_number: int,
    day_of_week: int,  # 0=Mon, 6=Sun
    date_str: str,  # ISO format
    workout_type: str,  # easy|long_run|tempo|intervals|rest
    phase: str,  # base|build|peak|taper
    volume_target_km: float,
    vdot: int,
    max_hr: int,
    purpose: Optional[str] = None,
    notes: Optional[str] = None,
    key_workout: Optional[bool] = None,
) -> dict:
    """
    Generate complete WorkoutPrescription dict with all required fields.

    This function:
    1. Calculates pace ranges from VDOT using Daniels tables
    2. Calculates HR zones from max_hr using %HRmax
    3. Assigns intensity zone based on workout type
    4. Sets RPE based on intensity
    5. Adds warmup/cooldown based on workout type
    6. Returns complete dict matching WorkoutPrescription schema

    Args:
        week_number: Week number in plan (1-indexed)
        day_of_week: Day of week (0=Monday, 6=Sunday)
        date_str: Workout date in ISO format (YYYY-MM-DD)
        workout_type: Type of workout (easy, long_run, tempo, intervals, rest, etc.)
        phase: Periodization phase (base, build, peak, taper)
        volume_target_km: Target weekly volume in km
        vdot: Athlete's VDOT (30-85)
        max_hr: Athlete's max heart rate (120-220)
        purpose: Optional custom purpose (overrides default)
        notes: Optional execution notes
        key_workout: Optional override for key_workout flag

    Returns:
        Complete WorkoutPrescription dict with all fields populated
    """
    # Validate inputs
    if not 30 <= vdot <= 85:
        raise ValueError(f"VDOT must be 30-85, got {vdot}")
    if not 120 <= max_hr <= 220:
        raise ValueError(f"max_hr must be 120-220, got {max_hr}")

    # Parse date
    workout_date = datetime.fromisoformat(date_str).date()

    # Convert phase string to enum
    phase_enum = PlanPhase(phase)

    # Build profile dict for create_workout
    profile = {
        "vdot": vdot,
        "vital_signs": {"max_hr": max_hr},
    }

    # Use existing create_workout function
    workout = create_workout(
        workout_type=workout_type,
        workout_date=workout_date,
        week_number=week_number,
        day_of_week=day_of_week,
        phase=phase_enum,
        volume_target_km=volume_target_km,
        profile=profile,
    )

    # Override purpose if provided
    if purpose:
        workout.purpose = purpose

    # Override notes if provided
    if notes:
        workout.notes = notes

    # Override key_workout if provided
    if key_workout is not None:
        workout.key_workout = key_workout

    # Convert to dict for JSON serialization
    return workout.model_dump(mode="json")


def generate_week_workouts(
    week_number: int,
    phase: str,
    start_date: str,  # Monday ISO format
    end_date: str,  # Sunday ISO format
    target_volume_km: float,
    workout_schedule: list[dict],
    vdot: int,
    max_hr: int,
    target_systemic_load_au: Optional[float] = None,
    is_recovery_week: bool = False,
    notes: Optional[str] = None,
) -> dict:
    """
    Generate complete week dict with workouts array populated.

    Args:
        week_number: Week number in plan (1-indexed)
        phase: Periodization phase (base, build, peak, taper)
        start_date: Week start date (Monday) in ISO format
        end_date: Week end date (Sunday) in ISO format
        target_volume_km: Target weekly volume in km
        workout_schedule: List of workout outlines with structure:
            [
                {
                    "day": "monday",  # or day_of_week: 0
                    "type": "easy",
                    "purpose": "Recovery",
                    "notes": "optional"
                },
                ...
            ]
        vdot: Athlete's VDOT
        max_hr: Athlete's max heart rate
        target_systemic_load_au: Optional target load (calculated if not provided)
        is_recovery_week: Whether this is a recovery week
        notes: Optional week-level notes

    Returns:
        Complete week dict with populated workouts array:
        {
            "week_number": 1,
            "phase": "base",
            "start_date": "2026-01-19",
            "end_date": "2026-01-25",
            "target_volume_km": 22.0,
            "target_systemic_load_au": 154.0,
            "is_recovery_week": false,
            "notes": "...",
            "workouts": [...]
        }
    """
    # Validate date alignment
    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()

    if start.weekday() != 0:
        raise ValueError(f"start_date must be Monday (weekday 0), got {start} (weekday {start.weekday()})")
    if end.weekday() != 6:
        raise ValueError(f"end_date must be Sunday (weekday 6), got {end} (weekday {end.weekday()})")

    # Calculate target load if not provided
    if target_systemic_load_au is None:
        target_systemic_load_au = round(target_volume_km * 7, 1)

    # Generate workouts
    workouts = []
    for workout_def in workout_schedule:
        # Get day of week (0-6)
        if "day_of_week" in workout_def:
            day_of_week = workout_def["day_of_week"]
        else:
            day_name = workout_def["day"].lower()
            day_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }
            day_of_week = day_map[day_name]

        # Calculate workout date
        workout_date = start + timedelta(days=day_of_week)

        # Create workout
        workout = create_workout_prescription(
            week_number=week_number,
            day_of_week=day_of_week,
            date_str=workout_date.isoformat(),
            workout_type=workout_def["type"],
            phase=phase,
            volume_target_km=target_volume_km,
            vdot=vdot,
            max_hr=max_hr,
            purpose=workout_def.get("purpose"),
            notes=workout_def.get("notes"),
            key_workout=workout_def.get("key_workout"),
        )

        workouts.append(workout)

    # Build week dict
    week = {
        "week_number": week_number,
        "phase": phase,
        "start_date": start_date,
        "end_date": end_date,
        "target_volume_km": round(target_volume_km, 1),
        "target_systemic_load_au": round(target_systemic_load_au, 1),
        "is_recovery_week": is_recovery_week,
        "workouts": workouts,
    }

    if notes:
        week["notes"] = notes

    return week


def generate_plan_workouts(
    plan_outline: dict,
    vdot: int,
    max_hr: int,
) -> dict:
    """
    Generate complete plan JSON with all weeks and workouts populated.

    Args:
        plan_outline: Plan structure with weeks array containing:
            - week_number, phase, start_date, end_date
            - target_volume_km
            - workout_schedule: list of workout definitions
            - Optional: target_systemic_load_au, is_recovery_week, notes
        vdot: Athlete's VDOT
        max_hr: Athlete's max heart rate

    Returns:
        Complete plan dict with all workouts populated
    """
    # Copy plan metadata
    plan = {
        "goal_type": plan_outline.get("goal_type"),
        "goal_date": plan_outline.get("goal_date"),
        "created_at": plan_outline.get("created_at", datetime.now().isoformat()),
        "weeks": [],
    }

    # Generate each week
    for week_outline in plan_outline["weeks"]:
        week = generate_week_workouts(
            week_number=week_outline["week_number"],
            phase=week_outline["phase"],
            start_date=week_outline["start_date"],
            end_date=week_outline["end_date"],
            target_volume_km=week_outline["target_volume_km"],
            workout_schedule=week_outline["workout_schedule"],
            vdot=vdot,
            max_hr=max_hr,
            target_systemic_load_au=week_outline.get("target_systemic_load_au"),
            is_recovery_week=week_outline.get("is_recovery_week", False),
            notes=week_outline.get("notes"),
        )
        plan["weeks"].append(week)

    return plan


def validate_week(week: dict) -> list[str]:
    """
    Validate a week structure and return list of errors (empty if valid).

    Checks:
    - start_date is Monday (weekday 0)
    - end_date is Sunday (weekday 6)
    - All workouts have required fields
    - Total workout volume ≈ target_volume_km (within 10%)
    """
    errors = []

    # Check date alignment
    start = datetime.fromisoformat(week["start_date"]).date()
    end = datetime.fromisoformat(week["end_date"]).date()

    if start.weekday() != 0:
        errors.append(f"Week {week['week_number']}: start_date {start} is not Monday (weekday {start.weekday()})")
    if end.weekday() != 6:
        errors.append(f"Week {week['week_number']}: end_date {end} is not Sunday (weekday {end.weekday()})")

    # Check workouts exist
    if not week.get("workouts"):
        errors.append(f"Week {week['week_number']}: workouts array is empty")
        return errors

    # Check each workout has required fields
    required_fields = [
        "id", "week_number", "day_of_week", "date",
        "workout_type", "phase", "duration_minutes",
        "intensity_zone", "target_rpe", "purpose",
    ]
    for i, workout in enumerate(week["workouts"]):
        for field in required_fields:
            if field not in workout:
                errors.append(f"Week {week['week_number']}, workout {i}: missing field '{field}'")

    # Check volume match (within 10%)
    actual_volume = sum(w.get("distance_km", 0) or 0 for w in week["workouts"])
    target_volume = week["target_volume_km"]
    volume_diff = abs(actual_volume - target_volume)
    if volume_diff > target_volume * 0.1:
        errors.append(
            f"Week {week['week_number']}: workout volume {actual_volume:.1f}km "
            f"differs from target {target_volume:.1f}km by {volume_diff:.1f}km (>{target_volume * 0.1:.1f}km)"
        )

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Generate complete WorkoutPrescription JSON for training plans"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Week command
    week_parser = subparsers.add_parser("week", help="Generate single week workouts")
    week_parser.add_argument("--week-file", required=True, help="JSON file with week outline")
    week_parser.add_argument("--vdot", type=int, required=True, help="Athlete VDOT (30-85)")
    week_parser.add_argument("--max-hr", type=int, required=True, help="Max heart rate (120-220)")
    week_parser.add_argument("--output", required=True, help="Output JSON file path")

    # Plan command
    plan_parser = subparsers.add_parser("plan", help="Generate full plan workouts")
    plan_parser.add_argument("--plan-outline", required=True, help="JSON file with plan outline")
    plan_parser.add_argument("--vdot", type=int, required=True, help="Athlete VDOT (30-85)")
    plan_parser.add_argument("--max-hr", type=int, required=True, help="Max heart rate (120-220)")
    plan_parser.add_argument("--output", required=True, help="Output JSON file path")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate week/plan structure")
    validate_parser.add_argument("--file", required=True, help="JSON file to validate")
    validate_parser.add_argument("--type", choices=["week", "plan"], required=True, help="File type")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "week":
            # Load week outline
            with open(args.week_file) as f:
                week_outline = json.load(f)

            # Generate week
            week = generate_week_workouts(
                week_number=week_outline["week_number"],
                phase=week_outline["phase"],
                start_date=week_outline["start_date"],
                end_date=week_outline["end_date"],
                target_volume_km=week_outline["target_volume_km"],
                workout_schedule=week_outline["workout_schedule"],
                vdot=args.vdot,
                max_hr=args.max_hr,
                target_systemic_load_au=week_outline.get("target_systemic_load_au"),
                is_recovery_week=week_outline.get("is_recovery_week", False),
                notes=week_outline.get("notes"),
            )

            # Validate
            errors = validate_week(week)
            if errors:
                print("⚠️  Validation warnings:", file=sys.stderr)
                for error in errors:
                    print(f"  - {error}", file=sys.stderr)

            # Write output
            with open(args.output, "w") as f:
                json.dump(week, f, indent=2)

            print(f"✅ Generated week {week['week_number']} with {len(week['workouts'])} workouts")
            print(f"   Output: {args.output}")

        elif args.command == "plan":
            # Load plan outline
            with open(args.plan_outline) as f:
                plan_outline = json.load(f)

            # Generate plan
            plan = generate_plan_workouts(
                plan_outline=plan_outline,
                vdot=args.vdot,
                max_hr=args.max_hr,
            )

            # Validate each week
            total_errors = []
            for week in plan["weeks"]:
                errors = validate_week(week)
                total_errors.extend(errors)

            if total_errors:
                print("⚠️  Validation warnings:", file=sys.stderr)
                for error in total_errors:
                    print(f"  - {error}", file=sys.stderr)

            # Write output
            with open(args.output, "w") as f:
                json.dump(plan, f, indent=2)

            total_workouts = sum(len(w["workouts"]) for w in plan["weeks"])
            print(f"✅ Generated {len(plan['weeks'])} weeks with {total_workouts} total workouts")
            print(f"   Output: {args.output}")

        elif args.command == "validate":
            # Load file
            with open(args.file) as f:
                data = json.load(f)

            # Validate
            if args.type == "week":
                errors = validate_week(data)
            else:  # plan
                errors = []
                for week in data["weeks"]:
                    errors.extend(validate_week(week))

            if errors:
                print("❌ Validation failed:", file=sys.stderr)
                for error in errors:
                    print(f"  - {error}", file=sys.stderr)
                sys.exit(1)
            else:
                print("✅ Validation passed")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
