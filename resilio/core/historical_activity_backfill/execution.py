"""Checkpointed batch commit, recovery, receipt, and rollback helpers."""

from __future__ import annotations

import os
import shutil
from datetime import date, datetime
from typing import Optional

import yaml

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_transaction import (
    MutationSidecar,
    commit_activity_mutation,
    recover_activity_mutation,
    remove_path,
)
from resilio.core.historical_activity_backfill.errors import (
    HistoricalActivityBackfillError,
)
from resilio.core.historical_activity_backfill.inventory import (
    archive_source_digest,
    tree_digest,
    visible_composite_match,
)
from resilio.core.historical_activity_backfill.rendering import (
    OWNERSHIP_PREFIX,
    RenderedHistoricalActivity,
    assert_remote_matches,
    readback_fingerprint,
    render_manual_activity,
)
from resilio.core.historical_activity_backfill.repository import (
    load_ledger,
    original_activity_path,
    run_root,
    save_ledger,
    save_run_envelope,
    verify_backup,
)
from resilio.core.sync_state import read_sync_state, write_sync_state
from resilio.integrations.intervals_icu.dto import ActivityDTO, HiddenActivityDTO
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.activity import ActivityAudit, ActivityOrigin, CanonicalActivity
from resilio.schemas.historical_backfill import (
    BackfillDecision,
    BackfillDecisionAction,
    BackfillPhase,
    BackfillPlan,
    BackfillRunEnvelope,
    HistoricalActivityPublication,
    PublicationStatus,
)


class BackfillExecutionMixin:
    """Implementation helpers shared by apply, resume, canary, and rollback."""

    def _verify_rollback_preflight(self, plan: BackfillPlan) -> str:
        verify_backup(self.repo_root, plan)
        records = {
            item.local_activity_id: item
            for item in ActivityArchive(self.archive_root).load_all()
        }
        for decision in plan.decisions:
            activity = records.get(decision.local_activity_id)
            if activity is None:
                raise HistoricalActivityBackfillError(
                    "A planned historical source is missing before rollback"
                )
            rendered = render_manual_activity(activity)
            if (
                rendered.source_fingerprint_sha256
                != decision.source_fingerprint_sha256
                or rendered.payload_fingerprint_sha256
                != decision.payload_fingerprint_sha256
            ):
                raise HistoricalActivityBackfillError(
                    "Historical source drift blocks exact rollback"
                )
        athlete = self._require_client().get_athlete()
        if athlete.timezone != plan.timezone:
            raise HistoricalActivityBackfillError(
                "Athlete timezone drift blocks historical rollback"
            )
        return athlete.id

    def _apply_batch(
        self,
        plan: BackfillPlan,
        decisions: list[BackfillDecision],
        *,
        athlete_id: str,
        batch_number: int,
    ) -> int:
        ledger = load_ledger(self.repo)
        remaining: list[
            tuple[BackfillDecision, CanonicalActivity, RenderedHistoricalActivity]
        ] = []
        for decision in decisions:
            activity, rendered = self._activity_and_rendered(plan, decision)
            receipt = ledger.publications.get(decision.local_activity_id)
            if receipt is not None and receipt.status == PublicationStatus.VERIFIED:
                if (
                    activity.origin.intervals_icu_activity_id
                    != receipt.destination_activity_id
                    or activity.origin.upstream_external_id
                    != receipt.ownership_external_id
                ):
                    raise HistoricalActivityBackfillError(
                        "Verified ledger receipt is not linked to the canonical activity"
                    )
                continue
            remaining.append((decision, activity, rendered))
        if not remaining:
            return 0

        oldest = min(activity.date for _decision, activity, _rendered in remaining)
        newest = max(activity.date for _decision, activity, _rendered in remaining)
        rows = self._fetch_inventory(oldest, newest, athlete_id=athlete_id)
        resolved: list[tuple[BackfillDecision, ActivityDTO]] = []
        absent: list[
            tuple[BackfillDecision, CanonicalActivity, RenderedHistoricalActivity]
        ] = []
        for decision, activity, rendered in remaining:
            owned = self._owned_rows(rows, rendered.payload.external_id)
            if len(owned) > 1:
                raise HistoricalActivityBackfillError(
                    "Multiple owned activities block batch recovery"
                )
            if len(owned) == 1:
                remote = self._require_client().get_activity(
                    owned[0].id,
                    intervals=False,
                )
                assert_remote_matches(remote, rendered.payload)
                resolved.append((decision, remote))
            else:
                self._resolve_or_submit_preflight(activity, rendered, rows)
                absent.append((decision, activity, rendered))
            self._write_pending(plan, decision, rendered, "apply")

        if absent:
            posted = self._submit_exact(
                [rendered for _decision, _activity, rendered in absent],
                athlete_id=athlete_id,
            )
            posted_by_external = {item.external_id: item for item in posted}
            resolved.extend(
                (
                    decision,
                    posted_by_external[rendered.payload.external_id],
                )
                for decision, _activity, rendered in absent
            )
        resolved.sort(key=lambda item: item[0].local_activity_id)
        self._commit_links(
            plan,
            resolved,
            transaction_name=f"apply-{batch_number:03d}",
        )
        self._finalize_receipts(plan, resolved)
        return len(resolved)

    def _resolve_or_submit_preflight(
        self,
        activity: CanonicalActivity,
        rendered: RenderedHistoricalActivity,
        rows: list[ActivityDTO | HiddenActivityDTO],
    ) -> None:
        for row in rows:
            if isinstance(row, ActivityDTO) and visible_composite_match(row, rendered):
                raise HistoricalActivityBackfillError(
                    "Visible unowned collision appeared before batch mutation"
                )
            if isinstance(row, HiddenActivityDTO):
                hidden_wall = datetime.fromisoformat(row.start_date_local).replace(
                    tzinfo=None
                )
                expected_wall = rendered.payload.start_date_local.replace(tzinfo=None)
                if (
                    hidden_wall.date() == activity.date
                    and (
                        rendered.time_mode == "local_noon"
                        or abs((hidden_wall - expected_wall).total_seconds()) <= 120
                    )
                ):
                    raise HistoricalActivityBackfillError(
                        "Hidden collision appeared before batch mutation"
                    )

    def _commit_links(
        self,
        plan: BackfillPlan,
        resolved: list[tuple[BackfillDecision, ActivityDTO]],
        *,
        transaction_name: str,
    ) -> None:
        if not resolved:
            return
        transaction_root = (
            run_root(self.repo_root, plan.run_id)
            / "transactions"
            / transaction_name
        )
        if (transaction_root / "committed.json").exists():
            return
        staging_root = transaction_root / "archive"
        remove_path(staging_root)
        transaction_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.archive_root, staging_root)
        staging = ActivityArchive(staging_root)
        staged_records = {
            item.local_activity_id: item for item in staging.load_all()
        }
        state = read_sync_state(self.repo)
        verified_at = self.clock()
        for decision, remote in resolved:
            current = staged_records[decision.local_activity_id]
            rendered = render_manual_activity(current)
            assert_remote_matches(remote, rendered.payload)
            existing_mapping = state.external_to_local.get(remote.id)
            if existing_mapping not in (None, decision.local_activity_id):
                raise HistoricalActivityBackfillError(
                    "Destination activity ID is already indexed to another local record"
                )
            origin = ActivityOrigin(
                kind=current.origin.kind,
                recording_provider=current.origin.recording_provider,
                intervals_icu_activity_id=remote.id,
                upstream_external_id=rendered.payload.external_id,
                original_file_sha256=current.origin.original_file_sha256,
            )
            audit = ActivityAudit(
                imported_at_utc=current.audit.imported_at_utc,
                external_created_at_utc=remote.created or verified_at,
                external_sync_at_utc=verified_at,
                external_fingerprint_sha256=readback_fingerprint(remote),
            )
            linked = current.model_copy(update={"origin": origin, "audit": audit})
            staging.write(linked)
            state.external_to_local[remote.id] = decision.local_activity_id

        commit_activity_mutation(
            active_archive=self.archive_root,
            staged_archive=staging_root,
            run_root=transaction_root,
            sidecars=[
                MutationSidecar(
                    self.sync_state_path,
                    "previous-sync-state.json",
                )
            ],
            apply_sidecars=lambda: write_sync_state(self.repo, state),
            replace=os.replace,
        )

    def _finalize_receipts(
        self,
        plan: BackfillPlan,
        resolved: list[tuple[BackfillDecision, ActivityDTO]],
    ) -> None:
        ledger = load_ledger(self.repo)
        verified_at = self.clock()
        for decision, remote in resolved:
            _activity, rendered = self._activity_and_rendered(plan, decision)
            existing = ledger.publications.get(decision.local_activity_id)
            receipt = HistoricalActivityPublication(
                local_activity_id=decision.local_activity_id,
                status=PublicationStatus.VERIFIED,
                destination_activity_id=remote.id,
                ownership_external_id=rendered.payload.external_id,
                local_date=decision.local_date,
                plan_digest_sha256=plan.plan_digest_sha256,
                source_fingerprint_sha256=decision.source_fingerprint_sha256,
                payload_fingerprint_sha256=decision.payload_fingerprint_sha256,
                readback_fingerprint_sha256=readback_fingerprint(remote),
                published_at_utc=(
                    existing.published_at_utc
                    if existing is not None
                    else remote.created or verified_at
                ),
                verified_at_utc=verified_at,
            )
            if existing is not None and (
                existing.destination_activity_id != receipt.destination_activity_id
                or existing.ownership_external_id != receipt.ownership_external_id
            ):
                raise HistoricalActivityBackfillError(
                    "Publication receipt identity changed during finalization"
                )
            ledger.publications[decision.local_activity_id] = receipt
            ledger.pending.pop(decision.local_activity_id, None)
        save_ledger(self.repo, ledger)

    def _cleanup_failed_canary(
        self,
        local_date: date,
        rendered: RenderedHistoricalActivity,
        *,
        athlete_id: str,
    ) -> None:
        rows = self._fetch_inventory(local_date, local_date, athlete_id=athlete_id)
        owned = self._owned_rows(rows, rendered.payload.external_id)
        for row in owned:
            remote = self._require_client().get_activity(row.id, intervals=False)
            if (
                remote.id != row.id
                or remote.external_id != rendered.payload.external_id
                or not remote.external_id.startswith(OWNERSHIP_PREFIX)
            ):
                raise HistoricalActivityBackfillError(
                    "Canary cleanup refused an activity without exact namespace proof"
                )
            self._require_client().delete_activity(remote.id)
            try:
                self._require_client().get_activity(remote.id, intervals=False)
            except IntervalsNotFoundError:
                continue
            raise HistoricalActivityBackfillError(
                "Canary cleanup deletion could not be verified"
            )
        remaining = self._owned_rows(
            self._fetch_inventory(local_date, local_date, athlete_id=athlete_id),
            rendered.payload.external_id,
        )
        if remaining:
            raise HistoricalActivityBackfillError(
                "Canary cleanup could not prove namespace absence"
            )

    def _restore_original(
        self,
        plan: BackfillPlan,
        receipt: HistoricalActivityPublication,
        *,
        transaction_name: str,
    ) -> None:
        source = original_activity_path(
            self.repo_root,
            plan,
            receipt.local_activity_id,
            receipt.local_date,
        )
        if not source.is_file():
            raise HistoricalActivityBackfillError(
                "Hash-verified backup lacks the original canonical activity"
            )
        original = CanonicalActivity.model_validate(yaml.safe_load(source.read_text()))
        decision = self._decision(plan, receipt.local_activity_id)
        if render_manual_activity(original).source_fingerprint_sha256 != (
            decision.source_fingerprint_sha256
        ):
            raise HistoricalActivityBackfillError(
                "Backed-up canonical activity does not match the immutable source"
            )
        transaction_root = (
            run_root(self.repo_root, plan.run_id)
            / "transactions"
            / transaction_name
        )
        if (transaction_root / "committed.json").exists():
            return
        staging_root = transaction_root / "archive"
        remove_path(staging_root)
        transaction_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.archive_root, staging_root)
        ActivityArchive(staging_root).write(original)
        state = read_sync_state(self.repo)
        mapped = state.external_to_local.get(receipt.destination_activity_id)
        if mapped not in (None, receipt.local_activity_id):
            raise HistoricalActivityBackfillError(
                "Rollback refused a sync index owned by another local activity"
            )
        state.external_to_local.pop(receipt.destination_activity_id, None)

        commit_activity_mutation(
            active_archive=self.archive_root,
            staged_archive=staging_root,
            run_root=transaction_root,
            sidecars=[
                MutationSidecar(
                    self.sync_state_path,
                    "previous-sync-state.json",
                )
            ],
            apply_sidecars=lambda: write_sync_state(self.repo, state),
            replace=os.replace,
        )

    def _recover_transactions(self, plan: BackfillPlan) -> None:
        root = run_root(self.repo_root, plan.run_id) / "transactions"
        if not root.is_dir():
            return
        recovered = False
        for transaction_root in sorted(path for path in root.iterdir() if path.is_dir()):
            recovered = (
                recover_activity_mutation(
                    active_archive=self.archive_root,
                    run_root=transaction_root,
                    replace=os.replace,
                )
                or recovered
            )
        if recovered:
            ActivityArchive(self.archive_root).load_all()

    def _verify_local_acceptance(
        self,
        plan: BackfillPlan,
        *,
        rolled_back: bool = False,
    ) -> None:
        records = ActivityArchive(self.archive_root).load_all()
        if len(records) != plan.coverage.archive_activity_count:
            raise HistoricalActivityBackfillError(
                "Canonical archive activity count changed during the backfill"
            )
        if archive_source_digest(records) != plan.archive_source_digest_sha256:
            raise HistoricalActivityBackfillError(
                "Historical source facts changed during the backfill"
            )
        if tree_digest(self.metrics_root) != plan.metrics_tree_digest_sha256:
            raise HistoricalActivityBackfillError(
                "Metrics changed during the historical backfill"
            )
        state = read_sync_state(self.repo)
        decisions = {
            item.local_activity_id: item
            for item in plan.decisions
            if item.action
            in {
                BackfillDecisionAction.PUBLISH,
                BackfillDecisionAction.ADOPT_OWNED,
            }
        }
        linked = [
            item
            for item in records
            if (
                item.local_activity_id in decisions
                and item.origin.intervals_icu_activity_id
            )
        ]
        expected = 0 if rolled_back else plan.coverage.publishable
        if len(linked) != expected:
            raise HistoricalActivityBackfillError(
                f"Expected {expected} canonical external links, found {len(linked)}"
            )
        total_external_links = sum(
            bool(activity.origin.intervals_icu_activity_id)
            for activity in records
        )
        expected_total = plan.coverage.initial_external_links + expected
        if total_external_links != expected_total:
            raise HistoricalActivityBackfillError(
                f"Expected {expected_total} total external links, "
                f"found {total_external_links}"
            )
        if not rolled_back:
            for activity in linked:
                if (
                    state.external_to_local.get(
                        activity.origin.intervals_icu_activity_id
                    )
                    != activity.local_activity_id
                ):
                    raise HistoricalActivityBackfillError(
                        "Canonical link and sync index are inconsistent"
                    )

    def _verify_rollback_acceptance(
        self,
        plan: BackfillPlan,
        *,
        metrics_digest_before: str,
        archive_count_before: int,
        external_links_before: int,
        restored: int,
    ) -> None:
        records = ActivityArchive(self.archive_root).load_all()
        if len(records) != archive_count_before:
            raise HistoricalActivityBackfillError(
                "Rollback changed the canonical archive activity count"
            )
        if tree_digest(self.metrics_root) != metrics_digest_before:
            raise HistoricalActivityBackfillError(
                "Rollback changed the metrics tree"
            )
        links_after = sum(
            bool(activity.origin.intervals_icu_activity_id)
            for activity in records
        )
        if links_after != external_links_before - restored:
            raise HistoricalActivityBackfillError(
                "Rollback external-link count does not reconcile"
            )
        by_local = {item.local_activity_id: item for item in records}
        ledger = load_ledger(self.repo)
        for decision in plan.decisions:
            publication = ledger.publications.get(decision.local_activity_id)
            if (
                publication is not None
                and publication.status == PublicationStatus.ROLLED_BACK
            ):
                activity = by_local[decision.local_activity_id]
                rendered = render_manual_activity(activity)
                if (
                    rendered.source_fingerprint_sha256
                    != decision.source_fingerprint_sha256
                ):
                    raise HistoricalActivityBackfillError(
                        "Rollback did not restore the exact historical source"
                    )

    def _save_envelope(
        self,
        plan: BackfillPlan,
        phase: BackfillPhase,
        *,
        error: Optional[str] = None,
    ) -> None:
        ledger = load_ledger(self.repo)
        relevant = [
            item
            for item in ledger.publications.values()
            if item.plan_digest_sha256 == plan.plan_digest_sha256
        ]
        save_run_envelope(
            self.repo_root,
            BackfillRunEnvelope(
                run_id=plan.run_id,
                phase=phase,
                plan_digest_sha256=plan.plan_digest_sha256,
                updated_at_utc=self.clock(),
                completed_publications=sum(
                    item.status == PublicationStatus.VERIFIED for item in relevant
                ),
                pending_publications=len(ledger.pending),
                rolled_back_publications=sum(
                    item.status == PublicationStatus.ROLLED_BACK
                    for item in relevant
                ),
                last_error=error,
            ),
        )
