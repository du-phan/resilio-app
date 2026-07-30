"""Training-plan commands over the focused planning API."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from resilio.api.plan import (
    apply_week_file,
    build_macro_template,
    create_macro_plan_from_file,
    get_current_plan,
    get_plan_status,
    get_plan_week,
    validate_week_file,
)
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import create_success_envelope, output_json

app = typer.Typer(help="Create, inspect, and apply approved training plans")


def _emit_result(result: object, message: str) -> None:
    envelope = api_result_to_envelope(result, success_message=message)
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command("show")
def show_command() -> None:
    _emit_result(get_current_plan(), "Current training plan")


@app.command("status")
def status_command() -> None:
    _emit_result(get_plan_status(), "Training-plan population status")


@app.command("week")
def week_command(
    week_number: int = typer.Option(..., "--week", min=1),
) -> None:
    _emit_result(
        get_plan_week(week_number),
        f"Training-plan week {week_number}",
    )


@app.command("next-unpopulated")
def next_unpopulated_command() -> None:
    status = get_plan_status()
    _emit_result(status, "Next unpopulated training-plan week")


@app.command("template-macro")
def template_macro_command(
    total_weeks: int = typer.Option(..., "--total-weeks", min=1),
    output_path: Path = typer.Option(..., "--out"),
) -> None:
    template = build_macro_template(total_weeks)
    if not isinstance(template, dict):
        _emit_result(template, "Macro template")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(template, indent=2) + "\n")
    envelope = create_success_envelope(
        message="Macro template created",
        data={"path": str(output_path.resolve()), "template": template},
    )
    output_json(envelope)


@app.command("create-macro")
def create_macro_command(
    draft_file: Path = typer.Option(..., "--from-json"),
) -> None:
    _emit_result(
        create_macro_plan_from_file(draft_file),
        "Methodology-explicit macro plan created",
    )


@app.command("validate-week")
def validate_week_command(
    approved_file: Path = typer.Option(..., "--file"),
) -> None:
    _emit_result(
        validate_week_file(approved_file),
        "Weekly plan payload is valid",
    )


@app.command("apply-week")
def apply_week_command(
    approved_file: Path = typer.Option(..., "--file"),
) -> None:
    _emit_result(
        apply_week_file(approved_file),
        "Approved weekly plan applied",
    )
