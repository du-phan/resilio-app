"""Import completed activities and inspect checkpoint state."""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from typing import Optional

import typer

from resilio.api.sync import sync_activities
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json
from resilio.core.activity_transaction import ACTIVITY_MUTATION_LOCK_PATH
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import read_sync_progress, read_sync_state
from resilio.schemas.sync import SyncLockStatus, SyncReport, SyncStatusSnapshot

LOCK_PATH = ACTIVITY_MUTATION_LOCK_PATH
LOCK_STALE_SECONDS = 300


def _lock_status(repo: RepositoryIO) -> Optional[SyncLockStatus]:
    path = repo.resolve_path(LOCK_PATH)
    if not path.exists():
        return None
    descriptor = os.open(path, os.O_RDWR)
    try:
        try:
            fcntl.flock(
                descriptor,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            pass
        else:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            return None
        raw = json.loads(path.read_text())
        acquired = datetime.fromisoformat(raw["acquired_at"])
        if acquired.tzinfo is None:
            acquired = acquired.replace(tzinfo=timezone.utc)
        age = max(int((datetime.now(timezone.utc) - acquired).total_seconds()), 0)
        pid = int(raw["pid"])
        return SyncLockStatus(
            pid=pid,
            operation=str(raw.get("operation", "activity_sync")),
            acquired_at=acquired,
            age_seconds=age,
            long_running=age > LOCK_STALE_SECONDS,
        )
    except Exception:
        return None
    finally:
        os.close(descriptor)


def _status(repo: RepositoryIO) -> SyncStatusSnapshot:
    lock = _lock_status(repo)
    return SyncStatusSnapshot(
        running=lock is not None,
        lock=lock,
        progress=read_sync_progress(repo),
        state=read_sync_state(repo),
        activity_files_count=len(repo.list_files("data/activities/**/*.yaml")),
    )


def _success_message(report: SyncReport) -> str:
    outcome = "partial" if report.partial else "complete"
    return (
        f"Activity sync {outcome}: "
        f"{report.activities_created} created, "
        f"{report.activities_updated} updated, "
        f"{report.activities_linked} linked, "
        f"{report.activities_unchanged} unchanged, "
        f"{report.ambiguous_rows} ambiguous, "
        f"{report.excluded_duplicate_rows} duplicate recordings excluded, "
        f"{report.quarantined_rows} quarantined "
        f"({report.acknowledged_quarantined_rows} acknowledged)."
    )


def sync_command(
    ctx: typer.Context,
    full: bool = typer.Option(
        False,
        "--full",
        help="Reconcile the complete configured activity-history range",
    ),
    confirm_deletions: bool = typer.Option(
        False,
        "--confirm-deletions",
        help="Tombstone externally confirmed missing activities after review",
    ),
    status: bool = typer.Option(
        False,
        "--status",
        help="Show sync lock, progress, and checkpoint state",
    ),
) -> None:
    """Import completed activities into the canonical local archive."""
    repo = RepositoryIO()
    if status:
        if full or confirm_deletions:
            raise typer.BadParameter("--status cannot be combined with mutation options")
        status_result = _status(repo)
        envelope = api_result_to_envelope(
            status_result,
            success_message="Sync status fetched.",
        )
    else:
        sync_result = sync_activities(
            full=full,
            confirm_deletions=confirm_deletions,
        )
        envelope = api_result_to_envelope(
            sync_result,
            success_message=(
                _success_message(sync_result)
                if isinstance(sync_result, SyncReport)
                else "Activity sync failed"
            ),
        )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))
