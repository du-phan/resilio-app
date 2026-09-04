import hashlib
import json
from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

import resilio.core.workout_fulfillment.migration as migration_module
from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import (
    archive_path,
    canonical_data_sha256,
    evidence_path,
    model_sha256,
)
from resilio.core.planning.assessment_context import create_assessment_planning_context
from resilio.core.planning.integrity import plan_skeleton_sha256
from resilio.core.planning.source_state import coaching_evidence_source_sha256
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.legacy_source_state import (
    legacy_coaching_evidence_source_sha256_unlocked,
)
from resilio.core.workout_fulfillment.migration import (
    migrate_workout_fulfillment_state,
)
from resilio.core.workout_fulfillment.migration_authority import (
    validate_migrated_fulfillment_authority,
)
from resilio.core.workout_fulfillment.planning_evidence_migration import (
    prepare_planning_evidence_migration,
)
from resilio.core.workout_fulfillment.planning_evidence_transform import (
    fulfillment_index,
    migrate_embedded_planning_contracts,
)
from resilio.core.workout_fulfillment.planning_proposal_migration import (
    PlanningProposalMigration,
    PlanningProposalMigrationError,
)
from resilio.core.workout_fulfillment.planning_state_migration import (
    PlanningEvidenceMigrationError,
    load_closed_archives,
    migrate_closed_plan_history,
)
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.preparation import rendered_workout_sha256
from resilio.schemas.approvals import (
    ActivePlanState,
    ClosedPlanArchive,
    ClosedPlanReference,
    OwnedBaselineAssessmentVDOTEvidence,
    PlanApproval,
    PlanningState,
    VDOTApproval,
    VDOTProposal,
)
from resilio.schemas.plan_history import (
    AssessmentClosure,
    DedicatedActivityAssessmentResult,
    PlanWorkoutIdentity,
)
from resilio.schemas.planning.plans import BaselineAssessmentPlan
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.planning_evidence import AssessmentPlanningContext
from resilio.schemas.profile import AthleteProfile, TrainingConstraints
from resilio.schemas.publication import PublicationManifest, RetiredWorkoutPublication
from resilio.schemas.workout_fulfillment import (
    HistoricalLegacyWorkoutFulfillment,
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from tests.factories import make_activity
from tests.unit.test_activity_sync import _publication
from tests.unit.test_baseline_assessment_contracts import _assessment_plan_payload


class _ChangedAssessmentReviewGraph:
    def validate_owned_assessment_evidence(
        self,
        _reference,
        _result,
        *,
        require_closed_archive,
    ):
        assert require_closed_archive
        pass

    def migrate(self, reference, **_kwargs):
        assert reference.artifact_type == "assessment_review"
        return reference.model_copy(update={"artifact_sha256": "f" * 64})


class _SourceReviewGraph:
    def __init__(self, source_payload):
        self.source_payload_value = source_payload
        self.blocked_cycle_review_keys: set[tuple[str, str]] = set()

    def migrate(self, reference, **_kwargs):
        return reference

    def source_payload(self, _reference):
        return self.source_payload_value


def _closed_assessment_archive(
    *,
    plan_id: str = "plan_august_assessment",
    plan_revision_id: str = "plan_revision_0123456789abcdef",
) -> ClosedPlanArchive:
    plan_payload = _assessment_plan_payload()
    plan_payload["id"] = plan_id
    plan_payload["plan_revision_id"] = plan_revision_id
    plan = BaselineAssessmentPlan.model_validate(plan_payload)
    active_plan = ActivePlanState(
        plan=plan,
        plan_approval=PlanApproval(
            approval_id="plan_approval_0123456789abcdef",
            plan_kind="baseline_assessment",
            plan_id=plan.id,
            plan_revision_id=plan.plan_revision_id,
            plan_skeleton_sha256=plan_skeleton_sha256(plan),
            planning_inputs_sha256=plan.planning_inputs_sha256,
            approved_at_utc=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        ),
    )
    return ClosedPlanArchive(
        active_plan_snapshot=active_plan,
        closure=AssessmentClosure(
            effective_end_date=date(2026, 8, 20),
            reason="The athlete completed and confirmed the baseline assessment.",
            athlete_confirmation_reference=(
                "Athlete approved closing this exact baseline assessment."
            ),
            assessment_review_artifact_sha256="c" * 64,
            closed_at_utc=datetime(2026, 8, 20, 19, tzinfo=timezone.utc),
        ),
    )


def _closed_reference(archive: ClosedPlanArchive) -> ClosedPlanReference:
    plan = archive.active_plan_snapshot.plan
    return ClosedPlanReference(
        plan_id=plan.id,
        plan_revision_id=plan.plan_revision_id,
        archive_sha256=model_sha256(archive),
        closed_at_utc=archive.closure.closed_at_utc,
    )


def test_planning_migration_rejects_review_misbound_to_source_archive(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    archive = _closed_assessment_archive()
    plan = archive.active_plan_snapshot.plan
    source_review = {
        "plan_id": plan.id,
        "plan_revision_id": plan.plan_revision_id,
        "active_plan_sha256": "f" * 64,
        "benchmark_intent": plan.benchmark_intent.model_dump(mode="json"),
        "result": {"performance_date": "2026-08-20"},
    }
    graph = _SourceReviewGraph(source_review)
    state = PlanningState(closed_plan_references=[_closed_reference(archive)])

    with pytest.raises(
        PlanningEvidenceMigrationError,
        match="did not match its source plan",
    ):
        migrate_closed_plan_history(
            state,
            [archive],
            graph,
            PlanningProposalMigration(repo, graph),
            [],
        )


def test_planning_migration_rejects_changed_closed_archive_bytes(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    archive = _closed_assessment_archive()
    plan = archive.active_plan_snapshot.plan
    path = repo.resolve_path(archive_path(plan.id))
    path.parent.mkdir(parents=True)
    path.write_text(archive.model_dump_json())
    reference = _closed_reference(archive).model_copy(update={"archive_sha256": "f" * 64})

    with pytest.raises(
        PlanningEvidenceMigrationError,
        match="missing, changed, or invalid",
    ):
        load_closed_archives(
            repo,
            PlanningState(closed_plan_references=[reference]),
        )


def test_planning_transform_does_not_backdate_late_recorded_fulfillment() -> None:
    authority = _authority()
    record = WorkoutFulfillmentRecord(
        local_activity_id="activity_recorded_later",
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256="2" * 64,
        activity_performance_evidence_sha256="3" * 64,
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=date(2026, 7, 28),
        execution_local_date=date(2026, 7, 28),
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=42,
            observed_at_utc=datetime(2026, 7, 30, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    weekly_context = {
        "as_of_date": "2026-07-29",
        "activities": [],
        "adherence": {
            "planned_workout_count": 1,
            "due_workout_count": 1,
            "verified_completed_workout_count": 1,
            "due_unmatched_workout_count": 0,
            "workouts": [
                {
                    "workout_identity": authority.identity.model_dump(mode="json"),
                    "occurrence_date": "2026-07-28",
                    "is_due": True,
                    "matched_local_activity_id": record.local_activity_id,
                }
            ],
        },
    }

    migrate_embedded_planning_contracts(
        weekly_context,
        evidence_by_identity=fulfillment_index(
            WorkoutFulfillmentManifest(fulfillments={record.local_activity_id: record})
        ),
    )

    adherence = weekly_context["adherence"]
    assert adherence["fulfilled_workout_count"] == 0
    assert adherence["due_fulfilled_workout_count"] == 0
    assert adherence["due_unfulfilled_workout_count"] == 1
    assert adherence["workouts"][0]["matched_local_activity_id"] is None


def _authority() -> AuthoritativeWorkout:
    workout = RunningWorkoutPrescription.model_validate(
        {
            "id": "planned-run",
            "date": "2026-07-28",
            "workout_type": "easy",
            "planned_duration_seconds": 2_400,
            "planned_distance_meters": 5_000,
            "planned_low_intensity_duration_seconds": 2_400,
            "planned_moderate_intensity_duration_seconds": 0,
            "planned_high_intensity_duration_seconds": 0,
            "target_rpe_1_to_10": 3,
            "purpose": "Complete one conversational five-kilometre run.",
            "structured_workout": {
                "sport": "run",
                "steps": [
                    {
                        "kind": "steady",
                        "duration": {"unit": "seconds", "value": 2_400},
                        "intensity": "active",
                    }
                ],
            },
        }
    )
    return AuthoritativeWorkout(
        identity=PlanWorkoutIdentity(
            plan_id="plan_test",
            plan_revision_id="plan_revision_1111111111111111",
            week_number=1,
            local_workout_id="planned-run",
        ),
        prescription=workout,
        applied_week_approval_id="week_approval_0123456789abcdef",
        applied_running_workouts_sha256="1" * 64,
        schedule_timezone="Europe/Paris",
    )


def test_external_assessment_vdot_approval_is_rebound_to_an_audited_managed_copy(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    result = DedicatedActivityAssessmentResult(
        workout_identity=PlanWorkoutIdentity(
            plan_id="plan_assessment",
            plan_revision_id="plan_revision_1111111111111111",
            week_number=3,
            local_workout_id="benchmark",
        ),
        local_activity_id="benchmark_activity",
        performance_evidence_sha256="a" * 64,
        race_distance="5k",
        performance_date=date(2026, 8, 20),
        performance_timezone="Europe/Paris",
        measured_distance_meters=5_000,
        elapsed_time_seconds=1_500,
        official_distance_confirmation_reference="Athlete confirmed five kilometres.",
        athlete_confirmation_reference="Athlete confirmed this assessment result.",
    )
    proposal = VDOTProposal(
        proposed_vdot=40,
        evidence=OwnedBaselineAssessmentVDOTEvidence(
            evidence_type="owned_baseline_assessment",
            race_distance="5k",
            elapsed_time_seconds=1_500,
            performance_date=date(2026, 8, 20),
            performance_timezone="Europe/Paris",
            assessment_review_sha256="e" * 64,
            result=result,
        ),
        evidence_summary=("The athlete-approved VDOT uses the exact closed baseline assessment."),
        generated_at_utc=datetime(2026, 8, 21, 8, tzinfo=timezone.utc),
    )
    source_path = tmp_path / "external-approved-vdot.json"
    source_bytes = proposal.model_dump_json(indent=2).encode()
    source_path.write_bytes(source_bytes)
    approval = VDOTApproval(
        approval_id="vdot_approval_1111111111111111",
        approved_vdot=40,
        proposal_file=str(source_path),
        proposal_file_sha256=hashlib.sha256(source_bytes).hexdigest(),
        evidence_type="owned_baseline_assessment",
        proposal_snapshot=proposal,
        approved_at_utc=datetime(2026, 8, 21, 9, tzinfo=timezone.utc),
    )
    migration = PlanningProposalMigration(repo, _ChangedAssessmentReviewGraph())

    migrated = migration.migrate_vdot_approval(approval)

    assert source_path.read_bytes() == source_bytes
    assert migrated.proposal_file != str(source_path)
    assert migrated.proposal_file_sha256 != approval.proposal_file_sha256
    assert isinstance(
        migrated.proposal_snapshot.evidence,
        OwnedBaselineAssessmentVDOTEvidence,
    )
    assert migrated.proposal_snapshot.evidence.assessment_review_sha256 == "f" * 64
    managed_relative_path = next(iter(migration.rewritten_bytes_by_relative_path))
    assert managed_relative_path.startswith("data/plans/proposals/")
    assert migration.file_migrations == [
        (
            str(source_path),
            managed_relative_path,
            approval.proposal_file_sha256,
            migrated.proposal_file_sha256,
        )
    ]
    managed_path = repo.resolve_path(managed_relative_path)
    managed_path.parent.mkdir(parents=True, exist_ok=True)
    managed_path.write_text('{"unrelated":"user-owned"}\n')
    with pytest.raises(PlanningProposalMigrationError, match="different bytes"):
        PlanningProposalMigration(
            repo,
            _ChangedAssessmentReviewGraph(),
        ).migrate_vdot_approval(approval)


def _migration_authority() -> migration_module._MigrationWorkoutAuthority:
    return migration_module._MigrationWorkoutAuthority(
        workout=_authority(),
        valid_from_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
        valid_until_utc=None,
        plan_approved_at_utc=datetime(2026, 7, 25, tzinfo=timezone.utc),
        weekly_approved_at_utc=datetime(2026, 7, 25, tzinfo=timezone.utc),
        effective_end_date=date(2026, 8, 2),
        retired_at_utc=None,
    )


def _legacy_published_payload(workout_id: str = "planned-run") -> dict[str, object]:
    payload = _publication(workout_id=workout_id).model_dump(mode="json")
    for field_name in (
        "applied_week_approval_id",
        "applied_running_workouts_sha256",
        "workout_prescription_sha256",
        "schedule_timezone",
    ):
        payload.pop(field_name)
    if workout_id == "planned-run":
        payload["rendered_workout_sha256"] = rendered_workout_sha256(_authority().prescription)
    return payload


def test_migration_is_dry_run_first_then_backs_up_and_applies(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    activity = make_activity(
        id="act_paired",
        date=date(2026, 7, 28),
        start_time=datetime(2026, 7, 28, 6, tzinfo=timezone.utc),
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    publication_payload = {
        "schema_version": 6,
        "workouts": {"planned-run": _legacy_published_payload()},
        "pending": {},
        "drift_resolutions": [],
    }
    publication_path = repo.resolve_path("data/state/workout_publications.json")
    publication_path.parent.mkdir(parents=True)
    publication_path.write_text(json.dumps(publication_payload))
    completion_path = repo.resolve_path("data/state/workout_completions.json")
    completion_path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "matches": {
                    activity.local_activity_id: {
                        "local_activity_id": activity.local_activity_id,
                        "workout_identity": _authority().identity.model_dump(mode="json"),
                        "match_method": "paired_event_id",
                        "matched_at_utc": "2026-07-28T09:00:00Z",
                    }
                },
            }
        )
    )
    original_publication_bytes = publication_path.read_bytes()
    original_completion_bytes = completion_path.read_bytes()
    monkeypatch.setattr(
        "resilio.core.workout_fulfillment.migration._load_authorities_unlocked",
        lambda _repo: [_migration_authority()],
    )
    monkeypatch.setattr(
        "resilio.core.workout_fulfillment.migration._athlete_local_migration_date",
        lambda _repo: date(2026, 8, 10),
    )

    dry_run = migrate_workout_fulfillment_state(repo, apply=False)

    assert dry_run.changes_required
    assert not dry_run.applied
    assert dry_run.active_publication_count == 1
    assert dry_run.historical_publication_count == 0
    assert dry_run.active_fulfillment_count == 1
    assert dry_run.historical_fulfillment_count == 0
    assert publication_path.read_bytes() == original_publication_bytes
    assert completion_path.read_bytes() == original_completion_bytes

    real_save_manifest = migration_module.save_manifest

    def fail_publication_write(*_args, **_kwargs):
        raise OSError("simulated publication write failure")

    monkeypatch.setattr(migration_module, "save_manifest", fail_publication_write)
    with pytest.raises(OSError, match="simulated publication write failure"):
        migrate_workout_fulfillment_state(repo, apply=True)
    assert publication_path.read_bytes() == original_publication_bytes
    assert completion_path.read_bytes() == original_completion_bytes
    assert not repo.resolve_path("data/state/workout_fulfillments.json").exists()
    monkeypatch.setattr(migration_module, "save_manifest", real_save_manifest)

    applied = migrate_workout_fulfillment_state(repo, apply=True)

    assert applied.applied
    assert applied.backup_relative_path is not None
    assert not completion_path.exists()
    assert load_manifest(repo).schema_version == 8
    fulfillment = load_fulfillment_manifest(repo).fulfillments[activity.local_activity_id]
    assert fulfillment.fulfillment_basis == "provider_paired"
    assert fulfillment.provider_pair is not None
    assert fulfillment.provider_pair.event_id == 42
    backup_root = repo.resolve_path(applied.backup_relative_path)
    backup_files = {path.name for path in backup_root.iterdir()}
    assert any(name.endswith("-workout_publications.json") for name in backup_files)
    assert any(name.endswith("-workout_completions.json") for name in backup_files)


def test_migration_rewrites_standalone_planning_evidence_once(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    ProfileRepository(repo).create(
        AthleteProfile(
            athlete_name="Alex",
            created_on=date(2026, 8, 1),
            training_timezone="Europe/Paris",
            constraints=TrainingConstraints(
                minimum_run_days_per_week=2,
                maximum_run_days_per_week=3,
            ),
        )
    )
    current_reference = create_assessment_planning_context(
        repo,
        evidence_as_of_date=date(2026, 8, 9),
        intended_plan_start_date=date(2026, 8, 10),
        assessment_reasons=["missing_baseline"],
        generated_at_utc=datetime(2026, 8, 9, 12, tzinfo=timezone.utc),
        current_local_date=date(2026, 8, 9),
    )
    current_path = repo.resolve_path(evidence_path(current_reference))
    legacy_payload = json.loads(current_path.read_text())
    for weekly_context in legacy_payload["recent_detailed_weeks"]:
        weekly_context.pop("schema_version")
        adherence = weekly_context["adherence"]
        adherence.pop("schema_version")
        adherence["verified_completed_workout_count"] = adherence.pop("due_fulfilled_workout_count")
        adherence["due_unmatched_workout_count"] = adherence.pop("due_unfulfilled_workout_count")
        adherence.pop("fulfilled_workout_count")
        adherence.pop("fulfilled_early_workout_count")
        adherence.pop("fulfilled_late_workout_count")
    legacy_payload["source_state_sha256"] = legacy_coaching_evidence_source_sha256_unlocked(
        repo,
        evidence_as_of_date=date(2026, 8, 9),
        evidence_window_start=None,
        legacy_completion_raw=None,
        legacy_publication_raw=None,
    )
    legacy_bytes = (
        json.dumps(
            legacy_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode()
    legacy_sha256 = hashlib.sha256(legacy_bytes).hexdigest()
    legacy_path = current_path.with_name(f"{legacy_sha256}.json")
    legacy_path.write_bytes(legacy_bytes)
    current_path.unlink()

    stale_activity = make_activity(
        id="activity_added_after_context",
        date=date(2026, 8, 8),
    )
    stale_activity_path = ActivityArchive(repo.resolve_path("data/activities")).write(
        stale_activity
    )
    stale_migration = prepare_planning_evidence_migration(
        repo,
        fulfillment_manifest=WorkoutFulfillmentManifest(),
        publication_manifest=PublicationManifest(),
    )
    stale_artifact = next(iter(stale_migration.new_artifacts_by_relative_path.values()))
    assert isinstance(stale_artifact, AssessmentPlanningContext)
    assert stale_artifact.source_state_sha256 != coaching_evidence_source_sha256(
        repo,
        evidence_as_of_date=stale_artifact.evidence_as_of_date,
    )
    stale_activity_path.unlink()

    dry_run = migrate_workout_fulfillment_state(repo, apply=False)
    assert dry_run.migrated_planning_artifact_count == 1
    assert legacy_path.exists()

    applied = migrate_workout_fulfillment_state(repo, apply=True)
    assert applied.applied
    assert not legacy_path.exists()
    migrated_paths = list(legacy_path.parent.glob("*.json"))
    assert len(migrated_paths) == 1
    migrated_context = AssessmentPlanningContext.model_validate_json(migrated_paths[0].read_text())
    assert migrated_context.source_state_sha256 == coaching_evidence_source_sha256(
        repo,
        evidence_as_of_date=migrated_context.evidence_as_of_date,
    )

    repeated = migrate_workout_fulfillment_state(repo, apply=True)
    assert not repeated.changes_required
    assert not repeated.applied


def test_migration_preserves_historical_ownership_without_fabricating_authority(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    active_activity = make_activity(
        id="active_pair",
        date=date(2026, 7, 28),
        start_time=datetime(2026, 7, 28, 6, tzinfo=timezone.utc),
    )
    historical_activity = make_activity(
        id="historical_pair",
        date=date(2026, 7, 27),
        start_time=datetime(2026, 7, 27, 6, tzinfo=timezone.utc),
    )
    archive = ActivityArchive(repo.resolve_path("data/activities"))
    archive.write(active_activity)
    archive.write(historical_activity)
    historical_publication = _legacy_published_payload("historical-run")
    historical_publication["event_id"] = 43
    historical_publication["occurrence_date"] = "2026-07-27"
    historical_publication["provider_start_date_local"] = "2026-07-27T07:00:00"
    publication_raw = {
        "schema_version": 6,
        "workouts": {
            "planned-run": _legacy_published_payload(),
            "historical-run": historical_publication,
        },
        "pending": {},
        "drift_resolutions": [],
    }

    publication_manifest, changed = migration_module._migrate_publication_manifest(
        publication_raw,
        [_migration_authority()],
        migration_date=date(2026, 8, 10),
    )
    completion_raw = {
        "schema_version": 3,
        "matches": {
            "active_pair": {
                "local_activity_id": "active_pair",
                "workout_identity": _authority().identity.model_dump(mode="json"),
                "match_method": "paired_event_id",
                "matched_at_utc": "2026-07-28T09:00:00Z",
            },
            "historical_pair": {
                "local_activity_id": "historical_pair",
                "workout_identity": historical_publication["workout_identity"],
                "match_method": "paired_event_id",
                "matched_at_utc": "2026-07-27T09:00:00Z",
            },
        },
    }
    fulfillment_manifest = migration_module._migrate_fulfillment_manifest(
        repo,
        completion_raw,
        publication_manifest,
        [_migration_authority()],
    )

    assert changed
    assert set(publication_manifest.workouts) == {"planned-run"}
    assert set(publication_manifest.historical_legacy_workouts) == {"historical-run"}
    assert set(fulfillment_manifest.fulfillments) == {"active_pair"}
    assert set(fulfillment_manifest.historical_legacy_fulfillments) == {"historical_pair"}


def test_migration_rejects_completion_superseded_before_schedule_deadline(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    activity = make_activity(
        id="active_pair",
        date=date(2026, 7, 28),
        start_time=datetime(2026, 7, 28, 6, tzinfo=timezone.utc),
    )
    ActivityArchive(repo.resolve_path("data/activities")).write(activity)
    first_authority = migration_module._MigrationWorkoutAuthority(
        workout=_authority(),
        valid_from_utc=datetime(2026, 7, 26, tzinfo=timezone.utc),
        valid_until_utc=datetime(2026, 7, 27, 12, tzinfo=timezone.utc),
        plan_approved_at_utc=datetime(2026, 7, 25, tzinfo=timezone.utc),
        weekly_approved_at_utc=datetime(2026, 7, 25, tzinfo=timezone.utc),
        effective_end_date=date(2026, 8, 2),
        retired_at_utc=None,
    )
    replacement_workout = _authority().prescription.model_copy(
        update={"purpose": "Complete the materially revised approved running session."}
    )
    replacement_authority = migration_module._MigrationWorkoutAuthority(
        workout=AuthoritativeWorkout(
            identity=_authority().identity,
            prescription=replacement_workout,
            applied_week_approval_id="week_approval_fedcba9876543210",
            applied_running_workouts_sha256="4" * 64,
            schedule_timezone="Europe/Paris",
        ),
        valid_from_utc=datetime(2026, 7, 27, 12, tzinfo=timezone.utc),
        valid_until_utc=None,
        plan_approved_at_utc=datetime(2026, 7, 25, tzinfo=timezone.utc),
        weekly_approved_at_utc=datetime(2026, 7, 27, 11, tzinfo=timezone.utc),
        effective_end_date=date(2026, 8, 2),
        retired_at_utc=None,
    )
    publication_manifest, _ = migration_module._migrate_publication_manifest(
        {
            "schema_version": 6,
            "workouts": {"planned-run": _legacy_published_payload()},
            "pending": {},
            "drift_resolutions": [],
        },
        [first_authority, replacement_authority],
        migration_date=date(2026, 8, 10),
    )
    completion_raw = {
        "schema_version": 3,
        "matches": {
            activity.local_activity_id: {
                "local_activity_id": activity.local_activity_id,
                "workout_identity": _authority().identity.model_dump(mode="json"),
                "match_method": "paired_event_id",
                "matched_at_utc": "2026-07-28T09:00:00Z",
            }
        },
    }

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="schedule-time workout authority",
    ):
        migration_module._migrate_fulfillment_manifest(
            repo,
            completion_raw,
            publication_manifest,
            [first_authority, replacement_authority],
        )


def test_migration_rejects_fulfillment_after_plan_closure_authority() -> None:
    authority = _authority()
    fulfillment = WorkoutFulfillmentRecord(
        local_activity_id="active_pair",
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        activity_performance_evidence_sha256="3" * 64,
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=authority.prescription.date,
        execution_local_date=authority.prescription.date,
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=42,
            observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    )
    closed_authority = replace(
        _migration_authority(),
        effective_end_date=date(2026, 7, 27),
        retired_at_utc=datetime(2026, 7, 27, 20, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="schedule-time workout authority"):
        validate_migrated_fulfillment_authority(
            fulfillment,
            [closed_authority],
        )


@pytest.mark.parametrize("timestamp", ["2026-07-28T09:00:00", "not-a-time"])
def test_migration_rejects_ambiguous_legacy_timestamps(timestamp: str) -> None:
    publication = _legacy_published_payload()
    publication["verified_at_utc"] = timestamp

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="authority observation time|timezone-aware|version 6 contract",
    ):
        migration_module._migrate_publication_manifest(
            {
                "schema_version": 6,
                "workouts": {"planned-run": publication},
                "pending": {},
                "drift_resolutions": [],
            },
            [_migration_authority()],
            migration_date=date(2026, 8, 10),
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.update({"unexpected": True}),
        lambda raw: raw["matches"]["activity-1"].update({"unexpected": True}),
        lambda raw: raw["matches"]["activity-1"].update(
            {"local_activity_id": "different-activity"}
        ),
        lambda raw: raw["matches"].update(
            {
                "activity-2": {
                    **raw["matches"]["activity-1"],
                    "local_activity_id": "activity-2",
                }
            }
        ),
    ],
)
def test_migration_rejects_completion_v3_contract_corruption(
    tmp_path,
    monkeypatch,
    mutate,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    raw = {
        "schema_version": 3,
        "matches": {
            "activity-1": {
                "local_activity_id": "activity-1",
                "workout_identity": _authority().identity.model_dump(mode="json"),
                "match_method": "paired_event_id",
                "matched_at_utc": "2026-07-28T09:00:00Z",
            }
        },
    }
    mutate(raw)

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="version 3 contract",
    ):
        migration_module._migrate_fulfillment_manifest(
            RepositoryIO(),
            raw,
            PublicationManifest(),
            [],
        )


def test_migration_preserves_published_plus_pending_recovery_state() -> None:
    published = _legacy_published_payload()
    pending = {
        field_name: published[field_name]
        for field_name in (
            "workout_identity",
            "uid",
            "external_id",
            "publication_fingerprint_sha256",
            "rendered_workout_sha256",
            "sport_settings_version_sha256",
            "sport",
            "occurrence_date",
            "approved_start_time_local",
            "provider_start_date_local",
        )
    }
    pending["prepared_at_utc"] = "2026-07-27T00:00:00Z"

    migrated, _ = migration_module._migrate_publication_manifest(
        {
            "schema_version": 6,
            "workouts": {"planned-run": published},
            "pending": {"planned-run": pending},
            "drift_resolutions": [],
        },
        [_migration_authority()],
        migration_date=date(2026, 8, 10),
    )

    assert "planned-run" in migrated.workouts
    assert "planned-run" in migrated.pending
def test_v7_early_retirement_becomes_historical_audit_for_native_pairing() -> None:
    publication = _publication()
    retired = RetiredWorkoutPublication(
        publication=publication,
        fulfilling_local_activity_id="activity-1",
        fulfillment_record_sha256_at_retirement="f" * 64,
        execution_local_date_at_retirement=date(2026, 7, 27),
        schedule_offset_days_at_retirement=-1,
        provider_deletion_status="deleted",
        retired_at_utc=datetime(2026, 7, 27, 12, tzinfo=timezone.utc),
    )

    migrated, changed = migration_module._migrate_publication_manifest(
        {
            "schema_version": 7,
            "retired": {"planned-run": retired.model_dump(mode="json")},
        },
        [],
        migration_date=date(2026, 8, 11),
    )

    assert changed is True
    assert migrated.schema_version == 8
    assert migrated.historical_fulfillment_event_retirements == [retired]


def test_v7_migration_rejects_duplicate_confirmed_drift_targets() -> None:
    target = {
        "local_workout_id": "planned-run",
        "event_id": 42,
        "observed_remote_fingerprint_sha256": "a" * 64,
    }
    raw = {
        "schema_version": 7,
        "drift_resolutions": [
            {
                "plan_id": "plan-1",
                "plan_revision_id": "plan_revision_0123456789abcdef",
                "week_number": 1,
                "strategy": "retire_fulfilled",
                "confirmed_targets": [target, target],
                "athlete_confirmation_reference": "Exact duplicate source evidence.",
                "confirmed_at_utc": "2026-08-10T09:00:00Z",
            }
        ],
    }

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="version 7 contract",
    ):
        migration_module._migrate_publication_manifest(
            raw,
            [],
            migration_date=date(2026, 8, 11),
        )


def _v1_active_fulfillment_migration_inputs():
    authority = _authority()
    record = WorkoutFulfillmentRecord(
        local_activity_id="activity-1",
        workout_identity=authority.identity,
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        activity_performance_evidence_sha256="a" * 64,
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=authority.prescription.date,
        execution_local_date=authority.prescription.date,
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=42,
            observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
        ),
        recorded_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    )
    raw = WorkoutFulfillmentManifest(
        fulfillments={record.local_activity_id: record}
    ).model_dump(mode="json")
    raw["schema_version"] = 1
    raw.pop("remote_pairing_operations")
    raw.pop("remote_pairing_drift_resolutions")
    raw["fulfillments"]["activity-1"]["provider_pair"].pop("provenance")

    publication = _publication().model_copy(
        update={
            "workout_identity": authority.identity,
            "applied_week_approval_id": authority.applied_week_approval_id,
            "applied_running_workouts_sha256": (
                authority.applied_running_workouts_sha256
            ),
            "workout_prescription_sha256": canonical_data_sha256(
                authority.prescription
            ),
            "schedule_timezone": authority.schedule_timezone,
            "occurrence_date": authority.prescription.date,
        }
    )
    publication_manifest = PublicationManifest(workouts={"planned-run": publication})
    migration_authority = _migration_authority()
    activity = make_activity(id="activity-1", date=authority.prescription.date)
    activity = activity.model_copy(
        update={
            "audit": activity.audit.model_copy(
                update={
                    "performance_evidence_sha256": "a" * 64,
                    "provider_snapshot_sha256": "f" * 64,
                    "canonical_mapping_version": 9,
                }
            )
        }
    )
    activities_by_local_id = {activity.local_activity_id: activity}
    return (
        raw,
        publication_manifest,
        [migration_authority],
        activities_by_local_id,
    )


def test_fulfillment_v1_migrates_exact_pair_provenance_and_is_idempotent() -> None:
    (
        raw,
        publication_manifest,
        authorities,
        activities_by_local_id,
    ) = _v1_active_fulfillment_migration_inputs()
    migrated, changed = migration_module._migrate_current_fulfillment_manifest(
        raw,
        publication_manifest,
        authorities,
        activities_by_local_id,
    )
    repeated, repeated_changed = migration_module._migrate_current_fulfillment_manifest(
        migrated.model_dump(mode="json"),
        publication_manifest,
        authorities,
        activities_by_local_id,
    )

    assert changed is True
    assert migrated.schema_version == 2
    assert migrated.fulfillments["activity-1"].provider_pair is not None
    assert migrated.fulfillments["activity-1"].provider_pair.provenance == "provider_observed"
    assert migrated.remote_pairing_operations == {}
    assert repeated == migrated
    assert repeated_changed is False


def test_current_publication_may_retain_an_earlier_fulfillment_authority() -> None:
    raw, publication_manifest, _, activities = _v1_active_fulfillment_migration_inputs()
    original = _migration_authority()
    replacement_time = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)
    original = replace(original, valid_until_utc=replacement_time)
    replacement_workout = replace(
        original.workout,
        applied_week_approval_id="week_approval_1111111111111111",
        applied_running_workouts_sha256="2" * 64,
    )
    replacement = replace(
        original,
        workout=replacement_workout,
        valid_from_utc=replacement_time,
        valid_until_utc=None,
        weekly_approved_at_utc=replacement_time,
    )
    publication = publication_manifest.workouts["planned-run"].model_copy(
        update={
            "applied_week_approval_id": replacement_workout.applied_week_approval_id,
            "applied_running_workouts_sha256": (
                replacement_workout.applied_running_workouts_sha256
            ),
        }
    )

    migrated, _ = migration_module._migrate_current_fulfillment_manifest(
        raw,
        PublicationManifest(workouts={"planned-run": publication}),
        [original, replacement],
        activities,
    )

    assert (
        migrated.fulfillments["activity-1"].applied_week_approval_id
        == original.workout.applied_week_approval_id
    )


def test_current_publication_replacement_requires_retained_authority() -> None:
    raw, publication_manifest, authorities, activities = (
        _v1_active_fulfillment_migration_inputs()
    )
    publication = publication_manifest.workouts["planned-run"].model_copy(
        update={
            "applied_week_approval_id": "week_approval_1111111111111111",
            "applied_running_workouts_sha256": "2" * 64,
        }
    )

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="exact publication authority",
    ):
        migration_module._migrate_current_fulfillment_manifest(
            raw,
            PublicationManifest(workouts={"planned-run": publication}),
            authorities,
            activities,
        )


def test_fulfillment_recorded_before_same_day_closure_retains_authority() -> None:
    raw, publication_manifest, _, activities = _v1_active_fulfillment_migration_inputs()
    authority = replace(
        _migration_authority(),
        effective_end_date=date(2026, 7, 28),
        retired_at_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc),
    )

    migrated, _ = migration_module._migrate_current_fulfillment_manifest(
        raw,
        publication_manifest,
        [authority],
        activities,
    )

    assert "activity-1" in migrated.fulfillments


def test_fulfillment_recorded_after_same_day_closure_is_rejected() -> None:
    raw, publication_manifest, _, activities = _v1_active_fulfillment_migration_inputs()
    raw["fulfillments"]["activity-1"]["provider_pair"]["observed_at_utc"] = (
        "2026-07-28T11:00:00Z"
    )
    raw["fulfillments"]["activity-1"]["recorded_at_utc"] = "2026-07-28T11:00:00Z"
    authority = replace(
        _migration_authority(),
        effective_end_date=date(2026, 7, 28),
        retired_at_utc=datetime(2026, 7, 28, 10, tzinfo=timezone.utc),
    )

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="schedule-time workout authority",
    ):
        migration_module._migrate_current_fulfillment_manifest(
            raw,
            publication_manifest,
            [authority],
            activities,
        )


def test_fulfillment_v1_rejects_provider_pair_for_a_different_owned_event() -> None:
    raw, publication_manifest, authorities, activities = (
        _v1_active_fulfillment_migration_inputs()
    )
    raw["fulfillments"]["activity-1"]["provider_pair"]["event_id"] = 999

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="exact publication authority",
    ):
        migration_module._migrate_current_fulfillment_manifest(
            raw,
            publication_manifest,
            authorities,
            activities,
        )


def test_fulfillment_v1_rejects_active_fulfillment_without_current_activity() -> None:
    raw, publication_manifest, authorities, _ = (
        _v1_active_fulfillment_migration_inputs()
    )

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="exact current running-activity evidence",
    ):
        migration_module._migrate_current_fulfillment_manifest(
            raw,
            publication_manifest,
            authorities,
            {},
        )


def test_fulfillment_v1_rejects_historical_pair_without_exact_publication() -> None:
    activity = make_activity(id="activity-historical", date=date(2026, 7, 28))
    activity = activity.model_copy(
        update={
            "audit": activity.audit.model_copy(
                update={
                    "performance_evidence_sha256": "a" * 64,
                    "provider_snapshot_sha256": "f" * 64,
                    "canonical_mapping_version": 9,
                }
            )
        }
    )
    historical = HistoricalLegacyWorkoutFulfillment(
        local_activity_id=activity.local_activity_id,
        workout_identity=_authority().identity,
        activity_performance_evidence_sha256="a" * 64,
        scheduled_local_date=date(2026, 7, 28),
        execution_local_date=date(2026, 7, 28),
        schedule_offset_days=0,
        provider_pair=ProviderPairedFulfillmentEvidence(
            event_id=42,
            provenance="provider_observed",
            observed_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
        ),
        matched_at_utc=datetime(2026, 7, 28, 9, tzinfo=timezone.utc),
    )
    raw = WorkoutFulfillmentManifest(
        historical_legacy_fulfillments={activity.local_activity_id: historical}
    ).model_dump(mode="json")
    raw["schema_version"] = 1
    raw.pop("remote_pairing_operations")
    raw.pop("remote_pairing_drift_resolutions")
    raw["historical_legacy_fulfillments"][activity.local_activity_id][
        "provider_pair"
    ].pop("provenance")

    with pytest.raises(
        migration_module.WorkoutFulfillmentMigrationError,
        match="exact legacy publication authority",
    ):
        migration_module._migrate_current_fulfillment_manifest(
            raw,
            PublicationManifest(),
            [],
            {activity.local_activity_id: activity},
        )
