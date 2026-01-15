"""
Tests for M13 - Memory & Insights

Tests focus on storage, deduplication, retrieval, and pattern analysis.
Memory extraction is handled by Claude Code (not tested here).
"""

from datetime import datetime, timedelta

import pytest

from sports_coach_engine.core.memory import (
    analyze_memory_patterns,
    archive_memory,
    cleanup_archived,
    deduplicate_memory,
    get_memories_by_type,
    get_memories_with_tag,
    get_relevant_memories,
    load_archived_memories,
    load_memories,
    save_memory,
)
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.memory import (
    Memory,
    MemoryConfidence,
    MemorySource,
    MemoryType,
)


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Create a test repository."""
    # Create .git directory to mark as repo root
    (tmp_path / ".git").mkdir()
    # Create athlete directory
    (tmp_path / "data" / "athlete").mkdir(exist_ok=True)
    # Change to tmp directory
    monkeypatch.chdir(tmp_path)
    return RepositoryIO()


@pytest.fixture
def sample_memory():
    """Create a sample memory for testing."""
    return Memory(
        id="mem_test123",
        type=MemoryType.INJURY_HISTORY,
        content="Left knee pain after long runs over 18km",
        source=MemorySource.CLAUDE_CODE,
        source_reference=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        confidence=MemoryConfidence.MEDIUM,
        occurrences=1,
        tags=["body:knee"],
    )


@pytest.fixture
def sample_memories():
    """Create multiple sample memories for testing."""
    now = datetime.now()
    return [
        Memory(
            id="mem_001",
            type=MemoryType.INJURY_HISTORY,
            content="Left knee pain after long runs",
            source=MemorySource.CLAUDE_CODE,
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            confidence=MemoryConfidence.HIGH,
            occurrences=3,
            tags=["body:knee"],
        ),
        Memory(
            id="mem_002",
            type=MemoryType.PREFERENCE,
            content="Prefers morning runs",
            source=MemorySource.USER_MESSAGE,
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
            confidence=MemoryConfidence.MEDIUM,
            occurrences=2,
            tags=["time:morning"],
        ),
        Memory(
            id="mem_003",
            type=MemoryType.INJURY_HISTORY,
            content="Right ankle soreness after trail runs",
            source=MemorySource.ACTIVITY_NOTE,
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3),
            confidence=MemoryConfidence.LOW,
            occurrences=1,
            tags=["body:ankle"],
        ),
    ]


# ============================================================
# STORAGE TESTS
# ============================================================


class TestStorage:
    """Test memory storage functions."""

    def test_save_memory_new(self, repo, sample_memory):
        """New memory is saved correctly."""
        final, archived = save_memory(sample_memory, repo)

        assert final.id == sample_memory.id
        assert archived is None

        # Verify file was written
        memories = load_memories(repo)
        assert len(memories) == 1
        assert memories[0].id == sample_memory.id

    def test_save_memory_exact_match(self, repo, sample_memory):
        """Exact match increments occurrences."""
        # Save first time
        save_memory(sample_memory, repo)

        # Save same content again
        duplicate = sample_memory.model_copy(deep=True)
        duplicate.id = "mem_different_id"

        final, archived = save_memory(duplicate, repo)

        # Should have incremented original
        assert final.id == sample_memory.id  # Original ID kept
        assert final.occurrences == 2
        assert archived is None

        # Only one memory in storage
        memories = load_memories(repo)
        assert len(memories) == 1

    def test_save_memory_supersedes(self, repo):
        """Same type+tag supersedes old memory."""
        # Save vague old memory
        old_memory = Memory(
            id="mem_old",
            type=MemoryType.INJURY_HISTORY,
            content="Occasional knee soreness",
            source=MemorySource.ACTIVITY_NOTE,
            created_at=datetime.now() - timedelta(days=30),
            updated_at=datetime.now() - timedelta(days=30),
            confidence=MemoryConfidence.LOW,
            occurrences=1,
            tags=["body:knee"],
        )
        save_memory(old_memory, repo)

        # Save more specific new memory
        new_memory = Memory(
            id="mem_new",
            type=MemoryType.INJURY_HISTORY,
            content="Chronic knee pain after runs over 15km",
            source=MemorySource.CLAUDE_CODE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.HIGH,
            occurrences=1,
            tags=["body:knee"],
        )
        final, archived = save_memory(new_memory, repo)

        # New memory kept, old archived
        assert final.id == new_memory.id
        assert archived is not None
        assert archived.id == old_memory.id
        assert archived.superseded_by == new_memory.id

        # Only new memory in active storage
        memories = load_memories(repo)
        assert len(memories) == 1
        assert memories[0].id == new_memory.id

        # Old memory in archived
        archived_list = load_archived_memories(repo)
        assert len(archived_list) == 1
        assert archived_list[0].id == old_memory.id

    def test_load_memories(self, repo, sample_memories):
        """Loads memories from YAML correctly."""
        # Save multiple memories
        for mem in sample_memories:
            save_memory(mem, repo)

        # Load and verify
        loaded = load_memories(repo)
        assert len(loaded) == len(sample_memories)

        loaded_ids = {m.id for m in loaded}
        expected_ids = {m.id for m in sample_memories}
        assert loaded_ids == expected_ids

    def test_load_archived_memories(self, repo):
        """Loads archived memories correctly."""
        # Create and save memories that will supersede each other
        old = Memory(
            id="mem_old",
            type=MemoryType.PREFERENCE,
            content="Likes easy runs",
            source=MemorySource.USER_MESSAGE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.MEDIUM,
            tags=["intensity:easy"],
        )
        save_memory(old, repo)

        new = Memory(
            id="mem_new",
            type=MemoryType.PREFERENCE,
            content="Prefers easy recovery runs under 10km",
            source=MemorySource.CLAUDE_CODE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.HIGH,
            tags=["intensity:easy"],
        )
        save_memory(new, repo)

        # Load archived
        archived = load_archived_memories(repo)
        assert len(archived) == 1
        assert archived[0].id == old.id

    def test_save_updates_file(self, repo, sample_memory):
        """File is written correctly on save."""
        import yaml
        save_memory(sample_memory, repo)

        # Read file directly
        path = repo.resolve_path("data/athlete/memories.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)

        assert "_schema" in data
        assert data["_schema"]["format_version"] == "1.0.0"
        assert data["_schema"]["schema_type"] == "memories"

        assert "memories" in data
        assert len(data["memories"]) == 1
        assert data["memories"][0]["id"] == sample_memory.id


# ============================================================
# DEDUPLICATION TESTS
# ============================================================


class TestDeduplication:
    """Test deduplication algorithm."""

    def test_dedup_exact_match(self):
        """Exact matches increment occurrences."""
        existing = Memory(
            id="mem_123",
            type=MemoryType.INJURY_HISTORY,
            content="Knee pain after long runs",
            source=MemorySource.ACTIVITY_NOTE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.MEDIUM,
            occurrences=2,
            tags=["body:knee"],
        )

        new = Memory(
            id="mem_456",
            type=MemoryType.INJURY_HISTORY,
            content="Knee pain after long runs",  # Same content
            source=MemorySource.ACTIVITY_NOTE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.MEDIUM,
            occurrences=1,
            tags=["body:knee"],
        )

        result, archived = deduplicate_memory(new, [existing])

        assert result.id == existing.id  # Original ID kept
        assert result.occurrences == 3  # Incremented
        assert archived is None

    def test_dedup_type_tag_supersedes(self):
        """Same type+entity supersedes old memory."""
        old = Memory(
            id="mem_old",
            type=MemoryType.INJURY_HISTORY,
            content="Occasional knee soreness",
            source=MemorySource.ACTIVITY_NOTE,
            created_at=datetime.now() - timedelta(days=30),
            updated_at=datetime.now() - timedelta(days=30),
            confidence=MemoryConfidence.LOW,
            occurrences=1,
            tags=["body:knee"],
        )

        new = Memory(
            id="mem_new",
            type=MemoryType.INJURY_HISTORY,
            content="Chronic knee pain after runs over 15km",
            source=MemorySource.CLAUDE_CODE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.HIGH,
            occurrences=1,
            tags=["body:knee"],
        )

        result, archived = deduplicate_memory(new, [old])

        assert result.id == new.id  # New memory kept
        assert result.occurrences == 2  # Old count transferred
        assert archived is not None
        assert archived.id == old.id
        assert archived.superseded_by == new.id
        assert "body:knee" in archived.reason

    def test_dedup_confidence_upgrade(self):
        """3+ occurrences upgrade to HIGH confidence."""
        existing = Memory(
            id="mem_123",
            type=MemoryType.PREFERENCE,
            content="Prefers morning runs",
            source=MemorySource.USER_MESSAGE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.MEDIUM,
            occurrences=2,
            tags=["time:morning"],
        )

        new = Memory(
            id="mem_456",
            type=MemoryType.PREFERENCE,
            content="Prefers morning runs",
            source=MemorySource.USER_MESSAGE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.MEDIUM,
            occurrences=1,
            tags=["time:morning"],
        )

        result, archived = deduplicate_memory(new, [existing])

        assert result.occurrences == 3
        assert result.confidence == MemoryConfidence.HIGH  # Upgraded!

    def test_dedup_new_memory(self):
        """No match creates new memory."""
        existing = Memory(
            id="mem_123",
            type=MemoryType.INJURY_HISTORY,
            content="Knee pain",
            source=MemorySource.ACTIVITY_NOTE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.MEDIUM,
            tags=["body:knee"],
        )

        new = Memory(
            id="mem_456",
            type=MemoryType.PREFERENCE,
            content="Likes tempo runs",  # Different type and content
            source=MemorySource.USER_MESSAGE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.MEDIUM,
            tags=["intensity:tempo"],
        )

        result, archived = deduplicate_memory(new, [existing])

        assert result.id == new.id  # New memory returned as-is
        assert result.occurrences == 1
        assert archived is None

    def test_normalize_for_comparison(self):
        """Content normalization works correctly."""
        from sports_coach_engine.core.memory import _normalize_for_comparison

        assert _normalize_for_comparison("Left knee pain!") == "left knee pain"
        assert _normalize_for_comparison("   Left   knee   pain   ") == "left knee pain"
        assert _normalize_for_comparison("Knee pain!!!") == "knee pain"
        assert _normalize_for_comparison("KNEE PAIN") == "knee pain"

    def test_occurrence_transfer(self):
        """Occurrences transfer on supersede."""
        old = Memory(
            id="mem_old",
            type=MemoryType.CONTEXT,
            content="Works as engineer",
            source=MemorySource.USER_MESSAGE,
            created_at=datetime.now() - timedelta(days=20),
            updated_at=datetime.now() - timedelta(days=20),
            confidence=MemoryConfidence.MEDIUM,
            occurrences=4,  # Already mentioned 4 times
            tags=["context:job"],
        )

        new = Memory(
            id="mem_new",
            type=MemoryType.CONTEXT,
            content="Works as software engineer with long commute",
            source=MemorySource.CLAUDE_CODE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.HIGH,
            occurrences=1,
            tags=["context:job"],
        )

        result, archived = deduplicate_memory(new, [old])

        assert result.occurrences == 5  # 4 + 1
        assert result.confidence == MemoryConfidence.HIGH  # Upgraded


# ============================================================
# RETRIEVAL TESTS
# ============================================================


class TestRetrieval:
    """Test memory retrieval functions."""

    def test_get_memories_by_type(self, repo, sample_memories):
        """Filters by type correctly."""
        # Save all memories
        for mem in sample_memories:
            save_memory(mem, repo)

        # Get injury memories
        injuries = get_memories_by_type(MemoryType.INJURY_HISTORY, repo)
        assert len(injuries) == 2  # 2 injury memories
        assert all(m.type == MemoryType.INJURY_HISTORY for m in injuries)

        # Get preference memories
        prefs = get_memories_by_type(MemoryType.PREFERENCE, repo)
        assert len(prefs) == 1
        assert prefs[0].type == MemoryType.PREFERENCE

    def test_get_relevant_memories(self, repo, sample_memories):
        """Scores by keyword relevance."""
        # Save all memories
        for mem in sample_memories:
            save_memory(mem, repo)

        # Search for knee-related memories
        relevant = get_relevant_memories("knee pain running", repo, limit=2)

        # Should return knee memory first (best match)
        assert len(relevant) > 0
        assert "knee" in relevant[0].content.lower()

    def test_relevant_memories_tag_matching(self, repo):
        """Tag matching boosts score."""
        mem1 = Memory(
            id="mem_1",
            type=MemoryType.INJURY_HISTORY,
            content="Some injury",
            source=MemorySource.CLAUDE_CODE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.MEDIUM,
            tags=["body:knee"],
        )
        mem2 = Memory(
            id="mem_2",
            type=MemoryType.INJURY_HISTORY,
            content="Another issue",
            source=MemorySource.CLAUDE_CODE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.MEDIUM,
            tags=["body:ankle"],
        )

        save_memory(mem1, repo)
        save_memory(mem2, repo)

        # Search with tag keyword
        relevant = get_relevant_memories("knee problem", repo)

        # Knee memory should be first (tag match)
        assert relevant[0].id == mem1.id

    def test_relevant_memories_confidence_boost(self, repo):
        """HIGH confidence memories get score boost."""
        low_conf = Memory(
            id="mem_low",
            type=MemoryType.PREFERENCE,
            content="Morning runs work well",
            source=MemorySource.CLAUDE_CODE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.LOW,
            tags=["time:morning"],
        )
        high_conf = Memory(
            id="mem_high",
            type=MemoryType.PREFERENCE,
            content="Morning sessions are best",
            source=MemorySource.CLAUDE_CODE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            confidence=MemoryConfidence.HIGH,
            occurrences=5,
            tags=["time:morning"],
        )

        save_memory(low_conf, repo)
        save_memory(high_conf, repo)

        relevant = get_relevant_memories("morning", repo)

        # High confidence should rank higher
        assert relevant[0].id == high_conf.id

    def test_get_memories_with_tag(self, repo, sample_memories):
        """Retrieves by specific tag."""
        # Save all memories
        for mem in sample_memories:
            save_memory(mem, repo)

        # Get knee-related memories
        knee_mems = get_memories_with_tag("body:knee", repo)
        assert len(knee_mems) == 1
        assert "body:knee" in knee_mems[0].tags


# ============================================================
# PATTERN ANALYSIS TESTS
# ============================================================


class TestPatternAnalysis:
    """Test pattern detection from stored memories."""

    def test_analyze_patterns_recurring_injury(self, repo):
        """Detects 3+ injury mentions as pattern."""
        now = datetime.now()

        # Create 4 knee injury memories
        for i in range(4):
            mem = Memory(
                id=f"mem_{i}",
                type=MemoryType.INJURY_HISTORY,
                content=f"Knee issue {i}",
                source=MemorySource.ACTIVITY_NOTE,
                created_at=now - timedelta(days=i),
                updated_at=now - timedelta(days=i),
                confidence=MemoryConfidence.MEDIUM,
                tags=["body:knee"],
            )
            save_memory(mem, repo)

        patterns = analyze_memory_patterns(repo)

        # Should detect recurring knee pattern
        assert len(patterns) > 0
        knee_pattern = next((p for p in patterns if p.pattern_type == "recurring_injury"), None)
        assert knee_pattern is not None
        assert "knee" in knee_pattern.description.lower()
        assert knee_pattern.confidence == MemoryConfidence.HIGH
        # After deduplication, all 4 memories merge into 1 with 4 occurrences
        assert len(knee_pattern.evidence) == 1
        assert "4 occurrences" in knee_pattern.description

    def test_analyze_patterns_empty_memories(self, repo):
        """Handles no memories gracefully."""
        patterns = analyze_memory_patterns(repo)
        assert patterns == []

    def test_analyze_patterns_confidence(self, repo):
        """Pattern confidence is correct."""
        now = datetime.now()

        # Create 3 ankle memories
        for i in range(3):
            mem = Memory(
                id=f"mem_ankle_{i}",
                type=MemoryType.INJURY_HISTORY,
                content=f"Ankle problem {i}",
                source=MemorySource.ACTIVITY_NOTE,
                created_at=now - timedelta(days=i),
                updated_at=now - timedelta(days=i),
                confidence=MemoryConfidence.MEDIUM,
                tags=["body:ankle"],
            )
            save_memory(mem, repo)

        patterns = analyze_memory_patterns(repo)

        ankle_pattern = next((p for p in patterns if "ankle" in p.description), None)
        assert ankle_pattern is not None
        assert ankle_pattern.confidence == MemoryConfidence.HIGH


# ============================================================
# ARCHIVAL TESTS
# ============================================================


class TestArchival:
    """Test memory archival functions."""

    def test_archive_memory(self, repo, sample_memory):
        """Archives memory correctly."""
        # Save memory first
        save_memory(sample_memory, repo)

        # Archive it
        archived = archive_memory(
            sample_memory.id,
            "mem_replacement",
            "Test archival",
            repo,
        )

        assert archived.id == sample_memory.id
        assert archived.superseded_by == "mem_replacement"
        assert archived.reason == "Test archival"

        # Memory no longer in active list
        active = load_memories(repo)
        assert len(active) == 0

        # Memory in archived list
        archived_list = load_archived_memories(repo)
        assert len(archived_list) == 1
        assert archived_list[0].id == sample_memory.id

    def test_cleanup_archived(self, repo):
        """Deletes old archived memories."""
        now = datetime.now()

        # Create old and recent archived memories
        old_mem = Memory(
            id="mem_old",
            type=MemoryType.PREFERENCE,
            content="Old preference",
            source=MemorySource.USER_MESSAGE,
            created_at=now - timedelta(days=100),
            updated_at=now - timedelta(days=100),
            confidence=MemoryConfidence.MEDIUM,
            tags=[],
        )
        recent_mem = Memory(
            id="mem_recent",
            type=MemoryType.PREFERENCE,
            content="Recent preference",
            source=MemorySource.USER_MESSAGE,
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
            confidence=MemoryConfidence.MEDIUM,
            tags=[],
        )

        # Save and then archive them
        save_memory(old_mem, repo)
        save_memory(recent_mem, repo)

        # Manually archive with old/recent dates
        import yaml
        path = repo.resolve_path("data/athlete/memories.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        data["archived"] = [
            {
                "id": "mem_old",
                "original_content": "Old preference",
                "superseded_by": "mem_new_old",
                "archived_at": (now - timedelta(days=100)).isoformat(),
                "reason": "Old",
            },
            {
                "id": "mem_recent",
                "original_content": "Recent preference",
                "superseded_by": "mem_new_recent",
                "archived_at": (now - timedelta(days=10)).isoformat(),
                "reason": "Recent",
            },
        ]
        data["memories"] = []
        with open(path, "w") as f:
            yaml.safe_dump(data, f)

        # Cleanup with 90-day retention
        deleted = cleanup_archived(repo, retention_days=90)

        assert deleted == 1  # Only old one deleted

        # Verify
        archived = load_archived_memories(repo)
        assert len(archived) == 1
        assert archived[0].id == "mem_recent"

    def test_cleanup_preserves_recent(self, repo):
        """Keeps recent archived memories."""
        now = datetime.now()

        mem = Memory(
            id="mem_recent",
            type=MemoryType.CONTEXT,
            content="Recent context",
            source=MemorySource.USER_MESSAGE,
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
            confidence=MemoryConfidence.MEDIUM,
            tags=[],
        )

        save_memory(mem, repo)

        # Archive manually
        archive_memory("mem_recent", "mem_new", "Test", repo)

        # Cleanup
        deleted = cleanup_archived(repo, retention_days=90)

        assert deleted == 0  # Nothing deleted

        # Still in archived
        archived = load_archived_memories(repo)
        assert len(archived) == 1
