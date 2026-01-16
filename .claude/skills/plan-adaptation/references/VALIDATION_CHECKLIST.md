# Validation Checklist

Verify these criteria before saving any adapted plan.

---

## Pre-Save Validation

**Before saving adapted plan**, verify:

### 1. ACWR Safety
Projected ACWR stays <1.3 after return

```bash
sce risk forecast --weeks 3 --metrics metrics.json --plan adapted_plan.json
```

### 2. Volume Progression
No week exceeds +10% increase

```bash
sce guardrails progression --previous [X] --current [Y]
```

### 3. Recovery Protocol
Adequate easy-only period per guardrails

- Check guardrails output was followed
- Verify no quality workouts during recovery period

### 4. Goal Feasibility
Still realistic given new CTL trajectory

```bash
sce validation assess-goal --goal-type [type] --goal-time [time] --goal-date [date] --current-vdot [vdot] --current-ctl [ctl]
```

### 5. 80/20 Distribution
Plan maintains intensity balance

- Use `sce analysis intensity` after 2-3 weeks back
- Target: 80% easy (RPE 3-5), 20% hard (RPE 7-9)

### 6. Multi-Sport Conflicts
Adjusted schedule respects other sports

- Review with athlete if climbing/cycling days affected
- Verify no quality run + hard other sport on consecutive days
- Check lower-body load separation (48h for quality runs)

---

## Success Criteria

✓ All validation checks passed
✓ Athlete reviewed and approved adapted plan
✓ JSON structure correct (week object vs weeks array)
✓ Dates and week numbers align properly
✓ Workout IDs follow convention (wN_day_type)
