# Historical activity backfill

`resilio activity-backfill` is a one-time, approval-gated surface for
publishing the frozen historical bouldering archive. It does not create new
local activities or recompute metrics.

The normal sequence is:

1. `dry-run --confirm-downloads-disabled`
2. `record-approval --stage canary --plan-digest <sha256>`
3. `canary --plan-digest <sha256>`
4. Athlete visually reviews the canary.
5. `record-approval --stage apply --plan-digest <sha256> --canary-digest <sha256>`
6. `apply --plan-digest <sha256> --canary-digest <sha256>`

The completed publication also supports a separately approved missing-RPE
repair:

```bash
resilio activity-backfill record-approval \
  --stage rpe_default \
  --plan-digest <sha256> \
  --canary-digest <sha256>
resilio activity-backfill set-default-rpe \
  --value <1-10> \
  --plan-digest <sha256> \
  --canary-digest <sha256>
```

This command changes only exact owned publications whose remote athlete RPE is
absent. It preserves every existing RPE and all protected local state.

Use `status` at any time. Use `resume` after an uncertain or interrupted
application; it adopts exact owned results and retries only activities proven
absent. `rollback` deletes only exact manifest-owned remote activities before
restoring their verified local originals.

The plan and canary digests are immutable approval identities, not optional
confirmation flags. Never substitute a newer dry run or canary digest without
a new athlete approval.

The verified backup, ownership ledger, and rollback executable are retained
through 2026-10-27. See the
[Intervals.icu integration reference](../../reference/intervals-icu-integration.md)
for the current retention and ownership rules.
