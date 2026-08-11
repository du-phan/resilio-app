"""Confirmed external-deletion reconciliation for a staged activity archive."""

from datetime import date, datetime, timezone

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.fulfillment_conflicts import (
    persist_unresolved_fulfillment_conflict,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import (
    IntervalsIcuError,
    IntervalsNotFoundError,
)
from resilio.schemas.activity import ActivityStatus, CanonicalActivity
from resilio.schemas.sync import SyncReport
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentManifest


def _record_missing_activity(
    *,
    activity: CanonicalActivity,
    fulfillment_manifest: WorkoutFulfillmentManifest,
    confirm_deletions: bool,
    staging: ActivityArchive,
    report: SyncReport,
    deletion_candidates: list[str],
) -> date | None:
    if activity.local_activity_id in fulfillment_manifest.fulfillments:
        persist_unresolved_fulfillment_conflict(
            fulfillment_manifest,
            local_activity_id=activity.local_activity_id,
            conflict_rule="fulfilled_activity_provider_deleted",
            paired_event_id=None,
            observed_at_utc=datetime.now(timezone.utc),
        )
        deletion_candidates.append(activity.local_activity_id)
        report.partial = True
        report.errors.append(
            "A fulfilled activity cannot be tombstoned without resolving its "
            "workout fulfillment first"
        )
        return None
    if not confirm_deletions:
        deletion_candidates.append(activity.local_activity_id)
        report.partial = True
        report.errors.append("A missing external activity requires deletion review")
        return None
    staging.write(activity.model_copy(update={"status": ActivityStatus.EXTERNAL_DELETED}))
    report.activities_tombstoned += 1
    return activity.occurrence.local_date


def reconcile_external_deletions(
    *,
    client: IntervalsIcuClient,
    staging: ActivityArchive,
    staging_records: list[CanonicalActivity],
    fulfillment_manifest: WorkoutFulfillmentManifest,
    listed_external_ids: set[str],
    oldest: date,
    newest: date,
    confirm_deletions: bool,
    report: SyncReport,
    deletion_candidates: list[str],
    earliest_changed_date: date | None,
) -> date | None:
    """Verify omissions by detail lookup and stage only confirmed safe tombstones."""
    for current in list(staging_records):
        external_id = current.origin.intervals_icu_activity_id
        if not external_id or external_id in listed_external_ids:
            continue
        if not (oldest <= current.occurrence.local_date <= newest):
            continue
        try:
            client.get_activity(external_id)
        except IntervalsNotFoundError:
            changed_date = _record_missing_activity(
                activity=current,
                fulfillment_manifest=fulfillment_manifest,
                confirm_deletions=confirm_deletions,
                staging=staging,
                report=report,
                deletion_candidates=deletion_candidates,
            )
            if changed_date is not None:
                earliest_changed_date = (
                    changed_date
                    if earliest_changed_date is None
                    else min(earliest_changed_date, changed_date)
                )
        except IntervalsIcuError as exc:
            report.partial = True
            report.errors.append(f"External deletion confirmation failed safely: {exc.error_type}")
        else:
            report.partial = True
            report.errors.append(
                "An activity omitted from a complete list still exists by detail lookup"
            )
    return earliest_changed_date
