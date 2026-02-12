# CLI: Sync Command

## Overview

The `sce sync` command imports activities from Strava and updates all training metrics (CTL, ATL, TSB, ACWR, readiness).

**Smart sync detection** (default):
- **First-time sync**: Fetches 365 days to establish CTL baseline
- **Subsequent syncs**: Incremental (only new activities since last sync)

**Explicit override** with `--since` flag for specific windows.

---

## Usage

### Automatic Smart Sync (Recommended)

```bash
sce sync              # Smart detection
```

**How it works:**
- Scans existing activity files
- If no activities exist → 365 days (first-time)
- If activities exist → incremental sync from latest activity date + 1-day buffer
- Buffer catches activities uploaded late to Strava

**Benefits:**
- Fast weekly syncs (5-10 seconds vs 20-30 seconds)
- Automatic - no manual window calculation needed
- Truly incremental - works whether it's been 1 day or 60 days since last sync

### Sync Status (Observability)

```bash
sce sync --status
```

Returns a JSON status snapshot without running sync:
- `running`: Whether an active non-stale sync lock exists
- `lock`: PID/timing/staleness for `config/.workflow_lock`
- `progress`: Last heartbeat from `config/.sync_progress.json`
- `resume_state`: Persisted backfill cursor state
- `activity_files_count`: Current number of synced activity files

`resume_state` is sourced from `data/athlete/training_history.yaml` and `progress` is sourced from `config/.sync_progress.json`.

---

## Explicit Sync Windows

Override smart detection with `--since` flag:

### Relative Windows

```bash
sce sync --since 7d   # Last 7 days (weekly analysis)
sce sync --since 14d  # Last 2 weeks
sce sync --since 30d  # Last month
sce sync --since 365d # Full year (explicit)
```

### Absolute Dates

```bash
sce sync --since 2026-01-01              # Since specific date
sce sync --since 2026-01-01T00:00:00     # With time (ISO 8601)
```

---

## Common Workflows

### Weekly Coaching Session

```bash
sce auth status
sce sync              # Smart sync (incremental, ~5-10 seconds)
sce status
sce week
```

**Optional explicit recent sync:**
```bash
sce sync --since 7d   # Force last week only (faster for weekly analysis)
```

### First-Time Setup

```bash
sce sync              # Automatic 365-day sync
```

Expects rate limit hit (~100 activities). If you want full year history:
```bash
# Wait 15 minutes for rate limit reset
sce sync              # Resumes automatically from where it left off
```

### After Long Break (30-60 days)

```bash
sce sync              # Smart sync catches up automatically
```

No manual calculation needed - automatically syncs all missing days.

---

## Rate Limit Handling (Expected During First Sync)

**Strava API limits**:
- **15-minute**: 100 requests (resets at :00, :15, :30, :45 past hour)
- **Daily**: 1,000 requests (resets midnight UTC)
- **Source**: [Strava Rate Limits Documentation](https://developers.strava.com/docs/rate-limits/)

**First-time sync (365 days)**: WILL hit rate limits for most athletes with regular training.

**Why**: Fetching 365 days for an athlete with 3-4 activities/week requires ~180 activities × 2 API requests = 360+ requests. This exceeds the 15-minute limit (100 requests) multiple times.

**This is normal, expected behavior** - not an error. The sync system is designed to handle this gracefully.

**When rate limit hit:**
1. All fetched data is saved successfully (no data loss)
2. Sync pauses and displays rate limit message
3. Wait 15 minutes for limit reset (or longer for daily limit)
4. Run `sce sync` again - automatically resumes from where it stopped
5. Repeat as needed until full history is synced

**For very active athletes** (7+ activities/week over 365 days):
- May need multiple 15-minute waits
- In rare cases, could approach daily limit (1,000 requests)
- Each resume automatically continues from last successful fetch

**Success message includes tip:**
```
Synced 95 new activities from Strava.

Strava rate limit hit. Data saved successfully.
Wait 15 minutes and run 'sce sync' again to continue.
```

---

## First-Time Sync Expectations

**Typical scenarios**:

| Athlete Activity Level | Activities/Year | Expected Rate Limits |
|------------------------|-----------------|----------------------|
| Light (1-2/week) | ~75 | Likely none or 1 wait |
| Moderate (3-4/week) | ~180 | 2-3 waits (15 min each) |
| Active (5-6/week) | ~280 | 3-4 waits (15 min each) |
| Very Active (7+/week) | ~365+ | 4-5 waits, may approach daily limit |

**Total time estimate**: 15-60 minutes for first sync (including wait periods), depending on activity level.

**Recommendation**: Start the first sync, let it run, then return after 15-30 minutes to resume.

---

## Technical Details

### Smart Sync Detection Logic

1. **Scan activity files**: `data/activities/**/*.yaml`
2. **Extract dates from filenames**: `YYYY-MM-DD_sport_duration.yaml`
3. **Find latest activity date**
4. **Calculate lookback**:
   - No activities → 365 days
   - Activities exist → `max(days_since_latest + 1, 1)`
5. **1-day buffer**: Catches late-uploaded activities

**Performance:**
- Filename parsing (not file reading) → ~50-100ms for 1000 files
- No impact on sync performance

### Idempotency

Safe to run multiple times:
- Duplicate activities are skipped (by ID)
- Metrics are recalculated from scratch
- No data loss on repeated syncs

---

## Lap Data Fetching (Adaptive Strategy)

**Lap data fetching adapts to your sync pattern:**

**Incremental sync** (regular usage):
- Fetches lap data for ALL new running activities
- No age filter applied (new activities are always recent)
- Perfect for weekly/daily sync habits

**Historical sync** (first-time or large backfill):
- Fetches lap data for running activities from last 60 days only
- Optimizes rate limit usage for large imports
- Prioritizes coaching-critical data (current training block)

**Why adaptive?**
- **Best UX**: Regular users get full lap data with zero overhead
- **Rate limit safety**: First-time sync doesn't exhaust API quota
- **Coaching-aligned**: Focuses on data that drives training decisions

**What's included:**

| Sync Type | Lap Data Coverage |
|-----------|-------------------|
| Incremental (<90 days) | ✓ All running activities |
| Historical (>90 days) | ✓ Last 60 days only |

**Coaching impact:**
- Weekly analysis: ✓ Full lap data always available
- Pattern detection: ✓ 8 weeks of lap history
- Historical archive: ⚠ Lap data limited to 60 days on first sync

**Configuration:**
Override in `config/settings.local.yaml`:
```yaml
strava:
  lap_fetch_incremental_days: 999999  # Fetch all laps (incremental sync)
  lap_fetch_historical_days: 90       # Extend historical window to 3 months
```

---

## Examples

### Smart sync (first-time)
```bash
$ sce sync
First-time sync: fetching last 365 days to establish training baseline...
Synced 127 new activities from Strava.
```

### Smart sync (incremental, 2 days since last sync)
```bash
$ sce sync
Incremental sync: fetching activities since 2026-01-31 (3 days)...
Synced 2 new activities from Strava.
```

### Explicit weekly window
```bash
$ sce sync --since 7d
Syncing activities since 2026-01-26...
Synced 5 new activities from Strava.
```

### Rate limit handling
```bash
$ sce sync
First-time sync: fetching last 365 days to establish training baseline...
Synced 95 new activities from Strava.

Strava rate limit hit. Data saved successfully.
Wait 15 minutes and run 'sce sync' again to continue.

# 15 minutes later...
$ sce sync
Incremental sync: fetching activities since 2025-06-01 (245 days)...
Synced 32 new activities from Strava.

# Check runtime status at any time (another terminal)
$ sce sync --status
```

---

## Related Commands

- `sce auth status` - Check Strava authentication
- `sce status` - View current metrics (CTL/ATL/TSB)
- `sce week` - View weekly summary
- `sce profile analyze` - Analyze synced activity patterns

---

## See Also

- [CLI Index](index.md)
- [Core Concepts](core_concepts.md)
- [Authentication](cli_auth.md)
