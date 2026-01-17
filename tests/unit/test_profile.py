"""
Unit tests for M4 - Athlete Profile Service module.

Tests profile CRUD operations, constraint validation, and error handling.
"""

import pytest
from sports_coach_engine.core.profile import (
    ProfileService,
    ProfileError,
    ProfileErrorType,
)
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.profile import (
    AthleteProfile,
    Goal,
    GoalType,
    TrainingConstraints,
    Weekday,
    RunningPriority,
    ConflictPolicy,
)


class TestProfileService:
    """Tests for ProfileService class."""

    def test_load_profile_returns_none_when_not_exists(self, tmp_path, monkeypatch):
        """Should return None when profile doesn't exist."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "data" / "athlete").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        result = service.load_profile()

        assert result is None

    def test_save_and_load_profile(self, tmp_path, monkeypatch):
        """Should save and load profile successfully."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        profile = AthleteProfile(
            name="Test Athlete",
            created_at="2026-01-12",
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.RUNNING_GOAL_WINS,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.TUESDAY, Weekday.SATURDAY],
                min_run_days_per_week=2,
                max_run_days_per_week=3,
            ),
            goal=Goal(type=GoalType.TEN_K),
        )

        error = service.save_profile(profile)
        assert error is None

        loaded = service.load_profile()
        assert loaded is not None
        assert not isinstance(loaded, ProfileError)
        assert loaded.name == "Test Athlete"
        assert loaded.running_priority == RunningPriority.PRIMARY

    def test_save_profile_creates_athlete_directory(self, tmp_path, monkeypatch):
        """Should create data/athlete/ directory if it doesn't exist."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        profile = AthleteProfile(
            name="Test Athlete",
            created_at="2026-01-12",
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.ASK_EACH_TIME,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.MONDAY],
                min_run_days_per_week=1,
                max_run_days_per_week=1,
            ),
            goal=Goal(type=GoalType.GENERAL_FITNESS),
        )

        error = service.save_profile(profile)
        assert error is None
        assert (tmp_path / "data" / "athlete" / "profile.yaml").exists()

    def test_update_profile_merges_changes(self, tmp_path, monkeypatch):
        """Should merge updates with existing profile."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        # Create initial profile
        profile = AthleteProfile(
            name="Original Name",
            created_at="2026-01-12",
            running_priority=RunningPriority.SECONDARY,
            primary_sport="climbing",
            conflict_policy=ConflictPolicy.PRIMARY_SPORT_WINS,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.TUESDAY, Weekday.THURSDAY],
                min_run_days_per_week=2,
                max_run_days_per_week=2,
            ),
            goal=Goal(type=GoalType.FIVE_K),
        )
        service.save_profile(profile)

        # Update name
        result = service.update_profile({"name": "Updated Name"})

        assert not isinstance(result, ProfileError)
        assert result.name == "Updated Name"
        assert result.running_priority == RunningPriority.SECONDARY
        assert result.primary_sport == "climbing"

        # Verify saved to disk
        loaded = service.load_profile()
        assert loaded.name == "Updated Name"

    def test_update_profile_returns_error_when_profile_not_found(
        self, tmp_path, monkeypatch
    ):
        """Should return error when trying to update non-existent profile."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        result = service.update_profile({"name": "New Name"})

        assert isinstance(result, ProfileError)
        assert result.error_type == ProfileErrorType.PROFILE_NOT_FOUND

    def test_update_profile_returns_error_on_validation_failure(
        self, tmp_path, monkeypatch
    ):
        """Should return error when update causes validation failure."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        # Create valid profile
        profile = AthleteProfile(
            name="Test",
            created_at="2026-01-12",
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.RUNNING_GOAL_WINS,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.MONDAY],
                min_run_days_per_week=1,
                max_run_days_per_week=1,
            ),
            goal=Goal(type=GoalType.TEN_K),
        )
        service.save_profile(profile)

        # Try to update with invalid data (missing required field)
        result = service.update_profile({"name": None})

        assert isinstance(result, ProfileError)
        assert result.error_type == ProfileErrorType.VALIDATION_ERROR

    def test_delete_profile_removes_file(self, tmp_path, monkeypatch):
        """Should delete profile file successfully."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        # Create profile
        profile = AthleteProfile(
            name="Test",
            created_at="2026-01-12",
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.ASK_EACH_TIME,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.FRIDAY],
                min_run_days_per_week=1,
                max_run_days_per_week=1,
            ),
            goal=Goal(type=GoalType.GENERAL_FITNESS),
        )
        service.save_profile(profile)

        profile_path = tmp_path / "data" / "athlete" / "profile.yaml"
        assert profile_path.exists()

        # Delete
        error = service.delete_profile()
        assert error is None
        assert not profile_path.exists()

    def test_delete_profile_returns_error_when_not_found(self, tmp_path, monkeypatch):
        """Should return error when trying to delete non-existent profile."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        error = service.delete_profile()

        assert isinstance(error, ProfileError)
        assert error.error_type == ProfileErrorType.PROFILE_NOT_FOUND

    def test_profile_with_optional_fields(self, tmp_path, monkeypatch):
        """Should handle profiles with optional fields populated."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        repo = RepositoryIO()
        service = ProfileService(repo)

        from sports_coach_engine.schemas.profile import (
            StravaConnection,
            RecentRace,
            OtherSport,
        )

        profile = AthleteProfile(
            name="Complete Profile",
            email="test@example.com",
            created_at="2026-01-12",
            age=32,
            strava=StravaConnection(athlete_id="12345678"),
            running_experience_years=5,
            recent_race=RecentRace(distance="10k", time="47:00", date="2025-04-20"),
            current_weekly_run_km=28.0,
            current_run_days_per_week=3,
            running_priority=RunningPriority.SECONDARY,
            primary_sport="bouldering",
            conflict_policy=ConflictPolicy.PRIMARY_SPORT_WINS,
            constraints=TrainingConstraints(
                available_run_days=[
                    Weekday.TUESDAY,
                    Weekday.WEDNESDAY,
                    Weekday.SATURDAY,
                ],
                preferred_run_days=[Weekday.TUESDAY, Weekday.SATURDAY],
                min_run_days_per_week=2,
                max_run_days_per_week=3,
            ),
            goal=Goal(
                type=GoalType.HALF_MARATHON,
                race_name="Paris Half",
                target_date="2026-03-01",
                target_time="1:45:00",
            ),
            other_sports=[
                OtherSport(
                    sport="bouldering",
                    days=[Weekday.MONDAY, Weekday.THURSDAY],
                    typical_duration_minutes=120,
                    typical_intensity="moderate_to_hard",
                    is_fixed=True,
                )
            ],
        )

        error = service.save_profile(profile)
        assert error is None

        loaded = service.load_profile()
        assert loaded is not None
        assert loaded.email == "test@example.com"
        assert loaded.age == 32
        assert loaded.strava.athlete_id == "12345678"
        assert loaded.recent_race.time == "47:00"
        assert len(loaded.other_sports) == 1
        assert loaded.other_sports[0].sport == "bouldering"


class TestProfileValidation:
    """Tests for profile schema validation."""

    def test_profile_validates_constraint_ranges(self, tmp_path, monkeypatch):
        """Should validate min/max run days ranges."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        with pytest.raises(Exception):  # Pydantic validation error
            AthleteProfile(
                name="Test",
                created_at="2026-01-12",
                running_priority=RunningPriority.PRIMARY,
                conflict_policy=ConflictPolicy.ASK_EACH_TIME,
                constraints=TrainingConstraints(
                    available_run_days=[Weekday.MONDAY],
                    min_run_days_per_week=1,
                    max_run_days_per_week=10,  # Invalid: > 7
                ),
                goal=Goal(type=GoalType.TEN_K),
            )

    def test_profile_validates_age_range(self, tmp_path, monkeypatch):
        """Should validate age is within reasonable range."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        with pytest.raises(Exception):  # Pydantic validation error
            AthleteProfile(
                name="Test",
                created_at="2026-01-12",
                age=150,  # Invalid: > 120
                running_priority=RunningPriority.PRIMARY,
                conflict_policy=ConflictPolicy.ASK_EACH_TIME,
                constraints=TrainingConstraints(
                    available_run_days=[Weekday.MONDAY],
                    min_run_days_per_week=1,
                    max_run_days_per_week=1,
                ),
                goal=Goal(type=GoalType.TEN_K),
            )


class TestVDOTCalculation:
    """Tests for VDOT calculation."""

    def test_calculate_vdot_for_10k_47min(self):
        """Should calculate VDOT ~43 for 47:00 10K."""
        from sports_coach_engine.core.profile import calculate_vdot, RaceDistance

        vdot = calculate_vdot(RaceDistance.TEN_K, "47:00")

        assert not isinstance(vdot, ProfileError)
        assert 42 <= vdot <= 44  # Expected VDOT ~43

    def test_calculate_vdot_for_5k_22min(self):
        """Should calculate VDOT ~43.5 for 22:30 5K."""
        from sports_coach_engine.core.profile import calculate_vdot, RaceDistance

        vdot = calculate_vdot(RaceDistance.FIVE_K, "22:30")

        assert not isinstance(vdot, ProfileError)
        assert 42 <= vdot <= 45

    def test_calculate_vdot_for_marathon(self):
        """Should calculate VDOT for marathon time."""
        from sports_coach_engine.core.profile import calculate_vdot, RaceDistance

        # 3:30:00 marathon ~ VDOT 45
        vdot = calculate_vdot(RaceDistance.MARATHON, "3:30:00")

        assert not isinstance(vdot, ProfileError)
        assert 43 <= vdot <= 47

    def test_calculate_vdot_invalid_time_format(self):
        """Should return error for invalid time format."""
        from sports_coach_engine.core.profile import calculate_vdot, RaceDistance

        result = calculate_vdot(RaceDistance.TEN_K, "invalid")

        assert isinstance(result, ProfileError)
        assert result.error_type == ProfileErrorType.VALIDATION_ERROR

    def test_parse_time_to_seconds_mmss(self):
        """Should parse MM:SS format correctly."""
        from sports_coach_engine.core.profile import parse_time_to_seconds

        seconds = parse_time_to_seconds("47:00")
        assert seconds == 2820  # 47 * 60

    def test_parse_time_to_seconds_hhmmss(self):
        """Should parse HH:MM:SS format correctly."""
        from sports_coach_engine.core.profile import parse_time_to_seconds

        seconds = parse_time_to_seconds("3:30:00")
        assert seconds == 12600  # 3*3600 + 30*60


class TestConstraintValidation:
    """Tests for constraint validation."""

    def test_validate_constraints_valid(self):
        """Should validate correct constraints."""
        from sports_coach_engine.core.profile import validate_constraints

        constraints = TrainingConstraints(
            available_run_days=[Weekday.TUESDAY, Weekday.SATURDAY],
            min_run_days_per_week=2,
            max_run_days_per_week=3,
        )
        goal = Goal(type=GoalType.TEN_K)

        result = validate_constraints(constraints, goal)

        assert result.valid
        assert len(result.errors) == 0

    def test_validate_constraints_error_max_less_than_min(self):
        """Should error when max < min."""
        from sports_coach_engine.core.profile import validate_constraints

        constraints = TrainingConstraints(
            available_run_days=[Weekday.TUESDAY],
            min_run_days_per_week=3,
            max_run_days_per_week=2,  # Invalid: max < min
        )
        goal = Goal(type=GoalType.TEN_K)

        result = validate_constraints(constraints, goal)

        assert not result.valid
        assert any(
            e.field == "max_run_days_per_week" and e.severity == "error"
            for e in result.errors
        )

    def test_validate_constraints_warning_insufficient_days(self):
        """Should warn when available days < min days."""
        from sports_coach_engine.core.profile import validate_constraints

        constraints = TrainingConstraints(
            available_run_days=[Weekday.TUESDAY],  # Only 1 day
            min_run_days_per_week=3,  # But need 3 days
            max_run_days_per_week=4,
        )
        goal = Goal(type=GoalType.TEN_K)

        result = validate_constraints(constraints, goal)

        # Should be valid (warning, not error)
        assert result.valid
        assert any(
            e.field == "available_run_days" and e.severity == "warning"
            for e in result.errors
        )

    def test_validate_constraints_error_no_days_race_goal(self):
        """Should error when no run days with race goal."""
        from sports_coach_engine.core.profile import validate_constraints

        constraints = TrainingConstraints(
            available_run_days=[],  # No days
            min_run_days_per_week=0,
            max_run_days_per_week=0,
        )
        goal = Goal(type=GoalType.HALF_MARATHON)  # Race goal

        result = validate_constraints(constraints, goal)

        assert not result.valid
        assert any(
            e.field == "available_run_days"
            and e.severity == "error"
            and "race-focused" in e.message
            for e in result.errors
        )

    def test_validate_constraints_allows_no_days_general_fitness(self):
        """Should allow no run days with general fitness goal."""
        from sports_coach_engine.core.profile import validate_constraints

        constraints = TrainingConstraints(
            available_run_days=[],
            min_run_days_per_week=0,
            max_run_days_per_week=0,
        )
        goal = Goal(type=GoalType.GENERAL_FITNESS)

        result = validate_constraints(constraints, goal)

        # Should be valid (no race goal)
        assert result.valid

    def test_validate_constraints_warning_consecutive_days(self):
        """Should warn when all days are consecutive."""
        from sports_coach_engine.core.profile import validate_constraints

        constraints = TrainingConstraints(
            available_run_days=[
                Weekday.MONDAY,
                Weekday.TUESDAY,
                Weekday.WEDNESDAY,
            ],  # All consecutive
            min_run_days_per_week=3,
            max_run_days_per_week=3,
        )
        goal = Goal(type=GoalType.TEN_K)

        result = validate_constraints(constraints, goal)

        # Should be valid (warning only)
        assert result.valid
        assert any(
            e.field == "available_run_days"
            and e.severity == "warning"
            and "Back-to-back" in e.message
            for e in result.errors
        )

    def test_validate_constraints_no_warning_non_consecutive(self):
        """Should not warn when days are not all consecutive."""
        from sports_coach_engine.core.profile import validate_constraints

        constraints = TrainingConstraints(
            available_run_days=[
                Weekday.TUESDAY,
                Weekday.THURSDAY,
                Weekday.SATURDAY,
            ],  # Not all consecutive
            min_run_days_per_week=3,
            max_run_days_per_week=3,
        )
        goal = Goal(type=GoalType.TEN_K)

        result = validate_constraints(constraints, goal)

        assert result.valid
        assert not any(
            "Back-to-back" in e.message for e in result.errors
        )
