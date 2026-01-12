"""
M13 - Memory & Insights

Extract durable athlete facts from notes and conversations.
"""

from typing import Any


def extract_memories(repo: Any, activity: dict) -> list[Any]:
    """Extract memories from activity notes."""
    raise NotImplementedError("Memory extraction not implemented yet")


def update_memory(repo: Any, memory: dict) -> None:
    """Update or create a memory."""
    raise NotImplementedError("Memory update not implemented yet")
