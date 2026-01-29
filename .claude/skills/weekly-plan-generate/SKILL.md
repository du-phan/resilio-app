---
name: weekly-plan-generate
description: Generates a single-week intent-based plan JSON and presents the review directly in chat without applying it. Use for Week 1 and all subsequent weeks.
disable-model-invocation: true
context: fork
agent: weekly-planner
allowed-tools: Bash, Read, Write
argument-hint: "[optional-notes]"
---

# Weekly Plan Generate (Executor)

Non-interactive. Use CLI only. Do not apply/save the plan.

## Preconditions (block if missing)
- Macro plan exists
- Target week identified (next unpopulated OR current week for update)
- Profile constraints present

If missing, return a blocking checklist and stop.

## Workflow

1) Identify target week:
```bash
sce plan next-unpopulated
sce plan status
sce plan week           # current week (use when updating current week)
sce plan week --week <N>
```
If the parent agent requests a current-week update, use `sce plan week` to set
`week_number`, `start_date`, `end_date`, and `phase`. Otherwise default to
the next unpopulated week.
Use `workout_structure_hints` from the macro plan week as the primary structure guide.

2) Load current metrics and recent response:
```bash
sce status
sce week
```
If you already have an activities JSON file for the last 28 days, you may run:
`sce analysis intensity --activities <FILE> --days 28`

3) Guardrails context:
```bash
sce guardrails analyze-progression \
  --previous <PREV_ACTUAL_KM> \
  --current <PROPOSED_KM> \
  --ctl <CTL> \
  --run-days <MAX_RUN_DAYS> \
  --age <AGE>
```

4) Produce intent-based weekly JSON:
**CRITICAL: ALWAYS use the CLI generator - NEVER manually construct JSON**

```bash
sce plan generate-week \
  --week <WEEK_NUMBER> \
  --run-days "<RUN_DAYS_CSV>" \
  --long-run-day <LONG_RUN_DAY> \
  --long-run-pct <LONG_RUN_PCT> \
  --easy-run-paces "<EASY_PACES>" \
  --long-run-pace "<LONG_PACE>" \
  --structure "<DESCRIPTIVE_STRUCTURE>" \
  --out /tmp/weekly_plan_w<week>.json
```

This command automatically generates a properly formatted JSON with all required fields:
- `week_number`, `phase`, `start_date`, `end_date`, `target_volume_km`, `target_systemic_load_au`
- `workout_pattern` with `run_days` (0=Mon..6=Sun), `long_run_day`, `long_run_pct`, and all required pace fields
- Complete workout specifications that pass validation

5) Validate:
```bash
sce plan validate-week --file /tmp/weekly_plan_w<week>.json
```

5b) Interval structure validation (conditional):
Run **only if** the generated week includes a structured tempo/interval workout
with explicit work + recovery bouts (Daniels-style). If not, skip.

Prepare two small JSON files from the planned session:
- `/tmp/work_bouts.json` (list of work bouts with durations)
- `/tmp/recovery_bouts.json` (list of recovery bouts)

Example formats:
```json
[
  { "duration_minutes": 4.0, "distance_km": 1.0, "pace_per_km_seconds": 240 },
  { "duration_minutes": 4.0, "distance_km": 1.0, "pace_per_km_seconds": 240 }
]
```

```json
[
  { "duration_minutes": 2.0, "type": "jog" },
  { "duration_minutes": 2.0, "type": "jog" }
]
```

Then run:
```bash
sce plan validate-intervals \
  --type intervals \
  --intensity I-pace \
  --work-bouts /tmp/work_bouts.json \
  --recovery-bouts /tmp/recovery_bouts.json \
  --weekly-volume <WEEKLY_KM>
```

6) Present directly in chat:
- Summary + rationale
- Volume change vs previous week
- Workouts by day
- Approval prompt text for the athlete
- Handoff note: main agent must record approval via
  `sce approvals approve-week --week <WEEK_NUMBER> --file /tmp/weekly_plan_w<week>.json`

## References (load only if needed)
- Weekly volume progression: `references/volume_progression_weekly.md`
- Workout generation: `references/workout_generation.md`
- Choosing run count: `references/choosing_run_count.md`
- Pace zones: `references/pace_zones.md`
- Guardrails: `references/guardrails_weekly.md`
- JSON workflow: `references/json_workflow.md`
- Multi-sport integration: `references/multi_sport_weekly.md`
- Common pitfalls: `references/common_pitfalls_weekly.md`
- Core methodology: `docs/coaching/methodology.md`

## Output
Return:
- `weekly_json_path`
- `week_number`
- `athlete_prompt` (single yes/no + adjustment question)
