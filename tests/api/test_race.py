"""
Unit tests for Race API - Race performance tracking and PB management.
"""

import pytest
from datetime import date as dt_date

from sports_coach_engine.api.race import (
    add_race_performance,
    list_race_history,
    RaceError,
    _update_pb_flags,
    _recalculate_peak_vdot,
)
from sports_coach_engine.schemas.profile import (
    AthleteProfile,
    RacePerformance,
    Goal,
    GoalType,
    TrainingConstraints,
    Weekday,
    RunningPriority,
    ConflictPolicy,
)
from sports_coach_engine.schemas.vdot import RaceSource


class TestAddRacePerformance:
    """Test adding race performances to profile."""

    def test_add_race_success(self, tmp_path, monkeypatch):
        """Should successfully add a race performance."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        # Create minimal profile
        from sports_coach_engine.api.profile import create_profile

        profile = create_profile(
            name="Test Athlete",
            min_run_days=2,
            max_run_days=4,
        )

        # Add race
        result = add_race_performance(
            distance="10k",
            time="42:30",
            date="2025-06-15",
            location="City 10K",
            source="official_race",
            notes="Perfect conditions",
        )

        assert not isinstance(result, RaceError)
        assert result.distance == "10k"
        assert result.time == "42:30"
        assert result.vdot == pytest.approx(44, abs=1)
        assert result.is_pb is True  # First race of distance is always PB

    def test_add_race_invalid_distance(self, tmp_path, monkeypatch):
        """Should return error for invalid distance."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        from sports_coach_engine.api.profile import create_profile

        create_profile(name="Test", min_run_days=2, max_run_days=4)

        result = add_race_performance(
            distance="50k",  # Invalid
            time="3:30:00",
            date="2025-06-15",
        )

        assert isinstance(result, RaceError)
        assert "Invalid distance" in result.message

    def test_add_race_invalid_date(self, tmp_path, monkeypatch):
        """Should return error for invalid date format."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        from sports_coach_engine.api.profile import create_profile

        create_profile(name="Test", min_run_days=2, max_run_days=4)

        result = add_race_performance(
            distance="10k",
            time="42:30",
            date="2025/06/15",  # Wrong format
        )

        assert isinstance(result, RaceError)
        assert "Invalid date format" in result.message

    def test_add_race_updates_pb_flag(self, tmp_path, monkeypatch):
        """Should update PB flags when adding faster race."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        from sports_coach_engine.api.profile import create_profile

        create_profile(name="Test", min_run_days=2, max_run_days=4)

        # Add first race
        race1 = add_race_performance(
            distance="10k",
            time="43:00",
            date="2025-05-01",
        )
        assert race1.is_pb is True

        # Add faster race
        race2 = add_race_performance(
            distance="10k",
            time="42:00",  # Faster
            date="2025-06-01",
        )
        assert race2.is_pb is True

        # Check that race history has correct PB flags
        races = list_race_history()
        assert not isinstance(races, RaceError)
        races_10k = races.get("10k", [])
        assert len(races_10k) == 2

        # The faster race (42:00) should be marked as PB
        assert any(r.time == "42:00" and r.is_pb for r in races_10k)


class TestListRaceHistory:
    """Test listing race history."""

    def test_list_empty_history(self, tmp_path, monkeypatch):
        """Should return empty dict for no races."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        from sports_coach_engine.api.profile import create_profile

        create_profile(name="Test", min_run_days=2, max_run_days=4)

        result = list_race_history()
        assert not isinstance(result, RaceError)
        assert result == {}

    def test_list_with_distance_filter(self, tmp_path, monkeypatch):
        """Should filter races by distance."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        from sports_coach_engine.api.profile import create_profile

        create_profile(name="Test", min_run_days=2, max_run_days=4)

        # Add races at different distances
        add_race_performance(distance="5k", time="20:00", date="2025-05-01")
        add_race_performance(distance="10k", time="42:00", date="2025-06-01")

        result = list_race_history(distance_filter="10k")
        assert not isinstance(result, RaceError)
        assert "10k" in result
        assert "5k" not in result

    def test_list_groups_by_distance(self, tmp_path, monkeypatch):
        """Should group races by distance."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        from sports_coach_engine.api.profile import create_profile

        create_profile(name="Test", min_run_days=2, max_run_days=4)

        # Add multiple 10K races
        add_race_performance(distance="10k", time="43:00", date="2025-05-01")
        add_race_performance(distance="10k", time="42:30", date="2025-06-01")
        add_race_performance(distance="5k", time="20:00", date="2025-05-15")

        result = list_race_history()
        assert not isinstance(result, RaceError)
        assert len(result["10k"]) == 2
        assert len(result["5k"]) == 1


class TestPBFlagUpdates:
    """Test PB flag management."""

    def test_update_pb_flags_single_distance(self):
        """Should mark fastest race as PB for each distance."""
        profile = AthleteProfile(
            name="Test",
            created_at="2025-01-01",
            running_priority=RunningPriority.EQUAL,
            conflict_policy=ConflictPolicy.ASK_EACH_TIME,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.MONDAY, Weekday.WEDNESDAY],
                min_run_days_per_week=2,
                max_run_days_per_week=2,
            ),
            goal=Goal(type=GoalType.TEN_K),
            race_history=[
                RacePerformance(
                    distance="10k",
                    time="43:00",
                    date="2025-05-01",
                    source=RaceSource.GPS_WATCH,
                    vdot=46.0,
                    is_pb=False,
                ),
                RacePerformance(
                    distance="10k",
                    time="42:00",  # Faster - highest VDOT
                    date="2025-06-01",
                    source=RaceSource.OFFICIAL_RACE,
                    vdot=48.0,
                    is_pb=False,
                ),
            ],
        )

        _update_pb_flags(profile)

        # The race with VDOT 48 should be marked as PB
        pb_race = next((r for r in profile.race_history if r.vdot == 48.0), None)
        assert pb_race is not None
        assert pb_race.is_pb is True

        # The slower race should not be PB
        slower_race = next((r for r in profile.race_history if r.vdot == 46.0), None)
        assert slower_race is not None
        assert slower_race.is_pb is False


class TestPeakVDOTCalculation:
    """Test peak VDOT calculation."""

    def test_recalculate_peak_vdot(self):
        """Should set peak VDOT to highest VDOT from race history."""
        profile = AthleteProfile(
            name="Test",
            created_at="2025-01-01",
            running_priority=RunningPriority.EQUAL,
            conflict_policy=ConflictPolicy.ASK_EACH_TIME,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.MONDAY, Weekday.WEDNESDAY],
                min_run_days_per_week=2,
                max_run_days_per_week=2,
            ),
            goal=Goal(type=GoalType.TEN_K),
            race_history=[
                RacePerformance(
                    distance="10k",
                    time="43:00",
                    date="2025-05-01",
                    source=RaceSource.GPS_WATCH,
                    vdot=46.0,
                    is_pb=False,
                ),
                RacePerformance(
                    distance="5k",
                    time="19:00",
                    date="2025-06-01",
                    source=RaceSource.OFFICIAL_RACE,
                    vdot=50.0,  # Highest
                    is_pb=True,
                ),
            ],
        )

        _recalculate_peak_vdot(profile)

        assert profile.peak_vdot == 50.0
        assert profile.peak_vdot_date == "2025-06-01"

    def test_recalculate_peak_vdot_empty_history(self):
        """Should set peak VDOT to None if no race history."""
        profile = AthleteProfile(
            name="Test",
            created_at="2025-01-01",
            running_priority=RunningPriority.EQUAL,
            conflict_policy=ConflictPolicy.ASK_EACH_TIME,
            constraints=TrainingConstraints(
                available_run_days=[Weekday.MONDAY, Weekday.WEDNESDAY],
                min_run_days_per_week=2,
                max_run_days_per_week=2,
            ),
            goal=Goal(type=GoalType.TEN_K),
            race_history=[],
        )

        _recalculate_peak_vdot(profile)

        assert profile.peak_vdot is None
        assert profile.peak_vdot_date is None
