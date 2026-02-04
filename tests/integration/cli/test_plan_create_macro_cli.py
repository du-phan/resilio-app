"""
Integration tests for sce plan create-macro CLI command.
"""

import json
from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace

from typer.testing import CliRunner

from sports_coach_engine.cli.commands.plan import app


runner = CliRunner()


def test_create_macro_derives_benchmark_date(tmp_path, monkeypatch):
    """Should derive benchmark date when --race-date is omitted."""
    start_date = date(2026, 1, 5)
    assert start_date.weekday() == 0  # Monday
    total_weeks = 4
    expected_race_date = start_date + timedelta(weeks=total_weeks, days=-1)

    template = {
        "template_version": "macro_template_v1",
        "total_weeks": total_weeks,
        "volumes_km": [20.0, 21.0, 22.0, 18.0],
        "weekly_volumes_km": [20.0, 21.0, 22.0, 18.0],
        "target_systemic_load_au": [0.0, 0.0, 0.0, 0.0],
        "workout_structure_hints": [
            {
                "quality": {"max_sessions": 1, "types": ["strides_only"]},
                "long_run": {"emphasis": "steady", "pct_range": [25, 30]},
                "intensity_balance": {"low_intensity_pct": 0.85},
            }
            for _ in range(total_weeks)
        ],
    }
    template_path = tmp_path / "macro_template.json"
    template_path.write_text(json.dumps(template))

    # Mock approvals state to allow baseline VDOT
    monkeypatch.setattr(
        "sports_coach_engine.core.state.load_approval_state",
        lambda: SimpleNamespace(approved_baseline_vdot=48.0),
    )

    captured = {}

    @dataclass
    class DummyPlan:
        phases: list

    def fake_create_macro_plan(**kwargs):
        captured["race_date"] = kwargs.get("race_date")
        return DummyPlan(phases=[{"phase": "base"}])

    monkeypatch.setattr(
        "sports_coach_engine.api.plan.create_macro_plan",
        fake_create_macro_plan,
    )

    result = runner.invoke(
        app,
        [
            "create-macro",
            "--goal-type",
            "10k",
            "--total-weeks",
            str(total_weeks),
            "--start-date",
            start_date.isoformat(),
            "--current-ctl",
            "30.0",
            "--baseline-vdot",
            "48.0",
            "--macro-template-json",
            str(template_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "warnings" in payload["data"]
    assert any("benchmark date" in w.lower() for w in payload["data"]["warnings"])
    assert captured["race_date"] == expected_race_date
