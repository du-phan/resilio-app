# Profile Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Commands for managing athlete profiles including personal information, constraints, multi-sport commitments, and preferences.

**Commands in this category:**
- `sce profile create` - Create a new athlete profile
- `sce profile get` - Get athlete profile with all settings
- `sce profile set` - Update profile fields
- `sce profile add-sport` - Add a sport commitment
- `sce profile remove-sport` - Remove a sport commitment
- `sce profile list-sports` - List all sport commitments
- `sce profile edit` - Open profile YAML in $EDITOR
- `sce profile analyze` - Analyze synced activity history to suggest profile values

---

## sce profile create

Create a new athlete profile with sensible defaults.

**Required:**
- `--name` (string) - Athlete name

**Optional - Basic Info:**
- `--age` (integer, 0-120) - Age in years
- `--email` (string) - Contact email

**Optional - Vital Signs:**
- `--max-hr` (integer, 120-220) - Maximum heart rate
- `--resting-hr` (integer, 30-100) - Resting heart rate

**Optional - Running Background:**
- `--injury-history` (string) - Free-text injury description
- `--run-experience-years` (integer) - Years of running experience
- `--weekly-km` (float) - Current weekly volume baseline
- `--run-days-per-week` (integer, 0-7) - Current frequency
- `--vdot` (float, 30-85) - Jack Daniels VDOT

**Optional - Constraints:**
- `--min-run-days` (integer, 0-7) - Minimum run days per week (default: 2)
- `--max-run-days` (integer, 0-7) - Maximum run days per week (default: 4)
- `--available-days` (comma-separated) - Available run days (e.g., "monday,wednesday,friday")
- `--preferred-days` (comma-separated) - Preferred run days (subset of available)
- `--time-preference` (`morning`, `evening`, `flexible`) - Time of day preference
- `--max-session-minutes` (integer) - Maximum session duration (default: 90)

**Optional - Multi-Sport:**
- `--run-priority` (`primary`, `secondary`, `equal`) - Running priority (default: equal)
- `--primary-sport` (string) - Primary sport name if not running
- `--conflict-policy` (`primary_sport_wins`, `running_goal_wins`, `ask_each_time`) - Conflict resolution (default: ask_each_time)

**Optional - Preferences:**
- `--detail-level` (`brief`, `moderate`, `detailed`) - Coaching detail level (default: moderate)
- `--coaching-style` (`supportive`, `direct`, `analytical`) - Communication style (default: supportive)
- `--intensity-metric` (`pace`, `hr`, `rpe`) - Primary intensity metric (default: pace)

**Examples:**

```bash
# Minimal profile
sce profile create --name "Alex"

# Full profile with all fields
sce profile create \
  --name "Alex" --age 32 --email "alex@example.com" \
  --max-hr 199 --resting-hr 55 \
  --injury-history "IT band 2024, resolved" \
  --run-experience-years 3 --weekly-km 25 \
  --available-days "tuesday,thursday,saturday,sunday" \
  --preferred-days "saturday,sunday" \
  --time-preference morning \
  --run-priority equal --primary-sport climbing \
  --conflict-policy ask_each_time \
  --detail-level moderate
```

---

## sce profile get

Get athlete profile with all settings.

**Usage:**

```bash
sce profile get
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "name": "Alex",
    "age": 32,
    "email": "alex@example.com",
    "max_hr": 190,
    "injury_history": "IT band 2024, resolved",
    "goal": {
      "type": "half_marathon",
      "target_date": "2026-09-15"
    },
    "constraints": {
      "available_run_days": ["tuesday", "thursday", "saturday", "sunday"],
      "preferred_run_days": ["saturday", "sunday"],
      "min_run_days_per_week": 2,
      "max_run_days_per_week": 4,
      "max_time_per_session_minutes": 90,
      "time_preference": "morning"
    },
    "running_priority": "equal",
    "conflict_policy": "ask_each_time",
    "preferences": {
      "detail_level": "moderate",
      "coaching_style": "supportive",
      "intensity_metric": "pace"
    }
  }
}
```

---

## sce profile set

Update profile fields. Only specified fields are updated; others remain unchanged.

**Available Fields:** (Same as `sce profile create` except `--name` is not required)

**Examples:**

```bash
# Update basic info
sce profile set --name "Alex" --age 33 --email "newemail@example.com"

# Update vital signs
sce profile set --max-hr 190 --resting-hr 55

# Update constraints
sce profile set --min-run-days 3 --max-run-days 4
sce profile set --available-days "tuesday,thursday,saturday,sunday"
sce profile set --time-preference morning

# Update priorities
sce profile set --run-priority primary
sce profile set --conflict-policy running_goal_wins

# Update preferences
sce profile set --detail-level detailed
sce profile set --coaching-style analytical
sce profile set --intensity-metric hr
```

---

## sce profile add-sport

Add a sport commitment to track multi-sport training load.

**Required:**
- `--sport` (string) - Sport name (e.g., climbing, yoga, cycling)

**Optional:**
- `--days` (comma-separated) - Days for this sport (omit for flexible scheduling)
- `--duration` (integer) - Typical session duration in minutes (default: 60)
- `--intensity` (string) - Intensity level: easy, moderate, hard, moderate_to_hard (default: moderate)
- `--flexible` / `--fixed` (boolean) - Flexible scheduling (True) or fixed commitment (False) (default: --fixed)
- `--notes` (string) - Optional notes about the commitment

**Examples:**

```bash
# Fixed commitment with specific days and duration/intensity (default --fixed)
sce profile add-sport \
  --sport climbing \
  --days tuesday,thursday \
  --duration 120 \
  --intensity moderate_to_hard \
  --notes "Bouldering gym 6-7pm"

# Flexible commitment - can reschedule if needed
sce profile add-sport \
  --sport yoga \
  --days monday \
  --intensity easy \
  --flexible

# Sport with flexible scheduling (no fixed days)
sce profile add-sport \
  --sport climbing \
  --intensity moderate_to_hard

# Sport with all defaults (flexible scheduling, 60min, moderate intensity)
sce profile add-sport --sport yoga
```

---

## sce profile remove-sport

Remove a sport commitment (case-insensitive).

**Usage:**

```bash
sce profile remove-sport --sport climbing
```

---

## sce profile list-sports

List all sport commitments.

**Usage:**

```bash
sce profile list-sports
```

**Returns:**

```json
{
  "ok": true,
  "message": "Found 2 sport commitment(s)",
  "data": {
    "sports": [
      {
        "sport": "climbing",
        "days": ["tuesday", "thursday"],
        "duration_minutes": 120,
        "intensity": "moderate_to_hard",
        "fixed": true,
        "notes": "Bouldering gym 6-7pm"
      },
      {
        "sport": "yoga",
        "days": ["monday"],
        "duration_minutes": 60,
        "intensity": "easy",
        "fixed": false,
        "notes": null
      }
    ]
  }
}
```

---

## sce profile edit

Open profile YAML in $EDITOR for direct editing (power-user feature).

**Environment Variables:**
- `EDITOR` - Your preferred editor (default: nano). Supports: nano, vim, emacs, code, etc.

**Usage:**

```bash
sce profile edit                    # Uses $EDITOR (default: nano)
EDITOR=vim sce profile edit         # Use vim
EDITOR=code sce profile edit        # Use VS Code
```

After editing, the profile is validated. If validation fails, you'll see the error message and can re-edit.

---

## sce profile analyze

Analyze synced activity history to suggest profile values.

**Usage:**

```bash
sce profile analyze
```

This analyzes your Strava activity history (last 120 days) to suggest:
- `max_hr` - Observed peak heart rate
- `weekly_km` - 4-week average volume
- `available_run_days` - Days you typically train
- `running_priority` - Based on sport distribution

---

**Navigation**: [Back to Index](index.md) | [Previous: Planning Commands](cli_planning.md) | [Next: VDOT Commands](cli_vdot.md)
