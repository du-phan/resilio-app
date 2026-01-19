# Activity Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Commands to list and search activities with their notes (description, private_note). These tools surface raw data for the AI coach to interpret.

**Commands in this category:**
- `sce activity list` - List activities in a date range with their notes
- `sce activity search` - Search activities by text content in notes

---

## sce activity list

List activities in a date range with their notes.

**Usage:**

```bash
# List activities from last 30 days (default)
sce activity list

# List activities from last 60 days
sce activity list --since 60d

# Filter by sport type
sce activity list --since 30d --sport run

# Only activities with notes
sce activity list --since 14d --has-notes

# Specific date range
sce activity list --since 2026-01-01
```

**Parameters:**

- `--since` (optional): Time period - '30d' for 30 days, or 'YYYY-MM-DD' (default: 30d)
- `--sport` (optional): Filter by sport type (e.g., 'run', 'climb', 'cycle', 'yoga')
- `--has-notes` (optional): Only return activities with description or private_note

**Returns:**

```json
{
  "ok": true,
  "data": {
    "activities": [
      {
        "id": "strava_17050189802",
        "date": "2026-01-14",
        "sport": "run",
        "name": "Evening Run",
        "duration_minutes": 35,
        "distance_km": 5.27,
        "average_hr": 157.1,
        "description": "",
        "private_note": "30 minutes @ 6:00 min/km. At minute 10, the right ankle started to feel a bit weird..."
      }
    ],
    "count": 15,
    "date_range": {
      "start": "2025-12-17",
      "end": "2026-01-17"
    },
    "filters": {
      "sport": null,
      "has_notes": false
    }
  }
}
```

**Use cases:**

- Review recent training notes for patterns
- Find activities with injury/wellness mentions
- Get context for coaching decisions

---

## sce activity search

Search activities by text content in notes.

**Usage:**

```bash
# Search for ankle mentions
sce activity search --query "ankle"

# Multiple keywords (OR match)
sce activity search --query "tired fatigue sore"

# Filter by sport and time period
sce activity search --query "pain" --sport run --since 60d
```

**Parameters:**

- `--query` (required): Keywords to search (space-separated = OR match)
- `--since` (optional): Time period (default: 30d)
- `--sport` (optional): Filter by sport type

**Returns:**

```json
{
  "ok": true,
  "data": {
    "matches": [
      {
        "id": "strava_17050189802",
        "date": "2026-01-14",
        "sport": "run",
        "name": "Evening Run",
        "duration_minutes": 35,
        "matched_field": "private_note",
        "matched_keywords": ["ankle"],
        "matched_text": "...right ankle started to feel a bit weird and not comfortable...",
        "full_note": "30 minutes @ 6:00 min/km. At minute 10, the right ankle..."
      }
    ],
    "query": "ankle",
    "total_matches": 4,
    "activities_searched": 45,
    "date_range": {
      "start": "2025-12-17",
      "end": "2026-01-17"
    },
    "filters": {
      "sport": null
    }
  }
}
```

**Use cases:**

- Find injury/pain mentions across activities
- Search for fatigue/wellness signals
- Identify recurring patterns
- Gather evidence for memory creation

---

**Navigation**: [Back to Index](index.md) | [Next: Metrics Commands](cli_metrics.md)
