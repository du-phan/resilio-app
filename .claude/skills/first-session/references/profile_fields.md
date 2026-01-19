# Complete Profile Fields Reference

## Overview

The profile system supports 28 fields accessible via `sce profile set` and `sce profile get`. Use natural conversation to gather most values, not AskUserQuestion.

---

## Basic Information Fields

### name (string)
**What**: Athlete's name
**How to gather**: Natural conversation
**Example**:
```
Coach: "What's your name?"
Athlete: "Alex"
Command: sce profile set --name "Alex"
```

### age (integer)
**What**: Athlete's age
**How to gather**: Natural conversation
**Example**:
```
Coach: "How old are you?"
Athlete: "32"
Command: sce profile set --age 32
```

---

## Physiological Fields

### max-hr (integer)
**What**: Maximum heart rate
**How to gather**: Reference `sce profile analyze` data first
**Example**:
```
Coach: "Looking at your Strava data, your peak HR is 199 bpm. Use that as your max HR?"
Athlete: "Yes" OR "Actually, I think it's 190"
Command: sce profile set --max-hr 199
```

**If no data available**: Use age-based estimate (220 - age) as starting point, verify later

### resting-hr (integer, optional)
**What**: Resting heart rate (morning, before getting up)
**How to gather**: Natural conversation
**Example**: `sce profile set --resting-hr 52`

---

## Training Constraints

### max-run-days (integer)
**What**: Maximum running days per week (3-7)
**How to gather**: Natural conversation
**Example**:
```
Coach: "How many days per week can you realistically run?"
Athlete: "4 days works best for me"
Command: sce profile set --max-run-days 4
```

### min-run-days (integer, optional)
**What**: Minimum running days per week
**Default**: 3 if not specified
**Example**: `sce profile set --min-run-days 3`

### max-session-minutes (integer)
**What**: Longest session duration in minutes
**How to gather**: Natural conversation
**Example**:
```
Coach: "What's the longest time you can spend on a long run?"
Athlete: "About 2 hours max"
Command: sce profile set --max-session-minutes 120
```

### available-days (comma-separated)
**What**: Days of week athlete can train
**Format**: Lowercase, comma-separated (e.g., "monday,wednesday,friday")
**Example**:
```
Coach: "Which days work best for running?"
Athlete: "Tuesdays, Thursdays, and weekends"
Command: sce profile set --available-days "tuesday,thursday,saturday,sunday"
```

### preferred-days (comma-separated, optional)
**What**: Days athlete prefers for long runs or quality
**Example**: `sce profile set --preferred-days "saturday,sunday"`

### time-preference (string, optional)
**What**: Preferred time of day for training
**Values**: "morning", "afternoon", "evening", "flexible"
**Example**: `sce profile set --time-preference morning`

---

## Sport Priority & Multi-Sport

### run-priority (string)
**What**: Running priority relative to other sports
**Values**:
- `"primary"`: Running is main sport (race goal focused)
- `"equal"`: Running and other sport equally important
- `"secondary"`: Running for fitness, other sport is primary

**How to gather**: Natural conversation
**Example**:
```
Coach: "Your activities show running (28%) and climbing (42%). Which is your primary sport?"
Athlete: "They're equal - I'm committed to both"
Command: sce profile set --run-priority equal
```

### conflict-policy (string)
**What**: How to handle scheduling conflicts between sports
**Values**:
- `"ask_each_time"`: Present options for each conflict
- `"primary_sport_wins"`: Prioritize primary sport automatically
- `"running_goal_wins"`: Keep key running workouts unless injury risk

**How to gather**: **AskUserQuestion** (ONLY appropriate use)
**Example**: See main SKILL.md Step 4d

---

## Additional Sport Constraints

### sport (via add-sport command)
**What**: Add non-running sport with constraints
**Fields per sport**:
- `--sport`: Sport name (e.g., "climbing", "cycling")
- `--days`: Fixed days for this sport (comma-separated)
- `--duration`: Typical session duration (minutes)
- `--intensity`: typical, easy, moderate, moderate_to_hard, hard

**Example**:
```bash
sce profile add-sport --sport climbing --days "tuesday,thursday" --duration 120 --intensity moderate_to_hard
```

**List all sports**:
```bash
sce profile list-sports
```

**Remove sport**:
```bash
sce profile remove-sport --sport yoga
```

---

## Goal & Race Information

### current-goal-distance (string, set via sce goal)
**What**: Current race distance goal
**Values**: "5k", "10k", "half_marathon", "marathon"
**Set via**: `sce goal --type half_marathon --date 2026-06-01`

### current-goal-date (date, set via sce goal)
**What**: Race date
**Format**: YYYY-MM-DD
**Set via**: Same `sce goal` command above

### current-goal-time (string, optional)
**What**: Goal race time (e.g., "1:30:00" for half marathon)
**Set via**: `sce goal --type half_marathon --date 2026-06-01 --time "1:30:00"`

---

## Training History (Auto-populated)

### training-age (integer, auto)
**What**: Years of consistent running training
**Source**: Calculated from Strava history analysis
**Usage**: Informs training volume progression rate

### injury-history (deprecated - use memory system)
**What**: Past injuries and concerns
**NEW APPROACH**: Store each injury as separate memory, not in profile field
**Why**: Better searchability, tagging, deduplication

See main SKILL.md Step 4b for memory-based injury storage.

---

## Advanced Fields (Auto-populated by analysis)

### vdot (float, auto)
**What**: Daniels' VDOT fitness score
**Source**: Calculated from recent race times or tempo efforts
**Usage**: Determines training pace zones
**Command**: `sce vdot calculate --race-type 10k --time 42:30`

### ctl-baseline (float, auto)
**What**: CTL at start of plan
**Source**: Populated when plan is created
**Usage**: Tracks fitness progression over plan

---

## Profile Management Commands

### View Profile
```bash
sce profile get
# Returns JSON with all fields
```

### Edit Profile (Advanced)
```bash
sce profile edit
# Opens profile in $EDITOR (vim, nano, etc.)
```

### Analyze Strava Data
```bash
sce profile analyze
# Returns suggested values from synced activities
```

### Set Multiple Fields at Once
```bash
sce profile set --name "Alex" --age 32 --max-hr 190 --max-run-days 4 --conflict-policy ask_each_time
```

### Update Individual Field
```bash
sce profile set --max-hr 185
# Only updates max-hr, leaves other fields unchanged
```

---

## Field Validation

### Required Fields (Cannot Create Plan Without)
- `name`
- `age`
- `max-hr`
- `max-run-days`
- Current goal (set via `sce goal`)

### Optional But Recommended
- `max-session-minutes` (defaults to 180 if not set)
- `available-days` (defaults to all days if not set)
- `conflict-policy` (defaults to "ask_each_time" if multi-sport)

### Auto-Populated (Don't Ask)
- `vdot` (calculated from races)
- `ctl-baseline` (set when plan created)
- `training-age` (estimated from history)

---

## Complete Field List (28 total)

| Field | Type | Required | How to Gather |
|-------|------|----------|---------------|
| name | string | Yes | Natural conversation |
| age | integer | Yes | Natural conversation |
| max-hr | integer | Yes | Reference analyze data |
| resting-hr | integer | No | Natural conversation |
| max-run-days | integer | Yes | Natural conversation |
| min-run-days | integer | No | Natural conversation |
| max-session-minutes | integer | Recommended | Natural conversation |
| available-days | csv | Recommended | Natural conversation |
| preferred-days | csv | No | Natural conversation |
| time-preference | string | No | Natural conversation |
| run-priority | string | Yes if multi-sport | Natural conversation |
| conflict-policy | string | Yes if multi-sport | **AskUserQuestion** |
| current-goal-distance | string | Yes | `sce goal` command |
| current-goal-date | date | Yes | `sce goal` command |
| current-goal-time | string | No | `sce goal` command |
| vdot | float | Auto | Calculated from races |
| ctl-baseline | float | Auto | Set when plan created |
| training-age | integer | Auto | From Strava analysis |

**Plus**: Sport-specific constraints via `add-sport` (unlimited sports)

---

## Additional Resources

- **CLI Reference**: [Profile Commands](../../../docs/coaching/cli/cli_profile.md)
- **Profile JSON schema**: See `sports_coach_engine/models/profile.py`
