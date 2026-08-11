"""Fail-closed gate while the coordinated fulfillment cutover is incomplete."""

from resilio.core.repository import RepositoryIO

MIGRATION_TRANSACTION_PATH = "data/state/workout-fulfillment-migration.json"


def assert_fulfillment_cutover_is_complete(repo: RepositoryIO) -> None:
    """Reject normal state access until crash recovery completes the cutover."""
    if repo.file_exists(MIGRATION_TRANSACTION_PATH):
        raise ValueError(
            "Workout fulfillment migration recovery is required before normal access"
        )
