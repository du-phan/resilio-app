"""Canonical planning fingerprints and profile-derived constraints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from resilio.schemas.plan import (
    MasterPlan,
    OtherSportPlanningConstraint,
    PlanningConstraintsSnapshot,
    WeekPlan,
)
from resilio.schemas.profile import AthleteProfile


def _canonical_sha256(value: BaseModel | dict[str, Any] | list[Any]) -> str:
    payload = (
        value.model_dump(mode="json", by_alias=True) if isinstance(value, BaseModel) else value
    )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of exact file bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65_536), b""):
            digest.update(block)
    return digest.hexdigest()


def planning_profile_sha256(profile: AthleteProfile) -> str:
    """Fingerprint only athlete-confirmed fields that constrain planning."""
    payload = {
        "goal": profile.goal.model_dump(mode="json"),
        "constraints": profile.constraints.model_dump(mode="json"),
        "other_sport_commitments": [
            commitment.model_dump(mode="json") for commitment in profile.other_sport_commitments
        ],
        "running_priority": profile.running_priority,
        "primary_sport_name": profile.primary_sport_name,
        "conflict_policy": profile.conflict_policy,
        "training_timezone": profile.training_timezone,
    }
    return _canonical_sha256(payload)


def planning_constraints_snapshot(
    profile: AthleteProfile,
) -> PlanningConstraintsSnapshot:
    """Capture the exact profile constraints used to create a plan revision."""
    maximum_duration_minutes = profile.constraints.maximum_session_duration_minutes
    return PlanningConstraintsSnapshot(
        unavailable_run_days=[day.value for day in profile.constraints.unavailable_run_days],
        minimum_run_days_per_week=(profile.constraints.minimum_run_days_per_week),
        maximum_run_days_per_week=(profile.constraints.maximum_run_days_per_week),
        maximum_session_duration_seconds=(
            maximum_duration_minutes * 60 if maximum_duration_minutes is not None else None
        ),
        active_other_sports=[
            OtherSportPlanningConstraint(
                sport_name=commitment.sport_name,
                sessions_per_week=commitment.sessions_per_week,
                unavailable_days=[day.value for day in commitment.unavailable_days],
                typical_session_duration_seconds=(commitment.typical_session_duration_minutes * 60),
                typical_intensity=commitment.typical_intensity.value,
            )
            for commitment in profile.other_sport_commitments
            if commitment.active
        ],
        running_priority=profile.running_priority.value,
        primary_sport_name=profile.primary_sport_name,
        training_timezone=profile.training_timezone,
    )


def macro_skeleton_sha256(plan: MasterPlan) -> str:
    """Hash immutable macro content, excluding exact weekly workouts."""
    payload = plan.model_dump(mode="json", by_alias=True)
    payload["weeks"] = [
        {
            **week,
            "workouts": [],
            "notes": None,
        }
        for week in payload["weeks"]
    ]
    return _canonical_sha256(payload)


def target_week_skeleton_sha256(week: WeekPlan) -> str:
    """Hash the exact macro-week skeleton that weekly content will populate."""
    payload = week.model_dump(mode="json")
    payload["workouts"] = []
    payload["notes"] = None
    return _canonical_sha256(payload)


def applied_workout_sha256(week: WeekPlan) -> str:
    """Hash the ordered exact workouts applied to a macro week."""
    return _canonical_sha256([workout.model_dump(mode="json") for workout in week.workouts])
