# Sports Coach Engine

AI-powered adaptive running coach for multi-sport athletes, running entirely in Claude Code terminal.

## Quick Start

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Initialize data directory:
   ```bash
   python -m sports_coach_engine.init
   ```

3. Connect to Strava:
   ```bash
   # Will guide you through OAuth flow
   python -m sports_coach_engine.strava_connect
   ```

4. Start coaching session:
   ```bash
   # Open Claude Code in this directory
   # Claude will use the API to provide coaching
   ```

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