"""Deterministic selection, inventory hashing, and collision classification."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from resilio.core.historical_activity_backfill.rendering import (
    OWNERSHIP_PREFIX,
    RenderedHistoricalActivity,
    assert_remote_matches,
    canonical_json,
    render_manual_activity,
    sha256_json,
    sha256_text,
    source_projection,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO, HiddenActivityDTO
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.historical_backfill import (
    BackfillCoverage,
    BackfillDecision,
    BackfillDecisionAction,
    FrozenBackfillBaseline,
    HistoricalTimeMode,
)
from resilio.schemas.sync import ActivitySyncState


class HistoricalInventoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackfillAnalysis:
    coverage: BackfillCoverage
    decisions: list[BackfillDecision]
    canary_local_activity_id: str | None
    report_payload: dict


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def archive_source_digest(records: Iterable[CanonicalActivity]) -> str:
    payload = []
    for activity in sorted(records, key=lambda item: item.local_activity_id):
        serialized = (
            source_projection(activity)
            if (
                activity.origin.kind == "historical_import"
                and activity.sport == "climb"
            )
            else activity.model_dump(mode="json", by_alias=True)
        )
        payload.append(
            {
                "local_activity_id": activity.local_activity_id,
                "record": serialized,
            }
        )
    return sha256_json(payload)


def sync_state_base_digest(path: Path, backfill_local_ids: set[str]) -> str:
    if not path.exists():
        payload = ActivitySyncState().model_dump(mode="json")
        return sha256_json(payload)
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HistoricalInventoryError("Activity sync state is not valid JSON") from exc
    external_to_local = payload.get("external_to_local")
    if isinstance(external_to_local, dict):
        payload["external_to_local"] = {
            external_id: local_id
            for external_id, local_id in external_to_local.items()
            if local_id not in backfill_local_ids
        }
    return sha256_json(payload)


def _inventory_row(row: ActivityDTO | HiddenActivityDTO) -> dict | None:
    if isinstance(row, ActivityDTO):
        if row.external_id and row.external_id.startswith(OWNERSHIP_PREFIX):
            return None
        return {
            "variant": "visible",
            "id_sha256": sha256_text(row.id),
            "external_id_sha256": (
                sha256_text(row.external_id) if row.external_id else None
            ),
            "type": row.type,
            "name_sha256": sha256_text(row.name),
            "description_sha256": (
                sha256_text(row.description) if row.description else None
            ),
            "start_date": row.start_date.isoformat(),
            "start_date_local": row.start_date_local.isoformat(),
            "elapsed_time": row.elapsed_time,
            "moving_time": row.moving_time,
            "distance": row.distance,
            "total_elevation_gain": row.total_elevation_gain,
            "perceived_exertion": row.perceived_exertion,
        }
    return {
        "variant": "hidden",
        "id_sha256": sha256_text(row.id),
        "start_date_local": row.start_date_local,
        "source": row.source,
    }


def external_inventory_base_digest(
    rows: Iterable[ActivityDTO | HiddenActivityDTO],
) -> str:
    sanitized = [item for row in rows if (item := _inventory_row(row)) is not None]
    sanitized.sort(key=canonical_json)
    return sha256_json(sanitized)


def select_historical_climbs(
    records: Iterable[CanonicalActivity],
) -> list[CanonicalActivity]:
    selected = [
        activity
        for activity in records
        if (
            activity.status == "active"
            and activity.origin.kind == "historical_import"
            and activity.sport == "climb"
        )
    ]
    local_ids = [activity.local_activity_id for activity in selected]
    if len(local_ids) != len(set(local_ids)):
        raise HistoricalInventoryError("Historical climb selection has duplicate local IDs")
    linked = [
        activity.local_activity_id
        for activity in selected
        if activity.origin.intervals_icu_activity_id
    ]
    if linked:
        raise HistoricalInventoryError(
            "Historical climb selection already contains external activity links"
        )
    return sorted(
        selected,
        key=lambda item: (item.date, item.local_activity_id),
    )


def _wall_datetime(value: str | datetime) -> datetime:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed.replace(tzinfo=None)


def _canonical_wall_start(activity: CanonicalActivity) -> datetime | None:
    if activity.occurrence.start_time_local is None:
        return None
    return activity.occurrence.start_time_local.replace(tzinfo=None)


def _hidden_candidate_maps(
    *,
    selected: list[CanonicalActivity],
    all_records: list[CanonicalActivity],
    hidden: list[HiddenActivityDTO],
) -> tuple[dict[str, list[HiddenActivityDTO]], dict[str, list[CanonicalActivity]]]:
    selected_ids = {item.local_activity_id for item in selected}
    by_local: dict[str, list[HiddenActivityDTO]] = {
        item.local_activity_id: [] for item in selected
    }
    by_hidden: dict[str, list[CanonicalActivity]] = {}
    for hidden_row in hidden:
        hidden_start = _wall_datetime(hidden_row.start_date_local)
        candidates = [
            activity
            for activity in all_records
            if (
                activity.status == "active"
                and (start := _canonical_wall_start(activity)) is not None
                and abs((start - hidden_start).total_seconds()) <= 120
            )
        ]
        by_hidden[hidden_row.id] = candidates
        for candidate in candidates:
            if candidate.local_activity_id in selected_ids:
                by_local[candidate.local_activity_id].append(hidden_row)
    return by_local, by_hidden


def _normalized_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def visible_composite_match(
    remote: ActivityDTO,
    rendered: RenderedHistoricalActivity,
) -> bool:
    expected = rendered.payload
    if remote.type not in {"Bouldering", "RockClimbing"}:
        return False
    remote_wall = remote.start_date_local.replace(tzinfo=None)
    expected_wall = expected.start_date_local.replace(tzinfo=None)
    if remote_wall.date() != expected_wall.date():
        return False
    duration_tolerance = max(60, expected.elapsed_time * 0.02)
    duration_matches = (
        abs(remote.elapsed_time - expected.elapsed_time) <= duration_tolerance
        or abs(remote.moving_time - expected.elapsed_time) <= duration_tolerance
    )
    title_matches = _normalized_title(remote.name) == _normalized_title(
        expected.name
    )
    if rendered.time_mode == HistoricalTimeMode.LOCAL_NOON:
        return (
            duration_matches
            and title_matches
            and round(remote.elapsed_time / 60)
            == round(expected.elapsed_time / 60)
        )
    return (
        abs((remote_wall - expected_wall).total_seconds()) <= 120
        and duration_matches
        and title_matches
    )


def analyze_inventory(
    *,
    selected: list[CanonicalActivity],
    all_records: list[CanonicalActivity],
    rows: list[ActivityDTO | HiddenActivityDTO],
    baseline: FrozenBackfillBaseline,
) -> BackfillAnalysis:
    if len(selected) != baseline.selected:
        raise HistoricalInventoryError(
            f"Frozen selection drifted: expected {baseline.selected}, found {len(selected)}"
        )

    rendered = {
        activity.local_activity_id: render_manual_activity(activity)
        for activity in selected
    }
    visible = [row for row in rows if isinstance(row, ActivityDTO)]
    hidden = [row for row in rows if isinstance(row, HiddenActivityDTO)]
    by_external_id: dict[str, list[ActivityDTO]] = {}
    for row in visible:
        if row.external_id:
            by_external_id.setdefault(row.external_id, []).append(row)
    hidden_by_local, canonical_by_hidden = _hidden_candidate_maps(
        selected=selected,
        all_records=all_records,
        hidden=hidden,
    )

    decisions: list[BackfillDecision] = []
    for activity in selected:
        item = rendered[activity.local_activity_id]
        external_id = item.payload.external_id
        owned = by_external_id.get(external_id, [])
        local_hidden = hidden_by_local[activity.local_activity_id]
        visible_conflicts = [
            row
            for row in visible
            if (
                row.external_id != external_id
                and visible_composite_match(row, item)
            )
        ]

        action = BackfillDecisionAction.PUBLISH
        reason: str | None = None
        remote_hash: str | None = None
        if len(owned) > 1:
            action = BackfillDecisionAction.QUARANTINE
            reason = "multiple_owned_external_id_matches"
        elif len(owned) == 1:
            remote_hash = sha256_text(owned[0].id)
            try:
                assert_remote_matches(owned[0], item.payload)
            except ValueError:
                action = BackfillDecisionAction.QUARANTINE
                reason = "owned_payload_conflict"
            else:
                action = BackfillDecisionAction.ADOPT_OWNED
        elif visible_conflicts:
            action = BackfillDecisionAction.QUARANTINE
            reason = "visible_unowned_composite_match"
        elif len(local_hidden) == 1:
            candidates = canonical_by_hidden[local_hidden[0].id]
            if (
                len(candidates) == 1
                and candidates[0].local_activity_id == activity.local_activity_id
            ):
                action = BackfillDecisionAction.EXCLUDE_HIDDEN
                reason = "one_to_one_hidden_wall_time_match"
                remote_hash = sha256_text(local_hidden[0].id)
            else:
                action = BackfillDecisionAction.QUARANTINE
                reason = "hidden_timestamp_ambiguity"
        elif len(local_hidden) > 1:
            action = BackfillDecisionAction.QUARANTINE
            reason = "multiple_hidden_timestamp_matches"

        decisions.append(
            BackfillDecision(
                local_activity_id=activity.local_activity_id,
                action=action,
                time_mode=item.time_mode,
                local_date=activity.date,
                source_fingerprint_sha256=item.source_fingerprint_sha256,
                payload_fingerprint_sha256=item.payload_fingerprint_sha256,
                remote_activity_id_sha256=remote_hash,
                reason=reason,
            )
        )

    hidden_excluded = sum(
        item.action == BackfillDecisionAction.EXCLUDE_HIDDEN
        for item in decisions
    )
    conflicts = sum(
        item.action == BackfillDecisionAction.QUARANTINE for item in decisions
    )
    publishable = sum(
        item.action
        in {BackfillDecisionAction.PUBLISH, BackfillDecisionAction.ADOPT_OWNED}
        for item in decisions
    )
    exact = sum(
        item.time_mode == HistoricalTimeMode.EXACT_WALL_TIME for item in decisions
    )
    noon = len(decisions) - exact
    coverage = BackfillCoverage(
        archive_activity_count=len(all_records),
        initial_external_links=sum(
            bool(activity.origin.intervals_icu_activity_id)
            for activity in all_records
        ),
        selected=len(selected),
        hidden_excluded=hidden_excluded,
        publishable=publishable,
        exact_time=exact,
        noon_adjusted=noon,
        athlete_rpe=sum(
            activity.perceived_effort is not None
            and activity.perceived_effort.source == "athlete"
            for activity in selected
        ),
        public_descriptions=sum(bool(activity.notes.description) for activity in selected),
        positive_distance=sum(
            bool(activity.distance_meters and activity.distance_meters > 0)
            for activity in selected
        ),
        positive_elevation=sum(
            bool(
                activity.elevation_gain_meters
                and activity.elevation_gain_meters > 0
            )
            for activity in selected
        ),
        owned_recoveries=sum(
            item.action == BackfillDecisionAction.ADOPT_OWNED for item in decisions
        ),
        conflicts=conflicts,
    )
    expected = {
        "hidden_excluded": baseline.hidden_excluded,
        "publishable": baseline.publishable,
        "exact_time": baseline.exact_time,
        "noon_adjusted": baseline.noon_adjusted,
    }
    actual = {key: getattr(coverage, key) for key in expected}
    if actual != expected or conflicts:
        raise HistoricalInventoryError(
            "Frozen reconciliation drifted or contains unresolved conflicts: "
            f"expected={expected}, actual={actual}, conflicts={conflicts}"
        )

    candidates = [
        activity
        for activity in selected
        if (
            next(
                decision
                for decision in decisions
                if decision.local_activity_id == activity.local_activity_id
            ).action
            in {BackfillDecisionAction.PUBLISH, BackfillDecisionAction.ADOPT_OWNED}
            and rendered[activity.local_activity_id].time_mode
            == HistoricalTimeMode.EXACT_WALL_TIME
            and bool(activity.notes.description)
            and activity.perceived_effort is not None
            and activity.perceived_effort.source == "athlete"
        )
    ]
    canary = max(
        candidates,
        key=lambda item: (
            rendered[item.local_activity_id].payload.start_date,
            item.local_activity_id,
        ),
        default=None,
    )
    report_payload = {
        "schema_version": 1,
        "coverage": coverage.model_dump(mode="json"),
        "canary_local_activity_id": (
            canary.local_activity_id if canary is not None else None
        ),
        "synthetic_time_local_activity_ids": [
            item.local_activity_id
            for item in decisions
            if item.time_mode == HistoricalTimeMode.LOCAL_NOON
        ],
        "conflict_local_activity_ids": [
            item.local_activity_id
            for item in decisions
            if item.action == BackfillDecisionAction.QUARANTINE
        ],
        "decisions": [
            item.model_dump(mode="json")
            for item in sorted(decisions, key=lambda decision: decision.local_activity_id)
        ],
    }
    return BackfillAnalysis(
        coverage=coverage,
        decisions=decisions,
        canary_local_activity_id=(
            canary.local_activity_id if canary is not None else None
        ),
        report_payload=report_payload,
    )
