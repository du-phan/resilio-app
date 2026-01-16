# Common Adaptation Scenarios

Real-world examples with CLI commands and JSON structures.

---

## Scenario 1: Mild Illness (3 days missed)

**Situation**: Athlete caught cold, missed Tuesday tempo and Thursday easy run. Feeling better Friday.

**Assessment**:
```bash
sce guardrails illness-recovery --severity minor --days-missed 3
```

**Returns**: "2 days easy running before resuming quality"

**Action**: Update current week only
- Skip missed workouts (don't reschedule)
- Replace Saturday long run with moderate easy run (70% duration)
- Next week: Resume normal plan with volume -10%

**JSON**: Single week update (`sce plan update-week`)

---

## Scenario 2: Severe Illness (10 days missed, flu)

**Situation**: Athlete had flu with fever, missed entire week + 3 days of next week.

**Assessment**:
```bash
sce guardrails illness-recovery --severity severe --days-missed 10
```

**Returns**: "7 days easy running before quality, reduce volume 30% first week"

**Action**: Partial replan from current week
- Week N: 3 easy runs, 60% of planned volume
- Week N+1: 4 easy runs, 75% of planned volume
- Week N+2: Resume quality (short tempo), 85% volume
- Week N+3: Normal progression resumes

**JSON**: Partial replan (`sce plan update-from`)

---

## Scenario 3: Injury (2 weeks off, knee pain)

**Situation**: Athlete rested 14 days for knee tendonitis, did swimming 3x/week.

**Assessment**:
```bash
sce guardrails break-return --days 14 --ctl 44 --cross-training moderate
```

**Returns**: "Start at 18 km/week, +5% weekly increase, 4 weeks to pre-injury volume"

**Action**: Partial replan with conservative buildup
- Extend base phase by 2 weeks
- Reduce peak volume by 10%
- Monitor knee pain signals (check notes in activities)

**JSON**: Partial replan with modified phases

---

## Scenario 4: Training Break (3 weeks vacation)

**Situation**: Athlete took 21 days off for travel, no training.

**Assessment**:
```bash
sce guardrails break-return --days 21 --ctl 44 --cross-training none
```

**Returns**: "CTL dropped to ~30. Start at 15 km/week, rebuild over 6 weeks"

**Action**: Major replan
- Restart base phase (or extend existing base)
- Adjust goal if timeline compromised
- Use conservative progression (+5% per week)

**JSON**: Partial replan, possibly full plan regeneration if goal date affected

---

## Scenario 5: Missed Long Run (Travel)

**Situation**: Athlete traveling for work, can't do Saturday 18km long run.

**Assessment**: No guardrails needed, simple rescheduling.

**Action**: Use AskUserQuestion to present options
- Option A: Run Sunday instead (move long run 1 day)
- Option B: Run Friday before travel (earlier in week)
- Option C: Skip this week, extend next week's long run to 20km

**JSON**: Single week update if rescheduling, or skip + adjust next week
