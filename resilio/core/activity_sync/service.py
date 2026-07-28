"""Checkpointed initial, incremental, and full completed-activity sync."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.completed_workouts import (
    reconcile_workout_completion,
)
from resilio.core.activity_sync.original_files import (
    probe_original_file_for_ambiguity,
)
from resilio.core.activity_sync.reconciliation import (
    merge_reviewed_activity,
    reconcile_activity,
)
from resilio.core.activity_sync.review import (
    build_mapping_quarantine_decision,
    load_override_ledger,
    load_quarantine_acknowledgement_ledger,
    reconciliation_review_fingerprint,
)
from resilio.core.activity_sync.windowing import (
    SaturatedActivityWindowError,
    enumerate_windows,
    fetch_complete_window,
)
from resilio.core.activity_transaction import (
    ACTIVITY_MUTATION_LOCK_PATH,
    MutationSidecar,
    commit_activity_mutation,
    recover_activity_mutation,
    remove_path,
    write_json,
)
from resilio.core.config import Config
from resilio.core.load import compute_load
from resilio.core.locking import OperationLock
from resilio.core.notes import analyze_activity
from resilio.core.profile import ProfileService
from resilio.core.repository import RepositoryIO
from resilio.core.rpe import select_best_rpe_estimate
from resilio.core.sync_state import (
    clear_sync_progress,
    read_sync_progress,
    read_sync_state,
    write_sync_progress,
    write_sync_state,
)
from resilio.core.workout_publication.completions import (
    WORKOUT_COMPLETIONS_PATH,
    load_completion_manifest,
    save_completion_manifest,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.integrations.intervals_icu.activity_mapper import map_activity
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import ActivityDTO, HiddenActivityDTO
from resilio.integrations.intervals_icu.errors import (
    IntervalsIcuError,
    IntervalsNotFoundError,
)
from resilio.schemas.activity import ActivityStatus, CanonicalActivity
from resilio.schemas.reconciliation import (
    ReconciliationAction,
    ReconciliationDecision,
)
from resilio.schemas.sync import (
    ActivitySyncState,
    CompleteSyncWindow,
    SyncPhase,
    SyncProgress,
    SyncReport,
)


class ActivitySyncError(RuntimeError):
    pass


def _archive_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.yaml")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _run_id(root: Path, oldest: date, newest: date, full: bool) -> str:
    material = (
        f"{_archive_digest(root)}\0{oldest.isoformat()}\0"
        f"{newest.isoformat()}\0{int(full)}"
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


def _external_id_sha256(external_id: str) -> str:
    return hashlib.sha256(external_id.encode()).hexdigest()


def _sanitized_decision(decision: ReconciliationDecision) -> dict:
    payload = decision.model_dump(mode="json", exclude={"activity"})
    external_id = payload.pop("external_activity_id")
    payload["external_activity_id_sha256"] = _external_id_sha256(external_id)
    return payload


def _load_for_activity(
    activity: CanonicalActivity,
    repo: RepositoryIO,
) -> CanonicalActivity:
    profile = ProfileService(repo).load_profile()
    if activity.perceived_exertion is not None:
        rpe = activity.perceived_exertion
    else:
        analysis = analyze_activity(activity, profile)
        rpe = select_best_rpe_estimate(analysis.rpe_estimates)
    load = compute_load(activity, rpe)
    return activity.model_copy(update={"calculated_load": load})


class ActivitySyncService:
    def __init__(
        self,
        repo: RepositoryIO,
        config: Config,
        client: IntervalsIcuClient,
        *,
        metrics_recompute: Optional[
            Callable[[RepositoryIO, Optional[date], Optional[date]], dict]
        ] = None,
    ):
        self.repo = repo
        self.config = config
        self.client = client
        self.metrics_recompute = metrics_recompute
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
        settings = self.config.settings.intervals_icu
        metrics_root = self.repo.resolve_path(
            self.config.settings.paths.metrics_dir
        )
        prior_progress = read_sync_progress(self.repo)
        if prior_progress is not None:
            prior_run_root = (
                self.repo_root
                / "data/state/sync-runs"
                / prior_progress.run_id
            )
            prior_previous = prior_run_root / "previous-archive"
            if prior_previous.exists():
                recover_activity_mutation(
                    active_archive=self.archive_root,
                    run_root=prior_run_root,
                    replace=os.replace,
                )
                clear_sync_progress(self.repo)
            else:
                # No active archive was displaced. Discard only incomplete
                # staging/sidecar artifacts and restart from the validated
                # active archive.
                for stale in (
                    prior_run_root / "archive",
                    prior_run_root / "previous-metrics",
                    prior_run_root / "previous-sync-state.json",
                    prior_run_root / "previous-workout-completions.json",
                    prior_run_root / "commit.json",
                ):
                    remove_path(stale)
                clear_sync_progress(self.repo)

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
        quarantine_path = run_root / "quarantine.json"

        active_archive = ActivityArchive(self.archive_root)
        active_archive.load_all()
        if previous_root.exists():
            raise ActivitySyncError(
                f"Run {run_id} has an unresolved previous archive; inspect before retry"
            )

        athlete = self.client.get_athlete()
        resolved_athlete_id = athlete.id
        self.client.get_connections(resolved_athlete_id)
        self.client.get_sport_settings(resolved_athlete_id)

        windows = enumerate_windows(oldest, newest, settings.initial_window_days)
        progress = SyncProgress(
            run_id=run_id,
            phase=SyncPhase.LISTING,
            oldest=oldest,
            newest=newest,
            windows_total=len(windows),
            updated_at_utc=datetime.now(timezone.utc),
        )
        write_sync_progress(self.repo, progress)

        complete_rows: dict[str, ActivityDTO] = {}
        listed_external_ids: set[str] = set()
        hidden_count = 0
        for window_start, window_end in windows:
            try:
                rows = fetch_complete_window(
                    self.client,
                    window_start,
                    window_end,
                    athlete_id=resolved_athlete_id,
                    limit=settings.list_limit,
                )
            except SaturatedActivityWindowError as exc:
                report.partial = True
                report.errors.append(str(exc))
                break
            for row in rows:
                listed_external_ids.add(row.id)
                if isinstance(row, HiddenActivityDTO):
                    hidden_count += 1
                else:
                    complete_rows[row.id] = row
            completed_at = datetime.now(timezone.utc)
            report.complete_windows.append(
                CompleteSyncWindow(
                    oldest=window_start,
                    newest=window_end,
                    activity_count=len(rows),
                    completed_at_utc=completed_at,
                )
            )
            progress.windows_complete += 1
            progress.activities_seen += len(rows)
            progress.hidden_rows = hidden_count
            progress.updated_at_utc = completed_at
            write_sync_progress(self.repo, progress)

        report.activities_seen = len(complete_rows) + hidden_count
        report.hidden_rows = hidden_count
        if report.partial:
            report.phase = SyncPhase.PARTIAL
            return report

        progress.phase = SyncPhase.DETAIL
        write_sync_progress(self.repo, progress)
        details: dict[str, ActivityDTO] = {}
        ids = sorted(complete_rows)
        for offset in range(0, len(ids), settings.detail_batch_size):
            batch_ids = ids[offset : offset + settings.detail_batch_size]
            batch = self.client.get_activities(
                batch_ids,
                athlete_id=resolved_athlete_id,
                intervals=True,
            )
            returned_ids = [activity.id for activity in batch]
            duplicate_ids = sorted(
                {
                    activity_id
                    for activity_id in returned_ids
                    if returned_ids.count(activity_id) > 1
                }
            )
            extra = sorted(set(returned_ids) - set(batch_ids))
            missing = sorted(set(batch_ids) - set(returned_ids))
            if duplicate_ids:
                report.partial = True
                report.quarantined_rows += len(duplicate_ids)
                report.errors.append(
                    f"Batch detail duplicated {len(duplicate_ids)} activity IDs"
                )
            if extra:
                report.partial = True
                report.quarantined_rows += len(extra)
                report.errors.append(
                    f"Batch detail returned {len(extra)} unrequested activity IDs"
                )
            if missing:
                report.partial = True
                report.quarantined_rows += len(missing)
                report.errors.append(
                    f"Batch detail omitted {len(missing)} validated activity IDs"
                )
            if not duplicate_ids and not extra and not missing:
                details.update({activity.id: activity for activity in batch})
        if report.partial:
            report.phase = SyncPhase.PARTIAL
            return report

        if staging_root.exists():
            shutil.rmtree(staging_root)
        shutil.copytree(self.archive_root, staging_root)
        staging = ActivityArchive(staging_root)
        staging_records = staging.load_all()
        override_ledger = load_override_ledger(self.repo)
        quarantine_acknowledgements = (
            load_quarantine_acknowledgement_ledger(self.repo)
        )
        publication_manifest = load_manifest(self.repo)
        completion_manifest = load_completion_manifest(self.repo)
        published_by_event_id = {
            publication.event_id: publication
            for publication in publication_manifest.workouts.values()
        }
        decisions: list[dict] = []
        completion_candidates: list[dict] = []
        external_deletion_candidates: list[str] = []
        earliest_changed: Optional[date] = None

        progress.phase = SyncPhase.RECONCILING
        write_sync_progress(self.repo, progress)
        for external_id in sorted(details):
            try:
                mapped = map_activity(
                    details[external_id],
                    default_timezone=athlete.timezone,
                )
            except Exception as exc:
                external_hash = _external_id_sha256(external_id)
                quarantine = build_mapping_quarantine_decision(
                    external_activity_id_sha256=external_hash,
                    error=exc,
                )
                acknowledgement = (
                    quarantine_acknowledgements.acknowledgements.get(
                        external_hash
                    )
                )
                report.quarantined_rows += 1
                if (
                    acknowledgement is not None
                    and acknowledgement.failure_fingerprint_sha256
                    == quarantine["failure_fingerprint_sha256"]
                    and quarantine["acknowledgeable"]
                ):
                    report.acknowledged_quarantined_rows += 1
                else:
                    report.partial = True
                decisions.append(
                    quarantine
                )
                continue
            decision = reconcile_activity(mapped, staging_records)
            if decision.action == ReconciliationAction.AMBIGUOUS:
                original_file_probe = probe_original_file_for_ambiguity(
                    client=self.client,
                    activity=mapped,
                    existing_records=staging_records,
                    decision=decision,
                )
                mapped = original_file_probe.activity
                decision = original_file_probe.decision
            if decision.action == ReconciliationAction.AMBIGUOUS:
                external_hash = _external_id_sha256(external_id)
                sanitized = _sanitized_decision(decision)
                exclusion = override_ledger.exclusions.get(external_hash)
                if exclusion is not None:
                    candidate = next(
                        (
                            item
                            for item in staging_records
                            if item.local_activity_id
                            == exclusion.local_activity_id
                        ),
                        None,
                    )
                    existing_external_id = (
                        candidate.origin.intervals_icu_activity_id
                        if candidate is not None
                        else None
                    )
                    exclusion_is_current = (
                        exclusion.local_activity_id
                        in decision.candidate_local_ids
                        and exclusion.review_fingerprint_sha256
                        == reconciliation_review_fingerprint(sanitized)
                        and existing_external_id is not None
                        and _external_id_sha256(existing_external_id)
                        != external_hash
                    )
                    if exclusion_is_current:
                        report.excluded_duplicate_rows += 1
                        decisions.append(
                            {
                                **sanitized,
                                "action": "excluded_duplicate_recording",
                                "review_fingerprint_sha256": (
                                    exclusion.review_fingerprint_sha256
                                ),
                            }
                        )
                        continue
                override = override_ledger.overrides.get(external_hash)
                if (
                    override is not None
                    and override.local_activity_id
                    in decision.candidate_local_ids
                ):
                    candidate = next(
                        item
                        for item in staging_records
                        if item.local_activity_id
                        == override.local_activity_id
                    )
                    decision = ReconciliationDecision(
                        action=ReconciliationAction.LINK,
                        rule="approved_review_override",
                        external_activity_id=external_id,
                        local_activity_id=candidate.local_activity_id,
                        activity=merge_reviewed_activity(
                            candidate,
                            mapped,
                        ),
                    )
                elif override is not None:
                    report.quarantined_rows += 1
                    report.partial = True
                    decisions.append(
                        {
                            "action": "quarantine",
                            "rule": "stale_review_override",
                            "external_activity_id_sha256": external_hash,
                            "error_type": "ReconciliationReviewError",
                        }
                    )
                    continue
            if decision.action == ReconciliationAction.AMBIGUOUS:
                report.ambiguous_rows += 1
                report.partial = True
                decisions.append(_sanitized_decision(decision))
                continue
            if decision.activity is None:
                raise ActivitySyncError("Reconciliation produced no activity")
            if decision.rule == "linked_fingerprint_unchanged":
                report.activities_unchanged += 1
                final_activity = decision.activity
            else:
                try:
                    if (
                        decision.activity.origin.kind == "historical_import"
                        and decision.activity.calculated_load is not None
                    ):
                        loaded = decision.activity
                    else:
                        loaded = _load_for_activity(
                            decision.activity,
                            self.repo,
                        )
                except Exception as exc:
                    report.quarantined_rows += 1
                    report.partial = True
                    decisions.append(
                        {
                            "action": "quarantine",
                            "rule": "load_calculation_failed",
                            "external_activity_id_sha256": (
                                _external_id_sha256(external_id)
                            ),
                            "error_type": type(exc).__name__,
                        }
                    )
                    continue
                staging.write(loaded)
                staging_records = [
                    item
                    for item in staging_records
                    if item.local_activity_id != loaded.local_activity_id
                ]
                staging_records.append(loaded)
                earliest_changed = (
                    loaded.date
                    if earliest_changed is None
                    else min(earliest_changed, loaded.date)
                )
                if decision.action == ReconciliationAction.CREATE:
                    report.activities_created += 1
                elif decision.action == ReconciliationAction.LINK:
                    report.activities_linked += 1
                else:
                    report.activities_updated += 1
                final_activity = loaded

            completion = reconcile_workout_completion(
                activity=final_activity,
                paired_event_id=details[external_id].paired_event_id,
                publications_by_event_id=published_by_event_id,
                publications=publication_manifest.workouts.values(),
                existing_match=completion_manifest.matches.get(
                    final_activity.local_activity_id
                ),
                matched_at_utc=datetime.now(timezone.utc),
            )
            if completion.conflict is not None:
                report.quarantined_rows += 1
                report.partial = True
                decisions.append(
                    {
                        "action": "quarantine",
                        "external_activity_id_sha256": (
                            _external_id_sha256(external_id)
                        ),
                        **completion.conflict,
                    }
                )
            elif completion.match is not None:
                completion_manifest.matches[
                    final_activity.local_activity_id
                ] = completion.match
                report.completion_matches_linked += 1
            elif completion.candidate is not None:
                completion_candidates.append(completion.candidate)
                report.completion_candidates_reported += 1

        if reconcile_full:
            for current in list(staging_records):
                external_id = current.origin.intervals_icu_activity_id
                if not external_id or external_id in listed_external_ids:
                    continue
                if not (oldest <= current.date <= newest):
                    continue
                try:
                    self.client.get_activity(external_id)
                except IntervalsNotFoundError:
                    if confirm_deletions:
                        tombstone = current.model_copy(
                            update={
                                "status": ActivityStatus.EXTERNAL_DELETED,
                                "calculated_load": None,
                            }
                        )
                        staging.write(tombstone)
                        report.activities_tombstoned += 1
                        earliest_changed = (
                            current.date
                            if earliest_changed is None
                            else min(earliest_changed, current.date)
                        )
                    else:
                        external_deletion_candidates.append(
                            current.local_activity_id
                        )
                        report.partial = True
                        report.errors.append(
                            "A missing external activity requires deletion review"
                        )
                except IntervalsIcuError as exc:
                    report.partial = True
                    report.errors.append(
                        "External deletion confirmation failed safely: "
                        f"{exc.error_type}"
                    )
                else:
                    report.partial = True
                    report.errors.append(
                        "An activity omitted from a complete list still exists "
                        "by detail lookup"
                    )

        write_json(
            quarantine_path,
            {
                "schema_version": 1,
                "run_id": run_id,
                "ambiguous_decisions": decisions,
                "completion_candidates": completion_candidates,
                "external_deletion_candidates": sorted(
                    external_deletion_candidates
                ),
                "hidden_rows": hidden_count,
            },
        )
        staged_records = staging.load_all()
        report.earliest_changed_date = earliest_changed

        progress.activities_created = report.activities_created
        progress.activities_updated = report.activities_updated
        progress.activities_linked = report.activities_linked
        progress.ambiguous_rows = report.ambiguous_rows
        progress.phase = SyncPhase.COMMITTING
        progress.updated_at_utc = datetime.now(timezone.utc)
        write_sync_progress(self.repo, progress)

        state.resolved_athlete_id = resolved_athlete_id
        state.incremental_overlap_days = settings.incremental_overlap_days
        state.external_to_local = {
            item.origin.intervals_icu_activity_id: item.local_activity_id
            for item in staged_records
            if item.origin.intervals_icu_activity_id
        }
        state.checkpoint_run_id = run_id
        if not report.partial:
            completed_at = datetime.now(timezone.utc)
            state.last_successful_incremental_at_utc = completed_at
            state.last_complete_window_start = oldest
            state.last_complete_window_end = newest
            if reconcile_full:
                state.last_full_reconciliation_at_utc = completed_at

        state_path = self.repo.resolve_path("data/state/activity_sync.json")
        completion_path = self.repo.resolve_path(WORKOUT_COMPLETIONS_PATH)

        def apply_sidecars() -> None:
            if earliest_changed is not None and self.metrics_recompute is not None:
                progress.phase = SyncPhase.METRICS
                write_sync_progress(self.repo, progress)
                self.metrics_recompute(self.repo, earliest_changed, today)
            save_completion_manifest(self.repo, completion_manifest)
            write_sync_state(self.repo, state)

        try:
            commit_activity_mutation(
                active_archive=self.archive_root,
                staged_archive=staging_root,
                run_root=run_root,
                sidecars=[
                    MutationSidecar(metrics_root, "previous-metrics"),
                    MutationSidecar(state_path, "previous-sync-state.json"),
                    MutationSidecar(
                        completion_path,
                        "previous-workout-completions.json",
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
        clear_sync_progress(self.repo)
        report.phase = SyncPhase.PARTIAL if report.partial else SyncPhase.DONE
        return report
