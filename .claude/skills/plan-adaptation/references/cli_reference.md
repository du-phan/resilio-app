# CLI Command Reference

> **Note**: This is a **skill-specific extract** containing only commands relevant to plan adaptation workflows. For comprehensive CLI documentation, see [CLI Command Index](../../../docs/coaching/cli/index.md).

Quick reference for plan adaptation commands.

---

## Guardrails

```bash
# Illness recovery protocols
sce guardrails illness-recovery --severity [minor|moderate|severe] --days-missed [N]

# Break return protocols (injury/time off)
sce guardrails break-return --days [N] --ctl [X] --cross-training [none|light|moderate|high]

# Race recovery protocols
sce guardrails race-recovery --distance [type] --age [N] --effort [easy|moderate|hard]

# Volume progression check
sce guardrails progression --previous [X] --current [Y]
```

---

## Plan Updates

```bash
# Single week update (JSON: single week object)
sce plan update-week --week [N] --from-json [file.json]

# Partial replan from week N onward (JSON: weeks array)
sce plan update-from --week [N] --from-json [file.json]

# View current plan (entire plan)
sce plan show

# Get specific week(s) from plan (efficient, smaller output)
sce plan week                    # Current week
sce plan week --next             # Next week
sce plan week --week [N]         # Specific week
sce plan week --date YYYY-MM-DD  # Week containing date
sce plan week --week [N] --count 2  # Multiple consecutive weeks
```

---

## Validation

```bash
# Forecast injury risk for upcoming weeks
sce risk forecast --weeks [N] --metrics metrics.json --plan plan.json

# Assess goal feasibility
sce validation assess-goal --goal-type [type] --goal-time [time] --goal-date [date] --current-vdot [vdot] --current-ctl [ctl]
```

---

## Status

```bash
# Current metrics (CTL/ATL/TSB/ACWR/readiness)
sce status

# Recent training pattern
sce week
```
