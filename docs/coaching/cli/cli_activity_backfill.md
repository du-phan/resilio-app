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

Use `status` at any time. Use `resume` after an uncertain or interrupted
application; it adopts exact owned results and retries only activities proven
absent. `rollback` deletes only exact manifest-owned remote activities before
restoring their verified local originals.

The plan and canary digests are immutable approval identities, not optional
confirmation flags. Never substitute a newer dry run or canary digest without
a new athlete approval.
