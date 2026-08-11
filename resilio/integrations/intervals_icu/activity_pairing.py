"""Exact fingerprints and mutability policy for native activity pairing."""

import hashlib
import json

from resilio.integrations.intervals_icu.dto import ActivityDTO


def activity_pairing_guard_sha256(activity: ActivityDTO) -> str:
    """Fingerprint every returned activity field except the pairing pointer."""
    payload = activity.model_dump(mode="json", exclude={"paired_event_id"})
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def activity_source_supports_pairing(activity: ActivityDTO) -> bool:
    """Apply the provider's documented prohibition on Strava activity updates."""
    return recording_source_supports_pairing(activity.source)


def recording_source_supports_pairing(source_recording_provider: str | None) -> bool:
    """Return whether Intervals permits updates for a recording source."""
    return (source_recording_provider or "").strip().upper() != "STRAVA"
