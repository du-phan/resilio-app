"""
sce memory - Manage athlete memories and insights.

Memories are durable facts about the athlete that persist across coaching sessions.
Types: INJURY_HISTORY, PREFERENCE, CONTEXT, INSIGHT, TRAINING_RESPONSE.
"""

from typing import Optional
from datetime import datetime
import uuid

import typer

from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core.memory import (
    save_memory,
    load_memories,
    get_memories_by_type,
    get_relevant_memories,
)
from sports_coach_engine.schemas.memory import Memory, MemoryType, MemorySource, MemoryConfidence
from sports_coach_engine.cli.errors import create_error_envelope, create_success_envelope
from sports_coach_engine.cli.output import output_json


# Create memory subcommand app
app = typer.Typer(
    name="memory",
    help="Manage athlete memories and insights",
    no_args_is_help=True,
)


def memory_add_command(
    ctx: typer.Context,
    memory_type: str = typer.Option(
        ...,
        "--type",
        help="Memory type: INJURY_HISTORY, PREFERENCE, CONTEXT, INSIGHT, TRAINING_RESPONSE",
    ),
    content: str = typer.Option(
        ...,
        "--content",
        help="Memory content (e.g., 'Left knee pain after long runs over 18km')",
    ),
    tags: Optional[str] = typer.Option(
        None,
        "--tags",
        help="Comma-separated tags (e.g., 'body:knee,trigger:long-run')",
    ),
    confidence: str = typer.Option(
        "medium",
        "--confidence",
        help="Confidence level: low, medium, high",
    ),
) -> None:
    """Add a new memory manually.

    Memories are automatically deduplicated - if similar content exists, occurrences
    will be incremented instead of creating a duplicate.

    Examples:
        sce memory add --type INJURY_HISTORY \\
            --content "Left knee pain after long runs over 18km" \\
            --tags "body:knee,trigger:long-run" \\
            --confidence high

        sce memory add --type TRAINING_RESPONSE \\
            --content "Consistently skips Tuesday runs" \\
            --tags "schedule:tuesday,pattern:skip" \\
            --confidence high

        sce memory add --type CONTEXT \\
            --content "Works late Mondays, prefers morning runs Tue-Fri" \\
            --tags "schedule:work" \\
            --confidence medium
    """
    # Validate memory type
    try:
        mem_type = MemoryType[memory_type.upper()]
    except KeyError:
        valid_types = [t.name for t in MemoryType]
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid memory type: {memory_type}. Valid types: {', '.join(valid_types)}",
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Validate confidence
    try:
        mem_confidence = MemoryConfidence[confidence.upper()]
    except KeyError:
        valid_confidences = [c.name for c in MemoryConfidence]
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid confidence: {confidence}. Valid: {', '.join(valid_confidences)}",
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Parse tags
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Create memory
    now = datetime.now()
    memory = Memory(
        id=f"mem_{uuid.uuid4().hex[:8]}",
        type=mem_type,
        content=content,
        source=MemorySource.CLAUDE_CODE,
        confidence=mem_confidence,
        tags=tag_list,
        created_at=now,
        updated_at=now,
    )

    # Save memory
    try:
        repo = RepositoryIO()
        final_memory, archived_memory = save_memory(memory, repo)

        # Build response
        result_message = f"Memory saved: {final_memory.type}"
        if archived_memory:
            result_message += f" (superseded old memory: {archived_memory.id})"
        elif final_memory.occurrences > 1:
            result_message += f" (duplicate detected, occurrences: {final_memory.occurrences})"

        envelope = create_success_envelope(
            message=result_message,
            data={
                "memory": final_memory.model_dump(mode='json'),
                "archived": archived_memory.model_dump(mode='json') if archived_memory else None,
            },
        )

    except Exception as e:
        envelope = create_error_envelope(
            error_type="unknown",
            message=f"Failed to save memory: {str(e)}",
        )
        output_json(envelope)
        raise typer.Exit(code=1)

    output_json(envelope)
    raise typer.Exit(code=0)


def memory_list_command(
    ctx: typer.Context,
    memory_type: Optional[str] = typer.Option(
        None,
        "--type",
        help="Filter by memory type (e.g., INJURY_HISTORY)",
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        help="Filter by tag (e.g., 'body:knee')",
    ),
) -> None:
    """List all memories, optionally filtered by type or tag.

    Examples:
        sce memory list
        sce memory list --type INJURY_HISTORY
        sce memory list --tag "body:knee"
    """
    try:
        repo = RepositoryIO()
        memories = load_memories(repo)

        # Apply filters
        if memory_type:
            try:
                mem_type = MemoryType[memory_type.upper()]
                memories = get_memories_by_type(mem_type, repo)
            except KeyError:
                valid_types = [t.name for t in MemoryType]
                envelope = create_error_envelope(
                    error_type="validation",
                    message=f"Invalid memory type: {memory_type}. Valid types: {', '.join(valid_types)}",
                )
                output_json(envelope)
                raise typer.Exit(code=5)

        if tag:
            memories = [m for m in memories if tag in m.tags]

        # Build response
        envelope = create_success_envelope(
            message=f"Found {len(memories)} memories",
            data={
                "memories": [m.model_dump(mode='json') for m in memories],
                "count": len(memories),
            },
        )

    except Exception as e:
        envelope = create_error_envelope(
            error_type="unknown",
            message=f"Failed to load memories: {str(e)}",
        )
        output_json(envelope)
        raise typer.Exit(code=1)

    output_json(envelope)
    raise typer.Exit(code=0)


def memory_search_command(
    ctx: typer.Context,
    query: str = typer.Option(
        ...,
        "--query",
        help="Search query (searches memory content)",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        help="Maximum number of results to return",
    ),
) -> None:
    """Search memories by content relevance.

    Uses keyword-based relevance scoring to find matching memories.

    Examples:
        sce memory search --query "knee pain"
        sce memory search --query "injury" --limit 5
    """
    try:
        repo = RepositoryIO()

        # Use get_relevant_memories for intelligent search
        relevant_memories = get_relevant_memories(
            context=query,
            repo=repo,
            limit=limit,
        )

        envelope = create_success_envelope(
            message=f"Found {len(relevant_memories)} memories matching '{query}'",
            data={
                "memories": [m.model_dump(mode='json') for m in relevant_memories],
                "count": len(relevant_memories),
                "query": query,
            },
        )

    except Exception as e:
        envelope = create_error_envelope(
            error_type="unknown",
            message=f"Failed to search memories: {str(e)}",
        )
        output_json(envelope)
        raise typer.Exit(code=1)

    output_json(envelope)
    raise typer.Exit(code=0)


# Register commands
app.command(name="add", help="Add a new memory manually")(memory_add_command)
app.command(name="list", help="List all memories")(memory_list_command)
app.command(name="search", help="Search memories by content")(memory_search_command)
