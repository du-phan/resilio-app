"""Ownership-safe remote-only RPE defaults for completed backfill receipts."""

from __future__ import annotations

from datetime import datetime

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_transaction import ACTIVITY_MUTATION_LOCK_PATH
from resilio.core.historical_activity_backfill.errors import (
    HistoricalActivityBackfillError,
)
from resilio.core.historical_activity_backfill.inventory import tree_digest
from resilio.core.historical_activity_backfill.rendering import (
    OWNERSHIP_PREFIX,
    RenderedHistoricalActivity,
    assert_remote_matches,
    readback_fingerprint,
    render_manual_activity,
    with_remote_athlete_rpe,
)
from resilio.core.historical_activity_backfill.repository import (
    load_approval,
    load_canary_proof,
    load_ledger,
    load_plan,
    save_ledger,
    verify_backup,
)
from resilio.core.locking import OperationLock
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.historical_backfill import (
    ApprovalStage,
    BackfillDecision,
    BackfillPlan,
    HistoricalActivityPublication,
    PendingPublicationIntent,
    PublicationStatus,
)

RPE_REPAIR_BATCH_SIZE = 25


class RpeRepairMixin:
    """Add an approved RPE only where an exact owned upload has none."""

    def _base_rendered(
        self,
        plan: BackfillPlan,
        decision: BackfillDecision,
        activity: CanonicalActivity,
    ) -> RenderedHistoricalActivity:
        rendered = render_manual_activity(activity)
        if (
            rendered.source_fingerprint_sha256
            != decision.source_fingerprint_sha256
            or rendered.payload_fingerprint_sha256
            != decision.payload_fingerprint_sha256
        ):
            raise HistoricalActivityBackfillError(
                "Local source or rendered payload drifted from the immutable plan"
            )
        return rendered

    def _receipt_rendered(
        self,
        plan: BackfillPlan,
        decision: BackfillDecision,
        receipt: HistoricalActivityPublication,
        activity: CanonicalActivity,
    ) -> RenderedHistoricalActivity:
        rendered = self._base_rendered(plan, decision, activity)
        override = receipt.remote_athlete_rpe_override
        if override is not None:
            rendered = with_remote_athlete_rpe(rendered, override)
        if (
            rendered.payload_fingerprint_sha256
            != receipt.payload_fingerprint_sha256
        ):
            raise HistoricalActivityBackfillError(
                "Remote payload receipt drift blocks exact mutation"
            )
        return rendered

    def set_default_rpe(
        self,
        *,
        plan_digest_sha256: str,
        canary_digest_sha256: str,
        value: int,
    ) -> dict:
        if not 1 <= value <= 10:
            raise HistoricalActivityBackfillError("Athlete RPE must be between 1 and 10")
        plan = load_plan(self.repo_root, plan_digest_sha256)
        proof = load_canary_proof(self.repo_root, plan)
        approval = load_approval(self.repo_root, plan, ApprovalStage.RPE_DEFAULT)
        if (
            proof.canary_digest_sha256 != canary_digest_sha256
            or approval.canary_digest_sha256 != canary_digest_sha256
        ):
            raise HistoricalActivityBackfillError(
                "RPE-default repair is not bound to the approved canary proof"
            )

        lock_path = self.repo_root / ACTIVITY_MUTATION_LOCK_PATH
        with OperationLock(lock_path, "historical_activity_backfill_rpe_default"):
            self._recover_transactions(plan)
            verify_backup(self.repo_root, plan)
            archive_digest_before = tree_digest(self.archive_root)
            metrics_digest_before = tree_digest(self.metrics_root)
            sync_state_before = self.sync_state_path.read_bytes()

            athlete = self._require_client().get_athlete()
            if athlete.timezone != plan.timezone:
                raise HistoricalActivityBackfillError(
                    "Athlete timezone drift blocks the RPE-default repair"
                )
            ledger = load_ledger(self.repo)
            receipts = sorted(
                (
                    item
                    for item in ledger.publications.values()
                    if item.plan_digest_sha256 == plan.plan_digest_sha256
                    and item.status == PublicationStatus.VERIFIED
                ),
                key=lambda item: (item.local_date, item.local_activity_id),
            )
            if len(receipts) != plan.coverage.publishable:
                raise HistoricalActivityBackfillError(
                    "RPE-default repair requires every publication receipt"
                )
            if any(
                intent.stage != "rpe_default"
                for intent in ledger.pending.values()
            ):
                raise HistoricalActivityBackfillError(
                    "Another publication mutation is pending"
                )

            entries = []
            expected_external_ids: set[str] = set()
            records = {
                item.local_activity_id: item
                for item in ActivityArchive(self.archive_root).load_all()
            }
            for receipt in receipts:
                decision = self._decision(plan, receipt.local_activity_id)
                activity = records.get(receipt.local_activity_id)
                if activity is None:
                    raise HistoricalActivityBackfillError(
                        "A planned source is missing before the RPE-default repair"
                    )
                base = self._base_rendered(plan, decision, activity)
                if (
                    activity.origin.intervals_icu_activity_id
                    != receipt.destination_activity_id
                    or activity.origin.upstream_external_id
                    != receipt.ownership_external_id
                    or receipt.ownership_external_id != base.payload.external_id
                ):
                    raise HistoricalActivityBackfillError(
                        "RPE-default repair found inconsistent local ownership"
                    )
                expected_external_ids.add(receipt.ownership_external_id)
                entries.append((decision, base, receipt))

            rows = self._fetch_inventory(
                plan.inventory_oldest,
                max(plan.inventory_newest, self.clock().date()),
                athlete_id=athlete.id,
            )
            owned_rows = [
                row
                for row in rows
                if isinstance(row, ActivityDTO)
                and row.external_id
                and row.external_id.startswith(OWNERSHIP_PREFIX)
            ]
            owned_external_ids = [
                row.external_id for row in owned_rows if row.external_id
            ]
            if (
                len(owned_external_ids) != len(set(owned_external_ids))
                or set(owned_external_ids) != expected_external_ids
            ):
                raise HistoricalActivityBackfillError(
                    "Remote ownership inventory drift blocks the RPE-default repair"
                )
            row_by_external = {
                row.external_id: row for row in owned_rows if row.external_id
            }

            targets: list[
                tuple[BackfillDecision, RenderedHistoricalActivity]
            ] = []
            recovered: list[
                tuple[
                    BackfillDecision,
                    ActivityDTO,
                    RenderedHistoricalActivity,
                    int,
                ]
            ] = []
            preserved_existing = 0
            already_defaulted = 0
            for decision, base, receipt in entries:
                row = row_by_external[receipt.ownership_external_id]
                if row.id != receipt.destination_activity_id:
                    raise HistoricalActivityBackfillError(
                        "Destination identity drift blocks the RPE-default repair"
                    )
                current = (
                    with_remote_athlete_rpe(
                        base,
                        receipt.remote_athlete_rpe_override,
                    )
                    if receipt.remote_athlete_rpe_override is not None
                    else base
                )
                if receipt.remote_athlete_rpe_override is not None:
                    if receipt.remote_athlete_rpe_override != value:
                        raise HistoricalActivityBackfillError(
                            "A different RPE override already owns this receipt"
                        )
                    self._assert_receipt_remote(receipt, row, current)
                    already_defaulted += 1
                    continue
                if base.payload.icu_rpe is not None:
                    self._assert_receipt_remote(receipt, row, base)
                    preserved_existing += 1
                    continue

                desired = with_remote_athlete_rpe(base, value)
                pending = ledger.pending.get(decision.local_activity_id)
                remote = self._require_client().get_activity(
                    receipt.destination_activity_id,
                    intervals=False,
                )
                if remote.icu_rpe is None:
                    self._assert_receipt_remote(receipt, remote, base)
                    if pending is not None:
                        self._assert_rpe_pending(plan, pending, desired)
                    targets.append((decision, desired))
                    continue
                if remote.icu_rpe == value and pending is not None:
                    self._assert_rpe_pending(plan, pending, desired)
                    assert_remote_matches(remote, desired.payload)
                    recovered.append((decision, remote, desired, value))
                    continue
                raise HistoricalActivityBackfillError(
                    "Remote RPE drift blocks the default-only repair"
                )

            if recovered:
                self._finalize_rpe_receipts(plan, recovered)

            processed = 0
            for offset in range(0, len(targets), RPE_REPAIR_BATCH_SIZE):
                batch = targets[offset : offset + RPE_REPAIR_BATCH_SIZE]
                for decision, rendered in batch:
                    self._write_pending(
                        plan,
                        decision,
                        rendered,
                        "rpe_default",
                    )
                remotes = self._submit_exact(
                    [rendered for _decision, rendered in batch],
                    athlete_id=athlete.id,
                )
                by_external = {
                    remote.external_id: remote for remote in remotes
                }
                resolved = [
                    (
                        decision,
                        by_external[rendered.payload.external_id],
                        rendered,
                        value,
                    )
                    for decision, rendered in batch
                ]
                self._finalize_rpe_receipts(plan, resolved)
                processed += len(resolved)

            if (
                tree_digest(self.archive_root) != archive_digest_before
                or tree_digest(self.metrics_root) != metrics_digest_before
                or self.sync_state_path.read_bytes() != sync_state_before
            ):
                raise HistoricalActivityBackfillError(
                    "RPE-default repair changed protected local state"
                )
            final_ledger = load_ledger(self.repo)
            if final_ledger.pending:
                raise HistoricalActivityBackfillError(
                    "RPE-default repair ended with pending intents"
                )
            verified_defaulted = sum(
                receipt.plan_digest_sha256 == plan.plan_digest_sha256
                and receipt.remote_athlete_rpe_override == value
                for receipt in final_ledger.publications.values()
            )
            return {
                "run_id": plan.run_id,
                "value": value,
                "processed": processed,
                "recovered": len(recovered),
                "already_defaulted": already_defaulted,
                "preserved_existing": preserved_existing,
                "verified_defaulted": verified_defaulted,
                "no_op": processed == 0 and not recovered,
            }

    def _assert_receipt_remote(
        self,
        receipt: HistoricalActivityPublication,
        remote: ActivityDTO,
        rendered: RenderedHistoricalActivity,
    ) -> None:
        assert_remote_matches(remote, rendered.payload)
        if (
            remote.id != receipt.destination_activity_id
            or remote.external_id != receipt.ownership_external_id
            or rendered.payload_fingerprint_sha256
            != receipt.payload_fingerprint_sha256
            or readback_fingerprint(remote) != receipt.readback_fingerprint_sha256
        ):
            raise HistoricalActivityBackfillError(
                "Remote receipt drift blocks the RPE-default repair"
            )

    def _assert_rpe_pending(
        self,
        plan: BackfillPlan,
        pending: PendingPublicationIntent,
        rendered: RenderedHistoricalActivity,
    ) -> None:
        if (
            pending.stage != "rpe_default"
            or pending.plan_digest_sha256 != plan.plan_digest_sha256
            or pending.ownership_external_id != rendered.payload.external_id
            or pending.payload_fingerprint_sha256
            != rendered.payload_fingerprint_sha256
        ):
            raise HistoricalActivityBackfillError(
                "RPE-default recovery found a conflicting pending intent"
            )

    def _finalize_rpe_receipts(
        self,
        plan: BackfillPlan,
        resolved: list[
            tuple[
                BackfillDecision,
                ActivityDTO,
                RenderedHistoricalActivity,
                int,
            ]
        ],
    ) -> None:
        ledger = load_ledger(self.repo)
        verified_at: datetime = self.clock()
        for decision, remote, rendered, value in resolved:
            current = ledger.publications.get(decision.local_activity_id)
            if current is None or current.status != PublicationStatus.VERIFIED:
                raise HistoricalActivityBackfillError(
                    "RPE-default finalization requires a verified receipt"
                )
            assert_remote_matches(remote, rendered.payload)
            if (
                current.destination_activity_id != remote.id
                or current.ownership_external_id != remote.external_id
            ):
                raise HistoricalActivityBackfillError(
                    "RPE-default finalization found identity drift"
                )
            ledger.publications[decision.local_activity_id] = current.model_copy(
                update={
                    "payload_fingerprint_sha256": (
                        rendered.payload_fingerprint_sha256
                    ),
                    "readback_fingerprint_sha256": readback_fingerprint(remote),
                    "verified_at_utc": verified_at,
                    "remote_athlete_rpe_override": value,
                }
            )
            ledger.pending.pop(decision.local_activity_id, None)
        save_ledger(self.repo, ledger)
