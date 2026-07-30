"""Resolve methodology choices against repository-owned source documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from resilio.core.planning.policy import PLANNING_POLICY_VERSION
from resilio.schemas.methodology import (
    MethodologyChoice,
    MethodologySelection,
    TrainingMethodology,
)


@dataclass(frozen=True)
class MethodologyDefinition:
    source_document: str
    expected_source_sha256: str
    source_edition: str
    source_summary_version: date = date(2026, 7, 30)
    source_verification_scope: Literal[
        "conceptual_summary_only"
    ] = "conceptual_summary_only"
    planning_authority: Literal[
        "coach_designed_conceptually_informed"
    ] = "coach_designed_conceptually_informed"
    executable_policy_version: Literal[
        "coach_planning_policy_v1"
    ] = PLANNING_POLICY_VERSION


METHODOLOGY_DEFINITIONS: dict[TrainingMethodology, MethodologyDefinition] = {
    TrainingMethodology.DANIELS: MethodologyDefinition(
        source_document="docs/training_books/daniels_running_formula.md",
        expected_source_sha256=(
            "dc67bdfe2af85dce6176fb32ff7acedd23561b2904fd35a16f7e01f9ab12ea0b"
        ),
        source_edition="fourth_edition_conceptual_reference",
    ),
    TrainingMethodology.PFITZINGER: MethodologyDefinition(
        source_document=(
            "docs/training_books/advanced_marathoning_pete_pfitzinger.md"
        ),
        expected_source_sha256=(
            "0df233e119b7c054aa3b9fceb5a7b4ad245c1ef572f5957fa3e638f52fc53b45"
        ),
        source_edition="edition_unverified",
    ),
    TrainingMethodology.FITZGERALD_80_20: MethodologyDefinition(
        source_document="docs/training_books/80_20_matt_fitzgerald.md",
        expected_source_sha256=(
            "730c1c396b1762eb4e878831712368f3148c1bbcb6a7e1c19ca57dc8511d8c47"
        ),
        source_edition="edition_unverified",
    ),
    TrainingMethodology.FIRST: MethodologyDefinition(
        source_document=(
            "docs/training_books/run_less_run_faster_bill_pierce.md"
        ),
        expected_source_sha256=(
            "557cc794dfc2c26e0b0565236876849908e34e41252ff154ca0a8a8ab998ecd8"
        ),
        source_edition="edition_unverified",
    ),
}


class MethodologyRegistryError(RuntimeError):
    """A registered methodology source could not be proven current."""


def _source_sha256(repo_root: Path, source_document: str) -> str:
    source_path = repo_root / source_document
    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise MethodologyRegistryError(
            f"Methodology source is unavailable: {source_document}"
        ) from exc
    return hashlib.sha256(source_bytes).hexdigest()


def _verified_definition(
    repo_root: Path,
    identifier: TrainingMethodology,
) -> MethodologyDefinition:
    definition = METHODOLOGY_DEFINITIONS[identifier]
    actual_sha256 = _source_sha256(repo_root, definition.source_document)
    if actual_sha256 != definition.expected_source_sha256:
        raise MethodologyRegistryError(
            "Methodology source bytes do not match the controlled registry"
        )
    return definition


def resolve_methodology_choice(
    repo_root: Path,
    choice: MethodologyChoice,
    *,
    goal_type: str | None = None,
) -> MethodologySelection:
    """Bind a coach choice to the exact registered source bytes."""
    if choice.identifier == TrainingMethodology.FIRST:
        raise MethodologyRegistryError(
            "FIRST planning is unavailable until its edition-specific "
            "pace and schedule tables are verified"
        )
    if (
        choice.identifier == TrainingMethodology.PFITZINGER
        and goal_type is not None
        and goal_type != "marathon"
    ):
        raise MethodologyRegistryError("The registered Pfitzinger source is marathon-specific")
    definition = _verified_definition(repo_root, choice.identifier)
    return MethodologySelection(
        identifier=choice.identifier,
        source_document=definition.source_document,
        source_revision_sha256=definition.expected_source_sha256,
        source_edition=definition.source_edition,
        source_summary_version=definition.source_summary_version,
        source_verification_scope=definition.source_verification_scope,
        planning_authority=definition.planning_authority,
        executable_policy_version=definition.executable_policy_version,
        selection_rationale=choice.selection_rationale,
    )


def verify_methodology_selection(
    repo_root: Path,
    selection: MethodologySelection,
) -> None:
    """Reject caller-supplied paths and source revisions changed in place."""
    definition = _verified_definition(repo_root, selection.identifier)
    if selection.source_document != definition.source_document:
        raise MethodologyRegistryError(
            "Plan methodology source does not match the controlled registry"
        )
    expected_metadata = {
        "source_revision_sha256": definition.expected_source_sha256,
        "source_edition": definition.source_edition,
        "source_summary_version": definition.source_summary_version,
        "source_verification_scope": definition.source_verification_scope,
        "planning_authority": definition.planning_authority,
        "executable_policy_version": definition.executable_policy_version,
    }
    actual_metadata = {
        field_name: getattr(selection, field_name) for field_name in expected_metadata
    }
    if actual_metadata != expected_metadata:
        raise MethodologyRegistryError(
            "Plan methodology metadata does not match the controlled registry"
        )
