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
  --history-weeks <COUNT>` — approved future plan skeleton plus history that
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
- `resilio plan create-assessment-context|template-assessment|create-assessment`
  — immutable evidence gate and short return-to-running skeleton with one
  athlete-approved benchmark intent and optional typed temporary scheduling
  constraints and week-specific other-sport count proposals; no VDOT or race
  methodology is required. Context creation accepts `--constraints-file` and
  `--other-sport-file` as separate typed JSON arrays.
- `resilio plan discard-unapproved --plan-revision <ID>` — remove only the
  exact unapproved, unapplied proposal after proving it has no publication or
  completion ownership; approved plans remain closure-only.
- `resilio plan assessment-candidates|create-assessment-review|close-assessment`
  — ownership-paired whole-activity or exact-segment selection, immutable
  assessment review, and separately confirmed archival.
- `resilio plan create-cycle-review|close-cycle` — evidence-bound lifecycle
  review and immutable plan archival; completed and did-not-finish goals may
  bind exact owned completion evidence or an athlete-confirmed canonical
  activity, including its retained performance measurements.
- `resilio plan create-macro-context` — new-plan evidence gate containing all
  closed race summaries and assessment results, up to 52 compact historical
  weeks, 12 detailed recent weeks, past goal performances, current constraints,
  the active VDOT approval, and a freshness fingerprint of mutable evidence.
- `resilio plan template-macro|create-macro` — methodology-explicit macro
  skeleton creation bound to one exact macro-planning context and
  evidence-cited adaptation decisions; the latest recent week and, for
  renewals, the latest cycle summary and goal outcome are mandatory evidence.
- `resilio plan validate-week|apply-week` — exact weekly proposal boundary.
- `resilio vdot create-proposal-from-assessment --review-sha256 --out` — create
  an independently approvable VDOT proposal from one immutable closed review.
- `resilio approvals status|approve-vdot --file|approve-plan|approve-week
  --file` — one atomic planning aggregate; plan approval is plan-kind-neutral,
  while VDOT and weekly approvals bind exact file paths and byte SHA-256 values.

## Running-workout synchronization

- `resilio workout config|configure` — read or record the athlete-confirmed
  automatic run-synchronization policy.
- `resilio workout capabilities --sport run` — read-only Intervals calendar,
  Garmin forwarding, targetless, absolute-heart-rate, percent-LTHR,
  percent-max-heart-rate, and pace-target readiness, with unavailable
  capabilities reported as limitations rather than global blockers.
- `resilio workout status|reconcile --week-number <N>` — inspect without
  mutation or converge one exact applied week's running-workout desired state;
  all non-running sports are ignored by contract.
- `resilio workout resolve-drift --week-number <N> --restore-local
  --confirmation-reference <TEXT>` — replace exact owned remote drift only
  after explicit athlete confirmation. There is no automatic remote adoption.

`resilio plan apply-week` returns the successful local application and its
automatic run-synchronization outcome in one typed result. A provider failure
does not undo or hide the local commit. Date-only runs use provider local
midnight while remaining date-only in local approval state.

Do not use removed local metrics, analysis, risk, recommendation, enrichment,
guardrail, performance-baseline, or historical-publication command families.
Their responsibilities are now native provider evidence, typed coaching
context, methodology-guided judgment, and focused plan validation.
