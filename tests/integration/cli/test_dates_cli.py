"""
Integration tests for sce dates CLI commands.

Tests the CLI interface, JSON output formatting, and error handling.
"""

import json
import pytest
from datetime import date, timedelta
from typer.testing import CliRunner

from sports_coach_engine.cli.commands.dates import app


runner = CliRunner()


class TestTodayCommand:
    """Tests for 'sce dates today' command."""

    def test_returns_json_envelope(self):
        """Should return valid JSON envelope with ok=True."""
        result = runner.invoke(app, ["today"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)

        assert data["ok"] is True
        assert data["schema_version"] == "1.0"
        assert "Today is" in data["message"]

    def test_includes_all_date_fields(self):
        """Should include date, day_name, day_number, next_monday, is_monday."""
        result = runner.invoke(app, ["today"])
        data = json.loads(result.stdout)["data"]

        assert "date" in data
        assert "day_name" in data
        assert "day_number" in data
        assert "next_monday" in data
        assert "is_monday" in data

    def test_day_name_is_correct(self):
        """Should return correct day name for today."""
        result = runner.invoke(app, ["today"])
        data = json.loads(result.stdout)["data"]

        today = date.today()
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        expected_day = day_names[today.weekday()]

        assert data["day_name"] == expected_day
        assert data["day_number"] == today.weekday()
        assert data["date"] == today.isoformat()

    def test_next_monday_is_correct(self):
        """Next Monday should be correct based on today."""
        result = runner.invoke(app, ["today"])
        data = json.loads(result.stdout)["data"]

        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        expected_monday = (today + timedelta(days=days_until_monday)).isoformat()

        assert data["next_monday"] == expected_monday

    def test_is_monday_flag(self):
        """is_monday should be True only if today is Monday."""
        result = runner.invoke(app, ["today"])
        data = json.loads(result.stdout)["data"]

        today = date.today()
        assert data["is_monday"] == (today.weekday() == 0)


class TestNextMondayCommand:
    """Tests for 'sce dates next-monday' command."""

    def test_from_saturday(self):
        """Next Monday from Saturday should be 2 days ahead."""
        result = runner.invoke(app, ["next-monday", "--from-date", "2026-01-17"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)["data"]

        assert data["date"] == "2026-01-19"
        assert data["day_name"] == "Monday"
        assert data["days_ahead"] == 2

    def test_from_sunday(self):
        """Next Monday from Sunday should be 1 day ahead."""
        result = runner.invoke(app, ["next-monday", "--from-date", "2026-01-18"])
        data = json.loads(result.stdout)["data"]

        assert data["date"] == "2026-01-19"
        assert data["days_ahead"] == 1

    def test_from_monday_returns_next_week(self):
        """Next Monday from Monday should be 7 days ahead."""
        result = runner.invoke(app, ["next-monday", "--from-date", "2026-01-19"])
        data = json.loads(result.stdout)["data"]

        assert data["date"] == "2026-01-26"
        assert data["days_ahead"] == 7

    def test_from_tuesday(self):
        """Next Monday from Tuesday should be 6 days ahead."""
        result = runner.invoke(app, ["next-monday", "--from-date", "2026-01-20"])
        data = json.loads(result.stdout)["data"]

        assert data["date"] == "2026-01-26"
        assert data["days_ahead"] == 6

    def test_without_from_date_uses_today(self):
        """Should use today if --from-date not provided."""
        result = runner.invoke(app, ["next-monday"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)["data"]

        assert "date" in data
        assert data["day_name"] == "Monday"
        assert "days_ahead" in data

    def test_invalid_date_format(self):
        """Should return error for invalid date format."""
        result = runner.invoke(app, ["next-monday", "--from-date", "2026-13-99"])

        assert result.exit_code == 5
        data = json.loads(result.stdout)

        assert data["ok"] is False
        assert data["error_type"] == "invalid_input"
        assert "Invalid date format" in data["message"]

    def test_includes_formatted_date(self):
        """Should include human-readable formatted date."""
        result = runner.invoke(app, ["next-monday", "--from-date", "2026-01-17"])
        data = json.loads(result.stdout)["data"]

        assert data["formatted"] == "Mon Jan 19, 2026"


class TestWeekBoundariesCommand:
    """Tests for 'sce dates week-boundaries' command."""

    def test_monday_input(self):
        """Should return Monday-Sunday boundaries."""
        result = runner.invoke(app, ["week-boundaries", "--start", "2026-01-19"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)["data"]

        assert data["start"] == "2026-01-19"
        assert data["end"] == "2026-01-25"
        assert data["formatted"] == "Mon Jan 19 - Sun Jan 25"
        assert data["duration_days"] == 7

    def test_rejects_tuesday(self):
        """Should reject Tuesday with error."""
        result = runner.invoke(app, ["week-boundaries", "--start", "2026-01-20"])

        assert result.exit_code == 5
        data = json.loads(result.stdout)

        assert data["ok"] is False
        assert data["error_type"] == "invalid_input"
        assert "must be Monday" in data["message"]
        assert "Tuesday" in data["message"]

    def test_rejects_sunday(self):
        """Should reject Sunday with error."""
        result = runner.invoke(app, ["week-boundaries", "--start", "2026-01-18"])

        assert result.exit_code == 5
        data = json.loads(result.stdout)

        assert data["ok"] is False
        assert "must be Monday" in data["message"]
        assert "Sunday" in data["message"]

    def test_month_boundary(self):
        """Should handle weeks spanning month boundaries."""
        result = runner.invoke(app, ["week-boundaries", "--start", "2026-01-26"])
        data = json.loads(result.stdout)["data"]

        assert data["start"] == "2026-01-26"
        assert data["end"] == "2026-02-01"
        assert data["formatted"] == "Mon Jan 26 - Sun Feb 01"

    def test_invalid_date_format(self):
        """Should return error for invalid date format."""
        result = runner.invoke(app, ["week-boundaries", "--start", "not-a-date"])

        assert result.exit_code == 5
        data = json.loads(result.stdout)

        assert data["ok"] is False
        assert data["error_type"] == "invalid_input"


class TestValidateCommand:
    """Tests for 'sce dates validate' command."""

    def test_monday_validates_as_monday(self):
        """Monday should validate as Monday."""
        result = runner.invoke(app, ["validate", "--date", "2026-01-19", "--must-be", "monday"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)["data"]

        assert data["valid"] is True
        assert data["day_name"] == "Monday"
        assert data["required_day"] == "Monday"
        assert "✓" in json.loads(result.stdout)["message"]

    def test_tuesday_fails_monday_validation(self):
        """Tuesday should fail Monday validation."""
        result = runner.invoke(app, ["validate", "--date", "2026-01-20", "--must-be", "monday"])

        assert result.exit_code == 0  # Command succeeds, validation result in data
        data = json.loads(result.stdout)["data"]

        assert data["valid"] is False
        assert data["day_name"] == "Tuesday"
        assert data["required_day"] == "Monday"
        assert "✗" in json.loads(result.stdout)["message"]

    def test_sunday_validates_as_sunday(self):
        """Sunday should validate as Sunday."""
        result = runner.invoke(app, ["validate", "--date", "2026-01-25", "--must-be", "sunday"])
        data = json.loads(result.stdout)["data"]

        assert data["valid"] is True
        assert data["day_name"] == "Sunday"

    def test_saturday_validates_as_saturday(self):
        """Saturday should validate as Saturday."""
        result = runner.invoke(app, ["validate", "--date", "2026-01-24", "--must-be", "saturday"])
        data = json.loads(result.stdout)["data"]

        assert data["valid"] is True
        assert data["day_name"] == "Saturday"

    def test_case_insensitive_day_names(self):
        """Should accept day names in any case."""
        result = runner.invoke(app, ["validate", "--date", "2026-01-19", "--must-be", "MONDAY"])
        data = json.loads(result.stdout)["data"]
        assert data["valid"] is True

        result = runner.invoke(app, ["validate", "--date", "2026-01-19", "--must-be", "MoNdAy"])
        data = json.loads(result.stdout)["data"]
        assert data["valid"] is True

    def test_invalid_day_name(self):
        """Should reject invalid day names."""
        result = runner.invoke(app, ["validate", "--date", "2026-01-19", "--must-be", "funday"])

        assert result.exit_code == 5
        data = json.loads(result.stdout)

        assert data["ok"] is False
        assert data["error_type"] == "invalid_input"
        assert "Invalid day name" in data["message"]

    def test_invalid_date_format(self):
        """Should reject invalid date formats."""
        result = runner.invoke(app, ["validate", "--date", "2026-99-99", "--must-be", "monday"])

        assert result.exit_code == 5
        data = json.loads(result.stdout)

        assert data["ok"] is False
        assert "Invalid date format" in data["message"]

    def test_all_weekdays(self):
        """Should validate all 7 weekdays correctly."""
        weekdays = [
            ("2026-01-19", "monday"),
            ("2026-01-20", "tuesday"),
            ("2026-01-21", "wednesday"),
            ("2026-01-22", "thursday"),
            ("2026-01-23", "friday"),
            ("2026-01-24", "saturday"),
            ("2026-01-25", "sunday"),
        ]

        for date_str, day_name in weekdays:
            result = runner.invoke(app, ["validate", "--date", date_str, "--must-be", day_name])
            data = json.loads(result.stdout)["data"]

            assert data["valid"] is True, f"{date_str} should be {day_name}"
            assert data["day_name"].lower() == day_name.lower()

    def test_default_must_be_is_monday(self):
        """Should default to validating Monday if --must-be not specified."""
        result = runner.invoke(app, ["validate", "--date", "2026-01-19"])
        data = json.loads(result.stdout)["data"]

        assert data["valid"] is True
        assert data["required_day"] == "Monday"


class TestJSONEnvelopeConsistency:
    """Tests for consistent JSON envelope structure across all commands."""

    def test_all_commands_return_json(self):
        """All commands should return valid JSON."""
        commands = [
            ["today"],
            ["next-monday"],
            ["week-boundaries", "--start", "2026-01-19"],
            ["validate", "--date", "2026-01-19", "--must-be", "monday"],
        ]

        for cmd in commands:
            result = runner.invoke(app, cmd)
            data = json.loads(result.stdout)  # Should not raise

            assert isinstance(data, dict)
            assert "ok" in data
            assert "schema_version" in data
            assert "message" in data

    def test_error_responses_consistent(self):
        """Error responses should have consistent structure."""
        error_commands = [
            ["next-monday", "--from-date", "invalid"],
            ["week-boundaries", "--start", "2026-01-20"],  # Tuesday
            ["validate", "--date", "2026-01-19", "--must-be", "funday"],
        ]

        for cmd in error_commands:
            result = runner.invoke(app, cmd)
            data = json.loads(result.stdout)

            assert data["ok"] is False
            assert data["error_type"] == "invalid_input"
            assert isinstance(data["message"], str)
            assert len(data["message"]) > 0


class TestHelpMessages:
    """Tests for help messages and command discoverability."""

    def test_dates_help(self):
        """Should show help for dates subcommand."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Date utilities" in result.stdout

    def test_today_help(self):
        """Should show help for today command."""
        result = runner.invoke(app, ["today", "--help"])

        assert result.exit_code == 0
        assert "today's date" in result.stdout.lower()

    def test_next_monday_help(self):
        """Should show help for next-monday command."""
        result = runner.invoke(app, ["next-monday", "--help"])

        assert result.exit_code == 0
        assert "--from-date" in result.stdout

    def test_week_boundaries_help(self):
        """Should show help for week-boundaries command."""
        result = runner.invoke(app, ["week-boundaries", "--help"])

        assert result.exit_code == 0
        assert "--start" in result.stdout

    def test_validate_help(self):
        """Should show help for validate command."""
        result = runner.invoke(app, ["validate", "--help"])

        assert result.exit_code == 0
        assert "--date" in result.stdout
        assert "--must-be" in result.stdout
