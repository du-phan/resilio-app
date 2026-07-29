# Intervals.icu migration acceptance record

- Date: 2026-07-28
- Status: implementation and owned calendar lifecycle verified; no active
  training plan; device observation deferred
- Plan: `docs/plans/2026-07-28-intervals-icu-migration.md`
- Historical bouldering backfill:
  `docs/plans/2026-07-29-historical-bouldering-backfill.md`
- Vault issue:
  `projects/resilio-app/issues/issue-20260728-intervals-icu-migration.md`
- Vault status: `projects/resilio-app/status.md`
- Weekly continuity: `weekly/2026-W31.md`
- Approved vault brief: `projects/resilio-app/brief.md`

This record contains only sanitized counts and pass/fail evidence. It must not
contain API keys, raw external payloads, plaintext external activity IDs, or
personal file contents.

## Completed evidence

| Journey | Status | Evidence |
|---|---|---|
| One local API-key credential | Pass | `.env.local` requires only `INTERVALS_ICU_API_KEY`; secret-safe config tests pass |
| Account validation | Pass live | Athlete alias resolves; timezone is `Europe/Paris`; no key is displayed |
| Historical migration | Pass | 1,114/1,114 records and 56/56 screenshot imports reconcile to the frozen totals |
| Backup and rollback | Pass | 2,775-file backup manifest verified; disposable apply/rollback and failure reversal pass |
| Initial import and rerun | Pass live | Active archive has 1,125 v2 records and 110 external links; authorized full reconciliation linked 39, left 71 unchanged, and excluded two duplicates; immediate rerun changed zero |
| Conservative overlap safety | Pass live | Athlete-authorized review linked 39 exact historical candidates and excluded two proven Wahoo/Garmin duplicate recordings; the complete rerun has zero ambiguities |
| Invalid measurement safety | Pass live | Athlete-authorized acknowledgement covers all four exact upper-bound failure fingerprints; the complete rerun has zero quarantines |
| External deletion safety | Pass | Detail confirmation and retained tombstones are tested; live deletion review queue is empty |
| Local metrics/coaching | Pass | 1,651 metric days through 2026-07-28; profile spans 1,638 days and 1,125 activities |
| Sport and provenance matrix | Pass offline/live | Every documented sport variant, Bouldering/RockClimbing convergence, manual yoga, Garmin/Wahoo/manual/upload provenance, power, and cadence are covered; live Garmin/Wahoo sibling recordings exercised duplicate exclusion |
| Structured workout model | Pass offline/live | Recursive steady/ramp/repeat steps, explicit targets, lap press, DST, and device preconditions pass; a live parser defect established that metres require `mtr` and max-HR targets require `% HR`, and exact read-back now has regression coverage |
| Owned event lifecycle | Pass live | Three owned acceptance events were created idempotently; two run events were corrected in place after exact ownership proof, repeated as no-ops, then all three were explicitly deleted at the athlete's request and verified absent |
| Remote ownership refresh | Pass live | Exact refreshes proved every server UID, external ID, category, sport, date, and rendered-workout identity before update and deletion; the publication manifest is now empty |
| Non-cascading deletion | Pass live | Exact DELETE sends `others=false`; all three selected owned events returned `404` afterward, no Resilio-owned event remained in the week, and manifests reject cross-workout identity collisions |
| Garmin attribution | Pass offline | Garmin-derived activity list/search rows display required attribution |
| Free-account dormancy notice | Pass | Setup and onboarding explain the 90-day login requirement |
| Vault brief | Pass | Explicit approval was received and the active integration text now describes Intervals.icu |
| Ignored active state | Pass | All 1,125 files validate as literal v2; the retired training-history sync file and unused entrypoints were removed; active athlete/state/plan files contain zero obsolete provider terms |
| Offline/architecture gates | Pass | 951 tests pass; focused Ruff, architecture/cleanup checks, `git diff --check`, and source/wheel builds pass |
| Latest incremental refresh | Pass live | Five recent activities were unchanged; the run was complete with zero create/update/link, ambiguity, quarantine, deletion, or completion-candidate result |
| Historical backfill implementation | Pass offline | Strict 433/29/404 fixtures, current 433-record rendering coverage, canary upsert/cleanup, lost-response adoption, shared archive/state rollback, feedback-sync provenance, exact rollback, and repeated-application no-op behavior pass without live network access |
| Historical backfill canary | Diagnostic retry pending | The original exact-`Bouldering` canary failed closed; the approved `RockClimbing` canary was then deleted exactly after strict read-back found a factual mismatch. Field-name-only diagnostics now preserve value secrecy, and repeat inventory proof remains exact with zero owned publications |

## Exact completion-gate audit

| Completion requirement | Status | Sanitized proof |
|---|---|---|
| Plan, issue, status, weekly note, and approved brief are current and cross-linked | Pass | Repository plan and acceptance record link the four current vault artifacts; the explicitly approved brief names Intervals.icu as the active integration |
| Existing user-owned worktree changes are preserved | Pass | The two pre-existing `.claude/worktrees` deletions remain deletions and were not recreated or repurposed |
| Verified backup exists and rollback is demonstrated | Pass | Restricted `0700` backup contains 2,775 manifest-verified files; isolated apply/rollback and injected-failure reversal tests pass |
| Dry run accounts for all 1,114 source records | Pass | Deterministic report digest accounts for 1,114/1,114 records without mutation |
| Every migrated record validates only as activity v2 | Pass | Direct active-state audit validates literal `_schema: {name: resilio.activity, version: 2}` in all 1,125 files; the reader rejects legacy schema |
| Historical counts, dates, sports, measurements, and loads reconcile | Pass | Frozen range, sport counts, duration, distance, elevation, systemic load, and lower-body load match exactly |
| All 56 screenshot records are preserved | Pass | Expected 28 climb, 22 cycle, and 6 run records remain across 2026-04-07 through 2026-07-15 |
| Metrics regenerate deterministically through the cutover date | Pass | 1,651 daily records cover 2022-01-20 through 2026-07-28 and reconciliation tests pass |
| Active application cannot read the old schema | Pass | Schema validator and archive tests fail closed on legacy metadata/version |
| Initial and repeat sync are idempotent | Pass live | Complete reconciliation followed by an immediate incremental run changed zero records and left no review/quarantine row |
| Late edits, deletion handling, partial runs, and interrupted resume pass | Pass offline | Fingerprint updates, detail-confirmed tombstones, cursor safety, checkpoint recovery, and transactional rollback have regression coverage |
| RockClimbing and Bouldering aggregate as `climb` | Partial live | Both variants pass strict inbound mapper/sibling tests; the live manual validator accepts `RockClimbing` and rejects `Bouldering`, and the athlete approved explicit `RockClimbing` publication for the historical backfill |
| Garmin, Wahoo, manual, and sensor sibling cases pass | Pass offline/live | Strict fixtures cover every provenance and HR/power/cadence case; live Garmin/Wahoo duplicate evidence exercised ownership-safe exclusion |
| Run/cycle workouts reach Garmin/Wahoo | Deferred | API-side connections, forwarding toggles, unrestricted Garmin filters, run-HR prerequisites, ride FTP, and Europe/Paris timezone pass; the athlete is not currently in a training plan, so the acceptance fixtures were removed before physical device observation |
| Update, reschedule, and delete affect only owned events | Partial live | Ownership-safe in-place update and exact deletion are live-proven; idempotency, remote drift, reschedule, `others=false`, and recovery remain covered offline |
| Full offline suite and structural/security/docs guards are green | Pass | See the current closing verification result below |
| Findings-first reviews have no unresolved high-severity item | Pass | Sync, migration, ownership, data-safety, secret-safety, dependency, and cleanup reviews closed all identified high-severity findings |
| Dependency usage is justified | Pass | Direct `requests` dependency is absent; `httpx` serves Intervals.icu and weather transport, while `tenacity` serves bounded weather retry |
| Active provider cleanup is complete | Pass | Case-insensitive audit finds zero unclassified obsolete terms or provider-named paths outside the vendored specification, migration history, verified rollback backup, and Git history |

## Pending athlete evidence

| Journey | Required evidence |
|---|---|
| Bouldering | One sanitized live activity imports as `climb` |
| Historical bouldering backfill | Fresh amended dry run, newly approved `RockClimbing` canary, then 404 verified owned manual activities; unchanged local facts/metrics and a 404-record repeat no-op |
| Manual yoga | One sanitized live manual activity imports as `yoga` |
| Run delivery | When the athlete starts a future plan, approve and publish a real structured run and observe it on Garmin |
| Cycling delivery | When the athlete starts a future plan, approve and publish a real structured ride and observe it on Wahoo |
| Update/reschedule | A future real owned event updates without identity or event duplication; in-place update is already live-proven |
| Device configuration | API-side connections, toggles, filters, sport settings, and account timezone pass; phone/device timezones still need physical confirmation |

## Controlled device procedure

1. Obtain athlete approval for one future structured run and one future
   structured ride. Do not create acceptance-only plan workouts implicitly.
2. Confirm the athlete timezone, device connections, upload toggles, sport
   filters, threshold pace/pace zones, and FTP.
3. Publish through the normal owned-workout path. Record only local workout
   IDs, sanitized action results, and whether each device received the event.
4. Repeat publication unchanged and prove a no-op.
5. Reschedule each workout while retaining its deterministic external ID and
   manifest-bound server UID; verify one remote event remains.
6. Before cleanup, fetch each exact stored event and re-prove manifest,
   requested UID, server UID, external ID, namespace, sport, and date.
7. Delete only those exact event IDs with related-event deletion disabled, and
   verify absence. Never use bulk or date-range deletion.

## Acceptance rule

No pending row may be marked complete from fixture coverage alone. Any defect
found during live acceptance first becomes a failing offline regression test,
then is fixed and reverified before acceptance resumes.
