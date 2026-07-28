# Resilio repository guide

Resilio is a local, AI-assisted running coach for multi-sport athletes. It
stores athlete state in YAML/JSON and computes load, readiness, profile
analysis, and coaching locally.

## Start here

1. Read [docs/index.md](docs/index.md).
2. Read the active plan linked from that index.
3. Inspect `git status --short --branch` and preserve user-owned changes.
4. Use one environment for the whole session. Prefer `poetry run`; never mix
   Poetry and `.venv` commands.
5. Before claiming a CLI command is unavailable, try `poetry run resilio`,
   then `resilio`, then `.venv/bin/resilio`.

## Repository map

- `resilio/schemas/`: provider-neutral persisted/domain contracts
- `resilio/integrations/`: strict external DTO and transport boundaries
- `resilio/core/`: deterministic calculations and application services
- `resilio/api/`: presentation-neutral callable surface
- `resilio/cli/`: Typer commands and JSON envelopes
- `data/`: ignored athlete state; never mutate without validation and backup
- `.agents/skills/`: authoritative repeatable coaching procedures
- `.claude/skills/`: mechanically validated mirror during the current migration
- `docs/reference/architecture-map.md`: dependency and ownership map
- `docs/guides/development/agent-workflow.md`: shared engineering/coaching rules

## Safety constraints

- Training weeks are always Monday–Sunday.
- Never calculate dates mentally. Use `resilio dates ...`.
- Before day-specific workout advice or a schedule change, use
  `resilio weather week --start <week-monday>`. Do not use web weather.
- Synced activity data is authoritative for factual training questions.
- Treat `data/activities`, metrics, profile, sync state, plans, and publication
  manifests as one coordinated state set during migrations.
- Never expose credentials or raw external payloads in logs, tests, reports, or
  documentation.
- Never mutate an external calendar event without local and remote ownership
  proof.

## Coaching workflow

Use the matching skill for onboarding, weekly analysis, multi-week progress,
VDOT proposal, macro planning, weekly generation, or weekly application.
The coach owns all athlete questions and approvals; executor skills do not ask
questions. Explain coaching outcomes and metrics in athlete language without
exposing commands, tools, skills, or file paths.

Full policy and command references:
[agent workflow](docs/guides/development/agent-workflow.md) and
[coaching CLI index](docs/coaching/cli/index.md).
