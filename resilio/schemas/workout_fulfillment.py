"""Exact evidence that one canonical activity fulfilled one approved run."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.plan_history import PlanWorkoutIdentity


class ProviderPairedFulfillmentEvidence(BaseModel):
    """Intervals.icu's exact pairing between an activity and an owned event."""

    event_id: int = Field(gt=0)
    observed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("observed_at_utc")
    @classmethod
    def observed_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


class WithdrawnProviderPairEvidence(BaseModel):
    """Exact provider pair withdrawn by a later synchronized observation."""

    provider_pair: ProviderPairedFulfillmentEvidence
    reason: Literal["provider_pair_removed"]
    withdrawn_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("withdrawn_at_utc")
    @classmethod
    def withdrawal_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("withdrawn_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


class AthleteConfirmedFulfillmentEvidence(BaseModel):
    """Athlete authority for one exact proposed activity/workout association."""

    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    athlete_confirmation_reference: str = Field(min_length=1, max_length=2_000)
    coaching_rationale: str = Field(min_length=20, max_length=2_000)
    confirmed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("confirmed_at_utc")
    @classmethod
    def confirmation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


FulfillmentBasis = Literal[
    "provider_paired",
    "athlete_confirmed",
    "provider_paired_and_athlete_confirmed",
]

FulfillmentTiming = Literal["early", "on_schedule", "late"]


class WorkoutFulfillmentCandidate(BaseModel):
    """Read-only exact facts offered for athlete confirmation."""

    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_activity_id: str = Field(min_length=1)
    workout_identity: PlanWorkoutIdentity
    applied_week_approval_id: str = Field(pattern=r"^week_approval_[a-f0-9]{16}$")
    applied_running_workouts_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workout_prescription_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    activity_performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_timezone: str = Field(min_length=1)
    scheduled_local_date: date
    execution_local_date: date
    schedule_offset_days: int = Field(ge=-6, le=6)
    timing: FulfillmentTiming
    workout_type: str = Field(min_length=1)
    workout_purpose: str = Field(min_length=1)
    planned_distance_meters: float = Field(gt=0, allow_inf_nan=False)
    planned_duration_seconds: int = Field(gt=0)
    activity_distance_meters: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    activity_elapsed_duration_seconds: int = Field(ge=0)
    activity_moving_duration_seconds: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def dates_and_timing_are_coherent(self) -> "WorkoutFulfillmentCandidate":
        expected_offset_days = (self.execution_local_date - self.scheduled_local_date).days
        if self.schedule_offset_days != expected_offset_days:
            raise ValueError("schedule_offset_days must equal execution date minus scheduled date")
        expected_timing: FulfillmentTiming = (
            "early"
            if expected_offset_days < 0
            else "late"
            if expected_offset_days > 0
            else "on_schedule"
        )
        if self.timing != expected_timing:
            raise ValueError("timing must match schedule_offset_days")
        return self


class FulfillmentActivityEvidenceRevision(BaseModel):
    """Provider-observed canonical activity correction after association approval."""

    previous_activity_performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replacement_activity_performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_execution_local_date: date
    replacement_execution_local_date: date
    observed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("observed_at_utc")
    @classmethod
    def observed_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def correction_changes_activity_evidence(
        self,
    ) -> "FulfillmentActivityEvidenceRevision":
        if (
            self.previous_activity_performance_evidence_sha256
            == self.replacement_activity_performance_evidence_sha256
            and self.previous_execution_local_date == self.replacement_execution_local_date
        ):
            raise ValueError("activity evidence revision must change evidence or execution date")
        return self


class WorkoutFulfillmentRecord(BaseModel):
    """Immutable identity and evidence for one fulfilled approved workout."""

    local_activity_id: str = Field(min_length=1)
    workout_identity: PlanWorkoutIdentity
    applied_week_approval_id: str = Field(pattern=r"^week_approval_[a-f0-9]{16}$")
    applied_running_workouts_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workout_prescription_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    activity_performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_timezone: str = Field(min_length=1)
    scheduled_local_date: date
    execution_local_date: date
    schedule_offset_days: int
    provider_pair: ProviderPairedFulfillmentEvidence | None = None
    athlete_confirmation: AthleteConfirmedFulfillmentEvidence | None = None
    withdrawn_provider_pairs: list[WithdrawnProviderPairEvidence] = Field(default_factory=list)
    activity_evidence_revisions: list[FulfillmentActivityEvidenceRevision] = Field(
        default_factory=list
    )
    recorded_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("schedule_timezone")
    @classmethod
    def schedule_timezone_is_iana(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("schedule_timezone must be a recognized IANA timezone") from exc
        return value

    @field_validator("recorded_at_utc")
    @classmethod
    def recorded_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def evidence_and_dates_are_coherent(self) -> "WorkoutFulfillmentRecord":
        if self.provider_pair is None and self.athlete_confirmation is None:
            raise ValueError("fulfillment requires at least one evidence source")
        expected_offset_days = (self.execution_local_date - self.scheduled_local_date).days
        if self.schedule_offset_days != expected_offset_days:
            raise ValueError("schedule_offset_days must equal execution date minus scheduled date")
        if self.athlete_confirmation is not None and self.provider_pair is None:
            scheduled_week_start = (
                self.scheduled_local_date.toordinal() - self.scheduled_local_date.weekday()
            )
            execution_week_start = (
                self.execution_local_date.toordinal() - self.execution_local_date.weekday()
            )
            if scheduled_week_start != execution_week_start:
                raise ValueError(
                    "athlete-confirmed fulfillment dates must fall in one training week"
                )
        previous_withdrawn_at_utc: datetime | None = None
        for withdrawal in self.withdrawn_provider_pairs:
            if (
                previous_withdrawn_at_utc is not None
                and withdrawal.withdrawn_at_utc <= previous_withdrawn_at_utc
            ):
                raise ValueError("provider pair withdrawal timestamps must be strictly increasing")
            previous_withdrawn_at_utc = withdrawal.withdrawn_at_utc
        if self.activity_evidence_revisions:
            expected_previous_sha256 = self.activity_evidence_revisions[
                0
            ].previous_activity_performance_evidence_sha256
            expected_previous_date = self.activity_evidence_revisions[
                0
            ].previous_execution_local_date
            previous_observed_at_utc: datetime | None = None
            for revision in self.activity_evidence_revisions:
                if (
                    revision.previous_activity_performance_evidence_sha256
                    != expected_previous_sha256
                    or revision.previous_execution_local_date != expected_previous_date
                ):
                    raise ValueError("activity evidence revision chain must be continuous")
                if (
                    previous_observed_at_utc is not None
                    and revision.observed_at_utc <= previous_observed_at_utc
                ):
                    raise ValueError(
                        "activity evidence revision timestamps must be strictly increasing"
                    )
                expected_previous_sha256 = revision.replacement_activity_performance_evidence_sha256
                expected_previous_date = revision.replacement_execution_local_date
                previous_observed_at_utc = revision.observed_at_utc
            if (
                expected_previous_sha256 != self.activity_performance_evidence_sha256
                or expected_previous_date != self.execution_local_date
            ):
                raise ValueError(
                    "activity evidence revision chain must end at current activity evidence"
                )
        return self

    @property
    def fulfillment_basis(self) -> FulfillmentBasis:
        if self.provider_pair is not None and self.athlete_confirmation is not None:
            return "provider_paired_and_athlete_confirmed"
        if self.provider_pair is not None:
            return "provider_paired"
        return "athlete_confirmed"

    @property
    def has_provider_pair_evidence(self) -> bool:
        """Whether exact provider pairing was observed."""
        return self.provider_pair is not None

    def provider_pair_supports_event(self, event_id: int) -> bool:
        """Prove exact provider event linkage."""
        return self.provider_pair is not None and self.provider_pair.event_id == event_id


class WorkoutFulfillmentCandidateDismissal(BaseModel):
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_activity_id: str = Field(min_length=1)
    workout_identity: PlanWorkoutIdentity
    athlete_response_reference: str = Field(min_length=1, max_length=2_000)
    dismissed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("dismissed_at_utc")
    @classmethod
    def dismissal_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("dismissed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


class HistoricalLegacyWorkoutFulfillment(BaseModel):
    """Read-only exact provider pair whose applied workout authority is unavailable."""

    local_activity_id: str = Field(min_length=1)
    workout_identity: PlanWorkoutIdentity
    activity_performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scheduled_local_date: date
    execution_local_date: date
    schedule_offset_days: int
    provider_pair: ProviderPairedFulfillmentEvidence
    matched_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("matched_at_utc")
    @classmethod
    def matched_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("matched_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def schedule_offset_matches_dates(self) -> "HistoricalLegacyWorkoutFulfillment":
        if (
            self.schedule_offset_days
            != (self.execution_local_date - self.scheduled_local_date).days
        ):
            raise ValueError("historical fulfillment offset must match its exact dates")
        return self


class WorkoutFulfillmentRevocation(BaseModel):
    """Athlete-authorized withdrawal of one previously accepted association."""

    revocation_id: str = Field(pattern=r"^fulfillment_revocation_[0-9a-f]{16}$")
    fulfillment: WorkoutFulfillmentRecord
    reason: Literal[
        "activity_deleted",
        "activity_reclassified",
        "association_incorrect",
    ]
    athlete_confirmation_reference: str = Field(min_length=1, max_length=2_000)
    coaching_rationale: str = Field(min_length=20, max_length=2_000)
    revoked_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("revoked_at_utc")
    @classmethod
    def revocation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("revoked_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


class UnresolvedFulfillmentConflict(BaseModel):
    """Durable synchronized contradiction that suspends fulfillment evidence."""

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


class WorkoutFulfillmentManifest(BaseModel):
    schema_version: Literal[1] = 1
    fulfillments: dict[str, WorkoutFulfillmentRecord] = Field(default_factory=dict)
    dismissed_candidates: dict[str, WorkoutFulfillmentCandidateDismissal] = Field(
        default_factory=dict
    )
    historical_legacy_fulfillments: dict[
        str,
        HistoricalLegacyWorkoutFulfillment,
    ] = Field(default_factory=dict)
    revoked_fulfillments: list[WorkoutFulfillmentRevocation] = Field(default_factory=list)
    unresolved_fulfillment_conflicts: dict[
        str,
        UnresolvedFulfillmentConflict,
    ] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def identities_are_unique(self) -> "WorkoutFulfillmentManifest":
        workout_owners: dict[tuple[str, str, int, str], str] = {}
        for local_activity_id, record in self.fulfillments.items():
            if record.local_activity_id != local_activity_id:
                raise ValueError("fulfillment manifest key must match local activity ID")
            identity = record.workout_identity
            identity_key = (
                identity.plan_id,
                identity.plan_revision_id,
                identity.week_number,
                identity.local_workout_id,
            )
            prior_activity_id = workout_owners.setdefault(identity_key, local_activity_id)
            if prior_activity_id != local_activity_id:
                raise ValueError("one workout cannot fulfill multiple activities")
        for candidate_sha256, dismissal in self.dismissed_candidates.items():
            if dismissal.candidate_sha256 != candidate_sha256:
                raise ValueError("dismissal manifest key must match candidate SHA-256")
        for local_activity_id, historical_record in self.historical_legacy_fulfillments.items():
            if historical_record.local_activity_id != local_activity_id:
                raise ValueError("historical fulfillment key must match local activity ID")
            if local_activity_id in self.fulfillments:
                raise ValueError("historical fulfillment cannot also remain active")
            identity = historical_record.workout_identity
            identity_key = (
                identity.plan_id,
                identity.plan_revision_id,
                identity.week_number,
                identity.local_workout_id,
            )
            prior_activity_id = workout_owners.setdefault(
                identity_key,
                local_activity_id,
            )
            if prior_activity_id != local_activity_id:
                raise ValueError("one workout cannot fulfill multiple activities")
        revocation_ids: set[str] = set()
        for revocation in self.revoked_fulfillments:
            if revocation.revocation_id in revocation_ids:
                raise ValueError("fulfillment revocation IDs must be unique")
            revocation_ids.add(revocation.revocation_id)
        for local_activity_id, conflict in self.unresolved_fulfillment_conflicts.items():
            if conflict.local_activity_id != local_activity_id:
                raise ValueError("fulfillment conflict key must match local activity ID")
        return self


class WorkoutFulfillmentWeekStatus(BaseModel):
    """Exact fulfillment overlay for one applied training week."""

    week_number: int = Field(ge=1)
    fulfilled: list[WorkoutFulfillmentRecord] = Field(default_factory=list)
    outstanding_workout_identities: list[PlanWorkoutIdentity] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
