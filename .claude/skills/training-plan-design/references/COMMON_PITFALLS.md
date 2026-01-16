# Common Pitfalls in Training Plan Design

**Purpose**: Deep-dive explanations of why certain planning mistakes happen and how to avoid them.

---

## Category 1: Volume Errors

### Pitfall 1.1: Ignoring CTL When Setting Starting Volume

**The Problem**:
Starting all half marathon plans at 50 km/week, regardless of athlete's current fitness (CTL).

**Why It Happens**:
- "Standard" volume seems like good baseline
- Confusion between goal pace and training load
- Overestimation of athlete's readiness

**What Goes Wrong**:
- CTL 35 athlete jumps to 50 km/week → ACWR immediately >1.3 → injury risk spikes
- Athlete is overreached in Week 1, struggles for first month
- Plan becomes demoralizing instead of motivating

**Real Example**:
```
Athlete A: CTL 22 (beginner), goal = first half marathon
Bad approach: Start 50 km/week plan
Result: ACWR 2.3 Week 1, knee pain Week 3

Good approach: Start 22 km/week, build at +5-8% per week
Result: Gradual adaptation, ACWR <1.3 sustained
```

**Solution**:
- Use `sce status` to get current CTL
- Set starting volume = 80-100% of current CTL (not arbitrary number)
- Example: CTL 35 → start 28-35 km/week, build from there
- Use `sce guardrails safe-volume --ctl X` to validate starting point

---

### Pitfall 1.2: Excessive Weekly Progression

**The Problem**:
Increasing volume 10% every single week, ignoring the "10% rule" is a guideline, not a mandate.

**Why It Happens**:
- Misunderstanding 10% rule as "always safe"
- Desire to reach peak volume quickly
- Underestimating cumulative load

**What Goes Wrong**:
```
Week 1: 30 km
Week 2: 33 km (+10%)
Week 3: 36 km (+10%)
Week 4: 40 km (+10%)
Week 5: 44 km (+10%)
...by week 8 you're at 60 km without recovery week
```

Result: ACWR trajectory is linear upward, no consolidation, injuries cluster in weeks 5-8.

**Solution**:
- Use 5-7% increases most weeks, reserve 10% for selected transitions
- Recovery weeks every 4-5 weeks (70% of previous week)
- Monitor ACWR trajectory, not just weekly increases
- Example safe progression:
  ```
  Week 1-3: +7% each
  Week 4: Recovery (70%)
  Week 5-8: +6-8% each
  Week 9: Recovery
  ```

---

### Pitfall 1.3: Building Long Runs Too Fast

**The Problem**:
Increasing long run distance 5-10 km at a time, instead of gradual +10-15 min progression.

**Why It Happens**:
- Desire to reach peak distance quickly
- Confusion between long run distance and weekly volume
- Underestimating lower-body impact accumulation

**What Goes Wrong**:
```
Week 1: Long run 8 km (30 min)
Week 3: Long run 13 km (50 min) ← +5 km jump
Week 5: Long run 18 km (70 min) ← +5 km jump

Result: Cumulative lower-body load spikes, ankle/knee pain by week 6
```

**Solution**:
- Increase long run by 10-15 minutes every 2-3 weeks, not every week
- Allows neuromuscular adaptation to impact
- Example: 8km (30min) → 9km (35min) → 10km (40min) → skip long run week 4 → 11km (42min)
- Use `sce guardrails long-run-caps` to validate max duration

---

## Category 2: Intensity Errors

### Pitfall 2.1: Excessive Quality Volume

**The Problem**:
Designing weeks with 8 km T-pace + 6 km I-pace in a 40 km week (35% quality volume).

**Why It Happens**:
- Wanting to improve fitness as fast as possible
- Confusion between race pace and training emphasis
- Not understanding Daniels' quality limits (T ≤10%, I ≤8%, R ≤5%)

**What Goes Wrong**:
```
Bad: Week 5, 40 km total
  - Tuesday: 3 km E + 5 km T + 2 km E = 10 km (5 km T)
  - Thursday: 2 km E + 6 km I + 2 km E = 10 km (6 km I)
  - Result: 11 km quality in 40 km week = 27.5% quality ← WAY too much

Good: Same week
  - Tuesday: 2 km E + 3 km T + 2 km E = 7 km (3 km T)
  - Thursday: 2 km E + 3 km I + 2 km E = 7 km (3 km I)
  - Result: 6 km quality in 40 km week = 15% quality ✓
```

Result: Overreached athlete, excessive fatigue, injury risk spikes, can't maintain intensity next week.

**Solution**:
- Calculate quality volume before each week: sum all T/I/R distance
- Validate against Daniels limits:
  - T-pace: ≤10% of weekly volume
  - I-pace: ≤8% of weekly volume
  - R-pace: ≤5% of weekly volume
- Most of quality volume should be from ONE session, not spread across multiple
- Use `sce guardrails quality-volume` to validate

---

### Pitfall 2.2: Ignoring Recovery After Quality

**The Problem**:
Scheduling two hard sessions only 24 hours apart (e.g., tempo Tuesday, intervals Wednesday).

**Why It Happens**:
- Limited training days available
- Misunderstanding recovery needs
- Pressure to "fit" both sessions

**What Goes Wrong**:
```
Tuesday: Tempo 5 km T-pace (moderate fatigue, CNS demand)
Wednesday: Intervals 6 × 800m I-pace (full CNS demand next day)

Result: Athlete can't hit interval pace Wednesday, undertrained quality session
  → Wednesday intervals become mediocre, fitness gains diminish
  → Cumulative fatigue builds, athlete can't recover for Sunday long run
```

**Solution**:
- Space quality sessions 48 hours apart minimum
- Pattern: Tuesday quality → Wednesday easy → Thursday quality (optimal)
- If only 2 quality days/week available:
  - Option 1: Tuesday hard + Friday hard (Wed + Thu easy recovery)
  - Option 2: Wednesday hard + Saturday hard (different body systems?)
- If limited days: Do one longer quality session, not two rushed ones

---

### Pitfall 2.3: No Intensity Distribution Validation

**The Problem**:
Not checking 80/20 split (80% easy, 20% quality) until plan is complete.

**Why It Happens**:
- Too many quality sessions designed independently
- No systematic tracking of volume type
- Feeling like more quality = faster improvement

**What Goes Wrong**:
```
20-week plan designed, looks good week-by-week
Final calculation: Overall intensity distribution is 70% easy, 30% quality ← TOO MUCH

Result: Plan is chronically overreached, athlete burns out by week 8
```

**Solution**:
- Calculate 80/20 after full plan is designed
- Use `sce analysis intensity --plan plan.json --days 140` to validate
- If <80% easy, remove one quality session per week or add easy runs
- Rebuild plan with validated 80/20 split

---

## Category 3: Structure Errors

### Pitfall 3.1: Forgetting Recovery Weeks

**The Problem**:
Designing 12 weeks of continuous building without recovery weeks (every 4 weeks at 70%).

**Why It Happens**:
- Believing recovery week "wastes" time
- Misunderstanding periodization purpose
- Pressure to build continuously

**What Goes Wrong**:
```
Week 1-3: Build (+8% per week)
Week 4-6: Build (+8% per week)  ← No recovery week 4
Week 7-9: Build (+8% per week)  ← No recovery week 8

Result: By week 7, cumulative fatigue is massive
  CTL still rising but ATL rising faster
  TSB drops to -30 (overreached)
  ACWR >1.5 (danger zone)
  Injuries cluster: weeks 8-10
```

**Solution**:
- Design recovery week every 4-5 weeks at 70% of previous week volume
- Recovery week maintains intensity (don't remove all quality)
- Use `sce validation validate-plan --recovery-weeks [list]` to verify placement
- Example structure: 3 build weeks, 1 recovery, repeat

---

### Pitfall 3.2: Not Presenting Plan for Review

**The Problem**:
Generating JSON and populating directly without athlete seeing full plan first.

**Why It Happens**:
- Belief that coach judgment is sufficient
- Efficiency over transparency
- Assuming athlete won't want changes

**What Goes Wrong**:
```
Claude generates plan directly to system:
  sce plan populate --from-json plan.json

Week 1: Athlete sees schedule - "Wait, Saturday long run? I have kids' soccer Saturday!"
  → Plan violated constraints that were discussed but not written down
  → Athlete loses trust, wants all changes

vs.

Claude creates markdown review file:
  [Plan presented for review in /tmp/plan_review.md]
  Athlete reviews: "Saturday doesn't work, but Sunday morning perfect"
  → Changes confirmed before saving
  → Athlete approves, has invested ownership
```

Result: Plan saved without constraint verification, athlete can't follow it.

**Solution**:
- Always create markdown presentation (see plan_presentation.md template)
- Present to athlete with key highlights
- Get approval BEFORE saving to system
- Use interactive pattern: Propose → Review → Approve → Save

---

### Pitfall 3.3: Skipping Plan Validation

**The Problem**:
Not running validation checks (Daniels compliance, guardrails, structure quality) before presenting plan.

**Why It Happens**:
- Manual plan design (not using toolkit validation)
- Assuming plan "looks good"
- Time pressure

**What Goes Wrong**:
```
Plan looks good on surface:
  - Phases: Base 8 weeks, Build 6 weeks, Peak 2 weeks, Taper 1 week (17 total, not 16!)
  - Long runs: Progressive but hit 35km peak (athlete max should be 32km)
  - Recovery weeks: Placed at weeks 4, 8, 12 (but week 16 should be recovery before taper, not loaded)

Result: Plan fails structural validation
  → Athlete sees errors, loses confidence
  → Requires regeneration, delays start
```

**Solution**:
- Use `sce validation validate-plan` before presenting
  ```bash
  sce validation validate-plan \
    --total-weeks 16 \
    --goal-type half_marathon \
    --phases phases.json \
    --weekly-volumes volumes.json \
    --recovery-weeks [4,8,12] \
    --race-week 16
  ```
- Fix all validation failures before presentation
- Show athlete validation has passed

---

## Category 4: Multi-Sport Errors

### Pitfall 4.1: Not Accounting for Multi-Sport Load

**The Problem**:
Scheduling tempo run the day after hard climbing, ignoring cumulative lower-body fatigue.

**Why It Happens**:
- Focusing only on running volume
- Forgetting other sports impose systemic load
- Not using two-channel load model (systemic vs. lower-body)

**What Goes Wrong**:
```
Monday: Climbing (2 hours hard, ~340 AU lower-body load)
Tuesday: Tempo 5 km (planning: should be fine, easy day on schedule)

Result: Athlete's lower-body is fatigued from climbing
  → Can't hit tempo pace Tuesday
  → Feels like undertrained, but actually overloaded
  → Frustration: "I'm stronger than this"
```

**Solution**:
- Always check multi-sport schedule before placing quality runs
- Pattern: Hard other sport → Easy running next day minimum
- Pattern: Hard other sport → Easy running 24h + moderate running 48h
- Use `sce analysis load --activities activities.json --days 7 --priority equal` before designing
- Example schedule for equal priority:
  ```
  Monday:   Easy run (recover from weekend climbing)
  Tuesday:  Hard climbing
  Wednesday: Quality run (48h after climbing, lower-body recovered)
  Thursday: Easy run (recover)
  Friday:   Climbing or easy
  Saturday: Long run (24h after any climbing)
  ```

---

### Pitfall 4.2: Ignoring Conflict Policy

**The Problem**:
Not applying athlete's stated conflict policy (ask_each_time, primary_sport_wins, running_goal_wins).

**Why It Happens**:
- Designing plan before constraint discussion
- Assuming one conflict policy applies uniformly
- Not reading athlete's stored policy

**What Goes Wrong**:
```
Athlete profile states: conflict_policy = "ask_each_time"

Coach creates plan that has:
  - Fixed Saturday long run (always Saturday)
  - Fixed Tuesday tempo (always Tuesday)

Result: Saturday, athlete has unexpected family commitment
  → Can't long run Saturday
  → But plan assumed Saturday locked
  → No alternatives considered
```

Solution: Designed plan that asks before each potential conflict.

**Solution**:
- Read athlete's conflict_policy from profile: `sce profile get | jq '.data.conflict_policy'`
- If "ask_each_time": Design flexibility into schedule, multiple run day options
- If "primary_sport_wins": Prioritize other sport, fit running around it
- If "running_goal_wins": Lock running days first, fit other sports around
- Example if conflict_policy = "ask_each_time":
  ```
  Long run options: Saturday 8am OR Sunday 9am (athlete chooses weekly)
  Tempo options: Tuesday 6pm OR Wednesday 6am (athlete chooses weekly)
  ```

---

### Pitfall 4.3: Overestimating Capacity During Multi-Sport Periods

**The Problem**:
Designing peak running volume (85 km/week) during heavy climbing season (multiple 2-hour sessions/week).

**Why It Happens**:
- Calculating running volume only
- Forgetting systemic load accumulates across sports
- Overestimating athlete's multi-sport capacity

**What Goes Wrong**:
```
Goal: Half marathon in 10 weeks
Climbing schedule: 3 times/week (fixed commitment)
Running goal: Build to 65 km/week

Result: Total systemic load = Running 65km (450 AU) + Climbing 3×2h (900 AU)
  = 1,350 AU/week in weeks 8-10

vs.

Athlete's typical load in off-season: 400 AU/week

Result: ACWR = 1,350 / 400 = 3.4 (EXTREME DANGER)
Injuries cluster in week 8
```

**Solution**:
- Calculate total systemic load BEFORE designing running volume
- Use `sce analysis load --activities activities.json --priority equal` to get baseline
- Reduce running volume targets if other sports are heavy
- Example realistic adjustment:
  ```
  Single sport peak: 85 km/week running
  Equal multi-sport peak: 50 km/week running + 2-3 climbing sessions
  Primary other sport: 40 km/week running + hard other sport
  ```
- Use `sce guardrails multi-sport-load` to validate

---

## Category 5: Communication Errors

### Pitfall 5.1: Designing Without Discussing Constraints

**The Problem**:
Creating 6-day/week plan when athlete only mentioned 4 days available during casual conversation.

**Why It Happens**:
- Assuming "standard" 6-day plan works for everyone
- Not confirming constraints in writing
- Changing availability but coach not knowing

**What Goes Wrong**:
```
Initial conversation: "I usually run 4 times a week"
Coach thinks: "Standard recreational, I'll design 5-day plan"
Plan created with 5 required run days

Week 1: Athlete sees plan, "Wait, I can't do 5 days consistently"
  → Plan doesn't match reality
  → Requires regeneration
```

**Solution**:
- Always explicitly ask and confirm BEFORE design:
  - "How many days per week can you realistically run?" (not "would like to")
  - "What days work best?" (specific days, not flexibility)
  - "What's your max long run duration?" (hour? 90 min?)
  - "Are there other sports I need to know about?" (climbing, cycling, etc.)
  - "What time of day?" (morning preference? evening only?)
- Write constraints down, show athlete confirmation
- Design plan only after constraints confirmed

---

### Pitfall 5.2: Changing Constraints Mid-Plan

**The Problem**:
Athlete's schedule changes (starts new job with evening shift, joins climbing gym) but coach designs plan as if original constraints still apply.

**Why It Happens**:
- Constraints discussed Week 1, changed Week 5, coach not notified
- Athlete assumes coach knows (doesn't explicitly tell)
- No systematic constraint re-verification

**What Goes Wrong**:
```
Original plan: Tuesday 6:30am tempo run
Week 1-4: Works fine
Week 5: Athlete starts new job (evening shift, only available Thu evening)

Athlete assumes: Coach will adjust plan
Coach assumes: Original schedule still works
Result: Week 5 plan still has Tuesday 6:30am tempo
Athlete skips workout or runs improper time
Plan misalignment grows
```

**Solution**:
- Ask at start of each new phase: "Anything changed since we started?"
- Revisit constraints mid-plan if athlete reports changes
- If changes, regenerate plan starting from that week using `sce plan update-from`
- Example re-verification pattern:
  - Week 1: Confirm constraints
  - Week 5 (start of Build phase): "Still good with the training schedule we planned?"
  - Week 13 (start of Peak): "Any schedule changes I should know about?"

---

## Summary: Common Pitfall Categories

| Category | Common Mistakes | Prevention |
|----------|-----------------|-----------|
| **Volume** | CTL ignored, excessive progression, fast long runs | CTL-based starting point, 5-7% increases, +10-15 min long runs |
| **Intensity** | Over-quality, no recovery, no 80/20 validation | Daniels limits, 48h spacing, calculate 80/20 after design |
| **Structure** | Missing recovery weeks, no plan review, no validation | Place recovery every 4-5 weeks, markdown presentation, validate before saving |
| **Multi-Sport** | Ignoring load, ignoring conflict policy, overestimating capacity | Check multi-sport baseline, apply conflict policy, reduce peak volume |
| **Communication** | Constraints not confirmed, changes not communicated | Explicit constraint discussion, periodic re-verification |

---

## Checklist Before Presenting Any Plan

- [ ] Constraints confirmed in writing (run days, times, max duration, other sports)
- [ ] Starting volume = 80-100% of current CTL
- [ ] Weekly progression: 5-7% most weeks, 10% max
- [ ] Recovery weeks: Every 4-5 weeks at 70%
- [ ] Long run progression: +10-15 min every 2-3 weeks (not per week)
- [ ] Quality volume validated: T≤10%, I≤8%, R≤5% of weekly total
- [ ] 80/20 split calculated: ~80% easy, ~20% quality
- [ ] Quality sessions spaced 48h apart minimum
- [ ] Multi-sport load calculated (if applicable)
- [ ] Conflict policy applied (if applicable)
- [ ] Plan structure validated: phases, recovery weeks, race week taper
- [ ] Markdown presentation created and reviewed
- [ ] Athlete approval obtained before saving to system

If any checkbox is unchecked, the plan needs fixing before presentation.
