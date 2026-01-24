"""
sce race - Race performance tracking and PB management.

Add races to history, list PBs, import races from Strava, and track
progression/regression over time.
"""

from typing import Optional

import typer

from sports_coach_engine.api.race import (
    add_race_performance,
    list_race_history,
    import_races_from_strava,
    remove_race_performance,
)
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import output_json

# Create subcommand app
app = typer.Typer(help="Race performance tracking and PB management")


@app.command(name="add")
def race_add_command(
    ctx: typer.Context,
    distance: str = typer.Option(
        ...,
        "--distance",
        help="Race distance: 5k, 10k, half_marathon, marathon"
    ),
    time: str = typer.Option(
        ...,
        "--time",
        help="Race time in MM:SS or HH:MM:SS format (e.g., '42:30' or '1:30:00')"
    ),
    date: str = typer.Option(
        ...,
        "--date",
        help="Race date in YYYY-MM-DD format"
    ),
    location: Optional[str] = typer.Option(
        None,
        "--location",
        help="Race name or location"
    ),
    source: str = typer.Option(
        "gps_watch",
        "--source",
        help="Race timing source: official_race, gps_watch, estimated"
    ),
    notes: Optional[str] = typer.Option(
        None,
        "--notes",
        help="Additional notes about the race"
    ),
) -> None:
    """Add a race performance to your race history.

    Automatically calculates VDOT, updates PB flags, and recalculates peak VDOT.

    Examples:
        sce race add --distance 10k --time 42:30 --date 2025-06-15 --location "City 10K" --source official_race
        sce race add --distance 5k --time 18:45 --date 2024-05-10 --source gps_watch
        sce race add --distance half_marathon --time 1:30:00 --date 2023-09-15

    Supported distances:
        - 5k
        - 10k
        - half_marathon
        - marathon
        - mile
        - 15k

    Race sources:
        - official_race: Chip-timed race (highest accuracy)
        - gps_watch: GPS-verified effort (good accuracy)
        - estimated: Calculated/estimated (lower accuracy)
    """
    # Call API
    result = add_race_performance(
        distance=distance,
        time=time,
        date=date,
        location=location,
        source=source,
        notes=notes,
    )

    # Build success message
    if hasattr(result, 'vdot'):
        pb_note = " [NEW PB]" if result.is_pb else ""
        msg = f"Added {distance.upper()} race: {time} on {date} (VDOT {result.vdot:.1f}){pb_note}"
    else:
        msg = "Failed to add race"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="list")
def race_list_command(
    ctx: typer.Context,
    distance: Optional[str] = typer.Option(
        None,
        "--distance",
        help="Filter by distance: 5k, 10k, half_marathon, marathon"
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Only show races after this date (YYYY-MM-DD)"
    ),
) -> None:
    """List race history grouped by distance.

    Shows all races with times, VDOTs, and PB flags.

    Examples:
        sce race list
        sce race list --distance 10k
        sce race list --since 2024-01-01
        sce race list --distance half_marathon --since 2023-06-01

    Output is grouped by distance with PBs marked.
    """
    # Call API
    result = list_race_history(
        distance_filter=distance,
        since_date=since,
    )

    # Build success message
    if isinstance(result, dict):
        total_races = sum(len(races) for races in result.values())
        msg = f"Found {total_races} races across {len(result)} distances"
    else:
        msg = "Failed to list races"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="import-from-strava")
def race_import_command(
    ctx: typer.Context,
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Only detect races after this date (YYYY-MM-DD)"
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Prompt for confirmation before adding races (default: True)"
    ),
) -> None:
    """Auto-detect potential race activities from Strava.

    Detects races based on:
    - Strava workout_type flag (1 = race)
    - Keywords in title/description (race, 5K, 10K, HM, PB, PR)
    - Distance matching standard race distances (±5%)

    Returns list of detected races for confirmation.
    User must confirm before races are added to profile.

    Examples:
        sce race import-from-strava
        sce race import-from-strava --since 2025-01-01
        sce race import-from-strava --no-interactive

    Note: This only detects races from synced activities (last 120 days).
    For older PBs, use 'sce race add' to manually add them.
    """
    # Call API
    result = import_races_from_strava(since_date=since)

    # Build success message
    if isinstance(result, list):
        msg = f"Detected {len(result)} potential races from Strava"
        if len(result) == 0:
            msg += " - no new races found that aren't already in your history"
    else:
        msg = "Failed to import races from Strava"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="remove")
def race_remove_command(
    ctx: typer.Context,
    date: str = typer.Option(
        ...,
        "--date",
        help="Race date to remove (YYYY-MM-DD)"
    ),
    distance: Optional[str] = typer.Option(
        None,
        "--distance",
        help="Distance filter if multiple races on same date"
    ),
) -> None:
    """Remove a race performance from your race history.

    If multiple races exist on the same date, you must specify --distance.
    Automatically recalculates PB flags and peak VDOT after removal.

    Examples:
        sce race remove --date 2025-01-15
        sce race remove --date 2025-03-20 --distance half_marathon
    """
    # Call API
    result = remove_race_performance(
        date=date,
        distance=distance,
    )

    # Build success message
    if result is True:
        msg = f"Removed race on {date}" + (f" ({distance})" if distance else "")
    else:
        msg = "Failed to remove race"

    # Convert to envelope
    envelope = api_result_to_envelope(result, success_message=msg)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))
