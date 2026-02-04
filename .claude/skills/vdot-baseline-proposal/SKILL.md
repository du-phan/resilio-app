---
name: vdot-baseline-proposal
description: Proposes a baseline VDOT and returns evidence plus a single approval prompt for the main agent. Use when a macro plan needs an approved baseline VDOT.
disable-model-invocation: true
context: fork
agent: vdot-analyst
allowed-tools: Bash, Read
argument-hint: "[notes]"
---

# VDOT Baseline Proposal (Executor)

Use CLI only. Present the review directly in chat for the main agent to use.

## Preconditions (block if missing)
- Goal exists (race type/date) and profile exists
- Metrics available (`sce status`)

If missing, return a blocking checklist and stop.

## Interactivity & Feedback

- Non-interactive: do not ask the athlete questions or call approval commands.
- Return an `athlete_prompt` for the main agent to ask and capture approval.
- If the athlete declines or requests changes, the main agent will re-run this skill with notes; treat notes as hard constraints and generate a new proposal.
- If new constraints are provided (injury, schedule limits), assume the main agent updated profile/memory before re-run.

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

4) Present directly in chat:
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
- `athlete_prompt` (single yes/no + adjustment question)
- If blocked: `blocking_checklist`
