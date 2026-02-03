"""
sce status - Get current training metrics.

Shows CTL (fitness), ATL (fatigue), TSB (form), ACWR (load spike), and readiness
with interpretations and trends.
"""

import typer

from sports_coach_engine.api import get_current_metrics
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import output_json


def status_command(ctx: typer.Context) -> None:
    """Get current training metrics with interpretations.

    Returns:
    - CTL (Chronic Training Load): 42-day weighted average, represents fitness
    - ATL (Acute Training Load): 7-day weighted average, represents fatigue
    - TSB (Training Stress Balance): CTL - ATL, represents form/freshness
    - ACWR (Acute:Chronic Workload Ratio): Load spike indicator
    - Readiness: Overall readiness score (0-100) with breakdown

    Each metric includes:
    - value: Raw numeric value
    - zone: Category (e.g., RECREATIONAL, COMPETITIVE)
    - interpretation: Human-readable explanation
    - trend: Change from last week
    """
    # Call API
    result = get_current_metrics()

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=_build_success_message(result),
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


def _build_success_message(result: any) -> str:
    """Build human-readable success message from metrics result.

    Args:
        result: EnrichedMetrics from API

    Returns:
        Human-readable message
    """
    # If it's EnrichedMetrics, extract key values
    if hasattr(result, 'ctl') and hasattr(result, 'readiness'):
        # Extract numeric values from MetricInterpretation objects
        ctl_val = result.ctl.value
        readiness_val = result.readiness.value
        return f"Current metrics: CTL {ctl_val:.0f}, Readiness {readiness_val:.0f}"

    # Fallback
    return "Retrieved current training metrics"
