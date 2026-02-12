# Goal Validation Reference

## Get Performance Baseline

```bash
resilio performance baseline
```

**Present context to athlete**:

- Current VDOT estimate: XX (from recent workouts)
- Peak VDOT: YY (from ZZ race on [date])
- Goal requires VDOT: ZZ
- Gap: +/- N VDOT points

## Set Goal (Automatic Validation)

The `resilio goal set` command automatically validates feasibility:

```bash
resilio goal set --type half_marathon --date 2026-06-01 --time "1:30:00"
# Automatically returns: goal saved + feasibility verdict + recommendations
```

**Output includes**:

- Feasibility verdict: VERY_REALISTIC / REALISTIC / AMBITIOUS_BUT_REALISTIC / AMBITIOUS / UNREALISTIC
- VDOT gap (current vs. required)
- Weeks available for training
- Recommendations for achieving goal

## Coaching Response Based on Verdict

**VERY_REALISTIC / REALISTIC:**

- Build confidence: "Your goal is well within reach based on your current fitness (VDOT 48) and training history."
- Set expectations: "We'll design a plan that maintains fitness and sharpens your speed."

**AMBITIOUS_BUT_REALISTIC:**

- Acknowledge challenge: "This is a stretch goal requiring VDOT improvement from 48 -> 52 (+8.3%) over 20 weeks."
- Build commitment: "It's achievable with strong adherence. Are you ready to commit to 4 quality runs/week?"

**AMBITIOUS:**

- Use chat-based numbered options to present options:
  - **Option 1**: Keep ambitious goal, design aggressive plan, acknowledge 40-50% success probability
  - **Option 2**: Adjust goal to realistic range (suggest alternative: 1:35:00 = VDOT 49)
  - **Option 3**: Target a later race (suggest +8 weeks for better preparation)

**UNREALISTIC:**

- Present reality: "Your goal requires VDOT 52, but current fitness is VDOT 45. That's a 15.6% improvement in 12 weeks."
- Show math: "Typical VDOT gains are 1.5 points/month. You'd need 7 points in 3 months = 2.3 points/month (50% faster than typical)."
- Recommend alternatives:
  - Alternative time: "Based on current fitness, 1:38:00 is realistic (VDOT 48)"
  - Alternative timeline: "For your 1:30:00 goal, I recommend targeting a race 5 months out"

**Decision point**: Wait for athlete confirmation before proceeding to Step 6 (Constraints Discussion).

## Edge Case: No Current VDOT Estimate

If `resilio performance baseline` returns no VDOT estimate (no recent quality workouts):

```
Coach: "I don't have enough recent quality workout data to estimate your current fitness.
Your goal is half marathon 1:30:00 (VDOT 52 required).

Let's take a conservative approach initially and reassess after your first tempo run gives us a VDOT estimate."
```

**Proceed with goal set**, but flag that validation will improve after first quality workout.
