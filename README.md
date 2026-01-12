# Sports Coach Engine

AI-powered adaptive running coach for multi-sport athletes, running entirely in Claude Code terminal.

**Current Status**: Phase 1 Core Infrastructure Complete (M2 Config, M3 Repository I/O, M4 Profile Service)

## Setup

### 1. Install Dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using poetry
poetry install
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

## Phase 1 Complete (M2, M3, M4)

Phase 1 implements the foundational infrastructure:

✅ **M2 - Config & Secrets**: Configuration loading and validation
✅ **M3 - Repository I/O**: File I/O with atomic writes and locking
✅ **M4 - Athlete Profile Service**: Profile CRUD, VDOT calculation, constraint validation

**55 tests passing** (8 config + 18 repository + 24 profile + 5 integration)

### What's Implemented

- Configuration loading from `config/settings.yaml` and `config/secrets.local.yaml`
- YAML read/write with schema validation
- Atomic writes (temp file + rename) to prevent corruption
- File locking to prevent concurrent access issues
- Athlete profile CRUD operations (load, save, update, delete)
- VDOT calculation from race times (Jack Daniels' formula)
- Constraint validation (4 rules per M4 spec)

### What's Next (Phase 2+)

- M5: Strava Integration (OAuth, activity sync)
- M6-M8: Activity processing pipeline (normalization, RPE analysis, load calculation)
- M9: Metrics Engine (CTL/ATL/TSB, ACWR, readiness)
- M10-M11: Plan generation and adaptation
- M12-M14: Data enrichment, memory, conversation logging
- API layer for Claude Code integration

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