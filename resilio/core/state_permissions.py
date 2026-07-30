"""Filesystem privacy policy for locally persisted athlete state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class StatePermissionError(OSError):
    """Sensitive state permissions could not be hardened safely."""


@dataclass(frozen=True)
class PermissionHardeningResult:
    directories_hardened: int
    files_hardened: int


def ensure_private_directory_tree(
    private_root: Path,
    directory: Path,
) -> None:
    """Create and harden a directory chain inside one private-state root."""
    try:
        relative_directory = directory.relative_to(private_root)
    except ValueError as exc:
        raise StatePermissionError(
            "Private directory must remain inside its declared state root"
        ) from exc
    existing_chain = [private_root]
    current = private_root
    for part in relative_directory.parts:
        current /= part
        existing_chain.append(current)
    for candidate in existing_chain:
        if candidate.is_symlink():
            raise StatePermissionError(
                f"Sensitive state path cannot be a symlink: {candidate}"
            )
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        for candidate in existing_chain:
            candidate.chmod(0o700)
    except OSError as exc:
        raise StatePermissionError(
            f"Unable to prepare private state directory: {directory}"
        ) from exc


def harden_sensitive_file(path: Path) -> None:
    """Apply the private file mode without following a symlink."""
    if path.is_symlink():
        raise StatePermissionError(
            f"Sensitive state file cannot be a symlink: {path}"
        )
    try:
        path.chmod(0o600)
    except OSError as exc:
        raise StatePermissionError(
            f"Unable to harden sensitive state file: {path}"
        ) from exc


def harden_sensitive_state_permissions(
    repo_root: Path,
) -> PermissionHardeningResult:
    """Set private modes on the complete local data tree.

    Symlinks are rejected so the migration can never chmod a target outside
    the repository-owned state boundary.
    """
    data_root = repo_root / "data"
    if not data_root.exists():
        return PermissionHardeningResult(0, 0)
    if data_root.is_symlink():
        raise StatePermissionError("Sensitive data root cannot be a symlink")

    directories_hardened = 0
    files_hardened = 0
    paths = [data_root, *sorted(data_root.rglob("*"))]
    for path in paths:
        if path.is_symlink():
            raise StatePermissionError(
                f"Sensitive state path cannot be a symlink: {path}"
            )
        try:
            if path.is_dir():
                path.chmod(0o700)
                directories_hardened += 1
            elif path.is_file():
                harden_sensitive_file(path)
                files_hardened += 1
        except OSError as exc:
            raise StatePermissionError(
                f"Unable to harden sensitive state path: {path}"
            ) from exc
    return PermissionHardeningResult(
        directories_hardened=directories_hardened,
        files_hardened=files_hardened,
    )
