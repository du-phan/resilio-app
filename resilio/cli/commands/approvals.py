"""Commands for exact-file, revision-bound athlete approvals."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, NoReturn

import typer

from resilio.cli.errors import get_exit_code_from_envelope
from resilio.cli.output import (
    create_error_envelope,
    create_success_envelope,
    output_json,
)
from resilio.core.planning.service import (
    PlanOperationError,
    approve_current_macro_plan,
    approve_vdot_proposal,
    approve_week_application,
    load_planning_aggregate,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import PlanningState

app = typer.Typer(help="Record approvals bound to exact planning payloads")


def _emit_error(error_type: str, message: str) -> NoReturn:
    envelope = create_error_envelope(error_type=error_type, message=message)
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


def _run_transition(
    operation: Callable[[], PlanningState],
    success_message: str,
) -> None:
    try:
        state = operation()
    except (OSError, PlanOperationError, ValueError) as exc:
        _emit_error("validation", str(exc))
    output_json(create_success_envelope(message=success_message, data=state))


@app.command("status")
def status_command() -> None:
    try:
        state = load_planning_aggregate(RepositoryIO(), allow_missing=True)
    except PlanOperationError as exc:
        _emit_error("validation", str(exc))
    output_json(
        create_success_envelope(
            message="Planning approval state",
            data=state or PlanningState(),
        )
    )


@app.command("approve-vdot")
def approve_vdot_command(
    proposal_file: Path = typer.Option(..., "--file"),
) -> None:
    repo = RepositoryIO()
    _run_transition(
        lambda: approve_vdot_proposal(repo, proposal_file),
        "Baseline VDOT proposal approved",
    )


@app.command("approve-macro")
def approve_macro_command() -> None:
    repo = RepositoryIO()
    _run_transition(
        lambda: approve_current_macro_plan(repo),
        "Current macro revision approved",
    )


@app.command("approve-week")
def approve_week_command(
    approved_file: Path = typer.Option(..., "--file"),
) -> None:
    repo = RepositoryIO()
    _run_transition(
        lambda: approve_week_application(repo, approved_file),
        "Exact weekly plan approved",
    )
