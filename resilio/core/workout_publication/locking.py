"""Canonical lock ordering for plan and publication coordination."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from resilio.core.locking import OperationLock
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.repository import RepositoryIO

PUBLICATION_LOCK_PATH = "data/state/.workout-publication.lock"


@contextmanager
def coordinated_publication_plan_lock(
    repo: RepositoryIO,
    operation: str,
) -> Iterator[None]:
    """Hold publication before plan authority everywhere both are required."""
    with OperationLock(repo.resolve_path(PUBLICATION_LOCK_PATH), operation):
        with coordinated_plan_lock(repo, operation):
            yield
