"""CLI contract for bounded running-workout publication."""

import json

from typer.testing import CliRunner

from resilio.cli import app
from resilio.cli.commands import migrate as migrate_commands
from resilio.cli.commands import workout as workout_commands
from resilio.core.locking import OperationLockError
from resilio.core.workout_fulfillment.migration import (
    WorkoutFulfillmentMigrationError,
)


def test_run_sync_commands_are_bounded_to_capabilities_and_one_week() -> None:
    runner = CliRunner()

    workout_help = runner.invoke(app, ["workout", "--help"])

    assert workout_help.exit_code == 0
    assert "capabilities" in workout_help.stdout
    assert "status" in workout_help.stdout
    assert "reconcile" in workout_help.stdout
    assert "reconcile-pairing-operations" in workout_help.stdout
    assert "resolve-drift" in workout_help.stdout
    assert "fulfillment-candidates" in workout_help.stdout
    assert "confirm-fulfillment" in workout_help.stdout
    assert "dismiss-fulfillment-candidate" in workout_help.stdout
    assert "revoke-fulfillment" in workout_help.stdout
    assert "fulfillment-status" in workout_help.stdout
    assert "config" in workout_help.stdout
    assert "configure" in workout_help.stdout
    assert "publish-plan" not in workout_help.stdout
    assert "publish-week" not in workout_help.stdout
    assert "publish" not in workout_help.stdout
    assert "delete" not in workout_help.stdout


def test_reconcile_pairing_operations_delegates_to_the_global_drain(
    monkeypatch,
) -> None:
    captured: list[str] = []
    monkeypatch.setattr(
        workout_commands,
        "reconcile_remote_workout_pairing_operations",
        lambda: captured.append("drained") or "reconciled",
    )
    monkeypatch.setattr(workout_commands, "_emit", lambda result, message: None)

    result = CliRunner().invoke(app, ["workout", "reconcile-pairing-operations"])

    assert result.exit_code == 0
    assert captured == ["drained"]


def test_run_capability_command_rejects_non_running_sports_before_network_access() -> None:
    result = CliRunner().invoke(
        app,
        ["workout", "capabilities", "--sport", "cycle"],
    )

    assert result.exit_code != 0
    assert "Only running-workout synchronization is supported" in result.output


def test_resolve_drift_passes_every_exact_confirmation_token(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def restore(week_number, **kwargs):
        captured.update({"week_number": week_number, **kwargs})
        return "restored"

    monkeypatch.setattr(workout_commands, "restore_local_week_run_workouts", restore)
    monkeypatch.setattr(workout_commands, "_emit", lambda result, message: None)

    result = CliRunner().invoke(
        app,
        [
            "workout",
            "resolve-drift",
            "--week-number",
            "3",
            "--confirmation-reference",
            "Athlete confirmed these exact remote bytes.",
            "--drift-target-token",
            "a" * 64,
            "--drift-target-token",
            "b" * 64,
        ],
    )

    assert result.exit_code == 0
    assert captured["confirmed_drift_target_tokens"] == ["a" * 64, "b" * 64]


def test_resolve_pairing_drift_passes_every_exact_confirmation_token(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def restore(week_number, **kwargs):
        captured.update({"week_number": week_number, **kwargs})
        return "restored"

    monkeypatch.setattr(
        workout_commands,
        "resolve_week_run_workout_pairing_drift",
        restore,
    )
    monkeypatch.setattr(workout_commands, "_emit", lambda result, message: None)

    result = CliRunner().invoke(
        app,
        [
            "workout",
            "resolve-pairing-drift",
            "--week-number",
            "3",
            "--confirmation-reference",
            "Athlete confirmed restoring these exact pairs.",
            "--pairing-drift-token",
            "a" * 64,
            "--pairing-drift-token",
            "b" * 64,
        ],
    )

    assert result.exit_code == 0
    assert captured["week_number"] == 3
    assert captured["confirmed_pairing_drift_tokens"] == ["a" * 64, "b" * 64]


def test_revoke_fulfillment_rejects_unknown_reason_before_api_call(monkeypatch) -> None:
    monkeypatch.setattr(
        workout_commands,
        "revoke_workout_fulfillment",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("API must not run")),
    )

    result = CliRunner().invoke(
        app,
        [
            "workout",
            "revoke-fulfillment",
            "--activity-id",
            "act-1",
            "--workout-id",
            "run-1",
            "--reason",
            "unknown",
            "--confirmation-reference",
            "Athlete confirmed.",
            "--rationale",
            "The association is contradicted by synchronized evidence.",
        ],
    )

    assert result.exit_code != 0
    assert "activity_deleted" in result.output


def test_workout_fulfillment_migration_failure_is_a_json_validation_envelope(
    monkeypatch,
) -> None:
    def fail(_repo, *, apply):
        assert not apply
        raise WorkoutFulfillmentMigrationError("exact cutover authority is unavailable")

    monkeypatch.setattr(
        migrate_commands,
        "migrate_workout_fulfillment_state",
        fail,
    )

    result = CliRunner().invoke(app, ["migrate", "workout-fulfillment-v2"])

    assert result.exit_code == 5
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_type"] == "validation"
    assert "authority is unavailable" in payload["message"]


def test_workout_fulfillment_migration_lock_failure_is_a_json_envelope(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        migrate_commands,
        "migrate_workout_fulfillment_state",
        lambda _repo, *, apply: (_ for _ in ()).throw(
            OperationLockError("migration lock is already held")
        ),
    )

    result = CliRunner().invoke(app, ["migrate", "workout-fulfillment-v2"])

    assert result.exit_code == 5
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_type"] == "validation"
    assert "lock is already held" in payload["message"]
