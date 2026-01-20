---
name: training-plan-design
description: Design personalized training plans for 5K-Marathon races using Pfitzinger periodization, Daniels pace zones, and 80/20 principles. Uses progressive disclosure (macro plan + monthly 4-week cycles) to reduce errors and enable adaptive planning. Accounts for multi-sport constraints, CTL-based volume progression, and injury history. Use when athlete requests "design my plan", "create training program", "how should I train for [race]", or after first-session onboarding.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Training Plan Design

## Overview

This skill designs evidence-based training plans using **progressive disclosure**:
- **Macro plan** (16-week structure): Phase boundaries, volume trajectory, CTL projections
- **Monthly plan** (4-week detail): Detailed workouts for next month only
- **Adaptive planning**: Reassess and regenerate each month based on actual response

**Training methodology**:
- Pfitzinger periodization (base → build → peak → taper)
- Daniels VDOT pace system (E/M/T/I/R zones)
- 80/20 intensity distribution
- CTL-based volume progression
- Multi-sport integration
- Guardrails validation (injury prevention)

**IMPORTANT: All distances in kilometers (km), all paces in min/km. System is fully metric.**

---

## CRITICAL PRINCIPLE: CLI-Only Computation

❌ **DO NOT manually calculate**:
- Dates (use `sce dates` commands)
- Volumes (use `sce guardrails` commands)
- Distances (use intent-based JSON format)
- HR zones (system calculates from max HR)
- Pace zones (use `sce vdot paces` command)
- Run counts (use `sce plan suggest-run-count`)

✅ **DO use CLI tools for ALL computations**

**Why**: Manual calculations introduce errors. The CLI guarantees correctness.

---

## Handling Interruptions

If interrupted, determine state by checking which files exist:
- `/tmp/macro_plan.json` exists? → Resume from Step 5
- `/tmp/monthly_plan_m1.json` exists? → Resume from Step 7
- `/tmp/training_plan_review_*.md` exists? → Resume from Step 9

Re-run context gathering if needed: `sce profile get`, `sce status`, `sce dates today`

---

## Copyable Workflow Checklist

```
Task Progress:
- [ ] Step 0: Get current date (sce dates today, next-monday)
- [ ] Step 1: Retrieve memories (injury history, preferences)
- [ ] Step 2: Gather context (sce profile get, sce status)
- [ ] Step 3: Calculate safe volumes (sce guardrails safe-volume)
- [ ] Step 3.5: PRE-FLIGHT CHECKS (run suggest-run-count for each week) ← CRITICAL
- [ ] Step 4: Generate macro plan (sce plan create-macro)
- [ ] Step 5: Determine VDOT (sce vdot calculate/estimate-current)
- [ ] Step 6: Generate first month (sce plan generate-month, use intent-based JSON)
- [ ] Step 7: Validate plan (sce plan validate-month)
- [ ] Step 8: Create markdown review (/tmp/training_plan_review_*.md)
- [ ] Step 9: Get athlete approval (present markdown, wait for OK)
- [ ] Step 10: Save plan (sce plan populate --from-json)
```

---

## Essential Commands

### Dates (ISO Weekdays: 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat, 7=Sun)
```bash
TODAY=$(sce dates today | jq -r '.data.date')
START_DATE=$(sce dates next-monday | jq -r '.data.date')
sce dates validate --date $START_DATE --must-be monday
```
**DO NOT use 0-6 notation (Python weekday). Use 1-7 (ISO weekday) in plan JSON.**

### Pre-Flight Validation (MANDATORY)
```bash
sce plan suggest-run-count --volume $KM --max-runs $MAX --phase $PHASE
sce guardrails safe-volume --ctl $CTL --goal-type $GOAL --recent-volume $RECENT
sce guardrails analyze-progression --previous $PREV --current $CURR
```

### Plan Generation
```bash
sce plan create-macro --goal-type $GOAL --race-date $DATE --start-date $START \
  --starting-volume $START_KM --peak-volume $PEAK_KM > /tmp/macro_plan.json

sce plan generate-month --month 1 --weeks "1,2,3,4" \
  --from-macro /tmp/macro_plan.json --current-vdot $VDOT > /tmp/monthly_plan_m1.json

sce plan validate-month --monthly-plan /tmp/monthly_plan_m1.json
sce plan populate --from-json /tmp/monthly_plan_m1.json  # After approval only
```

---

## Workflow Steps

### Step 0: Get Current Date

**Run**:
```bash
TODAY=$(sce dates today | jq -r '.data.date')
START_DATE=$(sce dates next-monday | jq -r '.data.date')
sce dates validate --date $START_DATE --must-be monday
```

**Success**: You have $START_DATE (verified Monday). Proceed to Step 1.

---

### Step 1: Retrieve Memories

**Run**:
```bash
sce memory list --type INJURY_HISTORY
sce memory list --type TRAINING_RESPONSE
sce memory list --type PREFERENCE
```

**Success**: Noted injury triggers, training preferences, constraints. Proceed to Step 2.

---

### Step 2: Gather Context

**Run**:
```bash
sce profile get
sce status
```

**Extract**:
- Current CTL: _____
- Goal: race type _____, date _____, time goal _____
- Constraints: max_run_days _____, max_session_minutes _____
- Running priority: PRIMARY / EQUAL / SECONDARY

**Verify constraints** via conversation:
- "How many days per week can you realistically run?"
- "What's your long run max duration?"
- "Are other sports fixed or flexible?"

**Success**: You have CTL, confirmed constraints, noted multi-sport commitments. Proceed to Step 3.

---

### Step 3: Calculate Safe Volumes

**Run**:
```bash
RECENT_VOLUME=$(sce profile get | jq -r '.data.running_volume.recent_4wk // 0')
sce guardrails safe-volume --ctl $CTL --goal-type $GOAL --recent-volume $RECENT_VOLUME
STARTING_VOLUME=$(echo "$result" | jq -r '.data.recommended_start_km')
PEAK_VOLUME=$(echo "$result" | jq -r '.data.recommended_peak_km')
```

**Success**: You have $STARTING_VOLUME and $PEAK_VOLUME. Starting ≤ 110% of recent volume (10% rule). Proceed to Step 3.5.

**See [volume_progression.md](references/volume_progression.md) for detailed rules.**

---

### Step 3.5: Pre-Flight Validation (CRITICAL - DO NOT SKIP)

**For EACH week in your planned macro, run**:
```bash
sce plan suggest-run-count --volume $WEEK_KM --max-runs $MAX_RUNS --phase $PHASE
```

**Example**:
```bash
# Week 1: 23km base
sce plan suggest-run-count --volume 23 --max-runs 4 --phase base
# Returns: {"recommended_runs": 3, "rationale": "23km/4 runs → 4.3km easy (below 5km min)"}
```

**Action**: If `recommended_runs < max_runs`, adjust plan to use fewer runs. DO NOT create weeks violating 5km easy / 8km long minimums.

**Success**: All weeks validated, no violations. Proceed to Step 4.

**See [choosing_run_count.md](references/choosing_run_count.md) for guidance.**

---

### Step 4: Generate Macro Plan

**Run**:
```bash
sce plan create-macro \
  --goal-type $GOAL_TYPE \
  --race-date $RACE_DATE \
  --start-date $START_DATE \
  --starting-volume $STARTING_VOLUME \
  --peak-volume $PEAK_VOLUME \
  > /tmp/macro_plan.json
```

**Verify**:
```bash
test -f /tmp/macro_plan.json && echo "✓ Macro plan created"
jq -r '.phase_boundaries, .volume_trajectory' /tmp/macro_plan.json
```

**Success**: File exists with phase_boundaries and volume_trajectory. Proceed to Step 5.

**See [periodization.md](references/periodization.md) for phase allocation.**

---

### Step 5: Determine VDOT & Training Paces

**Option A - Recent race (<6 weeks)**:
```bash
sce race list
BASELINE_VDOT=$RACE_VDOT
```

**Option B - Estimate from workouts**:
```bash
sce vdot estimate-current --lookback-days 28
BASELINE_VDOT=$ESTIMATED_VDOT
```

**Option C - No data**:
```bash
BASELINE_VDOT=45  # Conservative estimate (CTL 30-40 → VDOT 45, CTL 40-50 → VDOT 48)
```

**Calculate paces**:
```bash
sce vdot paces --vdot $BASELINE_VDOT
```

**Success**: You have $BASELINE_VDOT and training pace zones (E/M/T/I/R). Proceed to Step 6.

**See [pace_zones.md](references/pace_zones.md) for detailed scenarios.**

---

### Step 6: Generate First Monthly Plan (Weeks 1-4)

**FORMAT REQUIREMENT**: Use **intent-based format** (see [json_workflow.md](references/json_workflow.md)).

**Why**: You specify `target_volume_km` and `workout_pattern`, system calculates exact distances (guaranteed correct). DO NOT manually calculate distances.

**Run**:
```bash
sce plan generate-month \
  --month 1 \
  --weeks "1,2,3,4" \
  --from-macro /tmp/macro_plan.json \
  --current-vdot $BASELINE_VDOT \
  > /tmp/monthly_plan_m1.json
```

**Validate**:
```bash
sce plan validate-month --monthly-plan /tmp/monthly_plan_m1.json
```

**Success**: Validation passes (<5% volume discrepancy), no minimum duration violations (easy ≥5km, long ≥8km), recovery week at ~70%. Proceed to Step 7.

**If fails (>10% discrepancy)**: Regenerate with adjusted parameters.

**See [workout_generation.md](references/workout_generation.md) for details.**

---

### Step 7: Validate Against Guardrails

**Validation already done in Step 6.** Spot-check if needed:

```bash
sce guardrails quality-volume --t-pace 6.0 --i-pace 4.0 --weekly-volume 50.0
sce guardrails long-run --duration 120 --weekly-volume 55 --pct-limit 30
sce guardrails analyze-progression --previous 44 --current 48
```

**Success**: <5% volume discrepancy, no violations, quality limits respected (T≤10%, I≤8%, R≤5%), long run ≤30%, no week >10% increase. Proceed to Step 8.

**Volume tolerance**: <5% acceptable, 5-10% review, >10% regenerate.

**See [guardrails.md](references/guardrails.md) for complete rules.**

---

### Step 8: Create Markdown Review

**Create**:
```bash
cp templates/plan_presentation.md /tmp/training_plan_review_$(date +%Y_%m_%d).md
# Edit with: macro plan summary, first month workouts, training paces, guardrails check
```

**Verify dates**:
```bash
start_date=$(jq -r '.weeks[0].start_date' /tmp/monthly_plan_m1.json)
sce dates validate --date $start_date --must-be monday
```

**Success**: File exists with macro summary and first month details, all week start dates are Monday. Proceed to Step 9.

---

### Step 9: Present for Approval (CRITICAL)

**NEVER save directly. Always present markdown for approval first.**

**Present**:
```
I've designed your [race] plan using progressive disclosure:

📋 Review: /tmp/training_plan_review_YYYY_MM_DD.md

**Macro plan** (16 weeks): [X] phases, [Start]→[Peak] km/week, respects constraints
**First month** (weeks 1-4): Detailed daily workouts with paces
**Next months**: Generated every 4 weeks based on actual response

Approve, request changes, or ask questions?
```

**Handle response**:
- "Approve" → Proceed to Step 10
- "Change X" → Clarify → Regenerate → Return to Step 9
- "Question Y" → Answer → Re-confirm → Proceed when approved

**Success**: Athlete explicitly approved. Proceed to Step 10 ONLY after approval.

---

### Step 10: Save Plan to System

**Save**:
```bash
cp /tmp/macro_plan.json data/plans/current_plan_macro.json
sce plan populate --from-json /tmp/monthly_plan_m1.json
sce plan save-review --from-file /tmp/training_plan_review_$(date +%Y_%m_%d).md --approved
sce plan init-log
```

**Verify**:
```bash
sce plan show
sce plan week --next
```

**Success**: Macro saved to `data/plans/current_plan_macro.json`, first month saved to `data/plans/current_plan.yaml`, review saved, log initialized. `sce plan show` displays correctly.

**For future monthly cycles**: Use `monthly-transition` skill after completing weeks 1-4 to generate month 2 (weeks 5-8).

---

## Reference Documentation

**REQUIRED reading for specific steps**:
- **[json_workflow.md](references/json_workflow.md)** - Intent-based format (Step 6)
- **[choosing_run_count.md](references/choosing_run_count.md)** - suggest-run-count usage (Step 3.5)
- **[common_pitfalls.md](references/common_pitfalls.md)** - What NOT to do (read before any plan)

**Supporting references**:
- **[volume_progression.md](references/volume_progression.md)** - 10% rule interpretation
- **[periodization.md](references/periodization.md)** - Phase allocation
- **[pace_zones.md](references/pace_zones.md)** - VDOT scenarios and workout prescriptions
- **[workout_generation.md](references/workout_generation.md)** - Workout prescription details
- **[guardrails.md](references/guardrails.md)** - Safety rules
- **[multi_sport.md](references/multi_sport.md)** - Multi-sport integration

**Decision trees and update strategies**: See [common_pitfalls.md](references/common_pitfalls.md) for:
- Volume conflicts (athlete wants more than CTL suggests)
- Insufficient weeks to goal
- Multi-sport conflicts during key workouts
- Injury history adjustments
- Unknown VDOT scenarios
- Plan update strategies (mid-week, partial replan, full regeneration)
