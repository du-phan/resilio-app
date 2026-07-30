# Agent workflow

This is the shared engineering and coaching policy for Resilio.

## Session startup

1. Read [the documentation index](../../index.md) and any linked active plan.
2. Inspect `git status --short --branch`; preserve unrelated and user-owned
   changes.
3. Use one environment for the entire session. Prefer `poetry run`.
4. Before declaring the CLI unavailable, try `poetry run resilio`, then
   `resilio`, then `.venv/bin/resilio`.
5. Do not access a live network or `.env.local` from automated tests.

## Evidence and coaching

Synchronized completed activity data is authoritative for factual training
questions. Intervals.icu native analysis remains authoritative for completed
aerobic load, fitness/fatigue history, thresholds, and zones. Athlete profile,
goals, VDOT approval, methodology, coaching decisions, and plan approvals
remain locally owned.

Never replace missing values with estimates. Keep aerobic load points,
session-RPE arbitrary units, run exposure, other-sport exposure, and wellness
separate. Interpret recovery signal by signal; do not compute a composite
readiness score or injury probability.

Use the matching skill for onboarding, weekly analysis, multi-week review,
plan renewal, VDOT proposal, macro planning, weekly generation, and weekly
application. The main coach owns athlete questions and approvals. Executor
skills do not approve or apply their own proposals.

## Dates and weather

Training weeks are Monday-Sunday. Never calculate dates mentally:

```bash
poetry run resilio dates today
poetry run resilio dates next-monday
poetry run resilio dates week-boundaries --start YYYY-MM-DD
poetry run resilio dates validate --date YYYY-MM-DD --must-be monday
```

Before day-specific advice, a workout swap, or a schedule mutation:

```bash
poetry run resilio weather week --start <WEEK_MONDAY>
```

Do not use web weather. If the forecast is unavailable, state the uncertainty.

## Planning and approvals

Use one named, versioned primary methodology for the entire macro plan. Follow
the [methodology reference](../../coaching/methodology.md) and the selected
source in `docs/training_books/`.

The required sequence is:

1. propose baseline VDOT;
2. record athlete VDOT approval;
3. create the immutable macro-planning evidence context;
4. create and present the methodology-explicit, evidence-cited macro plan;
5. record macro approval;
6. generate a new exact weekly file;
7. bind athlete approval to that path and SHA-256;
8. apply those unchanged bytes and verify approval consumption.

Before a successor plan, synchronize through the evidence date, record the
athlete-confirmed goal outcome, create and present an immutable cycle review,
close and archive the active plan, then reassess profile, goal, and VDOT before
creating the successor context. A plan cannot be silently overwritten, and a
new VDOT cannot replace the dependency of an active plan.

The cycle review retains an exact completed or did-not-finish goal activity,
including its measured performance fields, when the athlete identifies one.
Closure re-proves the active-plan bytes and mutable training-evidence
fingerprint. Macro creation likewise re-proves its context fingerprint and
requires decisions to cite the latest recent week plus the latest closed-plan
summary and goal outcome for a renewal.

Every transition timestamp must follow that sequence; persisted state rejects
pre-approval plans, pre-context macro plans, pre-macro weekly approvals,
pre-approval applications, and closure records that contradict their source
revision or cycle review. Any revision is a new proposal and a new approval.

## Engineering workflow

Use red-green-refactor for behavior changes:

1. write the smallest test that fails for the right reason;
2. implement the general contract, not an example-specific branch;
3. refactor only under green tests;
4. probe important pure functions with `poetry run python -c`, including
   missing, zero, invalid, future-date, boundary, and sibling cases.

Base root-cause claims on source code, tests, state shape, or privacy-safe logs.
If confidence is below 95 percent, add targeted redacted diagnostics and keep
investigating. Do not add speculative fallbacks, dual-read compatibility,
aliases, or hot fixes.

Keep dependency direction mechanical:

```text
schemas <- integration DTOs/mappers <- repositories/core <- API <- CLI
```

Prefer focused packages and responsibility-specific modules. Production
modules are limited to 600 lines and functions to 120 lines, with no debt
allowlist; split cohesive responsibilities before adding behavior. Names for
physical quantities include units. Comments and docstrings explain contracts
or non-obvious reasons, not line-by-line mechanics.

For a non-trivial implementation phase, run two independent findings-first
reviews after the implementation pass. Give both reviewers the same evidence
scope, resolve all high-severity findings, and repeat the review if a material
fix changes the architecture or contract.

## Migration safety

Treat activities, wellness, sport settings, sync state, profile, plans,
approvals, and publication/completion manifests as coordinated state.

- Validate sources before backup.
- Create a permission-restricted, hash-verifiable backup outside switched
  paths.
- Transform only in staging.
- Reconcile identities, path sets, counts, and digests deterministically.
- Demonstrate rollback on a disposable copy.
- Switch same-filesystem paths atomically where possible.
- Never persist raw external payloads, credentials, or obsolete identifiers in
  reports and fixtures.
- Maintain mode `0700` on athlete-state directories and `0600` on
  athlete-state files at every write boundary, not only during initialization
  or migration.

Temporary legacy readers exist only inside a one-shot offline migration and are
deleted after the verified cutover.

## Completion gate

Completion requires:

```bash
poetry run pytest -q
poetry run ruff check resilio tests
poetry run mypy resilio
poetry run pytest -q tests/architecture
```

Also require targeted edge probes, documentation-link validation,
byte-identical `.agents/skills` and `.claude/skills`, deterministic migration
reconciliation, and demonstrated rollback. A focused green test is not
completion while a broader relevant gate is red.

See the [architecture map](../../reference/architecture-map.md),
[Intervals.icu reference](../../reference/intervals-icu-integration.md), and
[CLI index](../../coaching/cli/index.md).
