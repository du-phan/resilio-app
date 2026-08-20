"""Lock-aware approved-workout evidence reads."""

from datetime import date

from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.workout_evidence import (
    load_approved_workouts_for_date_range_unlocked,
)
from resilio.core.repository import RepositoryIO


def test_unlocked_approved_workout_read_does_not_reenter_held_plan_lock(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()

    with coordinated_plan_lock(repo, "test_approved_workout_read"):
        evidence = load_approved_workouts_for_date_range_unlocked(
            repo,
            window_start=date(2026, 8, 10),
            window_end=date(2026, 8, 16),
        )

    assert evidence.status == "no_plan"
    assert evidence.reason == "planning_state_missing"
