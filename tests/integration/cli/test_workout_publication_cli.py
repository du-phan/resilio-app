"""CLI contract for bounded running-workout publication."""

from typer.testing import CliRunner

from resilio.cli import app


def test_run_sync_commands_are_bounded_to_capabilities_and_one_week() -> None:
    runner = CliRunner()

    workout_help = runner.invoke(app, ["workout", "--help"])

    assert workout_help.exit_code == 0
    assert "capabilities" in workout_help.stdout
    assert "status" in workout_help.stdout
    assert "reconcile" in workout_help.stdout
    assert "resolve-drift" in workout_help.stdout
    assert "config" in workout_help.stdout
    assert "configure" in workout_help.stdout
    assert "publish-plan" not in workout_help.stdout
    assert "publish-week" not in workout_help.stdout
    assert "publish" not in workout_help.stdout
    assert "delete" not in workout_help.stdout


def test_run_capability_command_rejects_non_running_sports_before_network_access() -> None:
    result = CliRunner().invoke(
        app,
        ["workout", "capabilities", "--sport", "cycle"],
    )

    assert result.exit_code != 0
    assert "Only running-workout synchronization is supported" in result.output
