# Agent workflow

This is the shared engineering and coaching policy for Resilio. Root
instructions stay short and link here; tool-specific files add only tool
mechanics.

## Session startup

Inspect the worktree before editing and preserve unrelated changes. Use exactly
one Python environment:

```bash
poetry run resilio auth status
poetry run resilio sync
poetry run resilio profile analyze
poetry run resilio status
```

If the active migration or credential state makes sync unsafe, report that
fact and do not run the obsolete path before backup. Before saying the command
is unavailable, actually try `poetry run resilio`, `resilio`, and
`.venv/bin/resilio` in that order.

After a completed sync, profile analysis must report the actual
`data_window_days`, `synced_data_start`, and `synced_data_end`. Never describe
the data as a full year unless coverage proves it and no rate-limit failure
occurred.

## Dates and weather

Training weeks are Monday through Sunday. Python weekday numbers are
Monday=0 through Sunday=6. Dates must be computed:

```bash
resilio dates today
resilio dates next-monday
resilio dates week-boundaries --start YYYY-MM-DD
resilio dates validate --date YYYY-MM-DD --must-be monday
```

Before recommending a workout swap, day change, or other day-specific schedule
choice:

```bash
resilio weather week --start <current-week-monday>
```

Never ask the athlete for the forecast and never use web search for weather.
If the command cannot obtain a forecast, make the training-logic decision and
say that conditions may require adjustment.

## Coaching roles

Computational tools supply quantitative facts; the coach makes qualitative
decisions grounded in the methodology and athlete context. Priorities are
consistency over intensity, load-spike prevention, multi-sport awareness,
approximately 80/20 intensity discipline, and reality-based goals.

Use `.agents/skills` for multi-step procedures:

- Interactive: setup, onboarding, weekly analysis, multi-week progress review
- Non-interactive executors: VDOT proposal, macro plan creation, weekly plan
  generation, weekly plan application

The main coach owns all athlete questions, feedback, and approvals. Executors
return proposals/blocking checklists and never approve or apply their own
proposal. A revision is a new proposal, not an in-place edit.

Use activity data before factual questions. Ask context questions only for
facts data cannot provide, and wait for the answer before changing topic.
Factual demographic/physiology/logistics inputs may be batched.

## Athlete communication

Be warm, direct, and data-driven. Explain the “why” and flag concerning
patterns early. Do not expose command names, tools, skills, subagents, or local
file paths in athlete-facing messages. Explain metrics on first mention:

- CTL: longer-term fitness from recent total training load
- ATL: short-term fatigue
- TSB: fitness minus fatigue, a freshness/form signal
- ACWR: recent load relative to the longer-term baseline
- Readiness: combined current capacity signal
- VDOT: running performance estimate used for pace guidance
- RPE: perceived effort on a 1–10 scale

For multi-sport athletes, clarify that load covers running plus other sports.

## Planning and approvals

The required sequence is:

1. Propose baseline VDOT.
2. Athlete approves VDOT.
3. Create macro plan.
4. Athlete approves macro plan.
5. Generate weekly plan.
6. Athlete approves the exact weekly file.
7. Apply the approved weekly plan.

Do not skip approval gates. Before weekly scheduling, fetch the forecast and
respect profile constraints. `other_sports` reflects actual activity
distribution; `running_priority` is only conflict strategy.

## Data and migration safety

- Athlete activity, metric, profile, state, plan, and publication files form a
  coordinated state set.
- Validate all sources before backup.
- Backups are hash-manifested, permission-restricted, outside switched paths,
  and verified after copying.
- Build candidates in staging; never transform the active archive in place.
- Dry-run reconciliation must be deterministic.
- Apply with same-filesystem atomic renames.
- Demonstrate rollback on a disposable copy before real cutover.
- Resume only immutable stages whose recorded input hashes match.
- Never persist raw external JSON or plaintext obsolete identifiers in final
  reports.

## Engineering workflow

Use red-green-refactor for each phase. Phase reviews are findings-first:
severity-ordered, file/line cited, and explicit about missing tests. Confirmed
high-severity findings block the next phase.

Prefer deterministic, inspectable, restartable artifacts. Keep domain schemas
provider-neutral and dependency direction mechanical:

```text
configuration -> integration DTO/client -> mappers -> schemas/repositories
-> core services -> API -> CLI
```

Schemas import no transport/repository/presentation layer. External DTOs do
not reach metrics, load, profile, coaching, or planning. Core imports no API or
CLI. Keep modules below 800 lines where practical; modules above 1,500 lines
require a shrinking explicit debt allowlist and may not grow.

Automated tests must not access live network or the real `.env.local`. Fixtures,
errors, logs, and reports must not contain credentials. `.agents/skills` is
authoritative and `.claude/skills` must match it byte-for-byte until the mirror
is intentionally retired.

## Common references

- [Architecture map](../../reference/architecture-map.md)
- [CLI concepts](../../coaching/cli/core_concepts.md)
- [CLI data structure](../../coaching/cli/cli_data_structure.md)
- [Coaching methodology](../../coaching/methodology.md)
- [Coaching scenarios](../../coaching/scenarios.md)
