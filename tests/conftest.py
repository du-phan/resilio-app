"""
Pytest configuration and shared fixtures.
"""

import pytest
from pathlib import Path


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create subdirectories
    (data_dir / "config").mkdir()
    (data_dir / "athlete").mkdir()
    (data_dir / "activities").mkdir()
    (data_dir / "metrics" / "daily").mkdir(parents=True)
    (data_dir / "plans").mkdir()

    return data_dir


@pytest.fixture
def sample_profile():
    """Sample athlete profile for testing."""
    return {
        "_schema": {"format_version": "1.0.0", "schema_type": "profile"},
        "name": "Test Athlete",
        "created_at": "2026-01-12",
        "running_priority": "secondary",
        "primary_sport": "bouldering",
        "conflict_policy": "ask_each_time",
        "constraints": {
            "unavailable_run_days": ["monday", "wednesday", "thursday", "friday", "sunday"],
            "min_run_days_per_week": 2,
            "max_run_days_per_week": 3,
        },
        "goal": {
            "type": "half_marathon",
            "target_date": "2026-04-15",
        },
    }
