# CLI Command Reference

> **Note**: This is a **skill-specific extract** containing only commands relevant to race preparation workflows. For comprehensive CLI documentation, see [CLI Command Index](../../../docs/coaching/cli/index.md).

Quick reference for race preparation commands.

---

## Taper Verification

```bash
sce risk taper-status --race-date [YYYY-MM-DD] --metrics metrics.json --recent-weeks recent_weeks.json
```

---

## Performance Prediction

```bash
# Predict equivalent times
sce vdot predict --race-type [5k|10k|half_marathon|marathon] --time [HH:MM:SS] --goal-race [race_type]

# Calculate VDOT from race result
sce vdot calculate --race-type [type] --time [HH:MM:SS]
```

---

## Environmental Adjustments

```bash
sce vdot adjust --pace [M:SS] --condition [heat|altitude|wind] --severity [value]
```

---

## Recovery Protocol

```bash
sce guardrails race-recovery --distance [5k|10k|half_marathon|marathon] --age [N] --effort [easy|moderate|hard]
```

---

## Status

```bash
# Current metrics
sce status

# Recent training summary
sce week
```
