"""Tests for date utility functions."""
import pytest
from datetime import date, timedelta
from resilio.utils.dates import (
    get_next_monday,
    get_week_boundaries,
    format_week_range,
    validate_week_start,
)


class TestGetNextMonday:
    """Tests for get_next_monday function."""

    def test_from_saturday(self):
        """Next Monday from Saturday should be 2 days ahead."""
        saturday = date(2026, 1, 17)
        result = get_next_monday(saturday)
        assert result == date(2026, 1, 19)
        assert result.weekday() == 0  # Monday

    def test_from_sunday(self):
        """Next Monday from Sunday should be 1 day ahead."""
        sunday = date(2026, 1, 18)
        result = get_next_monday(sunday)
        assert result == date(2026, 1, 19)
        assert result.weekday() == 0

    def test_from_monday(self):
        """Next Monday from Monday should be 7 days ahead."""
        monday = date(2026, 1, 19)
        result = get_next_monday(monday)
        assert result == date(2026, 1, 26)
        assert result.weekday() == 0

    def test_from_tuesday(self):
        """Next Monday from Tuesday should be 6 days ahead."""
        tuesday = date(2026, 1, 20)
        result = get_next_monday(tuesday)
        assert result == date(2026, 1, 26)
        assert result.weekday() == 0

    def test_default_uses_today(self):
        """Should use today's date if none provided."""
        result = get_next_monday()
        assert result.weekday() == 0
        assert result > date.today()


class TestGetWeekBoundaries:
    """Tests for get_week_boundaries function."""

    def test_monday_input(self):
        """Should return Monday-Sunday range."""
        monday = date(2026, 1, 19)
        start, end = get_week_boundaries(monday)

        assert start == date(2026, 1, 19)
        assert end == date(2026, 1, 25)
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 6    # Sunday

    def test_rejects_non_monday(self):
        """Should raise ValueError if input is not Monday."""
        tuesday = date(2026, 1, 20)

        with pytest.raises(ValueError, match="must be Monday"):
            get_week_boundaries(tuesday)

    def test_span_is_7_days(self):
        """Week should always span exactly 7 days."""
        monday = date(2026, 1, 19)
        start, end = get_week_boundaries(monday)

        assert (end - start).days == 6  # Inclusive: Mon-Sun is 6 days apart


class TestFormatWeekRange:
    """Tests for format_week_range function."""

    def test_format_january_week(self):
        """Should format week in January correctly."""
        monday = date(2026, 1, 19)
        result = format_week_range(monday)

        assert result == "Mon Jan 19 - Sun Jan 25"

    def test_format_month_boundary(self):
        """Should handle month boundaries correctly."""
        monday = date(2026, 1, 26)
        result = format_week_range(monday)

        assert result == "Mon Jan 26 - Sun Feb 01"


class TestValidateWeekStart:
    """Tests for validate_week_start function."""

    def test_monday_returns_true(self):
        """Monday should validate as True."""
        monday = date(2026, 1, 19)
        assert validate_week_start(monday) is True

    def test_tuesday_returns_false(self):
        """Tuesday should validate as False."""
        tuesday = date(2026, 1, 20)
        assert validate_week_start(tuesday) is False

    def test_all_weekdays(self):
        """Test all days of week."""
        # Week of Jan 19-25, 2026
        monday = date(2026, 1, 19)

        for i in range(7):
            day = monday + timedelta(days=i)
            expected = (i == 0)  # Only Monday (i=0) should be True
            assert validate_week_start(day) == expected, \
                f"Day {i} ({day.strftime('%A')}) failed"
