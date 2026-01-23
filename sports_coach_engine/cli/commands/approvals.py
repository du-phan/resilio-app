"""
sce approvals - Approval state management for progressive disclosure workflows.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from sports_coach_engine.cli.errors import get_exit_code_from_envelope
from sports_coach_engine.cli.output import create_error_envelope, create_success_envelope, output_json
from sports_coach_engine.core.state import load_approval_state, save_approval_state
from sports_coach_engine.schemas.approvals import ApprovalState, WeeklyApproval
from sports_coach_engine.schemas.repository import RepoError

app = typer.Typer(help="Manage approval state for planning workflows")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_or_default() -> tuple[Optional[ApprovalState], Optional[RepoError]]:
    result = load_approval_state()
    if isinstance(result, RepoError):
        return None, result
    if result is None:
        return ApprovalState(), None
    return result, None


@app.command(name="status")
def approvals_status_command(ctx: typer.Context) -> None:
    """Show current approval state (if any)."""
    result = load_approval_state()
    if isinstance(result, RepoError):
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Failed to load approvals state: {result}",
            data={"path": getattr(result, "path", None)},
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    if result is None:
        envelope = create_success_envelope(
            message="Approval state not found",
            data={"exists": False, "state": None},
        )
        output_json(envelope)
        raise typer.Exit(code=0)

    envelope = create_success_envelope(
        message="Approval state loaded",
        data={"exists": True, "state": result},
    )
    output_json(envelope)
    raise typer.Exit(code=0)


@app.command(name="approve-vdot")
def approvals_approve_vdot_command(
    ctx: typer.Context,
    value: float = typer.Option(..., "--value", help="Approved baseline VDOT value"),
    timestamp: Optional[str] = typer.Option(
        None,
        "--timestamp",
        help="Override approval timestamp (ISO format). Defaults to now (UTC).",
    ),
) -> None:
    """Record baseline VDOT approval."""
    state, error = _load_or_default()
    if error:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Failed to load approvals state: {error}",
            data={"path": getattr(error, "path", None)},
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    state.approved_baseline_vdot = value
    state.vdot_approval_ts = timestamp or _now_iso()

    save_error = save_approval_state(state)
    if save_error:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Failed to save approvals state: {save_error}",
            data={"path": getattr(save_error, "path", None)},
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    envelope = create_success_envelope(
        message="Baseline VDOT approved",
        data={"approved_baseline_vdot": value, "vdot_approval_ts": state.vdot_approval_ts},
    )
    output_json(envelope)
    raise typer.Exit(code=0)


@app.command(name="approve-macro")
def approvals_approve_macro_command(
    ctx: typer.Context,
    timestamp: Optional[str] = typer.Option(
        None,
        "--timestamp",
        help="Override approval timestamp (ISO format). Defaults to now (UTC).",
    ),
) -> None:
    """Record macro plan approval."""
    state, error = _load_or_default()
    if error:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Failed to load approvals state: {error}",
            data={"path": getattr(error, "path", None)},
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    state.macro_approved = True
    state.macro_approval_ts = timestamp or _now_iso()

    save_error = save_approval_state(state)
    if save_error:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Failed to save approvals state: {save_error}",
            data={"path": getattr(save_error, "path", None)},
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    envelope = create_success_envelope(
        message="Macro plan approved",
        data={"macro_approved": True, "macro_approval_ts": state.macro_approval_ts},
    )
    output_json(envelope)
    raise typer.Exit(code=0)


@app.command(name="approve-week")
def approvals_approve_week_command(
    ctx: typer.Context,
    week: int = typer.Option(..., "--week", help="Approved week number"),
    file: str = typer.Option(
        ...,
        "--file",
        help="Path to approved weekly JSON payload",
    ),
    timestamp: Optional[str] = typer.Option(
        None,
        "--timestamp",
        help="Override approval timestamp (ISO format). Defaults to now (UTC).",
    ),
) -> None:
    """Record weekly plan approval with the exact JSON file path."""
    file_path = Path(file)
    if not file_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message=f"Approved JSON file not found: {file}",
            data={"path": str(file_path.absolute())},
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    state, error = _load_or_default()
    if error:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Failed to load approvals state: {error}",
            data={"path": getattr(error, "path", None)},
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    resolved = file_path.expanduser().resolve()
    state.weekly_approval = WeeklyApproval(
        week_number=week,
        approved_at=timestamp or _now_iso(),
        approved_file=str(resolved),
    )

    save_error = save_approval_state(state)
    if save_error:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Failed to save approvals state: {save_error}",
            data={"path": getattr(save_error, "path", None)},
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    envelope = create_success_envelope(
        message=f"Week {week} approved",
        data={
            "week_number": week,
            "approved_file": str(resolved),
            "approved_at": state.weekly_approval.approved_at,
        },
    )
    output_json(envelope)
    raise typer.Exit(code=0)
