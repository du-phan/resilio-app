---
name: plan-renewal
description: Review and close an active training cycle from exact plan, activity, course-result, adherence, multisport, recovery, and coverage evidence, then prepare the immutable historical context for its successor. Use when an athlete asks for a new or replacement plan, reaches a plan horizon, changes goals midcycle, or stops a cycle early.
---

# Renew a training plan

The main coach owns every athlete question and confirmation. Do not invent a
goal result, infer a completed course from date or distance, or create the
successor before the current cycle is reviewed and closed.

## Preconditions

Require:

- one active plan and its exact approval/application history;
- a coordinated sync through the requested evidence date;
- athlete confirmation of the goal outcome;
- reconciliation or deletion of owned future calendar workouts after the
  effective closure date.

Use `never_started` only when the plan has no reviewed training week.
Use `completed_horizon` only when the effective end equals the planned end.
Use `superseded_midcycle` for an athlete-requested replacement and
`stopped_early` when training ceased without an immediate replacement.

## Review and closure

1. Establish exact dates and refresh factual state:

   ```bash
   poetry run resilio dates today
   poetry run resilio plan show
   poetry run resilio approvals status
   poetry run resilio sync
   poetry run resilio sync --status
   ```

2. Ask the athlete whether the goal was completed, not started, not finished,
   cancelled, or deferred. General-fitness cycles use `not_applicable`. For a
   completed event, identify one exact synchronized canonical activity. For a
   did-not-finish result, retain an exact partial activity when one exists:

   ```bash
   poetry run resilio activity list \
     --since <EVENT_DATE> \
     --sport run
   ```

   If exact owned workout pairing exists, the review binds it. Otherwise,
   require the athlete to confirm the exact canonical activity ID. Never
   auto-match a result from date, sport, distance, name, or elapsed time.

3. Create the immutable cycle review:

   ```bash
   poetry run resilio plan create-cycle-review \
     --effective-end <DATE> \
     --evidence-as-of <DATE> \
     --goal-status <STATUS> \
     --goal-activity-id <LOCAL_ACTIVITY_ID_IF_COMPLETED_OR_DNF> \
     --athlete-confirmation "<EXACT_CONFIRMATION>" \
     --goal-notes "<OPTIONAL_CONTEXT>"
   ```

   Inspect the returned plan identity, goal evidence, plan targets, actual run
   exposure, exact completion counts, other-sport exposure, detailed recent
   weeks, compact weekly history, source coverage, and limitations. Keep
   planned and actual measurements separate. Do not manufacture completion,
   progression, readiness, performance, or injury-risk scores.

4. Present the review in athlete language. State incomplete coverage and
   unavailable adherence explicitly. Ask the athlete to confirm closure only
   after they have reviewed the outcome.

5. Close and archive the exact cycle:

   ```bash
   poetry run resilio plan close-cycle \
     --cycle-review-sha256 <SHA256> \
     --disposition <DISPOSITION> \
     --reason "<COACHING_AND_LIFECYCLE_REASON>" \
     --athlete-confirmation "<EXACT_CLOSURE_CONFIRMATION>"
   ```

   If future owned workout events block closure, delete or reconcile only
   those exact ownership-proven events, then retry.

## Successor evidence

1. Confirm the next goal and any changed profile constraints before building
   new planning evidence.

2. Reassess VDOT only from qualifying exact evidence. If a new proposal is
   warranted, run the baseline VDOT procedure and record its separate athlete
   approval. Otherwise retain the verified active approval.

3. Compute the next Monday with `resilio dates`; it must be strictly after the
   evidence date. Create the successor context:

   ```bash
   poetry run resilio plan create-macro-context \
     --evidence-as-of <DATE> \
     --start <NEXT_PLAN_MONDAY>
   ```

   The returned context contains every closed-plan summary, goal outcomes, up
   to 52 compact historical weeks, 12 detailed recent weeks, current profile
   constraints, the active VDOT approval, and stable evidence IDs.

4. Invoke the macro-plan procedure with this exact context reference. Every
   substantial plan decision must cite returned evidence IDs and distinguish
   observed facts, the planning change, and uncertainty. At minimum, cite the
   latest recent week plus the latest closed-plan summary and goal outcome.
   If synchronized evidence changes, discard the stale context and create a
   fresh one before drafting.

## Output

Return the confirmed closure facts, a plan-versus-execution review with units,
the exact goal outcome, other-sport and recovery observations, evidence
limitations, the closed plan identity, the macro-context reference, and the
next approval boundary. Do not imply that archival approves the successor.
