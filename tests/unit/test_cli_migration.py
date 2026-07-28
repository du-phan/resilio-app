"""CLI coverage for the restartable activity migration surface."""

import json

from typer.testing import CliRunner

from resilio.cli import app
from resilio.schemas.migration import MigrationRunEnvelope


def test_migration_status_reports_existing_run(tmp_path) -> None:
    state = MigrationRunEnvelope(
        run_id="migration-abc123",
        input_manifest_sha256="a" * 64,
        created_at_utc="2026-07-28T12:00:00Z",
        source_validated=True,
        backup_verified=True,
        candidate_built=True,
        reconciliation_passed=True,
        applied=True,
    )
    path = (
        tmp_path
        / "data/migrations/activity-v2/migration-abc123/run.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(state.model_dump_json())

    result = CliRunner().invoke(
        app,
        ["--repo-root", str(tmp_path), "activity-migration", "status"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["runs"][0]["run_id"] == "migration-abc123"
