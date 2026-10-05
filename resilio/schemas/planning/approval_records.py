"""Exact approvals and immutable history for amendments within a race cycle."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.plan_history import EvidenceArtifactReference
from resilio.schemas.planning.plans import RaceMacroPlan


class PlanApproval(BaseModel):
    approval_id: str = Field(pattern=r"^plan_approval_[a-f0-9]{16}$")
    plan_kind: Literal["race_macro", "baseline_assessment"]
    plan_id: str
    plan_revision_id: str
    plan_skeleton_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    vdot_approval_id: str | None = Field(
        default=None,
        pattern=r"^vdot_approval_[a-f0-9]{16}$",
    )
    planning_inputs_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("approved_at_utc")
    @classmethod
    def approval_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved_at_utc must be timezone-aware")
        return value

    @model_validator(mode="after")
    def vdot_binding_matches_plan_kind(self) -> "PlanApproval":
        if self.plan_kind == "race_macro" and self.vdot_approval_id is None:
            raise ValueError("race plan approval requires a VDOT approval")
        if self.plan_kind == "baseline_assessment" and self.vdot_approval_id is not None:
            raise ValueError("assessment plan approval cannot depend on VDOT")
        return self


class MacroAmendmentAudit(BaseModel):
    """A new approval retaining the entire previous approved macro snapshot."""

    amendment_id: str = Field(pattern=r"^macro_amendment_[a-f0-9]{16}$")
    previous_plan: RaceMacroPlan
    previous_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_amendment_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    previous_plan_approval: PlanApproval
    approval: PlanApproval
    approved_file: str = Field(min_length=1)
    approved_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_active_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    planning_context_references: list[EvidenceArtifactReference] = Field(min_length=1)
    affected_week_numbers: list[int] = Field(min_length=1)
    rationale: str = Field(min_length=40, max_length=4_000)
    athlete_confirmation_reference: str = Field(min_length=10, max_length=1_000)
    applied_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def amendment_follows_original_approval(self) -> "MacroAmendmentAudit":
        if self.applied_at_utc.tzinfo is None or self.applied_at_utc.utcoffset() is None:
            raise ValueError("amendment application timestamp must be timezone-aware")
        if self.previous_plan_approval.approved_at_utc >= self.approval.approved_at_utc:
            raise ValueError("amendment approval must follow previous macro approval")
        if self.applied_at_utc < self.approval.approved_at_utc:
            raise ValueError("amendment application cannot predate its approval")
        for approval in (self.previous_plan_approval, self.approval):
            if (
                approval.plan_id != self.previous_plan.id
                or approval.plan_revision_id != self.previous_plan.plan_revision_id
                or approval.plan_kind != "race_macro"
                or approval.vdot_approval_id != self.previous_plan.vdot_approval_id
                or approval.planning_inputs_sha256 != self.previous_plan.planning_inputs_sha256
            ):
                raise ValueError("amendment must retain the exact race-cycle lineage and inputs")
        if len(self.affected_week_numbers) != len(set(self.affected_week_numbers)):
            raise ValueError("amendment week numbers must be unique")
        if any(
            ref.artifact_type != "week_planning_context" for ref in self.planning_context_references
        ):
            raise ValueError("amendment requires week-planning evidence")
        return self
