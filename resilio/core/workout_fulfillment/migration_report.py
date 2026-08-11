"""Public result contract for the one-shot fulfillment cutover."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkoutFulfillmentMigrationReport:
    run_id: str
    active_publication_count: int
    pending_publication_count: int
    historical_publication_count: int
    active_fulfillment_count: int
    historical_fulfillment_count: int
    migrated_planning_artifact_count: int
    migrated_plan_count: int
    changes_required: bool
    applied: bool
    backup_relative_path: str | None
