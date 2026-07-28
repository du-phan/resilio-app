"""Conservative deterministic overlap reconciliation."""

from __future__ import annotations

import re
from typing import Iterable, Optional

from resilio.schemas.activity import (
    ActivityAudit,
    ActivityDevice,
    ActivityOrigin,
    CanonicalActivity,
)
from resilio.schemas.reconciliation import (
    ReconciliationAction,
    ReconciliationDecision,
)

HISTORICAL_BACKFILL_PREFIX = "resilio:v1:historical-activity:"


def _delta(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None
    return abs(left - right)


def _normalized_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def _start_delta_seconds(
    left: CanonicalActivity,
    right: CanonicalActivity,
) -> Optional[float]:
    left_start = left.occurrence.start_time_utc
    right_start = right.occurrence.start_time_utc
    if left_start is None or right_start is None:
        return None
    return abs((left_start - right_start).total_seconds())


def _historical_wall_start_delta_seconds(
    external: CanonicalActivity,
    candidate: CanonicalActivity,
) -> Optional[float]:
    """Compare wall-clock starts for records migrated from the v1 archive.

    The retired importer persisted the upstream local timestamp in the sole
    ``start_time`` field. During v2 migration that value could not safely be
    reinterpreted as UTC because the original timezone was not retained.
    This alternate is therefore limited to historical records whose timezone
    is explicitly unknown.
    """
    if (
        candidate.origin.kind != "historical_import"
        or candidate.occurrence.timezone is not None
    ):
        return None
    external_start = external.occurrence.start_time_local
    historical_start = candidate.occurrence.start_time_local
    if external_start is None or historical_start is None:
        return None
    return abs(
        (
            external_start.replace(tzinfo=None)
            - historical_start.replace(tzinfo=None)
        ).total_seconds()
    )


def _effective_start_deltas(
    external: CanonicalActivity,
    candidate: CanonicalActivity,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    utc_delta = _start_delta_seconds(external, candidate)
    historical_wall_delta = _historical_wall_start_delta_seconds(
        external,
        candidate,
    )
    comparable = [
        value for value in (utc_delta, historical_wall_delta) if value is not None
    ]
    effective = min(comparable) if comparable else None
    return effective, utc_delta, historical_wall_delta


def _within(value: Optional[float], tolerance: float) -> bool:
    return value is None or value <= tolerance


def _duration_tolerance(seconds: int, minimum: int, percentage: float) -> float:
    return max(float(minimum), seconds * percentage)


def _distance_tolerance(meters: Optional[float], minimum: int, percentage: float) -> float:
    return max(float(minimum), (meters or 0.0) * percentage)


def _compatible_source(
    left: CanonicalActivity,
    right: CanonicalActivity,
) -> bool:
    left_provider = left.origin.recording_provider
    right_provider = right.origin.recording_provider
    if left_provider in {"unknown", "other"} or right_provider in {"unknown", "other"}:
        return True
    return left_provider == right_provider


def _strong_recorded(
    external: CanonicalActivity,
    candidate: CanonicalActivity,
) -> tuple[bool, dict[str, Optional[float]]]:
    start_delta, utc_start_delta, historical_wall_start_delta = (
        _effective_start_deltas(external, candidate)
    )
    elapsed_delta = _delta(
        external.duration.elapsed_seconds,
        candidate.duration.elapsed_seconds,
    )
    moving_delta = _delta(
        external.duration.moving_seconds,
        candidate.duration.moving_seconds,
    )
    historical_duration_delta = None
    if candidate.origin.kind == "historical_import":
        historical_duration_delta = min(
            value
            for value in (
                _delta(
                    external.duration.elapsed_seconds,
                    candidate.duration.elapsed_seconds,
                ),
                _delta(
                    external.duration.moving_seconds,
                    candidate.duration.elapsed_seconds,
                ),
            )
            if value is not None
        )
    distance_delta = _delta(external.distance_meters, candidate.distance_meters)
    evidence = {
        "start_delta_seconds": start_delta,
        "utc_start_delta_seconds": utc_start_delta,
        "historical_wall_start_delta_seconds": historical_wall_start_delta,
        "elapsed_delta_seconds": elapsed_delta,
        "moving_delta_seconds": moving_delta,
        "historical_duration_delta_seconds": historical_duration_delta,
        "distance_delta_meters": distance_delta,
    }
    if candidate.origin.kind == "historical_import":
        duration_matches = _within(
            historical_duration_delta,
            _duration_tolerance(
                candidate.duration.elapsed_seconds,
                60,
                0.02,
            ),
        )
    else:
        duration_matches = _within(
            elapsed_delta,
            _duration_tolerance(external.duration.elapsed_seconds, 60, 0.02),
        ) and _within(
            moving_delta,
            _duration_tolerance(external.duration.moving_seconds, 60, 0.02),
        )
    valid = (
        start_delta is not None
        and start_delta <= 120
        and duration_matches
        and _within(
            distance_delta,
            _distance_tolerance(external.distance_meters, 100, 0.01),
        )
        and _compatible_source(external, candidate)
    )
    return valid, evidence


def _strong_manual(external: CanonicalActivity, candidate: CanonicalActivity) -> bool:
    return (
        candidate.origin.recording_provider == "manual"
        and external.distance_meters in (None, 0)
        and candidate.distance_meters in (None, 0)
        and round(external.duration.elapsed_seconds / 60)
        == round(candidate.duration.elapsed_seconds / 60)
        and _normalized_title(external.name) == _normalized_title(candidate.name)
    )


def _review_candidate(
    external: CanonicalActivity,
    candidate: CanonicalActivity,
) -> tuple[bool, dict[str, Optional[float]]]:
    start_delta, utc_start_delta, historical_wall_start_delta = (
        _effective_start_deltas(external, candidate)
    )
    elapsed_delta = _delta(
        external.duration.elapsed_seconds,
        candidate.duration.elapsed_seconds,
    )
    moving_delta = _delta(
        external.duration.moving_seconds,
        candidate.duration.moving_seconds,
    )
    historical_duration_delta = None
    if candidate.origin.kind == "historical_import":
        historical_duration_delta = min(
            value
            for value in (
                elapsed_delta,
                _delta(
                    external.duration.moving_seconds,
                    candidate.duration.elapsed_seconds,
                ),
            )
            if value is not None
        )
    distance_delta = _delta(external.distance_meters, candidate.distance_meters)
    evidence = {
        "start_delta_seconds": start_delta,
        "utc_start_delta_seconds": utc_start_delta,
        "historical_wall_start_delta_seconds": historical_wall_start_delta,
        "historical_start_unavailable": float(
            candidate.origin.kind == "historical_import"
            and candidate.occurrence.start_time_utc is None
            and candidate.occurrence.start_time_local is None
        ),
        "elapsed_delta_seconds": elapsed_delta,
        "moving_delta_seconds": moving_delta,
        "historical_duration_delta_seconds": historical_duration_delta,
        "distance_delta_meters": distance_delta,
    }
    duration_delta = (
        historical_duration_delta
        if candidate.origin.kind == "historical_import"
        else elapsed_delta
    )
    duration_base = (
        candidate.duration.elapsed_seconds
        if candidate.origin.kind == "historical_import"
        else external.duration.elapsed_seconds
    )
    has_reviewable_start = start_delta is not None and start_delta <= 1800
    historical_start_unavailable = (
        candidate.origin.kind == "historical_import"
        and candidate.occurrence.start_time_utc is None
        and candidate.occurrence.start_time_local is None
    )
    valid = (
        (has_reviewable_start or historical_start_unavailable)
        and _within(
            duration_delta,
            _duration_tolerance(duration_base, 300, 0.05),
        )
        and _within(
            distance_delta,
            _distance_tolerance(external.distance_meters, 250, 0.02),
        )
    )
    return valid, evidence


def _merged(
    existing: CanonicalActivity,
    external: CanonicalActivity,
) -> CanonicalActivity:
    """Merge validated external facts without overwriting authored facts."""
    historical = existing.origin.kind == "historical_import"
    origin = ActivityOrigin(
        kind=existing.origin.kind,
        recording_provider=(
            existing.origin.recording_provider
            if historical and existing.origin.recording_provider == "manual"
            else external.origin.recording_provider
        ),
        intervals_icu_activity_id=external.origin.intervals_icu_activity_id,
        upstream_external_id=(
            existing.origin.upstream_external_id
            or external.origin.upstream_external_id
        ),
        original_file_sha256=(
            existing.origin.original_file_sha256
            or external.origin.original_file_sha256
        ),
    )
    audit = ActivityAudit(
        imported_at_utc=existing.audit.imported_at_utc,
        external_created_at_utc=external.audit.external_created_at_utc,
        external_sync_at_utc=external.audit.external_sync_at_utc,
        external_fingerprint_sha256=external.audit.external_fingerprint_sha256,
    )
    if historical:
        if (
            existing.origin.upstream_external_id
            and existing.origin.upstream_external_id.startswith(
                HISTORICAL_BACKFILL_PREFIX
            )
        ):
            # Outbound historical publications are identity/status refreshes
            # only. Their local facts and preserved provenance remain the
            # authority and may not be replaced by the feedback sync.
            return existing.model_copy(
                update={
                    "status": external.status,
                    "origin": ActivityOrigin(
                        kind=existing.origin.kind,
                        recording_provider=existing.origin.recording_provider,
                        intervals_icu_activity_id=(
                            external.origin.intervals_icu_activity_id
                        ),
                        upstream_external_id=existing.origin.upstream_external_id,
                        original_file_sha256=existing.origin.original_file_sha256,
                    ),
                    "audit": audit,
                    "calculated_load": existing.calculated_load,
                }
            )
        device = ActivityDevice(
            name=existing.device.name or external.device.name,
            gear_external_id=(
                existing.device.gear_external_id
                or external.device.gear_external_id
            ),
        )
        return existing.model_copy(
            update={
                "status": external.status,
                "source_sport_type": external.source_sport_type,
                "source_sport_subtype": (
                    existing.source_sport_subtype
                    or external.source_sport_subtype
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
                "perceived_effort": (
                    existing.perceived_effort
                    or external.perceived_effort
                ),
                "device": device,
                "segments": existing.segments or external.segments,
                "origin": origin,
                "audit": audit,
                "calculated_load": existing.calculated_load,
            }
        )

    return existing.model_copy(
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
            "perceived_effort": existing.perceived_effort or external.perceived_effort,
            "device": external.device,
            "classification": external.classification,
            "segments": external.segments or existing.segments,
            "origin": origin,
            "audit": audit,
            "calculated_load": None,
        }
    )


def merge_reviewed_activity(
    existing: CanonicalActivity,
    external: CanonicalActivity,
) -> CanonicalActivity:
    """Apply a current explicit approval without weakening automatic rules."""
    if existing.sport_type != external.sport_type or existing.date != external.date:
        raise ValueError(
            "reviewed activity must retain the current sport/date candidate block"
        )
    existing_external_id = existing.origin.intervals_icu_activity_id
    incoming_external_id = external.origin.intervals_icu_activity_id
    if existing_external_id and existing_external_id != incoming_external_id:
        raise ValueError(
            "reviewed activity is already linked to a different external ID"
        )
    return _merged(existing, external)


def reconcile_activity(
    external: CanonicalActivity,
    existing_records: Iterable[CanonicalActivity],
) -> ReconciliationDecision:
    """Choose update/link/create/ambiguity with reviewable evidence."""
    external_id = external.origin.intervals_icu_activity_id
    if not external_id:
        raise ValueError("external activity is missing its Intervals.icu ID")
    existing = list(existing_records)

    linked = [
        item
        for item in existing
        if item.origin.intervals_icu_activity_id == external_id
    ]
    if len(linked) > 1:
        return ReconciliationDecision(
            action=ReconciliationAction.AMBIGUOUS,
            rule="duplicate_external_reference",
            external_activity_id=external_id,
            candidate_local_ids=sorted(item.local_activity_id for item in linked),
        )
    if linked:
        current = linked[0]
        if (
            current.audit.external_fingerprint_sha256
            == external.audit.external_fingerprint_sha256
        ):
            return ReconciliationDecision(
                action=ReconciliationAction.UPDATE,
                rule="linked_fingerprint_unchanged",
                external_activity_id=external_id,
                local_activity_id=current.local_activity_id,
                activity=current,
            )
        return ReconciliationDecision(
            action=ReconciliationAction.UPDATE,
            rule="linked_fingerprint_changed",
            external_activity_id=external_id,
            local_activity_id=current.local_activity_id,
            activity=_merged(current, external),
        )

    candidates = [
        item
        for item in existing
        if item.sport_type == external.sport_type and item.date == external.date
    ]
    upstream = [
        item
        for item in candidates
        if external.origin.upstream_external_id
        and item.origin.upstream_external_id == external.origin.upstream_external_id
    ]
    if len(upstream) == 1:
        match = upstream[0]
        return ReconciliationDecision(
            action=ReconciliationAction.LINK,
            rule="unique_upstream_external_id",
            external_activity_id=external_id,
            local_activity_id=match.local_activity_id,
            activity=_merged(match, external),
        )

    file_hash = [
        item
        for item in candidates
        if external.origin.original_file_sha256
        and item.origin.original_file_sha256 == external.origin.original_file_sha256
    ]
    if len(file_hash) == 1:
        match = file_hash[0]
        return ReconciliationDecision(
            action=ReconciliationAction.LINK,
            rule="unique_original_file_sha256",
            external_activity_id=external_id,
            local_activity_id=match.local_activity_id,
            activity=_merged(match, external),
        )

    strong: list[tuple[CanonicalActivity, dict[str, Optional[float]]]] = []
    for candidate in candidates:
        recorded, evidence = _strong_recorded(external, candidate)
        if recorded or _strong_manual(external, candidate):
            strong.append((candidate, evidence))
    if len(strong) == 1:
        match, evidence = strong[0]
        return ReconciliationDecision(
            action=ReconciliationAction.LINK,
            rule="unique_strong_composite",
            external_activity_id=external_id,
            local_activity_id=match.local_activity_id,
            evidence=evidence,
            activity=_merged(match, external),
        )
    if len(strong) > 1:
        return ReconciliationDecision(
            action=ReconciliationAction.AMBIGUOUS,
            rule="multiple_strong_candidates",
            external_activity_id=external_id,
            candidate_local_ids=sorted(item.local_activity_id for item, _ in strong),
        )

    review = [
        (candidate, evidence)
        for candidate in candidates
        for valid, evidence in [_review_candidate(external, candidate)]
        if valid
    ]
    if review:
        return ReconciliationDecision(
            action=ReconciliationAction.AMBIGUOUS,
            rule="review_window_candidates",
            external_activity_id=external_id,
            candidate_local_ids=sorted(item.local_activity_id for item, _ in review),
            evidence={
                item.local_activity_id: evidence
                for item, evidence in sorted(review, key=lambda pair: pair[0].local_activity_id)
            },
        )

    return ReconciliationDecision(
        action=ReconciliationAction.CREATE,
        rule="no_candidate",
        external_activity_id=external_id,
        local_activity_id=external.local_activity_id,
        activity=external,
    )
