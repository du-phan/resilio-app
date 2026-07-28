# Data authority

Intervals.icu is the external activity and calendar exchange. Resilio owns the
canonical local activity history and computes load, fitness, fatigue, form,
readiness, profile analysis, weekly summaries, and coaching decisions locally.

Supported completed-activity sources include Garmin, Wahoo, uploads, and
manual entries. Exact external sport labels are retained as metadata.
RockClimbing and Bouldering both normalize to `climb`; unknown sport labels
are quarantined instead of silently becoming `other`.

Use:

```bash
resilio sync
resilio profile analyze
resilio metrics recompute
```

Always report the actual profile-analysis date span. Hidden external rows do
not replace historical local data. Externally deleted linked activities remain
as tombstoned history and are excluded from active calculations after review.
