"""One-shot activity-v5 and wellness-v2 migration tests."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.evidence_migration.service import migrate_evidence_state
from resilio.core.evidence_migration.transform import (
    invalidate_stale_activity_mapping,
    transform_activity_v4,
    transform_wellness_v1,
)
from resilio.core.repository import RepositoryIO
from resilio.core.training_state_repository import load_wellness
from resilio.schemas.activity import ActivityFeedback
from tests.factories import make_activity


def _activity_v4_payload(*, historical: bool) -> dict:
    activity = make_activity(
        id="historical-1" if historical else "act_i_provider_1",
        date=date(2026, 8, 6),
        description="The source description must survive.",
        private_note="The existing private note must survive.",
    )
    payload = activity.model_dump(mode="json", by_alias=True)
    payload["_schema"]["version"] = 4
    feedback = payload.pop("feedback")
    payload["notes"] = {
        "description": feedback["provider_description"],
        "private_note": feedback["local_private_note"],
    }
    payload["subjective_effort"] = feedback["subjective_effort"]
    payload.pop("execution_summary")
    payload["audit"] = {
        **payload["audit"],
        "external_fingerprint_sha256": "a" * 64,
        "canonical_mapping_version": 7,
    }
    payload["audit"].pop("provider_snapshot_sha256", None)
    payload["audit"].pop("performance_evidence_sha256", None)
    if not historical:
        payload["origin"] = {
            **payload["origin"],
            "kind": "intervals_icu",
            "intervals_icu_activity_id": "i-provider-1",
        }
    return payload


def test_historical_description_is_preserved_as_local_feedback() -> None:
    migrated = transform_activity_v4(_activity_v4_payload(historical=True))

    assert migrated.feedback == ActivityFeedback(
        local_private_note=(
            "The source description must survive.\n\n" "The existing private note must survive."
        )
    )
    assert migrated.audit.provider_snapshot_sha256 is None
    assert migrated.audit.performance_evidence_sha256 is None


def test_provider_description_retains_provider_ownership() -> None:
    migrated = transform_activity_v4(_activity_v4_payload(historical=False))

    assert migrated.feedback.provider_description == ("The source description must survive.")
    assert migrated.feedback.local_private_note == ("The existing private note must survive.")


def test_stale_v5_mapping_hashes_are_invalidated_for_provider_remapping() -> None:
    payload = make_activity(
        id="act_i_provider_1",
        date=date(2026, 8, 6),
    ).model_dump(mode="json", by_alias=True)
    payload["origin"] = {
        **payload["origin"],
        "kind": "intervals_icu",
        "intervals_icu_activity_id": "i-provider-1",
    }
    payload["audit"] = {
        **payload["audit"],
        "provider_snapshot_sha256": "a" * 64,
        "performance_evidence_sha256": "b" * 64,
        "canonical_mapping_version": 8,
    }

    migrated = invalidate_stale_activity_mapping(payload)

    assert migrated.audit.provider_snapshot_sha256 is None
    assert migrated.audit.performance_evidence_sha256 is None
    assert migrated.audit.canonical_mapping_version is None


def test_wellness_v1_receives_explicit_schema_and_mapping_versions() -> None:
    migrated = transform_wellness_v1(
        {
            "local_date": "2026-08-06",
            "fitness_load_points": 4,
            "fatigue_load_points": 3,
            "resting_hr_is_temporary": False,
            "source": "intervals_icu",
        }
    )

    assert migrated.schema_version == 2
    assert migrated.mapping_version == 2


def _write_legacy_state(repo: RepositoryIO, root: Path) -> Path:
    activity_path = root / "data/activities/2026-08/historical-1.yaml"
    repo.write_yaml(activity_path, _activity_v4_payload(historical=True))
    repo.write_json(
        "data/wellness/2026-08.json",
        [
            {
                "local_date": "2026-08-06",
                "fitness_load_points": 4,
                "fatigue_load_points": 3,
                "resting_hr_is_temporary": False,
                "source": "intervals_icu",
            }
        ],
    )
    return activity_path


def test_dry_run_is_read_only_and_apply_is_validated_and_backed_up(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    activity_path = _write_legacy_state(repo, tmp_path)
    activity_before = activity_path.read_bytes()

    dry_run = migrate_evidence_state(repo, apply=False)

    assert dry_run.activity_count == 1
    assert activity_path.read_bytes() == activity_before
    assert not (tmp_path / "data/backups/evidence-v5").exists()

    applied = migrate_evidence_state(repo, apply=True)

    assert applied.applied is True
    assert ActivityArchive(tmp_path / "data/activities").load("historical-1") is not None
    assert load_wellness(repo)[date(2026, 8, 6)].schema_version == 2
    backup_root = tmp_path / applied.backup_relative_path
    assert (backup_root / "activities/2026-08/historical-1.yaml").exists()
    assert (backup_root / "wellness/2026-08.json").exists()
    assert activity_path.stat().st_mode & 0o777 == 0o600

    repeated = migrate_evidence_state(
        repo,
        apply=True,
        migrated_at_utc=datetime(2026, 8, 6, 13, 0, tzinfo=timezone.utc),
    )
    assert repeated.changes_required is False
    assert repeated.applied is False
    assert repeated.backup_relative_path == ""
    assert not (tmp_path / "data/backups/evidence-v5/migration-20260806T130000Z").exists()


def test_unresolved_transaction_preserves_recovery_journal_and_permanent_backup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    _write_legacy_state(repo, tmp_path)
    timestamp = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)

    def leave_recovery_journal(**kwargs) -> None:
        repo.write_json(kwargs["run_root"] / "commit.json", {"phase": "prepared"})
        raise RuntimeError("simulated interrupted transaction")

    monkeypatch.setattr(
        "resilio.core.evidence_migration.service.commit_activity_mutation",
        leave_recovery_journal,
    )

    with pytest.raises(RuntimeError, match="simulated interrupted"):
        migrate_evidence_state(repo, apply=True, migrated_at_utc=timestamp)

    run_id = "migration-20260806T120000Z"
    assert (tmp_path / f"data/migrations/evidence-v5/{run_id}/commit.json").exists()
    assert (tmp_path / f"data/backups/evidence-v5/{run_id}/activities").exists()
