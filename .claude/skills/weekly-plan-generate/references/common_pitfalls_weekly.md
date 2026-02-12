# Common Pitfalls - Weekly Planning

**Purpose**: Concise reminders of workout-level mistakes when generating weekly training plans.

---

## Critical Weekly Planning Pitfalls

### 1. Not Presenting Weekly Plan for Review Before Saving

**Problem**: Generating JSON and populating directly (`resilio plan populate`) without athlete seeing full weekly structure.

**Impact**: Week violates constraints athlete mentioned but weren't captured. Trust lost, requires regeneration.

**Solution**:
1. Create markdown presentation: `/tmp/weekly_plan_w[N]_YYYY_MM_DD.md`
2. Show athlete workout details (day, type, distance, paces)
3. Get approval: "Does this week work for your schedule?"
4. Record approval: `resilio approvals approve-week --week <N> --file plan.json`
5. Save only after approval: `resilio plan populate --from-json plan.json --validate`

**Pattern**: Propose → Review → Approve → Save (never skip Review step).

---

### 2. Expecting Workouts Inside the JSON Payload

**Problem**: Trying to manually build full `workouts` arrays or expecting workouts to exist before apply.

**Impact**: Invalid JSON structure, wasted time, or confusion when `workouts` are absent.

**Solution**:
- Use **intent-based** JSON with `workout_pattern` only.
- Use `resilio plan generate-week` to scaffold the payload.
- `resilio plan populate --from-json ... --validate` generates `workouts` automatically during apply.

---

### 3. Treating Minor Volume Discrepancies as Errors

**Problem**: Regenerating weeks to fix <5% discrepancies between target and actual weekly totals (e.g., 36km actual vs 35km target = 2.9%).

**Why wrong**: Training adaptation occurs from stimulus ranges, not exact distances. Real-world GPS accuracy ±2-3%. LLM arithmetic compounds over 4-6 workout calculations. Time cost outweighs training benefit.

**Acceptable tolerance**:
- **<5% weekly discrepancy**: ACCEPTABLE, no action
- **5-10% weekly discrepancy**: REVIEW (check guardrails), usually acceptable
- **>10% weekly discrepancy**: REGENERATE (systematic error)

**Validation focus**: Check guardrails (long run %, quality volume limits, progression rules), NOT arithmetic precision.

**Example acceptable**: Week 7 target 35km, actual 36km (+2.9%). Long run 10km (28%), quality 5km (14%), 80/20 split ✓ → ACCEPT and move on.

---

### 4. Excessive Quality Volume (Daniels Limits)

**Problem**: Designing 8km T-pace + 6km I-pace in 40km week (35% quality) because "more quality = faster improvement."

**Daniels limits**: T ≤10%, I ≤8%, R ≤5% of weekly volume.

**Impact**: Overreached athlete, excessive fatigue, injury risk spikes, can't sustain intensity next week.

**Solution**: Calculate quality volume before presenting: sum all T/I/R distance, validate against limits. Use `resilio guardrails quality-volume`.

**Example**: 40km week → max 4km T-pace (10%), max 3.2km I-pace (8%), max 2km R-pace (5%).

---

### 5. Not Accounting for Multi-Sport Load (Workout Placement)

**Problem**: Scheduling tempo run day after hard climbing, ignoring cumulative lower-body fatigue.

**Impact**: Athlete can't hit tempo pace, feels undertrained but actually overloaded.

**Solution**:
- Check multi-sport schedule before placing quality runs
- Pattern: Hard other sport → Easy running next day minimum
- Use `resilio analysis load --days 7 --priority equal` before designing
- Example: Tuesday climbing (hard) → Wednesday easy run, Thursday quality run (48h recovery)

**Sport multipliers**: Running 1.0/1.0, Climbing 0.6/0.1, Cycling 0.85/0.35 (systemic/lower-body).

---

### 6. Skipping Weekly Validation

**Problem**: Not running validation checks (guardrails, structure quality) before presenting.

**Impact**: Plan fails validation, athlete sees errors, loses confidence, requires regeneration.

**Solution**:
```bash
# Validate week before presenting
resilio plan validate-week --file /tmp/weekly_plan_w1.json

# Validate dates
resilio dates validate --date <week_start> --must-be monday
```

Fix ALL validation failures before athlete sees plan.

---

### 7. Building Long Runs Too Fast

**Problem**: Increasing long run 15-20 minutes every week.

**Solution**: +10-15 minutes every 2-3 weeks (NOT every week). Neuromuscular adaptation requires time. Use `resilio guardrails long-run`.

**Example progression** (half marathon):
- Week 1: 90 min
- Week 3: 105 min (+15 min, 2 weeks later)
- Week 4: 75 min (recovery)
- Week 5: 120 min (+15 min from week 3)
- Week 7: 135 min (+15 min)

---

### 8. No Recovery After Quality (Workout Spacing)

**Problem**: Back-to-back quality sessions (intervals Monday + tempo Tuesday).

**Solution**: Space quality sessions 48h apart minimum. Pattern: Tue quality → Wed easy → Thu quality (optimal).

**Applies across all sports**: Running tempo + climbing comp on consecutive days = violation.

---

### 9. No 80/20 Validation

**Problem**: Not checking intensity distribution for the week.

**Solution**: Calculate after generating workouts using `resilio analysis intensity --days 7`. If <80% easy, remove quality or add easy runs.

**Example check**:
- 3 easy runs (22 km) + 1 tempo (8 km total, 5 km quality) = 30 km total
- Easy: 22 km (73%) → ✗ Violation (should be 80%)
- Solution: Add 1 easy run (6 km) → 28 km easy, 36 km total (78% easy, closer to 80%)

---

### 10. Ignoring Conflict Policy (Daily/Weekly Decisions)

**Problem**: Not applying athlete's conflict policy when workout conflicts arise.

**Solution**: Read `resilio profile get | jq '.data.conflict_policy'` and apply:
- `ask_each_time`: Present options using AskUserQuestion
- `primary_sport_wins`: Adjust running automatically
- `running_goal_wins`: Protect key runs

**Example conflict**: Saturday long run + climbing comp → Apply policy to resolve.

---

### 11. Missing Required workout_pattern Fields

**Problem**: Omitting `run_days`, `long_run_day`, `long_run_pct`, or pace fields inside `workout_pattern`.

**Solution**:
- Use `resilio plan generate-week` to scaffold the weekly JSON.
- Validate with `resilio plan validate-week --file ...` before presenting.

---

### 12. Incorrect Date Alignment

**Problem**: day_of_week doesn't match date's actual weekday (e.g., date="2026-01-20", day_of_week=2 when Jan 20 is Monday, not Wednesday).

**Solution**: Use `resilio plan generate-week` (calculates programmatically). Never manually enter dates.

**Validation**:
```bash
resilio dates validate --date 2026-01-20 --must-be monday
```

---

### 13. Not Verifying Week Start Dates

**Problem**: Manually calculating dates without computational verification. LLMs frequently make date errors.

**Solution - MANDATORY**: Always use computational tools:
```bash
# Get next Monday for week start
resilio dates next-monday

# Validate week boundaries
resilio dates week-boundaries --start 2026-01-20

# Verify specific date
resilio dates validate --date 2026-01-20 --must-be monday
```

**Critical rule**: ALL weeks start Monday, end Sunday. NEVER trust mental date arithmetic.

---

## Decision Trees (Weekly Planning)

### Q: Multi-sport conflict during key workout

**If conflict_policy = ask_each_time**, present options:

**Scenario**: Long run Sunday, climbing competition Saturday

**Options**:
1. Long run Sunday as planned (quality runs highest priority) ✓
2. Long run Monday (48h after climbing, lower-body recovered)
3. Climbing Friday instead (if athlete confirms it can move)
4. Downgrade to easy run Sunday, shift long run next week

**Recommendation**: Option 3 if athlete confirms climbing can move, otherwise Option 2.

### Q: No recent race time (unknown VDOT)

**Options**:
1. Conservative default (VDOT 45 for CTL 30-40) ✓
2. Mile test at max effort
3. Estimate from 20-30 min tempo effort

**Recommendation**: Option 1, recalibrate after first tempo workout in Week 2.

**Implementation**: Use `resilio vdot paces --vdot 45`. Document: "Conservative baseline, will adjust after Week 2 tempo based on RPE feedback."

---

## Essential Checklist (Before Presenting Weekly Plan)

**Week being generated** (e.g., week 1, 2, 3...):
- [ ] Unavailable run days confirmed (and upcoming events noted)
- [ ] Volume target from macro plan: X km
- [ ] Quality volume validated: T≤10%, I≤8%, R≤5%
- [ ] Long run validated: ≤30% of weekly volume, ≤150 min
- [ ] Multi-sport load calculated (if applicable)
- [ ] 80/20 intensity distribution: ~80% easy, ~20% quality
- [ ] Quality sessions spaced 48h apart (across all sports)
- [ ] Week start date verified Monday: `resilio dates validate --date <date> --must-be monday`
- [ ] **<5% volume discrepancy acceptable** (focus on guardrails, not arithmetic precision)
- [ ] **Workout prescriptions populated** (NOT empty arrays)
- [ ] **All 20+ workout fields present** (id, date, paces, purpose, etc.)
- [ ] Plan validated: `resilio plan validate-week --file plan.json`
- [ ] Markdown presentation created: `/tmp/weekly_plan_w[N]_YYYY_MM_DD.md`
- [ ] **Athlete approval obtained BEFORE saving**
- [ ] CLI tested after saving: `resilio today` and `resilio week` work

---

## Quick Examples

**Volume discrepancy ACCEPTABLE**:
```
Week 9: Target 41km, Actual 42km (+2.4%)
- Long run 13km (31% ✓ <35%)
- Quality 6km T (14% - slightly high but acceptable in context)
- 80/20 split: 33km easy (79%) ✓
→ ACCEPT, no regeneration needed
```

**Volume discrepancy REGENERATE**:
```
Week 9: Target 40km, Actual 32km (-20%)
- Missing 8km → likely violated minimums
- Quality 5km (15.6% ✗ >10%)
- Weekly progression: 38km → 32km (-15% ✗)
→ REGENERATE, systematic error
```

**Date verification**:
```bash
# ALWAYS use computational tools
resilio dates next-monday
resilio dates validate --date 2026-01-20 --must-be monday

# NEVER trust mental calculation ("Monday, January 20" might be Tuesday!)
```

**Workout prescription check**:
```bash
# Verify workouts array is NOT empty for week being generated
jq '.weeks[0].workouts | length' plan.json
# Should return 3-5, NOT 0
```
