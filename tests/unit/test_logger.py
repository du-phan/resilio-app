"""
Unit tests for M14 - Conversation Logger (core/logger.py).

Tests session management, message logging, search, and cleanup functionality.
"""

import pytest
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from sports_coach_engine.core.logger import (
    MessageRole,
    log_message,
    start_session,
    end_session,
    get_session_transcript,
    search_conversations,
    cleanup_old_conversations,
    should_start_new_session,
    SearchMode,
)
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.logger import Message, Session, SessionSummary


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_repo(tmp_path):
    """Mock RepositoryIO with temp directory."""
    repo = Mock(spec=RepositoryIO)
    repo.repo_root = tmp_path
    repo.resolve_path = lambda p: tmp_path / p

    # Mock file operations
    def mock_ensure_directory(path):
        (tmp_path / path).mkdir(parents=True, exist_ok=True)

    def mock_append(path, content):
        file_path = tmp_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'a') as f:
            f.write(content)
        return None

    def mock_write_json(path, data):
        file_path = tmp_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data if isinstance(data, dict) else data.__dict__, f, default=str)
        return None

    def mock_read_json(path):
        file_path = tmp_path / path
        if not file_path.exists():
            return None
        with open(file_path) as f:
            return json.load(f)

    def mock_read_file(path):
        file_path = tmp_path / path
        if not file_path.exists():
            return None
        return file_path.read_text()

    def mock_directory_exists(path):
        return (tmp_path / path).exists() and (tmp_path / path).is_dir()

    def mock_list_files(pattern):
        return list(tmp_path.glob(pattern))

    def mock_file_exists(path):
        file_path = tmp_path / path
        return file_path.exists() and file_path.is_file()

    def mock_delete_file(path):
        file_path = tmp_path / path
        if file_path.exists():
            file_path.unlink()
        return None

    repo.ensure_directory = mock_ensure_directory
    repo.append_to_file = mock_append
    repo.write_json = mock_write_json
    repo.read_json = mock_read_json
    repo.read_file = mock_read_file
    repo.directory_exists = mock_directory_exists
    repo.list_files = mock_list_files
    repo.file_exists = mock_file_exists
    repo.delete_file = mock_delete_file

    return repo


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    return [
        Message(
            timestamp=datetime.now(),
            role=MessageRole.USER,
            content="Sync my Strava activities",
        ),
        Message(
            timestamp=datetime.now(),
            role=MessageRole.SYSTEM,
            content="Synced 5 activities. CTL is now 44.",
        ),
        Message(
            timestamp=datetime.now(),
            role=MessageRole.USER,
            content="What should I do today?",
        ),
    ]


# ============================================================
# SESSION MANAGEMENT TESTS
# ============================================================


class TestSessionManagement:
    """Test session lifecycle management."""

    def test_start_session(self, mock_repo):
        """Test starting a new session."""
        session_id = start_session(mock_repo, athlete_name="Test Athlete")

        assert session_id is not None
        assert "session_" in session_id
        # Session functionality is tested through API behavior

    def test_session_id_format(self, mock_repo):
        """Test session ID follows YYYY-MM-DD_session_NNN format."""
        session_id = start_session(mock_repo, athlete_name="Test Athlete")

        parts = session_id.split("_")
        assert len(parts) == 3  # YYYY-MM-DD, "session", NNN
        assert parts[1] == "session"
        assert parts[2].isdigit()

    def test_end_session(self, mock_repo):
        """Test ending a session generates summary."""
        start_session(mock_repo, athlete_name="Test Athlete")
        log_message(mock_repo, MessageRole.USER, "Test message")

        summary = end_session(mock_repo)

        assert summary is not None
        assert summary.message_count > 0

    def test_end_session_without_start(self, mock_repo):
        """Test ending non-existent session returns None."""
        summary = end_session(mock_repo)
        assert summary is None


class TestMessageLogging:
    """Test message logging to JSONL."""

    def test_log_message_creates_file(self, mock_repo, tmp_path):
        """Test that log_message creates JSONL file."""
        start_session(mock_repo, athlete_name="Test Athlete")
        log_message(mock_repo, MessageRole.USER, "Test message")

        # Check that transcript file was created
        transcript_files = list(tmp_path.glob("data/conversations/transcripts/**/*.jsonl"))
        assert len(transcript_files) > 0

    def test_log_message_appends_jsonl(self, mock_repo, tmp_path):
        """Test that messages are appended as JSONL (one per line)."""
        start_session(mock_repo, athlete_name="Test Athlete")
        log_message(mock_repo, MessageRole.USER, "Message 1")
        log_message(mock_repo, MessageRole.SYSTEM, "Message 2")

        transcript_files = list(tmp_path.glob("data/conversations/transcripts/**/*.jsonl"))
        assert len(transcript_files) == 1

        lines = transcript_files[0].read_text().strip().split("\n")
        assert len(lines) == 2

        # Each line should be valid JSON
        msg1 = json.loads(lines[0])
        msg2 = json.loads(lines[1])
        assert msg1["content"] == "Message 1"
        assert msg2["content"] == "Message 2"

    def test_log_message_auto_starts_session(self, mock_repo, tmp_path):
        """Test that log_message auto-starts session if needed."""
        # Don't start session manually
        log_message(mock_repo, MessageRole.USER, "Test message")

        # Session should be auto-started (verified by checking for transcript file)
        transcript_files = list(tmp_path.glob("data/conversations/transcripts/**/*.jsonl"))
        assert len(transcript_files) > 0


class TestSessionBoundaries:
    """Test session boundary detection."""

    def test_should_start_new_session_new_day(self):
        """Test new session on new day."""
        from datetime import timezone
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        assert should_start_new_session(yesterday)

    def test_should_start_new_session_timeout(self):
        """Test new session after 30min timeout."""
        from datetime import timezone
        long_ago = datetime.now(timezone.utc) - timedelta(minutes=31)
        assert should_start_new_session(long_ago)

    def test_should_not_start_new_session_recent(self):
        """Test no new session for recent activity."""
        from datetime import timezone
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert not should_start_new_session(recent)


# ============================================================
# TRANSCRIPT RETRIEVAL TESTS
# ============================================================


class TestTranscriptRetrieval:
    """Test retrieving session transcripts."""

    def test_get_session_transcript(self, mock_repo, sample_messages):
        """Test retrieving complete session transcript."""
        session_id = start_session(mock_repo, athlete_name="Test Athlete")

        for msg in sample_messages:
            log_message(mock_repo, msg.role, msg.content)

        end_session(mock_repo)

        # Retrieve transcript
        session = get_session_transcript(mock_repo, session_id)

        assert session is not None
        assert len(session.messages) == len(sample_messages)

    def test_get_nonexistent_transcript(self, mock_repo):
        """Test retrieving non-existent transcript raises SessionNotFoundError."""
        from sports_coach_engine.core.logger import SessionNotFoundError

        with pytest.raises(SessionNotFoundError, match="Invalid session ID format"):
            get_session_transcript(mock_repo, "nonexistent_session_id")


# ============================================================
# SEARCH TESTS
# ============================================================


class TestConversationSearch:
    """Test conversation search functionality."""

    def test_search_by_topic(self, mock_repo):
        """Test searching conversations by topic."""
        start_session(mock_repo, athlete_name="Test Athlete")
        log_message(mock_repo, MessageRole.USER, "Sync my Strava")
        end_session(mock_repo)

        results = search_conversations(
            mock_repo, query="strava_sync", mode=SearchMode.TOPIC
        )

        # Should find the session
        assert len(results) > 0

    def test_search_by_content(self, mock_repo):
        """Test searching conversations by content."""
        start_session(mock_repo, athlete_name="Test Athlete")
        log_message(mock_repo, MessageRole.USER, "Unique search term XYZ123")
        end_session(mock_repo)

        results = search_conversations(
            mock_repo, query="XYZ123", mode=SearchMode.CONTENT
        )

        assert len(results) > 0

    def test_search_limit(self, mock_repo):
        """Test search respects limit parameter."""
        # Create multiple sessions
        for i in range(5):
            start_session(mock_repo, athlete_name="Test Athlete")
            log_message(mock_repo, MessageRole.USER, f"Message {i}")
            end_session(mock_repo)

        results = search_conversations(
            mock_repo, query="Message", mode=SearchMode.CONTENT, limit=2
        )

        assert len(results) <= 2


# ============================================================
# CLEANUP TESTS
# ============================================================


class TestCleanup:
    """Test conversation cleanup and retention."""

    def test_cleanup_old_transcripts(self, mock_repo, tmp_path):
        """Test cleanup deletes old transcripts (>60 days)."""
        # Create old transcript
        old_date = date.today() - timedelta(days=70)
        old_transcript_dir = tmp_path / "data" / "conversations" / "transcripts" / old_date.strftime("%Y-%m")
        old_transcript_dir.mkdir(parents=True, exist_ok=True)
        old_transcript = old_transcript_dir / f"{old_date}_session_001.jsonl"
        old_transcript.write_text('{"test": "old"}')

        # Create recent transcript
        recent_transcript_dir = tmp_path / "data" / "conversations" / "transcripts" / date.today().strftime("%Y-%m")
        recent_transcript_dir.mkdir(parents=True, exist_ok=True)
        recent_transcript = recent_transcript_dir / f"{date.today()}_session_001.jsonl"
        recent_transcript.write_text('{"test": "recent"}')

        # Run cleanup
        cleanup_old_conversations(mock_repo)

        # Old should be deleted, recent should remain
        assert not old_transcript.exists()
        assert recent_transcript.exists()

    def test_cleanup_old_summaries(self, mock_repo, tmp_path):
        """Test cleanup deletes old summaries (>180 days)."""
        # Create old summary
        old_date = date.today() - timedelta(days=200)
        old_summary_dir = tmp_path / "data" / "conversations" / "summaries" / old_date.strftime("%Y-%m")
        old_summary_dir.mkdir(parents=True, exist_ok=True)
        old_summary = old_summary_dir / f"{old_date}_summary.json"
        old_summary.write_text('{"test": "old"}')

        # Create recent summary
        recent_summary_dir = tmp_path / "data" / "conversations" / "summaries" / date.today().strftime("%Y-%m")
        recent_summary_dir.mkdir(parents=True, exist_ok=True)
        recent_summary = recent_summary_dir / f"{date.today()}_summary.json"
        recent_summary.write_text('{"test": "recent"}')

        # Run cleanup
        cleanup_old_conversations(mock_repo)

        # Old should be deleted, recent should remain
        assert not old_summary.exists()
        assert recent_summary.exists()


# ============================================================
# SUMMARY GENERATION TESTS
# ============================================================


class TestSummaryGeneration:
    """Test session summary generation."""

    def test_summary_includes_message_count(self, mock_repo):
        """Test summary includes accurate message count."""
        start_session(mock_repo, athlete_name="Test Athlete")
        log_message(mock_repo, MessageRole.USER, "Message 1")
        log_message(mock_repo, MessageRole.SYSTEM, "Message 2")
        log_message(mock_repo, MessageRole.USER, "Message 3")

        summary = end_session(mock_repo)

        assert summary.message_count == 3

    def test_summary_extracts_topics(self, mock_repo):
        """Test summary extracts all topics from session."""
        start_session(mock_repo, athlete_name="Test Athlete")
        log_message(mock_repo, MessageRole.USER, "Sync my Strava")
        log_message(mock_repo, MessageRole.SYSTEM, "ACWR is 1.5")

        summary = end_session(mock_repo)

        assert "strava_sync" in summary.topics
        assert "acwr_elevated" in summary.topics

    def test_summary_duration(self, mock_repo):
        """Test summary calculates session duration."""
        start_session(mock_repo, athlete_name="Test Athlete")
        log_message(mock_repo, MessageRole.USER, "Message 1")

        # Simulate some time passing
        import time
        time.sleep(0.1)

        summary = end_session(mock_repo)

        assert summary.duration_minutes >= 0
