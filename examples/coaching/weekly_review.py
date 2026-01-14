#!/usr/bin/env python3
"""
Weekly training review with insights.

Shows pattern for analyzing training data and providing coaching context.
Demonstrates the handle_error() convenience function for cleaner code.
"""

from sports_coach_engine.api import (
    get_weekly_status,
    get_intensity_distribution,
    get_current_metrics,
)
from sports_coach_engine.api.helpers import handle_error


def main():
    print("=" * 60)
    print("WEEKLY TRAINING REVIEW")
    print("=" * 60)
    print()

    # Get weekly status using handle_error for concise error handling
    status = get_weekly_status()
    if handle_error(status, "Loading weekly status"):
        print("\nSync activities first:")
        print("  from sports_coach_engine.api import sync_strava")
        print("  result = sync_strava()")
        return

    # Completion summary
    print(f"Week: {status.week_start.strftime('%b %d')} to {status.week_end.strftime('%b %d, %Y')}")
    print()

    completion_pct = status.completion_rate * 100
    completion_emoji = "✓" if completion_pct >= 80 else "⚠️" if completion_pct >= 50 else "❌"
    print(f"Workout Completion: {completion_emoji}")
    print(f"  Completed: {status.completed_workouts}/{status.planned_workouts} workouts ({completion_pct:.0f}%)")
    print(f"  Total time: {status.total_duration_minutes} minutes ({status.total_duration_minutes / 60:.1f} hours)")
    print(f"  Total load: {status.total_load_au:.0f} AU")
    print()

    # Activities breakdown
    if status.activities:
        print("=" * 60)
        print("ACTIVITIES THIS WEEK")
        print("=" * 60)

        for activity in status.activities:
            activity_date = activity['date']
            sport_type = activity['sport_type']
            duration = activity['duration_minutes']
            load = activity['systemic_load_au']
            rpe = activity.get('rpe_estimate', 'N/A')

            print(f"{activity_date}  {sport_type:15} {duration:3}min  {load:5.0f} AU  RPE {rpe}")

        print()

    # Training metrics changes
    if status.current_ctl is not None:
        print("=" * 60)
        print("TRAINING METRICS")
        print("=" * 60)

        print(f"Fitness (CTL): {status.current_ctl:.1f}", end="")
        if status.ctl_change is not None:
            change_emoji = "↑" if status.ctl_change > 0 else "↓" if status.ctl_change < 0 else "→"
            print(f"  {change_emoji} {status.ctl_change:+.1f} this week")
        else:
            print()

        print(f"Form (TSB): {status.current_tsb:.1f}", end="")
        if status.tsb_change is not None:
            change_emoji = "↑" if status.tsb_change > 0 else "↓" if status.tsb_change < 0 else "→"
            print(f"  {change_emoji} {status.tsb_change:+.1f} this week")
        else:
            print()

        if status.current_readiness is not None:
            readiness_emoji = "🟢" if status.current_readiness >= 70 else "🟡" if status.current_readiness >= 50 else "🔴"
            print(f"Readiness: {readiness_emoji} {status.current_readiness}/100")

        print()

    # Pending suggestions
    if status.pending_suggestions > 0:
        print("=" * 60)
        print(f"⚠️  PENDING ADAPTATIONS ({status.pending_suggestions})")
        print("=" * 60)
        print("You have workout suggestions to review.")
        print("Use get_pending_suggestions() to see details.")
        print()

    # Intensity distribution analysis
    print("=" * 60)
    print("INTENSITY DISTRIBUTION")
    print("=" * 60)

    dist = get_intensity_distribution(days=7)
    if not handle_error(dist, "Loading intensity distribution"):
        total_minutes = dist.low_minutes + dist.moderate_minutes + dist.high_minutes

        print(f"Total Training: {total_minutes} minutes")
        print()

        # Visual bar chart
        bar_width = 40
        low_bar = "█" * int(dist.low_percent * bar_width / 100)
        mod_bar = "█" * int(dist.moderate_percent * bar_width / 100)
        high_bar = "█" * int(dist.high_percent * bar_width / 100)

        print(f"Low (Z1-2):     {dist.low_percent:5.1f}% │{low_bar}")
        print(f"Moderate (Z3):  {dist.moderate_percent:5.1f}% │{mod_bar}")
        print(f"High (Z4-5):    {dist.high_percent:5.1f}% │{high_bar}")
        print()

        # 80/20 compliance check
        if dist.is_compliant is not None:
            if dist.is_compliant:
                print("✓ Meeting 80/20 guideline")
                print("  Your training is appropriately polarized.")
            else:
                print("⚠️  Not meeting 80/20 guideline")
                if dist.target_low_percent:
                    gap = dist.target_low_percent - dist.low_percent
                    print(f"  Target: {dist.target_low_percent:.0f}% low intensity (gap: {gap:.0f}%)")
                print("  Consider more easy/recovery runs.")

        print()

    # Get detailed metrics for additional insights
    print("=" * 60)
    print("COACHING INSIGHTS")
    print("=" * 60)

    metrics = get_current_metrics()
    if not handle_error(metrics, "Loading detailed metrics"):
        # Provide context-aware coaching insights
        if metrics.tsb.value < -25:
            print("🔴 HIGH FATIGUE ALERT")
            print("   Your TSB indicates significant accumulated fatigue.")
            print("   Consider a recovery week to consolidate adaptations.")

        elif metrics.tsb.value < -10:
            print("🟡 PRODUCTIVE TRAINING ZONE")
            print("   You're in the optimal zone for building fitness.")
            print("   Balance hard days with adequate recovery.")

        elif metrics.tsb.value > 15:
            print("🟢 HIGHLY RESTED")
            print("   Your form is excellent - great time for a race or quality work.")

        print()

        if metrics.acwr and metrics.acwr.value > 1.3:
            print("⚠️  INJURY RISK ELEVATED")
            print(f"   ACWR is {metrics.acwr.value:.2f} (caution threshold: 1.3)")
            print("   Consider moderating training load increases.")
            print()

        if not metrics.intensity_on_target:
            print("💡 INTENSITY DISTRIBUTION")
            print(f"   Currently {metrics.low_intensity_percent:.0f}% low intensity")
            print("   Target: ~80% low intensity for optimal development")
            print()


if __name__ == "__main__":
    main()
