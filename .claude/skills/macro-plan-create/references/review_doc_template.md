# Macro Plan Review Document Template

This template defines the structure for macro plan review documents presented to athletes.

## Document Structure

### Header
- Goal: {race_type} on {race_date} | Target: {target_time} ({pace_per_km})
- Training Cycle: {start_date} (Monday) → {end_date} (Sunday) | {total_weeks} weeks
- Baseline VDOT: {vdot_value} | Starting CTL: {ctl_value}

### Phase Overview Table
| Phase | Weeks | Purpose |
|-------|-------|---------|
| Base | {weeks} | Build aerobic foundation |
| Build | {weeks} | Develop lactate threshold, race fitness |
| Peak | {weeks} | Maximum load, race sharpening |
| Taper | {weeks} | Reduce fatigue, maintain fitness |

### Volume Progression Table (All Weeks)
Show complete week-by-week structure:

| Week | Dates | Phase | Run (km) | Systemic (au)* | Recovery | Notes |
|------|-------|-------|----------|----------------|----------|-------|
| 1 | ... | Base | 18.0 | 85.0 | No | Starting volume |
| 2 | ... | Base | 19.5 | 92.0 | No | 8% increase |
| ... | ... | ... | ... | ... | ... | ... |

*For multi-sport: includes all sports. For single-sport: 0.0 (calculated from running only).

### Multi-Sport Integration (if applicable)
**Profile**: {other_sports} | Running priority: {PRIMARY/EQUAL/SECONDARY} | Run days: {N}/week

**Integration Notes**:
- Running volume fits {N}-day schedule and {priority} priority
- Systemic load accounts for {other_sports} (~{estimated_au} au/week)
- Quality runs scheduled on non-{sport} days to avoid fatigue stacking
- Recovery weeks reduce BOTH running and total load

### Coaching Rationale (Why This Structure)
- **Starting volume**: {start_km}km based on CTL {ctl_value}, recent volume. Conservative to prevent injury.
- **Progression**: ~{pct}% weekly increase (Pfitzinger's 5-10% guideline)
- **Recovery**: Every {N} weeks at ~70% of prior week. Allows adaptation, prevents overtraining.
- **Peak volume**: {peak_km}km in week {N}. Appropriate for VDOT {vdot_value} and {goal_type} goal.
- **Taper**: {N}-week taper reduces volume {pct}% to arrive fresh while maintaining fitness.

### Training Pace Zones (VDOT {vdot_value})
| Zone | Pace (per km) | RPE | Usage |
|------|---------------|-----|-------|
| Easy | {min}-{max} | 5-6 | 80% of volume, recovery, long runs |
| Tempo | {min}-{max} | 7-8 | Quality sessions (20-40 min) |
| Interval | {min}-{max} | 9 | Quality sessions (3-5 min reps) |
| Race Pace | {pace} | 8-9 | Race-specific workouts |

### What Happens Next
1. Review: Check volume progression, phase timing, conflicts
2. Approval: `sce approvals approve-macro` if this works
3. Weekly design: Week 1 with exact workouts (days, types, paces)
4. Adaptation: Weekly review of metrics (CTL, ACWR, readiness), adjust as needed

Storage: `/tmp/macro_plan_review_{YYYY_MM_DD}.md` (temporary). After approval → `data/plans/current_plan_review.md` (permanent).

### Approval Prompt
Does this {total_weeks}-week structure work for you? Any concerns:
- Volume progression (too aggressive/conservative?)
- Phase timing (conflicts with schedule?)
- Peak volume ({peak_km}km manageable?)
- Multi-sport balance (if applicable—running vs {other_sports} load?)

If you'd like adjustments, let me know and I'll regenerate with your constraints.

**Handoff**: main agent must record approval via `sce approvals approve-macro`
