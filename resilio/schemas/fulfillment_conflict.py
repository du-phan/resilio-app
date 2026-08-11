"""Durable contradictions that suspend workout-fulfillment evidence."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UnresolvedFulfillmentConflict(BaseModel):
    """One synchronized provider contradiction awaiting athlete resolution."""

    local_activity_id: str = Field(min_length=1)
    rule: str = Field(pattern=r"^(paired_event|fulfilled_activity)_[a-z0-9_]+$")
    provider_event_id_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    observed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("observed_at_utc")
    @classmethod
    def observation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)
