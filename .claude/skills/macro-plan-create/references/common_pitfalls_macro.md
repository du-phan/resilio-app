# Common Pitfalls - Macro Planning

**Purpose**: Concise reminders of macro-level mistakes when designing 16-week training plans.

---

## Critical Macro Planning Pitfalls

### 1. Ignoring CTL When Setting Starting Volume

**Problem**: Starting all plans at "standard" volume (e.g., 50km) regardless of athlete's current CTL.

**Impact**: Immediate ACWR spike >1.3, injury risk within 3 weeks, demoralizing start.

**Solution**: Starting volume = 80-100% of current CTL (not arbitrary). Use `sce guardrails safe-volume --ctl X` to validate.

**Example**: CTL 22 (beginner) → start 22km, build +5-8%/week. NOT 50km Week 1.

---

### 2. Not Presenting Macro Plan for Review Before Generating Week 1

**Problem**: Generating macro structure without showing volume trajectory, phase allocation, and recovery weeks to athlete.

**Impact**: Plan violates constraints athlete mentioned but weren't captured. Trust lost, requires regeneration.

**Solution**:
1. Create markdown presentation: `/tmp/macro_plan_review_YYYY_MM_DD.md`
2. Show athlete 16-week structure: phases, volume targets, recovery weeks
3. Get approval: "Does this structure work for your schedule?"
4. Save only after approval

**Pattern**: Propose → Review → Approve → Generate Week 1 (never skip Review step).

---

### 3. Generating Workouts for All Weeks Upfront (Violates Progressive Disclosure)

**Problem**: Creating detailed `workout_pattern` or `workouts` for weeks 2-16 during macro plan generation.

**Why wrong**: Defeats adaptability (can't adjust based on training response), creates rigid plan, increases error surface area.

**Correct pattern**:
- **Macro plan** (via `sce plan create-macro`): All 16 weeks with `target_volume_km` ONLY, NO workout_pattern
- **Week 1** (generated via weekly-plan-generate): ONLY week 1 with complete workout_pattern
- **Weeks 2-16**: Remain as volume targets until generated progressively (via weekly-plan-generate)

**Detection**: If macro plan JSON contains `workout_pattern` for week 5+, you've violated progressive disclosure.

**Blocker**: ⛔ DO NOT generate workouts for weeks 2-16 during macro plan design.

---

### 4. Forgetting Recovery Weeks

**Problem**: Designing continuous building without recovery weeks (should be every 4 weeks at 70% volume).

**Impact**: By week 7, cumulative fatigue massive. TSB drops to -30, ACWR >1.5 danger zone, injuries cluster weeks 8-10.

**Solution**: Recovery week every 4-5 weeks at 70% of previous week. Mark explicitly in macro plan (`is_recovery_week: true`).

**Pattern**: 3 build weeks, 1 recovery, repeat.

**Example 16-week structure**:
- Weeks 1-3: Build
- Week 4: Recovery (70%)
- Weeks 5-7: Build
- Week 8: Recovery (70%)
- Weeks 9-11: Build
- Week 12: Recovery (70%)
- Weeks 13-14: Peak (hold volume)
- Weeks 15-16: Taper

---

### 5. Excessive Weekly Progression (Macro Level)

**Problem**: Planning 10% every week ignores cumulative load and recovery weeks.

**Solution**: Use 5-7% most weeks, reserve 10% for transitions. Recovery weeks consolidate gains.

**Example macro trajectory**:
- Week 1: 32 km (base)
- Week 2: 35 km (+9%)
- Week 3: 38 km (+8%)
- Week 4: 27 km (recovery, 70% of week 3)
- Week 5: 40 km (+5% from week 3, conservative post-recovery)

---

### 6. Overestimating Multi-Sport Capacity

**Problem**: Designing 65km running peak during heavy climbing season. Total systemic load = running + climbing + cycling.

**Impact**: Athlete burns out, can't maintain both sports, forced to choose.

**Solution**: Adjust peak running volume based on priority:
- PRIMARY: Standard volumes (60-70 km half marathon)
- EQUAL: Reduced volumes (40-50 km half marathon)
- SECONDARY: Maintenance only (25-30 km)

**Use**: `sce guardrails safe-volume --priority equal`

---

### 7. Designing Without Confirming Constraints

**Problem**: Not explicitly asking constraints before macro planning.

**Solution**: Explicitly ask BEFORE design:
- "How many days per week can you realistically run?"
- "What days work best?"
- "Max long run duration?"
- "Other sport commitments?"

Write down, show confirmation before generating macro plan.

---

### 8. Not Verifying Week Start Dates (Common LLM Error)

**Problem**: Manually calculating dates ("Monday, January 20") without computational verification. LLMs frequently make date errors.

**Impact**: Weeks don't start on Monday, metrics calculations break, athlete sees wrong schedule.

**Solution - MANDATORY**: Always use computational tools for dates:
```bash
# Get next Monday for plan start
sce dates next-monday

# Validate all week start dates are Monday
sce dates validate --date 2026-01-20 --must-be monday
```

**Critical rule**: ALL weeks start Monday (weekday 0), end Sunday (weekday 6). NEVER trust mental date arithmetic.

---

## Decision Trees (Macro Planning)

### Q: Athlete wants higher volume than CTL suggests

**Challenge**: Starting above CTL → ACWR spike → injury risk

**Options**:
1. Start at 80-100% of CTL, reach desired volume by week 3-4 (safer) ✓
2. Start higher but extend base phase +2 weeks (more adaptation time)

**Recommendation**: Option 1. Example: CTL 35 suggests 35km, athlete wants 50km → Week 1: 35km, Week 2: 38km (+7%), Week 3: 42km (+10%), Week 4: 46km (+9%), Week 5: 50km (+8%). Reaches goal with safe progression.

### Q: Insufficient weeks to goal

**Scenario**: Half marathon in 8 weeks (minimum 12 recommended)

**Options**:
1. Extend goal date (+4 weeks) → proper periodization ✓
2. Compressed plan (8 weeks) → skip base, higher injury risk
3. Adjust expectations (participation vs time goal)

**Recommendation**: Extend if possible. Compressed plans skip base phase (4-6 weeks for adaptation), cluster injury risk in peak phase.

---

## Essential Checklist (Before Presenting Macro Plan)

- [ ] Constraints confirmed in writing (run days, max duration, other sports)
- [ ] Starting volume = 80-100% of CTL (validated via `sce guardrails safe-volume`)
- [ ] Phase allocation: Base (≥4 weeks), Build (≥4 weeks), Peak (≥2 weeks), Taper (2 weeks)
- [ ] Recovery weeks scheduled (every 4-5 weeks during base/build)
- [ ] Weekly progression: 5-7% most weeks, 10% max
- [ ] Multi-sport load considered (if applicable)
- [ ] Week start dates verified Monday: `sce dates validate --date <date> --must-be monday`
- [ ] Volume targets present (`target_volume_km`), NO workout_pattern for weeks 2-16
- [ ] Markdown presentation created: `/tmp/macro_plan_review_YYYY_MM_DD.md`
- [ ] **Athlete approval obtained BEFORE generating Week 1**
