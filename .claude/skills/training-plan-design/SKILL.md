---
name: training-plan-design
description: Design personalized training plans for 5K-Marathon races using Pfitzinger periodization, Daniels pace zones, and 80/20 principles. Uses progressive disclosure (macro plan + weekly detail) to reduce errors and enable adaptive planning. Accounts for multi-sport constraints, CTL-based volume progression, and injury history. Use when athlete requests "design my plan", "create training program", "how should I train for [race]", or after first-session onboarding.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Training Plan Design

## Overview

This skill designs evidence-based training plans using **progressive disclosure**:
- **Macro plan** (16-week structure): Phase boundaries, recovery weeks, starting/peak volume targets
- **Weekly plan** (1-week detail): AI-designed volume + detailed workouts for NEXT WEEK ONLY
- **Adaptive planning**: Regenerate weekly based on actual response (via weekly-analysis skill)

Training methodology: Pfitzinger periodization, Daniels VDOT paces, 80/20 intensity, AI-driven volume progression with guardrails validation, multi-sport integration.

**IMPORTANT**: All distances in kilometers (km), all paces in min/km. System is fully metric. Use CLI for ALL calculations (dates, volumes, paces). AI coach designs weekly volumes using guardrails - NO algorithmic interpolation.

---

## Quick Reference

```bash
# Dates (ALWAYS verify)
sce dates today                                    # Current date
sce dates next-monday                              # Plan start date
sce dates validate --date $DATE --must-be monday   # Verify Monday

# Context & Safety
sce status                                         # CTL/ATL/TSB/ACWR
sce profile get                                    # Constraints, goals
sce memory list --type INJURY_HISTORY              # Past injuries
sce guardrails safe-volume --ctl $CTL --goal-type $GOAL --recent-volume $VOL

# Pre-flight validation (MANDATORY)
sce plan suggest-run-count --volume $KM --max-runs $MAX --phase $PHASE

# Plan generation
sce plan create-macro --goal-type $GOAL --race-date $DATE --start-date $START \
  --starting-volume $START_KM --peak-volume $PEAK_KM > /tmp/macro_plan.json

# Week 1 volume design (AI decision, usually = starting_volume)
WEEK1_VOLUME=$STARTING_VOLUME

sce plan generate-week --week-number 1 --target-volume-km $WEEK1_VOLUME \
  --from-macro /tmp/macro_plan.json --current-vdot $VDOT > /tmp/weekly_plan_w1.json

# Validation & Save (AFTER approval)
sce plan validate-week --weekly-plan /tmp/weekly_plan_w1.json
sce plan populate --from-json /tmp/weekly_plan_w1.json
```

---

## Workflow Checklist

```
Task Progress:
- [ ] Step 1: Context (dates, profile, status, memories, WORKOUT PATTERNS)
- [ ] Step 2: Safe volumes (guardrails, pre-flight checks)
- [ ] Step 3: Generate macro (16 weeks, NO WORKOUTS)
- [ ] Step 4: Determine VDOT (calculate/estimate/conservative)
- [ ] Step 5: Generate week 1 ONLY (intent-based JSON)
- [ ] Step 6: Validate (guardrails check)
- [ ] Step 7: Create review markdown (macro summary + week 1 detail)
- [ ] Step 8: Present & save (ONLY after approval)

CRITICAL: Step 1 must detect/ask for typical_easy_distance_km and typical_long_run_distance_km
          - Try `sce profile analyze` first (auto-detect from Strava)
          - If missing, ask athlete directly (AskUserQuestion)
          - NEVER proceed with hardcoded defaults - that's poor coaching
```

---

## Workflow Steps

### Step 1: Gather Context

**Run**:
```bash
TODAY=$(sce dates today | jq -r '.data.date')
START_DATE=$(sce dates next-monday | jq -r '.data.date')
sce dates validate --date $START_DATE --must-be monday
sce profile get
sce status
sce memory list --type INJURY_HISTORY
sce memory list --type PREFERENCE
```

**Extract**: Current CTL, goal (race type/date/time), constraints (max_run_days, max_session_minutes, multi-sport commitments), injury history, training preferences.

**CRITICAL: Check for workout patterns**:
```bash
TYPICAL_EASY=$(sce profile get | jq -r '.data.typical_easy_distance_km')
TYPICAL_LONG=$(sce profile get | jq -r '.data.typical_long_run_distance_km')

if [ "$TYPICAL_EASY" == "null" ] || [ "$TYPICAL_LONG" == "null" ]; then
    # Missing athlete-specific workout patterns - try to detect from Strava
    echo "Detecting your typical workout distances from Strava history..."
    sce profile analyze

    # Recheck
    TYPICAL_EASY=$(sce profile get | jq -r '.data.typical_easy_distance_km')
    TYPICAL_LONG=$(sce profile get | jq -r '.data.typical_long_run_distance_km')

    if [ "$TYPICAL_EASY" == "null" ] || [ "$TYPICAL_LONG" == "null" ]; then
        # Still missing - ask athlete directly (use AskUserQuestion)
        echo "⚠️ Not enough activity history to detect typical workout distances"
        # Ask athlete: "What's your typical easy run distance?" and "typical long run?"
        # Store answers in profile before proceeding
    fi
fi
```

**Success**: You have all context for planning, including athlete-specific workout patterns. Proceed to Step 2.

---

### Step 2: Calculate Safe Volumes & Pre-Flight Validation

**Calculate starting/peak volumes**:
```bash
RECENT_VOLUME=$(sce profile get | jq -r '.data.running_volume.recent_4wk // 0')
result=$(sce guardrails safe-volume --ctl $CTL --goal-type $GOAL --recent-volume $RECENT_VOLUME)
STARTING_VOLUME=$(echo "$result" | jq -r '.data.recommended_start_km')
PEAK_VOLUME=$(echo "$result" | jq -r '.data.recommended_peak_km')
```

**Pre-flight check for week 1** (MANDATORY):
```bash
sce plan suggest-run-count --volume $STARTING_VOLUME --max-runs $MAX_RUNS --phase base
# If recommended_runs < max_runs, adjust plan to use fewer runs
```

**Success**: Safe volumes calculated, week 1 run count validated (no 5km easy / 8km long violations). Proceed to Step 3.

**See [volume_progression.md](references/volume_progression.md) and [choosing_run_count.md](references/choosing_run_count.md) for details.**

---

### Step 3: Generate Macro Plan (16 Weeks, NO WORKOUTS OR VOLUMES)

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
jq -r '.phases, .recovery_weeks, .starting_volume_km, .peak_volume_km' /tmp/macro_plan.json
```

⚠️ **CRITICAL**: Macro plan contains phase boundaries, recovery weeks, and starting/peak volume TARGETS only. Weekly volumes will be designed by AI using guardrails. NO `volume_trajectory` field, NO `workout_pattern` fields.

**Success**: File exists with phases, recovery_weeks, starting_volume_km, peak_volume_km. Proceed to Step 4.

**See [periodization.md](references/periodization.md) for phase allocation.**

---

### Step 4: Determine VDOT & Training Paces

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

**Option C - No data** (conservative default):
```bash
BASELINE_VDOT=45  # CTL 30-40 → VDOT 45, CTL 40-50 → VDOT 48
```

**Calculate paces**:
```bash
sce vdot paces --vdot $BASELINE_VDOT
```

**Success**: You have $BASELINE_VDOT and training pace zones (E/M/T/I/R). Proceed to Step 5.

**See [pace_zones.md](references/pace_zones.md) for detailed scenarios.**

---

### Step 5: Design Week 1 Volume & Generate Workouts

**FORMAT REQUIREMENT**: Use **intent-based format** (see [json_workflow.md](references/json_workflow.md)).

**Design Week 1 Volume** (AI decision):
```bash
# Usually Week 1 = starting_volume (safe ramp-up)
WEEK1_VOLUME=$STARTING_VOLUME

# Optional: Adjust if athlete context requires it
# (e.g., coming off injury: WEEK1_VOLUME=$(echo "$STARTING_VOLUME * 0.85" | bc))

# Optional: Validate progression (usually not needed for Week 1)
sce guardrails safe-volume --ctl $CTL --goal-type $GOAL
```

**Generate Week 1**:
```bash
sce plan generate-week \
  --week-number 1 \
  --target-volume-km $WEEK1_VOLUME \
  --from-macro /tmp/macro_plan.json \
  --current-vdot $BASELINE_VDOT \
  > /tmp/weekly_plan_w1.json
```

⚠️ **CRITICAL BOUNDARY**: Generate week 1 ONLY. Weeks 2-16 will be designed weekly based on actual training response (via weekly-planning skill). Each week's volume is an AI decision using guardrails, not pre-computed.

**Success**: Week 1 JSON created with AI-designed volume and complete `workout_pattern` using intent-based format. Proceed to Step 6.

**See [workout_generation.md](references/workout_generation.md) for details.**

---

### Step 6: Validate Week 1

**Run**:
```bash
sce plan validate-week --weekly-plan /tmp/weekly_plan_w1.json
```

**Check**:
- Volume discrepancy <5% (acceptable), 5-10% (review), >10% (regenerate)
- No minimum duration violations (easy ≥5km, long ≥8km)
- Quality volume limits respected (T≤10%, I≤8%, R≤5%)

**Success**: Validation passes, no violations. Proceed to Step 7.

**See [guardrails.md](references/guardrails.md) for complete rules.**

---

### Step 7: Create Markdown Review

**Create review file**:
```bash
cp templates/plan_presentation.md /tmp/training_plan_review_$(date +%Y_%m_%d).md
# Edit with: macro plan summary (16 weeks), week 1 detailed workouts, training paces
```

**Template structure**:
- **Macro Plan Overview**: 16 weeks, phases, recovery weeks, volume targets (starting → peak)
- **Week 1 Plan (Detailed)**: Daily workouts with paces, distances, durations
- **Upcoming Weeks Preview**: Phase progression overview (base → build → peak → taper)
- **Note**: "Weeks 2-16 volumes will be designed weekly by AI coach based on your actual training response, validated by guardrails"

**Verify dates**:
```bash
start_date=$(jq -r '.weeks[0].start_date' /tmp/weekly_plan_w1.json)
sce dates validate --date $start_date --must-be monday
```

**Success**: Review file exists with macro summary and week 1 details, start date verified Monday. Proceed to Step 8.

**See [plan_presentation.md](templates/plan_presentation.md) for template.**

---

### Step 8: Present for Approval & Save

**NEVER save directly. Always present markdown for approval first.**

**Present**:
```
I've designed your [race] plan using progressive disclosure:

📋 Review: /tmp/training_plan_review_YYYY_MM_DD.md

**Macro plan** (16 weeks): [X] phases, [Start]→[Peak] km/week, respects constraints
**Week 1** (detailed): [N] runs, [X] km, with daily paces and distances
**Future weeks**: Generated weekly based on actual training response

Approve, request changes, or ask questions?
```

**Handle response**:
- "Approve" → Save to system
- "Change X" → Clarify → Regenerate affected parts → Re-present
- "Question Y" → Answer → Re-confirm → Save when approved

**Save (ONLY after approval)**:
```bash
cp /tmp/macro_plan.json data/plans/current_plan_macro.json
sce plan populate --from-json /tmp/weekly_plan_w1.json
sce plan save-review --from-file /tmp/training_plan_review_$(date +%Y_%m_%d).md --approved
sce plan init-log
```

**Verify**:
```bash
sce plan show
```

**Success**: Macro saved, week 1 saved, review saved, log initialized. Plan displays correctly.

**For week 2**: After completing week 1, use `weekly-analysis` skill which will generate next week's workouts.

---

## Critical Boundaries

⛔ **DO NOT generate workouts for weeks 2-16** - Progressive disclosure means planning only the immediate week. Future weeks remain as mileage targets until they arrive.

⛔ **DO NOT manually calculate** - Dates, volumes, distances, paces must ALL use CLI commands. Manual calculations introduce errors.

⛔ **DO NOT save without athlete approval** - Always present markdown review first, wait for explicit "approve" or "OK".

⛔ **DO NOT skip pre-flight validation** - Step 2 suggest-run-count check prevents creating weeks with runs below minimum durations.

⛔ **DO NOT violate guardrails** - Quality volume limits (T≤10%, I≤8%, R≤5%), long run ≤30%, weekly progression ≤10%.

---

## When Things Go Wrong

**Volume too high** (athlete wants more than CTL suggests):
- See [volume_progression.md](references/volume_progression.md) for 10% rule interpretation
- Use guardrails to explain injury risk (ACWR >1.3 = elevated risk)
- Offer modified plan within safe limits

**Multi-sport conflict** (climbing/cycling competes with key runs):
- See [multi_sport.md](references/multi_sport.md) for conflict resolution
- Check athlete's conflict policy (primary_sport_wins / running_goal_wins / ask_each_time)
- Present trade-offs, let athlete decide

**Unknown VDOT** (no recent race or workout data):
- See [pace_zones.md](references/pace_zones.md) for conservative defaults
- Use CTL-based estimate: CTL 30-40 → VDOT 45, CTL 40-50 → VDOT 48, CTL 50+ → VDOT 50
- Plan will adapt after first few weeks of data

**Validation fails** (volume discrepancy >10%, duration violations):
- See [common_pitfalls.md](references/common_pitfalls.md) for troubleshooting
- Check intent-based format syntax (workout_pattern structure)
- Verify run_days use ISO weekdays (1=Mon, 7=Sun, NOT 0-6)
- Re-run suggest-run-count with adjusted parameters

**Plan interrupted** (skill stops mid-workflow):
- Check which files exist: /tmp/macro_plan.json, /tmp/weekly_plan_w1.json, /tmp/training_plan_review_*.md
- Resume from last completed step
- Re-run context gathering if needed (sce profile get, sce status, sce dates today)

---

## Reference Documentation

**REQUIRED reading for specific steps**:
- **[json_workflow.md](references/json_workflow.md)** - Intent-based format (Step 5)
- **[choosing_run_count.md](references/choosing_run_count.md)** - Pre-flight validation (Step 2)
- **[common_pitfalls.md](references/common_pitfalls.md)** - What NOT to do (read before any plan)

**Supporting references** (for edge cases and athlete education):
- **[volume_progression.md](references/volume_progression.md)** - 10% rule interpretation, load classification
- **[periodization.md](references/periodization.md)** - Phase allocation (base/build/peak/taper)
- **[pace_zones.md](references/pace_zones.md)** - VDOT scenarios, workout prescriptions
- **[workout_generation.md](references/workout_generation.md)** - Workout prescription details
- **[guardrails.md](references/guardrails.md)** - Safety rules (quality volume, long run, progression)
- **[multi_sport.md](references/multi_sport.md)** - Multi-sport integration, conflict resolution

**Note**: These references are for depth and edge cases. The primary workflow (Steps 1-8) is complete without them.
