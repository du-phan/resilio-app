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

Use the matching skill for onboarding, baseline-assessment planning and review,
weekly analysis, multi-week review, plan renewal, VDOT proposal, race-macro
planning, weekly generation, and weekly application. The main coach owns
athlete questions and approvals. Executor skills do not approve or apply their
own proposals.

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

Race-macro plans use one named, versioned primary methodology. Follow the
[methodology reference](../../coaching/methodology.md) and the selected source
in `docs/training_books/`. A baseline-assessment plan is a separate,
methodology-free lifecycle for establishing evidence after missing, disputed,
conflicting, or stale baseline evidence; it never requires an invented VDOT.

The race-planning sequence is:

1. propose baseline VDOT;
2. record athlete VDOT approval;
3. create the immutable macro-planning evidence context;
4. create and present the methodology-explicit, evidence-cited macro plan;
5. record plan approval;
6. generate a new exact weekly file;
7. bind athlete approval to that path and SHA-256;
8. apply those unchanged bytes and verify approval consumption.

The baseline-assessment sequence is:

1. exclude medical rehabilitation and record the exact assessment reason;
2. create the immutable assessment-planning context;
3. create and separately approve a short return plan with one timed-distance
   benchmark intent;
4. generate, approve, and apply exact weekly files;
5. publish the approved benchmark as a structured calendar-day or exactly
   timed run and require exact owned completion pairing;
6. let the athlete select either the whole paired activity or an exact
   canonical segment and confirm the official benchmark distance;
7. create the immutable review, separately confirm closure, and archive the
   assessment;
8. propose VDOT from that closed review and record a separate VDOT approval.

Five kilometers is the default benchmark distance. A longer benchmark requires
explicit athlete confirmation plus an evidence-backed rationale. Exact weekly
approval may retain a date-only workout; calendar publication represents it at
provider local midnight without treating midnight as an approved start time.
Weekly application returns local commit and automatic run-synchronization
outcomes separately. Enabled synchronization reconciles the exact applied week
immediately; a provider failure never rolls back or obscures the local commit.
Ordinary reconciliation blocks owned remote drift. Restore-local requires a
separate athlete-confirmation reference and never implies Garmin watch delivery.
Cycle-specific holidays and other unavailable date ranges belong in typed
assessment scheduling constraints with an athlete-confirmation reference, not
inferred from weekday availability or silently written into the durable profile.
When that shortened week makes a durable other-sport commitment infeasible,
the coach may propose a week-and-sport-specific session-count override with an
explicit rationale. It becomes binding only with whole-plan approval; do not
mislabel the proposal as a prior athlete confirmation or cram the normal count
into the remaining days.

An unapproved, unapplied plan proposal may be discarded for revision only by
its exact plan revision ID and only after local publication and completion
manifests prove that no ownership record exists. Approved plans always require
the normal evidence-backed closure lifecycle.

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

Every transition timestamp must follow its sequence; persisted state rejects
pre-approval plans, pre-context race plans, pre-plan weekly approvals,
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
