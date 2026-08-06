"""Conservative deterministic overlap reconciliation."""

from __future__ import annotations

import re
from typing import Iterable, Optional

from resilio.core.activity_sync.activity_merge import (
    merge_external_activity,
)
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.reconciliation import (
    ReconciliationAction,
    ReconciliationDecision,
)


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
    """Compare wall-clock starts for historical records without a timezone.

    Some preserved historical source records contain a local timestamp but no
    source timezone, so interpreting that value as UTC would invent a fact.
    This alternate remains limited to those explicitly timezone-unknown
    records.
    """
    if candidate.origin.kind != "historical_import" or candidate.occurrence.timezone is not None:
        return None
    external_start = external.occurrence.start_time_local
    historical_start = candidate.occurrence.start_time_local
    if external_start is None or historical_start is None:
        return None
    return abs(
        (
            external_start.replace(tzinfo=None) - historical_start.replace(tzinfo=None)
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
    comparable = [value for value in (utc_delta, historical_wall_delta) if value is not None]
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
    start_delta, utc_start_delta, historical_wall_start_delta = _effective_start_deltas(
        external, candidate
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
    start_delta, utc_start_delta, historical_wall_start_delta = _effective_start_deltas(
        external, candidate
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
        historical_duration_delta if candidate.origin.kind == "historical_import" else elapsed_delta
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


def reconcile_activity(
    external: CanonicalActivity,
    existing_records: Iterable[CanonicalActivity],
) -> ReconciliationDecision:
    """Choose update/link/create/ambiguity with reviewable evidence."""
    external_id = external.origin.intervals_icu_activity_id
    if not external_id:
        raise ValueError("external activity is missing its Intervals.icu ID")
    existing = list(existing_records)

    linked_decision = _linked_activity_decision(external, existing)
    if linked_decision is not None:
        return linked_decision

    candidates = [
        item
        for item in existing
        if (
            item.sport == external.sport
            and item.occurrence.local_date == external.occurrence.local_date
        )
    ]
    identity_decision = _candidate_identity_decision(external, candidates)
    if identity_decision is not None:
        return identity_decision
    composite_decision = _strong_composite_decision(external, candidates)
    if composite_decision is not None:
        return composite_decision
    review_decision = _review_window_decision(external, candidates)
    if review_decision is not None:
        return review_decision
    return ReconciliationDecision(
        action=ReconciliationAction.CREATE,
        rule="no_candidate",
        external_activity_id=external_id,
        local_activity_id=external.local_activity_id,
        activity=external,
    )


def _linked_activity_decision(
    external: CanonicalActivity,
    existing: list[CanonicalActivity],
) -> ReconciliationDecision | None:
    external_id = external.origin.intervals_icu_activity_id
    assert external_id is not None
    linked = [item for item in existing if item.origin.intervals_icu_activity_id == external_id]
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
            current.audit.provider_snapshot_sha256 == external.audit.provider_snapshot_sha256
            and current.audit.canonical_mapping_version == external.audit.canonical_mapping_version
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
            activity=merge_external_activity(current, external),
        )
    return None


def _candidate_identity_decision(
    external: CanonicalActivity,
    candidates: list[CanonicalActivity],
) -> ReconciliationDecision | None:
    external_id = external.origin.intervals_icu_activity_id
    assert external_id is not None
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
            activity=merge_external_activity(match, external),
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
            activity=merge_external_activity(match, external),
        )
    return None


def _strong_composite_decision(
    external: CanonicalActivity,
    candidates: list[CanonicalActivity],
) -> ReconciliationDecision | None:
    external_id = external.origin.intervals_icu_activity_id
    assert external_id is not None
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
            activity=merge_external_activity(match, external),
        )
    if len(strong) > 1:
        return ReconciliationDecision(
            action=ReconciliationAction.AMBIGUOUS,
            rule="multiple_strong_candidates",
            external_activity_id=external_id,
            candidate_local_ids=sorted(item.local_activity_id for item, _ in strong),
        )
    return None


def _review_window_decision(
    external: CanonicalActivity,
    candidates: list[CanonicalActivity],
) -> ReconciliationDecision | None:
    external_id = external.origin.intervals_icu_activity_id
    assert external_id is not None
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
    return None
