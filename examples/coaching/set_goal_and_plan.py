#!/usr/bin/env python3
"""
Set a training goal and generate a plan.

Shows the complete workflow from goal setting to plan generation.
Demonstrates proper error handling across multiple API calls.
"""

from datetime import date, timedelta
from sports_coach_engine.api import set_goal, get_current_plan
from sports_coach_engine.api.helpers import is_error


def main():
    print("=" * 60)
    print("GOAL SETTING AND PLAN GENERATION")
    print("=" * 60)
    print()

    # Set a half marathon goal 12 weeks from now
    target_date = date.today() + timedelta(weeks=12)

    print(f"Setting goal: Half Marathon on {target_date.strftime('%B %d, %Y')}")
    print("Target time: 1:45:00")
    print()

    goal = set_goal(
        race_type="half_marathon",
        target_date=target_date,
        target_time="1:45:00",
    )

    if is_error(goal):
        print(f"❌ Failed to set goal: {goal.message}")
        print(f"   Error type: {goal.error_type}")

        # Provide context-specific guidance
        if goal.error_type == "validation":
            print("\nCheck that:")
            print("  • Target date is in the future")
            print("  • Target time is in HH:MM:SS format")
            print("  • Race type is valid (5k, 10k, half_marathon, marathon)")
        elif goal.error_type == "not_found":
            print("\nCreate a profile first:")
            print("  from sports_coach_engine.api import update_profile")
            print("  profile = update_profile(name='Your Name', ...)")

        return

    print(f"✓ Goal set successfully!")
    print(f"  Type: {goal.type.value}")
    print(f"  Target date: {goal.target_date}")
    print(f"  Target time: {goal.target_time}")
    if goal.effort_level:
        print(f"  Effort level: {goal.effort_level}")
    print()

    # Get the generated plan
    print("Retrieving training plan...")
    plan = get_current_plan()

    if is_error(plan):
        print(f"❌ Plan not available: {plan.message}")
        print(f"   Error type: {plan.error_type}")

        if plan.error_type == "no_goal":
            print("\nSet a goal first (this shouldn't happen after setting goal above)")
        elif plan.error_type == "validation":
            print("\nPlan validation failed - check profile constraints")

        return

    print(f"✓ Training plan generated successfully!")
    print()

    print("=" * 60)
    print("TRAINING PLAN OVERVIEW")
    print("=" * 60)
    print(f"Duration: {plan.total_weeks} weeks")
    print(f"Start: {plan.plan_start}")
    print(f"End: {plan.plan_end}")
    print()

    print("Constraints Applied:")
    constraints = plan.constraints_applied
    print(f"  Run frequency: {constraints.min_run_days_per_week}-{constraints.max_run_days_per_week} days/week")
    print(f"  Available run days: {', '.join(constraints.available_run_days)}")
    if constraints.max_time_per_session_minutes:
        print(f"  Max session time: {constraints.max_time_per_session_minutes} minutes")
    print()

    # Show phase breakdown
    if plan.weeks:
        print("Phase Breakdown:")
        current_phase = None
        phase_weeks = []

        for week in plan.weeks:
            if week.phase != current_phase:
                if current_phase:
                    print(f"  {current_phase.title()}: Weeks {phase_weeks[0]}-{phase_weeks[-1]} ({len(phase_weeks)} weeks)")
                current_phase = week.phase
                phase_weeks = [week.week_number]
            else:
                phase_weeks.append(week.week_number)

        # Print last phase
        if current_phase:
            print(f"  {current_phase.title()}: Weeks {phase_weeks[0]}-{phase_weeks[-1]} ({len(phase_weeks)} weeks)")
        print()

    # Show first week details
    if plan.weeks:
        first_week = plan.weeks[0]
        print("=" * 60)
        print(f"WEEK 1 SCHEDULE ({first_week.week_start} to {first_week.week_end})")
        print("=" * 60)

        for workout in first_week.workouts:
            if workout:
                day_name = workout.date.strftime("%A")
                print(f"{day_name:10} {workout.workout_type_display:15} {workout.duration_minutes} min, RPE {workout.target_rpe}")
            else:
                print("          Rest day")

        print()
        print(f"Week 1 Totals:")
        print(f"  Volume: {first_week.weekly_volume_km:.1f} km")
        print(f"  Duration: {first_week.total_duration_minutes} minutes")

    print()
    print("Use get_todays_workout() to see details for any specific workout")


if __name__ == "__main__":
    main()
