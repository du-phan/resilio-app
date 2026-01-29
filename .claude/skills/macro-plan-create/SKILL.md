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

1. Gather context:

```bash
sce dates next-monday
sce profile get
sce status
sce memory list --type INJURY_HISTORY
```

2. Determine starting/peak volumes and weekly targets:

```bash
sce guardrails safe-volume --ctl <CTL> --goal-type <GOAL> --recent-volume <RECENT>
```

3. Create a macro template JSON at `/tmp/macro_template.json` using the CLI:

```bash
sce plan template-macro --total-weeks <N> --out /tmp/macro_template.json
```

Fill the template (replace all nulls) with AI-coach decisions. Example for 4 weeks (use N entries for total_weeks N):

```json
{
  "template_version": "macro_template_v1",
  "total_weeks": 4,
  "volumes_km": [32.0, 35.0, 28.0, 40.0],
  "workout_structure_hints": [
    {
      "quality": { "max_sessions": 1, "types": ["strides_only"] },
      "long_run": { "emphasis": "steady", "pct_range": [24, 30] },
      "intensity_balance": { "low_intensity_pct": 0.9 }
    },
    {
      "quality": { "max_sessions": 2, "types": ["tempo", "intervals"] },
      "long_run": { "emphasis": "steady", "pct_range": [24, 30] },
      "intensity_balance": { "low_intensity_pct": 0.85 }
    },
    {
      "quality": { "max_sessions": 0, "types": [] },
      "long_run": { "emphasis": "easy", "pct_range": [20, 25] },
      "intensity_balance": { "low_intensity_pct": 0.95 }
    },
    {
      "quality": { "max_sessions": 2, "types": ["tempo", "intervals"] },
      "long_run": { "emphasis": "progression", "pct_range": [24, 30] },
      "intensity_balance": { "low_intensity_pct": 0.85 }
    }
  ]
}
```

Rules:

- `volumes_km` length MUST equal `total_weeks`; each entry must be a positive number.
- `workout_structure_hints` length MUST equal `total_weeks`; each entry must conform to WorkoutStructureHints: `quality.max_sessions` 0–3, `quality.types` list of QualityType (e.g. tempo, intervals, strides_only); `long_run.emphasis` one of easy, steady, progression, race_specific; `long_run.pct_range` [min, max] in 15–35; `intensity_balance.low_intensity_pct` 0.75–0.95.
- Keep `template_version` and `total_weeks` unchanged.
- Hints are AI-coach defined (macro-level guidance only; no detailed workouts).

4. Create macro plan (store baseline VDOT):

```bash
sce plan create-macro \
  --goal-type <GOAL> \
  --race-date <YYYY-MM-DD> \
  --target-time "<HH:MM:SS>" \
  --total-weeks <N> \
  --start-date <YYYY-MM-DD> \
  --current-ctl <CTL> \
  --baseline-vdot <BASELINE_VDOT> \
  --macro-template-json /tmp/macro_template.json
```

5. Validate macro:

```bash
sce plan validate-macro
```

5b. Validate plan structure (phases/volumes/taper):
Export structure from the stored plan, then validate:

```bash
sce plan export-structure --out-dir /tmp

sce plan validate-structure \
  --total-weeks <N> \
  --goal-type <GOAL> \
  --phases /tmp/plan_phases.json \
  --weekly-volumes /tmp/weekly_volumes_list.json \
  --recovery-weeks /tmp/recovery_weeks.json \
  --race-week <RACE_WEEK>
```

6. Write `/tmp/macro_plan_review_YYYY_MM_DD.md` with:

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
