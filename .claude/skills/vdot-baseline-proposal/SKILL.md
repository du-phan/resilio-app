---
name: vdot-baseline-proposal
description: Proposes a baseline VDOT and writes a review doc with evidence and a single approval prompt. Use when a macro plan needs an approved baseline VDOT.
disable-model-invocation: true
context: fork
agent: vdot-analyst
allowed-tools: Bash, Read, Write
argument-hint: "[notes]"
---

# VDOT Baseline Proposal (Executor)

Non-interactive. Use CLI only. Write a review doc for the main agent to present.

## Preconditions (block if missing)
- Goal exists (race type/date) and profile exists
- Metrics available (`sce status`)

If missing, return a blocking checklist and stop.

## Workflow

1) Gather evidence:
```bash
sce profile get
sce race list
sce status
sce vdot estimate-current --lookback-days 28
sce activity list --since 30d --sport run
```

2) Choose a baseline VDOT:
- Prefer recent race (≤90 days)
- Else use `vdot estimate-current`
- Else conservative CTL-based estimate (cite as low confidence)

3) Get pace ranges:
```bash
sce vdot paces --vdot <VDOT>
```

4) Write `/tmp/vdot_review_YYYY_MM_DD.md` with:
- Proposed VDOT + confidence + source
- Recent evidence (race or key workouts)
- Pace table (easy/tempo/interval/long)
- Single approval prompt text for the athlete
- Handoff note: main agent must record approval via
  `sce approvals approve-vdot --value <VDOT>`

## References (load only if needed)
- VDOT methodology: `docs/coaching/methodology.md`
- Pace zones reference: `references/pace_zones.md`

## Output
Return:
- `proposed_vdot`
- `review_path`
- `athlete_prompt` (single yes/no + adjustment question)
