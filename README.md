# Sports Coach Engine

AI-powered adaptive running coach for multi-sport athletes, running entirely in Claude Code terminal.

**Current Status**: Phase 7 Complete (M1-M14). System ready for coaching sessions.

## Setup

### Getting Started (Non-Coders)

If you are not comfortable with the terminal, use the guided setup page:

- `docs/getting_started_non_coders.html`

### 1. Install Dependencies

```bash
# Using poetry (recommended)
poetry install

# Or using pip (PEP 517)
pip install -e .
```

### 2. Create Configuration

```bash
# Create config directory
mkdir -p config

# Copy templates
cp templates/settings.yaml config/settings.yaml
cp templates/secrets.local.yaml config/secrets.local.yaml

# Edit secrets with your Strava credentials
# Get credentials from: https://www.strava.com/settings/api
vim config/secrets.local.yaml
```

**Note**: `config/secrets.local.yaml` is gitignored and will not be committed.

### 3. Run Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# With coverage
pytest tests/ -v --cov=sports_coach_engine/core
```

## Implementation Status

All 14 modules are implemented (M1-M14), including Strava sync, metrics, planning,
adaptation, and conversation logging. See `docs/IMPLEMENTATION_PROGRESS.md` for the
full module/test breakdown.

## Architecture

- **Claude Code (AI)**: User interface - understands natural language intent
- **API Layer** (`api/`): Public functions Claude Code calls
- **Core Modules** (`core/`): Internal domain logic (M1-M14)
- **Schemas** (`schemas/`): Pydantic data models
- **Data Directory** (`data/`): Local YAML/JSON persistence

See `docs/` for complete specifications.

## Development

```bash
# Run tests
poetry run pytest

# Type check
poetry run mypy sports_coach_engine

# Format code
poetry run black sports_coach_engine

# Lint
poetry run ruff sports_coach_engine
```

## Documentation

- `docs/mvp/v0_product_requirements_document.md` - Complete PRD
- `docs/mvp/v0_technical_specification.md` - Architecture spec
- `docs/specs/api_layer.md` - API documentation
- `docs/specs/modules/` - Individual module specs (M1-M14)
- `CLAUDE.md` - Guide for Claude Code integration

## License

MIT
