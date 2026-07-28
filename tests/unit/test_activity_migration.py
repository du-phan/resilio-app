"""Data-safety tests for the restartable activity-v2 migration."""

from datetime import date
from pathlib import Path

import pytest
import yaml

from resilio.core.activity_migration.service import (
    ActivityV2Migrator,
    MigrationError,
)
from resilio.schemas.activity import (
    ActivityOrigin,
    ActivityOriginKind,
    CanonicalActivity,
    RecordingProvider,
)


def _legacy(activity_id: str = "legacy-private-id") -> dict:
    return {
        "schema_metadata": {
            "schema_type": "activity",
            "schema_version": "1.0",
        },
        "id": activity_id,
        "source": "historical",
        "sport_type": "run",
        "name": "Archived run",
        "date": date(2026, 1, 12),
        "start_time": "2026-01-12T07:00:00+00:00",
        "duration_minutes": 45,
        "duration_seconds": 2700,
        "distance_km": 8.0,
        "distance_meters": 8000.0,
        "elevation_gain_m": 50.0,
        "created_at": "2026-01-12T08:00:00+00:00",
        "updated_at": "2026-01-12T08:00:00+00:00",
        "calculated": {
            "activity_id": activity_id,
            "duration_minutes": 45,
            "estimated_rpe": 5,
            "sport_type": "run",
            "base_effort_au": 50.0,
            "systemic_multiplier": 1.0,
            "lower_body_multiplier": 1.0,
            "multiplier_adjustments": [],
            "systemic_load_au": 50.0,
            "lower_body_load_au": 50.0,
            "session_type": "moderate",
        },
    }


def _repo(tmp_path: Path, payload: dict) -> None:
    (tmp_path / ".git").mkdir()
    activity_dir = tmp_path / "data" / "activities" / "2026-01"
    activity_dir.mkdir(parents=True)
    (activity_dir / "legacy.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False)
    )
    for name in ("metrics", "athlete", "plans", "state"):
        directory = tmp_path / "data" / name
        directory.mkdir(parents=True)
        (directory / "snapshot.txt").write_text(f"original-{name}\n")


def test_dry_run_is_deterministic_and_does_not_switch_archive(tmp_path) -> None:
    _repo(tmp_path, _legacy())
    migrator = ActivityV2Migrator(tmp_path)

    first = migrator.dry_run()
    second = migrator.dry_run()

    assert first == second
    assert first.source.record_count == 1
    assert first.candidate.record_count == 1
    assert first.totals_match
    assert (
        tmp_path / "data" / "activities" / "2026-01" / "legacy.yaml"
    ).exists()
    candidate_files = list(
        (tmp_path / "data" / "migrations").rglob("candidate/**/*.yaml")
    )
    assert len(candidate_files) == 1
    candidate = CanonicalActivity.model_validate(
        yaml.safe_load(candidate_files[0].read_text())
    )
    assert candidate.local_activity_id.startswith("act_h_")
    for artifact in (tmp_path / "data" / "migrations").rglob("*"):
        if artifact.is_file():
            assert "legacy-private-id" not in artifact.read_text()


def test_apply_and_rollback_restore_source_hashes(tmp_path) -> None:
    _repo(tmp_path, _legacy())
    migrator = ActivityV2Migrator(tmp_path)
    report = migrator.dry_run()

    migrator.apply(report.input_manifest_sha256)
    active = list((tmp_path / "data" / "activities").rglob("*.yaml"))
    assert len(active) == 1
    CanonicalActivity.model_validate(yaml.safe_load(active[0].read_text()))
    for name in ("metrics", "athlete", "plans", "state"):
        (tmp_path / "data" / name / "snapshot.txt").write_text(
            f"post-migration-{name}\n"
        )

    migrator.rollback(report.input_manifest_sha256)
    restored = tmp_path / "data" / "activities" / "2026-01" / "legacy.yaml"
    assert restored.exists()
    assert yaml.safe_load(restored.read_text())["id"] == "legacy-private-id"
    for name in ("metrics", "athlete", "plans", "state"):
        assert (
            tmp_path / "data" / name / "snapshot.txt"
        ).read_text() == f"original-{name}\n"


def test_linked_history_repair_restores_migration_facts(tmp_path) -> None:
    _repo(tmp_path, _legacy())
    migrator = ActivityV2Migrator(tmp_path)
    report = migrator.dry_run()
    migrator.apply(report.input_manifest_sha256)

    active_path = next((tmp_path / "data" / "activities").rglob("*.yaml"))
    linked = CanonicalActivity.model_validate(
        yaml.safe_load(active_path.read_text())
    )
    linked = linked.model_copy(
        update={
            "duration": linked.duration.model_copy(
                update={"elapsed_seconds": 2760, "moving_seconds": 2760}
            ),
            "origin": ActivityOrigin(
                kind=ActivityOriginKind.HISTORICAL_IMPORT,
                recording_provider=RecordingProvider.WAHOO,
                intervals_icu_activity_id="external-1",
            ),
        }
    )
    active_path.write_text(
        yaml.safe_dump(
            linked.model_dump(mode="json", by_alias=True),
            sort_keys=False,
        )
    )

    repair = migrator.repair_linked_history(report.input_manifest_sha256)
    restored = CanonicalActivity.model_validate(
        yaml.safe_load(active_path.read_text())
    )

    assert repair["repaired_linked_records"] == 1
    assert repair["migration_totals_restored"]
    assert restored.duration.elapsed_seconds == 2700
    assert restored.origin.intervals_icu_activity_id == "external-1"
    assert restored.origin.recording_provider == RecordingProvider.WAHOO


def test_rollback_restore_failure_reverses_every_swapped_root(
    tmp_path,
    monkeypatch,
) -> None:
    _repo(tmp_path, _legacy())
    migrator = ActivityV2Migrator(tmp_path)
    report = migrator.dry_run()
    migrator.apply(report.input_manifest_sha256)
    for name in ("metrics", "athlete", "plans", "state"):
        (tmp_path / "data" / name / "snapshot.txt").write_text(
            f"post-migration-{name}\n"
        )

    real_replace = __import__(
        "resilio.core.activity_migration.service",
        fromlist=["os"],
    ).os.replace
    failing_source = (
        tmp_path
        / "data"
        / "migrations"
        / "activity-v2"
        / f"migration-{report.input_manifest_sha256[:12]}"
        / "rollback-restore"
        / "metrics"
    )
    failing_target = tmp_path / "data" / "metrics"

    def fail_metrics_restore(source, target):
        if Path(source) == failing_source and Path(target) == failing_target:
            raise OSError("simulated restore failure")
        return real_replace(source, target)

    monkeypatch.setattr(
        "resilio.core.activity_migration.service.os.replace",
        fail_metrics_restore,
    )

    with pytest.raises(OSError, match="simulated restore failure"):
        migrator.rollback(report.input_manifest_sha256)

    active = next((tmp_path / "data" / "activities").rglob("*.yaml"))
    CanonicalActivity.model_validate(yaml.safe_load(active.read_text()))
    for name in ("metrics", "athlete", "plans", "state"):
        assert (
            tmp_path / "data" / name / "snapshot.txt"
        ).read_text() == f"post-migration-{name}\n"
    rollback = (
        tmp_path
        / "data"
        / "migrations"
        / "activity-v2"
        / f"migration-{report.input_manifest_sha256[:12]}"
        / "rollback-activities-v1"
    )
    assert next(rollback.rglob("*.yaml"))


def test_invalid_source_produces_no_backup_or_candidate(tmp_path) -> None:
    _repo(tmp_path, {**_legacy(), "duration_seconds": 0})
    migrator = ActivityV2Migrator(tmp_path)

    with pytest.raises(ValueError, match="duration must be positive"):
        migrator.dry_run()

    assert not (tmp_path / "data" / "backups").exists()
    assert not (tmp_path / "data" / "migrations").exists()


def test_duplicate_ids_fail_without_switching_source(tmp_path) -> None:
    _repo(tmp_path, _legacy())
    second = tmp_path / "data" / "activities" / "2026-01" / "duplicate.yaml"
    second.write_text(yaml.safe_dump(_legacy(), sort_keys=False))

    with pytest.raises(MigrationError, match="Duplicate deterministic"):
        ActivityV2Migrator(tmp_path).dry_run()

    assert second.exists()
