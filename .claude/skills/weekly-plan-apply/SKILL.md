---
name: weekly-plan-apply
description: Apply an exact weekly plan file whose current bytes and path were explicitly approved by the athlete. Use only after weekly approval is recorded; never use to generate or revise workout content.
---

# Apply an approved week

This procedure only validates and persists approved bytes. Do not redesign,
rewrite, summarize as a new proposal, or ask the athlete a question.

## Preconditions

Require the approved file path and week number. Verify:

```bash
poetry run resilio approvals status
```

The recorded plan kind, plan ID, plan revision, plan-skeleton SHA-256, week number,
target-week-skeleton SHA-256, action, prior applied-workout SHA-256, absolute
path, and file SHA-256 must correspond to the current aggregate and supplied
file. If not, stop with a blocking checklist.

## Apply

```bash
poetry run resilio plan validate-week --file <APPROVED_FILE>
poetry run resilio plan apply-week --file <APPROVED_FILE>
poetry run resilio plan week --week <WEEK_NUMBER>
poetry run resilio approvals status
```

Do not repair a failing file. Return the exact validation or application error
to the main coach. Success requires non-empty persisted workouts and consumed
weekly approval state. It also requires a new active applied-week audit whose
workout SHA-256 matches the current week. A replacement must invalidate the
previous active audit for that week.

The `apply-week` result is the authoritative combined outcome. It always
reports the successful local commit separately from run synchronization. When
the athlete-confirmed synchronization mode is `after_weekly_apply`, application
immediately reconciles that exact week's running workouts. Do not invoke a
second publish step after a synchronized result.

A `blocked` or `failed` run-synchronization status must not roll back or
obscure `local_application_status: applied`. Return the exact typed sync report
or error to the coach; the running-workout-publication procedure owns explicit
status inspection, idempotent retry, and athlete-confirmed drift resolution.
Never describe `eligible_unverified` as watch delivery.
