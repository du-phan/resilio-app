---
name: training-plan-design
description: Design personalized training plans for 5K-Marathon races using Pfitzinger periodization, Daniels pace zones, and 80/20 principles. Uses progressive disclosure (macro plan + weekly detail) to reduce errors and enable adaptive planning. Accounts for multi-sport constraints, CTL-based volume progression, and injury history. Use when athlete requests "design my plan", "create training program", "how should I train for [race]", or after first-session onboarding.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Training Plan Design

## Overview

Creates evidence-based training plans using progressive disclosure:
- **Plan skeleton** (16 weeks): Phase boundaries, stub weeks with volume targets
- **Week 1 detail**: AI-designed workout structure for FIRST WEEK ONLY
- **Future weeks**: Designed weekly via weekly-analysis skill

Methodology: Pfitzinger periodization, Daniels VDOT paces, 80/20 intensity, AI-driven volume progression with **mandatory guardrails validation**.

**CRITICAL**: This workflow has MANDATORY checkpoints that CANNOT be skipped:
- ⚠️ **suggest-run-count** (Step 2 AND Step 5): Prevents creating weeks with runs below minimums (<5km easy, <8km long)
- ⚠️ **plan validate** (Step 5): Catches volume/duration violations before presenting to athlete
- ⚠️ **Athlete approval** (Step 7): Always present markdown review, wait for explicit approval

## Workflow

```
MANDATORY LINEAR WORKFLOW - DO NOT SKIP STEPS

Step 1: Context Gathering
        → sce dates, sce profile get, sce status, sce memory list
        ⛔ BLOCKER: Must have typical_easy_distance_km and typical_long_run_distance_km

Step 2: Safe Volumes & Pre-Flight ⚠️ MANDATORY
        → sce guardrails safe-volume
        → sce plan suggest-run-count (stores RECOMMENDED_RUNS)
        ⛔ BLOCKER: Must run suggest-run-count before creating any structures

Step 3: Create Plan Skeleton
        → sce plan create-macro (auto-persists to data/plans/current_plan.yaml)
        ⛔ BLOCKER: Must verify skeleton with sce plan show

Step 4: Determine VDOT
        → sce race list / sce vdot estimate-current / conservative default
        → sce vdot paces --vdot X

Step 5: Design Week 1 Workouts ⚠️ MANDATORY VALIDATION
        → sce plan suggest-run-count (re-validate for Week 1 volume)
        → Create workout_pattern JSON manually
        → sce plan validate --file /tmp/weekly_plan_w1.json (must have 0 violations)
        ⛔ BLOCKER: Cannot proceed until validation passes

Step 6: Create Review Markdown
        → Macro summary + Week 1 details in /tmp/training_plan_review_YYYY_MM_DD.md

Step 7: Present & Save
        → Present markdown to athlete
        → Wait for approval
        → sce plan populate --from-json /tmp/weekly_plan_w1.json
        ⛔ BLOCKER: NEVER save without explicit approval
```

## Step Details

### Step 1: Context Gathering

Run these commands:
```bash
poetry run sce dates today
poetry run sce dates next-monday
poetry run sce profile get
poetry run sce status
poetry run sce memory list --type INJURY_HISTORY
```

**Exit criteria:**
- [ ] START_DATE verified Monday (use `sce dates validate`)
- [ ] GOAL_TYPE, RACE_DATE, TARGET_TIME, MAX_RUN_DAYS extracted
- [ ] TYPICAL_EASY and TYPICAL_LONG populated (NOT null)
- [ ] CTL, TSB, ACWR known

**⛔ BLOCKER**: If typical_easy_distance_km or typical_long_run_distance_km are null:
1. Run `sce profile analyze` to auto-detect from Strava
2. If still null, use AskUserQuestion to ask athlete
3. Store with `sce profile set`

### Step 2: Safe Volumes & Pre-Flight Validation ⚠️

**See [volume_progression.md](references/volume_progression.md) for 10% rule interpretation.**
**See [choosing_run_count.md](references/choosing_run_count.md) for suggest-run-count logic.**

Run these commands:
```bash
poetry run sce guardrails safe-volume --ctl $CTL --goal-type $GOAL --recent-volume $VOL
poetry run sce plan suggest-run-count --volume $STARTING_VOLUME --max-runs $MAX --phase base
```

**Critical checkpoint**: Run `suggest-run-count` BEFORE creating any plan structures. Store RECOMMENDED_RUNS for use in Step 5.

**Exit criteria:**
- [ ] STARTING_VOLUME and PEAK_VOLUME calculated
- [ ] suggest-run-count executed
- [ ] RECOMMENDED_RUNS stored

**Why this matters**: Skipping suggest-run-count leads to creating weeks like "4 runs at 20km = 5km per run" which violates the 5km easy minimum.

### Step 3: Create Plan Skeleton

Run this command:
```bash
poetry run sce plan create-macro \
    --goal-type $GOAL_TYPE \
    --race-date $RACE_DATE \
    --target-time "$TARGET_TIME" \
    --total-weeks $TOTAL_WEEKS \
    --start-date $START_DATE \
    --current-ctl $CTL \
    --starting-volume-km $STARTING_VOLUME \
    --peak-volume-km $PEAK_VOLUME
```

Creates MasterPlan skeleton with stub weeks (phase, dates, volume targets, empty workouts). Auto-persists to `data/plans/current_plan.yaml`.

**Exit criteria:**
- [ ] create-macro completed (exit code 0)
- [ ] data/plans/current_plan.yaml exists
- [ ] `sce plan show` displays skeleton with phases

### Step 4: Determine VDOT & Training Paces

**See [pace_zones.md](references/pace_zones.md) for all VDOT scenarios.**

Options:
- Recent race: `sce race list`
- Estimate: `sce vdot estimate-current --lookback-days 28`
- Conservative: CTL 30-40 → VDOT 42, CTL 40-50 → VDOT 45

Get paces:
```bash
poetry run sce vdot paces --vdot $BASELINE_VDOT
```

**Exit criteria:**
- [ ] BASELINE_VDOT determined
- [ ] EASY_PACE, TEMPO_PACE extracted in min/km format

### Step 5: Design Week 1 Workouts ⚠️

**See [workout_generation.md](references/workout_generation.md) for workout_pattern JSON format.**
**See [json_workflow.md](references/json_workflow.md) for intent-based format specification.**

**Critical checkpoints**:
1. **Validate run count**:
   ```bash
   poetry run sce plan suggest-run-count --volume $WEEK1_VOLUME --max-runs $MAX --phase base
   ```
   Use WEEK1_RUN_COUNT (not MAX_RUN_DAYS) in workout structure.

2. **Create workout_pattern JSON** manually with:
   - `run_days`: Based on WEEK1_RUN_COUNT (e.g., 3 runs = [1,3,6] = Tue/Thu/Sun)
   - `long_run_pct`: Base=0.45, Build/Peak=0.47, Recovery=0.52
   - `paces`: From `sce vdot paces` output (NO hardcoded values)

3. **Validate BEFORE presenting**:
   ```bash
   poetry run sce plan validate --file /tmp/weekly_plan_w1.json
   ```
   Must have 0 violations.

**Exit criteria:**
- [ ] suggest-run-count executed and WEEK1_RUN_COUNT used
- [ ] /tmp/weekly_plan_w1.json created with workout_pattern
- [ ] plan validate executed with 0 violations

**⛔ BLOCKER**: If validation fails, regenerate JSON fixing violations. Do NOT proceed until validation passes.

### Step 6: Create Review Markdown

Create `/tmp/training_plan_review_$(date +%Y_%m_%d).md` with:
- **Macro overview**: 16 weeks, phases, volume progression (Start → Peak)
- **Week 1 details**: Daily workouts with paces/distances/durations
- **Future weeks**: "Weeks 2-16 designed weekly based on actual training response, validated by guardrails"
- **Training paces**: VDOT table with source noted (race/estimate/default)

### Step 7: Present & Save

**⛔ NEVER save directly. ALWAYS present for approval first.**

Present to athlete:
```
I've designed your [Race Type] training plan using progressive disclosure.

📋 Review: /tmp/training_plan_review_YYYY_MM_DD.md

**Plan Structure** (16 weeks):
- Start: [Date], [X] km/week
- Peak: [X] km/week in week [N]
- Phases: Base (1-5), Build (6-10), Peak (11-14), Taper (15-16)

**Week 1** (detailed): [N] runs, [X] km total
- [List days and distances]
- Paces: Easy [min/km], based on VDOT [X]

Questions or changes?
```

**Save** (ONLY after approval):
```bash
poetry run sce plan populate --from-json /tmp/weekly_plan_w1.json
poetry run sce plan save-review --from-file /tmp/training_plan_review_$(date +%Y_%m_%d).md --approved
poetry run sce plan show  # Verify
```

**Exit criteria:**
- [ ] Athlete explicitly approved
- [ ] plan populate executed successfully
- [ ] `sce plan show` displays week 1 with workouts

## Critical Boundaries

### ⛔ Mandatory Checkpoints (CANNOT BE SKIPPED)

1. **suggest-run-count** (Step 2 AND Step 5) - Prevents runs below minimums
2. **plan validate** (Step 5) - Catches violations before presenting
3. **Athlete approval** (Step 7) - Never save without confirmation

### ⛔ Do Not Do

- Skip guardrails: "I'll just use 4 runs" without suggest-run-count
- Manual calculations: "22km / 4 = 5.5km" → Use CLI tools
- Save without approval: Present first, save after
- Generate weeks 2-16: Week 1 ONLY
- Hardcode values: Get paces from `sce vdot paces`

### ✅ Do This

- Use CLI for everything: Dates, volumes, paces, validation
- Run suggest-run-count twice: Step 2 + Step 5
- Validate before presenting: Athlete sees validated plan
- Explain methodology: Use training science

## When Things Go Wrong

**See [common_pitfalls.md](references/common_pitfalls.md) for troubleshooting.**

Common problems:
- **suggest-run-count returns fewer runs**: Explain 5km minimum constraint, offer options (use fewer runs / increase volume / override with rationale)
- **Validation fails**: Check workout_pattern math, verify percentages sum to 1.0
- **Athlete wants more volume than safe**: Explain ACWR injury risk with data, offer conservative ramp
- **Workflow interrupted**: Check `/tmp/weekly_plan_w1.json`, `/tmp/training_plan_review_*.md`, `sce plan show` to determine last completed step

## Reference Documentation

**Core references**:
- **[json_workflow.md](references/json_workflow.md)** - Intent-based workout_pattern format
- **[workout_generation.md](references/workout_generation.md)** - Workout structure and JSON examples
- **[choosing_run_count.md](references/choosing_run_count.md)** - suggest-run-count logic and minimums
- **[common_pitfalls.md](references/common_pitfalls.md)** - What NOT to do

**Supporting references**:
- **[volume_progression.md](references/volume_progression.md)** - 10% rule, load classification
- **[pace_zones.md](references/pace_zones.md)** - VDOT scenarios and pace calculations
- **[periodization.md](references/periodization.md)** - Phase allocation logic
- **[guardrails.md](references/guardrails.md)** - Safety rules (quality volume, long run caps)
- **[multi_sport.md](references/multi_sport.md)** - Multi-sport integration

## Architecture

**ONE file system** (as of 2026-01-21):
- `create-macro` creates MasterPlan skeleton, auto-persists to `data/plans/current_plan.yaml`
- Stub weeks contain ONLY structural data (phase, dates, volume targets, empty workouts)
- AI coach designs workout structure progressively (not pre-computed)

**Philosophy**: Package provides tools, AI coach provides intelligence.
