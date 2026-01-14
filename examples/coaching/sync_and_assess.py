#!/usr/bin/env python3
"""
Sync activities and assess training impact.

Shows proper error handling for sync operations and metrics analysis.
Demonstrates how to handle SyncError with optional fields like retry_after.
"""

from sports_coach_engine.api import sync_strava, get_current_metrics
from sports_coach_engine.api.sync import SyncError
from sports_coach_engine.api.metrics import MetricsError


def main():
    print("=" * 60)
    print("SYNC AND ASSESS")
    print("=" * 60)
    print()

    # Sync with detailed error handling
    print("Syncing activities from Strava...")
    result = sync_strava()

    if isinstance(result, SyncError):
        print(f"❌ Sync failed: {result.message}")
        print(f"   Error type: {result.error_type}")

        # Handle rate limiting
        if result.retry_after:
            print(f"   Rate limited - retry after {result.retry_after} seconds")

        # Show partial success
        if result.activities_imported > 0:
            print(f"   Partial success: {result.activities_imported} activities imported")
            print(f"   Failed: {result.activities_failed} activities")

        # Provide guidance based on error type
        if result.error_type == "auth":
            print("\nCheck your Strava connection in config/secrets.local.yaml")
        elif result.error_type == "network":
            print("\nCheck your internet connection and try again")

        return

    # Success - analyze results
    print(f"✓ Successfully synced {result.activities_imported} activities")
    if result.activities_skipped > 0:
        print(f"  (Skipped {result.activities_skipped} duplicates)")

    print(f"\nActivity types: {', '.join(result.activity_types)}")
    print(f"Total training time: {result.total_duration_minutes} minutes ({result.total_duration_minutes / 60:.1f} hours)")
    print(f"Total load: {result.total_load_au:.0f} AU")
    print()

    # Show metric changes
    if result.metric_changes:
        print("Metric Changes:")
        for change in result.metric_changes:
            print(f"  • {change}")
        print()

    # Show suggestions if any were generated
    if result.suggestions_generated > 0:
        print(f"⚠️  {result.suggestions_generated} adaptation suggestions generated:")
        for suggestion in result.suggestion_summaries:
            print(f"  • {suggestion}")
        print()

    # Show errors if any occurred during processing
    if result.has_errors:
        print("⚠️  Some errors occurred during processing:")
        for error_summary in result.error_summaries:
            print(f"  • {error_summary}")
        print()

    # Get current status with enriched metrics
    print("=" * 60)
    print("CURRENT TRAINING STATUS")
    print("=" * 60)

    metrics = get_current_metrics()
    if isinstance(metrics, MetricsError):
        print(f"❌ Could not load metrics: {metrics.message}")
        if metrics.minimum_days_needed:
            print(f"   Need at least {metrics.minimum_days_needed} days of data")
        return

    print(f"\nFitness Level: {metrics.ctl.zone.upper()}")
    print(f"  CTL: {metrics.ctl.value:.1f} ({metrics.ctl.interpretation})")
    if metrics.ctl.trend:
        print(f"  Trend: {metrics.ctl.trend}")

    print(f"\nForm Status: {metrics.tsb.zone.upper()}")
    print(f"  TSB: {metrics.tsb.value:.1f} ({metrics.tsb.interpretation})")
    if metrics.tsb.trend:
        print(f"  Trend: {metrics.tsb.trend}")

    if metrics.acwr:
        print(f"\nInjury Risk (ACWR): {metrics.acwr.zone.upper()}")
        print(f"  ACWR: {metrics.acwr.formatted_value} ({metrics.acwr.interpretation})")

    print(f"\nReadiness: {metrics.readiness.value}/100")
    print(f"  Level: {metrics.readiness.zone.replace('_', ' ').title()}")
    print(f"  Interpretation: {metrics.readiness.interpretation}")

    print(f"\nIntensity Distribution:")
    print(f"  Low intensity: {metrics.low_intensity_percent:.0f}%")
    if metrics.intensity_on_target:
        print(f"  ✓ Meeting 80/20 guideline")
    else:
        print(f"  ⚠️  Not meeting 80/20 guideline (target: 80% low intensity)")

    if metrics.training_load_trend:
        print(f"\nTraining Load Trend: {metrics.training_load_trend}")
        if metrics.ctl_weekly_change:
            print(f"  CTL weekly change: {metrics.ctl_weekly_change:+.1f}")

    print()


if __name__ == "__main__":
    main()
