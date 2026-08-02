---
name: baseline-assessment-review
description: Confirm an ownership-paired benchmark activity or exact canonical segment, create an immutable assessment review, archive the completed assessment, and prepare a VDOT proposal. Use after the benchmark workout has been published, synchronized, and paired to its completion.
---

# Review a baseline assessment

Keep the conversation in athlete language. Never infer which activity or
segment is the result, never infer official distance from GPS distance, and
never approve the resulting VDOT on the athlete's behalf.

## Preconditions

Require one approved active baseline-assessment plan, one applied benchmark
workout, an exact publication record, and a synchronized provider-paired
completion. Refresh factual state:

```bash
poetry run resilio dates today
poetry run resilio sync
poetry run resilio sync --status
poetry run resilio plan show
poetry run resilio approvals status
```

If completion pairing is absent, do not match by date, title, sport, distance,
duration, or proximity. Reconcile the owned publication/completion chain first.

## Select exact result evidence

List candidates:

```bash
poetry run resilio plan assessment-candidates
```

Candidates may be the whole paired activity or exact canonical segments of
that same activity. Show each candidate's measured distance in meters, elapsed
seconds/formatted time, local date, timezone, activity identity, and segment
index when present. Ask the athlete to select exactly one candidate and confirm
that it represents the complete official benchmark distance. A warm-up plus
test activity is not automatically a dedicated test; a segment is not
automatically correct because its GPS distance looks close.

Create immutable review evidence only after both confirmations:

```bash
poetry run resilio plan create-assessment-review \
  --candidate <CANDIDATE_ID> \
  --evidence-as-of <DATE> \
  --official-distance-confirmation "<EXACT_CONFIRMATION>" \
  --athlete-confirmation "<EXACT_SELECTION_CONFIRMATION>" \
  --summary "<EVIDENCE_SUMMARY>"
```

Present the exact result, measured-versus-official distance distinction,
canonical source identity, and any evidence limitation. Ask separately for
closure approval.

## Close and propose VDOT

After explicit closure approval:

```bash
poetry run resilio plan close-assessment \
  --review-sha256 <SHA256> \
  --reason "<LIFECYCLE_REASON>" \
  --athlete-confirmation "<EXACT_CLOSURE_CONFIRMATION>"
```

Closure archives the exact plan/application history and clears the active plan.
It does not change VDOT. Create a new proposal file from the closed review:

```bash
poetry run resilio vdot create-proposal-from-assessment \
  --review-sha256 <SHA256> \
  --out <NEW_PROPOSAL_JSON>
```

Report the calculated integer VDOT, exact distance/time/date, selected result
kind, excluded alternatives, proposal bytes, and one approval prompt. Only
after explicit athlete approval may the main coach run:

```bash
poetry run resilio approvals approve-vdot --file <NEW_PROPOSAL_JSON>
```

After VDOT approval, create macro-planning context. Its latest assessment
summary and result evidence ID must be cited by the successor macro plan.

Do not calculate or update Intervals.icu threshold pace from this five-kilometre
result alone. Before the first pace-targeted phase, inspect Run publication
capabilities and decide whether threshold-specific evidence is actually needed.
Until a verified method, qualifying evidence, and exact athlete approval exist,
leave threshold pace and pace zones unchanged and prescribe targetless or
supported heart-rate guidance.
