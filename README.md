# Sports Coach Engine

AI-powered adaptive running coach for multi-sport athletes, designed to run entirely inside
Codex or Claude Code terminal sessions with local YAML/JSON persistence.

## Quick Links

- `AGENTS.md` - Codex usage, skills, coaching protocols
- `CLAUDE.md` - Claude Code usage, coaching protocols
- `docs/coaching/cli/index.md` - CLI command index
- `docs/coaching/methodology.md` - Training methodology
- `docs/getting_started_non_coders.html` - Reference landing page + guided start flow

## Coach Quickstart (Codex/Claude)

```bash
# Install dependencies (Poetry recommended)
poetry install

# Create config
mkdir -p config
cp templates/settings.yaml config/settings.yaml
cp templates/secrets.local.yaml config/secrets.local.yaml

# Add Strava credentials
vim config/secrets.local.yaml

# Core session flow
poetry run sce auth status
poetry run sce sync
poetry run sce profile analyze
poetry run sce status
```

For full coaching workflows and behavior rules, see `AGENTS.md` and `CLAUDE.md`.

## Developer Quickstart

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Type check
poetry run mypy sports_coach_engine

# Format
poetry run black sports_coach_engine

# Lint
poetry run ruff sports_coach_engine
```

## Architecture Snapshot

- `sports_coach_engine/cli/` - Typer CLI entrypoints (`sce`)
- `sports_coach_engine/core/` - Domain logic (metrics, planning, adaptation)
- `sports_coach_engine/api/` - Public API layer for agents
- `sports_coach_engine/schemas/` - Pydantic models
- `data/` - Local persistence (gitignored)

## Skills

Skills live in `.agents/skills` (Codex) and `.claude/skills` (Claude Code). For selection rules and workflows, see `AGENTS.md` and `CLAUDE.md`.

## License

MIT
