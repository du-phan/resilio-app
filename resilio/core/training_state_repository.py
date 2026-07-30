"""Persistence for provider-neutral wellness and sport-settings snapshots."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import date

from pydantic import TypeAdapter, ValidationError

from resilio.core.repository import RepositoryIO
from resilio.schemas.training_state import SportSettingsSnapshot, WellnessDay

WELLNESS_ROOT = "data/wellness"
SPORT_SETTINGS_PATH = "data/state/sport_settings.json"

_WELLNESS_LIST = TypeAdapter(list[WellnessDay])


def load_wellness(repo: RepositoryIO) -> dict[date, WellnessDay]:
    """Load every persisted wellness day and reject duplicate dates."""
    root = repo.resolve_path(WELLNESS_ROOT)
    if not root.exists():
        return {}
    result: dict[date, WellnessDay] = {}
    for path in sorted(root.glob("????-??.json")):
        try:
            rows = _WELLNESS_LIST.validate_python(json.loads(path.read_text()))
        except (OSError, ValueError, ValidationError) as exc:
            raise ValueError(f"Invalid wellness month {path.name}") from exc
        for row in rows:
            if row.local_date in result:
                raise ValueError(f"Duplicate wellness date {row.local_date.isoformat()}")
            result[row.local_date] = row
    return result


def merge_wellness(
    existing: dict[date, WellnessDay],
    received: list[WellnessDay],
    *,
    replace_window_start: date,
    replace_window_end: date,
) -> tuple[dict[date, WellnessDay], int]:
    """Replace an inclusive provider window while preserving outside history."""
    if replace_window_end < replace_window_start:
        raise ValueError("wellness replacement window is reversed")
    received_by_date = {row.local_date: row for row in received}
    if len(received_by_date) != len(received):
        raise ValueError("provider wellness response contains duplicate dates")
    outside = {
        day: row
        for day, row in existing.items()
        if not replace_window_start <= day <= replace_window_end
    }
    merged = {**outside, **received_by_date}
    changed_dates = {
        day for day in set(existing) | set(merged) if existing.get(day) != merged.get(day)
    }
    return merged, len(changed_dates)


def write_wellness(repo: RepositoryIO, wellness: dict[date, WellnessDay]) -> None:
    """Replace the wellness archive with deterministic monthly documents."""
    root = repo.resolve_path(WELLNESS_ROOT)
    if root.exists():
        shutil.rmtree(root)
    grouped: dict[str, list[WellnessDay]] = defaultdict(list)
    for row in wellness.values():
        grouped[row.local_date.strftime("%Y-%m")].append(row)
    for year_month, rows in sorted(grouped.items()):
        payload = [
            row.model_dump(mode="json") for row in sorted(rows, key=lambda item: item.local_date)
        ]
        error = repo.write_json(f"{WELLNESS_ROOT}/{year_month}.json", payload)
        if error is not None:
            raise OSError(f"Failed to persist wellness month {year_month}: {error}")


def load_sport_settings(
    repo: RepositoryIO,
) -> SportSettingsSnapshot | None:
    result = repo.read_json(SPORT_SETTINGS_PATH, SportSettingsSnapshot)
    if result is None:
        return None
    if not isinstance(result, SportSettingsSnapshot):
        raise ValueError(f"Invalid sport settings snapshot: {result}")
    return result


def write_sport_settings(
    repo: RepositoryIO,
    snapshot: SportSettingsSnapshot,
) -> None:
    error = repo.write_json(SPORT_SETTINGS_PATH, snapshot)
    if error is not None:
        raise OSError(f"Failed to persist sport settings: {error}")
