"""Revision-bound athlete approval and planning-state contracts."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.plan import MasterPlan, WeekPlan
from resilio.schemas.vdot import RaceDistance


class VDOTEvidenceType(str, Enum):
    RACE_PERFORMANCE = "race_performance"
    PERSONAL_BEST = "personal_best"
    MANUAL_ATHLETE_VALUE = "manual_athlete_value"


class PerformanceVDOTEvidence(BaseModel):
    race_distance: RaceDistance
    elapsed_time_seconds: int = Field(gt=0)
    performance_date: date
    performance_timezone: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("performance_timezone")
    @classmethod
    def performance_timezone_is_iana(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                "performance_timezone must be a recognized IANA timezone"
            ) from exc
        return value


class RacePerformanceVDOTEvidence(PerformanceVDOTEvidence):
    """Race evidence bound to one exact synchronized activity version."""

    evidence_type: Literal["race_performance"]
    source_local_activity_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
    )
    source_external_fingerprint_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )


class PersonalBestVDOTEvidence(PerformanceVDOTEvidence):
    """Personal-best evidence bound to the athlete-confirmed profile record."""

    evidence_type: Literal["personal_best"]


class ManualVDOTEvidence(BaseModel):
    evidence_type: Literal["manual_athlete_value"]
    athlete_confirmed_vdot: int = Field(ge=30, le=85)
    confirmation_reference: str = Field(min_length=10, max_length=500)

    model_config = ConfigDict(extra="forbid")


StructuredVDOTEvidence = Annotated[
    RacePerformanceVDOTEvidence
    | PersonalBestVDOTEvidence
    | ManualVDOTEvidence,
    Field(discriminator="evidence_type"),
]


class VDOTProposal(BaseModel):
    """A reviewable VDOT decision payload whose exact bytes can be approved."""

    schema_version: Literal[1] = 1
    proposed_vdot: int = Field(ge=30, le=85)
    evidence: StructuredVDOTEvidence
    evidence_summary: str = Field(min_length=20, max_length=2_000)
    generated_at_utc: datetime

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("generated_at_utc")
    @classmethod
    def generated_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at_utc must be timezone-aware")
        return value

    @property
    def evidence_type(self) -> VDOTEvidenceType:
        return VDOTEvidenceType(self.evidence.evidence_type)

    @model_validator(mode="after")
    def evidence_precedes_proposal(self) -> "VDOTProposal":
        if (
            isinstance(self.evidence, PerformanceVDOTEvidence)
            and self.evidence.performance_date
            > self.generated_at_utc.astimezone(
                ZoneInfo(self.evidence.performance_timezone)
            ).date()
        ):
            raise ValueError("race performance cannot postdate the proposal")
        return self


class VDOTApproval(BaseModel):
    approval_id: str = Field(pattern=r"^vdot_approval_[a-f0-9]{16}$")
    approved_vdot: int = Field(ge=30, le=85)
    proposal_file: str = Field(min_length=1)
    proposal_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_type: VDOTEvidenceType
    approved_at_utc: datetime

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("approved_at_utc")
    @classmethod
    def approval_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved_at_utc must be timezone-aware")
        return value


class MacroApproval(BaseModel):
    approval_id: str = Field(pattern=r"^macro_approval_[a-f0-9]{16}$")
    plan_id: str
    macro_revision_id: str
    macro_skeleton_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    vdot_approval_id: str
    planning_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("approved_at_utc")
    @classmethod
    def approval_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved_at_utc must be timezone-aware")
        return value


class WeeklyApplicationAction(str, Enum):
    INITIAL = "initial"
    REPLACE = "replace"


class WeeklyApproval(BaseModel):
    approval_id: str = Field(pattern=r"^week_approval_[a-f0-9]{16}$")
    plan_id: str
    macro_revision_id: str
    macro_skeleton_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    week_number: int = Field(ge=1)
    target_week_skeleton_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: WeeklyApplicationAction
    previous_applied_workout_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    approved_at_utc: datetime
    approved_file: str = Field(min_length=1)
    approved_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("approved_at_utc")
    @classmethod
    def approval_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved_at_utc must be timezone-aware")
        return value

    @model_validator(mode="after")
    def replacement_binding_matches_action(self) -> "WeeklyApproval":
        has_previous = self.previous_applied_workout_sha256 is not None
        if self.action == WeeklyApplicationAction.REPLACE and not has_previous:
            raise ValueError("replacement approval requires the previous workout hash")
        if self.action == WeeklyApplicationAction.INITIAL and has_previous:
            raise ValueError("initial approval cannot name a previous workout hash")
        return self


class AppliedWeekRevision(BaseModel):
    """Exact applied week content and its temporal authority interval."""

    approval_id: str
    plan_id: str
    macro_revision_id: str
    week_number: int = Field(ge=1)
    approved_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    applied_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    applied_week_snapshot: WeekPlan
    schedule_timezone: str = Field(min_length=1)
    weekly_approved_at_utc: datetime
    applied_at_utc: datetime
    active: bool = True
    invalidated_at_utc: datetime | None = None
    invalidation_reason: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "weekly_approved_at_utc",
        "applied_at_utc",
        "invalidated_at_utc",
    )
    @classmethod
    def audit_times_are_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("applied approval timestamps must be timezone-aware")
        return value

    @field_validator("schedule_timezone")
    @classmethod
    def schedule_timezone_is_iana(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                "schedule_timezone must be a recognized IANA timezone"
            ) from exc
        return value

    @model_validator(mode="after")
    def invalidation_fields_are_coherent(self) -> "AppliedWeekRevision":
        invalidated = self.invalidated_at_utc is not None
        if self.active == invalidated:
            raise ValueError("active applied approval cannot have invalidation metadata")
        if invalidated != (self.invalidation_reason is not None):
            raise ValueError("applied approval invalidation requires timestamp and reason")
        if self.applied_week_snapshot.week_number != self.week_number:
            raise ValueError("applied week snapshot has another week number")
        if not self.applied_week_snapshot.workouts:
            raise ValueError("applied week snapshot must preserve exact workouts")
        if self.applied_at_utc < self.weekly_approved_at_utc:
            raise ValueError(
                "applied week revision cannot predate its weekly approval"
            )
        if (
            self.invalidated_at_utc is not None
            and self.invalidated_at_utc <= self.applied_at_utc
        ):
            raise ValueError("applied week revision must be invalidated after application")
        return self


class RetiredPlanRevision(BaseModel):
    """Immutable audit record for a superseded macro revision."""

    plan: MasterPlan
    macro_approval: MacroApproval | None = None
    applied_week_revisions: list[AppliedWeekRevision] = Field(default_factory=list)
    retired_at_utc: datetime
    retirement_reason: str = Field(min_length=10, max_length=1_000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("retired_at_utc")
    @classmethod
    def retirement_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retired_at_utc must be timezone-aware")
        return value

    @model_validator(mode="after")
    def approval_lineage_matches_retired_plan(
        self,
    ) -> "RetiredPlanRevision":
        plan = self.plan
        if self.retired_at_utc < plan.created_at_utc:
            raise ValueError("plan revision cannot retire before it was created")
        if self.macro_approval is not None:
            approval = self.macro_approval
            if (
                approval.plan_id != plan.id
                or approval.macro_revision_id != plan.macro_revision_id
                or approval.vdot_approval_id != plan.vdot_approval_id
            ):
                raise ValueError("retired macro approval references another plan lineage")
            if approval.approved_at_utc > self.retired_at_utc:
                raise ValueError("retired macro approval cannot postdate retirement")
            if approval.approved_at_utc < plan.created_at_utc:
                raise ValueError("retired macro approval cannot predate plan creation")
        active_week_numbers: list[int] = []
        for applied_revision in self.applied_week_revisions:
            if (
                applied_revision.plan_id != plan.id
                or applied_revision.macro_revision_id != plan.macro_revision_id
            ):
                raise ValueError("retired applied approval references another plan lineage")
            if applied_revision.applied_at_utc > self.retired_at_utc:
                raise ValueError("retired applied approval cannot postdate retirement")
            if (
                self.macro_approval is not None
                and applied_revision.weekly_approved_at_utc
                < self.macro_approval.approved_at_utc
            ):
                raise ValueError(
                    "retired weekly approval cannot predate macro approval"
                )
            if applied_revision.active:
                active_week_numbers.append(applied_revision.week_number)
        if len(active_week_numbers) != len(set(active_week_numbers)):
            raise ValueError("only one retired applied approval may be active per week")
        return self


class PlanningState(BaseModel):
    """The single atomically persisted plan and approval aggregate."""

    schema_version: Literal[3] = 3
    vdot_approval: VDOTApproval | None = None
    current_plan: MasterPlan | None = None
    macro_approval: MacroApproval | None = None
    pending_weekly_approval: WeeklyApproval | None = None
    applied_week_revisions: list[AppliedWeekRevision] = Field(default_factory=list)
    retired_plan_revisions: list[RetiredPlanRevision] = Field(default_factory=list)
    plan_invalidated_at_utc: datetime | None = None
    plan_invalidation_reason: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("plan_invalidated_at_utc")
    @classmethod
    def invalidation_time_is_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("plan_invalidated_at_utc must be timezone-aware")
        return value

    @model_validator(mode="after")
    def approval_chain_is_coherent(self) -> "PlanningState":
        invalidated = self.plan_invalidated_at_utc is not None
        if invalidated != (self.plan_invalidation_reason is not None):
            raise ValueError("plan invalidation requires both timestamp and reason")
        if self.current_plan is None:
            if (
                self.macro_approval is not None
                or self.pending_weekly_approval is not None
                or self.applied_week_revisions
            ):
                raise ValueError("plan approvals require a current plan")
            if invalidated:
                raise ValueError("plan invalidation requires a current plan")
            return self
        if self.current_plan.vdot_approval_id != (
            self.vdot_approval.approval_id if self.vdot_approval else None
        ):
            raise ValueError("current plan does not reference the active VDOT approval")
        assert self.vdot_approval is not None
        if (
            self.current_plan.created_at_utc
            < self.vdot_approval.approved_at_utc
        ):
            raise ValueError(
                "plan creation cannot predate the active VDOT approval"
            )
        if self.macro_approval is not None:
            self._validate_macro_reference(self.macro_approval)
        if self.pending_weekly_approval is not None:
            if self.macro_approval is None:
                raise ValueError("weekly approval requires macro approval")
            self._validate_week_reference(self.pending_weekly_approval)
        active_week_numbers: list[int] = []
        if self.applied_week_revisions and self.macro_approval is None:
            raise ValueError("applied week revisions require macro approval")
        for approval in self.applied_week_revisions:
            if (
                approval.plan_id != self.current_plan.id
                or approval.macro_revision_id != self.current_plan.macro_revision_id
            ):
                raise ValueError("applied approval references another plan revision")
            assert self.macro_approval is not None
            if approval.weekly_approved_at_utc < self.macro_approval.approved_at_utc:
                raise ValueError(
                    "applied weekly approval cannot predate macro approval"
                )
            if approval.active:
                active_week_numbers.append(approval.week_number)
        if len(active_week_numbers) != len(set(active_week_numbers)):
            raise ValueError("only one applied approval may be active per week")
        return self

    def _validate_macro_reference(self, approval: MacroApproval) -> None:
        assert self.current_plan is not None
        assert self.vdot_approval is not None
        if (
            approval.plan_id != self.current_plan.id
            or approval.macro_revision_id != self.current_plan.macro_revision_id
            or approval.vdot_approval_id != self.vdot_approval.approval_id
        ):
            raise ValueError("macro approval references another planning revision")
        if approval.approved_at_utc < self.current_plan.created_at_utc:
            raise ValueError("macro approval cannot predate plan creation")

    def _validate_week_reference(self, approval: WeeklyApproval) -> None:
        assert self.current_plan is not None
        assert self.macro_approval is not None
        if (
            approval.plan_id != self.current_plan.id
            or approval.macro_revision_id != self.current_plan.macro_revision_id
            or approval.macro_skeleton_sha256 != self.macro_approval.macro_skeleton_sha256
        ):
            raise ValueError("weekly approval references another planning revision")
        if approval.approved_at_utc < self.macro_approval.approved_at_utc:
            raise ValueError("weekly approval cannot predate macro approval")
