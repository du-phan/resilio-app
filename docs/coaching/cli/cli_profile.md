# Profile Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Commands for managing athlete profiles: basic info, run constraints, and multi-sport commitments.

**Commands in this category:**
- `sce profile create`
- `sce profile get`
- `sce profile set`
- `sce profile add-sport`
- `sce profile remove-sport`
- `sce profile pause-sport`
- `sce profile resume-sport`
- `sce profile list-sports`
- `sce profile edit`
- `sce profile analyze`

---

## sce profile create

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
sce profile create --name "Alex"
sce profile create --name "Alex" --age 32 --max-hr 190 --unavailable-days "tuesday,thursday"
```

---

## sce profile get

Get athlete profile with all settings.

```bash
sce profile get
```

---

## sce profile set

Update profile fields. Only specified fields are updated.

**Examples:**

```bash
sce profile set --max-hr 190 --resting-hr 55
sce profile set --min-run-days 3 --max-run-days 4 --unavailable-days "tuesday,thursday"
sce profile set --run-priority primary --conflict-policy running_goal_wins
sce profile set --detail-level detailed --coaching-style analytical --intensity-metric hr
```

---

## sce profile add-sport

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
sce profile add-sport --sport climbing --frequency 3 --unavailable-days tuesday,thursday --duration 120 --intensity moderate_to_hard

# Frequency only (fully flexible)
sce profile add-sport --sport yoga --frequency 2 --duration 60 --intensity easy
```

---

## sce profile remove-sport

Remove a sport commitment.

```bash
sce profile remove-sport --sport climbing
```

---

## sce profile pause-sport

Temporarily pause a sport commitment (keeps it in profile history).

**Required:**
- `--sport` - Sport name
- `--reason` - `focus_running|injury|illness|off_season|other`

**Optional:**
- `--paused-at` - Date `YYYY-MM-DD` (default: today)

**Examples:**

```bash
sce profile pause-sport --sport climbing --reason focus_running
sce profile pause-sport --sport cycling --reason injury --paused-at 2026-02-09
```

---

## sce profile resume-sport

Resume a paused sport commitment.

```bash
sce profile resume-sport --sport climbing
```

---

## sce profile list-sports

List all sport commitments with scheduling and pause state.

```bash
sce profile list-sports
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

## sce profile edit

Open profile YAML in `$EDITOR`.

```bash
sce profile edit
EDITOR=vim sce profile edit
```

---

## sce profile analyze

Analyze synced activities and suggest profile setup values.

```bash
sce profile analyze
```

Typical outputs include:
- `max_hr_observed`
- `weekly_run_km_recent_4wk`
- `suggested_run_days`
- `suggested_running_priority`
- `sport_distribution`

---

**Navigation**: [Back to Index](index.md) | [Previous: Planning Commands](cli_planning.md) | [Next: VDOT Commands](cli_vdot.md)
