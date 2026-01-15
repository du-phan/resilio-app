"""
sce vdot - VDOT calculations and training pace generation.

Calculate VDOT from race performances, generate training pace zones,
predict equivalent race times, and apply environmental pace adjustments.
"""

from typing import Optional

import typer

from sports_coach_engine.api.vdot import (
    calculate_vdot_from_race,
    get_training_paces,
    predict_race_times,
    apply_six_second_rule_paces,
    adjust_pace_for_environment,
)
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import output_json

# Create subcommand app
app = typer.Typer(help="VDOT calculations and training paces")


@app.command(name="calculate")
def vdot_calculate_command(
    ctx: typer.Context,
    race_type: str = typer.Option(
        ...,
        "--race-type",
        help="Race distance: mile, 5k, 10k, 15k, half_marathon, marathon"
    ),
    time: str = typer.Option(
        ...,
        "--time",
        help="Race time in MM:SS or HH:MM:SS format (e.g., '42:30' or '1:30:00')"
    ),
    race_date: Optional[str] = typer.Option(
        None,
        "--race-date",
        help="Race date in YYYY-MM-DD format (affects confidence level)"
    ),
) -> None:
    """Calculate VDOT from race performance.

    VDOT is a measure of running fitness derived from race performance.
    Use this to determine your current fitness level and set training paces.

    Examples:
        sce vdot calculate --race-type 10k --time 42:30
        sce vdot calculate --race-type half_marathon --time 1:30:00 --race-date 2026-01-10
        sce vdot calculate --race-type 5k --time 20:15

    Supported race distances:
        - mile
        - 5k
        - 10k
        - 15k
        - half_marathon
        - marathon
    """
    # Call API
    result = calculate_vdot_from_race(
        race_distance=race_type,
        race_time=time,
        race_date=race_date,
    )

    # Build success message
    if hasattr(result, 'vdot'):
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


@app.command(name="paces")
def vdot_paces_command(
    ctx: typer.Context,
    vdot: int = typer.Option(..., "--vdot", help="VDOT value (30-85)"),
    unit: str = typer.Option(
        "min_per_km",
        "--unit",
        help="Pace unit: min_per_km or min_per_mile"
    ),
) -> None:
    """Get training pace zones from VDOT.

    Generates E/M/T/I/R pace ranges based on Jack Daniels' methodology.

    Examples:
        sce vdot paces --vdot 48
        sce vdot paces --vdot 55 --unit min_per_mile

    Pace zones:
        - E (Easy): Recovery runs, aerobic base
        - M (Marathon): Marathon race pace
        - T (Threshold): Lactate threshold, "comfortably hard"
        - I (Interval): VO2max intervals, hard repeats
        - R (Repetition): Speed work, very hard repeats
    """
    # Call API
    result = get_training_paces(vdot=vdot, unit=unit)

    # Build success message
    if hasattr(result, 'easy_pace_range'):
        msg = f"Generated training paces for VDOT {vdot}"
    else:
        msg = "Pace generation failed"

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
        ...,
        "--race-type",
        help="Source race distance: mile, 5k, 10k, 15k, half_marathon, marathon"
    ),
    time: str = typer.Option(
        ...,
        "--time",
        help="Source race time in MM:SS or HH:MM:SS format (e.g., '42:30')"
    ),
) -> None:
    """Predict equivalent race times for other distances.

    Calculates VDOT from one race and predicts times for all other distances.
    Useful for goal setting and performance tracking.

    Examples:
        sce vdot predict --race-type 10k --time 42:30
        sce vdot predict --race-type half_marathon --time 1:30:00

    Output includes predictions for:
        - Mile
        - 5K
        - 10K
        - 15K (if available)
        - Half Marathon
        - Marathon
    """
    # Call API
    result = predict_race_times(race_distance=race_type, race_time=time)

    # Build success message
    if hasattr(result, 'predictions'):
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


@app.command(name="six-second")
def vdot_six_second_command(
    ctx: typer.Context,
    mile_time: str = typer.Option(
        ...,
        "--mile-time",
        help="Mile time in M:SS format (e.g., '6:00')"
    ),
) -> None:
    """Apply six-second rule for novice runners.

    Use when you have no recent race but have a mile time.
    Generates estimated R/I/T paces using the 6-second rule:
        R-pace = mile pace
        I-pace = R-pace + 6 seconds per 400m
        T-pace = I-pace + 6 seconds per 400m

    Note: For VDOT 40-50 range, uses 7-8 seconds instead of 6.

    Examples:
        sce vdot six-second --mile-time 6:00
        sce vdot six-second --mile-time 8:30

    Recommendation:
        For more accurate paces, complete a recent 5K race and use
        'sce vdot calculate' instead.
    """
    # Call API
    result = apply_six_second_rule_paces(mile_time=mile_time)

    # Build success message
    if hasattr(result, 'r_pace_400m'):
        msg = f"Applied six-second rule to mile time {mile_time}"
    else:
        msg = "Six-second rule calculation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="adjust")
def vdot_adjust_command(
    ctx: typer.Context,
    pace: str = typer.Option(
        ...,
        "--pace",
        help="Base pace in M:SS per km format (e.g., '5:00')"
    ),
    condition: str = typer.Option(
        ...,
        "--condition",
        help="Condition type: altitude, heat, humidity, hills"
    ),
    severity: float = typer.Option(
        ...,
        "--severity",
        help="Severity: altitude in feet, temp in °C, humidity %, grade %"
    ),
) -> None:
    """Adjust pace for environmental conditions.

    Calculate pace adjustments for altitude, heat, humidity, or hills.
    Returns adjusted pace and coaching recommendations.

    Examples:
        sce vdot adjust --pace 5:00 --condition altitude --severity 7000
        sce vdot adjust --pace 4:30 --condition heat --severity 30
        sce vdot adjust --pace 5:15 --condition hills --severity 5

    Condition types:
        - altitude: Severity in feet (e.g., 7000 for 7000ft)
        - heat: Severity in °C (e.g., 30 for 30°C)
        - humidity: Severity in % (e.g., 80 for 80%)
        - hills: Severity in grade % (e.g., 5 for 5% grade)

    Recommendations:
        - Altitude >7000ft: Use effort-based pacing (RPE/HR)
        - Heat >30°C: Consider treadmill or cooler time of day
        - Hills >5%: Focus on effort, not pace
    """
    # Call API
    result = adjust_pace_for_environment(
        base_pace=pace,
        condition_type=condition,
        severity=severity,
    )

    # Build success message
    if hasattr(result, 'adjusted_pace_sec_per_km'):
        msg = f"Adjusted pace for {condition} ({severity})"
    else:
        msg = "Pace adjustment failed"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)
