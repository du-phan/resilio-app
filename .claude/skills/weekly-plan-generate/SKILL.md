---
name: weekly-plan-generate
description: Generates a single-week intent-based plan JSON and review doc without applying it. Use for Week 1 and all subsequent weeks.
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

2) Load current metrics and recent response:
```bash
sce status
sce week
sce analysis adherence --days 28
sce analysis intensity --days 28
```

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
- `week_number`, `phase`, `start_date`, `end_date`, `target_volume_km`, `target_systemic_load_au`
- `workout_pattern` with `run_days` (0=Mon..6=Sun), `long_run_day`, `long_run_pct`, paces

Write to `/tmp/weekly_plan_w<week>.json`.

Preferred: use CLI generator if available to avoid manual JSON edits:
```bash
sce plan generate-week \
  --week <WEEK_NUMBER> \
  --run-days "<RUN_DAYS_CSV>" \
  --long-run-day <LONG_RUN_DAY> \
  --long-run-pct <LONG_RUN_PCT> \
  --easy-run-paces "<EASY_PACES>" \
  --long-run-pace "<LONG_PACE>" \
  --out /tmp/weekly_plan_w<week>.json
```

5) Validate:
```bash
sce plan validate --file /tmp/weekly_plan_w<week>.json
```

6) Write `/tmp/weekly_plan_review_YYYY_MM_DD.md` with:
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
- `review_path`
- `week_number`
