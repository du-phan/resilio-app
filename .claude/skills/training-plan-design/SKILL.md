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
MACRO PLANNING WORKFLOW (6 STEPS - COMPLETE ALL BEFORE RETURNING)

Step 1: Context Gathering
        → sce dates, sce profile get, sce status, sce memory list
        ⛔ BLOCKER: Must have goal, CTL, constraints

Step 2: Determine Volume Trajectory
        → sce guardrails safe-volume (CTL-based starting point)
        → AI decides: starting volume, peak volume, progression strategy

Step 3: Determine & Validate Baseline VDOT (MUST GET ATHLETE APPROVAL)
        → Check recent races OR estimate from fitness OR use conservative default
        → sce vdot paces --vdot X (get pace ranges)
        → Present paces to athlete and ask for validation:
          - "Do these paces match your current fitness?"
          - "Is easy pace X:XX-X:XX comfortable for you?"
          - Show recent workout paces as reference
        → Use AskUserQuestion or return to main agent for validation
        ⛔ BLOCKER: MUST validate VDOT with athlete before Step 4
        → Adjust VDOT if athlete feedback indicates mismatch

Step 4: Create Macro Skeleton
        → sce plan create-macro (structure, volume targets + VALIDATED baseline VDOT)
        → Auto-persists to data/plans/current_plan.yaml
        ⛔ BLOCKER: Must verify skeleton with sce plan show

Step 5: Create Macro Plan Review Document (MANDATORY - DO NOT SKIP)
        → MUST create /tmp/macro_plan_review_YYYY_MM_DD.md
        → MUST include: Phase breakdown, volume table, VALIDATED pace zones, approval prompt
        → Use Write tool to create the markdown file
        ⛔ BLOCKER: This step is REQUIRED before returning to main agent

Step 6: Return Summary to Main Agent
        → Provide: Path to review markdown, plan summary, next steps
        → Do NOT suggest generating Week 1 workouts
        → Main agent will present to athlete and await final macro plan approval
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

### Step 3: Determine & Validate Baseline VDOT

**See [pace_zones.md](../weekly-planning/references/pace_zones.md) for VDOT scenarios.**

**Purpose**: Establish AND VALIDATE intensity baseline with athlete BEFORE creating macro plan. Athletes must approve paces before committing to a training structure.

**Phase A: Calculate Initial VDOT Estimate**

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

# Also check recent workout paces for reference
poetry run sce activity list --since 30d --sport run
```

**Use if**: No recent race, but consistent quality workouts last 4 weeks.

#### 3. Conservative Default (Safest)
**Use CTL-based estimation**:
- CTL 25-30 → VDOT 40-42 (beginner/recreational)
- CTL 30-40 → VDOT 42-47 (recreational/competitive)
- CTL 40-50 → VDOT 47-52 (competitive/advanced)
- CTL 50+ → VDOT 52+ (advanced/elite)

**Use if**: No race, inconsistent training, or uncertainty. Better to start conservative.

**Phase B: Get Pace Ranges**
```bash
poetry run sce vdot paces --vdot $INITIAL_VDOT
```

**Phase C: VALIDATE WITH ATHLETE (MANDATORY)**

**Present paces to athlete and ask for validation:**

```
I've calculated your baseline VDOT as [X] based on [source].

Your training paces would be:
- Easy runs: X:XX-X:XX/km (comfortable, conversational)
- Marathon pace: X:XX-X:XX/km (race pace)
- Tempo runs: X:XX-X:XX/km (comfortably hard, 10K-half marathon effort)
- Long runs: X:XX-X:XX/km (same as easy pace)

Looking at your recent workouts:
- [Date]: [Pace]/km ([workout type])
- [Date]: [Pace]/km ([workout type])

Do these paces match your current fitness?
- If easy pace feels too fast/slow, we should adjust your VDOT
- Your recent easy runs were around X:XX/km - does that align?
```

**Use AskUserQuestion or return to main agent for validation.**

**If athlete says paces are incorrect:**
1. Ask what their actual easy/tempo paces feel like
2. Recalculate VDOT based on their reported paces
3. Re-validate until athlete confirms

**Phase D: Store Validated VDOT**

**Store for create-macro**: `BASELINE_VDOT` (e.g., 45) - **MUST be athlete-validated**

**Why validation is critical**:
- VDOT is **strategic** (intensity baseline for entire plan duration), not tactical
- Wrong VDOT = wrong training stimulus for 10-16 weeks
- Example: "50km/week at 6:30 easy" vs "50km/week at 7:00 easy" are VERY different plans
- Athlete must approve intensity baseline BEFORE volume structure is created
- Prevents "surprise paces" problem and ensures informed consent

**Exit criteria:**
- [ ] BASELINE_VDOT calculated (race, estimate, or conservative default)
- [ ] Pace ranges retrieved (`sce vdot paces`)
- [ ] **Paces VALIDATED with athlete (confirmed they match actual fitness)**
- [ ] VDOT adjusted if athlete indicated mismatch
- [ ] Confidence level noted (high for race, medium for estimate, low for default)

---

### Step 4: Create Macro Skeleton

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

### Step 5: Create Macro Plan Review Document

**MANDATORY - DO NOT SKIP THIS STEP**

Create `/tmp/macro_plan_review_$(date +%Y_%m_%d).md` using the Write tool with:

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

**Exit criteria:**
- [ ] Markdown file created at `/tmp/macro_plan_review_YYYY_MM_DD.md`
- [ ] File includes all sections (overview, paces, volume table, approval prompt)
- [ ] Validated VDOT and paces are shown
- [ ] Multi-sport context included if applicable

---

### Step 6: Return Summary to Main Agent

**⛔ NEVER proceed without approval. Skill returns summary to main agent, who presents to athlete.**

Return to main agent:
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

- **Skip VDOT validation with athlete** - MUST validate paces BEFORE creating macro skeleton
- **Generate workouts for ANY week** (including Week 1) - That's weekly-planning's job
- **Skip Step 5 (create markdown review)** - This is MANDATORY before returning to main agent
- **Skip recovery weeks** - Every 4-5 weeks at 70% volume
- **Ignore CTL when setting starting volume** - Always use CTL-based starting point
- **Use mental date calculations** - Always use `sce dates` commands
- **Present without approval** - Main agent handles athlete presentation

### ✅ Do This (Macro Planning)

- **Step 3: Validate VDOT with athlete** - Present paces, compare to recent workouts, confirm accuracy
- **Step 5: Create markdown review file** - Use Write tool, include all required sections
- Use CLI for all computations (dates, volumes, validation)
- Start volume = 80-100% of CTL (use `sce guardrails safe-volume`)
- Plan recovery weeks (every 4-5 weeks at 70%)
- Validate dates are Monday-Sunday (use `sce dates validate`)
- Return path to markdown file (not raw analysis) to main agent
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
