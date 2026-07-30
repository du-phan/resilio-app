"""Traceable primary-methodology contracts for training plans."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrainingMethodology(str, Enum):
    """Supported primary planning systems."""

    DANIELS = "daniels"
    PFITZINGER = "pfitzinger"
    FITZGERALD_80_20 = "fitzgerald_80_20"
    FIRST = "first"


class MethodologyChoice(BaseModel):
    """Coach choice before authoritative source metadata is resolved."""

    identifier: TrainingMethodology
    selection_rationale: str = Field(min_length=40)

    model_config = ConfigDict(extra="forbid")

    @field_validator("selection_rationale")
    @classmethod
    def rationale_must_be_specific(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized.split()) < 7:
            raise ValueError("selection_rationale must state specific athlete evidence")
        return normalized


class MethodologySelection(MethodologyChoice):
    """Resolved source revision bound into a plan revision."""

    source_document: str = Field(
        pattern=r"^docs/training_books/[a-z0-9_]+\.md$",
    )
    source_revision_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_edition: str = Field(min_length=1)
    source_summary_version: date
    source_verification_scope: Literal["conceptual_summary_only"]
    planning_authority: Literal["coach_designed_conceptually_informed"]
    executable_policy_version: Literal["coach_planning_policy_v1"]
