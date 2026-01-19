# Data Management Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Initialize data directories and import activities from Strava.

**Commands in this category:**
- `sce init` - Initialize data directories and configuration
- `sce sync` - Import activities from Strava

---

## sce init

Initialize data directories and configuration.

**Usage:**

```bash
sce init
```

**Returns:**

```json
{
  "ok": true,
  "data": {
    "created_paths": ["data/athlete", "data/activities", ...],
    "skipped_paths": ["config/"],
    "next_steps": "Run 'sce auth url' to connect Strava"
  }
}
```

**What it does:**

- Creates `data/` directory structure
- Validates `config/settings.yaml` exists
- Checks for `config/secrets.local.yaml` (warns if missing)

**First-time setup:**

```bash
# 1. Initialize directories
sce init

# 2. Authenticate with Strava
sce auth url
# Follow OAuth flow...

# 3. Import activities
sce sync
```

---

## sce sync

Import activities from Strava.

**Usage:**

```bash
# Sync all activities (12+ weeks recommended for CTL baseline)
sce sync

# Sync last 14 days only
sce sync --since 14d

# Sync specific date range
sce sync --since 2026-01-01
```

**Parameters:**
- `--since PERIOD` - Sync activities since this period (optional)
  - Format: `14d` (days), `2026-01-01` (date)
  - Default: Last 120 days

**Returns:**

```json
{
  "ok": true,
  "data": {
    "activities_imported": 45,
    "date_range": { "start": "2025-10-15", "end": "2026-01-14" },
    "total_load_au": 12450,
    "metrics_updated": true,
    "ctl_baseline": 44.2
  }
}
```

**What it does:**

1. Fetches activities from Strava API
2. Normalizes sport types and units (M6)
3. Computes RPE from HR/pace/notes (M7)
4. Calculates systemic + lower-body loads (M8)
5. Recalculates daily/weekly metrics (M9)
6. Updates athlete profile with discovered data

**Rate limits:**

- Strava: 100 requests / 15 minutes, 1000 requests / day
- If hit, exit code 4, retry after indicated time

**Common workflow:**

```bash
# Initial sync (12 weeks minimum for CTL baseline)
sce sync

# Daily refresh (last 7 days)
sce sync --since 7d

# Check if sync succeeded
if [ $? -eq 0 ]; then
  echo "Activities synced successfully"
  sce status  # View updated metrics
fi
```

**CTL baseline requirements:**

- **Minimum**: 12 weeks (84 days) for 42-day CTL calculation
- **Recommended**: Full season history for accurate patterns
- Without sufficient history, CTL starts at 0 and builds from recent data

---

**Navigation**: [Back to Index](index.md) | [Previous: Auth Commands](cli_auth.md) | [Next: Metrics Commands](cli_metrics.md)
