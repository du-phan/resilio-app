"""VDOT race calculations and exact-evidence lookup."""

from datetime import date
from pathlib import Path
from typing import Optional

import typer

from resilio.api.vdot import (
    VDOTError,
    calculate_vdot_from_race,
    estimate_current_vdot,
    predict_race_times,
    propose_vdot_from_assessment,
)
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import create_success_envelope, output_json
from resilio.schemas.vdot import VDOTResult

# Create subcommand app
app = typer.Typer(help="VDOT race-performance calculations")


@app.command(name="create-proposal-from-assessment")
def create_proposal_from_assessment_command(
    review_sha256: str = typer.Option(..., "--review-sha256"),
    output_path: Path = typer.Option(..., "--out"),
) -> None:
    """Write exact VDOT proposal bytes from a closed assessment review."""
    result = propose_vdot_from_assessment(review_sha256)
    if isinstance(result, VDOTError):
        envelope = api_result_to_envelope(
            result,
            success_message="Assessment VDOT proposal",
        )
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.model_dump_json(indent=2) + "\n")
        envelope = create_success_envelope(
            message="Assessment VDOT proposal created",
            data={"path": str(output_path.resolve()), "proposal": result},
        )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="calculate")
def vdot_calculate_command(
    ctx: typer.Context,
    race_type: str = typer.Option(
        ..., "--race-type", help="Race distance: mile, 5k, 10k, half_marathon, marathon"
    ),
    time: str = typer.Option(
        ..., "--time", help="Race time in MM:SS or HH:MM:SS format (e.g., '42:30' or '1:30:00')"
    ),
    race_date: Optional[str] = typer.Option(
        None, "--race-date", help="Race date in YYYY-MM-DD format (reports evidence age)"
    ),
    as_of_date: Optional[str] = typer.Option(
        None,
        "--as-of-date",
        help="Athlete-local YYYY-MM-DD evidence date; required with --race-date",
    ),
) -> None:
    """Calculate VDOT from race performance.

    VDOT is a race-performance equivalence value. This command does not
    manufacture training pace zones.

    Examples:
        resilio vdot calculate --race-type 10k --time 42:30
        resilio vdot calculate --race-type half_marathon --time 1:30:00 \
          --race-date 2026-01-10 --as-of-date 2026-07-30
        resilio vdot calculate --race-type 5k --time 20:15

    Supported race distances:
        - mile
        - 5k
        - 10k
        - half_marathon
        - marathon
    """
    result: VDOTResult | VDOTError
    try:
        parsed_as_of_date = (
            date.fromisoformat(as_of_date)
            if as_of_date is not None
            else None
        )
    except ValueError:
        result = VDOTError(
            "invalid_input",
            "as_of_date must use YYYY-MM-DD",
        )
    else:
        result = calculate_vdot_from_race(
            race_distance=race_type,
            race_time=time,
            race_date=race_date,
            as_of_date=parsed_as_of_date,
        )

    # Build success message
    if hasattr(result, "vdot"):
        msg = f"VDOT {result.vdot} calculated from {race_type.upper()} @ {time}"
    else:
        msg = "VDOT calculation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="predict")
def vdot_predict_command(
    ctx: typer.Context,
    race_type: str = typer.Option(
        ..., "--race-type", help="Source race distance: mile, 5k, 10k, half_marathon, marathon"
    ),
    time: str = typer.Option(
        ..., "--time", help="Source race time in MM:SS or HH:MM:SS format (e.g., '42:30')"
    ),
) -> None:
    """Predict equivalent race times for other distances.

    Calculates VDOT from one race and predicts times for all other distances.
    Useful for goal setting and performance tracking.

    Examples:
        resilio vdot predict --race-type 10k --time 42:30
        resilio vdot predict --race-type half_marathon --time 1:30:00

    Output includes predictions for:
        - Mile
        - 5K
        - 10K
        - Half Marathon
        - Marathon
    """
    # Call API
    result = predict_race_times(race_distance=race_type, race_time=time)

    # Build success message
    if hasattr(result, "predictions"):
        msg = f"Predicted race times based on {race_type.upper()} @ {time}"
    else:
        msg = "Race prediction failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="estimate-current")
def vdot_estimate_current_command(
    ctx: typer.Context,
    lookback_days: int = typer.Option(
        28, "--lookback-days", help="Maximum age in days for personal-best evidence"
    ),
) -> None:
    """Return exact approved VDOT evidence or a recent personal best.

    No continuity decay, workout inference, provider VO2max conversion, or
    environmental heuristic is applied.

    Examples:
        resilio vdot estimate-current
        resilio vdot estimate-current --lookback-days 90

    Exact athlete approval is preferred. A dated personal best is used only
    when it falls inside the explicit lookback window.
    """
    # Call API
    result = estimate_current_vdot(lookback_days=lookback_days)

    # Build success message
    if not isinstance(result, VDOTError):
        msg = (
            f"Estimated current VDOT: {result.estimated_vdot} "
            f"(evidence age: {result.evidence_age_days} days)"
        )
    else:
        msg = "VDOT estimation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)
