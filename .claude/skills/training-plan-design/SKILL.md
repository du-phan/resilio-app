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

**Workflow**: Gather context → Generate macro plan → Generate first month → Validate → Present for review → Save after approval.

**For ongoing monthly cycles**: Use the `monthly-transition` skill (reassess completed month, generate next month).

---

## Workflow

### Step 0: Get Current Date and Calculate Start Date

**CRITICAL**: Before any planning, establish correct dates.

```bash
# Get current date
date +%Y-%m-%d
date +%A  # Day of week

# Calculate next Monday (if not Monday today)
# Use Python one-liner:
python3 -c "from datetime import date, timedelta; today = date.today(); next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7); print(f'Next Monday: {next_monday} ({next_monday.strftime(\"%A\")})')"
```

**Validation**:
- Verify day of week is Monday (weekday() == 0)
- Confirm with athlete: "Start training on [Monday, DATE]?"
- Never assume dates - always calculate programmatically

---

### Step 1: Retrieve Relevant Memories

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

### Step 2: Gather Context

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

### Step 3: Calculate Periodization

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

### Step 4: Generate Macro Plan (Structural Roadmap)

Create the high-level 16-week structure with phase boundaries, volume trajectory, and CTL projections.

**CRITICAL: Always include recent volume** to activate the 10% rule safety check:

```bash
# Extract current CTL and recent 4-week average volume from profile
CURRENT_CTL=$(sce status | jq -r '.data.ctl.value')
RECENT_VOLUME=$(sce profile get | jq -r '.data.running_volume.recent_4wk // 0')

# Get safe volume recommendations with recent volume consideration
SAFE_VOLUMES=$(sce guardrails safe-volume \
  --ctl $CURRENT_CTL \
  --goal-type half_marathon \
  --recent-volume $RECENT_VOLUME)

# Extract starting and peak volumes
STARTING_VOLUME=$(echo "$SAFE_VOLUMES" | jq -r '.data.recommended_start_km')
PEAK_VOLUME=$(echo "$SAFE_VOLUMES" | jq -r '.data.recommended_peak_km')

# Generate macro plan
sce plan create-macro \
  --goal-type half_marathon \
  --race-date 2026-05-03 \
  --target-time 01:30:00 \
  --total-weeks 16 \
  --start-date 2026-01-20 \
  --current-ctl $CURRENT_CTL \
  --starting-volume $STARTING_VOLUME \
  --peak-volume $PEAK_VOLUME
```

**Why recent volume matters**: If CTL suggests 45 km/week but athlete has only been running 18 km/week recently, the system will cap starting volume at 18 × 1.10 = 20 km/week to prevent dangerous volume spikes. This implements the evidence-based 10% weekly increase limit from the athlete's current actual capacity.

**Macro plan returns**:
- Phase boundaries (base/build/peak/taper weeks)
- Volume trajectory (weekly targets using 10% rule)
- CTL projections at key milestones (+0.75/week in base/build)
- Recovery week schedule (every 4th week)
- Assessment checkpoints

**Multi-sport adjustments**:
- EQUAL priority: Reduce peak 20-30% (other sports provide load)
- SECONDARY: Maintain base only (no peak)

See [VOLUME_PROGRESSION.md](references/VOLUME_PROGRESSION.md) for detailed progression rules.

---

### Step 5: Calculate VDOT & Training Paces

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

### Step 6: Generate First Monthly Plan (Weeks 1-4)

Generate detailed workouts for the first 4 weeks using the macro plan targets.

**Generate monthly plan**:
```bash
# Create monthly plan for weeks 1-4 (first month)
sce plan generate-month \
  --month 1 \
  --weeks "1,2,3,4" \
  --from-macro /tmp/macro_plan.json \
  --current-vdot 48 \
  --profile data/athlete/profile.yaml \
  > /tmp/monthly_plan_m1.json

# Validate before presenting
sce plan validate-month \
  --monthly-plan /tmp/monthly_plan_m1.json \
  --macro-targets /tmp/macro_targets_weeks_1_4.json
```

**What it generates for each week**:
- Detailed workout prescriptions (easy, long, tempo, intervals)
- Target distances and durations for each workout
- Pace zones from VDOT (E/M/T/I/R paces)
- Multi-sport integration (specific days for other sports)
- Phase-specific focus and purpose

**Validation checks** (<5% volume discrepancy acceptable):
- Volume accuracy: Actual vs. target within 5%
- Minimum durations: Easy 30min/5km, long 60min/8km
- Guardrail compliance: Quality limits, long run caps
- Recovery week verification: Week 4 at 70% volume

**If validation fails** (>10% discrepancy or critical violations):
- Review errors and regenerate monthly plan
- Adjust volume distribution or workout structure
- Validate again before presenting

**For workout prescription generation** (required for monthly plans):

See [WORKOUT_GENERATION.md](references/WORKOUT_GENERATION.md) for complete guidance on:
- Generating WorkoutPrescription objects with all 20+ required fields
- Using the workout generator script
- Volume distribution helper functions
- Long run progression logic
- Minimum duration guardrails
- Validation checklists

---

### Step 7: Prescribe Workouts by Phase

**IMPORTANT**: This step describes workout design principles for monthly plan generation. The actual detailed workouts are generated by `sce plan generate-month` in Step 6.

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

### Step 8: Integrate Multi-Sport Constraints

**IMPORTANT**: Multi-sport integration is automatically handled by `sce plan generate-month` using profile constraints. This step describes the principles used.

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

### Step 9: Validate Monthly Plan Against Guardrails

**IMPORTANT**: Validation is already done in Step 6 using `sce plan validate-month`. This step describes additional guardrail checks if needed.

Check monthly plan compliance with evidence-based safety rules (see [GUARDRAILS.md](references/GUARDRAILS.md)):

```bash
# Already validated in Step 6
sce plan validate-month \
  --monthly-plan /tmp/monthly_plan_m1.json \
  --macro-targets /tmp/macro_targets_weeks_1_4.json

# Additional spot checks if needed:

# Quality volume limits (for specific weeks)
sce guardrails quality-volume --t-pace 6.0 --i-pace 4.0 --r-pace 0 --weekly-volume 50.0
# Check: T≤10%, I≤8%, R≤5% of weekly volume

# Long run caps (for specific weeks)
sce guardrails long-run --duration 120 --weekly-volume 55 --pct-limit 30
# Check: Duration ≤150 min, long run ≤30% of volume

# Weekly progression (between consecutive weeks)
sce guardrails progression --previous 44 --current 48
# Check: No week >+10% (except after recovery)
```

**Action**: If validation found critical violations (>10% discrepancy), return to Step 6 and regenerate. For warnings (<5% discrepancy), proceed to presentation.

**Volume discrepancy tolerance**:
- **<5%**: Acceptable, no action needed (training physiology tolerates minor variations)
- **5-10%**: Review, often acceptable if no other violations
- **>10%**: Regenerate required (significant error)

---

### Step 10: Present Plan for Review (CRITICAL)

**NEVER save directly**. Always present markdown for athlete approval first.

**Workflow**:
1. Create `/tmp/training_plan_review_YYYY_MM_DD.md` using template at `/templates/plan_presentation.md`
2. Include:
   - **Macro plan** (16-week structure): Phase boundaries, volume trajectory, CTL goals
   - **First month** (weeks 1-4): Detailed daily workouts, paces, multi-sport integration
   - Goal overview, constraints, training paces, guardrails check
3. **Verify week start dates** (CRITICAL):
   ```bash
   # Extract first week start date from monthly plan JSON
   start_date=$(jq -r '.weeks[0].start_date' /tmp/monthly_plan_m1.json)

   # Verify it's Monday
   python3 -c "from datetime import date; d = date.fromisoformat('$start_date'); assert d.weekday() == 0, f'Week starts on {d.strftime(\"%A\")}, not Monday'; print(f'✓ Week 1 starts Monday, {d}')"
   ```
4. Present to athlete:
   ```
   I've designed your [race] plan using progressive disclosure:

   📋 Review: /tmp/training_plan_review_YYYY_MM_DD.md

   **Macro plan** (16 weeks): [X] phases, [Start]→[Peak] km/week, respects constraints
   **First month** (weeks 1-4): Detailed daily workouts with paces
   **Next months**: Generated every 4 weeks based on your actual response

   Approve, request changes, or ask questions?
   ```
5. Handle response: Approve → save, Modify → clarify + regenerate, Questions → answer + re-confirm

---

### Step 11: Save Plan to System (After Approval)

**Critical**: Only save after athlete explicitly approves the plan.

After athlete approval, save both macro and monthly plans.

**Save macro plan**:
```bash
# Save the macro plan structure (already generated in Step 4)
# This contains 16-week phase boundaries, volume trajectory, CTL projections
cp /tmp/macro_plan.json data/plans/current_plan_macro.json
```

**Save first month plan**:
```bash
# Option A: Use populate command with first month JSON
sce plan populate --from-json /tmp/monthly_plan_m1.json

# Option B: Python script (if needed for conversion)
python scripts/generate_plan.py \
  --from-monthly /tmp/monthly_plan_m1.json \
  --output /tmp/plan_weeks_1_4.json

sce plan populate --from-json /tmp/plan_weeks_1_4.json
```

**Save documentation**:
```bash
# 1. Save review markdown
sce plan save-review --from-file /tmp/training_plan_review_2026_01_20.md --approved

# 2. Initialize training log
sce plan init-log

# 3. Verify all saved correctly
sce plan show  # Verify plan structure (first month saved)
sce plan week --next  # Quick check next week (more efficient)
sce plan show-review  # Verify review markdown
sce plan show-log  # Verify log initialized
```

**What happens**:
- Macro plan saved to `data/plans/current_plan_macro.json`
- First month workouts saved to `data/plans/current_plan.yaml`
- Workouts saved to `data/plans/workouts/week_XX/` (weeks 1-4 only)
- Review saved to `data/plans/current_plan_review.md`
- Training log initialized at `data/plans/current_training_log.md`

**If athlete wants modifications**:
- Do NOT save yet
- Make requested changes
- Present updated plan for re-approval
- Save only after final approval

**For future monthly cycles**:
After completing weeks 1-4, use the `monthly-transition` skill to:
1. Assess month 1 completion (`sce plan assess-month`)
2. Recalibrate VDOT if needed
3. Generate month 2 (weeks 5-8) with updated context
4. Repeat every 4 weeks

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
