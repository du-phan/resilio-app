"""Checkpointed initial, incremental, and full completed-activity sync."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.errors import (
    ActivitySyncError as ActivitySyncError,
)
from resilio.core.activity_sync.evidence_coverage import record_sync_coverage
from resilio.core.activity_sync.retrieval import (
    ActivityListing,
    fetch_activity_details,
    list_complete_activity_rows,
)
from resilio.core.activity_sync.staged_reconciliation import (
    StagedActivityReconciler,
    StagedReconciliationOutcome,
)
from resilio.core.activity_sync.windowing import enumerate_windows
from resilio.core.activity_transaction import (
    ACTIVITY_MUTATION_LOCK_PATH,
    MutationSidecar,
    commit_activity_mutation,
    recover_activity_mutation,
    remove_path,
)
from resilio.core.locking import OperationLock
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import (
    clear_sync_progress,
    read_sync_progress,
    read_sync_state,
    write_sync_progress,
    write_sync_state,
)
from resilio.core.training_state_repository import (
    SPORT_SETTINGS_PATH,
    WELLNESS_ROOT,
    load_wellness,
    merge_wellness,
    write_sport_settings,
    write_wellness,
)
from resilio.core.workout_fulfillment.repository import (
    WORKOUT_FULFILLMENTS_PATH,
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.core.workout_publication.locking import coordinated_publication_plan_lock
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import ActivityDTO, AthleteDTO
from resilio.integrations.intervals_icu.training_state_mapper import (
    map_sport_settings,
    map_wellness,
)
from resilio.schemas.activity import ActivityStatus, CanonicalActivity
from resilio.schemas.config import Config
from resilio.schemas.sync import (
    ActivitySyncState,
    SyncPhase,
    SyncProgress,
    SyncReport,
)
from resilio.schemas.training_state import (
    SportSettingsSnapshot,
    WellnessDay,
)


@dataclass(frozen=True)
class SyncRunContext:
    state: ActivitySyncState
    reconcile_full: bool
    oldest: date
    newest: date
    run_id: str
    report: SyncReport
    run_root: Path
    staging_root: Path
    quarantine_path: Path


@dataclass(frozen=True)
class ProviderTrainingState:
    athlete: AthleteDTO
    sport_settings: SportSettingsSnapshot
    merged_wellness_by_date: dict[date, WellnessDay]


@dataclass(frozen=True)
class ActivityRetrieval:
    progress: SyncProgress
    listing: ActivityListing
    details: dict[str, ActivityDTO]


@dataclass(frozen=True)
class StagedSyncResult:
    records: list[CanonicalActivity]
    reconciliation: StagedReconciliationOutcome


def _archive_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.yaml")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _run_id(root: Path, oldest: date, newest: date, full: bool) -> str:
    material = (
        f"{_archive_digest(root)}\0{oldest.isoformat()}\0" f"{newest.isoformat()}\0{int(full)}"
    )
    return f"sync-{hashlib.sha256(material.encode()).hexdigest()[:16]}"


def _requires_full_reconciliation(
    *,
    today: date,
    state: ActivitySyncState,
    requested: bool,
    cadence_days: int,
) -> bool:
    if requested or state.last_successful_incremental_at_utc is None:
        return True
    if state.last_full_reconciliation_at_utc is None:
        return True
    elapsed = today - state.last_full_reconciliation_at_utc.date()
    return elapsed.days >= cadence_days


class ActivitySyncService:
    def __init__(
        self,
        repo: RepositoryIO,
        config: Config,
        client: IntervalsIcuClient,
    ):
        self.repo = repo
        self.config = config
        self.client = client
        self.repo_root = repo.repo_root
        self.archive_root = self.repo_root / config.settings.paths.activities_dir

    def run(
        self,
        *,
        today: date,
        full: bool = False,
        confirm_deletions: bool = False,
    ) -> SyncReport:
        lock_path = self.repo_root / ACTIVITY_MUTATION_LOCK_PATH
        with coordinated_publication_plan_lock(self.repo, "activity_sync"):
            with OperationLock(lock_path, "activity_sync"):
                return self._run(
                    today=today,
                    full=full,
                    confirm_deletions=confirm_deletions,
                )

    def _run(
        self,
        *,
        today: date,
        full: bool = False,
        confirm_deletions: bool = False,
    ) -> SyncReport:
        self._recover_prior_run()
        load_fulfillment_manifest(self.repo)
        context = self._prepare_run(today=today, full=full)
        provider_state = self._fetch_provider_training_state(context)
        retrieval = self._retrieve_activities(
            context,
            athlete_id=provider_state.athlete.id,
        )
        if context.report.partial:
            self._record_partial_retrieval(context, retrieval)
            context.report.phase = SyncPhase.PARTIAL
            return context.report
        staged = self._reconcile_staged_archive(
            context,
            retrieval,
            athlete_timezone=provider_state.athlete.timezone,
            confirm_deletions=confirm_deletions,
        )
        self._commit_run(
            context,
            provider_state,
            retrieval,
            staged,
        )
        clear_sync_progress(self.repo)
        context.report.phase = SyncPhase.PARTIAL if context.report.partial else SyncPhase.DONE
        return context.report

    def _recover_prior_run(self) -> None:
        prior_progress = read_sync_progress(self.repo)
        if prior_progress is None:
            return
        prior_run_root = self.repo_root / "data/state/sync-runs" / prior_progress.run_id
        if (prior_run_root / "commit.json").exists():
            recover_activity_mutation(
                active_archive=self.archive_root,
                run_root=prior_run_root,
                replace=os.replace,
            )
            clear_sync_progress(self.repo)
            return
        for stale in (
            prior_run_root / "archive",
            prior_run_root / "previous-wellness",
            prior_run_root / "previous-sync-state.json",
            prior_run_root / "previous-sport-settings.json",
            prior_run_root / "previous-workout-fulfillments.json",
            prior_run_root / "commit.json",
        ):
            remove_path(stale)
        clear_sync_progress(self.repo)

    def _prepare_run(self, *, today: date, full: bool) -> SyncRunContext:
        settings = self.config.settings.intervals_icu
        state = read_sync_state(self.repo)
        reconcile_full = _requires_full_reconciliation(
            today=today,
            state=state,
            requested=full,
            cadence_days=settings.full_reconciliation_days,
        )
        oldest = (
            settings.history_start_date
            if reconcile_full
            else today - timedelta(days=settings.incremental_overlap_days)
        )
        newest = today
        run_id = _run_id(self.archive_root, oldest, newest, reconcile_full)
        report = SyncReport(run_id=run_id, phase=SyncPhase.PREFLIGHT)
        run_root = self.repo_root / "data/state/sync-runs" / run_id
        staging_root = run_root / "archive"
        previous_root = run_root / "previous-archive"
        ActivityArchive(self.archive_root).load_all()
        if previous_root.exists():
            raise ActivitySyncError(
                f"Run {run_id} has an unresolved previous archive; inspect before retry"
            )
        return SyncRunContext(
            state=state,
            reconcile_full=reconcile_full,
            oldest=oldest,
            newest=newest,
            run_id=run_id,
            report=report,
            run_root=run_root,
            staging_root=staging_root,
            quarantine_path=run_root / "quarantine.json",
        )

    def _fetch_provider_training_state(
        self,
        context: SyncRunContext,
    ) -> ProviderTrainingState:
        athlete = self.client.get_athlete()
        self.client.get_connections(athlete.id)
        sport_settings = map_sport_settings(self.client.get_sport_settings(athlete.id))
        wellness_received = [
            map_wellness(item)
            for item in self.client.get_wellness(
                context.oldest,
                context.newest,
                athlete_id=athlete.id,
            )
        ]
        merged_wellness, wellness_days_changed = merge_wellness(
            load_wellness(self.repo),
            wellness_received,
            replace_window_start=context.oldest,
            replace_window_end=context.newest,
        )
        context.report.wellness_days_received = len(wellness_received)
        context.report.wellness_days_changed = wellness_days_changed
        context.report.sport_settings_fingerprint_sha256 = sport_settings.fingerprint_sha256
        return ProviderTrainingState(
            athlete=athlete,
            sport_settings=sport_settings,
            merged_wellness_by_date=merged_wellness,
        )

    def _retrieve_activities(
        self,
        context: SyncRunContext,
        *,
        athlete_id: str,
    ) -> ActivityRetrieval:
        settings = self.config.settings.intervals_icu
        windows = enumerate_windows(
            context.oldest,
            context.newest,
            settings.initial_window_days,
        )
        progress = SyncProgress(
            run_id=context.run_id,
            phase=SyncPhase.LISTING,
            oldest=context.oldest,
            newest=context.newest,
            windows_total=len(windows),
            updated_at_utc=datetime.now(timezone.utc),
        )
        write_sync_progress(self.repo, progress)
        listing = list_complete_activity_rows(
            client=self.client,
            repo=self.repo,
            athlete_id=athlete_id,
            oldest=context.oldest,
            newest=context.newest,
            settings=settings,
            progress=progress,
            report=context.report,
        )
        details: dict[str, ActivityDTO] = {}
        if not context.report.partial:
            progress.phase = SyncPhase.DETAIL
            write_sync_progress(self.repo, progress)
            details = fetch_activity_details(
                client=self.client,
                athlete_id=athlete_id,
                complete_rows_by_external_id=(listing.complete_rows_by_external_id),
                detail_batch_size=settings.detail_batch_size,
                report=context.report,
            )
        return ActivityRetrieval(
            progress=progress,
            listing=listing,
            details=details,
        )

    def _record_partial_retrieval(
        self,
        context: SyncRunContext,
        retrieval: ActivityRetrieval,
    ) -> None:
        """Persist that an attempted source window is not complete."""
        state = context.state
        record_sync_coverage(
            state,
            window_start=context.oldest,
            window_end=context.newest,
            current_exclusions=(retrieval.listing.source_coverage_exclusions()),
            partial=True,
            completed_at_utc=datetime.now(timezone.utc),
            full_reconciliation=False,
        )
        write_sync_state(self.repo, state)
        retrieval.progress.phase = SyncPhase.PARTIAL
        retrieval.progress.updated_at_utc = datetime.now(timezone.utc)
        write_sync_progress(self.repo, retrieval.progress)

    def _reconcile_staged_archive(
        self,
        context: SyncRunContext,
        retrieval: ActivityRetrieval,
        *,
        athlete_timezone: str | None,
        confirm_deletions: bool,
    ) -> StagedSyncResult:
        if context.staging_root.exists():
            shutil.rmtree(context.staging_root)
        shutil.copytree(self.archive_root, context.staging_root)
        staging = ActivityArchive(context.staging_root)
        staging_records = staging.load_all()
        progress = retrieval.progress
        progress.phase = SyncPhase.RECONCILING
        write_sync_progress(self.repo, progress)
        reconciler = StagedActivityReconciler(
            client=self.client,
            repo=self.repo,
            staging=staging,
            staging_records=staging_records,
            athlete_timezone=athlete_timezone,
            report=context.report,
        )
        reconciler.reconcile_details(retrieval.details)
        if context.reconcile_full:
            reconciler.confirm_external_deletions(
                listed_external_ids=retrieval.listing.listed_external_ids,
                oldest=context.oldest,
                newest=context.newest,
                confirm_deletions=confirm_deletions,
            )
        reconciler.write_quarantine_report(
            path=context.quarantine_path,
            run_id=context.run_id,
            hidden_row_count=retrieval.listing.hidden_row_count,
        )
        outcome = reconciler.outcome()
        staged_records = staging.load_all()
        context.report.activities_with_native_aerobic_load = sum(
            item.status == ActivityStatus.ACTIVE and item.aerobic_load is not None
            for item in staged_records
        )
        context.report.earliest_changed_date = outcome.earliest_changed_date
        return StagedSyncResult(
            records=staged_records,
            reconciliation=outcome,
        )

    def _commit_run(
        self,
        context: SyncRunContext,
        provider_state: ProviderTrainingState,
        retrieval: ActivityRetrieval,
        staged: StagedSyncResult,
    ) -> None:
        progress = retrieval.progress
        report = context.report
        progress.activities_created = report.activities_created
        progress.activities_updated = report.activities_updated
        progress.activities_linked = report.activities_linked
        progress.ambiguous_rows = report.ambiguous_rows
        progress.phase = SyncPhase.COMMITTING
        progress.updated_at_utc = datetime.now(timezone.utc)
        write_sync_progress(self.repo, progress)

        state = context.state
        state.resolved_athlete_id = provider_state.athlete.id
        settings = self.config.settings.intervals_icu
        state.incremental_overlap_days = settings.incremental_overlap_days
        state.external_to_local = {
            item.origin.intervals_icu_activity_id: item.local_activity_id
            for item in staged.records
            if item.origin.intervals_icu_activity_id
        }
        state.checkpoint_run_id = context.run_id
        state.sport_settings_fingerprint_sha256 = provider_state.sport_settings.fingerprint_sha256
        state.last_wellness_window_start = context.oldest
        state.last_wellness_window_end = context.newest
        current_exclusions = [
            *retrieval.listing.source_coverage_exclusions(),
            *staged.reconciliation.source_coverage_exclusions(),
        ]
        record_sync_coverage(
            state,
            window_start=context.oldest,
            window_end=context.newest,
            current_exclusions=current_exclusions,
            partial=report.partial,
            completed_at_utc=datetime.now(timezone.utc),
            full_reconciliation=context.reconcile_full,
        )

        state_path = self.repo.resolve_path("data/state/activity_sync.json")
        fulfillment_path = self.repo.resolve_path(WORKOUT_FULFILLMENTS_PATH)
        wellness_root = self.repo.resolve_path(WELLNESS_ROOT)
        sport_settings_path = self.repo.resolve_path(SPORT_SETTINGS_PATH)

        def apply_sidecars() -> None:
            write_wellness(
                self.repo,
                provider_state.merged_wellness_by_date,
            )
            write_sport_settings(self.repo, provider_state.sport_settings)
            save_fulfillment_manifest(
                self.repo,
                staged.reconciliation.fulfillment_manifest,
            )
            write_sync_state(self.repo, state)

        try:
            commit_activity_mutation(
                active_archive=self.archive_root,
                staged_archive=context.staging_root,
                run_root=context.run_root,
                sidecars=[
                    MutationSidecar(
                        wellness_root,
                        "previous-wellness",
                    ),
                    MutationSidecar(state_path, "previous-sync-state.json"),
                    MutationSidecar(
                        sport_settings_path,
                        "previous-sport-settings.json",
                    ),
                    MutationSidecar(
                        fulfillment_path,
                        "previous-workout-fulfillments.json",
                    ),
                ],
                apply_sidecars=apply_sidecars,
                replace=os.replace,
            )
        except Exception:
            progress.phase = SyncPhase.FAILED
            progress.updated_at_utc = datetime.now(timezone.utc)
            write_sync_progress(self.repo, progress)
            raise
