# Amend remaining race-macro targets

Use an amendment when the athlete approves changes to remaining weekly volume,
phase, recovery status, or quality/long-run hints within the same race goal,
baseline, methodology, horizon, and profile constraints. A new goal or cycle
still uses the normal review and closure workflow.

Evaluate whether to retain or amend the remaining targets through the
[macro continuity procedure](running-progression.md#macro-continuity-and-completed-deviations)
before generating exact workouts. New completed exposure, recovery evidence,
or scheduling context can make an achievable target strategically outdated.
An amendment can increase or reduce remaining targets when the whole-cycle
rationale supports it. Exceeding a previous prescription or reporting an easy
effort does not by itself justify an increase; retaining the current targets
with an explicit rationale remains a valid outcome.

An amendment is a new proposal and approval within the existing ownership
lineage. The plan and workout lineage IDs remain stable so native provider
events and exact historical fulfillment remain attributable. The new amendment
ID and macro approval identify the changed target authority. The original
macro, its approval timestamp, and prior weekly snapshots remain immutable in
the amendment history. Historical adherence selects the macro authority that
existed when each exact weekly file was approved.

1. Read current dates, plan, approvals, profile, and synchronized evidence.
   Back up validated athlete state before applying any mutation.
2. Create a fresh `coach create-planning-context` for each changed week, with
   evidence through the application date. Those contexts bind the existing
   approved targets and factual evidence motivating the amendment.
3. Write a new `MacroAmendmentProposal` JSON with `schema_version: 1`,
   `expected_active_plan_sha256` from the canonical complete active-plan state,
   `weeks` containing only changed skeletons with empty `running_workouts`,
   corresponding `planning_context_references` in the same order, and a specific
   `rationale` explaining the evidence, changes, and uncertainty.
4. Follow the [shared progression review](running-progression.md): assess the
   whole candidate with `plan assess-progression --kind amendment --file <JSON>`,
   author the review, and bind it with `plan bind-progression-review --kind amendment
   --file <JSON> --review-file <REVIEW_JSON> --out <FINAL_JSON>`.
5. Run `plan validate-amendment --file <FINAL_JSON>` and present only those final
   targets and the returned file SHA-256 for athlete approval.
6. After approval, run `plan apply-amendment --file <FINAL_JSON> --sha256 <SHA>
   --athlete-confirmation <TEXT>`. Review the exact readback.
7. Generate new weekly planning context and a new exact workout file for each
   retired upcoming week. Use separate exact weekly approval/application and
   inspect its automatic synchronization result. Future unpopulated weeks stay
   strategic until their normal weekly planning date.

Validation preserves week numbers and dates and rejects completed calendar
weeks. A populated partial week may be amended only while it has an upcoming,
unfulfilled workout. The later exact weekly replacement must retain every
elapsed prescription that was authoritative at its schedule deadline and every
exactly fulfilled prescription, including early execution and authority in an
inactive prior snapshot. Validation, approval, and application all recheck
these facts; newly backdated workouts are rejected. A replacement applied after
a workout expires during the amendment gap must be revised rather than creating
retroactive authority.
A missed elapsed prescription remains unchanged in the replacement and in
historical adherence. The scheduled weekly total includes its original distance;
state the expected remaining execution separately. For example, an unchanged
missed 5 km plus upcoming 10 km and 16 km prescriptions has a 31 km scheduled
total and 26 km remaining execution, rather than pretending the 5 km was run.
For an explicitly requested calendar cleanup, `resilio workout remove-missed
--workout-id <ID> --confirmation-reference <TEXT>` removes only an elapsed,
unfulfilled, ownership-proven event. A separate durable removal record retains
its original publication, exact remote fingerprint, athlete identity,
confirmation, and request/completion times. It does not change the plan,
historical adherence, or completed exposure. Normal reconciliation suppresses
the removed event; pending removal blocks reconciliation until the same command
is retried. Pending publication updates and provider-paired events are rejected.
A pending weekly approval must be resolved first. The exact active-state and
proposal-file digests prevent replay or changes after review. Evidence is
rechecked under the activity lock before the single planning-state commit.

An affected populated future week loses active weekly authority and becomes
unpopulated until its new exact workouts are approved and applied. Its prior
applied snapshot is retained with a temporal invalidation timestamp. Existing
owned provider events are retained; macro application itself never edits or
deletes a calendar event. The normal weekly reconciler subsequently uses the
retained ownership history to update the same events and protects remote drift.

If later weekly generation or publication fails, report macro application,
weekly application, and publication separately. Never claim a completed workout
update from a successful macro amendment alone, and never infer watch delivery
from forwarding eligibility.
