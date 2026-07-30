"""Reconcile fetched provider details into a staged canonical archive."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from resilio.core.activity_sync.activity_merge import merge_reviewed_activity
from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.completed_workouts import (
    reconcile_workout_completion,
)
from resilio.core.activity_sync.errors import ActivitySyncError
from resilio.core.activity_sync.original_files import (
    probe_original_file_for_ambiguity,
)
from resilio.core.activity_sync.reconciliation import reconcile_activity
from resilio.core.activity_sync.review import (
    build_mapping_quarantine_decision,
    load_override_ledger,
    load_quarantine_acknowledgement_ledger,
    reconciliation_review_fingerprint,
)
from resilio.core.activity_transaction import write_json
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.completions import (
    load_completion_manifest,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.integrations.intervals_icu.activity_fingerprint import (
    external_fingerprint,
)
from resilio.integrations.intervals_icu.activity_mapper import map_activity
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.integrations.intervals_icu.errors import (
    IntervalsIcuError,
    IntervalsNotFoundError,
)
from resilio.schemas.activity import (
    ActivityStatus,
    CanonicalActivity,
)
from resilio.schemas.publication import WorkoutCompletionManifest
from resilio.schemas.reconciliation import (
    ReconciliationAction,
    ReconciliationDecision,
)
from resilio.schemas.sync import SourceCoverageExclusion, SyncReport


@dataclass(frozen=True)
class StagedReconciliationOutcome:
    completion_manifest: WorkoutCompletionManifest
    earliest_changed_date: date | None
    decisions: list[dict[str, Any]]
    completion_candidates: list[dict[str, Any]]
    external_deletion_candidates: list[str]

    def source_coverage_exclusions(self) -> list[SourceCoverageExclusion]:
        exclusions: list[SourceCoverageExclusion] = []
        for decision in self.decisions:
            action = decision.get("action")
            local_date_raw = decision.get("local_date")
            if not isinstance(local_date_raw, str):
                continue
            local_date = date.fromisoformat(local_date_raw)
            if action == "excluded_duplicate_recording":
                exclusions.append(
                    SourceCoverageExclusion(
                        external_activity_id_sha256=str(decision["external_activity_id_sha256"]),
                        local_date=local_date,
                        source_sport_type=decision.get("source_sport_type"),
                        reason="represented_duplicate_recording",
                        represented_by_local_activity_id=str(decision["local_activity_id"]),
                        review_fingerprint_sha256=str(decision["review_fingerprint_sha256"]),
                    )
                )
            elif (
                action == "quarantine"
                and decision.get("acknowledged") is True
                and decision.get("acknowledgeable") is True
            ):
                exclusions.append(
                    SourceCoverageExclusion(
                        external_activity_id_sha256=str(decision["external_activity_id_sha256"]),
                        local_date=local_date,
                        source_sport_type=decision.get("source_sport_type"),
                        reason="acknowledged_unsupported_sport",
                    )
                )
        return exclusions


class StagedActivityReconciler:
    """Own the mutable state for one isolated staged-archive reconciliation."""

    def __init__(
        self,
        *,
        client: IntervalsIcuClient,
        repo: RepositoryIO,
        staging: ActivityArchive,
        staging_records: list[CanonicalActivity],
        athlete_timezone: str | None,
        report: SyncReport,
    ) -> None:
        self.client = client
        self.staging = staging
        self.staging_records = staging_records
        self.athlete_timezone = athlete_timezone
        self.report = report
        self.override_ledger = load_override_ledger(repo)
        self.quarantine_acknowledgements = load_quarantine_acknowledgement_ledger(repo)
        self.publication_manifest = load_manifest(repo)
        self.completion_manifest = load_completion_manifest(repo)
        self.published_by_event_id = {
            publication.event_id: publication
            for publication in self.publication_manifest.workouts.values()
        }
        self.decisions: list[dict[str, Any]] = []
        self.completion_candidates: list[dict[str, Any]] = []
        self.external_deletion_candidates: list[str] = []
        self.earliest_changed_date: date | None = None

    def reconcile_details(self, details: dict[str, ActivityDTO]) -> None:
        for external_id in sorted(details):
            self._reconcile_one(external_id, details[external_id])

    def _reconcile_one(self, external_id: str, detail: ActivityDTO) -> None:
        mapped = self._map_or_quarantine(external_id, detail)
        if mapped is None:
            return
        decision = reconcile_activity(mapped, self.staging_records)
        if decision.action == ReconciliationAction.AMBIGUOUS:
            probe = probe_original_file_for_ambiguity(
                client=self.client,
                activity=mapped,
                existing_records=self.staging_records,
                decision=decision,
            )
            mapped = probe.activity
            decision = probe.decision
        if decision.action == ReconciliationAction.AMBIGUOUS:
            reviewed_decision = self._apply_review_decision(
                external_id,
                mapped,
                decision,
            )
            if reviewed_decision is None:
                return
            decision = reviewed_decision
        if decision.action == ReconciliationAction.AMBIGUOUS:
            self.report.ambiguous_rows += 1
            self.report.partial = True
            self.decisions.append(
                _sanitized_decision(
                    decision,
                    external_source_fingerprint_sha256=(mapped.audit.external_fingerprint_sha256),
                )
            )
            return
        final_activity = self._store_reconciled_activity(decision)
        self._record_completion(external_id, detail, final_activity)

    def _map_or_quarantine(
        self,
        external_id: str,
        detail: ActivityDTO,
    ) -> CanonicalActivity | None:
        try:
            return map_activity(
                detail,
                default_timezone=self.athlete_timezone,
            )
        except Exception as exc:
            external_hash = _external_id_sha256(external_id)
            quarantine = build_mapping_quarantine_decision(
                external_activity_id_sha256=external_hash,
                external_source_fingerprint_sha256=external_fingerprint(
                    detail,
                    self.athlete_timezone,
                ),
                error=exc,
            )
            acknowledgement = self.quarantine_acknowledgements.acknowledgements.get(external_hash)
            self.report.quarantined_rows += 1
            if (
                acknowledgement is not None
                and acknowledgement.failure_fingerprint_sha256
                == quarantine["failure_fingerprint_sha256"]
                and quarantine["acknowledgeable"]
            ):
                self.report.acknowledged_quarantined_rows += 1
                quarantine["acknowledged"] = True
            else:
                self.report.partial = True
                quarantine["acknowledged"] = False
            quarantine["local_date"] = detail.start_date_local.date().isoformat()
            quarantine["source_sport_type"] = detail.type
            self.decisions.append(quarantine)
            return None

    def _apply_review_decision(
        self,
        external_id: str,
        mapped: CanonicalActivity,
        decision: ReconciliationDecision,
    ) -> ReconciliationDecision | None:
        external_hash = _external_id_sha256(external_id)
        sanitized = _sanitized_decision(
            decision,
            external_source_fingerprint_sha256=(mapped.audit.external_fingerprint_sha256),
        )
        exclusion = self.override_ledger.exclusions.get(external_hash)
        if exclusion is not None and self._exclusion_is_current(
            exclusion.local_activity_id,
            exclusion.review_fingerprint_sha256,
            external_hash,
            decision,
            sanitized,
        ):
            self.report.excluded_duplicate_rows += 1
            self.decisions.append(
                {
                    **sanitized,
                    "action": "excluded_duplicate_recording",
                    "review_fingerprint_sha256": (exclusion.review_fingerprint_sha256),
                    "local_date": mapped.occurrence.local_date.isoformat(),
                    "source_sport_type": mapped.source_sport_type,
                    "local_activity_id": exclusion.local_activity_id,
                }
            )
            return None

        override = self.override_ledger.overrides.get(external_hash)
        if override is None:
            return decision
        candidate = next(
            (
                item
                for item in self.staging_records
                if item.local_activity_id == override.local_activity_id
            ),
            None,
        )
        if (
            candidate is not None
            and candidate.local_activity_id in decision.candidate_local_ids
            and override.review_fingerprint_sha256
            == reconciliation_review_fingerprint(
                sanitized,
                self.staging_records,
            )
        ):
            return ReconciliationDecision(
                action=ReconciliationAction.LINK,
                rule="approved_review_override",
                external_activity_id=external_id,
                local_activity_id=candidate.local_activity_id,
                activity=merge_reviewed_activity(candidate, mapped),
            )
        self.report.quarantined_rows += 1
        self.report.partial = True
        self.decisions.append(
            {
                "action": "quarantine",
                "rule": "stale_review_override",
                "external_activity_id_sha256": external_hash,
                "error_type": "ReconciliationReviewError",
            }
        )
        return None

    def _exclusion_is_current(
        self,
        local_activity_id: str,
        review_fingerprint_sha256: str,
        external_id_sha256: str,
        decision: ReconciliationDecision,
        sanitized: dict[str, Any],
    ) -> bool:
        candidate = next(
            (item for item in self.staging_records if item.local_activity_id == local_activity_id),
            None,
        )
        existing_external_id = (
            candidate.origin.intervals_icu_activity_id if candidate is not None else None
        )
        return (
            local_activity_id in decision.candidate_local_ids
            and review_fingerprint_sha256
            == reconciliation_review_fingerprint(
                sanitized,
                self.staging_records,
            )
            and existing_external_id is not None
            and _external_id_sha256(existing_external_id) != external_id_sha256
        )

    def _store_reconciled_activity(
        self,
        decision: ReconciliationDecision,
    ) -> CanonicalActivity:
        if decision.activity is None:
            raise ActivitySyncError("Reconciliation produced no activity")
        activity = decision.activity
        if decision.rule == "linked_fingerprint_unchanged":
            self.report.activities_unchanged += 1
            return activity

        self.staging.write(activity)
        self.staging_records = [
            item
            for item in self.staging_records
            if item.local_activity_id != activity.local_activity_id
        ]
        self.staging_records.append(activity)
        self.earliest_changed_date = (
            activity.occurrence.local_date
            if self.earliest_changed_date is None
            else min(
                self.earliest_changed_date,
                activity.occurrence.local_date,
            )
        )
        if decision.action == ReconciliationAction.CREATE:
            self.report.activities_created += 1
        elif decision.action == ReconciliationAction.LINK:
            self.report.activities_linked += 1
        else:
            self.report.activities_updated += 1
        return activity

    def _record_completion(
        self,
        external_id: str,
        detail: ActivityDTO,
        activity: CanonicalActivity,
    ) -> None:
        completion = reconcile_workout_completion(
            activity=activity,
            paired_event_id=detail.paired_event_id,
            publications_by_event_id=self.published_by_event_id,
            publications=self.publication_manifest.workouts.values(),
            existing_match=self.completion_manifest.matches.get(activity.local_activity_id),
            matched_at_utc=datetime.now(timezone.utc),
        )
        if completion.conflict is not None:
            self.report.quarantined_rows += 1
            self.report.partial = True
            self.decisions.append(
                {
                    "action": "quarantine",
                    "external_activity_id_sha256": (_external_id_sha256(external_id)),
                    **completion.conflict,
                }
            )
        elif completion.match is not None:
            self.completion_manifest.matches[activity.local_activity_id] = completion.match
            self.report.completion_matches_linked += 1
        elif completion.candidate is not None:
            self.completion_candidates.append(completion.candidate)
            self.report.completion_candidates_reported += 1

    def confirm_external_deletions(
        self,
        *,
        listed_external_ids: set[str],
        oldest: date,
        newest: date,
        confirm_deletions: bool,
    ) -> None:
        for current in list(self.staging_records):
            external_id = current.origin.intervals_icu_activity_id
            if not external_id or external_id in listed_external_ids:
                continue
            if not (oldest <= current.occurrence.local_date <= newest):
                continue
            try:
                self.client.get_activity(external_id)
            except IntervalsNotFoundError:
                self._record_missing_external(current, confirm_deletions)
            except IntervalsIcuError as exc:
                self.report.partial = True
                self.report.errors.append(
                    "External deletion confirmation failed safely: " f"{exc.error_type}"
                )
            else:
                self.report.partial = True
                self.report.errors.append(
                    "An activity omitted from a complete list still exists " "by detail lookup"
                )

    def _record_missing_external(
        self,
        activity: CanonicalActivity,
        confirm_deletions: bool,
    ) -> None:
        if not confirm_deletions:
            self.external_deletion_candidates.append(activity.local_activity_id)
            self.report.partial = True
            self.report.errors.append("A missing external activity requires deletion review")
            return
        tombstone = activity.model_copy(update={"status": ActivityStatus.EXTERNAL_DELETED})
        self.staging.write(tombstone)
        self.report.activities_tombstoned += 1
        self.earliest_changed_date = (
            activity.occurrence.local_date
            if self.earliest_changed_date is None
            else min(
                self.earliest_changed_date,
                activity.occurrence.local_date,
            )
        )

    def write_quarantine_report(
        self,
        *,
        path: Path,
        run_id: str,
        hidden_row_count: int,
    ) -> None:
        write_json(
            path,
            {
                "schema_version": 1,
                "run_id": run_id,
                "ambiguous_decisions": self.decisions,
                "completion_candidates": self.completion_candidates,
                "external_deletion_candidates": sorted(self.external_deletion_candidates),
                "hidden_rows": hidden_row_count,
            },
        )

    def outcome(self) -> StagedReconciliationOutcome:
        return StagedReconciliationOutcome(
            completion_manifest=self.completion_manifest,
            earliest_changed_date=self.earliest_changed_date,
            decisions=self.decisions,
            completion_candidates=self.completion_candidates,
            external_deletion_candidates=self.external_deletion_candidates,
        )


def _external_id_sha256(external_id: str) -> str:
    return hashlib.sha256(external_id.encode()).hexdigest()


def _sanitized_decision(
    decision: ReconciliationDecision,
    *,
    external_source_fingerprint_sha256: str | None = None,
) -> dict[str, Any]:
    payload = decision.model_dump(mode="json", exclude={"activity"})
    external_id = payload.pop("external_activity_id")
    payload["external_activity_id_sha256"] = _external_id_sha256(external_id)
    if external_source_fingerprint_sha256 is not None:
        payload["external_source_fingerprint_sha256"] = external_source_fingerprint_sha256
    return payload
