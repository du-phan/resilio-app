---
name: running-workout-publication
description: Inspect and reconcile one exact applied week's running-workout desired state with Intervals.icu, using semantic readback, owned drift protection, and honest Garmin-forwarding status. Use after weekly application, for explicit sync requests, retries, or diagnosis.
---

# Synchronize approved running workouts

Operate non-interactively on exact applied-week authority. Never generate,
revise, approve, or repair workout content. Ignore bouldering and every
non-running session. The athlete chooses a workout from the watch list; this
procedure never schedules or starts a workout on the watch.

## Preconditions

Read the athlete-confirmed automation policy and current provider capability:

```bash
poetry run resilio workout config
poetry run resilio workout capabilities --sport run
poetry run resilio plan week --week <WEEK_NUMBER>
poetry run resilio approvals status
```

Require an approved plan, a consumed exact weekly approval, and an active
applied-week audit. Every future run must contain a typed
`structured_workout`. Date-only runs are valid and use provider local midnight
without claiming that midnight was athlete-approved.

Interpret capabilities precisely:

- targetless runs need no threshold pace;
- percent-LTHR targets require Run LTHR;
- percent-max-heart-rate targets require Run maximum heart rate;
- pace targets require both Run threshold pace and pace zones;
- one published run may use at most one target mode;
- missing Garmin connection, forwarding, or Run filter affects Garmin status,
  not Intervals calendar ownership;
- Wahoo state is outside this procedure and never blocks it.

Do not calculate or change threshold pace. A five-kilometre benchmark alone
does not authorize that setting. The coach reassesses whether threshold-specific
evidence is needed before the first pace-targeted phase.

## Inspect desired state

```bash
poetry run resilio workout status --week-number <WEEK_NUMBER>
```

Status performs no mutation. Require `reconciliation_safe: true` before an
ordinary reconcile. Report every blocker exactly; do not silently remove
targets, invent a start time, or synchronize only the runs that happen to pass.

## Reconcile and verify

```bash
poetry run resilio workout reconcile --week-number <WEEK_NUMBER>
```

Reconciliation updates retained owned identities in place, creates missing
future runs, and deletes only removed future, uncompleted, exactly owned runs.
Past or completed owned events remain in Intervals for completion pairing and
adherence. Non-running events and unowned workouts are never mutated.
Intervals controls its rolling Garmin export window and may remove older
downstream workouts to limit clutter. Resilio cannot inspect or delete the
watch's local workout list and never claims that cleanup occurred.

Success requires exact remote ownership and semantic readback of the ordered
executable steps: repetition expansion, time/distance termination, explicit
step intensity, athlete cue, and target. Provider-estimated duration is not
compared for a distance-terminated step. A nonempty but incomplete
`workout_doc` is a typed provider-semantics failure.

Names describe reusable executable content, not calendar placement: for
example `Easy4K`, `Tempo2x7m`, `Interval6x800m`, or `5KTest`. Do not use opaque
abbreviations. Moving a workout to a different day must not rename it.
Identical executable structures may share one name; compact variant suffixes
distinguish genuinely different structures with the same summary.

Remote failures do not roll back the already-applied local week. If the report
is partial, identify verified and failed items; the same reconcile command is
the idempotent retry. Never delete or overwrite remote drift during ordinary
reconciliation.

If status reports owned remote drift, return the blocker to the coach. Only
after the coach supplies explicit athlete confirmation may the executor use:

```bash
poetry run resilio workout resolve-drift \
  --week-number <WEEK_NUMBER> \
  --restore-local \
  --confirmation-reference "<ATHLETE_CONFIRMATION>"
```

This records the confirmation before replacing exact owned remote content.
There is no automatic adopt-remote strategy.

Report Intervals synchronization and Garmin forwarding separately:

- `eligible_unverified` means Intervals is configured to forward the workout
  and has reported no Garmin push error; it does not prove Garmin Connect or the
  watch received it;
- `not_configured` means the observed Garmin connection/settings/filter do not
  establish forwarding eligibility;
- `provider_error_observed` means Intervals reported a Garmin push error.

Never claim physical watch delivery without athlete confirmation. Intervals-
origin workouts being non-editable in Garmin Connect is expected; edits belong
in the approved local plan and are propagated through reconciliation. Garmin's
workout-list preview is target-oriented: `--` on a targetless run does not prove
that its distance/time steps are missing. Use exact Intervals semantic readback
for that determination and ask the athlete to inspect the opened workout or
watch step list when physical-device confirmation is needed.
