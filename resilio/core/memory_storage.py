"""Persistence and archival operations for athlete memories."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import yaml

from resilio.core.paths import athlete_memories_path
from resilio.core.repository import RepositoryIO
from resilio.schemas.memory import ArchivedMemory, Memory
from resilio.schemas.repository import RepoError


def _empty_memory_store() -> dict[str, Any]:
    return {
        "_schema": {
            "format_version": "1.0.0",
            "schema_type": "memories",
        },
        "memories": [],
        "archived": [],
    }


def _read_memories_yaml(repo: RepositoryIO) -> dict[str, Any]:
    path = repo.resolve_path(athlete_memories_path())
    if not path.exists():
        return _empty_memory_store()
    with path.open() as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items()}


def _write_memories_yaml(repo: RepositoryIO, data: dict[str, Any]) -> None:
    error = repo.write_yaml(athlete_memories_path(), data)
    if isinstance(error, RepoError):
        raise OSError(f"Failed to save athlete memories: {error}")


def load_memories(repo: RepositoryIO) -> list[Memory]:
    """Load valid active memories; invalid individual records are ignored."""
    memories: list[Memory] = []
    for payload in _read_memories_yaml(repo).get("memories", []):
        try:
            memories.append(Memory.model_validate(payload))
        except ValueError:
            continue
    return memories


def load_archived_memories(repo: RepositoryIO) -> list[ArchivedMemory]:
    """Load valid archived memories; invalid individual records are ignored."""
    archived_memories: list[ArchivedMemory] = []
    for payload in _read_memories_yaml(repo).get("archived", []):
        try:
            archived_memories.append(ArchivedMemory.model_validate(payload))
        except ValueError:
            continue
    return archived_memories


def write_memories(
    memories: list[Memory],
    new_archived: ArchivedMemory | None,
    repo: RepositoryIO,
) -> None:
    """Replace active memories and optionally append one archive record."""
    data = _read_memories_yaml(repo)
    data["memories"] = [memory.model_dump(mode="json") for memory in memories]
    if new_archived is not None:
        archived_list = data.get("archived", [])
        archived_list.append(new_archived.model_dump(mode="json"))
        data["archived"] = archived_list
    _write_memories_yaml(repo, data)


def archive_memory(
    memory_id: str,
    superseded_by: str,
    reason: str,
    repo: RepositoryIO,
) -> ArchivedMemory:
    """Move one active memory into the append-only archive."""
    data = _read_memories_yaml(repo)
    active_memories = data.get("memories", [])
    archived_memories = data.get("archived", [])
    memory_to_archive = next(
        (memory for memory in active_memories if memory["id"] == memory_id),
        None,
    )
    if memory_to_archive is None:
        raise ValueError(f"Memory not found: {memory_id}")

    archived = ArchivedMemory(
        id=memory_id,
        original_content=memory_to_archive["content"],
        superseded_by=superseded_by,
        archived_at=datetime.now(),
        reason=reason,
    )
    archived_memories.append(archived.model_dump())
    data["memories"] = [memory for memory in active_memories if memory["id"] != memory_id]
    data["archived"] = archived_memories
    _write_memories_yaml(repo, data)
    return archived


def cleanup_archived(repo: RepositoryIO, retention_days: int = 90) -> int:
    """Delete archive records older than the configured retention period."""
    data = _read_memories_yaml(repo)
    archived_memories = data.get("archived", [])
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    retained = [
        memory
        for memory in archived_memories
        if _parse_datetime(memory["archived_at"]) > cutoff_date
    ]
    deleted_count = len(archived_memories) - len(retained)
    if deleted_count:
        data["archived"] = retained
        _write_memories_yaml(repo, data)
    return deleted_count


def _parse_datetime(value: str | datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)
