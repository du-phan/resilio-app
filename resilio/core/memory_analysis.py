"""Deterministic pattern analysis over persisted athlete memories."""

from __future__ import annotations

from resilio.core.memory_storage import load_memories
from resilio.core.repository import RepositoryIO
from resilio.schemas.memory import (
    Memory,
    MemoryConfidence,
    MemoryType,
    PatternInsight,
)


def analyze_memory_patterns(repo: RepositoryIO) -> list[PatternInsight]:
    """Detect recurring injuries, override tendencies, and preferences."""
    memories = load_memories(repo)
    insights = _recurring_injury_insights(memories)
    override_insight = _override_tendency_insight(memories)
    if override_insight is not None:
        insights.append(override_insight)
    insights.extend(_consistent_preference_insights(memories))
    return insights


def _recurring_injury_insights(memories: list[Memory]) -> list[PatternInsight]:
    memories_by_body_part: dict[str, list[Memory]] = {}
    for memory in memories:
        if memory.type != MemoryType.INJURY_HISTORY:
            continue
        for tag in memory.tags:
            if tag.startswith("body:"):
                memories_by_body_part.setdefault(tag.split(":", 1)[1], []).append(memory)

    insights: list[PatternInsight] = []
    for body_part, matching_memories in memories_by_body_part.items():
        total_mentions = sum(memory.occurrences for memory in matching_memories)
        if total_mentions >= 3 or len(matching_memories) >= 3:
            insights.append(
                PatternInsight(
                    pattern_type="recurring_injury",
                    description=(
                        f"Recurring {body_part} issues detected " f"({total_mentions} occurrences)"
                    ),
                    evidence=[memory.id for memory in matching_memories],
                    confidence=MemoryConfidence.HIGH,
                )
            )
    return insights


def _override_tendency_insight(
    memories: list[Memory],
) -> PatternInsight | None:
    matching_memories = [
        memory
        for memory in memories
        if memory.type == MemoryType.TRAINING_RESPONSE and "override" in memory.content.lower()
    ]
    if len(matching_memories) < 3:
        return None
    return PatternInsight(
        pattern_type="override_tendency",
        description="Athlete frequently overrides rest suggestions",
        evidence=[memory.id for memory in matching_memories[:5]],
        confidence=MemoryConfidence.MEDIUM,
    )


def _consistent_preference_insights(
    memories: list[Memory],
) -> list[PatternInsight]:
    memories_by_tag: dict[str, list[Memory]] = {}
    for memory in memories:
        if memory.type != MemoryType.PREFERENCE:
            continue
        for tag in memory.tags:
            memories_by_tag.setdefault(tag, []).append(memory)

    return [
        PatternInsight(
            pattern_type="consistent_preference",
            description=f"Consistent preference for {tag} ({len(group)} mentions)",
            evidence=[memory.id for memory in group],
            confidence=MemoryConfidence.HIGH,
        )
        for tag, group in memories_by_tag.items()
        if len(group) >= 3
    ]
