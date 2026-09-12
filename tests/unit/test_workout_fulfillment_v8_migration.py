from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

import resilio.core.workout_fulfillment.migration as migration_module
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.artifacts import (
    canonical_data_sha256,
)
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.preparation import rendered_workout_sha256
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    RetiredWorkoutPublication,
)
from resilio.schemas.workout_fulfillment import (
    AthleteConfirmedFulfillmentEvidence,
    FulfillmentActivityEvidenceRevision,
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
    WorkoutFulfillmentRevocation,
)
from tests.factories import make_activity
from tests.unit.test_activity_sync import _publication
from tests.unit.test_workout_fulfillment_migration import (
    _authority,
    _migration_authority,
)


def test_v8_migration_attributes_legacy_move_only_to_exact_fulfillment() -> None:
    authority = _authority()
    execution_local_date = date(2026, 7, 27)
    publication = _publication().model_copy(
        update={
            "workout_identity": authority.identity,
            "applied_week_approval_id": authority.applied_week_approval_id,
            "applied_running_workouts_sha256": (authority.applied_running_workouts_sha256),
            "workout_prescription_sha256": canonical_data_sha256(authority.prescription),
            "rendered_workout_sha256": rendered_workout_sha256(authority.prescription),
            "schedule_timezone": authority.schedule_timezone,
            "occurrence_date": authority.prescription.date,
            "provider_start_date_local": "2026-07-27T07:00:00",
        }
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="activity-calendar-move",
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        activity_performance_evidence_sha256="a" * 64,
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=authority.prescription.date,
        execution_local_date=execution_local_date,
        schedule_offset_days=-1,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=publication.event_id,
            observed_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
    )

    migrated, changed = migration_module._migrate_publication_manifest(
        {
            "schema_version": 8,
            "workouts": {"planned-run": publication.model_dump(mode="json")},
        },
        [_migration_authority()],
        migration_date=date(2026, 8, 11),
        fulfillment_manifest=WorkoutFulfillmentManifest(
            fulfillments={fulfillment.local_activity_id: fulfillment}
        ),
    )

    assert changed
    placement = migrated.workout_provider_occurrence_placements["planned-run"]
    assert placement.calendar_source == "approved_schedule"
    assert placement.calendar_occurrence_date == authority.prescription.date
    assert placement.fulfillment_override is not None
    assert placement.fulfillment_override.local_activity_id == fulfillment.local_activity_id
    assert placement.effective_occurrence_date == execution_local_date


def test_v8_migration_requires_exact_schedule_time_publication_authority() -> None:
    authority = _authority()
    publication = _publication().model_copy(
        update={
            "workout_identity": authority.identity,
            "applied_week_approval_id": authority.applied_week_approval_id,
            "applied_running_workouts_sha256": (authority.applied_running_workouts_sha256),
            "workout_prescription_sha256": canonical_data_sha256(authority.prescription),
            "rendered_workout_sha256": rendered_workout_sha256(authority.prescription),
            "schedule_timezone": authority.schedule_timezone,
            "occurrence_date": authority.prescription.date,
        }
    )

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="schedule-time workout authority",
    ):
        migration_module._migrate_publication_manifest(
            {
                "schema_version": 8,
                "workouts": {"planned-run": publication.model_dump(mode="json")},
            },
            [],
            migration_date=date(2026, 8, 11),
        )


def test_v8_migration_prefers_active_fulfillment_over_revoked_history() -> None:
    authority = _authority()
    execution_local_date = date(2026, 7, 27)
    publication = _publication().model_copy(
        update={
            "workout_identity": authority.identity,
            "applied_week_approval_id": authority.applied_week_approval_id,
            "applied_running_workouts_sha256": (authority.applied_running_workouts_sha256),
            "workout_prescription_sha256": canonical_data_sha256(authority.prescription),
            "rendered_workout_sha256": rendered_workout_sha256(authority.prescription),
            "schedule_timezone": authority.schedule_timezone,
            "occurrence_date": authority.prescription.date,
            "provider_start_date_local": "2026-07-27T07:00:00",
        }
    )

    def fulfillment(local_activity_id: str, recorded_hour: int) -> WorkoutFulfillmentRecord:
        return WorkoutFulfillmentRecord(
            local_activity_id=local_activity_id,
            workout_identity=authority.identity,
            applied_week_approval_id=authority.applied_week_approval_id,
            applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
            workout_prescription_sha256=canonical_data_sha256(authority.prescription),
            activity_performance_evidence_sha256=local_activity_id[-1] * 64,
            schedule_timezone=authority.schedule_timezone,
            scheduled_local_date=authority.prescription.date,
            execution_local_date=execution_local_date,
            schedule_offset_days=-1,
            provider_pair=ProviderPairedFulfillmentEvidence(
                provenance="provider_observed",
                event_id=publication.event_id,
                observed_at_utc=datetime(
                    2026,
                    7,
                    27,
                    recorded_hour,
                    tzinfo=timezone.utc,
                ),
            ),
            recorded_at_utc=datetime(
                2026,
                7,
                27,
                recorded_hour,
                tzinfo=timezone.utc,
            ),
        )

    revoked = fulfillment("activity-1", 8)
    active = fulfillment("activity-2", 10)
    manifest = WorkoutFulfillmentManifest(
        fulfillments={active.local_activity_id: active},
        revoked_fulfillments=[
            WorkoutFulfillmentRevocation(
                revocation_id="fulfillment_revocation_1111111111111111",
                fulfillment=revoked,
                reason="association_incorrect",
                athlete_confirmation_reference="Athlete withdrew the old association.",
                coaching_rationale="The athlete identified a different completed activity.",
                revoked_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
            )
        ],
    )

    migrated, _ = migration_module._migrate_publication_manifest(
        {
            "schema_version": 8,
            "workouts": {"planned-run": publication.model_dump(mode="json")},
        },
        [_migration_authority()],
        migration_date=date(2026, 8, 11),
        fulfillment_manifest=manifest,
    )

    override = migrated.workout_provider_occurrence_placements["planned-run"].fulfillment_override
    assert override is not None
    assert override.local_activity_id == active.local_activity_id


def test_v8_migration_accepts_a_proven_prior_fulfillment_execution_date() -> None:
    authority = _authority()
    publication = _publication().model_copy(
        update={
            "workout_identity": authority.identity,
            "applied_week_approval_id": authority.applied_week_approval_id,
            "applied_running_workouts_sha256": (authority.applied_running_workouts_sha256),
            "workout_prescription_sha256": canonical_data_sha256(authority.prescription),
            "rendered_workout_sha256": rendered_workout_sha256(authority.prescription),
            "schedule_timezone": authority.schedule_timezone,
            "occurrence_date": authority.prescription.date,
            "provider_start_date_local": "2026-07-27T07:00:00",
        }
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="activity-corrected-date",
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        activity_performance_evidence_sha256="b" * 64,
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=authority.prescription.date,
        execution_local_date=authority.prescription.date,
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=publication.event_id,
            observed_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
        ),
        activity_evidence_revisions=[
            FulfillmentActivityEvidenceRevision(
                previous_activity_performance_evidence_sha256="a" * 64,
                replacement_activity_performance_evidence_sha256="b" * 64,
                previous_execution_local_date=date(2026, 7, 27),
                replacement_execution_local_date=authority.prescription.date,
                observed_at_utc=datetime(2026, 7, 28, 8, tzinfo=timezone.utc),
            )
        ],
        recorded_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
    )

    migrated, _ = migration_module._migrate_publication_manifest(
        {
            "schema_version": 8,
            "workouts": {"planned-run": publication.model_dump(mode="json")},
        },
        [_migration_authority()],
        migration_date=date(2026, 8, 11),
        fulfillment_manifest=WorkoutFulfillmentManifest(
            fulfillments={fulfillment.local_activity_id: fulfillment}
        ),
    )

    placement = migrated.workout_provider_occurrence_placements["planned-run"]
    assert placement.fulfillment_override is not None
    assert placement.fulfillment_override.execution_local_date == date(2026, 7, 27)
    assert placement.effective_occurrence_date == date(2026, 7, 27)


@pytest.mark.parametrize("provider_pair_event_id", [None, 73])
def test_v8_pending_only_publication_accepts_exact_active_fulfillment(
    provider_pair_event_id: int | None,
) -> None:
    authority = _authority()
    publication = _publication()
    pending = PendingWorkoutPublication(
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        schedule_timezone=authority.schedule_timezone,
        uid=publication.uid,
        external_id=publication.external_id,
        publication_fingerprint_sha256=publication.publication_fingerprint_sha256,
        rendered_workout_sha256=publication.rendered_workout_sha256,
        sport_settings_version_sha256=publication.sport_settings_version_sha256,
        sport="run",
        occurrence_date=authority.prescription.date,
        approved_start_time_local=publication.approved_start_time_local,
        provider_start_date_local="2026-07-28T07:00:00",
        prepared_at_utc=publication.verified_at_utc,
    )
    activity = make_activity(id="pending-activity", date=authority.prescription.date)
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=authority.prescription.date,
        execution_local_date=authority.prescription.date,
        schedule_offset_days=0,
        provider_pair=(
            ProviderPairedFulfillmentEvidence(
                provenance="provider_observed",
                event_id=provider_pair_event_id,
                observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
            )
            if provider_pair_event_id is not None
            else None
        ),
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="4" * 64,
            athlete_confirmation_reference="Athlete confirmed the exact association.",
            coaching_rationale="The athlete confirmed this run fulfilled the workout.",
            confirmed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    )
    raw_fulfillment = WorkoutFulfillmentManifest(
        fulfillments={fulfillment.local_activity_id: fulfillment}
    ).model_dump(mode="json")
    migrated_publication, _ = migration_module._migrate_publication_manifest(
        {
            "schema_version": 8,
            "pending": {"planned-run": pending.model_dump(mode="json")},
        },
        [_migration_authority()],
        migration_date=date(2026, 8, 11),
        fulfillment_manifest=WorkoutFulfillmentManifest.model_validate(raw_fulfillment),
    )

    migrated_fulfillment, _ = migration_module._migrate_current_fulfillment_manifest(
        raw_fulfillment,
        migrated_publication,
        [_migration_authority()],
        {activity.local_activity_id: activity},
    )

    assert set(migrated_fulfillment.fulfillments) == {activity.local_activity_id}


def test_current_v2_repairs_missing_pending_only_revoked_unpair() -> None:
    authority = _authority()
    publication = _publication()
    pending = PendingWorkoutPublication(
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        schedule_timezone=authority.schedule_timezone,
        uid=publication.uid,
        external_id=publication.external_id,
        publication_fingerprint_sha256=publication.publication_fingerprint_sha256,
        rendered_workout_sha256=publication.rendered_workout_sha256,
        sport_settings_version_sha256=publication.sport_settings_version_sha256,
        sport="run",
        occurrence_date=authority.prescription.date,
        approved_start_time_local=publication.approved_start_time_local,
        provider_start_date_local="2026-07-28T07:00:00",
        prepared_at_utc=publication.verified_at_utc,
    )
    activity = make_activity(id="revoked-pending", date=authority.prescription.date)
    activity = activity.model_copy(
        update={
            "origin": activity.origin.model_copy(
                update={"intervals_icu_activity_id": "i-revoked-pending"}
            )
        }
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=authority.prescription.date,
        execution_local_date=authority.prescription.date,
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=73,
            observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    )
    revocation = WorkoutFulfillmentRevocation(
        revocation_id="fulfillment_revocation_1111111111111111",
        fulfillment=fulfillment,
        intervals_icu_activity_id="i-revoked-pending",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew this exact association.",
        coaching_rationale="The athlete confirmed the activity did not fulfill this workout.",
        revoked_at_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc),
    )
    current = WorkoutFulfillmentManifest(revoked_fulfillments=[revocation])
    migrated_publication, _ = migration_module._migrate_publication_manifest(
        {
            "schema_version": 8,
            "pending": {"planned-run": pending.model_dump(mode="json")},
        },
        [_migration_authority()],
        migration_date=date(2026, 8, 11),
        fulfillment_manifest=current,
    )

    migrated, changed = migration_module._migrate_current_fulfillment_manifest(
        current.model_dump(mode="json"),
        migrated_publication,
        [_migration_authority()],
        {activity.local_activity_id: activity},
    )
    repeated, repeated_changed = migration_module._migrate_current_fulfillment_manifest(
        migrated.model_dump(mode="json"),
        migrated_publication,
        [_migration_authority()],
        {activity.local_activity_id: activity},
    )

    assert changed
    operations = list(migrated.remote_pairing_operations.values())
    assert len(operations) == 1
    assert operations[0].action == "unpair"
    assert operations[0].event_id == 73
    assert operations[0].revocation_id == revocation.revocation_id
    assert repeated == migrated
    assert not repeated_changed


def test_current_v2_repairs_missing_historical_revoked_unpair() -> None:
    authority = _authority()
    publication = _publication().model_copy(
        update={
            "workout_identity": authority.identity,
            "applied_week_approval_id": authority.applied_week_approval_id,
            "applied_running_workouts_sha256": (authority.applied_running_workouts_sha256),
            "workout_prescription_sha256": canonical_data_sha256(authority.prescription),
            "rendered_workout_sha256": rendered_workout_sha256(authority.prescription),
            "schedule_timezone": authority.schedule_timezone,
            "occurrence_date": authority.prescription.date,
        }
    )
    activity = make_activity(id="revoked-historical", date=date(2026, 7, 27))
    activity = activity.model_copy(
        update={
            "origin": activity.origin.model_copy(
                update={"intervals_icu_activity_id": "i-revoked-historical"}
            )
        }
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=authority.prescription.date,
        execution_local_date=date(2026, 7, 27),
        schedule_offset_days=-1,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=publication.event_id,
            observed_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
    )
    revocation = WorkoutFulfillmentRevocation(
        revocation_id="fulfillment_revocation_2222222222222222",
        fulfillment=fulfillment,
        intervals_icu_activity_id="i-revoked-historical",
        reason="association_incorrect",
        athlete_confirmation_reference="Athlete withdrew this exact association.",
        coaching_rationale="The athlete confirmed the activity did not fulfill this workout.",
        revoked_at_utc=datetime(2026, 7, 27, 10, tzinfo=timezone.utc),
    )
    current = WorkoutFulfillmentManifest(revoked_fulfillments=[revocation])
    publication_manifest = PublicationManifest(
        historical_fulfillment_event_retirements=[
            RetiredWorkoutPublication(
                publication=publication,
                fulfilling_local_activity_id=activity.local_activity_id,
                fulfillment_record_sha256_at_retirement=canonical_data_sha256(fulfillment),
                execution_local_date_at_retirement=date(2026, 7, 27),
                schedule_offset_days_at_retirement=-1,
                provider_deletion_status="deleted",
                retired_at_utc=datetime(2026, 7, 27, 9, 30, tzinfo=timezone.utc),
            )
        ]
    )

    migrated, changed = migration_module._migrate_current_fulfillment_manifest(
        current.model_dump(mode="json"),
        publication_manifest,
        [_migration_authority()],
        {activity.local_activity_id: activity},
    )

    assert changed
    operation = next(iter(migrated.remote_pairing_operations.values()))
    assert operation.action == "unpair"
    assert operation.event_id == publication.event_id
    assert operation.revocation_id == revocation.revocation_id


@pytest.mark.parametrize(
    ("provider_pair_event_id", "migration_is_valid"),
    [(None, True), (42, True), (73, False)],
)
def test_v8_dual_state_accepts_fulfillment_owned_by_revised_pending(
    provider_pair_event_id: int | None,
    migration_is_valid: bool,
) -> None:
    original = _authority()
    revision_boundary_utc = datetime(2026, 7, 28, 9, tzinfo=timezone.utc)
    revised = replace(
        original,
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    published = _publication().model_copy(
        update={
            "workout_identity": original.identity,
            "applied_week_approval_id": original.applied_week_approval_id,
            "applied_running_workouts_sha256": original.applied_running_workouts_sha256,
            "workout_prescription_sha256": canonical_data_sha256(original.prescription),
            "rendered_workout_sha256": rendered_workout_sha256(original.prescription),
            "schedule_timezone": original.schedule_timezone,
            "occurrence_date": original.prescription.date,
        }
    )
    pending = PendingWorkoutPublication(
        workout_identity=revised.identity,
        applied_week_approval_id=revised.applied_week_approval_id,
        applied_running_workouts_sha256=revised.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(revised.prescription),
        schedule_timezone=revised.schedule_timezone,
        uid=published.uid,
        external_id=published.external_id,
        publication_fingerprint_sha256=published.publication_fingerprint_sha256,
        rendered_workout_sha256=published.rendered_workout_sha256,
        sport_settings_version_sha256=published.sport_settings_version_sha256,
        sport="run",
        occurrence_date=revised.prescription.date,
        approved_start_time_local=published.approved_start_time_local,
        provider_start_date_local=published.provider_start_date_local,
        prepared_at_utc=revision_boundary_utc,
    )
    activity = make_activity(id="revised-activity", date=revised.prescription.date)
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id=activity.local_activity_id,
        workout_identity=revised.identity,
        applied_week_approval_id=revised.applied_week_approval_id,
        applied_running_workouts_sha256=revised.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(revised.prescription),
        activity_performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        schedule_timezone=revised.schedule_timezone,
        scheduled_local_date=revised.prescription.date,
        execution_local_date=revised.prescription.date,
        schedule_offset_days=0,
        provider_pair=(
            ProviderPairedFulfillmentEvidence(
                provenance="provider_observed",
                event_id=provider_pair_event_id,
                observed_at_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc),
            )
            if provider_pair_event_id is not None
            else None
        ),
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="5" * 64,
            athlete_confirmation_reference="Athlete confirmed the revised association.",
            coaching_rationale="The athlete confirmed this run fulfilled the revised workout.",
            confirmed_at_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc),
    )
    raw_fulfillment = WorkoutFulfillmentManifest(
        fulfillments={fulfillment.local_activity_id: fulfillment}
    ).model_dump(mode="json")
    original_migration_authority = replace(
        _migration_authority(),
        valid_until_utc=revision_boundary_utc,
    )
    revised_migration_authority = replace(
        _migration_authority(),
        workout=revised,
        valid_from_utc=revision_boundary_utc,
    )
    authorities = [original_migration_authority, revised_migration_authority]
    migrated_publication, _ = migration_module._migrate_publication_manifest(
        {
            "schema_version": 8,
            "workouts": {"planned-run": published.model_dump(mode="json")},
            "pending": {"planned-run": pending.model_dump(mode="json")},
        },
        authorities,
        migration_date=date(2026, 8, 11),
        fulfillment_manifest=WorkoutFulfillmentManifest.model_validate(raw_fulfillment),
    )

    if not migration_is_valid:
        with pytest.raises(
            migration_module.WorkoutFulfillmentMigrationError,
            match="exact publication authority",
        ):
            migration_module._migrate_current_fulfillment_manifest(
                raw_fulfillment,
                migrated_publication,
                authorities,
                {activity.local_activity_id: activity},
            )
        return
    migrated_fulfillment, _ = migration_module._migrate_current_fulfillment_manifest(
        raw_fulfillment,
        migrated_publication,
        authorities,
        {activity.local_activity_id: activity},
    )

    assert set(migrated_fulfillment.fulfillments) == {activity.local_activity_id}


def test_v8_publication_accepts_fulfillment_from_retained_approval_lineage() -> None:
    original = _authority()
    revision_boundary_utc = datetime(2026, 7, 28, 10, tzinfo=timezone.utc)
    revised = replace(
        original,
        applied_week_approval_id="week_approval_2222222222222222",
        applied_running_workouts_sha256="b" * 64,
    )
    publication = _publication().model_copy(
        update={
            "workout_identity": revised.identity,
            "applied_week_approval_id": revised.applied_week_approval_id,
            "applied_running_workouts_sha256": (revised.applied_running_workouts_sha256),
            "workout_prescription_sha256": canonical_data_sha256(revised.prescription),
            "rendered_workout_sha256": rendered_workout_sha256(revised.prescription),
            "schedule_timezone": revised.schedule_timezone,
            "occurrence_date": revised.prescription.date,
            "provider_start_date_local": "2026-07-27T07:00:00",
            "verified_at_utc": revision_boundary_utc,
        }
    )
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="retained-approval-activity",
        workout_identity=original.identity,
        applied_week_approval_id=original.applied_week_approval_id,
        applied_running_workouts_sha256=original.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(original.prescription),
        activity_performance_evidence_sha256="a" * 64,
        schedule_timezone=original.schedule_timezone,
        scheduled_local_date=original.prescription.date,
        execution_local_date=date(2026, 7, 27),
        schedule_offset_days=-1,
        athlete_confirmation=AthleteConfirmedFulfillmentEvidence(
            candidate_sha256="5" * 64,
            athlete_confirmation_reference="Athlete confirmed the exact association.",
            coaching_rationale="The athlete confirmed this run fulfilled the workout.",
            confirmed_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 27, 9, tzinfo=timezone.utc),
    )
    authorities = [
        replace(
            _migration_authority(),
            valid_until_utc=revision_boundary_utc,
        ),
        replace(
            _migration_authority(),
            workout=revised,
            valid_from_utc=revision_boundary_utc,
        ),
    ]

    migrated, _ = migration_module._migrate_publication_manifest(
        {
            "schema_version": 8,
            "workouts": {"planned-run": publication.model_dump(mode="json")},
        },
        authorities,
        migration_date=date(2026, 8, 11),
        fulfillment_manifest=WorkoutFulfillmentManifest(
            fulfillments={fulfillment.local_activity_id: fulfillment}
        ),
    )

    placement = migrated.workout_provider_occurrence_placements["planned-run"]
    assert placement.fulfillment_override is not None
    assert placement.fulfillment_override.local_activity_id == (fulfillment.local_activity_id)
    assert placement.effective_occurrence_date == date(2026, 7, 27)


def test_v8_migration_rejects_off_schedule_pending_without_fulfillment() -> None:
    publication = _publication()
    pending = PendingWorkoutPublication(
        workout_identity=publication.workout_identity,
        applied_week_approval_id=publication.applied_week_approval_id,
        applied_running_workouts_sha256=publication.applied_running_workouts_sha256,
        workout_prescription_sha256=publication.workout_prescription_sha256,
        schedule_timezone=publication.schedule_timezone,
        uid=publication.uid,
        external_id=publication.external_id,
        publication_fingerprint_sha256=publication.publication_fingerprint_sha256,
        rendered_workout_sha256=publication.rendered_workout_sha256,
        sport_settings_version_sha256=publication.sport_settings_version_sha256,
        sport="run",
        occurrence_date=publication.occurrence_date,
        approved_start_time_local=publication.approved_start_time_local,
        provider_start_date_local="2026-07-27T07:00:00",
        prepared_at_utc=publication.verified_at_utc,
    )

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="exact fulfillment placement authority",
    ):
        migration_module._migrate_publication_manifest(
            {
                "schema_version": 8,
                "pending": {"planned-run": pending.model_dump(mode="json")},
            },
            [_migration_authority()],
            migration_date=date(2026, 8, 11),
        )


def test_v8_publication_loader_reports_the_actionable_cutover_command(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    path = repo.resolve_path("data/state/workout_publications.json")
    path.parent.mkdir(parents=True)
    path.write_text('{"schema_version":8,"workouts":{},"pending":{}}')

    with pytest.raises(
        ValueError,
        match=r"resilio migrate workout-fulfillment-v2 --apply",
    ):
        load_manifest(repo)
