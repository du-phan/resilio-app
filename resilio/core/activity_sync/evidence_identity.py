"""Stable activity identities for evidence that must survive feedback edits."""

from __future__ import annotations

import hashlib
import json

from resilio.schemas.activity import ActivitySegment, CanonicalActivity


def _performance_segment_payload(segment: ActivitySegment) -> dict[str, object]:
    return {
        "index": segment.index,
        "origin_kind": segment.origin_kind,
        "elapsed_seconds": segment.elapsed_seconds,
        "moving_seconds": segment.moving_seconds,
        "distance_meters": segment.distance_meters,
        "start_time_utc": segment.start_time_utc,
        "start_time_local": segment.start_time_local,
        "source_start_index": segment.source_start_index,
        "source_end_index_exclusive": segment.source_end_index_exclusive,
        "end_offset_seconds": segment.end_offset_seconds,
        "minimum_speed_meters_per_second": segment.minimum_speed_meters_per_second,
        "average_speed_meters_per_second": segment.average_speed_meters_per_second,
        "maximum_speed_meters_per_second": segment.maximum_speed_meters_per_second,
        "heart_rate": segment.heart_rate,
        "elevation_gain_meters": segment.elevation_gain_meters,
        "power": segment.power,
        "cadence": segment.cadence,
        "average_gradient_percent": segment.average_gradient_percent,
        "minimum_altitude_meters": segment.minimum_altitude_meters,
        "maximum_altitude_meters": segment.maximum_altitude_meters,
        "average_stride_meters": segment.average_stride_meters,
        "work_joules": segment.work_joules,
    }


def activity_performance_evidence_sha256(activity: CanonicalActivity) -> str:
    """Identify measured performance without mutable feedback or provider analysis."""
    provider_identity = activity.audit.performance_evidence_sha256
    if provider_identity is not None:
        return provider_identity
    payload = {
        "local_activity_id": activity.local_activity_id,
        "sport": activity.sport,
        "source_sport_type": activity.source_sport_type,
        "source_sport_subtype": activity.source_sport_subtype,
        "occurrence": activity.occurrence,
        "duration": activity.duration,
        "distance_meters": activity.distance_meters,
        "elevation_gain_meters": activity.elevation_gain_meters,
        "heart_rate": activity.heart_rate,
        "power": activity.power,
        "cadence": activity.cadence,
        "execution_summary": {
            "average_speed_meters_per_second": (
                activity.execution_summary.average_speed_meters_per_second
            ),
            "maximum_speed_meters_per_second": (
                activity.execution_summary.maximum_speed_meters_per_second
            ),
            "gradient_adjusted_speed_meters_per_second": (
                activity.execution_summary.gradient_adjusted_speed_meters_per_second
            ),
            "average_stride_meters": activity.execution_summary.average_stride_meters,
        },
        "device": activity.device,
        "segments": [
            _performance_segment_payload(segment) for segment in activity.segments
        ],
        "origin": activity.origin,
    }
    canonical = json.dumps(
        payload,
        default=lambda value: value.model_dump(mode="json")
        if hasattr(value, "model_dump")
        else str(value),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
