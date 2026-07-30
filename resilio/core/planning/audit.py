"""Shared planning audit timestamps and collision-resistant identities."""

import uuid
from datetime import datetime, timezone

from resilio.core.planning.errors import PlanOperationError


def validated_utc_timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PlanOperationError("Planning timestamps must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def new_planning_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"
