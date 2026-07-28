---
name: plan-progress-review
description: Reviews training progress across all completed weeks of the current plan. Use when athlete asks "how is my training going so far?", "recap my marathon training", "how have the past N weeks been?", or any question spanning multiple training weeks — NOT single-week analysis.
compatibility: Codex CLI/IDE; requires local resilio CLI and repo context
---

# Plan Progress Review: Multi-Week Training Assessment

## Overview

This skill provides a comprehensive review of all completed training weeks in the current
plan. It covers plan adherence, volume trends, load progression, and overall coaching
assessment across the full period from plan start to now.

**Key principle**: Activity data is the source of truth. Never ask the athlete "were you
consistent?" when synced data can answer it. Use the data; reserve questions for context
only data can't provide (scheduling reasons, how an injury felt, etc.).

**Communication guideline**: Present findings naturally. Say "Let me review your marathon
training progress" not "I'll use plan-progress-review." See AGENTS.md "Athlete-Facing
Communication Guidelines."

**CLI execution rule**: Always attempt commands via the shell tool before concluding they
cannot be run. Never tell athletes to run commands in their terminal, even if an initial
attempt fails — try alternatives first (see AGENTS.md "CLI Failure Rule").

**Metric explainer rule (athlete-facing)**:
On first mention of any metric (VDOT/CTL/ATL/TSB/ACWR/Readiness/RPE), add a short,
plain-language definition. If multiple metrics appear together, use a single "Quick defs"
line. Do not repeat unless the athlete asks or seems confused. For multi-sport athletes,
add a brief clause tying the metric to total work across running + other sports.

---

## Workflow

### Step 1: Get Plan Context

```bash
resilio plan status
resilio dates today
```

Parse from output:
- `current_week_number` — which plan week we are in now
- `plan_start_date` — date the plan began (YYYY-MM-DD)
- `total_weeks` — total plan duration
- `n_completed_weeks` — number of fully completed weeks (= current_week_number - 1)
- Phase names and boundaries

**Stop condition**: If `n_completed_weeks == 0`, no full week has completed yet. Tell the
athlete: "Your plan just started — come back after your first full training week for a
progress review." Do not proceed further.

### Step 2: Pull All Completed Weeks' Plans

```bash
resilio plan week --week 1 --count [n_completed_weeks]
```

Returns planned workouts for each completed week with dates, distances, workout types, RPE,
and pace targets. Store for matching in Step 4.

### Step 3: Pull All Activities Since Plan Start

```bash
resilio activity list --since [plan_start_date] --sport run
resilio activity list --since [plan_start_date]
```

**CRITICAL**: These commands return ALL activities since the plan start date regardless of
what day they fall on. Do NOT pre-filter by planned workout days. All runs in each week
window (Mon-Sun) must be captured before matching begins.

The second command (all sports) is for load context — multi-sport activities affect fatigue
even when they are not running workouts.

### Step 4: Week-by-Week Activity-First Matching

For each completed week W(n) (week 1 through n_completed_weeks):

**4a — Define the week window**
- `week_start` = Monday of week n (use `resilio dates week-boundaries` if needed)
- `week_end` = Sunday of week n

**4b — Collect ALL activities in the window**
From the full activity list pulled in Step 3, extract every running activity whose date
falls between `week_start` and `week_end` (inclusive). Include activities on any day of
the week — Monday through Sunday.

**⚠️ CRITICAL — Activity-first, not plan-first**

Do NOT iterate over planned workout dates looking for matching activities. This silently
drops day-shifted activities (e.g., a Wednesday run done on Thursday) because no planned
entry exists for Thursday.

Instead: collect the full week's activities first, then match each one to the closest
planned workout.

**4c — Match each collected activity → closest planned workout**

| Category | Definition |
|----------|------------|
| ✅ Match | Type + volume aligns with a planned workout, same day |
| ⚠️ Day shift | Aligns with a planned workout by type/volume, but on a different day — **count as completed** |
| ⚠️ Volume variance | Matched by type/day but >15% over or under planned distance — flag, don't penalize |
| ❌ Missed | Planned workout with NO matching activity found anywhere in the week window |
| ➕ Extra | Activity with no corresponding planned workout (cross-training, bonus run) |

**4d — Compute week summary**

- `planned_workouts`: count of planned runs for the week
- `completed_workouts`: count of matched activities (✅ Match + ⚠️ Day shift)
- `planned_km`: sum of planned distances
- `actual_km`: sum of matched activity distances
- `volume_pct`: actual_km / planned_km × 100
- `week_status`: see status guide below

**Week status guide**:

| Condition | Status |
|-----------|--------|
| completed_workouts == planned_workouts AND volume_pct 85-115% | ✅ Excellent |
| completed_workouts == planned_workouts AND volume_pct outside 85-115% | ⚠️ Volume variance |
| completed_workouts == planned_workouts - 1 OR volume_pct 70-84% | ⚠️ Minor miss |
| completed_workouts <= planned_workouts - 2 OR volume_pct < 70% | ❌ Significant miss |
| completed_workouts > planned_workouts | ➕ Over-plan |

### Step 5: Overall Period Assessment

Compute aggregates across all completed weeks:

- `total_planned_workouts`: sum of planned_workouts across all weeks
- `total_completed_workouts`: sum of completed_workouts across all weeks
- `overall_adherence_pct`: total_completed / total_planned × 100
- `total_planned_km`: sum of planned_km
- `total_actual_km`: sum of actual_km
- `overall_volume_pct`: total_actual / total_planned × 100
- Identify the best week and most challenging week

**If 3+ weeks completed**, also pull current metrics for trend context:

```bash
resilio status
```

Parse: current CTL, ATL, TSB, ACWR, readiness.

### Step 6: Synthesize and Communicate

Present the findings inline. Do not ask the athlete "were you consistent?" — the data
already answers that. Reserve questions for context data cannot provide, such as the reason
behind a scheduling shift or how a hard week felt physically.

**Structure**:

1. **Opening hook**: Overall assessment in one sentence (positive first)
2. **Week-by-week table**: See output template below
3. **Key patterns**: 2-3 notable trends across the period
4. **Current state**: CTL/TSB/readiness in plain language (not raw numbers)
5. **Coaching assessment**: 2-3 actionable sentences about what the data shows and what to focus on next

---

## Output Template

```
## Training Progress: Week 1–[N] of [TOTAL] ([DATE_RANGE])

**Overall**: [X]/[Y] planned workouts completed ([Z]% adherence) | [actual_km]km of [planned_km]km ([vol_pct]%)

| Week | Dates | Planned | Completed | Volume | Status |
|------|-------|---------|-----------|--------|--------|
| 1 | Jan 26–Feb 1 | 3 runs, 23km | 3 runs, 22.5km | 98% | ✅ Excellent |
| 2 | Feb 2–8 | 3 runs, 26km | 2 runs, 22km | 85% | ⚠️ Minor miss |
| 3 | Feb 9–15 | 3 runs, 28km | 3 runs, 31.5km | 113% | ⚠️ Volume +13% |

**Key patterns**:
- [Pattern 1: e.g., consistent with weekday runs, long runs occasionally shifted or extended]
- [Pattern 2: e.g., multi-sport weeks caused slight volume dips]
- [Pattern 3 if applicable]

**Current state**: [Plain language — e.g., "You're well-adapted with good freshness heading into week 4."]

**Coaching assessment**: [2-3 sentences synthesizing what the data shows, what's working, and the one most important thing to focus on going forward.]
```

---

## Adherence Interpretation Zones

| Overall adherence | Assessment |
|-------------------|------------|
| ≥90% | Excellent — training is highly consistent |
| 75–89% | Good — minor gaps, investigate any recurring miss pattern |
| 60–74% | Fair — discuss barriers; consider plan adjustment |
| <60% | Poor — major replanning likely needed |

---

## Common Patterns to Flag

**Positive patterns** (reinforce):
- All quality sessions (tempo, long runs) completed even when easy runs were shifted
- Day-shifted workouts still completed — shows scheduling flexibility
- Volume staying within 85-115% of plan across multiple weeks

**Concerning patterns** (investigate):
- Consistently missing the same day each week → scheduling conflict worth addressing
- Long runs repeatedly over-distance → risk of cumulative load spike
- Volume adherence declining week-over-week → fatigue or motivation trend
- Multi-sport activities crowding out planned runs → load management conversation

---

## Quick Pitfalls Checklist

Before presenting the multi-week review, verify:

0. ✅ **Collected all activities first** — pulled full activity list since plan start date before matching
0b. ✅ **Checked all week days** — matched from full Mon–Sun window, not just planned dates
1. ✅ **Counted day-shifted activities as completed** — a run done Thursday instead of Wednesday = ✅, not ❌
2. ✅ **Started with positive** — overall completion before diving into individual misses
3. ✅ **Did not ask what data can answer** — synced data shows completion; questions are for context only
4. ✅ **Reported volume variance without penalizing** — flag +29% long run but count it as completed
5. ✅ **Plain language metrics** — "you're carrying fatigue" not "TSB is -12"

---

## CLI Reference

| Command | Purpose | Notes |
|---------|---------|-------|
| `resilio plan status` | Current week number, plan start date, total weeks | Parse: current_week_number, plan_start_date |
| `resilio dates today` | Current date | Use to verify week boundaries |
| `resilio plan week --week N --count M` | Planned workouts for weeks N through N+M-1 | Returns dates, distances, types |
| `resilio activity list --since YYYY-MM-DD --sport run` | All running activities since date | No `--until` flag; filter by week window manually |
| `resilio activity list --since YYYY-MM-DD` | All activities since date (all sports) | For multi-sport load context |
| `resilio status` | Current CTL/ATL/TSB/ACWR/readiness | Use for current state snapshot |

**Important constraint**: `resilio activity list` has no `--until` flag. Use `--since [plan_start_date]`
to get all activities from plan start to today, then filter each week's activities by date
range in the matching step.
