"""
Integration tests for Phase 1: Core Infrastructure.

Tests the complete workflow: Config → Repository → Profile
"""

import pytest
import yaml
from pathlib import Path

from sports_coach_engine.core.config import load_config, ConfigError
from sports_coach_engine.core.repository import RepositoryIO, RepoError
from sports_coach_engine.core.profile import ProfileService, ProfileError, validate_constraints, calculate_vdot, RaceDistance
from sports_coach_engine.schemas.profile import (
    AthleteProfile,
    Goal,
    GoalType,
    TrainingConstraints,
    Weekday,
    RunningPriority,
    ConflictPolicy,
    StravaConnection,
)


class TestPhase1Integration:
    """Integration tests for Phase 1 modules."""

    def test_full_phase1_workflow(self, tmp_path, monkeypatch):
        """Test complete Phase 1 workflow: config → repo → profile."""
        # Setup repo structure
        (tmp_path / ".git").mkdir()
        (tmp_path / "config").mkdir()

        # Create config files
        settings = {
            "paths": {"athlete_dir": "data/athlete"},
        }
        (tmp_path / "config" / "settings.yaml").write_text(yaml.dump(settings))

        secrets = {
            "strava": {
                "client_id": "12345",
                "client_secret": "s" * 40,
                "access_token": "token",
                "refresh_token": "refresh",
                "token_expires_at": 1704067200,
            }
        }
        (tmp_path / "config" / "secrets.local.yaml").write_text(yaml.dump(secrets))

        monkeypatch.chdir(tmp_path)

        # Step 1: Load config
        config = load_config()
        assert not isinstance(config, ConfigError)
        assert config.settings.paths.athlete_dir == "data/athlete"

        # Step 2: Initialize repository
        repo = RepositoryIO(config=config)
        assert repo.file_exists("config/settings.yaml")

        # Step 3: Create and save profile
        profile_service = ProfileService(repo)

        profile = AthleteProfile(
            name="Integration Test Athlete",
            email="test@example.com",
            created_at="2026-01-12",
            age=32,
            strava=StravaConnection(athlete_id="12345678"),
            running_experience_years=5,
            running_priority=RunningPriority.SECONDARY,
            primary_sport="bouldering",
            conflict_policy=ConflictPolicy.PRIMARY_SPORT_WINS,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.TUESDAY, Weekday.SATURDAY],
                min_run_days_per_week=2,
                max_run_days_per_week=2,
            ),
            goal=Goal(
                type=GoalType.HALF_MARATHON,
                race_name="Paris Half",
                target_date="2026-04-01",
                target_time="1:45:00",
            ),
        )

        # Validate constraints
        validation_result = validate_constraints(profile.constraints, profile.goal)
        assert validation_result.valid

        # Calculate VDOT
        vdot = calculate_vdot(RaceDistance.TEN_K, "47:00")
        assert not isinstance(vdot, ProfileError)
        assert 42 <= vdot <= 44

        # Save profile
        error = profile_service.save_profile(profile)
        assert error is None

        # Step 4: Reload and verify
        loaded = profile_service.load_profile()
        assert loaded is not None
        assert not isinstance(loaded, ProfileError)
        assert loaded.name == "Integration Test Athlete"
        assert loaded.email == "test@example.com"
        assert loaded.goal.type == GoalType.HALF_MARATHON
        assert loaded.goal.race_name == "Paris Half"
        assert len(loaded.constraints.available_run_days) == 2
        assert Weekday.TUESDAY in loaded.constraints.available_run_days

        # Step 5: Update profile
        updated = profile_service.update_profile({"age": 33})
        assert not isinstance(updated, ProfileError)
        assert updated.age == 33
        assert updated.name == "Integration Test Athlete"  # Other fields preserved

        # Step 6: Verify update persisted
        reloaded = profile_service.load_profile()
        assert reloaded.age == 33

    def test_concurrent_writes_with_locking(self, tmp_path, monkeypatch):
        """Test that locking prevents data corruption from concurrent writes."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "config").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()

        # Acquire lock
        lock1 = repo.acquire_lock("operation1", paths=["data/athlete/profile.yaml"])
        assert not isinstance(lock1, RepoError)
        assert lock1.operation == "operation1"

        # Try to acquire same lock (should timeout quickly)
        lock2 = repo.acquire_lock("operation2", timeout_ms=100)
        assert isinstance(lock2, RepoError)
        assert lock2.error_type.value == "lock_timeout"

        # Release and retry
        repo.release_lock(lock1)
        lock3 = repo.acquire_lock("operation3")
        assert not isinstance(lock3, RepoError)
        repo.release_lock(lock3)

    def test_profile_workflow_with_validation_errors(self, tmp_path, monkeypatch):
        """Test profile workflow handles validation errors correctly."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        # Create profile with invalid constraints
        constraints = TrainingConstraints(
            available_run_days=[],  # No days
            min_run_days_per_week=0,
            max_run_days_per_week=0,
        )
        goal = Goal(type=GoalType.MARATHON)  # Race goal requires run days

        # Validation should catch this
        validation = validate_constraints(constraints, goal)
        assert not validation.valid
        assert any(
            e.severity == "error" and "race-focused" in e.message
            for e in validation.errors
        )

    def test_vdot_calculation_workflow(self, tmp_path, monkeypatch):
        """Test VDOT calculation for various race distances."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        # Test multiple race times
        test_cases = [
            (RaceDistance.FIVE_K, "22:30", 42, 45),
            (RaceDistance.TEN_K, "47:00", 42, 44),
            (RaceDistance.HALF_MARATHON, "1:48:00", 41, 43),
            (RaceDistance.MARATHON, "3:30:00", 43, 47),
        ]

        for distance, time, min_vdot, max_vdot in test_cases:
            vdot = calculate_vdot(distance, time)
            assert not isinstance(vdot, ProfileError)
            assert min_vdot <= vdot <= max_vdot

    def test_atomic_writes_prevent_corruption(self, tmp_path, monkeypatch):
        """Test that atomic writes prevent partial file corruption."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        # Create initial profile
        profile = AthleteProfile(
            name="Test",
            created_at="2026-01-12",
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.ASK_EACH_TIME,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.MONDAY],
                min_run_days_per_week=1,
                max_run_days_per_week=1,
            ),
            goal=Goal(type=GoalType.TEN_K),
        )

        service.save_profile(profile)

        # Verify file exists and is valid
        profile_path = tmp_path / "data" / "athlete" / "profile.yaml"
        assert profile_path.exists()

        # Read back and verify structure
        loaded = service.load_profile()
        assert loaded is not None
        assert loaded.name == "Test"

        # Update should be atomic
        updated = service.update_profile({"name": "Updated"})
        assert not isinstance(updated, ProfileError)

        # File should still be valid
        reloaded = service.load_profile()
        assert reloaded.name == "Updated"
