# Coaching CLI

`poetry run resilio --help` and each command’s `--help` output are the option
authority. Commands return JSON envelopes.

## Setup and synchronized state

- `resilio init` — initialize configuration and local state directories.
- `resilio auth status` — validate Intervals.icu account access.
- `resilio sync [--full] [--confirm-deletions]` — coordinated completed-state
  import and reconciliation.
- `resilio sync --status` — inspect lock, progress, and checkpoint state.
- `resilio status` — current synchronized coaching context.
- `resilio activity list|search` — inspect canonical completed activities;
  list output includes exact elapsed seconds, activity timezone, canonical
  identity, and source fingerprint for evidence binding.
- `resilio activity-review ...` — review conservative match, quarantine, and
  deletion candidates.

## Typed coaching context

- `resilio coach context --week-start <MONDAY> --as-of <DATE>` — activities,
  separate run/other-sport exposure, exact adherence, source-zone evidence,
  training state, signal-first recovery, and coverage.
- `resilio coach history --as-of <DATE> --weeks <COUNT>` — typed multi-week
  evidence with explicit target-week and evidence-window boundaries.
- `resilio coach planning-context --week <NUMBER> --evidence-as-of <DATE>
  --history-weeks <COUNT>` — approved future macro skeleton plus history that
  ends on a separate, non-future evidence date.
- `resilio today [--date <DATE>]` — date-scoped planned and completed facts.
- `resilio week` — current weekly facts.
- `resilio dates ...` — authoritative date calculations.
- `resilio weather week --start <MONDAY>` — Monday-Sunday planning weather.

## Athlete-owned facts

- `resilio profile create|get|set` — strict athlete profile v2; create requires
  the IANA training timezone used to resolve scheduled local times.
- `resilio profile candidates [--as-of-date <DATE>]` — read-only provider
  threshold heart-rate, threshold-speed, power, and VO2-max candidates with
  provenance and explicit units.
- `resilio profile set-personal-best` — exact distance, elapsed time, and date.
- `resilio profile add-sport|remove-sport|pause-sport|resume-sport` —
  other-sport commitments.
- `resilio goal ...` — athlete goal.
- `resilio memory ...` — athlete-confirmed durable context.
- `resilio vdot calculate|predict|estimate-current` — athlete-local
  race-performance equivalence; dated calculations require an explicit
  `--as-of-date`, with no training-pace, easy-pace, or provider-VO2 inference.

## Planning and approvals

- `resilio plan show|status|week|next-unpopulated` — current plan reads.
- `resilio plan create-cycle-review|close-cycle` — evidence-bound lifecycle
  review and immutable plan archival; completed and did-not-finish goals may
  bind exact owned completion evidence or an athlete-confirmed canonical
  activity, including its retained performance measurements.
- `resilio plan create-macro-context` — new-plan evidence gate containing all
  closed-cycle summaries, up to 52 compact historical weeks, 12 detailed
  recent weeks, past goal performances, current constraints, the active VDOT
  approval, and a freshness fingerprint of the mutable source evidence.
- `resilio plan template-macro|create-macro` — methodology-explicit macro
  skeleton creation bound to one exact macro-planning context and
  evidence-cited adaptation decisions; the latest recent week and, for
  renewals, the latest cycle summary and goal outcome are mandatory evidence.
- `resilio plan validate-week|apply-week` — exact weekly proposal boundary.
- `resilio approvals status|approve-vdot --file|approve-macro|approve-week
  --file` — one atomic planning aggregate; VDOT and weekly approvals bind exact
  file paths and byte SHA-256 values.

## Calendar publication

- `resilio workout publish|publish-plan|delete` — ownership-proven structured
  workout mutation and provider readback; publication accepts only locally
  applied, still-approved plan/macro/week/workout identities.

Do not use removed local metrics, analysis, risk, recommendation, enrichment,
guardrail, performance-baseline, or historical-publication command families.
Their responsibilities are now native provider evidence, typed coaching
context, methodology-guided judgment, and focused plan validation.
