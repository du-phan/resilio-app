"""Shared strict validation primitives for the fulfillment cutover."""

from datetime import datetime, timezone


class WorkoutFulfillmentMigrationError(RuntimeError):
    """Persisted state cannot be transformed without losing exact authority."""


def parse_aware_legacy_datetime(value: object, *, field_name: str) -> datetime:
    """Parse an audit time without consulting the host machine timezone."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            f"Legacy {field_name} is not a valid timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkoutFulfillmentMigrationError(
            f"Legacy {field_name} must be timezone-aware"
        )
    return parsed.astimezone(timezone.utc)
