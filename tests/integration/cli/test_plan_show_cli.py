"""
Integration tests for `resilio plan show` CLI command variants.
"""

import json

from typer.testing import CliRunner

from resilio.cli.commands.plan import app


runner = CliRunner()


def test_plan_show_review_success(tmp_path, monkeypatch):
    """`--type review` should return a valid success envelope with content."""
    review_file = tmp_path / "current_plan_review.md"
    review_content = "# Plan Review\n\n## Week 1\nGood start."
    review_file.write_text(review_content)

    monkeypatch.setattr(
        "resilio.core.paths.current_plan_review_path",
        lambda: str(review_file),
    )

    result = runner.invoke(app, ["show", "--type", "review"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["schema_version"] == "1.0"
    assert payload["data"]["path"] == str(review_file)
    assert payload["data"]["content"] == review_content


def test_plan_show_review_missing_file(tmp_path, monkeypatch):
    """`--type review` should return not_found when review file is missing."""
    missing_review_file = tmp_path / "missing_review.md"

    monkeypatch.setattr(
        "resilio.core.paths.current_plan_review_path",
        lambda: str(missing_review_file),
    )

    result = runner.invoke(app, ["show", "--type", "review"])

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_type"] == "not_found"


def test_plan_show_log_success_all_weeks(tmp_path, monkeypatch):
    """`--type log` should return all log content by default."""
    log_file = tmp_path / "current_training_log.md"
    log_content = (
        "# Training Log\n\n"
        "## Week 1:\nSummary one.\n\n"
        "## Week 2:\nSummary two.\n"
    )
    log_file.write_text(log_content)

    monkeypatch.setattr(
        "resilio.core.paths.current_training_log_path",
        lambda: str(log_file),
    )

    result = runner.invoke(app, ["show", "--type", "log"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["schema_version"] == "1.0"
    assert payload["data"]["path"] == str(log_file)
    assert payload["data"]["weeks_shown"] == "all"
    assert payload["data"]["content"] == log_content


def test_plan_show_log_last_weeks_filter(tmp_path, monkeypatch):
    """`--type log --last-weeks N` should keep only the last N weeks."""
    log_file = tmp_path / "current_training_log.md"
    log_file.write_text(
        "# Training Log\n\n"
        "## Week 1:\nSummary one.\n\n"
        "## Week 2:\nSummary two.\n\n"
        "## Week 3:\nSummary three.\n"
    )

    monkeypatch.setattr(
        "resilio.core.paths.current_training_log_path",
        lambda: str(log_file),
    )

    result = runner.invoke(app, ["show", "--type", "log", "--last-weeks", "2"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["weeks_shown"] == 2
    content = payload["data"]["content"]
    assert "## Week 1:" not in content
    assert "## Week 2:" in content
    assert "## Week 3:" in content


def test_plan_show_log_missing_file(tmp_path, monkeypatch):
    """`--type log` should return not_found when log file is missing."""
    missing_log_file = tmp_path / "missing_log.md"

    monkeypatch.setattr(
        "resilio.core.paths.current_training_log_path",
        lambda: str(missing_log_file),
    )

    result = runner.invoke(app, ["show", "--type", "log"])

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_type"] == "not_found"


def test_plan_show_invalid_type_validation_error():
    """Invalid type should return validation error envelope."""
    result = runner.invoke(app, ["show", "--type", "invalid"])

    assert result.exit_code == 5
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_type"] == "validation"
    assert payload["data"]["valid_types"] == ["plan", "review", "log"]

