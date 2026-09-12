"""Persisted provenance for external workout calendar placement."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FulfillmentProviderOccurrencePlacement(BaseModel):
    """Exact fulfillment authority temporarily overriding calendar placement."""

    local_activity_id: str = Field(min_length=1)
    fulfillment_association_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_local_date: date

    model_config = ConfigDict(extra="forbid")


class ProviderOccurrencePlacement(BaseModel):
    """Persistent base calendar choice with an optional fulfillment override."""

    calendar_source: Literal["approved_schedule", "provider_calendar"]
    calendar_occurrence_date: date
    fulfillment_override: FulfillmentProviderOccurrencePlacement | None = None

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def approved_schedule(cls, occurrence_date: date) -> "ProviderOccurrencePlacement":
        return cls(
            calendar_source="approved_schedule",
            calendar_occurrence_date=occurrence_date,
        )

    @property
    def effective_occurrence_date(self) -> date:
        override = self.fulfillment_override
        return (
            override.execution_local_date if override is not None else self.calendar_occurrence_date
        )

    def without_fulfillment_override(self) -> "ProviderOccurrencePlacement":
        return self.model_copy(update={"fulfillment_override": None})

    def calendar_is_in_week_of(self, scheduled_local_date: date) -> bool:
        """Return whether the provider base remains in the approved week."""
        calendar_week_start = self.calendar_occurrence_date - timedelta(
            days=self.calendar_occurrence_date.weekday()
        )
        scheduled_week_start = scheduled_local_date - timedelta(days=scheduled_local_date.weekday())
        return calendar_week_start == scheduled_week_start
