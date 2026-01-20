"""
sce performance - Performance baseline and fitness tracking.

View current fitness vs. historical performance to assess progression/regression.
"""

from typing import Optional

import typer

from sports_coach_engine.api.performance import api_get_performance_baseline
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import output_json

# Create subcommand app
app = typer.Typer(help="Performance baseline and fitness tracking")


@app.command(name="baseline")
def performance_baseline_command(
    ctx: typer.Context,
    lookback_days: int = typer.Option(
        28,
        "--lookback-days",
        help="Number of days to look back for VDOT estimation (default: 28)"
    ),
) -> None:
    """Get consolidated performance baseline data.

    Combines current fitness (VDOT estimate, CTL) with historical performance
    (peak VDOT, race history) to provide complete performance context.

    This is useful for:
    - Assessing current fitness vs. peak fitness
    - Understanding progression/regression trends
    - Setting realistic race goals
    - Planning training volume and intensity

    Examples:
        sce performance baseline
        sce performance baseline --lookback-days 42

    Output includes:
        - Current fitness: VDOT estimate, CTL, confidence level
        - Peak performance: Historical peak VDOT, date, regression analysis
        - Race history: Personal bests with VDOT calculations
        - Training patterns: Typical workout distances and paces
        - Equivalent race times: Predicted times at current VDOT
        - Interpretation: Summary of fitness status
    """
    # Call API
    result = api_get_performance_baseline(lookback_days=lookback_days)

    # Build success message
    if hasattr(result, 'current_fitness'):
        current_vdot = result.current_fitness.get('vdot_estimate')
        if current_vdot:
            msg = f"Performance baseline: Current VDOT {current_vdot}"
        else:
            msg = "Performance baseline: Unable to estimate current VDOT"
    else:
        msg = "Performance baseline failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)
