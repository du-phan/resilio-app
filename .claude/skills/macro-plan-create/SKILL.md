---
name: macro-plan-create
description: Creates a macro plan skeleton from an approved baseline VDOT and writes a review doc. Use after baseline VDOT approval.
disable-model-invocation: true
context: fork
agent: macro-planner
allowed-tools: Bash, Read, Write
argument-hint: "baseline_vdot=<number>"
---

# Macro Plan Create (Executor)

Non-interactive. Use CLI only. Do not ask the athlete questions.

## Preconditions (block if missing)
- Approved baseline VDOT provided via arguments
- Goal present (race type/date/time)
- Profile constraints present
- Metrics available (`sce status`)

If missing, return a blocking checklist and stop.

## Workflow

1) Gather context:
```bash
sce dates next-monday
sce profile get
sce status
sce memory list --type INJURY_HISTORY
```

2) Determine starting/peak volumes and weekly targets:
```bash
sce guardrails safe-volume --ctl <CTL> --goal-type <GOAL> --recent-volume <RECENT>
```

3) Create a weekly volumes JSON (AI coach computed) at `/tmp/weekly_volumes.json` **using this exact format**:
```json
{
  "volumes_km": [32.0, 35.0, 38.0, 28.0, 40.0, 43.0, 46.0, 32.0, ...]
}
```
Rules:
- `volumes_km` length MUST equal `total_weeks`
- All values must be positive numbers

4) Create macro plan (store baseline VDOT):
```bash
sce plan create-macro \
  --goal-type <GOAL> \
  --race-date <YYYY-MM-DD> \
  --target-time "<HH:MM:SS>" \
  --total-weeks <N> \
  --start-date <YYYY-MM-DD> \
  --current-ctl <CTL> \
  --starting-volume-km <START_KM> \
  --peak-volume-km <PEAK_KM> \
  --baseline-vdot <BASELINE_VDOT> \
  --weekly-volumes-json /tmp/weekly_volumes.json
```

5) Validate macro:
```bash
sce plan validate-macro
```

6) Write `/tmp/macro_plan_review_YYYY_MM_DD.md` with:
- Start/end dates and phase breakdown
- Volume table (weeks, phase, target volume, recovery flag)
- Baseline VDOT + pace table
- Approval prompt text for the athlete
- Handoff note: main agent must record approval via
  `sce approvals approve-macro`

## References (load only if needed)
- Macro volume progression: `references/volume_progression_macro.md`
- Macro guardrails: `references/guardrails_macro.md`
- Periodization: `references/periodization.md`
- Common pitfalls: `references/common_pitfalls_macro.md`
- Multi-sport adjustments: `references/multi_sport_macro.md`
- Core methodology: `docs/coaching/methodology.md`

## Output
Return:
- `review_path`
- `macro_summary` (start/peak volumes, phases)
