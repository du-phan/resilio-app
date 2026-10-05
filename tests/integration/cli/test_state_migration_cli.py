"""Recover the exact journaled transaction through the supported CLI."""

import json

import pytest
from typer.testing import CliRunner

from resilio.cli import app
from resilio.core.repository import RepositoryIO
from resilio.core.state_migration_guard import MIGRATION_TRANSACTION_PATH
from resilio.core.state_migration_transaction import commit_state_migration


def test_recover_state_restores_interrupted_targets_without_another_cutover(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    relative_path = "data/plans/proposals/interrupted.json"
    path = repo.resolve_path(relative_path)
    path.parent.mkdir(parents=True)
    path.write_text("original approved bytes")

    def interrupt():
        path.write_text("partial cutover")
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        commit_state_migration(
            repo,
            run_id="cli-recovery",
            backup_relative_path="data/backups/cli-recovery",
            target_relative_paths=(relative_path,),
            apply_state=interrupt,
        )
    result = CliRunner().invoke(app, ["migrate", "recover-state"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["data"]["recovered"] is True
    assert path.read_text() == "original approved bytes"
    assert not repo.resolve_path(MIGRATION_TRANSACTION_PATH).exists()
    result = CliRunner().invoke(app, ["migrate", "recover-state"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["data"]["recovered"] is False
