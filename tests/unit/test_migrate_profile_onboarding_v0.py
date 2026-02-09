"""
Tests for one-time onboarding profile migration script.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "migrations" / "migrate_profile_onboarding_v0.py"


def _legacy_profile_payload() -> dict:
    return {
        "name": "Migration Athlete",
        "created_at": "2026-01-01",
        "constraints": {
            "available_run_days": ["monday", "wednesday", "friday"],
            "preferred_long_run_days": ["saturday", "sunday"],
            "min_run_days_per_week": 2,
            "max_run_days_per_week": 4,
        },
        "running_priority": "primary",
        "conflict_policy": "running_goal_wins",
        "goal": {"type": "general_fitness"},
        "other_sports": [
            {
                "sport": "climbing",
                "days": ["tuesday", "thursday"],
                "typical_duration_minutes": 90,
                "typical_intensity": "moderate_to_hard",
            },
            {
                "sport": "cycling",
                "typical_duration_minutes": 60,
                "typical_intensity": "moderate",
            },
        ],
    }


def _run_migration(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(REPO_ROOT)
        if not existing_pythonpath
        else f"{REPO_ROOT}:{existing_pythonpath}"
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_migration_dry_run_does_not_write(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    original = _legacy_profile_payload()
    profile_path.write_text(yaml.safe_dump(original, sort_keys=False), encoding="utf-8")

    result = _run_migration("--path", str(profile_path), "--dry-run", "--yes")

    assert result.returncode == 0, result.stderr
    assert "Dry run only" in result.stdout

    after = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    assert after == original
    backups = list(tmp_path.glob("profile.pre_onboarding_migration.*.yaml"))
    assert backups == []


def test_migration_apply_creates_backup_and_updates_shape(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        yaml.safe_dump(_legacy_profile_payload(), sort_keys=False), encoding="utf-8"
    )

    result = _run_migration("--path", str(profile_path), "--yes", "--default-frequency", "2")
    assert result.returncode == 0, result.stderr
    assert "Backup created:" in result.stdout
    assert "Migrated profile written:" in result.stdout

    migrated = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    constraints = migrated["constraints"]
    assert "available_run_days" not in constraints
    assert "preferred_long_run_days" not in constraints
    assert sorted(constraints["unavailable_run_days"]) == sorted(
        ["tuesday", "thursday", "saturday", "sunday"]
    )

    climbing = migrated["other_sports"][0]
    assert climbing["frequency_per_week"] == 2
    assert sorted(climbing["unavailable_days"]) == ["thursday", "tuesday"]
    assert climbing["active"] is True
    assert climbing["pause_reason"] is None
    assert climbing["paused_at"] is None

    cycling = migrated["other_sports"][1]
    assert cycling["frequency_per_week"] == 2  # from --default-frequency
    assert cycling.get("unavailable_days") is None

    backups = list(tmp_path.glob("profile.pre_onboarding_migration.*.yaml"))
    assert len(backups) == 1


def test_migration_is_idempotent_after_first_apply(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        yaml.safe_dump(_legacy_profile_payload(), sort_keys=False), encoding="utf-8"
    )

    first = _run_migration("--path", str(profile_path), "--yes")
    assert first.returncode == 0, first.stderr

    second = _run_migration("--path", str(profile_path), "--dry-run", "--yes")
    assert second.returncode == 0, second.stderr
    assert "No migration changes needed." in second.stdout
