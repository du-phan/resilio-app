"""Strict fulfillment-v1 contracts used only by the native-pairing cutover."""

from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.canonical import canonical_data_sha256
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    FulfillmentActivityEvidenceRevision,
    UnresolvedFulfillmentConflict,
    WorkoutFulfillmentCandidateDismissal,
    WorkoutFulfillmentRecord,
)


class LegacyV1ProviderPairEvidence(BaseModel):
    event_id: int = Field(gt=0)
    observed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("observed_at_utc")
    @classmethod
    def observation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


class LegacyV1WithdrawnProviderPairEvidence(BaseModel):
    provider_pair: LegacyV1ProviderPairEvidence
    reason: Literal["provider_pair_removed"]
    withdrawn_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("withdrawn_at_utc")
    @classmethod
    def withdrawal_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("withdrawn_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


class LegacyV1WorkoutFulfillmentRecord(BaseModel):
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
    provider_pair: LegacyV1ProviderPairEvidence | None = None
    athlete_confirmation: AthleteConfirmedFulfillmentEvidence | None = None
    withdrawn_provider_pairs: list[LegacyV1WithdrawnProviderPairEvidence] = Field(
        default_factory=list
    )
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
    def evidence_and_dates_are_coherent(self) -> "LegacyV1WorkoutFulfillmentRecord":
        if self.provider_pair is None and self.athlete_confirmation is None:
            raise ValueError("fulfillment requires at least one evidence source")
        expected_offset_days = (self.execution_local_date - self.scheduled_local_date).days
        if self.schedule_offset_days != expected_offset_days:
            raise ValueError("schedule_offset_days must match fulfillment dates")
        if self.athlete_confirmation is not None and self.provider_pair is None:
            scheduled_week_start = (
                self.scheduled_local_date.toordinal() - self.scheduled_local_date.weekday()
            )
            execution_week_start = (
                self.execution_local_date.toordinal() - self.execution_local_date.weekday()
            )
            if scheduled_week_start != execution_week_start:
                raise ValueError("athlete-confirmed dates must fall in one training week")
        previous_withdrawn_at_utc: datetime | None = None
        for withdrawal in self.withdrawn_provider_pairs:
            if (
                previous_withdrawn_at_utc is not None
                and withdrawal.withdrawn_at_utc <= previous_withdrawn_at_utc
            ):
                raise ValueError(
                    "provider pair withdrawal timestamps must be strictly increasing"
                )
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
                expected_previous_sha256 = (
                    revision.replacement_activity_performance_evidence_sha256
                )
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


class LegacyV1HistoricalWorkoutFulfillment(BaseModel):
    local_activity_id: str = Field(min_length=1)
    workout_identity: PlanWorkoutIdentity
    activity_performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scheduled_local_date: date
    execution_local_date: date
    schedule_offset_days: int
    provider_pair: LegacyV1ProviderPairEvidence
    matched_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("matched_at_utc")
    @classmethod
    def matched_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("matched_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def schedule_offset_matches_dates(self) -> "LegacyV1HistoricalWorkoutFulfillment":
        if self.schedule_offset_days != (
            self.execution_local_date - self.scheduled_local_date
        ).days:
            raise ValueError("historical fulfillment offset must match its exact dates")
        return self


class LegacyV1WorkoutFulfillmentRevocation(BaseModel):
    revocation_id: str = Field(pattern=r"^fulfillment_revocation_[0-9a-f]{16}$")
    fulfillment: LegacyV1WorkoutFulfillmentRecord
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


class LegacyV1WorkoutFulfillmentManifest(BaseModel):
    schema_version: Literal[1] = 1
    fulfillments: dict[str, LegacyV1WorkoutFulfillmentRecord] = Field(
        default_factory=dict
    )
    dismissed_candidates: dict[str, WorkoutFulfillmentCandidateDismissal] = Field(
        default_factory=dict
    )
    historical_legacy_fulfillments: dict[
        str,
        LegacyV1HistoricalWorkoutFulfillment,
    ] = Field(default_factory=dict)
    revoked_fulfillments: list[LegacyV1WorkoutFulfillmentRevocation] = Field(
        default_factory=list
    )
    unresolved_fulfillment_conflicts: dict[
        str,
        UnresolvedFulfillmentConflict,
    ] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def identities_are_unique(self) -> "LegacyV1WorkoutFulfillmentManifest":
        workout_owners: dict[tuple[str, str, int, str], str] = {}

        def claim_workout(
            local_activity_id: str,
            record: (
                LegacyV1WorkoutFulfillmentRecord
                | LegacyV1HistoricalWorkoutFulfillment
            ),
        ) -> None:
            if record.local_activity_id != local_activity_id:
                raise ValueError("fulfillment manifest key must match local activity ID")
            identity = record.workout_identity
            identity_key = (
                identity.plan_id,
                identity.plan_revision_id,
                identity.week_number,
                identity.local_workout_id,
            )
            if workout_owners.setdefault(identity_key, local_activity_id) != local_activity_id:
                raise ValueError("one workout cannot fulfill multiple activities")

        for local_activity_id, active_record in self.fulfillments.items():
            claim_workout(local_activity_id, active_record)
        for local_activity_id, historical_record in (
            self.historical_legacy_fulfillments.items()
        ):
            if local_activity_id in self.fulfillments:
                raise ValueError("historical fulfillment cannot also remain active")
            claim_workout(local_activity_id, historical_record)
        if any(
            dismissal.candidate_sha256 != candidate_sha256
            for candidate_sha256, dismissal in self.dismissed_candidates.items()
        ):
            raise ValueError("dismissal manifest key must match candidate SHA-256")
        revocation_ids = [item.revocation_id for item in self.revoked_fulfillments]
        if len(revocation_ids) != len(set(revocation_ids)):
            raise ValueError("fulfillment revocation IDs must be unique")
        if any(
            conflict.local_activity_id != local_activity_id
            for local_activity_id, conflict in self.unresolved_fulfillment_conflicts.items()
        ):
            raise ValueError("fulfillment conflict key must match local activity ID")
        return self


def migrate_legacy_v1_manifest(
    raw: dict[str, object],
    *,
    activities_by_local_id: dict[str, CanonicalActivity],
) -> tuple[dict[str, object], dict[str, str]]:
    """Validate v1 exactly, then add only evidence available at cutover."""
    legacy = LegacyV1WorkoutFulfillmentManifest.model_validate(raw)
    fulfillment_sha256_by_activity_id = {
        local_activity_id: canonical_data_sha256(record)
        for local_activity_id, record in legacy.fulfillments.items()
    }
    migrated = legacy.model_dump(mode="json")
    for raw_revocation in migrated["revoked_fulfillments"]:
        assert isinstance(raw_revocation, dict)
        fulfillment = raw_revocation["fulfillment"]
        assert isinstance(fulfillment, dict)
        local_activity_id = str(fulfillment["local_activity_id"])
        activity = activities_by_local_id.get(local_activity_id)
        external_activity_id = None
        if activity is not None:
            external_activity_id = activity.origin.intervals_icu_activity_id
        raw_revocation["intervals_icu_activity_id"] = external_activity_id
    return migrated, fulfillment_sha256_by_activity_id


def legacy_v1_fulfillment_sha256(record: WorkoutFulfillmentRecord) -> str:
    """Reproduce the exact pre-cutover hash from a translated v2 record."""
    payload = record.model_dump(mode="json")

    def remove_provenance(value: object, *, field_name: str | None = None) -> object:
        if isinstance(value, list):
            return [remove_provenance(item) for item in value]
        if not isinstance(value, dict):
            return value
        return {
            key: remove_provenance(item, field_name=key)
            for key, item in value.items()
            if not (field_name == "provider_pair" and key == "provenance")
        }

    legacy_payload = remove_provenance(payload)
    if not isinstance(legacy_payload, dict):
        raise TypeError("legacy fulfillment projection must remain an object")
    return canonical_data_sha256(legacy_payload)
