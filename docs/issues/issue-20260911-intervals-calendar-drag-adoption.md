# Intervals calendar drag adoption

Status: complete

## Evidence

Week 2 synchronized with both approved runs fulfilled and exact native
Intervals activity/event pairs. One approved Tuesday workout had been dragged
by the athlete to Monday, the factual execution date. The remote event retained
its exact owned identity, provider local-time component, rendered workout content,
and parsed step semantics, but status classified the date-only move as generic
remote drift.

The root cause was twofold: publication verification compared every provider
occurrence only with the last locally recorded date, and provider-paired
fulfillments were excluded from execution placement unless they also carried a
redundant athlete-confirmation record.

## Decision

- Keep the approved prescription date immutable and expose provider occurrence
  date as a separate fact.
- Adopt only an exact owned date-only move within the same Monday-Sunday
  training week. Preserve the provider local-time component derived from the
  prescription and require exact equality for all other owned fields and parsed
  workout semantics.
- Persist adoption from provider readback without rewriting the remote event.
- Give a current exact provider-paired or athlete-confirmed fulfillment
  precedence, using its canonical activity execution date.
- Continue to reject unpaired cross-week, start-time, content, target, name,
  description, ambiguous-ownership, and unowned-event changes as drift. An
  exact provider pair remains authoritative evidence of factual execution even
  across a training-week boundary.
- A provider-observed pair may prove current fulfillment but cannot authorize
  restoring that pair after it disappears; restoration still requires explicit
  athlete authority.

## Validation required

- Red/green tests for accepted date-only moves and rejected time, content, and
  cross-week changes.
- Regression coverage for provider-paired placement and missing-pair
  restoration safety.
- Targeted boundary probes, full tests, lint, type checks, architecture checks,
  two independent findings-first reviews, and live Week 2 readback.

## Review findings and resolution

The first two independent reviews converged on two high-severity lifecycle
defects and independently reproduced them: a published workout was skipped once
its approved date passed, and fulfillment revocation could overwrite a later
calendar choice. Published current-identity events now remain in read-only
verification after their approved dates pass.

The same reviews found three preflight/result inconsistencies. Pair inspection
now accepts approval-only revisions through retained prescription authority,
binds local provider-pair evidence to the exact publication event, and reports
mutation-time drift with `reconciliation_safe: false`. A provider-only activity
paired to another event reaches the precise different-event blocker. Publication
record/result construction was also consolidated to remove duplicate field
mapping.

The second review round found that the first revocation repair still depended
on an unfinished unpair operation and therefore failed after the global reaper
completed first. Both reviewers independently reproduced the ordering defect.
A reaper-first regression now covers that execution order.

The round also found that approval lineage could be assembled from fields
belonging to different retained revisions. Publication placement and pairing
now share one exact matcher over approval ID, applied-week hash, prescription
hash, timezone, and scheduled date, followed by a separate current-workout
semantic check. A deliberately inconsistent retained snapshot is rejected.

Finally, replacement deletion previously selected candidates from persisted
dates before reading Intervals. Every obsolete owned publication is now a
read-only classification candidate. Exact date-only moves are recognized from
the last verified provider fingerprint: a locally past event dragged later in
the same week is safely retired, while a locally future event dragged into the
past is preserved. The provider date is checked again at mutation time to close
the preflight race. Content edits and cross-week moves remain drift.

The third review round proved that timestamps cannot identify who moved a
calendar event: an earlier athlete drag and a later fulfillment placement can
share the same date, while administrative timestamps can arrive in either
order. Publication schema v9 therefore stores two explicit layers for every
active or pending occurrence: an immutable approved/provider-observed base
calendar placement and an optional exact fulfillment override bound to the
local activity, execution date, and stable association-lineage SHA-256.
Revocation removes only that exact override, so an independent athlete drag
survives. Reconciliation order and wall-clock ordering are no longer used as
provenance.

The same review showed that a stored provider fingerprint does not contain
parsed `workout_doc` semantics and therefore cannot alone authorize deletion of
a dragged obsolete event. Deletion now reconstructs the exact stale
prescription from its immutable applied-week revision and performs the same
full semantic comparison used for active publication before classifying the
live date. Missing or changed step semantics block deletion. Because v8 did not
persist independent drag provenance, the v8-to-v9 migration reconstructs the
approved schedule as the conservative base and accepts any off-schedule
placement only with exact fulfillment authority. It validates version 8
publication records against schedule-time plan authority and writes publication
and fulfillment manifests transactionally.

The fourth review round exercised interrupted create/update recovery and
mutation-time races. Pending-only and dual published/pending identities now
adopt an exact date-only move under the same semantic rule, re-read the remote
state before mutation, and preserve the newer pending placement across restart.
A content-only approval revision retains a provider-calendar base only when the
prior record is present in exact applied-authority history. The same authority
lineage permits v8 migration across approval-only revisions without weakening
identity, prescription, date, timezone, provider-pair, or execution-date checks.

The round also found two destructive retirement edges. Ordinary tombstone
reconciliation now freshly reads and fingerprints the exact event immediately
before deletion. When an old published event is already past but a newer update
has an ambiguous provider outcome, Resilio preserves the past event and keeps a
durable monitoring obligation for a possible late materialization. Existing
version 1 tombstone identities remain byte-stable. Publication and fulfillment
normal access both reject v8 until coordinated cutover completes.

Regression suites are now separated by schedule adoption, placement lifecycle,
retirement/tombstones, and migration version. Targeted publication, fulfillment,
migration, lint, typing, and architecture checks pass. Full-suite validation,
final independent review, and live Week 2 reconciliation remain required before
closure.

The fifth review round extended the safety proof across crash recovery and
historical authority. Confirmed past restoration now stages durable intent,
targets a provider-rewritten UID without losing the deterministic request UID,
and recovers after a lost update response. Pending recovery re-reads exact event
bytes after native-pair preflight. All provider activity and event point reads
must return the requested identity, existing-event upserts retain that event ID,
and destructive deletion binds to the freshly observed provider UID. DST gap and
fold wall times are rejected rather than adopted as calendar moves.

Revocation now resolves exact active or historical publication authority across
canonical and version-1 fulfillment hashes and the complete activity-evidence
revision lineage. Reusing a local workout ID in a later plan cannot hide or
impersonate the historical event. Version-1 migration followed by runtime
revocation has dedicated coverage. Tombstone results report the observed
provider occurrence date when a remote event exists.

After these repairs, the focused feature suite passed 203 tests, architecture
passed 16 checks, strict typing passed across 239 source files, lint passed, and
the full suite passed 857 tests. Final independent review and live Week 2
reconciliation remain before closure.

## Live validation

The coordinated publication/fulfillment migration passed dry-run validation and
was applied with a recoverable backup. Week 2 status was safe before mutation.
Reconciliation adopted the exact owned easy-run occurrence on Monday 2026-09-07
while preserving its approved Tuesday 2026-09-08 date, and retained the long run
on Friday 2026-09-11. Both exact native activity/event pairs were already valid.
A second reconciliation returned `noop` for both events, with no deletion
candidates and both approved runs fulfilled.

The final independent review round found no unresolved high- or medium-severity
defect. Its last low test-adequacy observation is covered by an exact tombstone
regression that asserts the observed provider date on both a failed deletion
attempt and the subsequent confirmed deletion.

The final reporting-only follow-up now also covers a dual-state tombstone whose
previous event and pending intent have different dates. Monitoring reports the
date freshly proven by the exact provider point-read when the preserved event
still exists; it uses the pending intent date only when no remote event exists.
The same observed-date contract now applies to remote-drift errors and to a
confirmed drift target that disappears before deletion. Red/green regressions
exercise both paths, and the full 857-test suite, 16 architecture checks, strict
typing across 239 source files, lint, diff validation, and skill-mirror checks
all pass after the correction.

Both independent closure reviewers then rechecked these paths and reported no
remaining correctness, ownership-safety, architecture, naming, or test finding.
