# Example Onboarding: Runner Primary (Race-Focused)

## Scenario

**Athlete**: Jordan, 28M, competitive runner training for 10K PR
**Other sports**: Occasional cycling for cross-training
**Priority**: Running primary, cycling secondary
**Goal**: Sub-40 10K in 12 weeks

---

## Complete Session Transcript

### Step 1: Authentication

**User**: "I want to train for a 10K PR"

**Coach**: "Great! Let's get you set up. First, I need to check your Strava authentication."

```bash
sce auth status
# Exit code: 3 (not authenticated)
```

**Coach**: "Your Strava account isn't connected yet. I need access to your training history to provide intelligent coaching. Let me generate an authorization link."

```bash
sce auth url
# Returns: https://strava.com/oauth/authorize?client_id=12345&redirect_uri=...
```

**Coach**: "Here's your authorization URL: [URL]

Please:
1. Open this URL in your browser
2. Click 'Authorize' to grant access
3. Copy the code from the final page
4. Paste it here"

**Athlete**: "ABC123XYZ789"

**Coach**:
```bash
sce auth exchange --code ABC123XYZ789
# Success
```

"Perfect! Connected to your Strava account."

---

### Step 2: Sync Activities

**Coach**:
```bash
sce sync
# Imported 127 activities (6 months)
```

"Great! Imported 127 activities from the last 6 months (180 days). Let me analyze your training patterns."

---

### Step 3: Analyze Historical Data

**Coach**:
```bash
sce status
sce profile analyze
```

**Analysis results**:
```json
{
  "max_hr_observed": 194,
  "avg_hr_mean": 152,
  "weekly_run_km_avg": 48.2,
  "training_days_distribution": {
    "monday": 0.15,
    "tuesday": 0.82,
    "wednesday": 0.10,
    "thursday": 0.88,
    "friday": 0.05,
    "saturday": 0.92,
    "sunday": 0.85
  },
  "sport_distribution": {
    "running": 0.88,
    "cycling": 0.12
  },
  "ctl_current": 52.3,
  "ctl_interpretation": "competitive fitness level"
}
```

**Coach**: "I can see:
- Your CTL is 52 (competitive fitness level)
- You average 48 km/week running
- You also do occasional cycling (12% of activities)
- You typically train Tuesdays, Thursdays, Saturdays, Sundays
- Your peak HR is 194 bpm

Let's set up your profile. What's your name?"

---

### Step 4: Profile Setup

**Athlete**: "Jordan"

**Coach**: "And how old are you?"

**Athlete**: "28"

**Coach**: "Looking at your Strava data, your peak heart rate is 194 bpm. Should we use that as your max HR?"

**Athlete**: "Yes, that's accurate"

**Coach**: "I see a 10-day gap in your training in late December where your CTL dropped from 54 to 48. Was that planned or due to injury?"

**Athlete**: "Just holiday break, no injuries"

**Coach**: "Good to know. Your activities show running at 88% and occasional cycling. Is running your primary sport?"

**Athlete**: "Yes, I'm focused on improving my 10K time. Cycling is just for active recovery."

**Coach**: "Perfect. Since you're race-focused, when there's a conflict between running and cycling, should running workouts take priority, or would you like me to ask each time?"

**Athlete**: "Running should always win - it's my priority"

**Coach**:
```bash
sce profile set --name "Jordan" --age 28 --max-hr 194 --run-priority primary --conflict-policy running_goal_wins
```

"Profile created. Since running is your primary sport, I'll prioritize key running workouts and schedule cycling around them."

---

### Step 5: Goal Setting

**Coach**: "Tell me about your 10K goal. When is the race?"

**Athlete**: "March 15th, 2026"

**Coach**: "And what's your goal time?"

**Athlete**: "Sub-40. My PR is 41:15, so shaving off 75 seconds"

**Coach**: "That's a 3% improvement - very achievable. Let me calculate your current VDOT."

```bash
sce vdot calculate --race-type 10k --time 41:15
# VDOT: 51.2
```

**Coach**: "Your current VDOT is 51.2. VDOT is a running fitness score based on your recent race or hard-effort times. I use it to set your training paces so your running stays matched to your current fitness alongside your other sports. To run sub-40 (3:59/km pace), you'd need a VDOT of 53.5 - a 2.3 point improvement over 12 weeks. That's realistic with focused training."

```bash
sce goal --type 10k --date 2026-03-15 --time "39:59"
```

"Goal set: 10K on March 15th, 2026, goal time 39:59."

---

### Step 6: Constraints Discussion

**Coach**: "Before I design your plan, a few questions about your schedule:

How many days per week can you run?"

**Athlete**: "I can do 5 days comfortably, maybe 6 if needed"

**Coach**: "Any days you absolutely cannot run?"

**Athlete**: "Mondays and Wednesdays are tough with work."

**Coach**: "Got it. What's the longest time you can spend on a long run?"

**Athlete**: "90 minutes max on weekends"

**Coach**: "And your cycling - how many times per week? Any days you can’t do it?"

**Athlete**: "Twice a week, usually Wednesdays or Fridays. Easy spinning for recovery."

**Coach**:
```bash
sce profile set --max-run-days 5 --unavailable-days "monday,wednesday" --max-session-minutes 90

sce profile add-sport --sport cycling --frequency 2 --duration 60 --intensity easy
```

"Perfect. I have everything I need:
- 5 run days/week (Tue/Thu/Fri/Sat/Sun)
- Long runs Saturday or Sunday (max 90 min)
- Easy cycling 2x/week for recovery"

---

### Step 7: Transition to Plan Design

**Coach**: "Excellent! Here's what I have:

**Your Profile**:
Quick defs (first mention only): CTL is your long-term training load—think of it as your 6-week fitness trend. For multi-sport athletes, it reflects total work across running + other sports.
- Jordan, 28M, max HR 194 bpm
- Running primary, cycling for recovery
- CTL 52 (competitive fitness)
- VDOT 51.2

**Your Goal**:
- 10K on March 15th (12 weeks away)
- Goal time: 39:59 (VDOT 53.5)
- Need +2.3 VDOT improvement

**Your Constraints**:
- 5 run days/week
- Tuesday track club (typical)
- Max 90-min long runs
- Easy cycling Wed/Fri

**Recommended Plan Structure**:
Based on your current fitness and goal, I recommend a Daniels-based 10K plan with:
- 3 quality sessions/week (Tues intervals at track, Thurs tempo, Sat long run)
- 2 easy days (Fri recovery, Sun easy)
- Total volume: 52-60 km/week (slight build from current 48)
- Cycling: Keep Wed/Fri easy spins

Would you like me to design your full 12-week plan now?"

**Athlete**: "Yes, let's do it"

**Coach**:
[Runs `vdot-baseline-proposal`, then `macro-plan-create` with context:
- Profile data
- Goal (10K, 2026-03-15, 39:59)
- Constraints (5 days, 90min max, Tues track club)
- Current fitness (CTL 52, VDOT 51.2)
]

---

## Key Coaching Elements Demonstrated

1. **Authentication first**: Always check auth before proceeding
2. **Data-driven questions**: Referenced actual numbers (48 km/week, CTL 52, peak HR 194)
3. **Natural conversation**: All inputs via conversation, not chat-based numbered options
4. **Context awareness**: Used activity gaps to check for injuries
5. **Sport priority clarity**: Running primary, cycling secondary
6. **Conflict policy**: Running_goal_wins (auto-prioritize race prep)
7. **VDOT calculation**: Showed athlete exactly what improvement is needed
8. **Smooth handoff**: Transitioned to macro plan creation with full context

---

## Onboarding Checklist

- ✅ Authentication successful
- ✅ 127 activities synced (180 days)
- ✅ Profile created (name, age, max HR, priority, conflict policy)
- ✅ No injury history (confirmed via activity gap check)
- ✅ Goal set (10K, March 15th, sub-40)
- ✅ Constraints captured (5 days, 90min max, Tues track club, Wed/Fri cycling)
- ✅ VDOT calculated (51.2 current, 53.5 target)
- ✅ Ready for plan generation

**Result**: Complete onboarding with all context needed for intelligent plan design.
