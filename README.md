# Resilio

AI-powered adaptive coach for multi-sport athletes, designed to run entirely inside
Codex or Claude Code terminal sessions with local YAML/JSON persistence.

**How to use Resilio:**

> Open this folder in **Claude Code** or **Codex**, then chat with the assistant.
>
> The assistant acts as your AI coach. Resilio provides the tools, training methodology, and local data the coach uses to guide your training.

**Methodology focus (current):** Resilio is currently strongest on running methodology, grounded in frameworks from Daniels' _Running Formula_, Pfitzinger's _Advanced Marathoning_, Fitzgerald's _80/20 Running_, and FIRST's _Run Less, Run Faster_.

## Start Here (2 steps)

1. Open this folder in **Claude Code** or **Codex**.
2. Start chatting with the assistant (for example: "Let's get started"). The assistant guides setup, authentication, sync, and profile onboarding.

## Quick Links

- `AGENTS.md` - Codex usage, skills, coaching protocols
- `CLAUDE.md` - Claude Code usage, coaching protocols
- `docs/coaching/cli/index.md` - CLI command index
- `docs/coaching/methodology.md` - Training methodology
- `docs/coaching/scenarios.md` - Practical coaching scenarios

## Coach Quickstart (Codex/Claude)

```bash
# Install dependencies (Poetry recommended)
poetry install

# Create config
mkdir -p config
cp templates/settings.yaml config/settings.yaml
cp templates/secrets.local.yaml config/secrets.local.yaml

# Add Strava credentials (edit with your preferred editor)
${EDITOR:-vim} config/secrets.local.yaml

# Core session flow
poetry run resilio auth status
poetry run resilio sync
poetry run resilio profile analyze
poetry run resilio status
```

You can run those commands manually, or simply start chatting and let the assistant guide the same flow.
For full coaching workflows and behavior rules, see `AGENTS.md` and `CLAUDE.md`.

## Developer Quickstart

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Type check
poetry run mypy resilio

# Format
poetry run black resilio

# Lint
poetry run ruff resilio
```

## Architecture Snapshot

- `resilio/cli/` - Typer CLI entrypoints (`resilio`)
- `resilio/core/` - Domain logic (metrics, planning, adaptation)
- `resilio/api/` - Public API layer for agents
- `resilio/schemas/` - Pydantic models
- `data/` - Local persistence (gitignored)

## Skills

Skills live in `.agents/skills` (Codex) and `.claude/skills` (Claude Code). For selection rules and workflows, see `AGENTS.md` and `CLAUDE.md`.

## License

MIT
