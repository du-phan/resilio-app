"""Canonical planning fingerprints and profile-derived constraints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from resilio.schemas.planning.constraints import (
    AthleteManagedSportExpectation,
    PlanningConstraintsSnapshot,
)
from resilio.schemas.planning.plans import TrainingPlan
from resilio.schemas.planning.weeks import WeekPlan
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


def planning_inputs_sha256(profile: AthleteProfile) -> str:
    """Fingerprint only athlete-confirmed fields that constrain planning."""
    payload = {
        "goal": profile.goal.model_dump(mode="json"),
        "constraints": profile.constraints.model_dump(mode="json"),
        "athlete_managed_sports": [
            sport.model_dump(mode="json")
            for sport in profile.athlete_managed_sports
            if sport.active
        ],
        "training_priority": profile.training_priority.model_dump(mode="json"),
        "training_timezone": profile.training_timezone,
    }
    return _canonical_sha256(payload)


def planning_constraints_snapshot(
    profile: AthleteProfile,
) -> PlanningConstraintsSnapshot:
    """Capture the exact profile constraints used to create a plan revision."""
    maximum_duration_minutes = profile.constraints.maximum_session_duration_minutes
    return PlanningConstraintsSnapshot(
        unavailable_run_days=list(profile.constraints.unavailable_run_days),
        minimum_run_days_per_week=(profile.constraints.minimum_run_days_per_week),
        maximum_run_days_per_week=(profile.constraints.maximum_run_days_per_week),
        maximum_session_duration_seconds=(
            maximum_duration_minutes * 60 if maximum_duration_minutes is not None else None
        ),
        athlete_managed_sport_expectations=[
            AthleteManagedSportExpectation(
                sport_name=sport.sport_name,
                participation_pattern=sport.participation_pattern,
                typical_session_duration_seconds=(sport.typical_session_duration_minutes * 60),
                athlete_reported_typical_intensity=(sport.athlete_reported_typical_intensity),
                athlete_context_note=sport.athlete_context_note,
            )
            for sport in profile.athlete_managed_sports
            if sport.active
        ],
        training_priority=profile.training_priority,
        training_timezone=profile.training_timezone,
    )


def plan_skeleton_sha256(plan: TrainingPlan) -> str:
    """Hash immutable plan content, excluding exact weekly workouts."""
    payload = plan.model_dump(mode="json", by_alias=True)
    payload["weeks"] = [
        {
            **week,
            "running_workouts": [],
            "notes": None,
        }
        for week in payload["weeks"]
    ]
    return _canonical_sha256(payload)


def target_week_skeleton_sha256(week: WeekPlan) -> str:
    """Hash the exact macro-week skeleton that weekly content will populate."""
    payload = week.model_dump(mode="json")
    payload["running_workouts"] = []
    payload["notes"] = None
    return _canonical_sha256(payload)


def applied_running_workouts_sha256(week: WeekPlan) -> str:
    """Hash the ordered exact running workouts applied to a macro week."""
    return _canonical_sha256([workout.model_dump(mode="json") for workout in week.running_workouts])
