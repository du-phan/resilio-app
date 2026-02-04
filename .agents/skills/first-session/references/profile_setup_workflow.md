# Profile Setup Workflow

## Contents
- [Basic Information Fields (Step 4a)](#step-4a-basic-info)
- [Running Experience (Step 4a-experience)](#step-4a-experience-running-experience)
- [Injury History (Step 4b)](#step-4b-injury-history-context-aware-with-memory-system)
- [Sport Priority (Step 4c)](#step-4c-sport-priority-natural-conversation)
- [Conflict Policy (Step 4d)](#step-4d-conflict-policy-askuserquestion---only-use-here)
- [Creating Profile (Step 4e)](#step-4e-create-profile)
- [Personal Bests - Race History (Step 4.5)](#step-45-personal-bests-pbs---race-history-capture)
- [Other Sports Collection (Step 4f)](#step-4f-other-sports-collection-data-driven-mandatory)
- [Data Alignment Check (Step 4f-validation)](#step-4f-validation-data-alignment-check)
- [Communication Preferences (Step 4g)](#step-4g-communication-preferences-optional---can-skip)

---

## Step 4a: Basic Info

**Use natural conversation for all text/number inputs.**

### Name & Age

```
Coach: "What's your name?"
Athlete: "Alex"
Coach: [Store for later]

Coach: "How old are you?"
Athlete: "32"
Coach: [Store for later]
```

### Max HR (reference analyzed data)

```
Coach: "Looking at your Strava data, peak HR is 199 bpm. Use that as your max HR?"
Athlete: "Yes" OR "Actually, I think it's 190"
Coach: [Store actual value]
```

### Resting HR

```
Coach: "What's your morning resting heart rate? (Measure first thing when you wake up)"
Athlete: "Around 52 bpm"
Coach: [Store value]
```

**If athlete doesn't know**: "No problem - you can measure it tomorrow and add later with `sce profile set --resting-hr XX`"

---

## Step 4a-experience: Running Experience

**Ask about running background** (natural conversation):

```
Coach: "How long have you been running? Just a rough estimate is fine."
Athlete: "About 5 years, but took a 2-year break in the middle"
```

**Save to profile**:
```bash
sce profile set --running-experience-years 5
```

### Why This Matters

- Helps contextualize fitness level and injury risk
- Newer runners (<2 years) need more conservative volume progression
- Experienced runners (>5 years) can handle higher training loads
- Informs coaching tone (more explanations for beginners)

### Handle Edge Cases

**"Just started this year"**:
- Calculate from first activity: `sce profile analyze` shows first activity date
- Example: First activity was March 2025 → ~10 months = 0-1 years

**"Been running since high school but stopped for a decade"**:
- Count active years only
- Example: "Ran 4 years in high school, stopped 10 years, resumed 2 years ago" → 6 years total

**"Not sure"**:
- Skip field, mark in notes: "Running experience not specified during onboarding"
- Can estimate from Strava first activity date if available

---

## Step 4b: Injury History (Context-Aware with Memory System)

**Gather injury signals from data**:

```bash
sce profile analyze                                      # Check activity gaps
sce activity search --query "pain injury sore" --since 120d  # Search notes
sce activity list --since 90d --has-notes --sport run      # Context
```

### If Gap or Pain Mention Detected

```
Coach: "I noticed a 2-week gap in November (CTL dropped 44→28). Was that injury-related?"
Coach: "Quick note: CTL is your long-term training load—think of it as your 6-week fitness trend. For multi-sport athletes, it reflects total work across running + other sports."
Athlete: "Yeah, left knee tendonitis. Healed now but I watch mileage."
```

### If No Gaps

```
Coach: "Any past injuries I should know about? Helps me watch for warning signs."
```

### IMPORTANT: Store Each Injury as Structured Memory

**NOT in profile field - use memory system**:

```bash
sce memory add --type INJURY_HISTORY \
  --content "Left knee tendonitis Nov 2023, fully healed, watches mileage" \
  --tags "body:knee,year:2023,status:resolved,caution:mileage" \
  --confidence high
```

### Why Memory System

- Independent searchability (query across all injuries)
- Rich tagging (body part, trigger, threshold, status, solution)
- Deduplication (prevents duplicate entries)
- Confidence scoring (high/medium/low)

### Tag Conventions

- `body:{part}`: knee, achilles, hamstring, it-band, plantar-fascia
- `trigger:{type}`: frequency, long-run, volume, speed, terrain
- `threshold:{value}`: 3-days, 18km, 50km-week, 5min-pace
- `status:{state}`: current, resolved, monitoring, recurring
- `solution:{method}`: rest, strength, form, volume-cap, shoe-change

### Examples

**Resolved knee injury with volume trigger**:
```bash
sce memory add --type INJURY_HISTORY \
  --content "Right knee pain when volume >45km/week, resolved with strength work" \
  --tags "body:knee,trigger:volume,threshold:45km-week,status:resolved,solution:strength" \
  --confidence high
```

**Recurring achilles issue**:
```bash
sce memory add --type INJURY_HISTORY \
  --content "Left achilles tendonitis, flares with speed work, ongoing management" \
  --tags "body:achilles,trigger:speed,status:recurring,solution:warmup" \
  --confidence high
```

---

## Step 4c: Sport Priority (Natural Conversation)

Reference sport distribution from `sce profile analyze`:

```
Coach: "Your activities show running (28%) and climbing (42%). Primary sport or equal?"
Athlete: "Equal - committed to both"
```

### Options

- `"running"` = PRIMARY: Running is the main sport (race focus)
- `"equal"` = EQUAL: Multiple sports equally important
- Other sport name (e.g., `"climbing"`) = SECONDARY: Running supports primary sport

### Store Value

```bash
sce profile set --running-priority equal
# OR
sce profile set --running-priority primary
# OR
sce profile set --running-priority secondary
```

---

## Step 4d: Conflict Policy (chat-based numbered options - ONLY USE HERE)

**This is a decision with trade-offs** - appropriate for chat-based numbered options.

### Prompt

"When there's a conflict between running and climbing - like long run + climbing comp same day - how should I handle it?"

### Options

1. **Ask me each time** - Present options/trade-offs per conflict (most flexible)
2. **Climbing wins by default** - Running adjusts around climbing (protect primary sport)
3. **Running goal wins** - Keep key runs unless injury risk (prioritize race prep)

### Store As

`conflict_policy` = `"ask_each_time"` | `"primary_sport_wins"` | `"running_goal_wins"`

```bash
sce profile set --conflict-policy ask_each_time
```

---

## Step 4e: Create Profile

**Combine all collected data into profile creation**:

```bash
sce profile set --name "Alex" --age 32 --max-hr 190 \
  --resting-hr 52 --running-experience-years 5 \
  --running-priority equal --conflict-policy ask_each_time
```

**Note**: Injury history stored separately in memory system (Step 4b).

**For complete field reference (28 fields)**: See [profile_fields.md](profile_fields.md)

---

## Step 4.5: Personal Bests (PBs) - Race History Capture

### Why This Matters

PBs provide accurate fitness baseline + motivational context. Even old PBs reveal progression/regression.

**CRITICAL**: Strava sync only captures last 6 months (180 days). PBs older than 6 months won't be auto-detected. **Manual entry is PRIMARY workflow.**

### Workflow: Manual Entry FIRST, Then Auto-Import

#### Step 1: Ask Directly for PBs

**Natural conversation**:
```
Coach: "What are your personal bests for 5K, 10K, half marathon, and marathon?"
Coach: "When did you run these? Were they official races or GPS efforts?"
```

#### Step 2: Manual Entry for Each PB Mentioned

```bash
sce race add --distance 10k --time 42:30 --date 2023-06-15 \
  --source official_race --location "City 10K Championship"

sce race add --distance 5k --time 18:45 --date 2022-05-10 \
  --source gps_watch --notes "Parkrun effort"
```

**Race sources**:
- `official_race`: Chip-timed race (highest accuracy)
- `gps_watch`: GPS-verified effort (good accuracy)
- `estimated`: Calculated/estimated (lower accuracy)

#### Step 3: Auto-Import Recent Races

**After manual entry, supplement with auto-import**:

```bash
sce race import-from-strava --since 120d
```

**What this detects**:
- Strava activities with `workout_type == 1` (race flag)
- Keywords in title/description: "race", "5K", "10K", "HM", "PB", "PR"
- Distance matching standard race distances (±5%)

**Present detected races for confirmation**:
```
Coach: "Found 2 potential races in last 6 months (180 days):
- Half Marathon 1:32:00 (Nov 2025) - not yet in race_history
- 10K 43:00 (Dec 2025) - not yet in race_history

Should I add these to your race history?"
```

**If athlete confirms**, add each race:
```bash
sce race add --distance half_marathon --time 1:32:00 --date 2025-11-15 \
  --source gps_watch --location "State Half Marathon"
```

#### Step 4: Verify Race History

```bash
sce race list
```

**Review with athlete**:
```
Coach: "I have your 10K PB at 42:30 (Jun 2023, VDOT 48), 5K at 18:45 (May 2022, VDOT 51). VDOT is a running fitness score based on your recent race or hard-effort times. I use it to set your training paces so your running stays matched to your current fitness alongside your other sports. Anything missing?"
```

#### Step 5: Store Key PBs in Memory System

**For long-term context**:

```bash
sce memory add --type RACE_HISTORY \
  --content "10K PB: 42:30 (Jun 2023, City 10K, VDOT 48)" \
  --tags "distance:10k,vdot:48,year:2023,pb:true" \
  --confidence high
```

**Why memory + profile**: Profile stores structured race data, memory enables natural language search and long-term pattern detection.

### Benefits of Race History

1. **Accurate VDOT baseline**: Use historical PBs (even if >180 days old) for training pace calculation
2. **Goal validation**: "Your 10K PB (VDOT 48) predicts 1:25 half, is 1:20 realistic?"
3. **Motivational context**: "Let's rebuild to your 42:30 fitness"
4. **Progression tracking**: Compare current VDOT estimate to peak PB VDOT over time

### Common Scenarios

#### Q: Athlete says "I don't remember exact times"

**Response**: "No problem - we can estimate. What's your rough 5K or 10K time?"

Use `--source estimated` and add note: `--notes "Athlete estimate, not official"`

#### Q: Athlete has no race history

**Response**: "No PBs yet? We'll establish baseline from tempo workouts. First quality run will give us VDOT estimate."

Skip race entry, use `sce vdot estimate-current` after first tempo workout

#### Q: Old PBs from years ago

**Response**: "That 42:30 10K from 2018 is still useful! Gives baseline even if fitness has changed."

Enter with accurate date, system tracks progression/regression from peak

---

## Step 4f: Other Sports Collection (Data-Driven, MANDATORY)

**CRITICAL: Check Strava data and collect ALL significant activities, regardless of running_priority.**

### Why This Matters

- **Complete athlete picture**: Need full activity context for intelligent coaching
- **Accurate load calculations**: CTL/ACWR require ALL training load, not just running
- **Schedule awareness**: Can't avoid conflicts without knowing commitments
- **Recovery planning**: Upper-body work (climbing) affects systemic fatigue even if legs are fresh

**running_priority determines CONFLICT RESOLUTION, not whether to track sports.**

### Workflow: Analyze Data FIRST, Then Collect

#### Step 1: Check Sport Distribution

```bash
sce profile analyze
# Examine sport_distribution and sport_percentages
```

#### Step 2: Present Findings to Athlete

**Reference actual data**:

```
Coach: "Looking at your last 6 months (180 days) on Strava:
- Climbing: 40% (30 sessions)
- Running: 31% (23 sessions)
- Yoga: 19% (14 sessions)
- Cycling: 10% (8 sessions)

I need to track your climbing/yoga schedule to:
1. Calculate total training load (CTL/ACWR)
2. Design run days that avoid overtraining
3. Understand when you're truly rested vs fatigued"
```

#### Step 3: Collect EACH Significant Sport

**For each sport >15% of activities**:

**Climbing (40%)**:
```
Coach: "What days do you typically climb?"
Athlete: "Tuesdays and Thursdays, usually 2-hour sessions."
Coach: "Intensity? Light technique work or full sending?"
Athlete: "Moderate to hard - I push pretty hard both days."
```

```bash
sce profile add-sport --sport climbing --days tue,thu --duration 120 --intensity moderate_to_hard
```

**Yoga (19%)**:
```bash
sce profile add-sport --sport yoga --days sun --duration 60 --intensity easy
```

### Handle Edge Cases

#### If running_priority='primary' AND significant other sports exist

```
Coach: "You said running is your primary sport (marathon focus), but I see you also
climb 40% of the time. I'll track your climbing to avoid scheduling conflicts, but
when there's a conflict, the marathon training will take priority. Sound good?"
```

→ Still collect other_sports, just set conflict_policy appropriately

#### If running_priority='equal' but Strava shows >85% running

```
Coach: "Your Strava shows mostly running (91%). Do you have other sports not tracked
on Strava, or should I change running_priority to 'primary'?"

→ If other sports off Strava: Collect manually
→ If truly just running: Update running_priority="primary"
```

#### Verify Collection

```bash
sce profile list-sports
# Should show all sports >15% from analyze data
```

---

## Step 4f-validation: Data Alignment Check

**MANDATORY: Verify other_sports matches actual activity patterns**

```bash
sce profile validate
# Or manually:
sce profile get | jq '.other_sports'
sce profile analyze | jq '.sport_percentages'
```

### Check for Alignment

- ✅ **Good**: Climbing shows 40% in analyze → climbing in other_sports
- ❌ **Bad**: Climbing shows 40% in analyze → other_sports is empty

### If Validation Shows Missing Sports

```
Coach: "I see a mismatch. Your Strava shows {sport} at {percentage}%, but it's not
in your profile. Let me add it now before we continue."
```

**Return to Step 4f and collect missing sports.**

### Only Proceed When

- All sports >15% from analyze are in other_sports
- OR athlete confirms those activities are irregular/one-off

---

## Step 4g: Communication Preferences (Optional - Can Skip)

**Offer customization without creating decision fatigue**:

```
Coach: "I can tailor my coaching style to your preferences, or use defaults if you'd like to get started quickly.
Would you like to customize how I communicate?"
```

### If Athlete Says YES

**Detail level**:
```
Coach: "Do you prefer brief updates, moderate detail, or comprehensive analysis after each workout?"
Athlete: "Moderate detail works for me"
# Store: detail_level = "moderate"
```

**Coaching style**:
```
Coach: "What coaching tone works best for you: supportive, direct, or analytical?"
Athlete: "Direct - just tell me what to do"
# Store: coaching_style = "direct"
```

**Intensity metric**:
```
Coach: "For workouts, do you prefer pace targets, heart rate zones, or RPE (perceived effort, 1–10 scale)?"
Athlete: "Pace - I like tangible numbers"
# Store: intensity_metric = "pace"
```

**Update profile**:
```bash
sce profile set --detail-level moderate --coaching-style direct --intensity-metric pace
```

### If Athlete Says NO or "use defaults"

```
Coach: "No problem! I'll use moderate detail, supportive tone, and pace-based workouts.
You can adjust anytime with 'sce profile set'."
```

**Skip to Step 5 (Goal Setting)**

---

## Summary

**Profile setup complete when**:
- ✅ Basic info collected (name, age, max HR, resting HR, experience)
- ✅ Injury history recorded in memory system (if applicable)
- ✅ Sport priority set (primary/equal/secondary)
- ✅ Conflict policy chosen (ask_each_time/primary_sport_wins/running_goal_wins)
- ✅ Profile created with `sce profile set`
- ✅ Race history captured (PBs added manually + auto-import)
- ✅ Other sports collected (all >15% from Strava)
- ✅ Data validation passed (other_sports matches Strava distribution)
- ✅ Communication preferences set (or defaults accepted)

**Return to main workflow** → Step 5: Goal Setting
