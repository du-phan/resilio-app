"""Progression authoring commands registered on the plan command group."""

from enum import Enum
from pathlib import Path

import typer

from resilio.api.running_progression import (
    assess_running_progression,
    bind_running_progression_review,
)
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json


class CandidateKind(str, Enum):
    MACRO = "macro"
    AMENDMENT = "amendment"
    WEEK = "week"


def register_progression_commands(app: typer.Typer) -> None:
    @app.command("assess-progression")
    def assess_command(
        kind: CandidateKind = typer.Option(..., "--kind"),
        proposal_file: Path = typer.Option(..., "--file"),
    ) -> None:
        result = assess_running_progression(proposal_file, kind=kind.value)
        envelope = api_result_to_envelope(result, success_message="Running progression evidence")
        output_json(envelope)
        raise typer.Exit(get_exit_code_from_envelope(envelope))

    @app.command("bind-progression-review")
    def bind_command(
        kind: CandidateKind = typer.Option(..., "--kind"),
        proposal_file: Path = typer.Option(..., "--file"),
        review_file: Path = typer.Option(..., "--review-file"),
        output_file: Path = typer.Option(..., "--out"),
    ) -> None:
        result = bind_running_progression_review(
            proposal_file, review_file, output_file, kind=kind.value
        )
        envelope = api_result_to_envelope(
            result, success_message="Running progression review result"
        )
        output_json(envelope)
        raise typer.Exit(get_exit_code_from_envelope(envelope))
