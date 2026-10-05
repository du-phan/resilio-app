"""Fail-closed gate while the coordinated state cutover is incomplete."""

from resilio.core.repository import RepositoryIO

MIGRATION_TRANSACTION_PATH = "data/state/state-migration.json"


def assert_state_migration_is_complete(repo: RepositoryIO) -> None:
    """Reject normal state access until crash recovery completes the cutover."""
    if repo.file_exists(MIGRATION_TRANSACTION_PATH):
        raise ValueError("State migration recovery is required before normal access")
