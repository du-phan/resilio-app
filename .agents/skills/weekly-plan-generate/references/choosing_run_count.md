# Choosing Optimal Run Count Per Week

## Problem

`max_run_days` in profile is an upper limit, not a target. When weekly volume is low, using max_run_days results in very short runs that feel unsatisfying.

## Solution

**Before creating workout pattern JSON**, consult the system for optimal run count:

```bash
poetry run resilio plan suggest-run-count --volume 23 --max-runs 4 --phase base
```

## Example Output

```json
{
  "recommended_runs": 3,
  "rationale": "23km spread across 4 runs averages 5.75km per run. With long run at 10km, easy runs would be 4.3km each (below 5km minimum). Recommend 3 runs: 2×6km easy + 11km long.",
  "distribution_preview": {
    "with_4_runs": {
      "easy": [4.0, 4.5, 4.0],
      "long": 10.5,
      "concerns": ["Easy runs below 5.0km minimum"]
    },
    "with_3_runs": {
      "easy": [6.0, 6.0],
      "long": 11.0,
      "concerns": []
    }
  },
  "minimum_volume_for_max_runs": 23.0,
  "comfortable_volume_for_max_runs": 28.0
}
```

## Decision Heuristics (Built Into Command)

1. **Easy run minimum**: 5km (or 80% of athlete's typical)
2. **Long run minimum**: 8km (or 80% of athlete's typical)
3. **Long run percentage**: 40-50% of weekly volume (varies by phase)
4. **Sweet spot**: Easy runs should be 6-7km for comfortable sessions

## Workflow Integration

### When Creating Monthly Plan

```bash
# For each week, determine optimal run count:
poetry run resilio plan suggest-run-count --volume 23 --max-runs 4 --phase base
# Output: Recommend 3 runs

poetry run resilio plan suggest-run-count --volume 30 --max-runs 4 --phase base
# Output: Recommend 4 runs

poetry run resilio plan suggest-run-count --volume 21 --max-runs 4 --phase recovery
# Output: Recommend 3 runs (recovery weeks use fewer days)
```

### Then Create Workout Pattern

Use the recommended run count in your pattern JSON:

```json
{
  "week_number": 1,
  "target_volume_km": 23.0,
  "workout_pattern": {
    "run_days": [0, 2, 6],
    "long_run_day": 6,
    "long_run_pct": 0.48,
    "easy_run_paces": "6:30-6:50",
    "long_run_pace": "6:30-6:50"
  }
}
```

## Edge Cases

### Very Low Volume (<18km)
- Recommend 2 runs minimum (1 easy + 1 long)
- Example: 15km → 7km easy + 8km long

### Very High Volume (>45km)
- Can use max_runs safely
- Example: 48km with 5 runs → 4×8km easy + 16km long

### Recovery Weeks
- Typically reduce both volume AND frequency
- Example: 21km recovery → 3 runs instead of 4

## Formula Reference

**Minimum weekly volume for N runs**:
```
min_km = (N - 1) × easy_min + long_min
```

Examples:
- 2 runs: (2-1) × 5 + 8 = 13km minimum
- 3 runs: (3-1) × 5 + 8 = 18km minimum
- 4 runs: (4-1) × 5 + 8 = 23km minimum
- 5 runs: (5-1) × 5 + 8 = 28km minimum

**Comfortable weekly volume for N runs** (add 1km buffer per run):
```
comfortable_km = min_km + N
```

## Best Practices

1. **Always consult before creating pattern** - Don't guess run count
2. **Trust the recommendation** - It considers minimums, phase, athlete history
3. **Override cautiously** - If overriding, document rationale in plan notes
4. **Progressive increase** - Can increase run count as volume grows across weeks
