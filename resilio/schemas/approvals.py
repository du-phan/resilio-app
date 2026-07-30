"""Revision-bound athlete approval and planning-state contracts."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.plan import MasterPlan, WeekPlan
from resilio.schemas.plan_history import (
    ClosedPlanCycleReference,
    PlanClosure,
)
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
            raise ValueError("performance_timezone must be a recognized IANA timezone") from exc
        return value


class RacePerformanceVDOTEvidence(PerformanceVDOTEvidence):
    """Race evidence bound to one exact synchronized activity version."""

    evidence_type: Literal["race_performance"]
    source_local_activity_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    source_external_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PersonalBestVDOTEvidence(PerformanceVDOTEvidence):
    """Personal-best evidence bound to the athlete-confirmed profile record."""

    evidence_type: Literal["personal_best"]


class ManualVDOTEvidence(BaseModel):
    evidence_type: Literal["manual_athlete_value"]
    athlete_confirmed_vdot: int = Field(ge=30, le=85)
    confirmation_reference: str = Field(min_length=10, max_length=500)

    model_config = ConfigDict(extra="forbid")


StructuredVDOTEvidence = Annotated[
    RacePerformanceVDOTEvidence | PersonalBestVDOTEvidence | ManualVDOTEvidence,
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
            > self.generated_at_utc.astimezone(ZoneInfo(self.evidence.performance_timezone)).date()
        ):
            raise ValueError("race performance cannot postdate the proposal")
        return self


class VDOTApproval(BaseModel):
    approval_id: str = Field(pattern=r"^vdot_approval_[a-f0-9]{16}$")
    approved_vdot: int = Field(ge=30, le=85)
    proposal_file: str = Field(min_length=1)
    proposal_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_type: VDOTEvidenceType
    proposal_snapshot: VDOTProposal
    approved_at_utc: datetime

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("approved_at_utc")
    @classmethod
    def approval_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved_at_utc must be timezone-aware")
        return value

    @model_validator(mode="after")
    def proposal_snapshot_matches_approval(self) -> "VDOTApproval":
        if self.proposal_snapshot.proposed_vdot != self.approved_vdot:
            raise ValueError("VDOT approval value must match its proposal snapshot")
        if self.proposal_snapshot.evidence_type != self.evidence_type:
            raise ValueError("VDOT approval evidence type must match its proposal snapshot")
        if self.approved_at_utc < self.proposal_snapshot.generated_at_utc:
            raise ValueError("VDOT approval cannot predate its proposal snapshot")
        return self


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
            raise ValueError("schedule_timezone must be a recognized IANA timezone") from exc
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
            raise ValueError("applied week revision cannot predate its weekly approval")
        if self.invalidated_at_utc is not None and self.invalidated_at_utc <= self.applied_at_utc:
            raise ValueError("applied week revision must be invalidated after application")
        return self


class ActivePlanState(BaseModel):
    """The complete mutable state for the one active plan revision."""

    plan: MasterPlan
    macro_approval: MacroApproval | None = None
    pending_weekly_approval: WeeklyApproval | None = None
    applied_week_revisions: list[AppliedWeekRevision] = Field(default_factory=list)
    invalidated_at_utc: datetime | None = None
    invalidation_reason: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("invalidated_at_utc")
    @classmethod
    def invalidation_time_is_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("invalidated_at_utc must be timezone-aware")
        return value

    @model_validator(mode="after")
    def approval_chain_is_coherent(self) -> "ActivePlanState":
        invalidated = self.invalidated_at_utc is not None
        if invalidated != (self.invalidation_reason is not None):
            raise ValueError("plan invalidation requires timestamp and reason")
        if self.macro_approval is not None:
            self._validate_macro_reference(self.macro_approval)
        if self.pending_weekly_approval is not None:
            if self.macro_approval is None:
                raise ValueError("weekly approval requires macro approval")
            self._validate_week_reference(self.pending_weekly_approval)
        if self.applied_week_revisions and self.macro_approval is None:
            raise ValueError("applied week revisions require macro approval")
        active_week_numbers: list[int] = []
        for approval in self.applied_week_revisions:
            if (
                approval.plan_id != self.plan.id
                or approval.macro_revision_id != self.plan.macro_revision_id
            ):
                raise ValueError("applied approval references another plan revision")
            assert self.macro_approval is not None
            if approval.weekly_approved_at_utc < self.macro_approval.approved_at_utc:
                raise ValueError("applied weekly approval cannot predate macro approval")
            if approval.active:
                active_week_numbers.append(approval.week_number)
        if len(active_week_numbers) != len(set(active_week_numbers)):
            raise ValueError("only one applied approval may be active per week")
        return self

    def _validate_macro_reference(self, approval: MacroApproval) -> None:
        if (
            approval.plan_id != self.plan.id
            or approval.macro_revision_id != self.plan.macro_revision_id
            or approval.vdot_approval_id != self.plan.vdot_approval_id
        ):
            raise ValueError("macro approval references another planning revision")
        if approval.approved_at_utc < self.plan.created_at_utc:
            raise ValueError("macro approval cannot predate plan creation")

    def _validate_week_reference(self, approval: WeeklyApproval) -> None:
        assert self.macro_approval is not None
        if (
            approval.plan_id != self.plan.id
            or approval.macro_revision_id != self.plan.macro_revision_id
            or approval.macro_skeleton_sha256 != self.macro_approval.macro_skeleton_sha256
        ):
            raise ValueError("weekly approval references another planning revision")
        if approval.approved_at_utc < self.macro_approval.approved_at_utc:
            raise ValueError("weekly approval cannot predate macro approval")


class ClosedPlanCycle(BaseModel):
    """Immutable archived active-plan state plus confirmed closure facts."""

    schema_version: Literal[1] = 1
    active_plan_snapshot: ActivePlanState
    closure: PlanClosure

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def closure_follows_plan_history(self) -> "ClosedPlanCycle":
        snapshot = self.active_plan_snapshot
        latest_timestamp = snapshot.plan.created_at_utc
        if snapshot.macro_approval is not None:
            latest_timestamp = max(
                latest_timestamp,
                snapshot.macro_approval.approved_at_utc,
            )
        for revision in snapshot.applied_week_revisions:
            latest_timestamp = max(latest_timestamp, revision.applied_at_utc)
            if revision.invalidated_at_utc is not None:
                latest_timestamp = max(latest_timestamp, revision.invalidated_at_utc)
        if self.closure.closed_at_utc < latest_timestamp:
            raise ValueError("plan closure cannot predate its recorded plan history")
        return self


class PlanningState(BaseModel):
    """Compact active state with immutable plan-history references."""

    schema_version: Literal[4] = 4
    vdot_approvals: list[VDOTApproval] = Field(default_factory=list)
    active_vdot_approval_id: str | None = None
    active_plan: ActivePlanState | None = None
    closed_plan_cycle_references: list[ClosedPlanCycleReference] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def state_references_are_coherent(self) -> "PlanningState":
        approval_ids = [approval.approval_id for approval in self.vdot_approvals]
        if len(approval_ids) != len(set(approval_ids)):
            raise ValueError("VDOT approval identities must be unique")
        if self.active_vdot_approval_id is not None:
            if self.active_vdot_approval_id not in set(approval_ids):
                raise ValueError("active VDOT approval ID is absent from approval history")
        elif approval_ids:
            raise ValueError("VDOT approval history requires one active approval ID")
        if self.active_plan is not None:
            if self.active_vdot_approval_id is None:
                raise ValueError("active plan requires an active VDOT approval")
            if self.active_plan.plan.vdot_approval_id != self.active_vdot_approval_id:
                raise ValueError("active plan references another VDOT approval")
            approval = self.active_vdot_approval
            assert approval is not None
            if self.active_plan.plan.created_at_utc < approval.approved_at_utc:
                raise ValueError("plan creation cannot predate its VDOT approval")
        plan_ids = [reference.plan_id for reference in self.closed_plan_cycle_references]
        macro_revision_ids = [
            reference.macro_revision_id for reference in self.closed_plan_cycle_references
        ]
        if len(plan_ids) != len(set(plan_ids)):
            raise ValueError("closed plan cycle IDs must be unique")
        if len(macro_revision_ids) != len(set(macro_revision_ids)):
            raise ValueError("closed macro revision IDs must be unique")
        if self.active_plan is not None:
            if self.active_plan.plan.id in set(plan_ids):
                raise ValueError("active plan cannot also be a closed cycle")
            if self.active_plan.plan.macro_revision_id in set(macro_revision_ids):
                raise ValueError("active macro revision cannot also be a closed cycle")
        return self

    @property
    def active_vdot_approval(self) -> VDOTApproval | None:
        if self.active_vdot_approval_id is None:
            return None
        return next(
            approval
            for approval in self.vdot_approvals
            if approval.approval_id == self.active_vdot_approval_id
        )
