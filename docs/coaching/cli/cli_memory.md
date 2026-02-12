# Memory Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Store and retrieve durable athlete facts (injury history, preferences, insights, context).

**Commands in this category:**
- `resilio memory add` - Add a structured memory
- `resilio memory list` - List memories by type
- `resilio memory search` - Search memories by keyword

---

## resilio memory add

Add a structured memory about the athlete.

**Usage:**

```bash
resilio memory add --type TYPE --content "CONTENT" [--tags "tag1,tag2"] [--confidence LEVEL]
```

**Parameters:**
- `--type TYPE` - Memory type (required)
  - `INJURY_HISTORY` - Past or ongoing injuries
  - `TRAINING_RESPONSE` - How athlete responds to training stimuli
  - `PREFERENCE` - Training preferences
  - `CONTEXT` - Life context, schedule constraints
  - `INSIGHT` - Observed patterns detected by coach
- `--content "CONTENT"` - The fact to store (required)
- `--tags "tag1,tag2"` - Entity tags for filtering (optional)
- `--confidence LEVEL` - Confidence level: `high`, `medium`, `low` (optional, default: `medium`)

**Examples:**

```bash
# Injury history
resilio memory add --type INJURY_HISTORY \
  --content "Left knee pain after long runs >18km" \
  --tags "body:knee,trigger:long-run,threshold:18km" \
  --confidence high

# Training response
resilio memory add --type TRAINING_RESPONSE \
  --content "Responds well to quality over quantity - prefers 3 hard runs/week vs 5 moderate" \
  --confidence high

# Preference
resilio memory add --type PREFERENCE \
  --content "Prefers morning runs before 7am due to work schedule" \
  --confidence high

# Context
resilio memory add --type CONTEXT \
  --content "Work travel every other Thursday - needs flexible Thursday workouts" \
  --confidence high

# Insight (pattern detected by coach)
resilio memory add --type INSIGHT \
  --content "Consistently skips Tuesday runs - likely capacity issue" \
  --tags "pattern:adherence,day:tuesday" \
  --confidence medium
```

**Returns:**

```json
{
  "ok": true,
  "message": "Memory saved successfully",
  "data": {
    "memory": {
      "id": "mem_20260114_123456",
      "type": "injury_history",
      "content": "Left knee pain after long runs >18km",
      "confidence": "high",
      "tags": ["body:knee", "trigger:long-run", "threshold:18km"],
      "created_at": "2026-01-14T12:34:56Z",
      "occurrences": 1
    },
    "deduplication": {
      "is_duplicate": false,
      "merged_with": null
    }
  }
}
```

**Automatic deduplication:**

If similar memory exists, system will:
- Increment occurrence count
- Upgrade confidence if 3+ occurrences
- Merge tags

---

## resilio memory list

List memories by type.

**Usage:**

```bash
# List all memories
resilio memory list

# List specific type
resilio memory list --type INJURY_HISTORY
resilio memory list --type TRAINING_RESPONSE
resilio memory list --type PREFERENCE
resilio memory list --type CONTEXT
resilio memory list --type INSIGHT
```

**Parameters:**
- `--type TYPE` - Filter by memory type (optional)

**Returns:**

```json
{
  "ok": true,
  "data": {
    "memories": [
      {
        "id": "mem_20260114_123456",
        "type": "injury_history",
        "content": "Left knee pain after long runs >18km",
        "confidence": "high",
        "tags": ["body:knee", "trigger:long-run"],
        "created_at": "2026-01-14T12:34:56Z",
        "updated_at": "2026-01-14T12:34:56Z",
        "occurrences": 1
      }
    ],
    "count": 1,
    "filter": {
      "type": "injury_history"
    }
  }
}
```

**Common workflows:**

```bash
# Review all injury history before planning
resilio memory list --type INJURY_HISTORY

# Check athlete preferences for workout timing
resilio memory list --type PREFERENCE

# Review training response patterns
resilio memory list --type TRAINING_RESPONSE
```

---

## resilio memory search

Search memories by keyword.

**Usage:**

```bash
resilio memory search --query "KEYWORD"
```

**Parameters:**
- `--query "KEYWORD"` - Search term (required)
  - Searches in content field
  - Case-insensitive
  - Supports multiple keywords (OR match)

**Examples:**

```bash
# Find all ankle-related memories
resilio memory search --query "ankle"

# Find taper-related insights
resilio memory search --query "taper"

# Multiple keywords (OR match)
resilio memory search --query "tired fatigue"
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "matches": [
      {
        "id": "mem_20260114_123456",
        "type": "injury_history",
        "content": "Left knee pain after long runs >18km",
        "confidence": "high",
        "match_score": 0.95,
        "matched_terms": ["pain", "long"]
      }
    ],
    "query": "pain long",
    "count": 1
  }
}
```

---

## When to Capture Memories

**During first session:**
- Injury history (past and current)
- Known preferences (timing, frequency, volume)
- Schedule constraints (work, family, other sports)

**During weekly analysis:**
- Training responses (after 3+ observations)
- Adherence patterns (consistently skipped days/types)

**During risk assessment:**
- New injury signals (pain mentions in activity notes)
- Recovery patterns (how long to bounce back)

**Confidence guidelines:**
- **HIGH**: Explicit statement or 3+ occurrences
- **MEDIUM**: Single clear instance
- **LOW**: Inferred from ambiguous data

---

**Navigation**: [Back to Index](index.md) | [Previous: Activity Commands](cli_activity.md) | [Next: Analysis Commands](cli_analysis.md)
