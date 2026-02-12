"""
Unit tests for sync CLI command status observability.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from typer.testing import CliRunner

from resilio.cli import app
from resilio.cli.commands.sync import _build_success_message
from resilio.schemas.sync import SyncPhase, SyncReport


def _parse_output(stdout: str) -> dict:
    return json.loads(stdout)


def test_sync_status_no_lock_no_progress(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "--status"])

    assert result.exit_code == 0
    envelope = _parse_output(result.stdout)
    assert envelope["ok"] is True
    assert envelope["data"]["running"] is False
    assert envelope["data"]["lock"] is None
    assert envelope["data"]["progress"] is None


def test_sync_status_active_lock(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "config").mkdir()
    monkeypatch.chdir(tmp_path)

    lock_payload = {
        "pid": os.getpid(),
        "operation": "sync",
        "acquired_at": datetime.now(timezone.utc).isoformat(),
    }
    (tmp_path / "config" / ".workflow_lock").write_text(json.dumps(lock_payload))

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "--status"])

    assert result.exit_code == 0
    envelope = _parse_output(result.stdout)
    assert envelope["data"]["running"] is True
    assert envelope["data"]["lock"]["stale"] is False


def test_sync_status_stale_lock(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "config").mkdir()
    monkeypatch.chdir(tmp_path)

    stale_payload = {
        "pid": 999999,
        "operation": "sync",
        "acquired_at": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
    }
    (tmp_path / "config" / ".workflow_lock").write_text(json.dumps(stale_payload))

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "--status"])

    assert result.exit_code == 0
    envelope = _parse_output(result.stdout)
    assert envelope["data"]["running"] is False
    assert envelope["data"]["lock"]["stale"] is True


def test_sync_status_malformed_progress_file(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "config").mkdir()
    monkeypatch.chdir(tmp_path)

    (tmp_path / "config" / ".sync_progress.json").write_text("{bad-json")

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "--status"])

    assert result.exit_code == 0
    envelope = _parse_output(result.stdout)
    assert envelope["data"]["progress"] is None


def test_sync_status_reads_resume_state_from_training_history(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "athlete").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    training_history = """
backfill_in_progress: true
target_start_date: "2025-02-12"
resume_before_timestamp: 1737000000
last_progress_at: "2026-02-12T12:00:00+00:00"
"""
    (tmp_path / "data" / "athlete" / "training_history.yaml").write_text(training_history)

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "--status"])

    assert result.exit_code == 0
    envelope = _parse_output(result.stdout)
    resume_state = envelope["data"]["resume_state"]
    assert resume_state["backfill_in_progress"] is True
    assert resume_state["target_start_date"] == "2025-02-12"
    assert resume_state["resume_before_timestamp"] == 1737000000
    parsed_last_progress = datetime.fromisoformat(
        resume_state["last_progress_at"].replace("Z", "+00:00")
    )
    assert parsed_last_progress == datetime(2026, 2, 12, 12, 0, tzinfo=timezone.utc)


def test_sync_status_reads_valid_progress_payload(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "config").mkdir()
    monkeypatch.chdir(tmp_path)

    progress_payload = {
        "phase": "fetching",
        "activities_seen": 12,
        "activities_imported": 10,
        "activities_skipped": 2,
        "activities_failed": 0,
        "current_page": 3,
        "current_month": "2025-11",
        "cursor_before_timestamp": 1736000000,
        "updated_at": "2026-02-12T12:03:00+00:00",
    }
    (tmp_path / "config" / ".sync_progress.json").write_text(json.dumps(progress_payload))

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "--status"])

    assert result.exit_code == 0
    envelope = _parse_output(result.stdout)
    progress = envelope["data"]["progress"]
    assert progress["phase"] == "fetching"
    assert progress["activities_seen"] == 12
    assert progress["cursor_before_timestamp"] == 1736000000


def test_sync_status_malformed_history_defaults_resume_state(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "data" / "athlete").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    training_history = """
backfill_in_progress: "true"
target_start_date: "not-a-date"
resume_before_timestamp: "oops"
last_progress_at: "bad-datetime"
"""
    (tmp_path / "data" / "athlete" / "training_history.yaml").write_text(training_history)

    runner = CliRunner()
    result = runner.invoke(app, ["sync", "--status"])

    assert result.exit_code == 0
    envelope = _parse_output(result.stdout)
    resume_state = envelope["data"]["resume_state"]
    assert resume_state["backfill_in_progress"] is True
    assert resume_state["target_start_date"] is None
    assert resume_state["resume_before_timestamp"] is None
    assert resume_state["last_progress_at"] is None


def test_build_success_message_uses_sync_report_contract():
    report = SyncReport(
        activities_imported=5,
        activities_skipped=2,
        activities_failed=1,
        laps_fetched=3,
        laps_skipped_age=2,
        lap_fetch_failures=1,
        phase=SyncPhase.DONE,
        rate_limited=False,
        errors=[],
    )

    msg = _build_success_message(report)
    assert "Synced 5 new activities" in msg
    assert "Lap data fetched for 3 running activities." in msg
