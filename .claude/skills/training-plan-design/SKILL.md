---
name: training-plan-design
description: Design macro training plans (volume trajectory, phases, recovery weeks) for 5K-Marathon races. Creates 16-week structure using Pfitzinger periodization and CTL-based volume progression. Does NOT generate detailed workouts - use weekly-planning skill for that. Use when athlete requests "design my plan", "create training program", "how should I train for [race]", or after first-session onboarding.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Training Plan Design (Macro Planning)

## Overview

Creates strategic 16-week training plan with volume trajectory, phase boundaries, and recovery weeks. Does NOT generate detailed workouts - those are designed week-by-week using the weekly-planning skill.

**Output**: Macro plan skeleton with:
- Phase allocation (Base → Build → Peak → Taper)
- Weekly volume targets (starting volume → peak volume)
- Baseline VDOT (intensity baseline for 16 weeks)
- Recovery week timing (every 4-5 weeks at 70%)
- Date boundaries (Monday-Sunday for all weeks)

**Methodology**: Pfitzinger periodization, CTL-based volume progression, multi-sport load awareness, AI-driven volume trajectory with guardrails validation.

## Workflow

```
MACRO PLANNING WORKFLOW (6 STEPS)

Step 1: Context Gathering
        → sce dates, sce profile get, sce status, sce memory list
        ⛔ BLOCKER: Must have goal, CTL, constraints

Step 2: Determine Volume Trajectory
        → sce guardrails safe-volume (CTL-based starting point)
        → AI decides: starting volume, peak volume, progression strategy

Step 2.5: Determine Baseline VDOT
        → Check recent races OR estimate from fitness OR use conservative default
        → sce vdot paces --vdot X (get pace ranges for macro presentation)
        → Baseline VDOT = intensity baseline for entire 16-week plan

Step 3: Create Macro Skeleton
        → sce plan create-macro (16-week structure, volume targets + baseline VDOT)
        → Auto-persists to data/plans/current_plan.yaml
        ⛔ BLOCKER: Must verify skeleton with sce plan show

Step 4: Present Macro Plan
        → Create /tmp/macro_plan_review_YYYY_MM_DD.md
        → Show: Phase breakdown, volume progression, recovery weeks, pace context
        → Include: "Based on VDOT X, easy pace ~Y:YY/km"
        → Explicitly: "Workouts will be designed week-by-week starting with Week 1"

Step 5: Save & Transition
        → Athlete approves macro structure (volume + intensity)
        → Ask: "Ready to design Week 1 workouts?" → Activate weekly-planning skill
        ⛔ BLOCKER: NEVER proceed without approval
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

**Extract**:
- START_DATE (next Monday from `sce dates next-monday`)
- GOAL_TYPE, RACE_DATE, TARGET_TIME (from profile)
- MAX_RUN_DAYS, CONFLICT_POLICY, MULTI_SPORT_CONSTRAINTS (from profile)
- CTL, TSB, ACWR (from status)
- INJURY_HISTORY (from memory)

**Exit criteria:**
- [ ] START_DATE verified Monday (use `sce dates validate`)
- [ ] GOAL_TYPE, RACE_DATE extracted
- [ ] CTL known
- [ ] Multi-sport constraints identified (if applicable)

---

### Step 2: Determine Volume Trajectory

**See [volume_progression_macro.md](references/volume_progression_macro.md) for CTL-based starting volumes.**
**See [guardrails_macro.md](references/guardrails_macro.md) for recovery week timing.**

Run this command:
```bash
poetry run sce guardrails safe-volume --ctl $CTL --goal-type $GOAL --recent-volume $VOL
```

**AI decides**:
- **Starting volume**: 80-100% of CTL (not arbitrary)
  - Example: CTL 35 → Start 32-35 km/week
- **Peak volume**: Race-specific and CTL-appropriate
  - Half marathon, CTL 35 → Peak 55-60 km
- **Progression strategy**: Conservative (5-7%/week) or standard (7-10%/week)
  - Factors: Injury history, masters age, multi-sport load

**Exit criteria:**
- [ ] STARTING_VOLUME calculated (CTL-based)
- [ ] PEAK_VOLUME determined (goal-specific)
- [ ] Progression strategy chosen (conservative vs standard)

---

### Step 2.5: Determine Baseline VDOT

**See [pace_zones.md](../weekly-planning/references/pace_zones.md) for VDOT scenarios.**

**Purpose**: Establish intensity baseline for the entire 16-week plan. Athletes need complete picture (volume + paces) for informed consent.

**Three approaches** (in order of preference):

#### 1. Recent Race Result (Most Accurate)
```bash
# Check for recent races
poetry run sce race list

# If race within last 30 days, calculate VDOT
poetry run sce vdot calculate --race-type [TYPE] --time [TIME]
```

**Use if**: Race result within 30 days, confident in result accuracy.

#### 2. Estimate from Current Fitness
```bash
# Estimate based on recent training performance
poetry run sce vdot estimate-current --lookback-days 28
```

**Use if**: No recent race, but consistent quality workouts last 4 weeks.

#### 3. Conservative Default (Safest)
**Use CTL-based estimation**:
- CTL 25-30 → VDOT 40-42 (beginner/recreational)
- CTL 30-40 → VDOT 42-47 (recreational/competitive)
- CTL 40-50 → VDOT 47-52 (competitive/advanced)
- CTL 50+ → VDOT 52+ (advanced/elite)

**Use if**: No race, inconsistent training, or uncertainty. Better to start conservative.

**Get pace ranges for presentation**:
```bash
poetry run sce vdot paces --vdot $BASELINE_VDOT
```

**Store for create-macro**: `BASELINE_VDOT` (e.g., 45)

**Why this belongs in macro planning**:
- VDOT is **strategic** (intensity baseline for 16 weeks), not tactical (daily adjustments)
- Athletes need **complete informed consent** (volume + paces) before approving macro
- Volume without intensity context = incomplete framework
- Example: "50km/week at 6:30 easy" vs "50km/week at 7:00 easy" are VERY different plans
- Prevents "surprise paces" problem when Week 1 generated

**Exit criteria:**
- [ ] BASELINE_VDOT determined (race, estimate, or conservative default)
- [ ] Pace ranges retrieved (`sce vdot paces`)
- [ ] Confidence level noted (high for race, medium for estimate, low for default)

---

### Step 3: Create Macro Skeleton

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
    --peak-volume-km $PEAK_VOLUME \
    --baseline-vdot $BASELINE_VDOT
```

**Creates**: MasterPlan skeleton with:
- 16 weeks with phase assignments (Base/Build/Peak/Taper)
- `target_volume_km` for each week
- Recovery weeks marked (`is_recovery_week: true`)
- Date boundaries (all Monday-Sunday)
- Empty `workouts: []` arrays (filled progressively by weekly-planning skill)

**Auto-persists** to `data/plans/current_plan.yaml`.

**Exit criteria:**
- [ ] create-macro completed (exit code 0)
- [ ] data/plans/current_plan.yaml exists
- [ ] `sce plan show` displays skeleton with phases
- [ ] Volume trajectory looks smooth (no sudden jumps)
- [ ] Recovery weeks present (weeks 4, 8, 12 typically)

---

### Step 4: Present Macro Plan

Create `/tmp/macro_plan_review_$(date +%Y_%m_%d).md` with:

**Macro overview**:
- Start date (Monday), end date (Sunday race week)
- Starting volume → Peak volume
- Phase breakdown (Base weeks X-Y, Build weeks Z-W, etc.)
- Recovery week schedule (weeks 4, 8, 12 at 70%)
- **Baseline VDOT and pace context** (NEW - complete informed consent)

**Intensity baseline** (provide complete picture):
```markdown
## Training Paces (Baseline VDOT: [X])

Based on your current fitness (VDOT [X]), your training paces will be:
- **Easy runs**: [Y:YY]-[Y:YY]/km (comfortable, conversational)
- **Tempo runs**: [Z:ZZ]-[Z:ZZ]/km (comfortably hard, 10K-half marathon effort)
- **Long runs**: [Y:YY]-[Y:YY]/km (same as easy pace)

*Note: Paces may be refined weekly based on your training response and fitness gains.*
```

**Volume progression table**:
```markdown
| Week | Phase | Volume | Recovery | Notes |
|------|-------|--------|----------|-------|
| 1    | Base  | 32 km  |          | Establishing routine |
| 2    | Base  | 35 km  |          | +9% |
| ...
| 12   | Build | 41 km  | ✓        | Recovery week (70%) |
| 15   | Taper | 35 km  |          | -20% |
| 16   | Taper | 21 km  |          | Race week |
```

**Important notes**:
- Explicitly state: "Workouts will be designed week-by-week starting with Week 1"
- Explain: "This allows adaptation based on your actual training response"
- If multi-sport: Note load distribution targets (e.g., "Running 45%, Climbing 45%, Recovery 10%")
- **Pace context**: Athlete sees BOTH volume trajectory AND intensity before committing

---

### Step 5: Save & Transition

**⛔ NEVER proceed without approval. ALWAYS present macro plan first.**

Present to athlete:
```
I've created your [Race Type] macro training plan.

📋 Review: /tmp/macro_plan_review_YYYY_MM_DD.md

**Plan Structure** (16 weeks):
- Start: [Date] (Monday), [X] km/week
- Peak: [X] km/week in week [N]
- Phases: Base (1-7), Build (8-12), Peak (13-14), Taper (15-16)
- Recovery weeks: 4, 8, 12 (70% volume)

**Training Paces** (Baseline VDOT: [X]):
- Easy pace: [Y:YY]-[Y:YY]/km
- Tempo pace: [Z:ZZ]-[Z:ZZ]/km
- Long run pace: [Y:YY]-[Y:YY]/km

**Volume Trajectory**:
- Weeks 1-7 (Base): [X] km → [Y] km
- Weeks 8-12 (Build): [Y] km → [Z] km
- Weeks 13-14 (Peak): [Z] km (hold)
- Weeks 15-16 (Taper): [A] km → [B] km

**Next Step**: Design Week 1 workouts (specific days, paces, distances).

Questions or changes to the macro structure?
```

**After approval**:
1. Macro plan is already saved (create-macro auto-persists)
2. Activate weekly-planning skill to design Week 1 workouts

```
Macro plan saved! Your 16-week structure is ready.

Ready to design Week 1 workouts? I'll use the weekly-planning skill to create your first week with specific workout details (days, paces, distances).
```

**Exit criteria:**
- [ ] Athlete explicitly approved macro structure
- [ ] Macro plan exists in data/plans/current_plan.yaml
- [ ] `sce plan show` displays 16-week skeleton
- [ ] weekly-planning skill activated for Week 1 design

---

## Critical Boundaries

### ⛔ Do Not Do (Macro Planning)

- **Generate workouts for ANY week** (including Week 1) - That's weekly-planning's job
- **Skip recovery weeks** - Every 4-5 weeks at 70% volume
- **Ignore CTL when setting starting volume** - Always use CTL-based starting point
- **Use mental date calculations** - Always use `sce dates` commands
- **Save without approval** - Present macro plan markdown first
- **Design without confirming constraints** - Ask about run days, multi-sport schedule, time availability

### ✅ Do This (Macro Planning)

- Use CLI for all computations (dates, volumes, validation)
- Start volume = 80-100% of CTL (use `sce guardrails safe-volume`)
- Plan recovery weeks (every 4-5 weeks at 70%)
- Validate dates are Monday-Sunday (use `sce dates validate`)
- Present macro plan for approval before proceeding to Week 1
- Account for multi-sport load in volume planning (see multi_sport_macro.md)

---

## When Things Go Wrong

**See [common_pitfalls_macro.md](references/common_pitfalls_macro.md) for troubleshooting.**

Common problems:
- **Athlete wants higher volume than CTL suggests**: Explain ACWR injury risk with data, offer conservative ramp (reach desired volume by week 3-4)
- **Insufficient weeks to goal**: Recommend extending goal date or compressed plan with adjusted expectations
- **Multi-sport conflicts**: Adjust peak running volume based on priority (EQUAL: reduce 20-30%)
- **Workflow interrupted**: Check `/tmp/macro_plan_review_*.md`, `sce plan show` to determine last completed step

---

## Reference Documentation

**Core references**:
- **[volume_progression_macro.md](references/volume_progression_macro.md)** - CTL-based starting volumes, phase progression rates
- **[periodization.md](references/periodization.md)** - Phase allocation logic (Base/Build/Peak/Taper)
- **[guardrails_macro.md](references/guardrails_macro.md)** - Recovery week timing, phase allocation guardrails
- **[common_pitfalls_macro.md](references/common_pitfalls_macro.md)** - What NOT to do (macro level)

**Supporting references**:
- **[multi_sport_macro.md](references/multi_sport_macro.md)** - Volume adjustments for multi-sport athletes

---

## Architecture

**Macro planning scope**:
- Creates 16-week structure with volume targets + baseline VDOT
- Baseline VDOT = strategic intensity baseline (not daily pace adjustments)
- Does NOT generate workout_pattern or detailed workouts
- Auto-persists to `data/plans/current_plan.yaml`
- Workouts remain empty (`workouts: []`) until generated by weekly-planning skill

**VDOT Architecture**:
- **Macro plan stores**: `baseline_vdot` (strategic, fixed for plan duration)
- **Weekly planning updates**: `current_vdot` (tactical, refined based on fitness gains)
- Athlete approves macro with complete picture (volume + intensity)

**Philosophy**: Macro planning = strategic direction (volume + intensity baseline). Weekly planning = tactical execution (detailed workouts + pace refinement). Separate skills, clear boundaries.
