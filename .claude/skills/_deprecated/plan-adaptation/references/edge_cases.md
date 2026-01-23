# Edge Cases

Handling unusual adaptation situations.

---

## Edge Case 1: Illness During Taper

**Problem**: Athlete gets sick 10 days before race.

**Decision**:
- If fever/severe: Consider skipping race (no safe adaptation)
- If mild: Maintain taper volume reduction, skip quality sessions
- Race day: Start conservatively, adjust goals to "finish comfortably"

**No plan update needed** - focus on recovery and race readiness.

---

## Edge Case 2: Injury During Peak Phase

**Problem**: Acute injury 4 weeks before race, peak phase training.

**Decision**:
- 1-2 weeks off: Possible to salvage race with reduced goals
- 3+ weeks off: Recommend moving race date or DNS (do not start)

**Use AskUserQuestion** to discuss options:
- Option A: Race with adjusted goals (finish, not time)
- Option B: Move to later race
- Option C: DNS, replan for different goal

---

## Edge Case 3: Multiple Disruptions in Short Period

**Problem**: Illness → recovered → injury → recovered (4 weeks total disruption).

**Decision**: Full plan regeneration likely needed.

**Action**:
1. Assess current CTL
2. Calculate weeks to goal
3. Use vdot-baseline-proposal (if needed) + macro-plan-create to regenerate plan
4. Present new plan (not adaptation, but fresh start)

---

## Edge Case 4: Schedule Change Affects Key Long Run Day

**Problem**: Athlete can no longer run on Sundays (traditional long run day).

**Decision**: Permanent schedule restructure.

**Action**:
1. Identify new long run day (Saturday? Friday?)
2. Validate with multi-sport constraints
3. Update all future weeks with new schedule pattern
4. Use `sce plan update-from` with restructured weekly pattern
