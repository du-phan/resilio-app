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
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.memory import (
    ArchivedMemory,
    Memory,
    MemoryConfidence,
    MemoryType,
    PatternInsight,
)


# ============================================================
# YAML I/O HELPERS
# ============================================================


def _read_memories_yaml(repo: RepositoryIO) -> dict:
    """
    Read memories.yaml as raw dictionary.

    Returns empty structure if file doesn't exist.
    """
    path = repo.resolve_path("athlete/memories.yaml")

    if not path.exists():
        return {
            "_schema": {
                "format_version": "1.0.0",
                "schema_type": "memories",
            },
            "memories": [],
            "archived": [],
        }

    with open(path) as f:
        return yaml.safe_load(f) or {}


def _write_memories_yaml(repo: RepositoryIO, data: dict) -> None:
    """
    Write memories.yaml from raw dictionary.

    Uses atomic write (temp file + rename).
    """
    path = repo.resolve_path("athlete/memories.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write
    temp_path = path.with_suffix(".tmp")
    try:
        with open(temp_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        temp_path.replace(path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _parse_datetime(value: str | datetime) -> datetime:
    """
    Parse datetime from string or datetime object.

    YAML auto-parses ISO format strings to datetime objects,
    so we need to handle both formats.
    """
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


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
            final_memory if m.id == final_memory.id else m
            for m in existing_memories
        ]

    # Write back to file
    _write_memories(existing_memories, archived_memory, repo)

    return final_memory, archived_memory


def load_memories(repo: RepositoryIO) -> list[Memory]:
    """
    Load all active memories from athlete/memories.yaml.

    Returns:
        List of all active (non-archived) memories. Returns empty list if
        file doesn't exist or has no memories.

    Example:
        >>> memories = load_memories(repo)
        >>> injury_memories = [m for m in memories if m.type == MemoryType.INJURY_HISTORY]
        >>> len(injury_memories)
        3
    """
    data = _read_memories_yaml(repo)
    memories_data = data.get("memories", [])

    memories = []
    for mem_dict in memories_data:
        try:
            memory = Memory(**mem_dict)
            memories.append(memory)
        except Exception:
            # Skip invalid memory entries
            continue

    return memories


def load_archived_memories(repo: RepositoryIO) -> list[ArchivedMemory]:
    """
    Load all archived memories from athlete/memories.yaml.

    Returns:
        List of archived memories. Returns empty list if file doesn't exist
        or has no archived memories.

    Example:
        >>> archived = load_archived_memories(repo)
        >>> recent_archived = [a for a in archived if a.archived_at > cutoff_date]
    """
    data = _read_memories_yaml(repo)
    archived_data = data.get("archived", [])

    archived_memories = []
    for arch_dict in archived_data:
        try:
            archived = ArchivedMemory(**arch_dict)
            archived_memories.append(archived)
        except Exception:
            continue

    return archived_memories


def _write_memories(
    memories: list[Memory],
    new_archived: Optional[ArchivedMemory],
    repo: RepositoryIO,
) -> None:
    """
    Write memories to athlete/memories.yaml.

    Creates file with schema if it doesn't exist.
    """
    # Load existing data
    data = _read_memories_yaml(repo)

    # Update memories (mode='json' ensures enums/datetimes serialize correctly)
    data["memories"] = [m.model_dump(mode='json') for m in memories]

    # Add new archived memory if provided
    if new_archived:
        archived_list = data.get("archived", [])
        archived_list.append(new_archived.model_dump(mode='json'))
        data["archived"] = archived_list

    _write_memories_yaml(repo, data)


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
            if updated_memory.occurrences >= 3 and updated_memory.confidence != MemoryConfidence.HIGH:
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
                    reason=f"Updated by newer observation about {', '.join(sorted(existing_tags_set & new_tags_set))}",
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
    normalized = re.sub(r'\s+', ' ', normalized)

    # Strip punctuation
    normalized = re.sub(r'[^\w\s]', '', normalized)

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
    context_words = set(re.findall(r'\w+', context_lower))

    # Score each memory
    scored = []
    now = datetime.now()

    for memory in all_memories:
        score = 0.0

        # Content overlap
        memory_words = set(re.findall(r'\w+', memory.content.lower()))
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


# ============================================================
# PATTERN ANALYSIS
# ============================================================


def analyze_memory_patterns(
    repo: RepositoryIO,
) -> list[PatternInsight]:
    """
    Detect patterns from stored memories.

    Patterns detected:
        - Recurring injury locations (3+ mentions)
        - Training response patterns (consistent reactions)
        - Preference consistency

    Args:
        repo: RepositoryIO instance

    Returns:
        List of pattern insights with evidence

    Example:
        >>> patterns = analyze_memory_patterns(repo)
        >>> # PatternInsight(
        >>> #     pattern_type="recurring_injury",
        >>> #     description="Recurring knee issues detected (4 occurrences)",
        >>> #     evidence=["mem_123", "mem_456", "mem_789", "mem_abc"],
        >>> #     confidence=MemoryConfidence.HIGH
        >>> # )
    """
    memories = load_memories(repo)
    insights = []

    # Pattern 1: Recurring injury location (3+ mentions)
    injury_memories = [m for m in memories if m.type == MemoryType.INJURY_HISTORY]

    body_part_counts: dict[str, list[Memory]] = {}
    for mem in injury_memories:
        for tag in mem.tags:
            if tag.startswith("body:"):
                part = tag.split(":")[1]
                if part not in body_part_counts:
                    body_part_counts[part] = []
                body_part_counts[part].append(mem)

    for part, mems in body_part_counts.items():
        # Calculate total mentions (sum of all occurrences)
        total_mentions = sum(m.occurrences for m in mems)

        # Pattern detected if 3+ total mentions OR 3+ separate memories
        if total_mentions >= 3 or len(mems) >= 3:
            insights.append(
                PatternInsight(
                    pattern_type="recurring_injury",
                    description=f"Recurring {part} issues detected ({total_mentions} occurrences)",
                    evidence=[m.id for m in mems],
                    confidence=MemoryConfidence.HIGH,
                )
            )

    # Pattern 2: Override tendency (from training responses)
    override_memories = [
        m
        for m in memories
        if m.type == MemoryType.TRAINING_RESPONSE
        and "override" in m.content.lower()
    ]

    if len(override_memories) >= 3:
        insights.append(
            PatternInsight(
                pattern_type="override_tendency",
                description="Athlete frequently overrides rest suggestions",
                evidence=[m.id for m in override_memories[:5]],
                confidence=MemoryConfidence.MEDIUM,
            )
        )

    # Pattern 3: Consistent preferences (3+ mentions of same preference)
    preference_memories = [m for m in memories if m.type == MemoryType.PREFERENCE]

    # Group by tag
    pref_by_tag: dict[str, list[Memory]] = {}
    for mem in preference_memories:
        for tag in mem.tags:
            if tag not in pref_by_tag:
                pref_by_tag[tag] = []
            pref_by_tag[tag].append(mem)

    for tag, mems in pref_by_tag.items():
        if len(mems) >= 3:
            insights.append(
                PatternInsight(
                    pattern_type="consistent_preference",
                    description=f"Consistent preference for {tag} ({len(mems)} mentions)",
                    evidence=[m.id for m in mems],
                    confidence=MemoryConfidence.HIGH,
                )
            )

    return insights


# ============================================================
# ARCHIVAL
# ============================================================


def archive_memory(
    memory_id: str,
    superseded_by: str,
    reason: str,
    repo: RepositoryIO,
) -> ArchivedMemory:
    """
    Archive a memory that has been superseded.

    Process:
        1. Load memories.yaml
        2. Find memory by ID
        3. Create ArchivedMemory record
        4. Move to archived list
        5. Remove from active list
        6. Write updated memories.yaml
        7. Return ArchivedMemory

    Args:
        memory_id: ID of memory to archive
        superseded_by: ID of memory that replaces it
        reason: Human-readable reason for archiving
        repo: RepositoryIO instance

    Returns:
        ArchivedMemory record

    Raises:
        ValueError: If memory_id not found

    Example:
        >>> archived = archive_memory(
        ...     "mem_old123",
        ...     "mem_new456",
        ...     "Updated by newer observation",
        ...     repo
        ... )
        >>> archived.id  # "mem_old123"
        >>> archived.superseded_by  # "mem_new456"
    """
    # Load memories
    data = _read_memories_yaml(repo)
    active_memories = data.get("memories", [])
    archived_memories = data.get("archived", [])

    # Find the memory to archive
    memory_to_archive = next(
        (m for m in active_memories if m["id"] == memory_id),
        None,
    )

    if not memory_to_archive:
        raise ValueError(f"Memory not found: {memory_id}")

    # Create archived record
    archived = ArchivedMemory(
        id=memory_id,
        original_content=memory_to_archive["content"],
        superseded_by=superseded_by,
        archived_at=datetime.now(),
        reason=reason,
    )

    # Add to archived list
    archived_memories.append(archived.model_dump())

    # Remove from active list
    active_memories = [m for m in active_memories if m["id"] != memory_id]

    # Update file
    data["memories"] = active_memories
    data["archived"] = archived_memories
    _write_memories_yaml(repo, data)

    return archived


def cleanup_archived(
    repo: RepositoryIO,
    retention_days: int = 90,
) -> int:
    """
    Remove archived memories older than retention period.

    Process:
        1. Load memories.yaml
        2. Filter archived memories older than retention_days
        3. Remove old archived memories
        4. Write updated memories.yaml
        5. Return count deleted

    Args:
        repo: RepositoryIO instance
        retention_days: Days to retain archived memories (default 90)

    Returns:
        Number of archived memories deleted

    Example:
        >>> deleted_count = cleanup_archived(repo, retention_days=90)
        >>> deleted_count  # 3 (removed 3 old archived memories)
    """
    data = _read_memories_yaml(repo)
    archived_memories = data.get("archived", [])

    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    # Filter out old archived memories
    initial_count = len(archived_memories)
    archived_memories = [
        m
        for m in archived_memories
        if _parse_datetime(m["archived_at"]) > cutoff_date
    ]

    deleted_count = initial_count - len(archived_memories)

    if deleted_count > 0:
        # Update file
        data["archived"] = archived_memories
        _write_memories_yaml(repo, data)

    return deleted_count
