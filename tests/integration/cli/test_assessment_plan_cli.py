"""CLI exposure for the baseline-assessment lifecycle."""

import json

from typer.testing import CliRunner

from resilio.cli import app


def test_assessment_template_command_writes_agent_editable_contract(tmp_path) -> None:
    output_path = tmp_path / "assessment.json"

    result = CliRunner().invoke(
        app,
        [
            "plan",
            "template-assessment",
            "--total-weeks",
            "3",
            "--out",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text())
    assert len(payload["weeks"]) == 3
    assert payload["benchmark_intent"]["race_distance"] == "5k"
    assert payload["temporary_schedule_constraints"] == []
    assert payload["temporary_other_sport_commitment_overrides"] == []
    assert payload["medical_rehabilitation_excluded"] is True


def test_plan_neutral_approval_and_assessment_commands_are_exposed() -> None:
    runner = CliRunner()
    plan_help = runner.invoke(app, ["plan", "--help"])
    approvals_help = runner.invoke(app, ["approvals", "--help"])
    vdot_help = runner.invoke(app, ["vdot", "--help"])

    assert plan_help.exit_code == 0
    assert "create-assessment-context" in plan_help.stdout
    context_help = runner.invoke(
        app,
        ["plan", "create-assessment-context", "--help"],
    )
    assert context_help.exit_code == 0
    assert "--constraints-file" in context_help.stdout
    assert "--other-sport-file" in context_help.stdout
    assert "assessment-candidates" in plan_help.stdout
    assert "close-assessment" in plan_help.stdout
    assert "discard-unapproved" in plan_help.stdout
    assert approvals_help.exit_code == 0
    assert "approve-plan" in approvals_help.stdout
    assert "approve-macro" not in approvals_help.stdout
    assert vdot_help.exit_code == 0
    assert "create-proposal-from-assessment" in vdot_help.stdout
