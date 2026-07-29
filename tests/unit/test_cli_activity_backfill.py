"""CLI coverage for the gated historical activity backfill surface."""

import json

from typer.testing import CliRunner

from resilio.api.historical_backfill import BackfillOperationError
from resilio.cli import app
from resilio.cli.errors import api_result_to_envelope


def test_backfill_status_is_offline_and_does_not_require_env_file(tmp_path):
    settings = tmp_path / "config/settings.yaml"
    settings.parent.mkdir(parents=True)
    settings.write_text("{}\n")

    result = CliRunner().invoke(
        app,
        [
            "--repo-root",
            str(tmp_path),
            "activity-backfill",
            "status",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"] == {
        "runs": [],
        "ledger_counts": {
            "pending": 0,
            "verified": 0,
            "rollback_pending": 0,
            "rolled_back": 0,
        },
        "pending": 0,
    }


def test_apply_requires_exact_plan_and_canary_digests():
    result = CliRunner().invoke(
        app,
        ["activity-backfill", "apply", "--help"],
    )

    assert result.exit_code == 0
    rendered = f"{result.stdout}\n{result.stderr}"
    assert "--plan-digest" in rendered
    assert "--canary-digest" in rendered


def test_backfill_operation_errors_produce_failure_envelopes():
    envelope = api_result_to_envelope(
        BackfillOperationError(
            error_type="invalid_payload",
            message="sanitized provider rejection",
        ),
        success_message="must not be used",
    )

    assert envelope.ok is False
    assert envelope.error_type == "invalid_payload"
    assert envelope.message == "sanitized provider rejection"
