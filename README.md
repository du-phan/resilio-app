# Resilio

AI-powered adaptive running coach for multi-sport athletes, designed to run entirely inside
Codex or Claude Code terminal sessions with local YAML/JSON persistence.

## Quick Links

- `AGENTS.md` - Codex usage, skills, coaching protocols
- `CLAUDE.md` - Claude Code usage, coaching protocols
- `docs/coaching/cli/index.md` - CLI command index
- `docs/coaching/methodology.md` - Training methodology
- `docs/getting_started.html` - Reference landing page + guided start flow

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
poetry run resilio auth status
poetry run resilio sync
poetry run resilio profile analyze
poetry run resilio status
```

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
