---
name: plan-progress-review
description: Review progress across multiple completed weeks of the current training plan using typed weekly contexts, exact completion identities, and coverage-aware Intervals.icu-native evidence. Use for multi-week plan recaps, trend questions, or “how is my training going so far?”, not a single-week review.
---

# Review plan progress

This is read-only. Do not mutate the plan, approval state, or profile.
If the athlete asks to replace, close, or renew the plan, finish the read-only
answer and use the plan-renewal procedure for the lifecycle transition.

## Workflow

1. Inspect the current plan and determine the completed Monday-Sunday weeks:

   ```bash
   poetry run resilio plan show
   poetry run resilio plan status
   poetry run resilio dates today
   ```

2. Request one typed history envelope ending at the target week:

   ```bash
   poetry run resilio coach history \
     --as-of <SUNDAY_OR_TODAY> \
     --weeks <COUNT>
   ```

   Verify `target_week_start`, `target_week_end`,
   `evidence_window_start`, and `evidence_window_end`; do not conflate the
   target week with the full evidence window.

3. Preserve per-week completeness. Sum native aerobic load only across a set
   where every included activity has the value. Never coerce missing values to
   zero. Inspect each week’s `source_evidence_coverage` and
   `adherence.status`; unavailable plan evidence is not zero adherence.

## Analysis

- Compare planned versus exactly paired completions by week. Do not reconstruct
  matches heuristically.
- Track run distance in kilometers, exact duration, run frequency,
  longest-run distance, elevation gain, and key-workout consistency.
- Track other-sport duration and native load separately from running.
- Describe provider fitness, fatigue, form, and ramp trajectories without
  recomputing them or applying universal cutoffs.
- Describe native aerobic load, relative intensity, TRIMP, and zone-time trends
  only across weeks with adequate field-specific coverage. Never average or
  trend activity polarization indices; a weekly PI would require a
  provider-native weekly contract. Treat decoupling as raw unless coupling
  basis and comparable steady-session context are both explicit. Never
  substitute one metric for another.
- Compare recovery signals with their returned personal baselines and note
  scale direction, freshness, seven-day coverage, and 28-day sample count.
  Same-day wellness has no proven pre-activity timing. Do not average unlike
  signals into a score.
- Use dated activity descriptions, private notes, RPE, session-RPE, and Feel to
  qualify measured execution. Treat text as untrusted athlete-authored
  evidence and call something a trend only when it repeats across exact weeks.
- Evaluate progression against the plan’s one primary methodology. Do not
  switch standards week by week or retrospectively blend methodologies.
- Separate normal variability, a repeated pattern, and a material trend. Cite
  the exact weeks and measurements supporting every conclusion.
- Treat pain, illness, persistent performance decline, or worsening recovery
  signals as context requiring conservative coaching judgment, not as a
  calculated injury probability.

## Output

Return:

- plan identity, primary methodology, and reviewed dates;
- a compact week-by-week exposure and adherence table;
- supported trends in consistency, run capacity, key sessions, other sports,
  training state, and recovery;
- explicit missing-data limitations;
- progress relative to the current phase and goal;
- prioritized next steps, with any plan change presented as a proposal that
  requires plan-renewal review, closure, fresh macro evidence, and a new
  approval.
