# Profile Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Commands for managing athlete profiles: basic info, run constraints, and multi-sport commitments.

**Commands in this category:**
- `resilio profile create`
- `resilio profile get`
- `resilio profile set`
- `resilio profile add-sport`
- `resilio profile remove-sport`
- `resilio profile pause-sport`
- `resilio profile resume-sport`
- `resilio profile list-sports`
- `resilio profile edit`
- `resilio profile analyze`

---

## resilio profile create

Create a new athlete profile.

**Required:**
- `--name` - Athlete name

**Optional:**
- `--age` - Age in years
- `--max-hr` - Maximum heart rate
- `--resting-hr` - Resting heart rate
- `--run-priority` - `primary|secondary|equal` (default: `equal`)
- `--primary-sport` - Primary sport name if not running
- `--conflict-policy` - `primary_sport_wins|running_goal_wins|ask_each_time` (default: `ask_each_time`)
- `--min-run-days` - Minimum run days/week (default: `2`)
- `--max-run-days` - Maximum run days/week (default: `4`)
- `--unavailable-days` - Days you cannot run (comma-separated)
- `--detail-level` - `brief|moderate|detailed`
- `--coaching-style` - `supportive|direct|analytical`
- `--intensity-metric` - `pace|hr|rpe`

**Examples:**

```bash
resilio profile create --name "Alex"
resilio profile create --name "Alex" --age 32 --max-hr 190 --unavailable-days "tuesday,thursday"
```

---

## resilio profile get

Get athlete profile with all settings.

```bash
resilio profile get
```

---

## resilio profile set

Update profile fields. Only specified fields are updated.

**Examples:**

```bash
resilio profile set --max-hr 190 --resting-hr 55
resilio profile set --min-run-days 3 --max-run-days 4 --unavailable-days "tuesday,thursday"
resilio profile set --run-priority primary --conflict-policy running_goal_wins
resilio profile set --detail-level detailed --coaching-style analytical --intensity-metric hr
```

---

## resilio profile add-sport

Add a non-running sport commitment.

**Required:**
- `--sport` - Sport name
- `--frequency` - Sessions/week (`1-7`)

**Optional:**
- `--unavailable-days` - Days you cannot do this sport (comma-separated)
- `--duration` - Typical session duration in minutes (default: `60`)
- `--intensity` - `easy|moderate|hard|moderate_to_hard` (default: `moderate`)
- `--notes` - Optional notes

**Examples:**

```bash
# Frequency with unavailable days
resilio profile add-sport --sport climbing --frequency 3 --unavailable-days tuesday,thursday --duration 120 --intensity moderate_to_hard

# Frequency only (fully flexible)
resilio profile add-sport --sport yoga --frequency 2 --duration 60 --intensity easy
```

---

## resilio profile remove-sport

Remove a sport commitment.

```bash
resilio profile remove-sport --sport climbing
```

---

## resilio profile pause-sport

Temporarily pause a sport commitment (keeps it in profile history).

**Required:**
- `--sport` - Sport name
- `--reason` - `focus_running|injury|illness|off_season|other`

**Optional:**
- `--paused-at` - Date `YYYY-MM-DD` (default: today)

**Examples:**

```bash
resilio profile pause-sport --sport climbing --reason focus_running
resilio profile pause-sport --sport cycling --reason injury --paused-at 2026-02-09
```

---

## resilio profile resume-sport

Resume a paused sport commitment.

```bash
resilio profile resume-sport --sport climbing
```

---

## resilio profile list-sports

List all sport commitments with scheduling and pause state.

```bash
resilio profile list-sports
```

Returns each sport with fields such as:
- `sport`
- `unavailable_days`
- `frequency_per_week`
- `duration_minutes`
- `intensity`
- `active`
- `pause_reason`
- `paused_at`
- `notes`

---

## resilio profile edit

Open profile YAML in `$EDITOR`.

```bash
resilio profile edit
EDITOR=vim resilio profile edit
```

---

## resilio profile analyze

Analyze synced activities and suggest profile setup values.

```bash
resilio profile analyze
```

Typical outputs include:
- `max_hr_observed`
- `weekly_run_km_recent_4wk`
- `suggested_running_priority`
- `sport_distribution`

---

**Navigation**: [Back to Index](index.md) | [Previous: Planning Commands](cli_planning.md) | [Next: VDOT Commands](cli_vdot.md)
