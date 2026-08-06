"""Field-level merge policy for reconciled canonical activities."""

from __future__ import annotations

from resilio.schemas.activity import (
    ActivityAudit,
    ActivityDevice,
    ActivityFeedback,
    ActivityOrigin,
    ActivitySegment,
    CanonicalActivity,
    DataCompleteness,
    RecordingProvider,
    SubjectiveSessionEffort,
)

HISTORICAL_BACKFILL_PREFIX = "resilio:v1:historical-activity:"


def merge_external_activity(
    existing: CanonicalActivity,
    external: CanonicalActivity,
) -> CanonicalActivity:
    """Merge validated external facts without overwriting authored facts."""
    origin = _merged_origin(existing, external)
    audit = _merged_audit(existing, external)
    if existing.origin.kind == "historical_import":
        return _merged_historical(existing, external, origin=origin, audit=audit)
    return _merged_provider_activity(existing, external, origin=origin, audit=audit)


def merge_reviewed_activity(
    existing: CanonicalActivity,
    external: CanonicalActivity,
) -> CanonicalActivity:
    """Apply a current explicit approval without weakening automatic rules."""
    if (
        existing.sport != external.sport
        or existing.occurrence.local_date != external.occurrence.local_date
    ):
        raise ValueError("reviewed activity must retain the current sport/date candidate block")
    existing_external_id = existing.origin.intervals_icu_activity_id
    incoming_external_id = external.origin.intervals_icu_activity_id
    if existing_external_id and existing_external_id != incoming_external_id:
        raise ValueError("reviewed activity is already linked to a different external ID")
    return merge_external_activity(existing, external)


def _merged_origin(
    existing: CanonicalActivity,
    external: CanonicalActivity,
) -> ActivityOrigin:
    historical = existing.origin.kind == "historical_import"
    return ActivityOrigin(
        kind=existing.origin.kind,
        recording_provider=(
            RecordingProvider(existing.origin.recording_provider)
            if historical and existing.origin.recording_provider == "manual"
            else RecordingProvider(external.origin.recording_provider)
        ),
        source_recording_provider=(
            external.origin.source_recording_provider or existing.origin.source_recording_provider
        ),
        intervals_icu_activity_id=external.origin.intervals_icu_activity_id,
        upstream_external_id=(
            existing.origin.upstream_external_id or external.origin.upstream_external_id
        ),
        original_file_sha256=(
            existing.origin.original_file_sha256 or external.origin.original_file_sha256
        ),
    )


def _merged_audit(
    existing: CanonicalActivity,
    external: CanonicalActivity,
) -> ActivityAudit:
    return ActivityAudit(
        imported_at_utc=existing.audit.imported_at_utc,
        external_created_at_utc=external.audit.external_created_at_utc,
        external_sync_at_utc=external.audit.external_sync_at_utc,
        provider_snapshot_sha256=external.audit.provider_snapshot_sha256,
        performance_evidence_sha256=external.audit.performance_evidence_sha256,
        canonical_mapping_version=external.audit.canonical_mapping_version,
    )


def _merged_historical(
    existing: CanonicalActivity,
    external: CanonicalActivity,
    *,
    origin: ActivityOrigin,
    audit: ActivityAudit,
) -> CanonicalActivity:
    if existing.origin.upstream_external_id and existing.origin.upstream_external_id.startswith(
        HISTORICAL_BACKFILL_PREFIX
    ):
        return _merged_historical_backfill(existing, external, audit=audit)
    device = ActivityDevice(
        name=existing.device.name or external.device.name,
        gear_external_id=(existing.device.gear_external_id or external.device.gear_external_id),
    )
    classification = existing.classification.model_copy(
        update={
            "has_gps_data": (
                existing.classification.has_gps_data or external.classification.has_gps_data
            )
        }
    )
    merged = existing.model_copy(
        update={
            "status": external.status,
            "source_sport_type": external.source_sport_type,
            "source_sport_subtype": (
                existing.source_sport_subtype or external.source_sport_subtype
            ),
            "distance_meters": (
                existing.distance_meters
                if existing.distance_meters is not None
                else external.distance_meters
            ),
            "elevation_gain_meters": (
                existing.elevation_gain_meters
                if existing.elevation_gain_meters is not None
                else external.elevation_gain_meters
            ),
            "heart_rate": existing.heart_rate or external.heart_rate,
            "power": existing.power or external.power,
            "cadence": existing.cadence or external.cadence,
            "execution_summary": external.execution_summary,
            "feedback": _merged_feedback(
                existing,
                external,
                preserve_existing_when_provider_missing=True,
            ),
            "aerobic_load": external.aerobic_load,
            "native_analysis": external.native_analysis,
            "native_analysis_applicability": (external.native_analysis_applicability),
            "analysis_thresholds": external.analysis_thresholds,
            "zone_time_distributions": external.zone_time_distributions,
            "data_completeness": external.data_completeness,
            "device": device,
            "classification": classification,
            "segments": _merged_historical_segments(existing, external),
            "origin": origin,
            "audit": audit,
        }
    )
    return _with_canonical_completeness(merged)


def _merged_historical_backfill(
    existing: CanonicalActivity,
    external: CanonicalActivity,
    *,
    audit: ActivityAudit,
) -> CanonicalActivity:
    """Refresh provider evidence while preserving authored historical facts."""
    classification = existing.classification.model_copy(
        update={
            "has_gps_data": (
                existing.classification.has_gps_data or external.classification.has_gps_data
            )
        }
    )
    merged = existing.model_copy(
        update={
            "status": external.status,
            "origin": ActivityOrigin(
                kind=existing.origin.kind,
                recording_provider=existing.origin.recording_provider,
                source_recording_provider=(
                    external.origin.source_recording_provider
                    or existing.origin.source_recording_provider
                ),
                intervals_icu_activity_id=(external.origin.intervals_icu_activity_id),
                upstream_external_id=existing.origin.upstream_external_id,
                original_file_sha256=existing.origin.original_file_sha256,
            ),
            "audit": audit,
            "aerobic_load": external.aerobic_load,
            "native_analysis": external.native_analysis,
            "native_analysis_applicability": (external.native_analysis_applicability),
            "analysis_thresholds": external.analysis_thresholds,
            "zone_time_distributions": external.zone_time_distributions,
            "execution_summary": external.execution_summary,
            "feedback": _merged_feedback(
                existing,
                external,
                preserve_existing_when_provider_missing=True,
            ),
            "segments": _merged_historical_segments(existing, external),
            "data_completeness": external.data_completeness,
            "classification": classification,
        }
    )
    return _with_canonical_completeness(merged)


def _merged_historical_segments(
    existing: CanonicalActivity,
    external: CanonicalActivity,
) -> list[ActivitySegment]:
    """Retain authored laps and refresh the provider-owned interval partition."""
    if not external.segments:
        return existing.segments
    historical_segments = [
        segment for segment in existing.segments if segment.origin_kind == "historical_segment"
    ]
    combined = [*historical_segments, *external.segments]
    return [
        segment.model_copy(update={"index": index})
        for index, segment in enumerate(combined, start=1)
    ]


def _merged_provider_activity(
    existing: CanonicalActivity,
    external: CanonicalActivity,
    *,
    origin: ActivityOrigin,
    audit: ActivityAudit,
) -> CanonicalActivity:
    merged = existing.model_copy(
        update={
            "status": external.status,
            "source_sport_type": external.source_sport_type,
            "source_sport_subtype": external.source_sport_subtype,
            "name": external.name,
            "occurrence": external.occurrence,
            "duration": external.duration,
            "distance_meters": external.distance_meters,
            "elevation_gain_meters": external.elevation_gain_meters,
            "heart_rate": external.heart_rate or existing.heart_rate,
            "power": external.power or existing.power,
            "cadence": external.cadence or existing.cadence,
            "execution_summary": external.execution_summary,
            "feedback": _merged_feedback(
                existing,
                external,
                preserve_existing_when_provider_missing=False,
            ),
            "aerobic_load": external.aerobic_load,
            "native_analysis": external.native_analysis,
            "native_analysis_applicability": (external.native_analysis_applicability),
            "analysis_thresholds": external.analysis_thresholds,
            "zone_time_distributions": external.zone_time_distributions,
            "data_completeness": external.data_completeness,
            "device": external.device,
            "classification": external.classification,
            "segments": external.segments or existing.segments,
            "origin": origin,
            "audit": audit,
        }
    )
    return _with_canonical_completeness(merged)


def _with_canonical_completeness(
    activity: CanonicalActivity,
) -> CanonicalActivity:
    """Derive completeness flags from the final merged canonical facts."""
    return activity.model_copy(
        update={
            "data_completeness": DataCompleteness(
                has_location_stream=activity.classification.has_gps_data,
                has_heart_rate_data=activity.heart_rate is not None,
                has_power_data=activity.power is not None,
                has_cadence_data=activity.cadence is not None,
                has_interval_data=bool(activity.segments),
                has_native_aerobic_load=activity.aerobic_load is not None,
                has_zone_time_data=bool(activity.zone_time_distributions),
                has_native_activity_analysis=activity.native_analysis is not None,
            )
        }
    )


def _merged_feedback(
    existing: CanonicalActivity,
    external: CanonicalActivity,
    *,
    preserve_existing_when_provider_missing: bool,
) -> ActivityFeedback:
    existing_effort = existing.feedback.subjective_effort
    external_effort = external.feedback.subjective_effort
    if existing_effort is not None and existing_effort.is_athlete_confirmed:
        subjective_effort: SubjectiveSessionEffort | None = existing_effort
    elif preserve_existing_when_provider_missing:
        subjective_effort = external_effort or existing_effort
    else:
        subjective_effort = external_effort
    return ActivityFeedback(
        provider_description=(
            external.feedback.provider_description
            if not preserve_existing_when_provider_missing
            else (external.feedback.provider_description or existing.feedback.provider_description)
        ),
        local_private_note=existing.feedback.local_private_note,
        subjective_effort=subjective_effort,
        feel=(
            external.feedback.feel
            if not preserve_existing_when_provider_missing
            else external.feedback.feel or existing.feedback.feel
        ),
    )
