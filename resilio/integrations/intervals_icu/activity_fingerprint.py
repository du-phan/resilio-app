"""Deterministic fingerprinting of canonical Intervals.icu activity facts."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Optional

from resilio.integrations.intervals_icu.dto import ActivityDTO, IntervalDTO

CANONICAL_MAPPING_VERSION: Literal[7] = 7


def ordered_intervals(activity: ActivityDTO) -> list[IntervalDTO]:
    """Canonical provider interval order used by hashing and mapping."""
    return sorted(
        activity.icu_intervals,
        key=lambda item: (item.start_time, item.id),
    )


def external_fingerprint(
    activity: ActivityDTO,
    default_timezone: Optional[str] = None,
) -> str:
    """Hash only mapped external facts, independent of response ordering."""
    payload = {
        "id": activity.id,
        "type": activity.type,
        "sub_type": activity.sub_type,
        "name": activity.name,
        "description": activity.description,
        "start_date": activity.start_date.isoformat(),
        "start_date_local": activity.start_date_local.isoformat(),
        "timezone": activity.timezone,
        "default_timezone": default_timezone if not activity.timezone else None,
        "elapsed_time": activity.elapsed_time,
        "moving_time": activity.moving_time,
        "distance": activity.distance,
        "total_elevation_gain": activity.total_elevation_gain,
        "average_heartrate": activity.average_heartrate,
        "max_heartrate": activity.max_heartrate,
        "average_cadence": activity.average_cadence,
        "max_cadence": activity.max_cadence,
        "icu_average_watts": activity.icu_average_watts,
        "p_max": activity.p_max,
        "icu_weighted_avg_watts": activity.icu_weighted_avg_watts,
        "native_analysis": {
            "icu_training_load": activity.icu_training_load,
            "icu_training_load_edited": activity.icu_training_load_edited,
            "power_load": activity.power_load,
            "hr_load": activity.hr_load,
            "pace_load": activity.pace_load,
            "hr_load_type": activity.hr_load_type,
            "pace_load_type": activity.pace_load_type,
            "load_order": activity.load_order,
            "tiz_order": activity.tiz_order,
            "icu_intensity": activity.icu_intensity,
            "session_rpe": activity.session_rpe,
            "ftp": activity.ftp,
            "lthr": activity.lthr,
            "max_hr": activity.max_hr,
            "threshold_speed_meters_per_second": (activity.threshold_speed_meters_per_second),
            "pace_display_unit": activity.pace_display_unit,
            "icu_power_zones": activity.icu_power_zones,
            "power_zone_names": activity.power_zone_names,
            "hr_zones": activity.hr_zones,
            "hr_zone_names": activity.hr_zone_names,
            "pace_zones": activity.pace_zones,
            "pace_zone_names": activity.pace_zone_names,
            "icu_zone_times": [
                zone.model_dump(mode="json", exclude_none=False)
                for zone in sorted(
                    activity.icu_zone_times,
                    key=lambda item: item.id,
                )
            ],
            "icu_hr_zone_times": activity.icu_hr_zone_times,
            "pace_zone_times": activity.pace_zone_times,
            "gap_zone_times": activity.gap_zone_times,
            "use_gap_zone_times": activity.use_gap_zone_times,
            "stream_types": sorted(activity.stream_types),
            "decoupling": activity.decoupling,
            "icu_hrr": (
                activity.icu_hrr.model_dump(mode="json") if activity.icu_hrr is not None else None
            ),
            "icu_ignore_time": activity.icu_ignore_time,
            "icu_ignore_power": activity.icu_ignore_power,
            "icu_ignore_hr": activity.icu_ignore_hr,
            "ignore_velocity": activity.ignore_velocity,
            "ignore_pace": activity.ignore_pace,
            "polarization_index": activity.polarization_index,
            "trimp": activity.trimp,
        },
        "perceived_exertion": activity.perceived_exertion,
        "icu_rpe": activity.icu_rpe,
        "device_name": activity.device_name,
        "external_id": activity.external_id,
        "file_type": activity.file_type,
        "source": activity.source,
        "created": activity.created.isoformat() if activity.created else None,
        "icu_sync_date": (activity.icu_sync_date.isoformat() if activity.icu_sync_date else None),
        "intervals": [
            interval.model_dump(mode="json", exclude_none=False)
            for interval in ordered_intervals(activity)
        ],
    }
    if activity.paired_event_id is not None:
        payload["paired_event_id"] = activity.paired_event_id
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
