"""Training-plan commands over the focused planning API."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import typer
from pydantic import TypeAdapter, ValidationError

from resilio.api.plan import (
    PlanError,
    build_assessment_template,
    build_macro_template,
    close_assessment,
    close_plan_cycle,
    create_assessment_context_evidence,
    create_assessment_plan_from_file,
    create_assessment_review_evidence,
    create_cycle_review_evidence,
    create_macro_context_evidence,
    create_macro_plan_from_file,
    discard_unapproved_plan,
    get_assessment_result_candidates,
    get_current_plan,
    get_plan_status,
    get_plan_week,
)
from resilio.api.week_application import apply_week_file, validate_week_file
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import create_success_envelope, output_json
from resilio.schemas.assessment import (
    AssessmentReason,
    TemporaryScheduleConstraint,
)
from resilio.schemas.plan_history import PlanClosureDisposition

app = typer.Typer(help="Create, inspect, and apply approved training plans")
SCHEDULE_CONSTRAINTS_ADAPTER: TypeAdapter[list[TemporaryScheduleConstraint]] = TypeAdapter(
    list[TemporaryScheduleConstraint]
)


def _emit_result(result: object, message: str) -> None:
    envelope = api_result_to_envelope(result, success_message=message)
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command("show")
def show_command() -> None:
    _emit_result(get_current_plan(), "Current training plan")


@app.command("discard-unapproved")
def discard_unapproved_command(
    plan_revision_id: str = typer.Option(
        ...,
        "--plan-revision",
        help="Exact current proposal revision selected for discard.",
    ),
) -> None:
    """Discard an exact plan proposal that has never been approved or applied."""
    _emit_result(
        discard_unapproved_plan(expected_plan_revision_id=plan_revision_id),
        "Unapproved training-plan proposal discarded",
    )


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


@app.command("template-assessment")
def template_assessment_command(
    total_weeks: int = typer.Option(..., "--total-weeks", min=1),
    output_path: Path = typer.Option(..., "--out"),
) -> None:
    template = build_assessment_template(total_weeks)
    if not isinstance(template, dict):
        _emit_result(template, "Assessment template")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(template, indent=2) + "\n")
    output_json(
        create_success_envelope(
            message="Assessment template created",
            data={"path": str(output_path.resolve()), "template": template},
        )
    )


@app.command("create-assessment")
def create_assessment_command(
    draft_file: Path = typer.Option(..., "--from-json"),
) -> None:
    _emit_result(
        create_assessment_plan_from_file(draft_file),
        "Baseline-assessment plan created",
    )


@app.command("create-assessment-context")
def create_assessment_context_command(
    evidence_as_of_date: str = typer.Option(..., "--evidence-as-of"),
    intended_plan_start_date: str = typer.Option(..., "--start"),
    assessment_reasons: list[AssessmentReason] = typer.Option(..., "--reason"),
    schedule_constraints_file: Path
    | None = typer.Option(
        None,
        "--constraints-file",
        help="JSON array of athlete-confirmed unavailable date ranges.",
    ),
) -> None:
    """Create bounded evidence for a non-rehabilitation assessment block."""
    try:
        parsed_evidence_as_of = date.fromisoformat(evidence_as_of_date)
        parsed_plan_start = date.fromisoformat(intended_plan_start_date)
    except ValueError as exc:
        _emit_result(
            PlanError("validation", f"Dates must use YYYY-MM-DD format: {exc}"),
            "Assessment-planning context",
        )
    try:
        schedule_constraints = (
            SCHEDULE_CONSTRAINTS_ADAPTER.validate_python(
                json.loads(schedule_constraints_file.read_text())
            )
            if schedule_constraints_file is not None
            else []
        )
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        _emit_result(
            PlanError("validation", f"Schedule constraints file is invalid: {exc}"),
            "Assessment-planning context",
        )
    _emit_result(
        create_assessment_context_evidence(
            evidence_as_of_date=parsed_evidence_as_of,
            intended_plan_start_date=parsed_plan_start,
            assessment_reasons=assessment_reasons,
            temporary_schedule_constraints=schedule_constraints,
        ),
        "Immutable assessment-planning evidence context created",
    )


@app.command("assessment-candidates")
def assessment_candidates_command() -> None:
    _emit_result(
        get_assessment_result_candidates(),
        "Owned baseline-assessment result candidates",
    )


@app.command("create-assessment-review")
def create_assessment_review_command(
    candidate_id: str = typer.Option(..., "--candidate"),
    evidence_as_of_date: str = typer.Option(..., "--evidence-as-of"),
    official_distance_confirmation_reference: str = typer.Option(
        ...,
        "--official-distance-confirmation",
    ),
    athlete_confirmation_reference: str = typer.Option(
        ...,
        "--athlete-confirmation",
    ),
    review_summary: str = typer.Option(..., "--summary"),
) -> None:
    try:
        parsed_evidence_as_of = date.fromisoformat(evidence_as_of_date)
    except ValueError as exc:
        _emit_result(
            PlanError("validation", f"Date must use YYYY-MM-DD format: {exc}"),
            "Assessment review",
        )
    _emit_result(
        create_assessment_review_evidence(
            candidate_id=candidate_id,
            evidence_as_of_date=parsed_evidence_as_of,
            official_distance_confirmation_reference=(official_distance_confirmation_reference),
            athlete_confirmation_reference=athlete_confirmation_reference,
            review_summary=review_summary,
        ),
        "Immutable baseline-assessment review created",
    )


@app.command("close-assessment")
def close_assessment_command(
    assessment_review_sha256: str = typer.Option(..., "--review-sha256"),
    reason: str = typer.Option(..., "--reason"),
    athlete_confirmation_reference: str = typer.Option(
        ...,
        "--athlete-confirmation",
    ),
) -> None:
    _emit_result(
        close_assessment(
            assessment_review_sha256=assessment_review_sha256,
            reason=reason,
            athlete_confirmation_reference=athlete_confirmation_reference,
        ),
        "Baseline assessment closed and archived",
    )


@app.command("create-cycle-review")
def create_cycle_review_command(
    effective_end_date: str = typer.Option(..., "--effective-end"),
    evidence_as_of_date: str = typer.Option(..., "--evidence-as-of"),
    goal_status: str = typer.Option(..., "--goal-status"),
    athlete_confirmation_reference: str = typer.Option(
        ...,
        "--athlete-confirmation",
    ),
    goal_activity_id: str
    | None = typer.Option(
        None,
        "--goal-activity-id",
    ),
    goal_notes: str | None = typer.Option(None, "--goal-notes"),
) -> None:
    """Create immutable retrospective evidence for the active plan."""
    try:
        parsed_effective_end = date.fromisoformat(effective_end_date)
        parsed_evidence_as_of = date.fromisoformat(evidence_as_of_date)
    except ValueError as exc:
        _emit_result(
            PlanError("validation", f"Cycle-review inputs are invalid: {exc}"),
            "Cycle review evidence",
        )
    _emit_result(
        create_cycle_review_evidence(
            effective_end_date=parsed_effective_end,
            evidence_as_of_date=parsed_evidence_as_of,
            goal_status=goal_status,
            goal_activity_id=goal_activity_id,
            athlete_confirmation_reference=(athlete_confirmation_reference),
            goal_notes=goal_notes,
        ),
        "Immutable plan-cycle review created",
    )


@app.command("close-cycle")
def close_cycle_command(
    cycle_review_sha256: str = typer.Option(..., "--cycle-review-sha256"),
    disposition: PlanClosureDisposition = typer.Option(..., "--disposition"),
    reason: str = typer.Option(..., "--reason"),
    athlete_confirmation_reference: str = typer.Option(
        ...,
        "--athlete-confirmation",
    ),
) -> None:
    """Archive the active plan after athlete-confirmed review facts."""
    _emit_result(
        close_plan_cycle(
            cycle_review_sha256=cycle_review_sha256,
            disposition=disposition,
            reason=reason,
            athlete_confirmation_reference=(athlete_confirmation_reference),
        ),
        "Active plan cycle closed and archived",
    )


@app.command("create-macro-context")
def create_macro_context_command(
    evidence_as_of_date: str = typer.Option(..., "--evidence-as-of"),
    intended_plan_start_date: str = typer.Option(..., "--start"),
) -> None:
    """Create the bounded historical evidence required by a macro draft."""
    try:
        parsed_evidence_as_of = date.fromisoformat(evidence_as_of_date)
        parsed_plan_start = date.fromisoformat(intended_plan_start_date)
    except ValueError as exc:
        _emit_result(
            PlanError("validation", f"Dates must use YYYY-MM-DD format: {exc}"),
            "Macro-planning context",
        )
    _emit_result(
        create_macro_context_evidence(
            evidence_as_of_date=parsed_evidence_as_of,
            intended_plan_start_date=parsed_plan_start,
        ),
        "Immutable macro-planning evidence context created",
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
    create_assessment_context_evidence,
    create_assessment_plan_from_file,
    create_assessment_review_evidence,
    get_assessment_result_candidates,
