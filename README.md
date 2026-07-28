# Resilio

Resilio is a local AI-assisted running coach for multi-sport athletes. It
imports completed activities through Intervals.icu, computes load/readiness
locally, adapts plans using the athlete’s complete training context, and can
publish owned run and cycling workouts back to the external calendar.

Open this repository in Claude Code or Codex and ask to get started. The
assistant guides environment setup, account validation, sync, profile
onboarding, goals, and training plans.

## Setup

```bash
poetry install
poetry run resilio init
```

Add the personal Intervals.icu API key to the permission-restricted
`.env.local` created by `resilio init`:

```text
INTERVALS_ICU_API_KEY=your-personal-api-key
```

Then validate and import:

```bash
poetry run resilio auth status
poetry run resilio sync
poetry run resilio profile analyze
poetry run resilio status
```

Garmin, Wahoo, climbing, bouldering, yoga, strength, and other recorded or
manual activities should flow into Intervals.icu first. Resilio retains its
canonical local history and remains authoritative for coaching calculations.

Free Intervals.icu accounts should be opened at least once every 90 days so
the account does not become dormant and stop processing new files.

## Development

```bash
poetry run pytest
poetry run mypy resilio
poetry run ruff check resilio tests
```

Start with [AGENTS.md](AGENTS.md) and the
[documentation index](docs/index.md). The architecture is summarized in
[docs/reference/architecture-map.md](docs/reference/architecture-map.md).

Skills are authored in `.agents/skills`; `.claude/skills` is a mechanically
validated discovery mirror.

## License

MIT
