"""Distance and session-boundary evidence, independent of workout labels."""

from datetime import date, datetime, timedelta, timezone

import pytest

from resilio.core.coaching_context.running_progression import (
    comparison_window,
    distance_change_percent,
    group_recordings,
)
from resilio.schemas.running_progression import RunningRecording


def recording(identifier: str, start: datetime | None, distance_meters: float = 5000):
    return RunningRecording(
        activity_id=identifier,
        canonical_sha256="a" * 64,
        local_date=date(2026, 10, 2),
        start_time_utc=start,
        distance_meters=distance_meters,
        moving_duration_seconds=1800,
        elapsed_duration_seconds=2000,
        surface="road",
        feedback=[],
    )


def test_distance_progression_is_not_weekly_share_or_previous_recovery_run():
    assert distance_change_percent(13000, 10206.45) == pytest.approx(27.3704, abs=0.0001)
    assert distance_change_percent(17000, 15000) == pytest.approx(13.333333)
    assert distance_change_percent(13000, None) is None
    assert distance_change_percent(13000, 0) is None


@pytest.mark.parametrize("pause_seconds, expected_count", [(0, 1), (899, 1), (900, 2), (-1, 2)])
def test_split_recording_pause_boundary(pause_seconds, expected_count):
    start = datetime(2026, 10, 2, 8, tzinfo=timezone.utc)
    sessions, limitations = group_recordings(
        [
            recording("a", start),
            recording("b", start + timedelta(seconds=2000 + pause_seconds)),
        ]
    )
    assert len(sessions) == expected_count
    if expected_count == 1:
        assert sessions[0].distance_meters == 10000
        assert sessions[0].moving_duration_seconds == 3600
        assert sessions[0].elapsed_duration_seconds == 4000
        assert sessions[0].pause_duration_seconds == pause_seconds
        assert sessions[0].wall_span_seconds == 4000 + pause_seconds
    if pause_seconds < 0:
        assert "overlapping_recordings" in limitations


def test_missing_timing_does_not_invent_session_grouping():
    sessions, limitations = group_recordings([recording("a", None), recording("b", None)])
    assert len(sessions) == 2
    assert "missing_recording_start_times" in limitations


def test_future_candidate_has_unobserved_comparator_interval():
    start, end, observed_end = comparison_window(date(2026, 10, 11), date(2026, 10, 5))
    assert (start, end, observed_end) == (date(2026, 9, 11), date(2026, 10, 10), date(2026, 10, 5))


def test_nested_overlaps_never_form_a_demonstrated_joined_session():
    start = datetime(2026, 10, 2, 8, tzinfo=timezone.utc)
    large = recording("a", start).model_copy(update={"elapsed_duration_seconds": 3600})
    small = recording("b", start + timedelta(seconds=600)).model_copy(
        update={"elapsed_duration_seconds": 600, "moving_duration_seconds": 600}
    )
    third = recording("c", start + timedelta(seconds=1260)).model_copy(
        update={"elapsed_duration_seconds": 600, "moving_duration_seconds": 600}
    )
    sessions, limitations = group_recordings([large, small, third])
    assert len(sessions) == 3 and "overlapping_recordings" in limitations


def test_calendar_exposure_and_split_session_supporting_distance_are_distinct():
    from resilio.core.coaching_context.running_progression import _weekly_totals

    start = datetime(2026, 10, 4, 23, 30, tzinfo=timezone.utc)
    sunday = recording("sunday", start, 1000).model_copy(update={"local_date": date(2026, 10, 4)})
    monday = recording("monday", start + timedelta(seconds=2060), 1000).model_copy(
        update={"local_date": date(2026, 10, 5)}
    )
    sessions, _ = group_recordings([sunday, monday])
    assert len(sessions) == 1 and sessions[0].local_date == date(2026, 10, 4)
    week = _weekly_totals(sessions, [sunday, monday], date(2026, 10, 5), date(2026, 10, 11))
    assert week.running_day_count == 1 and week.session_count == 0
    assert week.distance_meters == 1000 and week.supporting_distance_meters == 0
    same_day = monday.model_copy(update={"local_date": sunday.local_date})
    sessions, _ = group_recordings([sunday, same_day])
    week = _weekly_totals(sessions, [sunday, same_day], date(2026, 9, 28), date(2026, 10, 4))
    assert week.distance_meters == 2000 and week.supporting_distance_meters == 0
