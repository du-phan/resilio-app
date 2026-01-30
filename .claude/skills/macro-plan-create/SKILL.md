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

Fill the template (replace all nulls) with AI-coach decisions.

**Example 1: Single-sport runner (12-week half marathon)**

```json
{
  "template_version": "macro_template_v1",
  "total_weeks": 12,
  "weekly_volumes_km": [40.0, 42.0, 45.0, 42.0, 48.0, 50.0, 52.0, 48.0, 55.0, 58.0, 50.0, 35.0],
  "target_systemic_load_au": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "workout_structure_hints": [
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "steady", "pct_range": [25, 30]}, "intensity_balance": {"low_intensity_pct": 0.85}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "steady", "pct_range": [26, 30]}, "intensity_balance": {"low_intensity_pct": 0.82}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "steady", "pct_range": [28, 32]}, "intensity_balance": {"low_intensity_pct": 0.80}},
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "easy", "pct_range": [22, 26]}, "intensity_balance": {"low_intensity_pct": 0.90}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "progression", "pct_range": [28, 32]}, "intensity_balance": {"low_intensity_pct": 0.80}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "progression", "pct_range": [28, 32]}, "intensity_balance": {"low_intensity_pct": 0.78}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "progression", "pct_range": [30, 34]}, "intensity_balance": {"low_intensity_pct": 0.78}},
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "easy", "pct_range": [22, 26]}, "intensity_balance": {"low_intensity_pct": 0.90}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "race_specific"]}, "long_run": {"emphasis": "race_specific", "pct_range": [30, 34]}, "intensity_balance": {"low_intensity_pct": 0.75}},
    {"quality": {"max_sessions": 2, "types": ["race_specific"]}, "long_run": {"emphasis": "race_specific", "pct_range": [32, 35]}, "intensity_balance": {"low_intensity_pct": 0.75}},
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "steady", "pct_range": [24, 28]}, "intensity_balance": {"low_intensity_pct": 0.85}},
    {"quality": {"max_sessions": 0, "types": []}, "long_run": {"emphasis": "easy", "pct_range": [18, 22]}, "intensity_balance": {"low_intensity_pct": 0.95}}
  ]
}
```

**Example 2: Multi-sport athlete (12-week half marathon + climbing + yoga)**

```json
{
  "template_version": "macro_template_v1",
  "total_weeks": 12,
  "weekly_volumes_km": [35.0, 38.0, 40.0, 38.0, 42.0, 45.0, 48.0, 45.0, 50.0, 52.0, 45.0, 30.0],
  "target_systemic_load_au": [85.0, 92.0, 98.0, 90.0, 105.0, 110.0, 118.0, 108.0, 125.0, 130.0, 115.0, 75.0],
  "workout_structure_hints": [
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "steady", "pct_range": [25, 30]}, "intensity_balance": {"low_intensity_pct": 0.85}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "steady", "pct_range": [26, 30]}, "intensity_balance": {"low_intensity_pct": 0.82}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "steady", "pct_range": [28, 32]}, "intensity_balance": {"low_intensity_pct": 0.80}},
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "easy", "pct_range": [22, 26]}, "intensity_balance": {"low_intensity_pct": 0.90}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "progression", "pct_range": [28, 32]}, "intensity_balance": {"low_intensity_pct": 0.80}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "progression", "pct_range": [28, 32]}, "intensity_balance": {"low_intensity_pct": 0.78}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "progression", "pct_range": [30, 34]}, "intensity_balance": {"low_intensity_pct": 0.78}},
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "easy", "pct_range": [22, 26]}, "intensity_balance": {"low_intensity_pct": 0.90}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "race_specific"]}, "long_run": {"emphasis": "race_specific", "pct_range": [30, 34]}, "intensity_balance": {"low_intensity_pct": 0.75}},
    {"quality": {"max_sessions": 2, "types": ["race_specific"]}, "long_run": {"emphasis": "race_specific", "pct_range": [32, 35]}, "intensity_balance": {"low_intensity_pct": 0.75}},
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "steady", "pct_range": [24, 28]}, "intensity_balance": {"low_intensity_pct": 0.85}},
    {"quality": {"max_sessions": 0, "types": []}, "long_run": {"emphasis": "easy", "pct_range": [18, 22]}, "intensity_balance": {"low_intensity_pct": 0.95}}
  ]
}
```

Note: In Example 2, `target_systemic_load_au` represents total aerobic load across ALL sports (running + climbing + yoga). Week 9 systemic load (125 AU) = 50 km running (50 AU) + climbing sessions (60 AU) + yoga sessions (15 AU).

**Validation Rules:**

- `weekly_volumes_km` length MUST equal `total_weeks`; each entry must be a positive number
- `target_systemic_load_au` length MUST equal `total_weeks`; each entry must be >= 0.0
  - Single-sport athletes: Use `[0.0, 0.0, ...]` (systemic load calculated later from running volume)
  - Multi-sport athletes: Plan total systemic load targets using `sce analysis load` (running + cross-training + other sports)
- `workout_structure_hints` length MUST equal `total_weeks`; each entry must conform to WorkoutStructureHints:
  - `quality.max_sessions`: 0–3
  - `quality.types`: list of QualityType (e.g., tempo, intervals, strides_only, race_specific)
  - `long_run.emphasis`: one of easy, steady, progression, race_specific
  - `long_run.pct_range`: [min, max] in 15–35
  - `intensity_balance.low_intensity_pct`: 0.75–0.95
- Keep `template_version` and `total_weeks` unchanged
- Hints are macro-level guidance only (no detailed workouts)

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
