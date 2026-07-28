"""Small exclusive lock used by mutating application services."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class OperationLockError(RuntimeError):
    pass


class OperationLock:
    def __init__(self, path: Path, operation: str):
        self.path = path
        self.operation = operation
        self.acquired = False

    def __enter__(self) -> "OperationLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "operation": self.operation,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise OperationLockError(
                f"Operation lock is already held: {self.path}"
            ) from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
        self.acquired = True
        return self

    def __exit__(self, *_args) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False
