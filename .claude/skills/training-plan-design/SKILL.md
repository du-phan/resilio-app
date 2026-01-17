---
name: training-plan-design
description: Design personalized training plans for 5K-Marathon races using Pfitzinger periodization, Daniels pace zones, and 80/20 principles. Accounts for multi-sport constraints, CTL-based volume progression, and injury history. Use when athlete requests "design my plan", "create training program", "how should I train for [race]", or after first-session onboarding.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Training Plan Design

## Overview

This skill designs evidence-based training plans using:
- Pfitzinger periodization (base → build → peak → taper)
- Daniels VDOT pace system (E/M/T/I/R zones)
- 80/20 intensity distribution
- CTL-based volume progression
- Multi-sport integration
- Guardrails validation (injury prevention)

**Workflow**: Gather context → Calculate periodization → Design workouts → Validate → Present for review → Save after approval.

---

## Workflow

### Step 0: Retrieve Relevant Memories

**Before designing plan, load athlete's history to inform volume/intensity decisions.**

```bash
# Retrieve injury history
sce memory list --type INJURY_HISTORY

# Retrieve training response patterns
sce memory list --type TRAINING_RESPONSE

# Retrieve preferences
sce memory list --type PREFERENCE

# Search for specific concerns
sce memory search --query "volume injury recovery"
```

**Apply retrieved memories**:
- Cap weekly volume based on past injury triggers (e.g., "knee pain after 18km+")
- Adjust recovery based on observed patterns (e.g., "needs 3 easy days after hard climbing")
- Respect schedule constraints (e.g., "Tuesday work travel monthly")
- Reference preferences (e.g., "prefers frequency over volume")

---

### Step 1: Gather Context

Get athlete's current state and confirm training constraints.

**Commands**:
```bash
sce profile get     # Profile: goal, constraints, injury history
sce status          # Metrics: CTL/ATL/TSB/ACWR
```

**Extract key data**:
- Current CTL (determines safe starting volume)
- Goal: race type, date, time goal
- Constraints: run days/week, long run max, other sports
- Running priority: PRIMARY/EQUAL/SECONDARY
- Conflict policy: ask_each_time/primary_sport_wins/running_goal_wins

**Minimum weeks by distance**: 5K (6), 10K (8), half (12), marathon (16)

**Verify constraints** via natural conversation:
- How many days per week realistically?
- Long run max duration?
- Are other sports fixed or flexible?
- Long run day preference?

See [COMMON_PITFALLS.md](references/COMMON_PITFALLS.md#category-5-communication-errors) to avoid constraint errors.

---

### Step 2: Calculate Periodization

Divide weeks into phases (base, build, peak, taper) using race distance and weeks available.

**Standard allocation** (see [PERIODIZATION.md](references/PERIODIZATION.md)):
- Base: 45-50% (aerobic foundation)
- Build: 30-35% (race-specific intensity)
- Peak: 10-15% (maximum load)
- Taper: 8-12% (recover, peak fitness)

**Recovery weeks**: Every 4th week during base/build at 70% volume (not during peak/taper).

**Distance adjustments**:
- Marathon: Extend base +1-2w, longer taper (3w)
- 10K: Shorter base, no separate peak

---

### Step 3: Design Volume Progression

Use CTL to determine safe starting and peak volumes.

**Get recommendations**:
```bash
sce guardrails safe-volume --ctl 44 --goal-type half_marathon
```

Returns: starting volume, peak volume, weekly progression strategy

**Phase progression** (see [VOLUME_PROGRESSION.md](references/VOLUME_PROGRESSION.md)):
- Base: +5-10% per week (recovery every 4th)
- Build: +0-5% per week (slower due to intensity)
- Peak: Hold (no increase)
- Taper: -20-30% per week

**Multi-sport adjustments**:
- EQUAL priority: Reduce peak 20-30% (other sports provide load)
- SECONDARY: Maintain base only (no peak)

---

### Step 4: Calculate VDOT & Training Paces

**Get VDOT** from recent race or estimate:
```bash
sce vdot calculate --race-type 10k --time 42:30  # From race result
sce vdot six-second --mile-time 7:00              # From mile test
# Or: Conservative estimate VDOT 45-50, adjust after first tempo
```

**Get training paces**:
```bash
sce vdot paces --vdot 48
# Returns: E-pace, M-pace, T-pace, I-pace, R-pace
```

See [PACE_ZONES.md](references/PACE_ZONES.md) for workout type guidance.

---

### Step 5: Prescribe Workouts by Phase

Design weekly structure based on phase focus.

**Base phase**: 80-90% easy, 10-20% moderate (long runs + optional late-base tempo)
**Build phase**: 70-75% easy, 25-30% quality (tempo runs + M-pace long runs + intervals)
**Peak phase**: 65-70% easy, 30-35% quality (maximum load + race-pace focus)
**Taper phase**: Maintain pace zones, reduce volume 30-50% (maintain sharpness, build freshness)

See [PACE_ZONES.md](references/PACE_ZONES.md) for workout type prescriptions by distance.

**Long run progression**: +10-15 min every 2-3 weeks (not per week), cap at 30% of weekly volume

**Quality session spacing**: 48 hours apart minimum

**Completed examples**: See `examples/` directory (10K, half marathon, marathon plans)

---

### Step 6: Integrate Multi-Sport Constraints

Map running workouts around other sports.

**Principle** (see [MULTI_SPORT.md](references/MULTI_SPORT.md)):
- Easy runs 24 hours after other sports (systemic recovery)
- Quality runs 48 hours after hard sessions (full recovery)
- Long runs positioned for good recovery window

**Example schedule** (EQUAL priority, climbing + running):
```
Mon: Rest
Tue: Climbing
Wed: Easy run (24h after climbing)
Thu: Climbing
Fri: Rest
Sat: Climbing
Sun: Long run (24h after climbing)
Mon: Tempo run (48h after Sat climbing)
```

**Verify load balance**:
```bash
sce analysis load --activities activities.json --days 7 --priority equal
# Check: Running ~40-50%, other sports ~40-50%
```

---

### Step 7: Validate Against Guardrails

Check plan compliance with evidence-based safety rules.

**Validation commands** (see [GUARDRAILS.md](references/GUARDRAILS.md)):
```bash
# Quality volume limits
sce guardrails quality-volume --t-pace 6.0 --i-pace 4.0 --r-pace 0 --weekly-volume 50.0
# Check: T≤10%, I≤8%, R≤5% of weekly volume

# Long run caps
sce guardrails long-run --duration 120 --weekly-volume 55 --pct-limit 30
# Check: Duration ≤150 min, long run ≤30% of volume

# Weekly progression
sce guardrails progression --previous 44 --current 48
# Check: No week >+10% (except after recovery)

# Overall plan structure
sce validation validate-plan --total-weeks 16 --goal-type half_marathon \
  --phases phases.json --weekly-volumes volumes.json --recovery-weeks recovery.json --race-week 16
# Returns: quality score, violations, recommendations
```

**Action**: Fix all violations before presenting plan to athlete

---

### Step 8: Present Plan for Review (CRITICAL)

**NEVER save directly**. Always present markdown for athlete approval first.

**Workflow**:
1. Create `/tmp/training_plan_review_YYYY_MM_DD.md` using template at `/templates/plan_presentation.md`
2. Include: Goal overview, plan structure, constraints, weekly breakdown, training paces, guardrails check
3. Present to athlete:
   ```
   I've designed your [race] plan ([weeks] weeks).

   📋 Review: /tmp/training_plan_review_YYYY_MM_DD.md
   Key highlights: [X]w phases, [Start]→[Peak] km/week, respects your constraints

   Approve, request changes, or ask questions?
   ```
4. Handle response: Approve → save, Modify → clarify + regenerate, Questions → answer + re-confirm

---

### Step 9: Save Plan to System

After athlete approval, convert plan to JSON and populate.

**Generate plan JSON**:
```bash
# Option A: Python script (recommended for complex plans)
python scripts/generate_plan.py --goal-type half_marathon --weeks 16 --output /tmp/plan.json

# Option B: Manual JSON creation (see examples/ for full structure)
# Create /tmp/plan.json with week/workout objects
```

**Save plan**:
```bash
sce plan populate --from-json /tmp/plan.json
sce plan show  # Verify saved correctly
```

**JSON structure** (see `examples/` for complete examples):
- `weeks`: Array of week objects
- Each week: `week_number`, `phase`, `start_date`, `target_volume_km`, `is_recovery_week`, `workouts`
- Each workout: `id`, `day_of_week`, `workout_type`, `distance_km`, `target_pace_per_km`, `purpose`

---

## Decision Trees

### Q: Athlete wants higher volume than CTL suggests

**Challenge**: Starting above CTL → immediate ACWR spike → injury risk

**Options**:
1. Start at 80-100% of CTL, reach desired volume by week 3-4 (safer)
2. Start higher but extend base phase +2 weeks (more adaptation time)

**Recommendation**: Option 1 - gradual buildup reduces injury risk without delaying fitness

### Q: Insufficient weeks to goal

**Scenario**: Half marathon in 8 weeks (minimum 12 weeks recommended)

**Options**:
1. Extend goal date (+4 weeks) → proper periodization, lower risk
2. Compressed plan (8 weeks) → skip/shorten base, higher risk
3. Adjust expectations (participation vs. time goal)

**Recommendation**: Extend goal date if possible

### Q: Multi-sport conflict during key workout

**If conflict_policy = ask_each_time**, present options:
- Prioritize running key workout (long runs are most important)
- Shift run 24 hours (easy runs ok with delay)
- Shift other sport (less frequent than running)

**Store preference** for similar conflicts

### Q: Athlete has injury history

**Example**: "Left knee sensitive after 18km+"

**Adjustments**:
- Cap long run at 16 km (below sensitivity threshold)
- Increase frequency (5 runs instead of 4, spread volume)
- More cross-training (cycling/swimming for volume)
- Monitor closely, adjust if signals appear

### Q: No recent race time (unknown VDOT)

**Options**:
1. Mile test at max effort: `sce vdot six-second --mile-time 7:00`
2. Estimate from "comfortably hard" 20-30 min pace
3. Conservative default (VDOT 45), adjust after first tempo

**Recalculate** VDOT after first quality session

---

## Common Pitfalls

Before designing any plan, review **[COMMON_PITFALLS.md](references/COMMON_PITFALLS.md)** for detailed explanations of:

- **Volume errors**: Ignoring CTL, excessive progression, fast long runs
- **Intensity errors**: Over-quality, insufficient recovery, no 80/20 validation
- **Structure errors**: Missing recovery weeks, no plan review, no validation
- **Multi-sport errors**: Ignoring load, ignoring conflict policy, overestimating capacity
- **Communication errors**: Constraints not confirmed, changes not communicated

Use the checklist before presenting any plan.

---

## Plan Update Strategies

After initial plan creation, athletes may need adjustments.

### Mid-Week Adjustment
**Use**: `sce plan update-week --week N --from-json week.json`
**Scenario**: Athlete got sick week 5, need to downgrade week 5 workouts
**JSON**: Single week object (not array)

### Partial Replan
**Use**: `sce plan update-from --week N --from-json weeks.json`
**Scenario**: After week 4, replan weeks 5-16 due to injury setback
**JSON**: Weeks array starting from week N
**Preserves**: Weeks 1 to N-1

### Full Regeneration
**Use**: `sce plan regen` or `sce plan populate --from-json`
**Scenario**: Goal changed (10K → half marathon), complete redesign needed

---

## Links to References

**Training methodology** (1-page summaries, load on-demand):
- [PERIODIZATION.md](references/PERIODIZATION.md) - Phase allocation, recovery weeks
- [PACE_ZONES.md](references/PACE_ZONES.md) - VDOT system, E/M/T/I/R zones
- [VOLUME_PROGRESSION.md](references/VOLUME_PROGRESSION.md) - 10% rule, CTL-based starting volumes
- [GUARDRAILS.md](references/GUARDRAILS.md) - 80/20, quality limits, long run caps
- [MULTI_SPORT.md](references/MULTI_SPORT.md) - Two-channel load model, conflict resolution

**Training books** (comprehensive methodology, deep dives):
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md)
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md)
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md)
- [Faster Road Racing](../../../docs/training_books/faster_road_racing_pete_pfitzinger.md)
- [Run Less, Run Faster](../../../docs/training_books/run_less_run_faster_bill_pierce.md)

**Example plans** (see `examples/` directory):
- [10K plan: 8 weeks](examples/10k_plan_8weeks.md)
- [Half marathon plan: 16 weeks with multi-sport](examples/half_marathon_16weeks.md)
- [Marathon plan: 20 weeks, masters athlete](examples/marathon_20weeks.md)

**Scripts**:
- [generate_plan.py](scripts/generate_plan.py) - Automated plan generation from profile + goal

**Template**:
- [plan_presentation.md](templates/plan_presentation.md) - Markdown template for athlete review
