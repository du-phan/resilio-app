"""Kernel-released operation locking and truthful status behavior."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from resilio.cli.commands.sync import _lock_status
from resilio.core.locking import OperationLock, OperationLockError
from resilio.core.repository import RepositoryIO


def test_concurrent_operation_lock_is_rejected(tmp_path: Path) -> None:
    lock_path = tmp_path / "operation.lock"

    with OperationLock(lock_path, "first"):
        with pytest.raises(OperationLockError, match="already held"):
            with OperationLock(lock_path, "second"):
                pass


def test_process_exit_releases_lock_without_sentinel_cleanup(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "operation.lock"
    script = (
        "import os\n"
        "from pathlib import Path\n"
        "from resilio.core.locking import OperationLock\n"
        f"with OperationLock(Path({str(lock_path)!r}), 'crash'):\n"
        "    os._exit(17)\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
    )

    assert completed.returncode == 17
    assert lock_path.exists()
    with OperationLock(lock_path, "recovery"):
        pass


def test_status_reports_only_kernel_held_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    lock_path = repo.resolve_path("data/state/.activity-mutation.lock")

    with OperationLock(lock_path, "activity_sync"):
        status = _lock_status(repo)
        assert status is not None
        assert status.operation == "activity_sync"
        assert not status.long_running

    assert _lock_status(repo) is None
