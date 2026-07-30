"""Typed coach-context CLI integration tests."""

import json

from typer.testing import CliRunner

from resilio.cli import app


def test_coach_context_is_read_only_and_reports_missing_data(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "coach",
            "context",
            "--week-start",
            "2026-07-27",
            "--as-of",
            "2026-07-29",
        ],
    )

    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["data"]["week_start"] == "2026-07-27"
    assert envelope["data"]["week_end"] == "2026-08-02"
    assert envelope["data"]["training_state"] is None
    assert not (tmp_path / "data" / "metrics").exists()
    assert not (tmp_path / "data" / "plans" / "weekly_summary.yaml").exists()


def test_coach_context_rejects_non_monday_week_start(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "coach",
            "context",
            "--week-start",
            "2026-07-28",
            "--as-of",
            "2026-07-29",
        ],
    )

    assert result.exit_code == 5
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    assert envelope["error_type"] == "validation"
    assert "Monday" in envelope["message"]


def test_coach_history_separates_target_week_from_evidence_window(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "activities").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "coach",
            "history",
            "--as-of",
            "2026-07-30",
            "--weeks",
            "3",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)["data"]
    assert payload["target_week_start"] == "2026-07-27"
    assert payload["target_week_end"] == "2026-08-02"
    assert payload["evidence_window_start"] == "2026-07-13"
    assert payload["evidence_window_end"] == "2026-07-30"
    assert len(payload["weeks"]) == 3
