# Decision Trees

Decision logic for common plan adaptation scenarios.

---

## Q: How severe is the illness?

**Decision factors**:
- Above neck (sniffles, sore throat) → Minor
- Body aches, fatigue, full cold → Moderate
- Fever, chest congestion, flu → Severe

**Actions**:
- Minor: 1-2 days rest, return with easy runs
- Moderate: 3-7 days rest, use `sce guardrails illness-recovery --severity moderate`
- Severe: 7-14 days rest, use `sce guardrails illness-recovery --severity severe` + partial replan

---

## Q: Can the goal still be achieved?

**Factors to consider**:
- Weeks remaining to goal
- CTL drop from disruption
- Training phase (base is flexible, peak/taper less so)
- Goal difficulty (time goal vs finish comfortably)

**Decision**:
1. Calculate CTL projection with adapted plan
2. Use `sce vdot predict` to estimate race performance at projected CTL
3. Compare to goal time
4. Present options using **AskUserQuestion**:
   - Option A: Keep goal, accept higher training load
   - Option B: Adjust goal (more realistic time)
   - Option C: Move race date (if possible)

---

## Q: Should quality workouts be reduced or eliminated?

**During illness recovery**:
- Week 1 back: Easy runs only (no quality)
- Week 2 back: Light tempo if feeling good (reduced duration)
- Week 3+ back: Resume quality gradually

**During injury recovery**:
- Until pain-free: No quality workouts
- First week pain-free: Short tempo test (if successful, continue)
- Rebuild intensity over 2-4 weeks

**Check readiness**:
```bash
sce status | jq '.data.readiness'
```

If readiness < 50 after return, delay quality workouts.

---

## Q: What if they miss a long run?

**Options**:
1. **Move to next available day** (if within same week)
2. **Skip and continue** (if recent long run was adequate)
3. **Reduce and reschedule** (shorter version later in week)
4. **Extend next week's long run** (add 10-15 min)

**Use AskUserQuestion** to present options with context:
- Current CTL
- Previous long run date/duration
- Upcoming schedule constraints
- Goal proximity

---

## Q: What if schedule change is permanent?

**Example**: "I can no longer run on Thursdays"

**Workflow**:
1. Identify affected workouts (quality sessions, long runs)
2. Map to new available days
3. Validate with multi-sport constraints (see weekly-plan-generate/references/multi_sport_weekly.md)
4. Update affected weeks using `sce plan populate` (one call per week)

**Considerations**:
- Quality sessions need 48 hours separation
- Long runs need recovery day after
- Other sports: avoid quality run + hard climbing on consecutive days
