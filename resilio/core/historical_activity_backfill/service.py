"""Restartable ownership-safe publication of historical bouldering activities."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.windowing import fetch_complete_window
from resilio.core.activity_transaction import (
    ACTIVITY_MUTATION_LOCK_PATH,
)
from resilio.core.config import Config
from resilio.core.historical_activity_backfill.errors import (
    HistoricalActivityBackfillError,
)
from resilio.core.historical_activity_backfill.execution import (
    BackfillExecutionMixin,
)
from resilio.core.historical_activity_backfill.inventory import (
    analyze_inventory,
    archive_source_digest,
    external_inventory_base_digest,
    select_historical_climbs,
    sync_state_base_digest,
    tree_digest,
    visible_composite_match,
)
from resilio.core.historical_activity_backfill.rendering import (
    HistoricalActivityRenderingError,
    RenderedHistoricalActivity,
    assert_remote_matches,
    external_id_for,
    readback_fingerprint,
    render_manual_activity,
    sha256_json,
    sha256_text,
)
from resilio.core.historical_activity_backfill.repository import (
    approval_digest,
    canary_digest,
    create_verified_backup,
    load_approval,
    load_canary_proof,
    load_ledger,
    load_plan,
    now_utc,
    plan_digest,
    run_root,
    save_approval,
    save_canary_proof,
    save_ledger,
    save_plan,
    verify_backup,
)
from resilio.core.historical_activity_backfill.rpe_repair import RpeRepairMixin
from resilio.core.locking import OperationLock
from resilio.core.repository import RepositoryIO
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import ActivityDTO, HiddenActivityDTO
from resilio.integrations.intervals_icu.errors import (
    IntervalsInvalidPayloadError,
    IntervalsNotFoundError,
)
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.historical_backfill import (
    ApprovalStage,
    BackfillApproval,
    BackfillDecision,
    BackfillDecisionAction,
    BackfillPhase,
    BackfillPlan,
    BackfillRunEnvelope,
    CanaryProof,
    FrozenBackfillBaseline,
    PendingPublicationIntent,
    PublicationStatus,
)

BATCH_SIZE = 25


class HistoricalActivityBackfillService(RpeRepairMixin, BackfillExecutionMixin):
    def __init__(
        self,
        repo: RepositoryIO,
        config: Config,
        client: Optional[IntervalsIcuClient],
        *,
        baseline: Optional[FrozenBackfillBaseline] = None,
        clock=now_utc,
    ):
        self.repo = repo
        self.config = config
        self.client = client
        self.baseline = baseline or FrozenBackfillBaseline()
        self.clock = clock
        self.repo_root = repo.repo_root
        self.archive_root = self.repo_root / config.settings.paths.activities_dir
        self.metrics_root = self.repo_root / config.settings.paths.metrics_dir
        self.sync_state_path = self.repo.resolve_path("data/state/activity_sync.json")

    def _require_client(self) -> IntervalsIcuClient:
        if self.client is None:
            raise HistoricalActivityBackfillError(
                "This backfill operation requires Intervals.icu access"
            )
        return self.client

    def _fetch_inventory(
        self,
        oldest: date,
        newest: date,
        *,
        athlete_id: str,
    ) -> list[ActivityDTO | HiddenActivityDTO]:
        settings = self.config.settings.intervals_icu
        return fetch_complete_window(
            self._require_client(),
            oldest,
            newest,
            athlete_id=athlete_id,
            limit=settings.list_limit,
        )

    def dry_run(
        self,
        *,
        today: date,
        downloads_disabled_confirmed: bool,
    ) -> BackfillPlan:
        records = ActivityArchive(self.archive_root).load_all()
        selected = select_historical_climbs(records)
        athlete = self._require_client().get_athlete()
        if athlete.timezone != "Europe/Paris":
            raise HistoricalActivityBackfillError(
                "Backfill requires the Intervals.icu athlete timezone Europe/Paris"
            )
        oldest = min(
            self.config.settings.intervals_icu.history_start_date,
            min(activity.date for activity in selected),
        )
        rows = self._fetch_inventory(oldest, today, athlete_id=athlete.id)
        analysis = analyze_inventory(
            selected=selected,
            all_records=records,
            rows=rows,
            baseline=self.baseline,
        )
        if analysis.canary_local_activity_id is None:
            raise HistoricalActivityBackfillError(
                "No exact-time description-and-RPE canary satisfies the frozen policy"
            )

        selected_ids = {activity.local_activity_id for activity in selected}
        archive_digest = archive_source_digest(records)
        metrics_digest = tree_digest(self.metrics_root)
        sync_digest = sync_state_base_digest(
            self.sync_state_path,
            selected_ids,
        )
        inventory_digest = external_inventory_base_digest(rows)
        run_material = {
            "archive": archive_digest,
            "inventory": inventory_digest,
            "decisions": sha256_json(analysis.report_payload),
            "oldest": oldest.isoformat(),
            "newest": today.isoformat(),
            "downloads_disabled_confirmed": downloads_disabled_confirmed,
        }
        run_id = f"backfill-{sha256_json(run_material)[:16]}"
        report_payload = {
            **analysis.report_payload,
            "run_id": run_id,
            "inventory_oldest": oldest.isoformat(),
            "inventory_newest": today.isoformat(),
            "downloads_disabled_confirmed": downloads_disabled_confirmed,
            "archive_source_digest_sha256": archive_digest,
            "metrics_tree_digest_sha256": metrics_digest,
            "sync_state_base_digest_sha256": sync_digest,
            "external_inventory_base_digest_sha256": inventory_digest,
        }
        report_digest = sha256_json(report_payload)
        provisional = BackfillPlan(
            run_id=run_id,
            inventory_oldest=oldest,
            inventory_newest=today,
            downloads_disabled_confirmed=downloads_disabled_confirmed,
            frozen_baseline=self.baseline,
            archive_source_digest_sha256=archive_digest,
            metrics_tree_digest_sha256=metrics_digest,
            sync_state_base_digest_sha256=sync_digest,
            external_inventory_base_digest_sha256=inventory_digest,
            report_digest_sha256=report_digest,
            canary_local_activity_id=analysis.canary_local_activity_id,
            coverage=analysis.coverage,
            decisions=sorted(
                analysis.decisions,
                key=lambda item: item.local_activity_id,
            ),
            plan_digest_sha256="0" * 64,
        )
        plan = provisional.model_copy(
            update={"plan_digest_sha256": plan_digest(provisional)}
        )
        save_plan(self.repo_root, plan, report_payload)
        create_verified_backup(self.repo_root, plan)
        self._save_envelope(plan, BackfillPhase.DRY_RUN)
        return plan

    def record_approval(
        self,
        *,
        stage: ApprovalStage,
        plan_digest_sha256: str,
        canary_digest_sha256: Optional[str] = None,
    ) -> BackfillApproval:
        plan = load_plan(self.repo_root, plan_digest_sha256)
        if not plan.downloads_disabled_confirmed:
            raise HistoricalActivityBackfillError(
                "Future activity downloads must be disabled in the Intervals.icu UI "
                "and confirmed in a new dry run before approval"
            )
        if stage in {ApprovalStage.APPLY, ApprovalStage.RPE_DEFAULT}:
            proof = load_canary_proof(self.repo_root, plan)
            if canary_digest_sha256 != proof.canary_digest_sha256:
                raise HistoricalActivityBackfillError(
                    f"{stage.value} approval must bind the exact verified canary digest"
                )
        elif canary_digest_sha256 is not None:
            raise HistoricalActivityBackfillError(
                "Canary approval does not accept a canary digest"
            )
        approval_path = (
            run_root(self.repo_root, plan.run_id)
            / f"approval-{stage.value}.json"
        )
        if approval_path.exists():
            existing = load_approval(self.repo_root, plan, stage)
            if existing.canary_digest_sha256 != canary_digest_sha256:
                raise HistoricalActivityBackfillError(
                    "Recorded approval is bound to a different canary digest"
                )
            return existing
        provisional = BackfillApproval(
            stage=stage,
            plan_digest_sha256=plan.plan_digest_sha256,
            canary_digest_sha256=canary_digest_sha256,
            recorded_at_utc=self.clock(),
            approval_digest_sha256="0" * 64,
        )
        approval = provisional.model_copy(
            update={"approval_digest_sha256": approval_digest(provisional)}
        )
        save_approval(self.repo_root, plan, approval)
        return approval

    def canary(self, *, plan_digest_sha256: str) -> CanaryProof:
        plan = load_plan(self.repo_root, plan_digest_sha256)
        existing_path = run_root(self.repo_root, plan.run_id) / "canary-proof.json"
        if existing_path.exists():
            return load_canary_proof(self.repo_root, plan)
        approval = load_approval(self.repo_root, plan, ApprovalStage.CANARY)
        if approval.plan_digest_sha256 != plan_digest_sha256:
            raise HistoricalActivityBackfillError("Canary approval digest mismatch")
        lock_path = self.repo_root / ACTIVITY_MUTATION_LOCK_PATH
        with OperationLock(lock_path, "historical_activity_backfill_canary"):
            self._recover_transactions(plan)
            athlete_id, rows = self._verify_plan_drift(plan)
            decision = self._decision(plan, plan.canary_local_activity_id)
            activity, rendered = self._activity_and_rendered(plan, decision)
            if decision.action == BackfillDecisionAction.EXCLUDE_HIDDEN:
                raise HistoricalActivityBackfillError(
                    "Frozen canary unexpectedly became a hidden exclusion"
                )
            self._save_envelope(plan, BackfillPhase.CANARY_PENDING)
            self._write_pending(plan, decision, rendered, "canary")
            try:
                first = self._resolve_or_submit_one(
                    activity=activity,
                    rendered=rendered,
                    rows=rows,
                    athlete_id=athlete_id,
                )
                repeated = self._submit_exact([rendered], athlete_id=athlete_id)[0]
                assert_remote_matches(repeated, rendered.payload)
                if repeated.id != first.id:
                    raise HistoricalActivityBackfillError(
                        "Personal-key canary upsert changed the activity identity"
                    )
                current_rows = self._fetch_inventory(
                    activity.date,
                    activity.date,
                    athlete_id=athlete_id,
                )
                owned = self._owned_rows(current_rows, rendered.payload.external_id)
                if len(owned) != 1 or owned[0].id != first.id:
                    raise HistoricalActivityBackfillError(
                        "Repeated canary submission did not leave exactly one owned activity"
                    )
                readback = self._require_client().get_activity(first.id, intervals=False)
                assert_remote_matches(readback, rendered.payload)
            except (
                HistoricalActivityBackfillError,
                HistoricalActivityRenderingError,
                IntervalsInvalidPayloadError,
            ):
                self._cleanup_failed_canary(
                    activity.date,
                    rendered,
                    athlete_id=athlete_id,
                )
                self._clear_pending(decision.local_activity_id)
                self._save_envelope(
                    plan,
                    BackfillPhase.FAILED,
                    error="Canary ownership/type/idempotency gate failed",
                )
                raise

            self._commit_links(
                plan,
                [(decision, readback)],
                transaction_name="canary",
            )
            self._finalize_receipts(plan, [(decision, readback)])
            provisional = CanaryProof(
                plan_digest_sha256=plan.plan_digest_sha256,
                local_activity_id=decision.local_activity_id,
                destination_activity_id=readback.id,
                ownership_external_id=rendered.payload.external_id,
                payload_fingerprint_sha256=rendered.payload_fingerprint_sha256,
                readback_fingerprint_sha256=readback_fingerprint(readback),
                repeated_submission_activity_id=repeated.id,
                matching_remote_count=1,
                verified_at_utc=self.clock(),
                canary_digest_sha256="0" * 64,
            )
            proof = provisional.model_copy(
                update={"canary_digest_sha256": canary_digest(provisional)}
            )
            save_canary_proof(self.repo_root, plan, proof)
            self._save_envelope(plan, BackfillPhase.CANARY_VERIFIED)
            return proof

    def apply(
        self,
        *,
        plan_digest_sha256: str,
        canary_digest_sha256: str,
    ) -> dict:
        plan = load_plan(self.repo_root, plan_digest_sha256)
        proof = load_canary_proof(self.repo_root, plan)
        approval = load_approval(self.repo_root, plan, ApprovalStage.APPLY)
        if (
            proof.canary_digest_sha256 != canary_digest_sha256
            or approval.canary_digest_sha256 != canary_digest_sha256
        ):
            raise HistoricalActivityBackfillError(
                "Application is not bound to the approved canary proof"
            )
        lock_path = self.repo_root / ACTIVITY_MUTATION_LOCK_PATH
        with OperationLock(lock_path, "historical_activity_backfill_apply"):
            self._recover_transactions(plan)
            athlete_id, _rows = self._verify_plan_drift(plan)
            publishable = [
                decision
                for decision in plan.decisions
                if decision.action
                in {
                    BackfillDecisionAction.PUBLISH,
                    BackfillDecisionAction.ADOPT_OWNED,
                }
            ]
            publishable.sort(
                key=lambda item: (item.local_date, item.local_activity_id)
            )
            self._save_envelope(plan, BackfillPhase.APPLY_PENDING)
            processed = 0
            for offset in range(0, len(publishable), BATCH_SIZE):
                batch = publishable[offset : offset + BATCH_SIZE]
                processed += self._apply_batch(
                    plan,
                    batch,
                    athlete_id=athlete_id,
                    batch_number=offset // BATCH_SIZE,
                )
                self._save_envelope(plan, BackfillPhase.APPLY_PENDING)
            ledger = load_ledger(self.repo)
            verified = [
                item
                for item in ledger.publications.values()
                if (
                    item.plan_digest_sha256 == plan.plan_digest_sha256
                    and item.status == PublicationStatus.VERIFIED
                )
            ]
            if len(verified) != plan.coverage.publishable or ledger.pending:
                raise HistoricalActivityBackfillError(
                    "Application stopped with incomplete ownership ledger entries"
                )
            self._verify_local_acceptance(plan)
            self._save_envelope(plan, BackfillPhase.APPLIED)
            return {
                "run_id": plan.run_id,
                "processed": processed,
                "verified_publications": len(verified),
                "no_op": processed == 0,
            }

    def resume(
        self,
        *,
        plan_digest_sha256: str,
        canary_digest_sha256: str,
    ) -> dict:
        return self.apply(
            plan_digest_sha256=plan_digest_sha256,
            canary_digest_sha256=canary_digest_sha256,
        )

    def rollback(
        self,
        *,
        plan_digest_sha256: str,
        canary_digest_sha256: str,
    ) -> dict:
        plan = load_plan(self.repo_root, plan_digest_sha256)
        proof = load_canary_proof(self.repo_root, plan)
        load_approval(self.repo_root, plan, ApprovalStage.APPLY)
        if proof.canary_digest_sha256 != canary_digest_sha256:
            raise HistoricalActivityBackfillError(
                "Rollback is not bound to the exact canary proof"
            )
        lock_path = self.repo_root / ACTIVITY_MUTATION_LOCK_PATH
        with OperationLock(lock_path, "historical_activity_backfill_rollback"):
            self._recover_transactions(plan)
            self._verify_rollback_preflight(plan)
            metrics_before = tree_digest(self.metrics_root)
            records_before = ActivityArchive(self.archive_root).load_all()
            records_by_local = {
                item.local_activity_id: item for item in records_before
            }
            links_before = sum(
                bool(item.origin.intervals_icu_activity_id)
                for item in records_before
            )
            ledger = load_ledger(self.repo)
            receipts = [
                item
                for item in ledger.publications.values()
                if (
                    item.plan_digest_sha256 == plan.plan_digest_sha256
                    and item.status
                    in {
                        PublicationStatus.VERIFIED,
                        PublicationStatus.ROLLBACK_PENDING,
                    }
                )
            ]
            receipts.sort(
                key=lambda item: (item.local_date, item.local_activity_id),
                reverse=True,
            )
            self._save_envelope(plan, BackfillPhase.ROLLBACK_PENDING)
            restored = 0
            for receipt in receipts:
                decision = self._decision(plan, receipt.local_activity_id)
                rendered = self._receipt_rendered(
                    plan,
                    decision,
                    receipt,
                    records_by_local[receipt.local_activity_id],
                )
                remote: ActivityDTO | None
                try:
                    remote = self._require_client().get_activity(
                        receipt.destination_activity_id,
                        intervals=False,
                    )
                except IntervalsNotFoundError:
                    if receipt.status != PublicationStatus.ROLLBACK_PENDING:
                        raise HistoricalActivityBackfillError(
                            "Owned activity disappeared before rollback intent was recorded"
                        )
                    remote = None
                if remote is not None:
                    assert_remote_matches(remote, rendered.payload)
                    if (
                        remote.id != receipt.destination_activity_id
                        or remote.external_id != receipt.ownership_external_id
                        or readback_fingerprint(remote)
                        != receipt.readback_fingerprint_sha256
                    ):
                        raise HistoricalActivityBackfillError(
                            "Remote activity drift blocks exact rollback"
                        )
                    receipt = receipt.model_copy(
                        update={"status": PublicationStatus.ROLLBACK_PENDING}
                    )
                    ledger.publications[receipt.local_activity_id] = receipt
                    save_ledger(self.repo, ledger)
                    self._require_client().delete_activity(
                        receipt.destination_activity_id
                    )
                    try:
                        self._require_client().get_activity(
                            receipt.destination_activity_id,
                            intervals=False,
                        )
                    except IntervalsNotFoundError:
                        pass
                    else:
                        raise HistoricalActivityBackfillError(
                            "Exact activity deletion could not be verified"
                        )
                self._restore_original(
                    plan,
                    receipt,
                    transaction_name=(
                        f"rollback-{sha256_text(receipt.local_activity_id)[:12]}"
                    ),
                )
                ledger = load_ledger(self.repo)
                current = ledger.publications[receipt.local_activity_id]
                ledger.publications[receipt.local_activity_id] = current.model_copy(
                    update={
                        "status": PublicationStatus.ROLLED_BACK,
                        "rolled_back_at_utc": self.clock(),
                    }
                )
                ledger.pending.pop(receipt.local_activity_id, None)
                save_ledger(self.repo, ledger)
                restored += 1
                self._save_envelope(plan, BackfillPhase.ROLLBACK_PENDING)
            self._verify_rollback_acceptance(
                plan,
                metrics_digest_before=metrics_before,
                archive_count_before=len(records_before),
                external_links_before=links_before,
                restored=restored,
            )
            self._save_envelope(plan, BackfillPhase.ROLLED_BACK)
            return {
                "run_id": plan.run_id,
                "restored": restored,
                "no_op": restored == 0,
            }

    def status(self) -> dict:
        runs = []
        root = self.repo_root / "data/migrations/historical-activity-backfill"
        if root.is_dir():
            for path in sorted(root.glob("*/run.json")):
                envelope = BackfillRunEnvelope.model_validate_json(path.read_text())
                runs.append(envelope.model_dump(mode="json"))
        ledger = load_ledger(self.repo)
        counts = {
            status.value: sum(
                item.status == status
                for item in ledger.publications.values()
            )
            for status in PublicationStatus
        }
        return {
            "runs": runs,
            "ledger_counts": counts,
            "rpe_defaulted": sum(
                item.remote_athlete_rpe_override is not None
                for item in ledger.publications.values()
            ),
            "pending": len(ledger.pending),
        }

    def _verify_plan_drift(
        self,
        plan: BackfillPlan,
    ) -> tuple[str, list[ActivityDTO | HiddenActivityDTO]]:
        if not plan.downloads_disabled_confirmed:
            raise HistoricalActivityBackfillError(
                "Future activity downloads were not confirmed disabled"
            )
        verify_backup(self.repo_root, plan)
        records = ActivityArchive(self.archive_root).load_all()
        selected_ids = {item.local_activity_id for item in plan.decisions}
        for activity in records:
            if (
                activity.local_activity_id in selected_ids
                and activity.origin.intervals_icu_activity_id
                and activity.origin.upstream_external_id
                != external_id_for(activity.local_activity_id)
            ):
                raise HistoricalActivityBackfillError(
                    "A planned source acquired a non-backfill external link"
                )
        if archive_source_digest(records) != plan.archive_source_digest_sha256:
            raise HistoricalActivityBackfillError(
                "Canonical archive drift invalidated the recorded approvals"
            )
        if tree_digest(self.metrics_root) != plan.metrics_tree_digest_sha256:
            raise HistoricalActivityBackfillError(
                "Metrics drift invalidated the recorded approvals"
            )
        if (
            sync_state_base_digest(self.sync_state_path, selected_ids)
            != plan.sync_state_base_digest_sha256
        ):
            raise HistoricalActivityBackfillError(
                "Activity sync-state drift invalidated the recorded approvals"
            )
        athlete = self._require_client().get_athlete()
        if athlete.timezone != plan.timezone:
            raise HistoricalActivityBackfillError(
                "Athlete timezone drift invalidated the recorded approvals"
            )
        rows = self._fetch_inventory(
            plan.inventory_oldest,
            max(plan.inventory_newest, self.clock().date()),
            athlete_id=athlete.id,
        )
        if (
            external_inventory_base_digest(rows)
            != plan.external_inventory_base_digest_sha256
        ):
            raise HistoricalActivityBackfillError(
                "External inventory drift invalidated the recorded approvals"
            )
        return athlete.id, rows

    def _decision(
        self,
        plan: BackfillPlan,
        local_activity_id: Optional[str],
    ) -> BackfillDecision:
        matches = [
            item
            for item in plan.decisions
            if item.local_activity_id == local_activity_id
        ]
        if len(matches) != 1:
            raise HistoricalActivityBackfillError(
                "Immutable plan does not contain exactly one requested decision"
            )
        return matches[0]

    def _activity_and_rendered(
        self,
        plan: BackfillPlan,
        decision: BackfillDecision,
    ) -> tuple[CanonicalActivity, RenderedHistoricalActivity]:
        matches = [
            item
            for item in ActivityArchive(self.archive_root).load_all()
            if item.local_activity_id == decision.local_activity_id
        ]
        if len(matches) != 1:
            raise HistoricalActivityBackfillError(
                "Planned local activity is missing or duplicated"
            )
        activity = matches[0]
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
        return activity, rendered

    def _owned_rows(
        self,
        rows: list[ActivityDTO | HiddenActivityDTO],
        external_id: str,
    ) -> list[ActivityDTO]:
        return [
            row
            for row in rows
            if isinstance(row, ActivityDTO) and row.external_id == external_id
        ]

    def _resolve_or_submit_one(
        self,
        *,
        activity: CanonicalActivity,
        rendered: RenderedHistoricalActivity,
        rows: list[ActivityDTO | HiddenActivityDTO],
        athlete_id: str,
    ) -> ActivityDTO:
        owned = self._owned_rows(rows, rendered.payload.external_id)
        if len(owned) > 1:
            raise HistoricalActivityBackfillError(
                "Multiple remote activities use the deterministic ownership ID"
            )
        if len(owned) == 1:
            remote = self._require_client().get_activity(
                owned[0].id,
                intervals=False,
            )
            assert_remote_matches(remote, rendered.payload)
            return remote
        for row in rows:
            if isinstance(row, ActivityDTO) and visible_composite_match(row, rendered):
                raise HistoricalActivityBackfillError(
                    "A visible unowned composite match blocks publication"
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
                        "A new hidden collision blocks publication"
                    )
        return self._submit_exact([rendered], athlete_id=athlete_id)[0]

    def _submit_exact(
        self,
        rendered: list[RenderedHistoricalActivity],
        *,
        athlete_id: str,
    ) -> list[ActivityDTO]:
        expected = [item.payload.external_id for item in rendered]
        response = self._require_client().create_manual_activities(
            [item.payload for item in rendered],
            athlete_id=athlete_id,
        )
        returned = [item.external_id for item in response]
        if (
            set(returned) != set(expected)
            or len(returned) != len(set(returned))
            or len(returned) != len(expected)
        ):
            raise HistoricalActivityBackfillError(
                "Bulk manual response omitted, duplicated, or added ownership IDs"
            )
        by_external = {item.external_id: item for item in response}
        exact: list[ActivityDTO] = []
        for item in rendered:
            response_item = by_external[item.payload.external_id]
            assert_remote_matches(response_item, item.payload)
            remote = self._require_client().get_activity(
                response_item.id,
                intervals=False,
            )
            assert_remote_matches(remote, item.payload)
            exact.append(remote)
        return exact

    def _write_pending(
        self,
        plan: BackfillPlan,
        decision: BackfillDecision,
        rendered: RenderedHistoricalActivity,
        stage: str,
    ) -> None:
        ledger = load_ledger(self.repo)
        existing = ledger.pending.get(decision.local_activity_id)
        intent = PendingPublicationIntent(
            local_activity_id=decision.local_activity_id,
            ownership_external_id=rendered.payload.external_id,
            plan_digest_sha256=plan.plan_digest_sha256,
            payload_fingerprint_sha256=rendered.payload_fingerprint_sha256,
            stage=stage,
            initiated_at_utc=self.clock(),
        )
        if existing is not None:
            comparable = (
                existing.local_activity_id == intent.local_activity_id
                and existing.ownership_external_id == intent.ownership_external_id
                and existing.plan_digest_sha256 == intent.plan_digest_sha256
                and existing.payload_fingerprint_sha256
                == intent.payload_fingerprint_sha256
                and existing.stage == intent.stage
            )
            if not comparable:
                raise HistoricalActivityBackfillError(
                    "A conflicting durable publication intent already exists"
                )
            return
        ledger.pending[decision.local_activity_id] = intent
        save_ledger(self.repo, ledger)

    def _clear_pending(self, local_activity_id: str) -> None:
        ledger = load_ledger(self.repo)
        ledger.pending.pop(local_activity_id, None)
        save_ledger(self.repo, ledger)
