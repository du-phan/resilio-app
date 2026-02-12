"""
Unit tests for Profile API (api/profile.py).

Tests get_profile(), update_profile(), and set_goal().
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch

from resilio.api.profile import (
    create_profile,
    get_profile,
    update_profile,
    set_goal,
    add_sport_to_profile,
    remove_sport_from_profile,
    pause_sport_in_profile,
    resume_sport_in_profile,
    ProfileError,
)
from resilio.schemas.profile import (
    AthleteProfile,
    Goal,
    GoalType,
    Weekday,
    TrainingConstraints,
    RunningPriority,
    ConflictPolicy,
    OtherSport,
    PauseReason,
)
from resilio.schemas.repository import RepoError, RepoErrorType


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_profile():
    """Mock AthleteProfile."""
    profile = Mock(spec=AthleteProfile)
    profile.name = "Test Athlete"
    profile.goal = None
    profile.constraints = Mock()
    profile.constraints.runs_per_week = 3
    return profile


@pytest.fixture
def mock_profile_with_goal():
    """Mock AthleteProfile with goal."""
    profile = Mock(spec=AthleteProfile)
    profile.name = "Test Athlete"
    profile.goal = Mock(spec=Goal)
    profile.goal.type = GoalType.HALF_MARATHON
    profile.goal.target_date = date.today() + timedelta(weeks=12)
    return profile


@pytest.fixture
def mock_log():
    """Mock logger (unused in most tests, but kept for compatibility)."""
    return Mock()


# ============================================================
# GET_PROFILE TESTS
# ============================================================


class TestGetProfile:
    """Test get_profile() function."""
    @patch("resilio.api.profile.RepositoryIO")
    def test_get_profile_success(self, mock_repo_cls, mock_log, mock_profile):
        """Test successful profile retrieval."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock loading profile
        mock_repo.read_yaml.return_value = mock_profile

        result = get_profile()

        # Should return AthleteProfile
        assert isinstance(result, Mock)  # Mock of AthleteProfile
        assert result == mock_profile
        assert result.name == "Test Athlete"

    @patch("resilio.api.profile.RepositoryIO")
    def test_get_profile_with_goal(self, mock_repo_cls, mock_log, mock_profile_with_goal):
        """Test profile retrieval with goal set."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile_with_goal

        result = get_profile()

        # Should return AthleteProfile with goal
        assert isinstance(result, Mock)
        assert result.goal is not None
        assert result.goal.type == GoalType.HALF_MARATHON

    @patch("resilio.api.profile.RepositoryIO")
    def test_get_profile_not_found(self, mock_repo_cls, mock_log):
        """Test profile retrieval when file not found."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock file not found error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "File not found")

        result = get_profile()

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "not_found"
        assert "Failed to load profile" in result.message

    @patch("resilio.api.profile.RepositoryIO")
    def test_get_profile_validation_error(self, mock_repo_cls, mock_log):
        """Test profile retrieval with validation error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock validation error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.VALIDATION_ERROR, "Invalid profile data")

        result = get_profile()

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "Failed to load profile" in result.message


# ============================================================
# UPDATE_PROFILE TESTS
# ============================================================


class TestUpdateProfile:
    """Test update_profile() function."""
    @patch("resilio.api.profile.RepositoryIO")
    @patch("resilio.api.profile.AthleteProfile")
    def test_update_profile_success(self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile):
        """Test successful profile update."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock loading profile
        mock_repo.read_yaml.return_value = mock_profile

        # Mock validation
        mock_profile_cls.model_validate.return_value = mock_profile
        mock_profile.model_dump.return_value = {"name": "Test Athlete"}

        # Mock saving
        mock_repo.write_yaml.return_value = None

        result = update_profile(name="Updated Athlete")

        # Should return updated AthleteProfile
        assert isinstance(result, Mock)
        assert result == mock_profile

        # Verify save was called
        mock_repo.write_yaml.assert_called_once()

    @patch("resilio.api.profile.RepositoryIO")
    def test_update_profile_invalid_field(self, mock_repo_cls, mock_log, mock_profile):
        """Test updating profile with invalid field."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile

        result = update_profile(invalid_field="value")

        # Should return ProfileError (Pydantic catches invalid fields during validation)
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "validation error" in result.message.lower()

    @patch("resilio.api.profile.RepositoryIO")
    def test_update_profile_not_found(self, mock_repo_cls, mock_log):
        """Test updating profile when file not found."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock file not found
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "File not found")

        result = update_profile(name="Updated Athlete")

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "not_found"
        assert "Failed to load profile" in result.message

    @patch("resilio.api.profile.RepositoryIO")
    @patch("resilio.api.profile.AthleteProfile")
    def test_update_profile_validation_error(
        self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile
    ):
        """Test updating profile with validation error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile

        # Mock validation error
        mock_profile.model_dump.return_value = {"name": "Test"}
        mock_profile_cls.model_validate.side_effect = Exception("Validation failed")

        result = update_profile(name="Updated")

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "Invalid profile data" in result.message

    @patch("resilio.api.profile.RepositoryIO")
    @patch("resilio.api.profile.AthleteProfile")
    def test_update_profile_save_error(
        self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile
    ):
        """Test updating profile with save error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile
        mock_profile.model_dump.return_value = {"name": "Test"}
        mock_profile_cls.model_validate.return_value = mock_profile

        # Mock save error
        mock_repo.write_yaml.return_value = RepoError(RepoErrorType.WRITE_ERROR, "Write failed")

        result = update_profile(name="Updated")

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "unknown"
        assert "Failed to save profile" in result.message


# ============================================================
# SET_GOAL TESTS
# ============================================================


class TestSetGoal:
    """Test set_goal() function."""
    @patch("resilio.api.profile.RepositoryIO")
    def test_set_goal_success(self, mock_repo_cls, mock_log, mock_profile):
        """Test successful goal setting."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock loading and saving profile
        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        target_date = date.today() + timedelta(weeks=12)
        result = set_goal(
            race_type="half_marathon",
            target_date=target_date,
            target_time="1:45:00",
        )

        # Should return Goal
        assert isinstance(result, Goal)
        assert result.type == GoalType.HALF_MARATHON
        assert result.target_date == target_date.isoformat()  # Goal stores as ISO string
        assert result.target_time == "1:45:00"

    @patch("resilio.api.profile.RepositoryIO")
    def test_set_goal_invalid_race_type(self, mock_repo_cls, mock_log):
        """Test setting goal with invalid race type."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        result = set_goal(
            race_type="invalid_race",
            target_date=date.today() + timedelta(weeks=12),
        )

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "Invalid race type" in result.message

    @patch("resilio.api.profile.RepositoryIO")
    def test_set_goal_profile_not_found(self, mock_repo_cls, mock_log):
        """Test setting goal when profile not found."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock profile load error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "Profile not found")

        result = set_goal(
            race_type="half_marathon",
            target_date=date.today() + timedelta(weeks=12),
        )

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "not_found"
        assert "Failed to load profile" in result.message

    @patch("resilio.api.profile.RepositoryIO")
    def test_set_goal_save_error(self, mock_repo_cls, mock_log, mock_profile):
        """Test setting goal with save error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile

        # Mock save error
        mock_repo.write_yaml.return_value = RepoError(RepoErrorType.WRITE_ERROR, "Write failed")

        result = set_goal(
            race_type="half_marathon",
            target_date=date.today() + timedelta(weeks=12),
        )

        # Should return ProfileError
        assert isinstance(result, ProfileError)
        assert result.error_type == "unknown"
        assert "Failed to save profile" in result.message

    @patch("resilio.api.profile.RepositoryIO")
    def test_set_goal_plan_generation_error(
        self, mock_repo_cls, mock_log, mock_profile
    ):
        """Goal setting no longer performs plan generation in profile API."""

        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = RepoError(RepoErrorType.WRITE_ERROR, "write failed")

        result = set_goal(
            race_type="half_marathon",
            target_date=date.today() + timedelta(weeks=12),
        )

        # Should return save error from profile write
        assert isinstance(result, ProfileError)
        assert result.error_type == "unknown"
        assert "failed to save profile" in result.message.lower()

    @patch("resilio.api.profile.RepositoryIO")
    def test_set_goal_without_target_time(
        self, mock_repo_cls, mock_log, mock_profile
    ):
        """Test setting goal without target time."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        target_date = date.today() + timedelta(weeks=12)
        result = set_goal(
            race_type="10k",
            target_date=target_date,
        )

        # Should return Goal without target_time
        assert isinstance(result, Goal)
        assert result.type == GoalType.TEN_K
        assert result.target_date == target_date.isoformat()  # Goal stores as ISO string
        assert result.target_time is None


# ============================================================
# PR1: NEW FIELD TESTS
# ============================================================


class TestPR1NewFields:
    """Test new profile fields added in PR1."""
    @patch("resilio.api.profile.RepositoryIO")
    @patch("resilio.api.profile.AthleteProfile")
    def test_update_profile_dict_merge_not_setattr(
        self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile
    ):
        """Verify update_profile uses dict-merging instead of setattr."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        # Mock model_dump to return dict
        mock_profile.model_dump.return_value = {"name": "Test", "age": 30}

        # Mock model_validate to return updated profile
        mock_profile_cls.model_validate.return_value = mock_profile

        result = update_profile(age=35)

        # Verify dict-merging was used (model_dump + model_validate)
        mock_profile.model_dump.assert_called_once_with(mode='json')
        mock_profile_cls.model_validate.assert_called_once()
        assert isinstance(result, Mock)

    @patch("resilio.api.profile.RepositoryIO")
    @patch("resilio.api.profile.AthleteProfile")
    def test_update_profile_with_vdot(
        self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile
    ):
        """Test updating profile with vdot field."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        mock_profile.model_dump.return_value = {"name": "Test", "vdot": None}
        mock_profile_cls.model_validate.return_value = mock_profile

        result = update_profile(vdot=48.5)

        assert isinstance(result, Mock)
        mock_repo.write_yaml.assert_called_once()

    @patch("resilio.api.profile.RepositoryIO")
    @patch("resilio.api.profile.AthleteProfile")
    def test_update_profile_with_running_experience_years(
        self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile
    ):
        """Test updating profile with running_experience_years field."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        mock_profile.model_dump.return_value = {"name": "Test", "running_experience_years": None}
        mock_profile_cls.model_validate.return_value = mock_profile

        result = update_profile(running_experience_years=3)

        assert isinstance(result, Mock)
        mock_repo.write_yaml.assert_called_once()

    @patch("resilio.api.profile.RepositoryIO")
    @patch("resilio.api.profile.AthleteProfile")
    def test_update_profile_with_weekly_km(
        self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile
    ):
        """Test updating profile with current_weekly_run_km field."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.read_yaml.return_value = mock_profile
        mock_repo.write_yaml.return_value = None

        mock_profile.model_dump.return_value = {"name": "Test", "current_weekly_run_km": None}
        mock_profile_cls.model_validate.return_value = mock_profile

        result = update_profile(current_weekly_run_km=22.5)

        assert isinstance(result, Mock)
        mock_repo.write_yaml.assert_called_once()

    @patch("resilio.api.profile.RepositoryIO")
    @patch("resilio.api.profile.AthleteProfile")
    def test_update_profile_validation_immediate(
        self, mock_profile_cls, mock_repo_cls, mock_log, mock_profile
    ):
        """Test that Pydantic validation happens immediately during update."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.read_yaml.return_value = mock_profile

        mock_profile.model_dump.return_value = {"name": "Test", "vdot": None}

        # Mock Pydantic validation error
        mock_profile_cls.model_validate.side_effect = ValueError("VDOT must be between 30-85")

        result = update_profile(vdot=150)  # Invalid VDOT

        # Should return ProfileError due to validation failure
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "Invalid profile data" in result.message


class TestPR2ConstraintFields:
    """Test constraint fields added in PR2."""
    @patch("resilio.api.profile.RepositoryIO")
    def test_create_profile_with_unavailable_days(self, mock_repo_cls, mock_log):
        """Test creating profile with unavailable_run_days constraint."""
        from resilio.schemas.profile import Weekday

        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.read_yaml.return_value = None  # No existing profile
        mock_repo.write_yaml.return_value = None

        unavailable_days = [Weekday.TUESDAY, Weekday.THURSDAY]

        result = create_profile(
            name="Test Athlete",
            unavailable_run_days=unavailable_days,
        )

        # Should return AthleteProfile
        assert isinstance(result, AthleteProfile)
        assert result.name == "Test Athlete"
        assert result.constraints.unavailable_run_days == unavailable_days

    @patch("resilio.api.profile.RepositoryIO")
    def test_create_profile_constraint_defaults(self, mock_repo_cls, mock_log):
        """Test that constraint fields use sensible defaults when not provided."""
        from resilio.schemas.profile import Weekday

        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.read_yaml.return_value = None  # No existing profile
        mock_repo.write_yaml.return_value = None

        result = create_profile(name="Test Athlete")

        # Should return AthleteProfile with defaults
        assert isinstance(result, AthleteProfile)
        # Default: no unavailable days (all days available)
        assert len(result.constraints.unavailable_run_days) == 0


class TestSportCommitments:
    """Tests for add/remove/pause/resume sport profile APIs."""

    @staticmethod
    def _base_profile() -> AthleteProfile:
        return AthleteProfile(
            name="Test Athlete",
            created_at="2026-02-09",
            constraints=TrainingConstraints(
                unavailable_run_days=[Weekday.TUESDAY],
                min_run_days_per_week=3,
                max_run_days_per_week=5,
            ),
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.RUNNING_GOAL_WINS,
            goal=Goal(type=GoalType.GENERAL_FITNESS),
            other_sports=[],
        )

    @patch("resilio.api.profile.RepositoryIO")
    def test_add_sport_with_unavailable_days(self, mock_repo_cls, mock_log):
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        profile = self._base_profile()
        mock_repo.read_yaml.return_value = profile
        mock_repo.write_yaml.return_value = None

        result = add_sport_to_profile(
            sport="climbing",
            frequency=2,
            unavailable_days=[Weekday.TUESDAY, Weekday.THURSDAY],
            duration=90,
        )

        assert isinstance(result, AthleteProfile)
        assert len(result.other_sports) == 1
        sport = result.other_sports[0]
        assert sport.sport == "climbing"
        assert sport.unavailable_days == [Weekday.TUESDAY, Weekday.THURSDAY]
        assert sport.frequency_per_week == 2

    @patch("resilio.api.profile.RepositoryIO")
    def test_add_sport_frequency_only(self, mock_repo_cls, mock_log):
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        profile = self._base_profile()
        mock_repo.read_yaml.return_value = profile
        mock_repo.write_yaml.return_value = None

        result = add_sport_to_profile(
            sport="cycling",
            frequency=3,
            duration=75,
        )

        assert isinstance(result, AthleteProfile)
        added = result.other_sports[0]
        assert added.frequency_per_week == 3
        assert added.unavailable_days is None

    @patch("resilio.api.profile.RepositoryIO")
    def test_add_sport_missing_profile_returns_not_found(self, mock_repo_cls, mock_log):
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "missing")

        result = add_sport_to_profile(sport="climbing", frequency=2)

        assert isinstance(result, ProfileError)
        assert result.error_type == "not_found"

    @patch("resilio.api.profile.RepositoryIO")
    def test_add_sport_requires_frequency(self, mock_repo_cls, mock_log):
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        profile = self._base_profile()
        mock_repo.read_yaml.return_value = profile

        result = add_sport_to_profile(sport="climbing")
        assert isinstance(result, ProfileError)
        assert result.error_type == "validation"
        assert "Missing required frequency" in result.message

    @patch("resilio.api.profile.RepositoryIO")
    def test_remove_sport_missing_profile_returns_not_found(self, mock_repo_cls, mock_log):
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "missing")

        result = remove_sport_from_profile(sport="climbing")

        assert isinstance(result, ProfileError)
        assert result.error_type == "not_found"

    @patch("resilio.api.profile.RepositoryIO")
    def test_pause_and_resume_sport(self, mock_repo_cls, mock_log):
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        profile = self._base_profile()
        profile.other_sports = [
            OtherSport(
                sport="climbing",
                frequency_per_week=1,
                unavailable_days=[Weekday.MONDAY],
                typical_duration_minutes=120,
            )
        ]

        mock_repo.read_yaml.return_value = profile
        mock_repo.write_yaml.return_value = None

        paused = pause_sport_in_profile(
            sport="climbing",
            reason="focus_running",
            paused_at="2026-02-09",
        )
        assert isinstance(paused, AthleteProfile)
        assert paused.other_sports[0].active is False
        assert paused.other_sports[0].pause_reason == PauseReason.FOCUS_RUNNING
        assert paused.other_sports[0].paused_at == "2026-02-09"

        resumed = resume_sport_in_profile(sport="climbing")
        assert isinstance(resumed, AthleteProfile)
        assert resumed.other_sports[0].active is True
        assert resumed.other_sports[0].pause_reason is None
        assert resumed.other_sports[0].paused_at is None
