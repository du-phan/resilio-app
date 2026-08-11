"""Transactional athlete-confirmed workout fulfillment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_transaction import ACTIVITY_MUTATION_LOCK_PATH
from resilio.core.locking import OperationLock
from resilio.core.planning.adherence_evidence import (
    AuthoritativeWorkout,
    resolve_approved_workouts_for_date_range,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.planning.state_repository import required_planning_state_unlocked
from resilio.core.planning.workout_evidence import load_publishable_workouts_unlocked
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.candidates import (
    FulfillmentWorkoutAuthority,
    build_fulfillment_candidates,
)
from resilio.core.workout_fulfillment.evidence import (
    assert_fulfillment_authority_is_current,
    assert_fulfillment_is_usable,
)
from resilio.core.workout_fulfillment.repository import (
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.core.workout_publication.locking import (
    coordinated_publication_plan_activity_lock,
    coordinated_publication_plan_lock,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.retirement_reopening import (
    reopen_revoked_fulfillment_retirement,
)
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    WorkoutFulfillmentCandidate,
    WorkoutFulfillmentCandidateDismissal,
    WorkoutFulfillmentRecord,
    WorkoutFulfillmentRevocation,
    WorkoutFulfillmentWeekStatus,
)


class WorkoutFulfillmentError(ValueError):
    """Fulfillment authority or confirmation evidence is invalid."""


class WorkoutFulfillmentService:
    """Prove and persist one exact activity-to-approved-workout association."""

    def __init__(self, repo: RepositoryIO):
        self.repo = repo

    def _load_activity_unlocked(self, local_activity_id: str) -> CanonicalActivity:
        activity = ActivityArchive(self.repo.resolve_path("data/activities")).load(
            local_activity_id
        )
        if activity is None:
            raise WorkoutFulfillmentError(f"Canonical activity does not exist: {local_activity_id}")
        return activity

    def _load_workout_authorities_unlocked(
        self,
    ) -> list[AuthoritativeWorkout]:
        state = required_planning_state_unlocked(self.repo)
        if state.active_plan is None:
            raise WorkoutFulfillmentError("There is no active plan")
        return load_publishable_workouts_unlocked(self.repo, state)

    def _load_candidate_workout_authorities_unlocked(
        self,
        activity: CanonicalActivity,
    ) -> list[FulfillmentWorkoutAuthority]:
        """Resolve the workout revision in force at each scheduled instant."""
        state = required_planning_state_unlocked(self.repo)
        anchor_date = activity.occurrence.local_date
        window = resolve_approved_workouts_for_date_range(
            state,
            window_start=anchor_date - timedelta(days=7),
            window_end=anchor_date + timedelta(days=7),
            closed_plan_archives=[],
        )
        if window.status != "available":
            raise WorkoutFulfillmentError(
                "Exact historical workout authority is unavailable: "
                f"{window.reason or window.status}"
            )
        return [
            FulfillmentWorkoutAuthority(
                identity=workout.identity,
                prescription=workout.prescription,
                applied_week_approval_id=workout.applied_week_approval_id,
                applied_running_workouts_sha256=(workout.applied_running_workouts_sha256),
                schedule_timezone=workout.schedule_timezone,
            )
            for workout in window.workouts
        ]

    def _candidates_unlocked(
        self,
        local_activity_id: str,
    ) -> list[WorkoutFulfillmentCandidate]:
        activity = self._load_activity_unlocked(local_activity_id)
        return build_fulfillment_candidates(
            activity=activity,
            workout_authorities=self._load_candidate_workout_authorities_unlocked(activity),
            manifest=load_fulfillment_manifest(self.repo),
        )

    def candidates(
        self,
        *,
        local_activity_id: str,
    ) -> list[WorkoutFulfillmentCandidate]:
        with coordinated_publication_plan_lock(
            self.repo,
            "list_workout_fulfillment_candidates",
        ):
            with OperationLock(
                self.repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH),
                "list_workout_fulfillment_candidates",
            ):
                return self._candidates_unlocked(local_activity_id)

    def week_status(self, *, week_number: int) -> WorkoutFulfillmentWeekStatus:
        with coordinated_publication_plan_lock(
            self.repo,
            "get_workout_fulfillment_week_status",
        ):
            with OperationLock(
                self.repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH),
                "get_workout_fulfillment_week_status",
            ):
                authorities = [
                    authority
                    for authority in self._load_workout_authorities_unlocked()
                    if authority.identity.week_number == week_number
                ]
                if not authorities:
                    raise WorkoutFulfillmentError(
                        f"Week {week_number} has no active applied workouts"
                    )
                manifest = load_fulfillment_manifest(self.repo)
                fulfillment_by_identity = {
                    (
                        record.workout_identity.plan_id,
                        record.workout_identity.plan_revision_id,
                        record.workout_identity.week_number,
                        record.workout_identity.local_workout_id,
                    ): record
                    for record in manifest.fulfillments.values()
                }
                fulfilled: list[WorkoutFulfillmentRecord] = []
                outstanding = []
                for authority in authorities:
                    identity = authority.identity
                    record = fulfillment_by_identity.get(
                        (
                            identity.plan_id,
                            identity.plan_revision_id,
                            identity.week_number,
                            identity.local_workout_id,
                        )
                    )
                    if record is None:
                        outstanding.append(identity)
                    else:
                        activity = self._load_activity_unlocked(record.local_activity_id)
                        try:
                            assert_fulfillment_authority_is_current(record, authority)
                            assert_fulfillment_is_usable(record, activity, manifest)
                        except ValueError as exc:
                            raise WorkoutFulfillmentError(str(exc)) from exc
                        fulfilled.append(record)
                return WorkoutFulfillmentWeekStatus(
                    week_number=week_number,
                    fulfilled=fulfilled,
                    outstanding_workout_identities=outstanding,
                )

    def confirm(
        self,
        *,
        local_activity_id: str,
        local_workout_id: str,
        candidate_sha256: str,
        athlete_confirmation_reference: str,
        coaching_rationale: str,
        confirmed_at_utc: datetime | None = None,
    ) -> WorkoutFulfillmentRecord:
        confirmation_time_utc = confirmed_at_utc or datetime.now(timezone.utc)
        with coordinated_publication_plan_lock(
            self.repo,
            "confirm_workout_fulfillment",
        ):
            with OperationLock(
                self.repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH),
                "confirm_workout_fulfillment",
            ):
                return self._confirm_unlocked(
                    local_activity_id=local_activity_id,
                    local_workout_id=local_workout_id,
                    candidate_sha256=candidate_sha256,
                    athlete_confirmation_reference=athlete_confirmation_reference,
                    coaching_rationale=coaching_rationale,
                    confirmed_at_utc=confirmation_time_utc,
                )

    def _confirm_unlocked(
        self,
        *,
        local_activity_id: str,
        local_workout_id: str,
        candidate_sha256: str,
        athlete_confirmation_reference: str,
        coaching_rationale: str,
        confirmed_at_utc: datetime,
    ) -> WorkoutFulfillmentRecord:
        manifest = load_fulfillment_manifest(self.repo)
        confirmation = AthleteConfirmedFulfillmentEvidence(
            candidate_sha256=candidate_sha256,
            athlete_confirmation_reference=athlete_confirmation_reference,
            coaching_rationale=coaching_rationale,
            confirmed_at_utc=confirmed_at_utc,
        )
        existing = manifest.fulfillments.get(local_activity_id)
        if existing is not None:
            existing_confirmation = existing.athlete_confirmation
            if (
                existing.workout_identity.local_workout_id == local_workout_id
                and existing_confirmation is not None
                and existing_confirmation.candidate_sha256 == candidate_sha256
                and existing_confirmation.athlete_confirmation_reference
                == athlete_confirmation_reference
                and existing_confirmation.coaching_rationale == coaching_rationale
            ):
                return existing
            candidate = next(
                (
                    item
                    for item in self._candidates_unlocked(local_activity_id)
                    if item.workout_identity.local_workout_id == local_workout_id
                    and item.candidate_sha256 == candidate_sha256
                ),
                None,
            )
            if (
                existing.provider_pair is not None
                and existing.athlete_confirmation is None
                and candidate is not None
                and candidate.workout_identity == existing.workout_identity
            ):
                enriched = WorkoutFulfillmentRecord.model_validate(
                    {
                        **existing.model_dump(mode="python"),
                        "athlete_confirmation": confirmation,
                    }
                )
                updated = manifest.model_copy(deep=True)
                updated.fulfillments[local_activity_id] = enriched
                save_fulfillment_manifest(self.repo, updated)
                return enriched
            raise WorkoutFulfillmentError(
                "Confirmation conflicts with the existing fulfillment record"
            )
        candidate = next(
            (
                item
                for item in self._candidates_unlocked(local_activity_id)
                if item.workout_identity.local_workout_id == local_workout_id
                and item.candidate_sha256 == candidate_sha256
            ),
            None,
        )
        if candidate is None:
            raise WorkoutFulfillmentError(
                "Fulfillment candidate is stale or ineligible; list candidates again"
            )
        record = WorkoutFulfillmentRecord(
            local_activity_id=local_activity_id,
            workout_identity=candidate.workout_identity,
            applied_week_approval_id=candidate.applied_week_approval_id,
            applied_running_workouts_sha256=(candidate.applied_running_workouts_sha256),
            workout_prescription_sha256=candidate.workout_prescription_sha256,
            activity_performance_evidence_sha256=(candidate.activity_performance_evidence_sha256),
            schedule_timezone=candidate.schedule_timezone,
            scheduled_local_date=candidate.scheduled_local_date,
            execution_local_date=candidate.execution_local_date,
            schedule_offset_days=candidate.schedule_offset_days,
            athlete_confirmation=confirmation,
            recorded_at_utc=confirmed_at_utc,
        )
        updated = manifest.model_copy(deep=True)
        updated.fulfillments[local_activity_id] = record
        save_fulfillment_manifest(self.repo, updated)
        return record

    def dismiss_candidate(
        self,
        *,
        local_activity_id: str,
        local_workout_id: str,
        candidate_sha256: str,
        athlete_response_reference: str,
        dismissed_at_utc: datetime | None = None,
    ) -> WorkoutFulfillmentCandidateDismissal:
        dismissal_time_utc = dismissed_at_utc or datetime.now(timezone.utc)
        if dismissal_time_utc.tzinfo is None or dismissal_time_utc.utcoffset() is None:
            raise WorkoutFulfillmentError("dismissed_at_utc must be timezone-aware")
        dismissal_time_utc = dismissal_time_utc.astimezone(timezone.utc)
        with coordinated_publication_plan_lock(
            self.repo,
            "dismiss_workout_fulfillment_candidate",
        ):
            with OperationLock(
                self.repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH),
                "dismiss_workout_fulfillment_candidate",
            ):
                manifest = load_fulfillment_manifest(self.repo)
                active_fulfillment = manifest.fulfillments.get(local_activity_id)
                if (
                    active_fulfillment is not None
                    and active_fulfillment.provider_pair is not None
                    and active_fulfillment.athlete_confirmation is None
                    and active_fulfillment.workout_identity.local_workout_id == local_workout_id
                ):
                    raise WorkoutFulfillmentError(
                        "Provider-paired fulfillment denial requires explicit revocation"
                    )
                existing = manifest.dismissed_candidates.get(candidate_sha256)
                if existing is not None:
                    exact_retry = (
                        existing.local_activity_id == local_activity_id
                        and existing.workout_identity.local_workout_id == local_workout_id
                        and existing.athlete_response_reference == athlete_response_reference
                    )
                    if exact_retry:
                        return existing
                    raise WorkoutFulfillmentError(
                        "Dismissal conflicts with the existing candidate decision"
                    )
                proposed = WorkoutFulfillmentCandidateDismissal(
                    candidate_sha256=candidate_sha256,
                    local_activity_id=local_activity_id,
                    workout_identity=self._required_candidate_unlocked(
                        local_activity_id=local_activity_id,
                        local_workout_id=local_workout_id,
                        candidate_sha256=candidate_sha256,
                    ).workout_identity,
                    athlete_response_reference=athlete_response_reference,
                    dismissed_at_utc=dismissal_time_utc,
                )
                updated = manifest.model_copy(deep=True)
                updated.dismissed_candidates[candidate_sha256] = proposed
                save_fulfillment_manifest(self.repo, updated)
                return proposed

    def revoke(
        self,
        *,
        local_activity_id: str,
        local_workout_id: str,
        reason: Literal[
            "activity_deleted",
            "activity_reclassified",
            "association_incorrect",
        ],
        athlete_confirmation_reference: str,
        coaching_rationale: str,
        revoked_at_utc: datetime | None = None,
    ) -> WorkoutFulfillmentRevocation:
        """Withdraw one exact association and reopen any retirement it authorized."""
        revocation_time_utc = revoked_at_utc or datetime.now(timezone.utc)
        if revocation_time_utc.tzinfo is None or revocation_time_utc.utcoffset() is None:
            raise WorkoutFulfillmentError("revoked_at_utc must be timezone-aware")
        with coordinated_publication_plan_activity_lock(
            self.repo,
            "revoke_workout_fulfillment",
        ):
            manifest = load_fulfillment_manifest(self.repo)
            existing = manifest.fulfillments.get(local_activity_id)
            semantic_payload = {
                "local_activity_id": local_activity_id,
                "local_workout_id": local_workout_id,
                "reason": reason,
                "athlete_confirmation_reference": athlete_confirmation_reference,
                "coaching_rationale": coaching_rationale,
            }
            if existing is None:
                prior = next(
                    (
                        item
                        for item in reversed(manifest.revoked_fulfillments)
                        if item.fulfillment.local_activity_id == local_activity_id
                        and item.fulfillment.workout_identity.local_workout_id == local_workout_id
                        and item.reason == reason
                        and item.athlete_confirmation_reference == athlete_confirmation_reference
                        and item.coaching_rationale == coaching_rationale
                    ),
                    None,
                )
                if prior is not None:
                    reopen_revoked_fulfillment_retirement(
                        self.repo,
                        load_manifest(self.repo),
                        local_workout_id=local_workout_id,
                    )
                    return prior
                raise WorkoutFulfillmentError(
                    "No active workout fulfillment matches the revocation request"
                )
            semantic_payload["fulfillment_sha256"] = canonical_data_sha256(existing)
            revocation_id = (
                "fulfillment_revocation_" f"{canonical_data_sha256(semantic_payload)[:16]}"
            )
            if existing.workout_identity.local_workout_id != local_workout_id:
                raise WorkoutFulfillmentError(
                    "Fulfillment revocation workout identity does not match"
                )
            revocation = WorkoutFulfillmentRevocation(
                revocation_id=revocation_id,
                fulfillment=existing,
                reason=reason,
                athlete_confirmation_reference=athlete_confirmation_reference,
                coaching_rationale=coaching_rationale,
                revoked_at_utc=revocation_time_utc,
            )
            updated = manifest.model_copy(deep=True)
            del updated.fulfillments[local_activity_id]
            updated.unresolved_fulfillment_conflicts.pop(local_activity_id, None)
            updated.revoked_fulfillments.append(revocation)
            save_fulfillment_manifest(self.repo, updated)
            reopen_revoked_fulfillment_retirement(
                self.repo,
                load_manifest(self.repo),
                local_workout_id=local_workout_id,
            )
            return revocation

    def _required_candidate_unlocked(
        self,
        *,
        local_activity_id: str,
        local_workout_id: str,
        candidate_sha256: str,
    ) -> WorkoutFulfillmentCandidate:
        for candidate in self._candidates_unlocked(local_activity_id):
            if (
                candidate.workout_identity.local_workout_id == local_workout_id
                and candidate.candidate_sha256 == candidate_sha256
            ):
                return candidate
        raise WorkoutFulfillmentError(
            "Fulfillment candidate is stale or ineligible; list candidates again"
        )
