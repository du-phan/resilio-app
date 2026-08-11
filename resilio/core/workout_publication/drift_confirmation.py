"""Opaque athlete-confirmation tokens for exact owned remote drift bytes."""

from __future__ import annotations

from dataclasses import dataclass

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.core.workout_publication.retirement_service import (
    WorkoutRetirementService,
)
from resilio.schemas.publication import (
    ConfirmedPublicationDriftTarget,
    WeekSynchronizationItem,
)


@dataclass(frozen=True)
class ObservedPublicationDriftTarget:
    target: ConfirmedPublicationDriftTarget
    confirmation_token_sha256: str


def observe_publication_drift_target(
    retirement_service: WorkoutRetirementService,
    *,
    local_workout_id: str,
    authoritative_workout: AuthoritativeWorkout,
    provider_name: str,
) -> ObservedPublicationDriftTarget:
    event_id, remote_fingerprint_sha256 = retirement_service.observe_remote_target(
        local_workout_id,
        authoritative_workout=authoritative_workout,
        provider_name=provider_name,
    )
    target = ConfirmedPublicationDriftTarget(
        local_workout_id=local_workout_id,
        event_id=event_id,
        observed_remote_fingerprint_sha256=remote_fingerprint_sha256,
    )
    return ObservedPublicationDriftTarget(
        target=target,
        confirmation_token_sha256=canonical_data_sha256(target.model_dump(mode="json")),
    )


def confirm_publication_drift_targets(
    retirement_service: WorkoutRetirementService,
    *,
    drift_items: list[WeekSynchronizationItem],
    authoritative_workouts_by_local_id: dict[str, AuthoritativeWorkout],
    provider_names_by_local_workout_id: dict[str, str],
    supplied_confirmation_tokens: list[str],
) -> list[ConfirmedPublicationDriftTarget]:
    """Bind consent to preflight tokens and prove the remote bytes remain unchanged."""
    expected_tokens = {
        item.drift_resolution_token_sha256
        for item in drift_items
        if item.drift_resolution_token_sha256 is not None
    }
    if (
        len(expected_tokens) != len(drift_items)
        or len(supplied_confirmation_tokens) != len(set(supplied_confirmation_tokens))
        or set(supplied_confirmation_tokens) != expected_tokens
    ):
        raise PublicationSafetyError(
            "Athlete confirmation must provide every and only displayed drift token"
        )
    confirmed_targets: list[ConfirmedPublicationDriftTarget] = []
    for item in sorted(drift_items, key=lambda candidate: candidate.local_workout_id):
        observed = observe_publication_drift_target(
            retirement_service,
            local_workout_id=item.local_workout_id,
            authoritative_workout=authoritative_workouts_by_local_id[item.local_workout_id],
            provider_name=provider_names_by_local_workout_id[item.local_workout_id],
        )
        if observed.confirmation_token_sha256 != item.drift_resolution_token_sha256:
            raise PublicationSafetyError(
                "Remote event changed after drift status was shown to the athlete"
            )
        confirmed_targets.append(observed.target)
    return confirmed_targets
