"""Coordinated recovery and local-date preflight for fulfillment cutover."""

from __future__ import annotations

import os
from datetime import date, datetime

from resilio.core.activity_transaction import recover_activity_mutation, remove_path
from resilio.core.local_dates import athlete_local_date
from resilio.core.paths import athlete_profile_path
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import clear_sync_progress, read_sync_progress
from resilio.schemas.profile import AthleteProfile
from resilio.schemas.repository import ReadOptions, RepoError


class WorkoutFulfillmentMigrationPreflightError(ValueError):
    """The coordinated cutover preflight cannot prove safe local state."""


def recover_activity_sync_before_migration(repo: RepositoryIO) -> None:
    progress = read_sync_progress(repo)
    if progress is None:
        return
    run_root = repo.resolve_path(f"data/state/sync-runs/{progress.run_id}")
    if not (run_root / "commit.json").exists():
        for stale in (
            run_root / "archive",
            run_root / "previous-wellness",
            run_root / "previous-sync-state.json",
            run_root / "previous-sport-settings.json",
            run_root / "previous-workout-fulfillments.json",
        ):
            remove_path(stale)
        clear_sync_progress(repo)
        return
    recover_activity_mutation(
        active_archive=repo.resolve_path("data/activities"),
        run_root=run_root,
        replace=os.replace,
    )
    clear_sync_progress(repo)


def athlete_local_migration_date(
    repo: RepositoryIO,
    *,
    now_utc: datetime | None = None,
) -> date:
    profile = repo.read_yaml(
        athlete_profile_path(),
        AthleteProfile,
        ReadOptions(allow_missing=False),
    )
    if profile is None or isinstance(profile, RepoError):
        raise WorkoutFulfillmentMigrationPreflightError(
            "Workout-fulfillment migration requires a valid athlete profile timezone"
        )
    return athlete_local_date(profile.training_timezone, now_utc=now_utc)
