"""Deterministic historical wall-time correction and manual payload rendering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from resilio.integrations.intervals_icu.dto import (
    ActivityDTO,
    ManualActivityWriteDTO,
)
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.historical_backfill import HistoricalTimeMode

TIMEZONE_NAME = "Europe/Paris"
OWNERSHIP_PREFIX = "resilio:v1:historical-activity:"
NOON_DISCLOSURE = (
    "Exact historical start time unavailable; displayed at local noon."
)


class HistoricalActivityRenderingError(ValueError):
    pass


@dataclass(frozen=True)
class RenderedHistoricalActivity:
    payload: ManualActivityWriteDTO
    time_mode: HistoricalTimeMode
    source_fingerprint_sha256: str
    payload_fingerprint_sha256: str


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(payload: object) -> str:
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def external_id_for(local_activity_id: str) -> str:
    return f"{OWNERSHIP_PREFIX}{local_activity_id}"


def _valid_local_datetime(naive: datetime, timezone_name: str) -> datetime:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HistoricalActivityRenderingError(
            f"Historical timezone is not recognized: {timezone_name}"
        ) from exc

    candidates: dict[object, datetime] = {}
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        round_trip = (
            aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        )
        if round_trip == naive:
            candidates[aware.utcoffset()] = aware
    if not candidates:
        raise HistoricalActivityRenderingError(
            "Historical local time does not exist because of a daylight-saving transition"
        )
    if len(candidates) > 1:
        raise HistoricalActivityRenderingError(
            "Historical local time is ambiguous because of a daylight-saving transition"
        )
    return next(iter(candidates.values()))


def corrected_local_start(
    activity: CanonicalActivity,
) -> tuple[datetime, HistoricalTimeMode]:
    """Interpret preserved clock components in Paris; synthesize date-only noon."""
    stored = activity.occurrence.start_time_local
    if stored is None:
        naive = datetime.combine(activity.date, time(hour=12))
        return (
            _valid_local_datetime(naive, TIMEZONE_NAME),
            HistoricalTimeMode.LOCAL_NOON,
        )
    if stored.date() != activity.date:
        raise HistoricalActivityRenderingError(
            "Historical start clock does not match the canonical local date"
        )
    return (
        _valid_local_datetime(stored.replace(tzinfo=None), TIMEZONE_NAME),
        HistoricalTimeMode.EXACT_WALL_TIME,
    )


def source_projection(activity: CanonicalActivity) -> dict:
    """Remove only fields owned by this outbound migration from source hashing."""
    payload = activity.model_dump(mode="json", by_alias=True)
    origin = dict(payload["origin"])
    origin["intervals_icu_activity_id"] = None
    owned_external_id = origin.get("upstream_external_id")
    if isinstance(owned_external_id, str) and owned_external_id.startswith(
        OWNERSHIP_PREFIX
    ):
        origin["upstream_external_id"] = None
    payload["origin"] = origin
    audit = dict(payload["audit"])
    audit["external_created_at_utc"] = None
    audit["external_sync_at_utc"] = None
    audit["external_fingerprint_sha256"] = None
    payload["audit"] = audit
    return payload


def source_fingerprint(activity: CanonicalActivity) -> str:
    return sha256_json(source_projection(activity))


def _public_description(activity: CanonicalActivity, *, synthetic_noon: bool) -> str | None:
    description = activity.notes.description
    if not synthetic_noon:
        return description
    if description:
        return f"{description.rstrip()}\n\n{NOON_DISCLOSURE}"
    return NOON_DISCLOSURE


def render_manual_activity(activity: CanonicalActivity) -> RenderedHistoricalActivity:
    if activity.status != "active":
        raise HistoricalActivityRenderingError("Only active history can be published")
    if activity.origin.kind != "historical_import" or activity.sport != "climb":
        raise HistoricalActivityRenderingError(
            "Only historical climb records can be rendered by this backfill"
        )
    if (
        activity.origin.intervals_icu_activity_id
        and activity.origin.upstream_external_id
        != external_id_for(activity.local_activity_id)
    ):
        raise HistoricalActivityRenderingError(
            "Historical activity has a non-backfill external activity link"
        )

    local_start, time_mode = corrected_local_start(activity)
    athlete_rpe = (
        activity.perceived_effort.value
        if activity.perceived_effort is not None
        and activity.perceived_effort.source == "athlete"
        else None
    )
    payload = ManualActivityWriteDTO(
        external_id=external_id_for(activity.local_activity_id),
        type="RockClimbing",
        name=activity.name,
        start_date=local_start.astimezone(timezone.utc),
        start_date_local=local_start,
        timezone=TIMEZONE_NAME,
        elapsed_time=activity.duration.elapsed_seconds,
        moving_time=activity.duration.moving_seconds,
        description=_public_description(
            activity,
            synthetic_noon=time_mode == HistoricalTimeMode.LOCAL_NOON,
        ),
        icu_rpe=athlete_rpe,
        distance=(
            activity.distance_meters
            if activity.distance_meters is not None
            and activity.distance_meters > 0
            else None
        ),
        total_elevation_gain=(
            activity.elevation_gain_meters
            if activity.elevation_gain_meters is not None
            and activity.elevation_gain_meters > 0
            else None
        ),
    )
    rendered = payload.model_dump(mode="json", exclude_none=True)
    return RenderedHistoricalActivity(
        payload=payload,
        time_mode=time_mode,
        source_fingerprint_sha256=source_fingerprint(activity),
        payload_fingerprint_sha256=sha256_json(rendered),
    )


def with_remote_athlete_rpe(
    rendered: RenderedHistoricalActivity,
    value: int,
) -> RenderedHistoricalActivity:
    """Override only remote athlete RPE while retaining immutable local facts."""
    if not 1 <= value <= 10:
        raise HistoricalActivityRenderingError("Athlete RPE must be between 1 and 10")
    payload = rendered.payload.model_copy(update={"icu_rpe": value})
    return RenderedHistoricalActivity(
        payload=payload,
        time_mode=rendered.time_mode,
        source_fingerprint_sha256=rendered.source_fingerprint_sha256,
        payload_fingerprint_sha256=sha256_json(
            payload.model_dump(mode="json", exclude_none=True)
        ),
    )


def _remote_local_start(remote: ActivityDTO, timezone_name: str) -> datetime:
    zone = ZoneInfo(timezone_name)
    utc_start = remote.start_date.astimezone(timezone.utc)
    expected = utc_start.astimezone(zone)
    supplied = remote.start_date_local
    if supplied.replace(tzinfo=None) != expected.replace(tzinfo=None):
        raise HistoricalActivityRenderingError(
            "Remote local occurrence is inconsistent with its UTC occurrence"
        )
    if supplied.tzinfo is not None and supplied.utcoffset() is not None:
        if supplied.utcoffset() != expected.utcoffset():
            raise HistoricalActivityRenderingError(
                "Remote local occurrence offset is inconsistent with the timezone"
            )
    return expected


def assert_remote_matches(
    remote: ActivityDTO,
    expected: ManualActivityWriteDTO,
) -> None:
    """Verify exact ownership and every athlete-authored factual field."""
    local_start = _remote_local_start(remote, expected.timezone)
    expected_local = expected.start_date_local
    mismatches: list[str] = []
    comparisons = (
        ("external_id", remote.external_id, expected.external_id),
        ("type", remote.type, expected.type),
        ("name", remote.name, expected.name),
        (
            "start_date",
            remote.start_date.astimezone(timezone.utc),
            expected.start_date,
        ),
        ("start_date_local", local_start, expected_local),
        (
            "timezone",
            remote.timezone if remote.timezone is not None else expected.timezone,
            expected.timezone,
        ),
        ("elapsed_time", remote.elapsed_time, expected.elapsed_time),
        ("moving_time", remote.moving_time, expected.moving_time),
        ("description", remote.description, expected.description),
        (
            "icu_rpe",
            remote.icu_rpe,
            expected.icu_rpe,
        ),
    )
    mismatches.extend(
        field_name
        for field_name, actual, approved in comparisons
        if actual != approved
    )
    if (
        remote.distance != expected.distance
        and not (expected.distance is None and remote.distance == 0)
    ):
        mismatches.append("distance")
    if (
        remote.total_elevation_gain != expected.total_elevation_gain
        and not (
            expected.total_elevation_gain is None
            and remote.total_elevation_gain == 0
        )
    ):
        mismatches.append("total_elevation_gain")
    if mismatches:
        raise HistoricalActivityRenderingError(
            "Remote manual activity does not match approved fields: "
            + ", ".join(sorted(mismatches))
        )


def readback_fingerprint(remote: ActivityDTO) -> str:
    """Hash factual read-back plus ownership, excluding server-calculated load."""
    payload = {
        "id": remote.id,
        "external_id": remote.external_id,
        "type": remote.type,
        "name": remote.name,
        "start_date": remote.start_date.astimezone(timezone.utc).isoformat(),
        "start_date_local": remote.start_date_local.isoformat(),
        "timezone": remote.timezone,
        "elapsed_time": remote.elapsed_time,
        "moving_time": remote.moving_time,
        "description": remote.description,
        "icu_rpe": remote.icu_rpe,
        "distance": remote.distance,
        "total_elevation_gain": remote.total_elevation_gain,
    }
    return sha256_json(payload)
