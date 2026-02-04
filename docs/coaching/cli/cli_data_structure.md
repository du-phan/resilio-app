# Activity Data Storage Structure

## Overview

The Sports Coach Engine stores activity data in an organized monthly folder structure for efficient storage, fast incremental syncing, and clear organization. Understanding this structure is essential for monitoring sync progress and validating data integrity.

## Directory Structure

```
data/
└── activities/
    ├── 2025-01/
    │   ├── 2025-01-03_run_0830.yaml
    │   ├── 2025-01-05_run_1745.yaml
    │   ├── 2025-01-07_climb_1900.yaml
    │   └── ...
    ├── 2025-02/
    │   ├── 2025-02-01_run_0645.yaml
    │   ├── 2025-02-03_cycle_1530.yaml
    │   └── ...
    └── 2024-12/
        ├── 2024-12-28_run_0900.yaml
        └── ...
```

**Key principles**:
- Activities organized by **month** (`YYYY-MM/`)
- One YAML file per activity
- Filename encodes date, sport, and start time for fast parsing

## Filename Format

Each activity file follows this pattern:

```
YYYY-MM-DD_sport_HHmm.yaml
```

**Components**:
- `YYYY-MM-DD`: Activity date (ISO 8601 format)
- `sport`: Activity type (run, climb, cycle, swim, etc.) - lowercase with underscores
- `HHmm`: Start time in 24-hour format (e.g., 0830 = 8:30 AM, 1945 = 7:45 PM)

**Examples**:
- `2025-01-15_run_0830.yaml` → Run on Jan 15, 2025, starting at 8:30 AM
- `2025-02-03_climb_1900.yaml` → Climb on Feb 3, 2025, starting at 7:00 PM
- `2026-01-08_cycle_1745.yaml` → Cycle on Jan 8, 2026, starting at 5:45 PM

## Activity Count vs Directory Count

**CRITICAL**: When monitoring sync progress, count **files** (activities), not **directories** (months).

**Common mistake**:
```bash
# WRONG: Counts month folders, not activities
ls -1 data/activities/ | wc -l
# Returns: 11 (11 months)
```

**Correct approach**:
```bash
# CORRECT: Counts YAML files across all months
find data/activities -name "*.yaml" | wc -l
# Returns: 183 (183 activities)
```

**Why this matters**: A sync message saying "imported 183 activities" means 183 files across multiple monthly folders, NOT 183 folders.

## Smart Sync Detection

The filename structure enables **fast incremental sync** without reading file contents:

1. **Parse filename** → extract date (`YYYY-MM-DD`)
2. **Compare to sync window** → check if activity falls within requested range
3. **Skip existing files** → no redundant API calls

**Example**: `sce sync --since 7d`
- Only checks files dated within last 7 days
- Skips files with dates outside window
- Fetches only missing activities from Strava API

This is why subsequent syncs are fast: the system knows what it has by reading filenames.

## Sync Monitoring Best Practices

### During First Sync (Greedy Sync)

The initial `sce sync` fetches up to 365 days of history. Progress messages show:
- **"Fetching recent activities..."** → API requests in progress
- **"Imported X activities"** → Final count of YAML files created

**To monitor in real-time** (separate terminal):
```bash
watch -n 2 'find data/activities -name "*.yaml" | wc -l'
```

### After Sync Completion

**Verify activity count**:
```bash
find data/activities -name "*.yaml" | wc -l
```

**Check date range** (earliest and latest):
```bash
find data/activities -name "*.yaml" | sort | head -1
find data/activities -name "*.yaml" | sort | tail -1
```

**List activities by month**:
```bash
for dir in data/activities/*/; do
  count=$(find "$dir" -name "*.yaml" | wc -l)
  echo "$(basename $dir): $count activities"
done
```

## Validation Checklist

After sync completes, verify:

1. ✅ **Activity count matches sync message**
   ```bash
   find data/activities -name "*.yaml" | wc -l
   ```

2. ✅ **Date range covers expected period**
   ```bash
   # First activity
   find data/activities -name "*.yaml" | sort | head -1
   # Last activity
   find data/activities -name "*.yaml" | sort | tail -1
   ```

3. ✅ **No empty month folders**
   ```bash
   # Should return nothing
   find data/activities -type d -empty
   ```

4. ✅ **Monthly distribution looks reasonable**
   ```bash
   for dir in data/activities/*/; do
     count=$(find "$dir" -name "*.yaml" | wc -l)
     echo "$(basename $dir): $count activities"
   done | sort
   ```

## Why Monthly Folders?

**Benefits**:
- **Fast directory listings**: Listing 30 files vs 365 files
- **Clear organization**: Human-readable month-based browsing
- **Efficient sync**: Only check relevant month folders for date ranges
- **Manageable backups**: Archive old months separately if needed

**Trade-offs**:
- Must traverse multiple directories for full activity count
- Requires `find` instead of simple `ls` for cross-month operations

The performance benefits for sync operations outweigh the slightly more complex counting pattern.

## Related Commands

- [`sce sync`](cli_sync.md) - Smart sync and activity import
- [`sce activity list`](cli_activity.md) - List activities with notes
- [`sce profile analyze`](cli_profile.md) - Analyze activity patterns
- [`sce status`](cli_metrics.md) - Current metrics derived from activities

---

**Quick Reference**: Always count activities with `find data/activities -name "*.yaml" | wc -l`, never with `ls data/activities/ | wc -l`.
