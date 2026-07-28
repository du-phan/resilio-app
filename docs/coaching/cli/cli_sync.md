# Completed-activity sync

```bash
resilio sync
resilio sync --full
resilio sync --status
resilio sync --full --confirm-deletions
resilio activity-review list
resilio activity-review approve \
  --external-hash <full-sha256> \
  --local-id <candidate-local-id>
resilio activity-review exclude-duplicate \
  --external-hash <full-sha256> \
  --review-fingerprint <full-sha256>
resilio activity-review quarantines
resilio activity-review acknowledge-quarantine \
  --external-hash <full-sha256> \
  --failure-fingerprint <full-sha256>
resilio activity-review deletions
```

The first successful run and `--full` enumerate the configured historical
range in complete, bisection-capable date windows. Normal incremental runs
query a 30-day overlap so late edits can be found.

Each run:

1. validates account access, connections, and sport settings;
2. lists complete windows and reports hidden external rows;
3. fetches validated activity details and intervals;
4. maps them into provider-neutral activity v2 records;
5. links strict historical matches, quarantines ambiguity/invalid data, and
   stages unambiguous changes;
6. atomically switches the archive and recomputes local metrics from the
   earliest changed date.

`--status` is read-only and reports lock, progress, checkpoint, and file count.

Missing externally linked IDs are retained unless a detail request confirms
`404` and `--confirm-deletions` is supplied after review. Confirmed deletions
become local tombstones; historical data is not erased.

`activity-review deletions` shows the retained local ID, date, sport, and name
for every current `404` candidate. It is read-only. Re-run the full sync with
`--confirm-deletions` only after reviewing that queue.

A partial run may still commit validated changes, but its complete cursor does
not advance. Repeating the same input must create zero duplicates.

`activity-review list` presents local date, sport, title, duration, distance,
and numeric deltas for conservative historical matches without exposing the
external activity ID. Approval records only the selected SHA-256/local-ID pair;
it does not mutate the archive. The next sync applies it only if that exact
record is still a candidate under the current sport/date/reconciliation rules.
Stale or conflicting approvals fail closed.

If a candidate is already linked to another external recording of the same
physical activity, `exclude-duplicate` records a hash-bound exclusion instead
of overwriting that ownership link. The review fingerprint must still match on
the next sync; any candidate or payload change reopens review.

For an activity that fails canonical validation, `activity-review quarantines`
shows only a hashed external identity, sanitized validation locations/types,
and a deterministic failure fingerprint. An acknowledgement applies only
while that exact validation failure remains current; changed payloads require
review again. Unsupported sports and logical conflicts cannot be acknowledged.

When JSON identity evidence leaves a match ambiguous, sync temporarily
downloads the original activity file, hashes it in memory, and retries the
identity decision. Raw file bytes are never persisted. The review queue records
only whether the hash produced a unique match.
