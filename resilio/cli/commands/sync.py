"""
sce sync - Import activities from Strava and inspect sync status.
"""

import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import typer

from sports_coach_engine.api import sync_strava
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import output_json
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core.sync_state import read_resume_state
from sports_coach_engine.core.strava import DEFAULT_SYNC_LOOKBACK_DAYS
from sports_coach_engine.schemas.repository import RepoError
from sports_coach_engine.schemas.sync import (
    SyncLockStatus,
    SyncPhase,
    SyncProgress,
    SyncReport,
    SyncStatusSnapshot,
)


WORKFLOW_LOCK_FILE = "config/.workflow_lock"
SYNC_PROGRESS_FILE = "config/.sync_progress.json"
LOCK_STALE_SECONDS = 300


def _determine_sync_window(repo: RepositoryIO) -> int:
    """
    Determine optimal sync window based on existing data.

    Implements smart sync detection:
    - If no activities exist -> 365 days (first-time sync)
    - If activities exist -> days since latest activity + 1 (incremental with buffer)
    """
    activities_pattern = "data/activities/**/*.yaml"
    latest_date = None

    try:
        for file_path in repo.list_files(activities_pattern):
            filename = file_path.name
            if filename.startswith("."):
                continue

            try:
                activity_date = date.fromisoformat(filename[:10])
                if latest_date is None or activity_date > latest_date:
                    latest_date = activity_date
            except (ValueError, IndexError):
                continue
    except Exception:
        return DEFAULT_SYNC_LOOKBACK_DAYS

    if latest_date is None:
        return DEFAULT_SYNC_LOOKBACK_DAYS

    days_since = (date.today() - latest_date).days
    return max(days_since + 1, 1)


def _parse_since_param(since: str) -> datetime:
    """Parse --since parameter into datetime."""
    if since.endswith("d"):
        try:
            days = int(since[:-1])
            return datetime.now() - timedelta(days=days)
        except ValueError as exc:
            raise ValueError(f"Invalid days format: {since}. Use '14d' for 14 days.") from exc

    try:
        return datetime.fromisoformat(since)
    except ValueError as exc:
        raise ValueError(
            f"Invalid date format: {since}. Use 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'."
        ) from exc


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _build_lock_status(repo: RepositoryIO) -> Optional[SyncLockStatus]:
    raw = repo.read_json(WORKFLOW_LOCK_FILE)
    if raw is None or isinstance(raw, RepoError) or not isinstance(raw, dict):
        return None

    try:
        pid = int(raw["pid"])
        operation = str(raw.get("operation", "unknown"))
        acquired_at = datetime.fromisoformat(str(raw["acquired_at"]))
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    if acquired_at.tzinfo is None:
        acquired_at = acquired_at.replace(tzinfo=timezone.utc)
    age_seconds = int((now - acquired_at).total_seconds())
    stale = age_seconds > LOCK_STALE_SECONDS or not _is_pid_running(pid)

    return SyncLockStatus(
        pid=pid,
        operation=operation,
        acquired_at=acquired_at,
        age_seconds=max(age_seconds, 0),
        stale=stale,
    )


def _build_progress_status(repo: RepositoryIO) -> Optional[SyncProgress]:
    raw = repo.read_json(SYNC_PROGRESS_FILE)
    if raw is None or isinstance(raw, RepoError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return SyncProgress.model_validate(raw)
    except Exception:
        return None


def _build_sync_status(repo: RepositoryIO) -> SyncStatusSnapshot:
    lock = _build_lock_status(repo)
    progress = _build_progress_status(repo)
    resume_state = read_resume_state(repo)
    activity_files_count = len(repo.list_files("data/activities/**/*.yaml"))

    running = bool(lock is not None and not lock.stale)
    return SyncStatusSnapshot(
        running=running,
        lock=lock,
        progress=progress,
        resume_state=resume_state,
        activity_files_count=activity_files_count,
    )


def _build_success_message(result: SyncReport) -> str:
    msg = f"Synced {result.activities_imported} new activities from Strava."
    if result.laps_fetched > 0:
        msg += f"\nLap data fetched for {result.laps_fetched} running activities."
    if result.laps_skipped_age > 0:
        msg += (
            f"\n{result.laps_skipped_age} older activities synced without lap data "
            f"(>60 days old, limited coaching value)."
        )
    if result.lap_fetch_failures > 0:
        msg += f"\nLap fetch failed for {result.lap_fetch_failures} activities."
    if result.rate_limited:
        msg += (
            "\n\nStrava rate limit hit. Data saved successfully. "
            "Wait 15 minutes and run 'sce sync' again to continue."
        )
    return msg


def sync_command(
    ctx: typer.Context,
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Sync activities since (e.g., '14d' for 14 days, or '2026-01-01')",
    ),
    status: bool = typer.Option(
        False,
        "--status",
        help="Show current sync lock/progress/resume status without running sync",
    ),
) -> None:
    """Import activities from Strava and update metrics."""
    repo = RepositoryIO()

    if status:
        if since is not None:
            raise typer.BadParameter("--since cannot be combined with --status")
        snapshot = _build_sync_status(repo)
        envelope = api_result_to_envelope(
            snapshot,
            success_message="Sync status fetched.",
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    if since:
        since_dt = _parse_since_param(since)
        typer.echo(f"Syncing activities since {since_dt.date()}...")
    else:
        resume_state = read_resume_state(repo)
        if resume_state.backfill_in_progress and resume_state.target_start_date is not None:
            since_dt = datetime.combine(
                resume_state.target_start_date,
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            typer.echo(
                "Resuming historical sync backfill "
                f"from {resume_state.target_start_date.isoformat()}..."
            )
        else:
            lookback_days = _determine_sync_window(repo)
            since_dt = datetime.now() - timedelta(days=lookback_days)
            if lookback_days == DEFAULT_SYNC_LOOKBACK_DAYS:
                typer.echo(
                    "First-time sync: fetching last 365 days to establish training baseline..."
                )
            else:
                typer.echo(
                    f"Incremental sync: fetching activities since {since_dt.date()} "
                    f"({lookback_days} days)..."
                )

    result = sync_strava(since=since_dt)
    success_message = (
        _build_success_message(result)
        if isinstance(result, SyncReport)
        else "Sync completed"
    )
    envelope = api_result_to_envelope(
        result,
        success_message=success_message,
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))
