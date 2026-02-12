# Date Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Computational date utilities for training plans. Training weeks always run Monday-Sunday. Never do mental date math; always use these commands.

**Commands in this category:**
- `resilio dates today` - Current date and next Monday
- `resilio dates next-monday` - Calculate the next Monday from a given date
- `resilio dates week-boundaries` - Get Monday-Sunday range for a week
- `resilio dates validate` - Verify a date is a specific weekday

---

## resilio dates today

Get today's date with day name and next Monday.

**Usage:**

```bash
resilio dates today
```

**Returns:**
- `date` (YYYY-MM-DD)
- `day_name` (Monday, Tuesday, ...)
- `day_number` (0=Monday, 6=Sunday)
- `next_monday`
- `is_monday`

---

## resilio dates next-monday

Get the next Monday from a given date (or today by default).

**Usage:**

```bash
resilio dates next-monday
resilio dates next-monday --from-date 2026-01-17
```

**Returns:**
- `date` (next Monday)
- `day_name` (always Monday)
- `formatted` (human-readable)
- `days_ahead`

---

## resilio dates week-boundaries

Get Monday-Sunday boundaries for a week.

**Usage:**

```bash
resilio dates week-boundaries --start 2026-01-19
```

**Returns:**
- `start` (Monday)
- `end` (Sunday)
- `formatted` (e.g., Mon Jan 19 - Sun Jan 25)
- `duration_days` (always 7)

---

## resilio dates validate

Validate that a date is a specific weekday.

**Usage:**

```bash
resilio dates validate --date 2026-01-19 --must-be monday
resilio dates validate --date 2026-01-25 --must-be sunday
```

**Returns:**
- `valid` (true/false)
- `date`
- `day_name` (actual)
- `required_day`

---

## Weekday Numbering

The system uses Python's `date.weekday()` convention:

- 0 = Monday
- 1 = Tuesday
- 2 = Wednesday
- 3 = Thursday
- 4 = Friday
- 5 = Saturday
- 6 = Sunday

---

**Navigation**: [Back to Index](index.md)
