"""Pure transformations for the evidence-v5 coordinated cutover."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from resilio.schemas.activity import (
    ACTIVITY_CANONICAL_MAPPING_VERSION,
    CanonicalActivity,
)
from resilio.schemas.training_state import WellnessDay


def _migrated_local_private_note(
    description: str | None,
    private_note: str | None,
) -> str | None:
    values = [value for value in (description, private_note) if value]
    return "\n\n".join(values) if values else None


def _transform_measurements(container: dict[str, Any]) -> None:
    heart_rate = container.get("heart_rate")
    if isinstance(heart_rate, dict):
        heart_rate.setdefault("minimum_beats_per_minute", None)
    cadence = container.get("cadence")
    if isinstance(cadence, dict):
        cadence["minimum_cadence_per_minute"] = cadence.pop(
            "minimum_revolutions_per_minute",
            None,
        )
        cadence["average_cadence_per_minute"] = cadence.pop(
            "average_revolutions_per_minute",
            None,
        )
        cadence["maximum_cadence_per_minute"] = cadence.pop(
            "maximum_revolutions_per_minute",
            None,
        )
        cadence["source_basis"] = "provider_unspecified"


def transform_activity_v4(raw: dict[str, Any]) -> CanonicalActivity:
    """Transform one exact v4 payload without inventing provider ownership."""
    source = deepcopy(raw)
    schema = source.get("_schema")
    if not isinstance(schema, dict) or schema.get("version") != 4:
        raise ValueError("activity migration requires one resilio.activity v4 payload")
    if schema.get("name") != "resilio.activity":
        raise ValueError("activity migration source has an invalid schema name")
    notes = source.pop("notes", {}) or {}
    description = notes.get("description")
    private_note = notes.get("private_note")
    subjective_effort = source.pop("subjective_effort", None)
    origin = source.get("origin", {})
    is_provider_origin = origin.get("kind") == "intervals_icu"
    source["feedback"] = {
        "provider_description": description if is_provider_origin else None,
        "local_private_note": (
            private_note
            if is_provider_origin
            else _migrated_local_private_note(description, private_note)
        ),
        "subjective_effort": subjective_effort,
        "feel": None,
    }
    source["execution_summary"] = {}
    _transform_measurements(source)
    for segment in source.get("segments", []):
        _transform_measurements(segment)
    audit = source.get("audit")
    if not isinstance(audit, dict):
        raise ValueError("activity migration source is missing its audit record")
    audit.pop("external_fingerprint_sha256", None)
    audit["provider_snapshot_sha256"] = None
    audit["performance_evidence_sha256"] = None
    audit["canonical_mapping_version"] = None
    schema["version"] = 5
    return CanonicalActivity.model_validate(source)


def invalidate_stale_activity_mapping(raw: dict[str, Any]) -> CanonicalActivity:
    """Clear prior mapper hashes so the provider must be mapped with current logic."""
    source = deepcopy(raw)
    schema = source.get("_schema")
    if not isinstance(schema, dict) or schema.get("version") != 5:
        raise ValueError("mapping invalidation requires one resilio.activity v5 payload")
    if schema.get("name") != "resilio.activity":
        raise ValueError("activity mapping invalidation source has an invalid schema name")
    audit = source.get("audit")
    if not isinstance(audit, dict):
        raise ValueError("activity mapping invalidation source is missing its audit record")
    if audit.get("canonical_mapping_version") != ACTIVITY_CANONICAL_MAPPING_VERSION:
        audit["provider_snapshot_sha256"] = None
        audit["performance_evidence_sha256"] = None
        audit["canonical_mapping_version"] = None
    return CanonicalActivity.model_validate(source)


def transform_wellness_v1(raw: dict[str, Any]) -> WellnessDay:
    """Add explicit v2 semantics to one provider-neutral legacy wellness day."""
    source = deepcopy(raw)
    source["schema_version"] = 2
    source["mapping_version"] = 2
    source.setdefault("provider_updated_at_utc", None)
    source.setdefault("provider_snapshot_sha256", None)
    if "provider_hydration_volume_value" in source:
        source["hydration_volume_liters"] = source.pop("provider_hydration_volume_value")
    return WellnessDay.model_validate(source)
