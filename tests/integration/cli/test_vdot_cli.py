"""VDOT CLI date-boundary behavior."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from resilio.cli.commands.vdot import app


def test_calculate_rejects_invalid_as_of_date_with_json_envelope() -> None:
    result = CliRunner().invoke(
        app,
        [
            "calculate",
            "--race-type",
            "10k",
            "--time",
            "42:30",
            "--race-date",
            "2026-07-20",
            "--as-of-date",
            "not-a-date",
        ],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 5
    assert payload["ok"] is False
    assert payload["error_type"] == "invalid_input"
    assert payload["message"] == "as_of_date must use YYYY-MM-DD"


def test_calculate_requires_explicit_as_of_date_for_dated_evidence() -> None:
    result = CliRunner().invoke(
        app,
        [
            "calculate",
            "--race-type",
            "10k",
            "--time",
            "42:30",
            "--race-date",
            "2026-07-20",
        ],
    )

    payload = json.loads(result.stdout)
    assert result.exit_code == 5
    assert payload["ok"] is False
    assert payload["error_type"] == "invalid_input"
    assert payload["message"] == ("as_of_date is required when race_date is supplied")
