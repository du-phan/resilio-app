"""Presentation helpers for the `activity laps` command."""

from __future__ import annotations

from typing import Literal

import typer
from rich.console import Console
from rich.table import Table

from resilio.cli.output import (
    create_error_envelope,
    create_success_envelope,
    output_json,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.activity import CanonicalActivity


def _load_activity(
    repo: RepositoryIO,
    local_activity_id: str,
) -> CanonicalActivity | None:
    for file_path in repo.list_files("data/activities/**/*.yaml"):
        result = repo.read_yaml(file_path, CanonicalActivity)
        if isinstance(result, CanonicalActivity) and result.local_activity_id == local_activity_id:
            return result
    return None


def activity_laps_command(
    ctx: typer.Context,
    activity_id: str = typer.Argument(
        ...,
        help="Canonical local activity ID",
    ),
    format: str = typer.Option("table", help="Output format: table|json"),
) -> None:
    """Display source lap or interval evidence for one activity."""
    try:
        activity = _load_activity(RepositoryIO(), activity_id)
        if activity is None:
            output_json(
                create_error_envelope(
                    error_type="not_found",
                    message=f"Activity {activity_id} not found",
                )
            )
            raise typer.Exit(code=4)
        if not activity.segments:
            output_json(
                create_error_envelope(
                    error_type="not_available",
                    message=(
                        f"No segment data available for {activity.name}. "
                        "This activity has no imported lap or interval markers."
                    ),
                )
            )
            raise typer.Exit(code=4)
        if format == "json":
            output_json(
                create_success_envelope(
                    message=f"Lap data for {activity.name}",
                    data={
                        "activity_id": activity.local_activity_id,
                        "activity_name": activity.name,
                        "activity_date": (activity.occurrence.local_date.isoformat()),
                        "laps": [segment.model_dump(mode="json") for segment in activity.segments],
                        "lap_count": len(activity.segments),
                    },
                )
            )
        elif format == "table":
            _display_laps_table(activity)
        else:
            output_json(
                create_error_envelope(
                    error_type="validation",
                    message="Output format must be 'table' or 'json'",
                )
            )
            raise typer.Exit(code=5)
    except typer.Exit:
        raise
    except Exception as exc:
        output_json(
            create_error_envelope(
                error_type="unknown",
                message=f"Failed to display laps: {exc}",
            )
        )
        raise typer.Exit(code=1) from exc
    if format == "json":
        raise typer.Exit(code=0)


def _display_laps_table(activity: CanonicalActivity) -> None:
    console = Console()
    table = Table(title=f"Laps: {activity.name} ({activity.occurrence.local_date})")
    columns: tuple[
        tuple[
            str,
            Literal["default", "left", "center", "right", "full"],
            str | None,
        ],
        ...,
    ] = (
        ("Lap", "right", "cyan"),
        ("Distance", "right", None),
        ("Time", "right", None),
        ("Pace", "right", "yellow"),
        ("Avg HR", "right", None),
        ("Max HR", "right", None),
        ("Elev+", "right", None),
    )
    for heading, justification, style in columns:
        table.add_column(
            heading,
            justify=justification,
            style=style,
        )
    for segment in activity.segments:
        average_hr_bpm = (
            segment.heart_rate.average_beats_per_minute if segment.heart_rate is not None else None
        )
        maximum_hr_bpm = (
            segment.heart_rate.maximum_beats_per_minute if segment.heart_rate is not None else None
        )
        table.add_row(
            str(segment.index),
            (
                f"{segment.distance_meters / 1_000:.2f} km"
                if segment.distance_meters is not None
                else "—"
            ),
            (
                _format_duration(segment.moving_seconds)
                if segment.moving_seconds is not None
                else "—"
            ),
            _pace_per_kilometer(segment.average_speed_meters_per_second) or "—",
            f"{int(average_hr_bpm)}" if average_hr_bpm else "—",
            f"{int(maximum_hr_bpm)}" if maximum_hr_bpm else "—",
            (f"{int(segment.elevation_gain_meters)}m" if segment.elevation_gain_meters else "—"),
        )
    console.print(table)
    _display_laps_summary(console, activity)


def _display_laps_summary(
    console: Console,
    activity: CanonicalActivity,
) -> None:
    distances_meters = [
        segment.distance_meters
        for segment in activity.segments
        if segment.distance_meters is not None
    ]
    moving_durations_seconds = [
        segment.moving_seconds
        for segment in activity.segments
        if segment.moving_seconds is not None
    ]
    total_distance_km = (
        sum(distances_meters) / 1_000 if len(distances_meters) == len(activity.segments) else None
    )
    total_moving_seconds = (
        sum(moving_durations_seconds)
        if len(moving_durations_seconds) == len(activity.segments)
        else None
    )
    distance_text = (
        f"{total_distance_km:.2f} km" if total_distance_km is not None else "distance incomplete"
    )
    duration_text = (
        _format_duration(total_moving_seconds)
        if total_moving_seconds is not None
        else "time incomplete"
    )
    console.print(f"\n[bold]Total:[/bold] {distance_text} in {duration_text}")
    if total_distance_km and total_moving_seconds is not None:
        pace_seconds = round(total_moving_seconds / total_distance_km)
        console.print("[bold]Avg Pace:[/bold] " f"{pace_seconds // 60}:{pace_seconds % 60:02d} /km")
    else:
        console.print("[bold]Avg Pace:[/bold] —")


def _format_duration(seconds: int) -> str:
    hours = seconds // 3_600
    minutes = (seconds % 3_600) // 60
    remaining_seconds = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes}:{remaining_seconds:02d}"


def _pace_per_kilometer(
    average_speed_meters_per_second: float | None,
) -> str | None:
    if not average_speed_meters_per_second:
        return None
    seconds_per_kilometer = round(1_000 / average_speed_meters_per_second)
    return f"{seconds_per_kilometer // 60}:" f"{seconds_per_kilometer % 60:02d}"
