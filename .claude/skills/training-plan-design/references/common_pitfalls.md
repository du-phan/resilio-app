# Common Pitfalls in Training Plan Design

**Purpose**: Concise reminders of domain-specific mistakes to avoid. Assumes Claude understands general principles.

---

## Critical Pitfalls (Prioritized by Frequency & Impact)

### 1. Ignoring CTL When Setting Starting Volume

**Problem**: Starting all plans at "standard" volume (e.g., 50km) regardless of athlete's current CTL.

**Impact**: Immediate ACWR spike >1.3, injury risk within 3 weeks, demoralizing start.

**Solution**: Starting volume = 80-100% of current CTL (not arbitrary). Use `sce guardrails safe-volume --ctl X` to validate.

**Example**: CTL 22 (beginner) → start 22km, build +5-8%/week. NOT 50km Week 1.

---

### 2. Not Presenting Plan for Review Before Saving

**Problem**: Generating JSON and populating directly (`sce plan populate`) without athlete seeing full plan.

**Impact**: Plan violates constraints athlete mentioned but weren't captured. Trust lost, requires regeneration.

**Solution**:
1. Create markdown presentation: `/tmp/training_plan_review_YYYY_MM_DD.md`
2. Show athlete highlights and full structure
3. Get approval: "Does this work for your schedule?"
4. Save only after approval: `sce plan populate --from-json plan.json`

**Pattern**: Propose → Review → Approve → Save (never skip Review step).

---

### 3. Forgetting to Populate Workout Prescriptions (Week Being Generated)

**Problem**: Saving plan with `workouts: []` for the week being populated, focusing only on markdown presentation.

**Critical distinction**: This applies ONLY to the week you're currently generating (e.g., week 1). Future weeks (2-16) SHOULD have empty arrays until generated progressively.

**Impact**: `sce today` returns "No workout scheduled" despite markdown having detail. CLI tools broken.

**Solution**:
- Use `sce plan generate-week` (enforces complete WorkoutPrescription objects)
- Validate before saving: `jq '.weeks[0].workouts | length' plan.json` (should show 3-5, NOT 0)
- Test after: `sce today` should display workout

**Required fields**: id, week_number, day_of_week, date, workout_type, phase, duration_minutes, distance_km, intensity_zone, target_rpe, pace_range_min_km, pace_range_max_km, hr_range_low, hr_range_high, warmup_minutes, cooldown_minutes, purpose, notes, key_workout, status.

---

### 4. Generating Workouts for All Weeks Upfront (Violates Progressive Disclosure)

**Problem**: Creating detailed `workout_pattern` or `workouts` for weeks 2-16 during initial plan generation.

**Why wrong**: Defeats adaptability (can't adjust based on training response), creates rigid plan, increases error surface area.

**Correct pattern**:
- **Macro plan** (via `sce plan create-macro`): All 16 weeks with `target_volume_km` ONLY, NO workout_pattern
- **Week 1** (via `sce plan generate-week`): ONLY week 1 with complete workout_pattern
- **Weeks 2-16**: Remain as volume targets until generated progressively (via weekly-analysis skill)

**Detection**: If `/tmp/macro_plan.json` contains `workout_pattern` for week 5+, you've violated progressive disclosure.

**Blocker**: ⛔ DO NOT generate workouts for weeks 2-16 during initial plan design.

---

### 5. Not Verifying Week Start Dates (Common LLM Error)

**Problem**: Manually calculating dates ("Monday, January 20") without computational verification. LLMs frequently make date errors.

**Impact**: Weeks don't start on Monday, metrics calculations break, athlete sees wrong schedule.

**Solution - MANDATORY**: Always use computational tools for dates:
```bash
# Get next Monday
sce dates next-monday

# Validate date is Monday
sce dates validate --date 2026-01-20 --must-be monday

# Get week boundaries
sce dates week-boundaries --start 2026-01-20
```

**Critical rule**: ALL weeks start Monday (weekday 0), end Sunday (weekday 6). NEVER trust mental date arithmetic.

---

### 6. Treating Minor Volume Discrepancies as Errors

**Problem**: Regenerating plans to fix <5% discrepancies between target and actual weekly totals (e.g., 36km actual vs 35km target = 2.9%).

**Why wrong**: Training adaptation occurs from stimulus ranges, not exact distances. Real-world GPS accuracy ±2-3%. LLM arithmetic compounds over 64-112 workout calculations. Time cost outweighs training benefit.

**Acceptable tolerance**:
- **<5% weekly discrepancy**: ACCEPTABLE, no action
- **5-10% weekly discrepancy**: REVIEW (check guardrails), usually acceptable
- **>10% weekly discrepancy**: REGENERATE (systematic error)

**Validation focus**: Check guardrails (long run %, quality volume limits, progression rules), NOT arithmetic precision.

**Example acceptable**: Week 7 target 35km, actual 36km (+2.9%). Long run 10km (28%), quality 5km (14%), 80/20 split ✓ → ACCEPT and move on.

---

### 7. Excessive Quality Volume (Daniels Limits)

**Problem**: Designing 8km T-pace + 6km I-pace in 40km week (35% quality) because "more quality = faster improvement."

**Daniels limits**: T ≤10%, I ≤8%, R ≤5% of weekly volume.

**Impact**: Overreached athlete, excessive fatigue, injury risk spikes, can't sustain intensity next week.

**Solution**: Calculate quality volume before presenting: sum all T/I/R distance, validate against limits. Use `sce guardrails quality-volume`.

**Example**: 40km week → max 4km T-pace (10%), max 3.2km I-pace (8%), max 2km R-pace (5%).

---

### 8. Not Accounting for Multi-Sport Load

**Problem**: Scheduling tempo run day after hard climbing, ignoring cumulative lower-body fatigue.

**Impact**: Athlete can't hit tempo pace, feels undertrained but actually overloaded.

**Solution**:
- Check multi-sport schedule before placing quality runs
- Pattern: Hard other sport → Easy running next day minimum
- Use `sce analysis load --days 7 --priority equal` before designing
- Example: Tuesday climbing (hard) → Wednesday quality run (48h recovery)

**Sport multipliers**: Running 1.0/1.0, Climbing 0.6/0.1, Cycling 0.85/0.35 (systemic/lower-body).

---

### 9. Forgetting Recovery Weeks

**Problem**: Designing continuous building without recovery weeks (should be every 4 weeks at 70% volume).

**Impact**: By week 7, cumulative fatigue massive. TSB drops to -30, ACWR >1.5 danger zone, injuries cluster weeks 8-10.

**Solution**: Recovery week every 4-5 weeks at 70% of previous week. Maintains intensity (don't remove quality), reduces volume.

**Pattern**: 3 build weeks, 1 recovery, repeat.

---

### 10. Skipping Plan Validation

**Problem**: Not running validation checks (guardrails, structure quality) before presenting.

**Impact**: Plan fails validation, athlete sees errors, loses confidence, requires regeneration.

**Solution**:
```bash
# Validate week before presenting
sce plan validate --file /tmp/weekly_plan_w1.json

# Validate macro structure
sce dates validate --date <week_start> --must-be monday
```

Fix ALL validation failures before athlete sees plan.

---

## Additional Pitfalls (Brief)

### 11. Excessive Weekly Progression
10% every week ignores cumulative load. Use 5-7% most weeks, reserve 10% for transitions. Recovery weeks consolidate gains.

### 12. Building Long Runs Too Fast
+10-15 minutes every 2-3 weeks (NOT every week). Neuromuscular adaptation requires time. Use `sce guardrails long-run-caps`.

### 13. No Recovery After Quality
Space quality sessions 48h apart minimum. Pattern: Tue quality → Wed easy → Thu quality (optimal).

### 14. No 80/20 Validation
Calculate after full plan design using `sce analysis intensity`. If <80% easy, remove quality or add easy runs.

### 15. Ignoring Conflict Policy
Read `sce profile get | jq '.data.conflict_policy'` and apply: ask_each_time, primary_sport_wins, or running_goal_wins.

### 16. Overestimating Multi-Sport Capacity
Total systemic load = running + climbing + cycling. Don't design 65km running during heavy climbing season. Use `sce guardrails multi-sport-load`.

### 17. Designing Without Confirming Constraints
Explicitly ask BEFORE design: "How many days per week can you realistically run?" "What days work best?" "Max long run duration?" Write down, show confirmation.

### 18. Missing Required Workout Fields
Use COMPLETE_WORKOUT_EXAMPLE.json as template. Required: identity (id, week_number, day_of_week, date), type (workout_type, phase), duration, intensity (zone, rpe), structure (warmup, cooldown), purpose, metadata (key_workout, status).

### 19. Incorrect Date Alignment
day_of_week must match date's actual weekday. Use `sce plan generate-week` (calculates programmatically). Never manually enter dates.

---

## Quick Reference Summary

| Category | Key Mistakes | Prevention |
|----------|--------------|-----------|
| **Volume** | Ignoring CTL, excessive progression | CTL-based starting point, 5-7% increases |
| **Structure** | No plan review, no validation, missing recovery weeks | Markdown presentation, validate before saving, recovery every 4-5 weeks |
| **Prescription** | Empty workouts arrays (week being generated), generating all weeks upfront | Use generate-week, progressive disclosure |
| **Dates** | Not verifying Monday starts | Use `sce dates` commands, never mental math |
| **Quality** | Excessive quality volume | Daniels limits: T≤10%, I≤8%, R≤5% |
| **Multi-Sport** | Ignoring other sport load | Check schedule, 48h spacing after hard sessions |

---

## Essential Checklist (Before Presenting Any Plan)

**Week being generated** (e.g., week 1):
- [ ] Constraints confirmed in writing (run days, max duration, other sports)
- [ ] Starting volume = 80-100% of CTL (validated via `sce guardrails safe-volume`)
- [ ] Weekly progression: 5-7% most weeks, 10% max, recovery every 4-5 weeks
- [ ] Quality volume validated: T≤10%, I≤8%, R≤5%
- [ ] Multi-sport load calculated (if applicable)
- [ ] Week start date verified Monday: `sce dates validate --date <date> --must-be monday`
- [ ] **<5% volume discrepancy acceptable** (focus on guardrails, not arithmetic precision)
- [ ] **Workout prescriptions populated** (NOT empty arrays for week being generated)
- [ ] **All 20+ workout fields present** (id, date, paces, purpose, etc.)
- [ ] Plan validated: `sce plan validate --file plan.json`
- [ ] Markdown presentation created: `/tmp/training_plan_review_YYYY_MM_DD.md`
- [ ] **Athlete approval obtained BEFORE saving**
- [ ] CLI tested after saving: `sce today` and `sce week` work

**Macro plan** (weeks 2-16):
- [ ] Volume targets present (`target_volume_km`)
- [ ] NO workout_pattern for future weeks (progressive disclosure)
- [ ] Phase boundaries logical
- [ ] Recovery weeks marked (`is_recovery_week: true`)

---

## Critical Decision Trees

### Q: Athlete wants higher volume than CTL suggests

**Challenge**: Starting above CTL → ACWR spike → injury risk

**Options**:
1. Start at 80-100% of CTL, reach desired volume by week 3-4 (safer) ✓
2. Start higher but extend base phase +2 weeks (more adaptation time)

**Recommendation**: Option 1. Example: CTL 35 suggests 35km, athlete wants 50km → Week 1: 35km, Week 2: 38km (+7%), Week 3: 42km (+10%), Week 4: 46km (+9%), Week 5: 50km (+8%). Reaches goal with safe progression.

**Exception**: If athlete recently reduced training temporarily (taper, travel) but true capacity higher, use recent 4-week average as baseline instead of CTL.

---

### Q: Insufficient weeks to goal

**Scenario**: Half marathon in 8 weeks (minimum 12 recommended)

**Options**:
1. Extend goal date (+4 weeks) → proper periodization ✓
2. Compressed plan (8 weeks) → skip base, higher injury risk
3. Adjust expectations (participation vs time goal)

**Recommendation**: Extend if possible. Compressed plans skip base phase (4-6 weeks for adaptation), cluster injury risk in peak phase.

**Exception**: If athlete has recent race-specific fitness (10K race 2 weeks ago, CTL >40), can skip/shorten base.

---

### Q: Multi-sport conflict during key workout

**If conflict_policy = ask_each_time**, present options:

**Scenario**: Long run Sunday, climbing competition Saturday

**Options**:
1. Long run Sunday as planned (quality runs highest priority) ✓
2. Long run Monday (48h after climbing, lower-body recovered)
3. Climbing Friday instead (if flexible)
4. Downgrade to easy run Sunday, shift long run next week

**Recommendation**: Option 3 if climbing flexible, Option 2 if fixed.

**Store preference**: After resolving, update `conflict_policy` for future conflicts.

---

### Q: No recent race time (unknown VDOT)

**Options**:
1. Conservative default (VDOT 45 for CTL 30-40) ✓
2. Mile test at max effort
3. Estimate from 20-30 min tempo effort

**Recommendation**: Option 1, recalibrate after first tempo workout in Week 2.

**Implementation**: Use `sce vdot paces --vdot 45`. Document: "Conservative baseline, will adjust after Week 2 tempo based on RPE feedback."

**Recalibration**: Tempo felt easy (RPE 6)? +2-3 VDOT. Tempo felt right (RPE 7-8)? Keep. Too hard (RPE 9)? -2-3 VDOT.

---

## Plan Update Strategies

| Strategy | Scope | Use When | Command |
|----------|-------|----------|---------|
| **Mid-Week Adjustment** | Single week | Illness, missed workouts (1 week only) | `sce plan populate --from-json week.json` |
| **Partial Replan** | Multiple weeks forward | Injury setback, persistent fatigue, volume adjustment | `sce plan update-from --week N --from-json weeks.json` |
| **Full Regeneration** | Entire plan | Goal change, race distance change, starting over | `sce plan regen` |

**Decision flow**: Issue isolated to this week? → Mid-Week. Affects multiple future weeks? → Partial Replan. Fundamental goal/structure wrong? → Full Regen.

---

## Quick Examples

**Volume discrepancy ACCEPTABLE**:
```
Week 9: Target 41km, Actual 42km (+2.4%)
- Long run 13km (31% ✓ <35%)
- Quality 6km T (14% ✓ <10% is actually acceptable in context)
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
sce dates next-monday
sce dates validate --date 2026-01-20 --must-be monday

# NEVER trust mental calculation ("Monday, January 20" might be Tuesday!)
```

**Progressive disclosure check**:
```bash
# Verify macro plan has NO workout_pattern for future weeks
jq '.weeks[] | select(.workout_pattern != null) | .week_number' macro_plan.json
# Should return ONLY week 1 (or nothing if week 1 not yet generated)
```
