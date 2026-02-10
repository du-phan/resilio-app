---
name: macro-plan-create
description: Creates a macro plan skeleton from an approved baseline VDOT and writes a review doc with an approval prompt for the main agent. Use after baseline VDOT approval.
disable-model-invocation: false
context: fork
agent: macro-planner
allowed-tools: Bash, Read, Write
argument-hint: "baseline_vdot=<number>"
---

# Macro Plan Create (Executor)

Use CLI only.

## Preconditions (block if missing)

- Approved baseline VDOT provided via arguments
- Goal present (race type/date/time)
- Profile constraints present
- Metrics available (`sce status`)

If missing, return a blocking checklist and stop.

## Interactivity & Feedback

- Non-interactive: do not ask the athlete questions or call approval commands.
- Include an `athlete_prompt` for the main agent to ask and capture approval.
- If the athlete declines or requests changes, the main agent will re-run this skill with notes; treat notes as hard constraints and generate a new plan + review doc.
- If new constraints are provided (injury, schedule limits), assume the main agent updated profile/memory before re-run.
- If any CLI command fails (exit code ≠ 0), include the error output in your response and return a blocking checklist.

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

2b. Validate volume feasibility against session duration constraints:

```bash
# Get easy pace (slower end for conservative estimate)
EASY_PACE=$(sce vdot paces --vdot <VDOT> | jq -r '.data.E.max_min_per_km')

# Check if peak is achievable
FEASIBILITY=$(sce guardrails feasible-volume \
  --run-days <max_run_days_per_week> \
  --max-session-minutes <max_time_per_session_minutes> \
  --easy-pace-min-per-km $EASY_PACE \
  --target-volume <recommended_peak_km>)

OVERALL_OK=$(echo "$FEASIBILITY" | jq -r '.data.overall_ok')
```

**If `OVERALL_OK` is `false`**: Return blocking checklist with:
- Problem statement: "Peak volume infeasible with current constraints"
- Math: Required session distance/time vs available (extract from `$FEASIBILITY`)
- Max feasible volume: `max_weekly_volume_km` from validation
- Context data for main agent to use in coaching conversation

**Format the blocking response as**:
```json
{
  "blocking_checklist": [
    "Peak volume is infeasible with current constraints",
    "Data: Required <X>km per session (<Y> min at easy pace), available <Z>km per session (<W> min)",
    "Max feasible weekly volume: <max_feasible>km (vs <recommended>km recommended based on CTL)",
    "Main agent: Use this data to discuss options with athlete (increase time/frequency, adjust goal, or accept lower volume)"
  ],
  "feasibility_data": {
    "recommended_peak_km": <value>,
    "max_feasible_km": <value>,
    "required_session_km": <value>,
    "max_session_km": <value>,
    "required_minutes": <value>,
    "available_minutes": <value>,
    "current_run_days": <value>,
    "easy_pace_min_per_km": <value>
  }
}
```

**Fallback**: If VDOT paces fails, use conservative estimates (VDOT 30-40: 7.0, 41-50: 6.0, 51-60: 5.5, 61+: 5.0 min/km).

3. Create a macro template JSON at `/tmp/macro_template.json` using the CLI:

```bash
sce plan template-macro --total-weeks <N> --out /tmp/macro_template.json
```

Fill the template (replace all nulls) with AI-coach decisions:

- **Starting volume**: Use `sce guardrails safe-volume` output as the baseline for week 1.
- **Peak volume**: Use the recommended peak from `sce guardrails safe-volume` (Step 2b validation blocks if infeasible).
- **Weekly progression**: 5-10% volume increase per non-recovery week, respecting guardrails.
- **Recovery weeks**: Every 3rd-4th week at ~70% of the prior week's volume.
- **Phase-specific patterns**: See `references/volume_progression_macro.md` for base/build/peak/taper guidance.

**Example 1: Single-sport runner (4-week generic block)**

```json
{
  "template_version": "macro_template_v1",
  "total_weeks": 4,
  "weekly_volumes_km": [40.0, 42.0, 45.0, 35.0],
  "target_systemic_load_au": [0.0, 0.0, 0.0, 0.0],
  "workout_structure_hints": [
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "steady", "pct_range": [25, 30]}, "intensity_balance": {"low_intensity_pct": 0.85}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "steady", "pct_range": [26, 30]}, "intensity_balance": {"low_intensity_pct": 0.82}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "steady", "pct_range": [28, 32]}, "intensity_balance": {"low_intensity_pct": 0.80}},
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "easy", "pct_range": [22, 26]}, "intensity_balance": {"low_intensity_pct": 0.90}}
  ]
}
```

**Example 2: Multi-sport athlete (4-week block)**

```json
{
  "template_version": "macro_template_v1",
  "total_weeks": 4,
  "weekly_volumes_km": [35.0, 38.0, 40.0, 30.0],
  "target_systemic_load_au": [85.0, 92.0, 98.0, 75.0],
  "workout_structure_hints": [
    {"quality": {"max_sessions": 1, "types": ["strides_only"]}, "long_run": {"emphasis": "steady", "pct_range": [25, 30]}, "intensity_balance": {"low_intensity_pct": 0.85}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "steady", "pct_range": [26, 30]}, "intensity_balance": {"low_intensity_pct": 0.82}},
    {"quality": {"max_sessions": 2, "types": ["tempo", "intervals"]}, "long_run": {"emphasis": "steady", "pct_range": [28, 32]}, "intensity_balance": {"low_intensity_pct": 0.80}},
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

6. Generate review document:

**Structure**: Follow `references/review_doc_template.md` exactly.

**Critical requirements**:
- Complete volume table (all weeks, no omissions)
- Coaching rationale explains WHY these decisions (build trust)
- Multi-sport section ONLY if `other_sports` in profile (check with `sce profile get`)
- Systemic load column:
  - Multi-sport: Show total load targets (running + other sports)
  - Single-sport: Use 0.0 or omit column
- Pace zones from VDOT using `sce vdot paces --vdot {value}`
- Storage note: temporary in `/tmp/`, permanent in `data/plans/` after approval

Write to: `/tmp/macro_plan_review_YYYY_MM_DD.md`

**Validation**: After writing, verify:
- All weeks have entries (count rows = total_weeks)
- Recovery weeks clearly marked
- Phase transitions align with table
- Approval prompt is athlete-facing (no CLI commands exposed)

## References (load only if needed)

- Review doc structure: `references/review_doc_template.md`
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
- `athlete_prompt` (single yes/no + adjustment question)
- If blocked: `blocking_checklist`
