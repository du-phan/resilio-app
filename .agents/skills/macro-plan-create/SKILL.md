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

2. Extract profile context and determine volumes:

```bash
# Get running priority from profile
PRIORITY=$(sce profile get | jq -r '.data.running_priority')

# If priority is null/empty, BLOCK - profile incomplete
if [ -z "$PRIORITY" ] || [ "$PRIORITY" == "null" ]; then
  echo '{"blocking_checklist": ["Profile missing running_priority field. Run: sce profile set --run-priority [primary|equal|secondary]"]}'
  exit 1
fi

# Get safe volume with priority context
sce guardrails safe-volume \
  --ctl <CTL> \
  --priority "$PRIORITY" \
  --goal <GOAL_TYPE> \
  --age <AGE> \
  --recent-volume <RECENT_VOLUME_KM>
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
MAX_FEASIBLE=$(echo "$FEASIBILITY" | jq -r '.data.max_weekly_volume_km')
RECOMMENDED_PEAK=$(echo "$SAFE_VOL" | jq -r '.data.recommended_peak_km')
```

**Priority-aware feasibility handling**:

The CLI has provided priority-adjusted volumes and feasibility data. Decision logic:

- **If PRIMARY + infeasible**: BLOCK - athlete needs to increase time/days or adjust goal
- **If EQUAL/SECONDARY + infeasible**: PROCEED with max_feasible - legitimate multi-sport constraint

```bash
# For PRIMARY athletes, enforce feasibility strictly
if [ "$PRIORITY" == "primary" ] && [ "$OVERALL_OK" == "false" ]; then
  echo '{"blocking_checklist": ["Peak volume infeasible for PRIMARY priority athlete", "Data: [extract from FEASIBILITY]", "Main agent: Discuss increasing session time/frequency or adjusting goal"]}'
  exit 1
fi

# For EQUAL/SECONDARY, max_feasible is appropriate
if [ "$OVERALL_OK" == "false" ]; then
  USE_PEAK=$MAX_FEASIBLE
else
  USE_PEAK=$RECOMMENDED_PEAK
fi
```

**Context for AI coach**: The skill provides data; AI coach in main agent makes final judgment based on:
- Priority (EQUAL/SECONDARY can legitimately use lower volumes)
- Athlete's other sports commitments
- Goal importance vs sustainability
- Multi-sport load patterns

**Fallback**: If VDOT paces fails, use conservative estimates (VDOT 30-40: 7.0, 41-50: 6.0, 51-60: 5.5, 61+: 5.0 min/km).

3. Create a macro template JSON at `/tmp/macro_template.json` using the CLI:

```bash
sce plan template-macro --total-weeks <N> --out /tmp/macro_template.json
```

Fill the template (replace all nulls) with AI-coach decisions:

**NOTE**: The CLI has provided priority-adjusted volumes and feasibility data. YOU (the AI coach) now make the final coaching decisions:

- **Starting volume**: Consider recommended_start_km from safe-volume (already priority-adjusted)
- **Peak volume**: Choose between recommended_peak and max_feasible based on:
  - Priority (EQUAL/SECONDARY can use lower volumes legitimately)
  - Athlete's other sports commitments (climbing frequency, intensity)
  - Goal importance vs sustainability
  - Time constraints are real - respect them
- **Weekly progression**: 5-10% guideline, but adjust based on:
  - Multi-sport load patterns (climbing weeks, yoga frequency)
  - Historical adaptation rates
  - Injury history
- **Recovery weeks**: Every 3-4 weeks at ~70%, but consider:
  - Climbing trips or other sport intensification
  - Life stress, travel
- **Coaching notes**: Explain WHY you chose this peak/progression
  - Don't just cite the numbers - explain the judgment call
  - If using max_feasible < recommended_peak, explain why that's appropriate for this athlete
  - Reference priority and multi-sport context

**PHILOSOPHY**: The CLI gives you data. You provide wisdom.

See `references/volume_progression_macro.md` for base/build/peak/taper guidance.

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
