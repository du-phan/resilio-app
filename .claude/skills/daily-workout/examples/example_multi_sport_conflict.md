# Example: Multi-Sport Conflict (Climbing Comp vs Long Run)

## Scenario

**Athlete**: Casey, multi-sport athlete (running EQUAL priority with climbing)
**Day**: Saturday (week 4 of 16-week half marathon plan)
**Scheduled workout**: Long run - 18 km at 6:10-6:30/km (easy pace)
**Context**: Local climbing competition Saturday morning (registered 2 months ago), conflict policy = `ask_each_time`

---

## Complete Coaching Interaction

### Step 1: Athlete Initiates Conflict

**Athlete**: "Hey, I have a climbing comp tomorrow (Saturday) morning, but my 18 km long run is also scheduled. What should I do?"

### Step 2: Coach Checks Profile and Context

**Coach runs**:
```bash
sce profile get | grep -E "run_priority|conflict_policy"
# Returns:
# - run_priority: "equal"
# - conflict_policy: "ask_each_time"

sce memory search --query "climbing competition"
# Returns: "Climbing comps are important social events, not just performance"
```

**Coach runs**:
```bash
sce today
```

**Response**:
```json
{
  "workout": {
    "type": "long_run",
    "distance_km": 18,
    "pace_range": "6:10-6:30/km",
    "duration_minutes": 112,
    "description": "Aerobic endurance development at easy, conversational pace"
  },
  "current_metrics": {
    "ctl": { "value": 42, "interpretation": "solid recreational fitness level" },
    "tsb": { "value": -8, "zone": "productive training zone" },
    "acwr": { "value": 1.14, "risk_level": "safe range" },
    "readiness": { "value": 68, "level": "good" }
  },
  "adaptation_triggers": [],
  "goal_context": {
    "race_type": "half_marathon",
    "race_date": "2026-05-24",
    "weeks_to_goal": 12
  }
}
```

### Step 3: Coach Assesses Situation

**Profile**:
- run_priority: "equal" (running and climbing equally important)
- conflict_policy: "ask_each_time" (no automatic resolution)

**Context**:
- Climbing comp registered 2 months ago (pre-planned commitment)
- Memory: "Climbing comps are social events" (high importance)
- Long run: 18 km, cornerstone of half marathon training
- Metrics: All good (CTL 42, ACWR 1.14, readiness 68)
- Half marathon: 12 weeks away (still in base-building phase)

**Coaching assessment**:
- Both activities have legitimate importance
- Metrics allow for flexibility (no triggers, good readiness)
- Base phase = some schedule flexibility exists
- Conflict policy = present trade-offs, athlete decides

### Step 4: Coach Presents Options with Trade-Offs

**Coach**:
```
I see the conflict. Your profile shows running and climbing are **equal priority**, and you prefer to decide conflicts case-by-case.

Let me give you context, then present options:

**Climbing comp context**:
- You registered 2 months ago (pre-existing commitment)
- I know climbing comps are social events for you, not just performance
- This is important to you

**Long run context**:
- 18 km is a key endurance-building workout
- Half marathon is 12 weeks away (still in base phase)
- Long runs are cornerstone of marathon/half training
- Missing one long run has modest impact (<5% race fitness)

**Your current state**:
- CTL: 42 (solid fitness)
- ACWR: 1.14 (safe)
- Readiness: 68 (good)
- No triggers - you're in great shape for either activity

**Here are your options:**

[Uses AskUserQuestion with 4 options]
```

**Options presented**:

1. **Climbing comp Saturday, long run Sunday** (reschedule, recommended)
   - **Pro**: Both activities completed at full quality
   - **Pro**: Honors pre-existing climbing commitment
   - **Pro**: Back-to-back training is manageable (CTL 42, no triggers)
   - **Con**: Sunday long run after Saturday climbing (legs may feel some fatigue)
   - **Con**: Two consecutive training days (no rest day between)
   - **Load estimate**: Climbing 340 AU systemic, 34 AU lower-body (minimal leg impact) → Sunday long run legs should be ~85-90% fresh

2. **Easy 6 km run + climbing comp Saturday** (compromise)
   - **Pro**: Maintains running frequency (4 days this week)
   - **Pro**: Light aerobic stimulus before comp (~30-40 AU)
   - **Pro**: Climbing comp is main focus
   - **Con**: Misses long run stimulus (18 km → 6 km = 67% reduction)
   - **Con**: Week's long run distance reduced significantly
   - **Impact**: Base building slightly slower this week, catch up next week

3. **Long run Saturday morning, skip climbing comp** (prioritize running)
   - **Pro**: Stays on training plan exactly
   - **Pro**: Long run completed as scheduled
   - **Pro**: Sunday rest day preserved
   - **Con**: Misses pre-planned climbing comp (social event)
   - **Con**: Climbing training disrupted
   - **Con**: Opportunity cost (comps are infrequent)

4. **Light climbing Saturday + shortened long run Sunday** (split both)
   - **Pro**: Participate in climbing comp (even if not at full effort)
   - **Pro**: Get long run stimulus (12 km = 67% of planned)
   - **Con**: Neither activity at full quality/commitment
   - **Con**: Climbing comp may feel compromised (conservation mode)
   - **Con**: Long run shortened (less endurance stimulus)

**My recommendation**: **Option 1** (climbing comp Sat, long run Sun).

**Why**:
- Your climbing comp was planned 2 months ago - honor that commitment
- Your metrics are excellent (no triggers, good readiness)
- Climbing's lower-body load is minimal (34 AU vs running's 100+ AU)
- Your legs will be 85-90% fresh Sunday for the long run
- Base phase = schedule flexibility exists (not peak phase)
- Both activities completed at full quality

**What would you prefer?**
```

### Step 5: Athlete Asks Clarifying Question

**Athlete**: "If I do option 1, will my legs be too tired from climbing to do the long run Sunday?"

### Step 6: Coach Explains Lower-Body Load Model

**Coach**:
```
Great question. Let's break down the physiology:

**Climbing impact on legs** (from our sport multiplier model):
- **Systemic load**: 340 AU (significant cardio/whole-body fatigue)
- **Lower-body load**: 34 AU (minimal leg-specific strain)
- **Why low?**: Climbing is upper-body dominant - your legs assist but aren't primary movers

**Comparison**:
- Hard cycling Saturday: 280 AU systemic, **98 AU lower-body** (high leg strain)
- Climbing Saturday: 340 AU systemic, **34 AU lower-body** (low leg strain)

**Sunday long run feasibility**:
- Your legs will have ~85-90% freshness (not 100%, but very close)
- Systemic fatigue from climbing recovers overnight (12-16 hours)
- Leg-specific recovery need is minimal (34 AU vs running's 100+ AU)

**Real-world comparison**:
- Climbing Sat + run Sun: Similar to "easy run Sat + long run Sun" (totally fine)
- Cycling Sat + run Sun: More challenging (high leg fatigue accumulation)

**What to monitor Sunday**:
- **First 2-3 km**: Legs may feel slightly heavy initially (systemic fatigue)
- **After warm-up**: Should feel normal (upper-body soreness, but legs fresh)
- **Pace**: Stick to 6:10-6:30/km easy pace (don't push harder due to fatigue)

**If legs feel off Sunday**:
- Shorten to 14 km (78% of planned) instead of 18 km
- Still valuable endurance stimulus
- Better than forcing 18 km through fatigue

**Bottom line**: Climbing's leg impact is minimal. Sunday long run is very feasible given your metrics (CTL 42, readiness 68, ACWR 1.14).

Does that help?
```

### Step 7: Athlete Decides

**Athlete**: "That makes sense! I'll do the climbing comp Saturday and long run Sunday. Thanks for explaining the leg load thing."

### Step 8: Coach Confirms Plan and Provides Tips

**Coach**:
```
Perfect! Here's your weekend plan:

**Saturday: Climbing Comp**
- Give it full effort - this is your planned commitment
- Hydrate well during comp
- Eat normally (don't restrict - your body needs fuel for Sunday)
- Post-comp: Light stretching for upper body

**Saturday evening**:
- Get good sleep (8+ hours if possible)
- Protein with dinner (muscle recovery)
- Hydrate well

**Sunday: Long Run (18 km at 6:10-6:30/km)**
- **Warm-up**: First 2-3 km may feel sluggish (systemic fatigue from climbing)
- **After warm-up**: Legs should feel fresh (upper body will be sore, but legs are fine)
- **Pace**: Easy, conversational (RPE 3-4)
- **Monitoring**: If legs feel unusually heavy past 5 km, shorten to 14 km
- **Fuel**: Bring water/fuel if it's a hot day or long route

**Why this works**:
- Climbing's leg impact is minimal (34 AU lower-body)
- Your readiness is good (68)
- ACWR is safe (1.14)
- Base phase = schedule flexibility

**Monday**:
- Rest day or easy 6 km recovery (depending on how you feel)

You're managing both sports intelligently. Enjoy the comp! 🧗‍♀️➡️🏃‍♀️
```

### Step 9: Sunday Check-In (Post Long Run)

**Sunday evening...**

**Athlete**: "Long run done! 18 km at 6:18 avg pace. Legs did feel a bit heavy first 3 km like you said, but after that felt totally fine."

**Coach**:
```
Excellent execution! A few observations:

**Pace analysis**:
- 6:18/km avg is right in your easy zone (6:10-6:30/km)
- Perfect pacing for aerobic development

**Fatigue pattern**:
- Heavy first 3 km = systemic fatigue from climbing (as predicted)
- Cleared after warm-up = legs were indeed fresh (lower-body load minimal)
- This confirms our sport multiplier model works 💡

**What this tells us**:
- You can handle climbing + running back-to-back (when climbing comes first)
- Lower-body load model is accurate for your physiology
- Future conflicts: Climbing → running (next day) is feasible
- Avoid: Running long/hard → climbing (next day) might be riskier (leg fatigue impacts footwork)

**Training impact**:
- Full long run completed ✅
- Climbing comp completed ✅
- CTL will track up this week (great progression)
- ACWR stays safe (1.14 → ~1.18, still safe range)

**This week**:
- Monday: Rest or easy 6 km recovery (your choice)
- Tuesday: Easy 8 km
- Wednesday: Rest
- Thursday: Tempo 8 km
- Friday: Easy 6 km
- Saturday: Climbing (regular training)

You managed the conflict perfectly. Both sports got quality attention. This is smart multi-sport training. 🎯
```

### Step 10: Capture Pattern as Memory

**Coach runs** (internally, after interaction):
```bash
sce memory add --type TRAINING_RESPONSE \
  --content "Successfully completed climbing comp Saturday + long run 18km Sunday. Legs felt heavy first 3km (systemic fatigue) then normal. Confirms climbing → running back-to-back feasible." \
  --tags "multi-sport:climbing-running,sequence:climbing-first,recovery:overnight,load:lower-body-minimal" \
  --confidence high
```

---

## Key Coaching Elements Demonstrated

1. **Profile respect**: Checked conflict_policy (ask_each_time), honored equal priority
2. **Memory integration**: Referenced "climbing comps are social events"
3. **Context gathering**: Assessed both activities' importance and flexibility
4. **Trade-off presentation**: 4 distinct options with pros/cons for each
5. **Clear recommendation**: Suggested option 1 with rationale
6. **Athlete question**: Answered clarifying question about leg freshness
7. **Sport science education**: Explained lower-body load model with examples
8. **Execution guidance**: Provided specific tips for both days
9. **Monitoring framework**: What to watch for Sunday (heavy legs first 3 km)
10. **Post-workout validation**: Confirmed execution, tied to sport multiplier model
11. **Pattern capture**: Stored successful sequence as memory for future conflicts

---

## Workflow Summary

```
1. Athlete reports conflict → Climbing comp Sat vs long run Sat
2. Check profile → run_priority: equal, conflict_policy: ask_each_time
3. Check memory → "Climbing comps are social events"
4. Get scheduled workout → Long run 18 km
5. Assess context → Comp pre-planned, base phase = flexibility
6. Present 4 options → Reschedule, compromise, prioritize running, split
7. Recommend option 1 → Climbing Sat, long run Sun (with rationale)
8. Athlete asks question → Will legs be too tired?
9. Explain sport model → Lower-body load minimal, systemic fatigue overnight recovery
10. Athlete decides → Option 1
11. Confirm plan + tips → Both days with execution guidance
12. Post-workout analysis → Confirmed model prediction (heavy 3km, then fine)
13. Capture memory → Store pattern for future conflicts
```

---

## Why This Worked

**Alignment of factors**:
- ✅ Equal priority profile (neither sport automatically wins)
- ✅ Conflict policy: ask_each_time (coach presents options)
- ✅ Climbing pre-planned 2 months ago (legitimate commitment)
- ✅ Base phase = schedule flexibility exists
- ✅ Good metrics (no triggers, ACWR safe, readiness good)
- ✅ Lower-body load model predicts feasibility

**Coaching approach**:
- **Respect both sports**: Neither dismissed as less important
- **Educational**: Explained lower-body load model (builds athlete understanding)
- **Trade-off clarity**: 4 options with specific pros/cons
- **Clear recommendation**: Suggested best option with reasoning
- **Athlete agency**: Let athlete decide after full context
- **Execution support**: Provided tips for both days
- **Validation**: Post-workout analysis confirmed model accuracy
- **Pattern learning**: Captured successful sequence as memory

This demonstrates **multi-sport coaching** - respecting both commitments, using sport science (load models) to predict feasibility, and empowering athlete with full context to make informed decisions.

---

## Contrast: What Poor Coaching Looks Like

**❌ Bad coaching response**:
```
"You have a long run scheduled. You need to skip the climbing comp and focus on your running goal."
```

**Why bad**:
- Ignores equal priority profile
- Dismisses pre-planned commitment
- Binary thinking (one sport must lose)
- No trade-off analysis
- No athlete agency

**✅ Good coaching (what we did)**:
- Honored equal priority
- Presented 4 options with trade-offs
- Explained feasibility using sport science
- Recommended best option with rationale
- Athlete made informed decision
- Both activities completed successfully

---

## Key Takeaway

Multi-sport athletes have **complex schedules with legitimate competing commitments**. Good coaching:
1. Respects profile settings (priority, conflict policy)
2. Gathers context (importance, flexibility, timing)
3. Uses sport science (load models) to assess feasibility
4. Presents options with clear trade-offs
5. Makes recommendation with rationale
6. Empowers athlete to decide
7. Provides execution support
8. Validates outcomes and captures patterns

**Result**: Both climbing comp and long run completed successfully, athlete satisfaction high, training plan intact, pattern learned for future conflicts.
