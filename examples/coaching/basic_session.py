#!/usr/bin/env python3
"""
Basic coaching session - checking readiness and getting today's workout.

This example shows the essential error handling pattern for API calls.
When working as an AI coach, always check for errors before accessing fields.
"""

from sports_coach_engine.api import (
    get_profile,
    get_current_metrics,
    get_todays_workout,
)
from sports_coach_engine.api.helpers import is_error


def main():
    print("=" * 60)
    print("BASIC COACHING SESSION")
    print("=" * 60)
    print()

    # 1. Get athlete profile
    print("Loading athlete profile...")
    profile = get_profile()
    if is_error(profile):
        print(f"❌ Cannot load profile: {profile.message}")
        print("\nTo create a profile, use:")
        print("  from sports_coach_engine.api import update_profile")
        print("  profile = update_profile(name='Your Name', ...)")
        return

    print(f"✓ Athlete: {profile.name}")
    if profile.goal:
        print(f"✓ Goal: {profile.goal.type.value}")
        if profile.goal.target_date:
            print(f"✓ Target date: {profile.goal.target_date}")
    print()

    # 2. Check current training status
    print("Checking current metrics...")
    metrics = get_current_metrics()
    if is_error(metrics):
        print(f"❌ No metrics available: {metrics.message}")
        print("\nTo sync activities:")
        print("  from sports_coach_engine.api import sync_strava")
        print("  result = sync_strava()")
        return

    print("Current Training Status:")
    print(f"  Fitness (CTL): {metrics.ctl.formatted_value} - {metrics.ctl.interpretation}")
    print(f"  Fatigue (ATL): {metrics.atl.formatted_value}")
    print(f"  Form (TSB): {metrics.tsb.formatted_value} - {metrics.tsb.zone}")
    if metrics.acwr:
        print(f"  ACWR: {metrics.acwr.formatted_value} - {metrics.acwr.zone}")
    print(f"  Readiness: {metrics.readiness.formatted_value}/100 - {metrics.readiness.zone}")
    print()

    # 3. Get today's workout with adaptation checks
    print("Getting today's workout...")
    workout = get_todays_workout()
    if is_error(workout):
        print(f"❌ No workout available: {workout.message}")
        if workout.error_type == "no_plan":
            print("\nTo create a plan:")
            print("  from sports_coach_engine.api import set_goal")
            print("  goal = set_goal(race_type='10k', target_date='2026-06-01')")
        return

    print("=" * 60)
    print(f"TODAY'S WORKOUT: {workout.workout_type_display}")
    print("=" * 60)
    print(f"Duration: {workout.duration_minutes} minutes")
    print(f"Target RPE: {workout.target_rpe}/10")
    print(f"Intensity: {workout.intensity_description}")
    print()

    if workout.pace_guidance:
        print(f"Pace Guidance:")
        print(f"  {workout.pace_guidance}")
    if workout.hr_guidance:
        print(f"Heart Rate Guidance:")
        print(f"  {workout.hr_guidance}")
    print()

    print(f"Purpose: {workout.purpose}")
    print()

    if workout.has_pending_suggestion:
        print("⚠️  ADAPTATION SUGGESTED:")
        print(f"  {workout.suggestion_summary}")
        print()

    print("Rationale:")
    print(f"  {workout.rationale}")
    print()


if __name__ == "__main__":
    main()
