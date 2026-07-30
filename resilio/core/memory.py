"""
M13 — Memory & Insights

Persist and retrieve durable athlete facts extracted by Claude Code. Provides
storage with smart deduplication, confidence scoring, and pattern detection.

Design Philosophy: Leverage Claude Code's AI intelligence for extraction
(understands "knee pain after long runs" vs "slight knee soreness") rather
than rigid regex patterns. M13 focuses on robust storage, preventing duplicate
memories, and efficient retrieval.

Key Features:
- Three-step deduplication (exact match, type+tag match, new)
- Automatic confidence upgrades (3+ occurrences → HIGH)
- Retrieval by type, tag, and relevance scoring
- Pattern detection from stored memories (3+ mentions = pattern)
"""

import re
from datetime import datetime
from typing import Optional

from resilio.core.memory_analysis import (
    analyze_memory_patterns as analyze_memory_patterns,
)
from resilio.core.memory_storage import (
    archive_memory as archive_memory,
)
from resilio.core.memory_storage import (
    cleanup_archived as cleanup_archived,
)
from resilio.core.memory_storage import (
    load_archived_memories as load_archived_memories,
)
from resilio.core.memory_storage import (
    load_memories as load_memories,
)
from resilio.core.memory_storage import write_memories
from resilio.core.repository import RepositoryIO
from resilio.schemas.memory import (
    ArchivedMemory,
    Memory,
    MemoryConfidence,
    MemoryType,
)

# ============================================================
# STORAGE FUNCTIONS
# ============================================================


def save_memory(
    memory: Memory,
    repo: RepositoryIO,
) -> tuple[Memory, Optional[ArchivedMemory]]:
    """
    Save a single memory with automatic deduplication.
    Called by Claude Code after extraction.

    Process:
        1. Load existing memories from athlete/memories.yaml
        2. Deduplicate against existing using three-step algorithm
        3. Write updated memories back to file
        4. Return final memory and archived memory (if superseded)

    Args:
        memory: Memory to save (extracted by Claude Code)
        repo: RepositoryIO instance

    Returns:
        (final_memory, archived_memory_if_superseded)

    Example:
        >>> memory = Memory(
        ...     id="mem_abc123",
        ...     type=MemoryType.INJURY_HISTORY,
        ...     content="Left knee pain after long runs over 18km",
        ...     source=MemorySource.CLAUDE_CODE,
        ...     confidence=MemoryConfidence.MEDIUM,
        ...     tags=["body:knee"],
        ... )
        >>> final, archived = save_memory(memory, repo)
        >>> # If exact match: final.occurrences = 2, archived = None
        >>> # If supersedes: final = memory, archived = old_memory
        >>> # If new: final = memory, archived = None
    """
    # Load existing memories
    existing_memories = load_memories(repo)

    # Deduplicate
    final_memory, archived_memory = deduplicate_memory(memory, existing_memories)

    # Update existing list
    if archived_memory:
        # Remove old memory, add new
        existing_memories = [m for m in existing_memories if m.id != archived_memory.id]
        existing_memories.append(final_memory)
    elif final_memory.id == memory.id:
        # Truly new memory
        existing_memories.append(final_memory)
    else:
        # Existing memory was updated (occurrences incremented)
        existing_memories = [
            final_memory if m.id == final_memory.id else m for m in existing_memories
        ]

    # Write back to file
    write_memories(existing_memories, archived_memory, repo)

    return final_memory, archived_memory


# ============================================================
# DEDUPLICATION
# ============================================================


def deduplicate_memory(
    new_memory: Memory,
    existing_memories: list[Memory],
) -> tuple[Memory, Optional[ArchivedMemory]]:
    """
    Three-step deduplication algorithm:
    1. Exact content match → increment occurrences
    2. Same type + overlapping tags → update content (supersede old)
    3. No match → return as new memory

    Confidence upgrade: 3+ occurrences → HIGH

    Args:
        new_memory: Memory to check
        existing_memories: List of existing memories

    Returns:
        (result_memory, archived_memory_if_replaced)

    Example:
        >>> # Step 1: Exact match
        >>> result, archived = deduplicate_memory(new_mem, [exact_match])
        >>> result.occurrences  # 3 (was 2, now 3)
        >>> archived  # None

        >>> # Step 2: Same type+tag supersedes
        >>> result, archived = deduplicate_memory(new_mem, [vague_old_mem])
        >>> result.id == new_mem.id  # True (new memory kept)
        >>> archived.id == old_mem.id  # True (old memory archived)

        >>> # Step 3: No match
        >>> result, archived = deduplicate_memory(new_mem, [])
        >>> result.id == new_mem.id  # True
        >>> archived  # None
    """
    # Normalize new memory content for comparison
    normalized_new = _normalize_for_comparison(new_memory.content)

    # Step 1: Check for exact content match
    for existing in existing_memories:
        normalized_existing = _normalize_for_comparison(existing.content)

        if normalized_new == normalized_existing:
            # Exact match - increment occurrences
            updated_memory = existing.model_copy(deep=True)
            updated_memory.occurrences += 1
            updated_memory.updated_at = datetime.now()

            # Upgrade confidence if 3+ occurrences
            if (
                updated_memory.occurrences >= 3
                and updated_memory.confidence != MemoryConfidence.HIGH
            ):
                updated_memory.confidence = MemoryConfidence.HIGH

            return updated_memory, None

    # Step 2: Check for same type + overlapping tags (supersede)
    for existing in existing_memories:
        if existing.type == new_memory.type:
            # Check for overlapping tags
            existing_tags_set = set(existing.tags)
            new_tags_set = set(new_memory.tags)

            if existing_tags_set & new_tags_set:  # Intersection is non-empty
                # Same entity, newer observation supersedes old
                archived = ArchivedMemory(
                    id=existing.id,
                    original_content=existing.content,
                    superseded_by=new_memory.id,
                    archived_at=datetime.now(),
                    reason=(
                        "Updated by newer observation about "
                        f"{', '.join(sorted(existing_tags_set & new_tags_set))}"
                    ),
                )

                # Transfer occurrences to new memory
                updated_memory = new_memory.model_copy(deep=True)
                updated_memory.occurrences = existing.occurrences + 1
                updated_memory.updated_at = datetime.now()

                # Upgrade confidence if 3+ occurrences
                if updated_memory.occurrences >= 3:
                    updated_memory.confidence = MemoryConfidence.HIGH

                return updated_memory, archived

    # Step 3: No match - return as new memory
    return new_memory, None


def _normalize_for_comparison(content: str) -> str:
    """
    Normalize content for exact comparison.
    Lowercases, removes extra whitespace, strips punctuation.

    Args:
        content: Memory content string

    Returns:
        Normalized string for comparison

    Example:
        >>> _normalize_for_comparison("Left knee pain!")
        'left knee pain'
        >>> _normalize_for_comparison("   Left   knee   pain   ")
        'left knee pain'
    """
    # Lowercase
    normalized = content.lower()

    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized)

    # Strip punctuation
    normalized = re.sub(r"[^\w\s]", "", normalized)

    return normalized.strip()


# ============================================================
# RETRIEVAL FUNCTIONS
# ============================================================


def get_memories_by_type(
    memory_type: MemoryType,
    repo: RepositoryIO,
) -> list[Memory]:
    """
    Get all memories of a specific type, sorted by confidence/recency.

    Sort order: HIGH confidence first, then MEDIUM, then LOW.
    Within same confidence, most recent first.

    Args:
        memory_type: The type of memories to retrieve
        repo: RepositoryIO instance

    Returns:
        List of memories matching the type, sorted by confidence/recency

    Example:
        >>> injuries = get_memories_by_type(MemoryType.INJURY_HISTORY, repo)
        >>> injuries[0].confidence  # MemoryConfidence.HIGH (most confident first)
        >>> injuries[0].updated_at > injuries[1].updated_at  # Most recent within confidence
    """
    all_memories = load_memories(repo)

    # Filter by type
    filtered = [m for m in all_memories if m.type == memory_type]

    # Sort by confidence (HIGH first) then recency
    confidence_order = {
        MemoryConfidence.HIGH: 3,
        MemoryConfidence.MEDIUM: 2,
        MemoryConfidence.LOW: 1,
    }

    filtered.sort(
        key=lambda m: (confidence_order.get(m.confidence, 0), m.updated_at),
        reverse=True,
    )

    return filtered


def get_relevant_memories(
    context: str,
    repo: RepositoryIO,
    limit: int = 5,
) -> list[Memory]:
    """
    Get memories relevant to current context using keyword matching.

    Scoring:
        - Content overlap (keyword matching): +1 per matching word
        - Tag matching: +2 per matching tag
        - Confidence level: HIGH +3, MEDIUM +2, LOW +1
        - Recency: +0.1 per day within last 30 days

    Args:
        context: Context string to match against (e.g., "knee pain")
        repo: RepositoryIO instance
        limit: Maximum number of memories to return

    Returns:
        List of most relevant memories, sorted by relevance score

    Example:
        >>> # Context: "knee pain after running"
        >>> relevant = get_relevant_memories("knee pain after running", repo, limit=3)
        >>> relevant[0].content  # "Left knee pain after long runs over 18km" (high score)
        >>> relevant[0].tags  # ["body:knee"] (tag match)
    """
    all_memories = load_memories(repo)

    if not all_memories:
        return []

    # Tokenize context
    context_lower = context.lower()
    context_words = set(re.findall(r"\w+", context_lower))

    # Score each memory
    scored = []
    now = datetime.now()

    for memory in all_memories:
        score = 0.0

        # Content overlap
        memory_words = set(re.findall(r"\w+", memory.content.lower()))
        matching_words = context_words & memory_words
        score += len(matching_words)

        # Tag matching
        for tag in memory.tags:
            tag_value = tag.split(":")[-1] if ":" in tag else tag
            if tag_value in context_lower:
                score += 2

        # Confidence boost
        if memory.confidence == MemoryConfidence.HIGH:
            score += 3
        elif memory.confidence == MemoryConfidence.MEDIUM:
            score += 2
        else:
            score += 1

        # Recency boost (last 30 days)
        days_ago = (now - memory.updated_at).days
        if days_ago <= 30:
            score += (30 - days_ago) * 0.1

        if score > 0:
            scored.append((score, memory))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Return top N
    return [memory for _, memory in scored[:limit]]


def get_memories_with_tag(
    tag: str,
    repo: RepositoryIO,
) -> list[Memory]:
    """
    Get all memories with a specific tag.

    Args:
        tag: Tag to filter by (e.g., "body:knee")
        repo: RepositoryIO instance

    Returns:
        List of memories with the specified tag, sorted by recency

    Example:
        >>> knee_memories = get_memories_with_tag("body:knee", repo)
        >>> all(mem.tags for mem in knee_memories)  # All have tags
        >>> all("body:knee" in mem.tags for mem in knee_memories)  # All match tag
    """
    all_memories = load_memories(repo)

    # Filter by tag
    filtered = [m for m in all_memories if tag in m.tags]

    # Sort by recency
    filtered.sort(key=lambda m: m.updated_at, reverse=True)

    return filtered
