"""
sce activity - List and search activities.

Simple CLI commands to surface activity data including notes (description, private_note).
These tools compute/gather data - the AI coach interprets and decides.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import re

import typer

from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.activity import NormalizedActivity
from sports_coach_engine.cli.output import output_json, create_success_envelope, create_error_envelope


# Create activity subcommand app
app = typer.Typer(
    name="activity",
    help="List and search activities",
    no_args_is_help=True,
)


def _parse_since(since: str) -> date:
    """Parse --since parameter into date.

    Supports:
    - Relative: '14d', '30d' (days ago)
    - Absolute: '2026-01-01'

    Args:
        since: Since parameter string

    Returns:
        Parsed date

    Raises:
        ValueError: If format is invalid
    """
    # Relative format: '14d'
    if since.endswith('d'):
        try:
            days = int(since[:-1])
            return (datetime.now() - timedelta(days=days)).date()
        except ValueError:
            raise ValueError(f"Invalid days format: {since}. Use '14d' for 14 days.")

    # Absolute format: YYYY-MM-DD
    try:
        return date.fromisoformat(since)
    except ValueError:
        raise ValueError(f"Invalid date format: {since}. Use 'YYYY-MM-DD'.")


def _load_activities_in_range(
    repo: RepositoryIO,
    start_date: date,
    end_date: date,
    sport: Optional[str] = None,
    has_notes: bool = False,
) -> list[dict]:
    """Load activities from YAML files in date range.

    Args:
        repo: Repository IO instance
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)
        sport: Optional sport type filter (e.g., 'run', 'climb')
        has_notes: If True, only return activities with description or private_note

    Returns:
        List of activity dicts with relevant fields
    """
    activities = []

    # Find all activity YAML files
    activity_files = repo.list_files("data/activities/**/*.yaml")

    for file_path in activity_files:
        # Read activity file
        result = repo.read_yaml(file_path, NormalizedActivity)
        if isinstance(result, NormalizedActivity):
            activity = result

            # Filter by date range
            if not (start_date <= activity.date <= end_date):
                continue

            # Filter by sport
            if sport and activity.sport_type != sport:
                continue

            # Get notes
            description = activity.description or ""
            private_note = activity.private_note or ""

            # Filter by has_notes
            if has_notes and not (description.strip() or private_note.strip()):
                continue

            # Build activity dict with relevant fields
            activities.append({
                "id": activity.id,
                "date": activity.date.isoformat(),
                "sport": activity.sport_type,
                "name": activity.name,
                "duration_minutes": activity.duration_minutes,
                "distance_km": activity.distance_km,
                "average_hr": activity.average_hr,
                "description": description,
                "private_note": private_note,
            })

    # Sort by date descending (most recent first)
    activities.sort(key=lambda x: x["date"], reverse=True)

    return activities


def _search_activities(
    activities: list[dict],
    query: str,
) -> list[dict]:
    """Search activities by keyword in notes.

    Args:
        activities: List of activity dicts
        query: Space-separated keywords (OR match)

    Returns:
        List of matching activities with match context
    """
    # Split query into keywords
    keywords = query.lower().split()

    matches = []
    for activity in activities:
        description = activity["description"].lower()
        private_note = activity["private_note"].lower()

        # Check for any keyword match (OR)
        matched_keywords = []
        matched_field = None
        matched_text = ""

        for keyword in keywords:
            if keyword in description:
                matched_keywords.append(keyword)
                if not matched_field:
                    matched_field = "description"
                    matched_text = activity["description"]
            if keyword in private_note:
                matched_keywords.append(keyword)
                if not matched_field or matched_field == "description":
                    # Prefer private_note if it has the match
                    matched_field = "private_note"
                    matched_text = activity["private_note"]

        if matched_keywords:
            # Create context snippet around the first match
            full_note = activity["private_note"] if matched_field == "private_note" else activity["description"]

            # Find the first keyword and extract surrounding context
            lower_note = full_note.lower()
            first_keyword = matched_keywords[0]
            pos = lower_note.find(first_keyword)

            if pos >= 0:
                # Extract ~50 chars before and after
                start = max(0, pos - 50)
                end = min(len(full_note), pos + len(first_keyword) + 50)
                snippet = full_note[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(full_note):
                    snippet = snippet + "..."
            else:
                snippet = full_note[:100] + ("..." if len(full_note) > 100 else "")

            matches.append({
                "id": activity["id"],
                "date": activity["date"],
                "sport": activity["sport"],
                "name": activity["name"],
                "duration_minutes": activity["duration_minutes"],
                "matched_field": matched_field,
                "matched_keywords": list(set(matched_keywords)),
                "matched_text": snippet,
                "full_note": full_note,
            })

    return matches


def activity_list_command(
    ctx: typer.Context,
    since: str = typer.Option(
        "30d",
        "--since",
        help="Time period (e.g., '30d' for 30 days, or 'YYYY-MM-DD')",
    ),
    sport: Optional[str] = typer.Option(
        None,
        "--sport",
        help="Filter by sport type (e.g., 'run', 'climb', 'cycle')",
    ),
    has_notes: bool = typer.Option(
        False,
        "--has-notes",
        help="Only return activities with description or private_note",
    ),
) -> None:
    """List activities in a date range with their notes.

    Returns activities with full context including description and private_note
    fields for AI coach to analyze.

    Examples:
        sce activity list --since 30d
        sce activity list --since 60d --sport run
        sce activity list --since 14d --has-notes
    """
    try:
        # Parse since parameter
        try:
            start_date = _parse_since(since)
        except ValueError as e:
            envelope = create_error_envelope(
                error_type="validation",
                message=str(e),
            )
            output_json(envelope)
            raise typer.Exit(code=5)

        end_date = date.today()

        # Load activities
        repo = RepositoryIO()
        activities = _load_activities_in_range(
            repo=repo,
            start_date=start_date,
            end_date=end_date,
            sport=sport,
            has_notes=has_notes,
        )

        # Build response
        envelope = create_success_envelope(
            message=f"Found {len(activities)} activities",
            data={
                "activities": activities,
                "count": len(activities),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "filters": {
                    "sport": sport,
                    "has_notes": has_notes,
                },
            },
        )

    except typer.Exit:
        raise
    except Exception as e:
        envelope = create_error_envelope(
            error_type="unknown",
            message=f"Failed to list activities: {str(e)}",
        )
        output_json(envelope)
        raise typer.Exit(code=1)

    output_json(envelope)
    raise typer.Exit(code=0)


def activity_search_command(
    ctx: typer.Context,
    query: str = typer.Option(
        ...,
        "--query",
        help="Keywords to search (space-separated = OR match)",
    ),
    since: str = typer.Option(
        "30d",
        "--since",
        help="Time period (e.g., '30d' for 30 days, or 'YYYY-MM-DD')",
    ),
    sport: Optional[str] = typer.Option(
        None,
        "--sport",
        help="Filter by sport type (e.g., 'run', 'climb', 'cycle')",
    ),
) -> None:
    """Search activities by text content in notes.

    Searches both description and private_note fields for matching keywords.
    Multiple keywords are OR-matched (any match returns the activity).

    Examples:
        sce activity search --query "ankle"
        sce activity search --query "tired fatigue" --since 60d
        sce activity search --query "pain" --sport run
    """
    try:
        # Parse since parameter
        try:
            start_date = _parse_since(since)
        except ValueError as e:
            envelope = create_error_envelope(
                error_type="validation",
                message=str(e),
            )
            output_json(envelope)
            raise typer.Exit(code=5)

        end_date = date.today()

        # Load activities
        repo = RepositoryIO()
        activities = _load_activities_in_range(
            repo=repo,
            start_date=start_date,
            end_date=end_date,
            sport=sport,
            has_notes=False,  # Search all activities, including those without notes
        )

        # Search activities
        matches = _search_activities(activities, query)

        # Build response
        envelope = create_success_envelope(
            message=f"Found {len(matches)} activities matching '{query}'",
            data={
                "matches": matches,
                "query": query,
                "total_matches": len(matches),
                "activities_searched": len(activities),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "filters": {
                    "sport": sport,
                },
            },
        )

    except typer.Exit:
        raise
    except Exception as e:
        envelope = create_error_envelope(
            error_type="unknown",
            message=f"Failed to search activities: {str(e)}",
        )
        output_json(envelope)
        raise typer.Exit(code=1)

    output_json(envelope)
    raise typer.Exit(code=0)


def activity_export_command(
    ctx: typer.Context,
    since: str = typer.Option(
        "28d",
        "--since",
        help="Time period (e.g., '28d' for 28 days, or 'YYYY-MM-DD')",
    ),
    out: str = typer.Option(
        "/tmp/activities_export.json",
        "--out",
        help="Output JSON file path",
    ),
    sport: Optional[str] = typer.Option(
        None,
        "--sport",
        help="Filter by sport type (e.g., 'run', 'climb', 'cycle')",
    ),
) -> None:
    """Export activities as JSON for use with analysis commands.

    Creates a JSON file that can be passed to sce analysis commands
    (intensity, load, gaps, capacity, risk-assess).

    Examples:
        sce activity export --since 28d --out /tmp/activities.json
        sce activity export --since 7d --out /tmp/week_activities.json --sport run
        sce analysis intensity --activities /tmp/activities.json --days 28
    """
    import json as json_module

    try:
        # Parse since parameter
        try:
            start_date = _parse_since(since)
        except ValueError as e:
            envelope = create_error_envelope(
                error_type="validation",
                message=str(e),
            )
            output_json(envelope)
            raise typer.Exit(code=5)

        end_date = date.today()

        # Load activities from YAML files
        repo = RepositoryIO()
        activity_files = repo.list_files("data/activities/**/*.yaml")

        exported = []
        for file_path in activity_files:
            result = repo.read_yaml(file_path, NormalizedActivity)
            if isinstance(result, NormalizedActivity):
                activity = result

                # Filter by date range
                if not (start_date <= activity.date <= end_date):
                    continue

                # Filter by sport
                if sport and activity.sport_type != sport:
                    continue

                # Serialize to dict using Pydantic
                exported.append(activity.model_dump(mode="json"))

        # Sort by date
        exported.sort(key=lambda x: x.get("date", ""), reverse=True)

        # Write JSON file
        with open(out, "w") as f:
            json_module.dump(exported, f, indent=2, default=str)

        # Build response
        envelope = create_success_envelope(
            message=f"Exported {len(exported)} activities to {out}",
            data={
                "count": len(exported),
                "output_file": out,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "filters": {
                    "sport": sport,
                },
            },
        )

    except typer.Exit:
        raise
    except Exception as e:
        envelope = create_error_envelope(
            error_type="unknown",
            message=f"Failed to export activities: {str(e)}",
        )
        output_json(envelope)
        raise typer.Exit(code=1)

    output_json(envelope)
    raise typer.Exit(code=0)


def activity_laps_command(
    ctx: typer.Context,
    activity_id: str = typer.Argument(..., help="Activity ID (e.g., strava_12345678901)"),
    format: str = typer.Option("table", help="Output format: table|json"),
) -> None:
    """
    Display lap-by-lap breakdown for a workout.

    Useful for verifying workout execution:
    - Did warmup stay easy? (HR < 140)
    - Were intervals at target pace? (e.g., 5:02-5:14)
    - How much elevation per lap?

    Examples:
        sce activity laps strava_12345678901
        sce activity laps strava_12345678901 --format json
    """
    try:
        repo = RepositoryIO()

        # Load activity by searching through all activities
        # NOTE: This is O(N) linear scan - acceptable for testing phase (<100 activities)
        # but will become slow as data grows:
        # - 100 activities: <1s
        # - 1000 activities: ~5-10s
        # - 5000+ activities: 30+ seconds
        # TODO: Build activity index (id -> file_path) for O(1) lookup when scaling
        activity_files = repo.list_files("data/activities/**/*.yaml")

        activity = None
        for file_path in activity_files:
            result = repo.read_yaml(file_path, NormalizedActivity)
            if isinstance(result, NormalizedActivity) and result.id == activity_id:
                activity = result
                break

        if not activity:
            envelope = create_error_envelope(
                error_type="not_found",
                message=f"Activity {activity_id} not found",
            )
            output_json(envelope)
            raise typer.Exit(code=4)

        if not activity.has_laps or not activity.laps:
            envelope = create_error_envelope(
                error_type="not_available",
                message=f"No lap data available for {activity.name}. This activity doesn't have lap markers from Strava.",
            )
            output_json(envelope)
            raise typer.Exit(code=4)

        # Format output
        if format == "json":
            laps_data = [lap.model_dump(mode="json") for lap in activity.laps]
            envelope = create_success_envelope(
                message=f"Lap data for {activity.name}",
                data={
                    "activity_id": activity.id,
                    "activity_name": activity.name,
                    "activity_date": activity.date.isoformat(),
                    "laps": laps_data,
                    "lap_count": len(activity.laps),
                },
            )
            output_json(envelope)
        else:
            # Human-readable table format
            _display_laps_table(activity)

    except typer.Exit:
        raise
    except Exception as e:
        envelope = create_error_envelope(
            error_type="unknown",
            message=f"Failed to display laps: {str(e)}",
        )
        output_json(envelope)
        raise typer.Exit(code=1)

    if format == "json":
        raise typer.Exit(code=0)


def _display_laps_table(activity: NormalizedActivity) -> None:
    """Display laps in human-readable table format using Rich."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title=f"Laps: {activity.name} ({activity.date})")

    table.add_column("Lap", justify="right", style="cyan")
    table.add_column("Distance", justify="right")
    table.add_column("Time", justify="right")
    table.add_column("Pace", justify="right", style="yellow")
    table.add_column("Avg HR", justify="right")
    table.add_column("Max HR", justify="right")
    table.add_column("Elev+", justify="right")

    for lap in activity.laps:
        # Format values
        dist_km = f"{lap.distance_meters / 1000:.2f} km"
        time_str = _format_duration(lap.moving_time_seconds)
        pace = lap.pace_per_km or "—"
        avg_hr = f"{int(lap.average_hr)}" if lap.average_hr else "—"
        max_hr = f"{int(lap.max_hr)}" if lap.max_hr else "—"
        elev = f"{int(lap.total_elevation_gain_meters)}m" if lap.total_elevation_gain_meters else "—"

        table.add_row(
            str(lap.lap_index),
            dist_km,
            time_str,
            pace,
            avg_hr,
            max_hr,
            elev,
        )

    console.print(table)

    # Summary
    total_dist = sum(lap.distance_meters for lap in activity.laps) / 1000
    total_time = sum(lap.moving_time_seconds for lap in activity.laps)
    avg_pace_s = (total_time / total_dist / 60) if total_dist > 0 else 0

    console.print(f"\n[bold]Total:[/bold] {total_dist:.2f} km in {_format_duration(total_time)}")
    console.print(f"[bold]Avg Pace:[/bold] {int(avg_pace_s)}:{int((avg_pace_s % 1) * 60):02d} /km")


def _format_duration(seconds: int) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# Register commands
app.command(name="list", help="List activities in a date range")(activity_list_command)
app.command(name="search", help="Search activities by text content")(activity_search_command)
app.command(name="export", help="Export activities as JSON for analysis commands")(activity_export_command)
app.command(name="laps", help="Display lap-by-lap breakdown for a workout")(activity_laps_command)
