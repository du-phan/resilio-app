"""Small exclusive lock used by mutating application services."""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from resilio.core.state_permissions import ensure_private_directory_tree


class OperationLockError(RuntimeError):
    pass


class OperationLock:
    def __init__(self, path: Path, operation: str):
        self.path = path
        self.operation = operation
        self._descriptor: int | None = None

    def __enter__(self) -> "OperationLock":
        ensure_private_directory_tree(self.path.parent, self.path.parent)
        payload = {
            "pid": os.getpid(),
            "operation": self.operation,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        }
        descriptor = os.open(
            self.path,
            os.O_CREAT | os.O_RDWR,
            0o600,
        )
        try:
            fcntl.flock(
                descriptor,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError as exc:
            os.close(descriptor)
            raise OperationLockError(f"Operation lock is already held: {self.path}") from exc
        serialized = (json.dumps(payload, sort_keys=True) + "\n").encode()
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, serialized)
        os.fsync(descriptor)
        self._descriptor = descriptor
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exception_type, exception, traceback
        descriptor = self._descriptor
        if descriptor is not None:
            self._descriptor = None
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
