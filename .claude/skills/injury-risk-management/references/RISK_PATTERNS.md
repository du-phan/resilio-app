# Common Risk Patterns

Recognizable injury risk patterns and their mitigation strategies.

---

## Pattern 1: Post-Recovery Week Spike

**Scenario**: After recovery week (30% volume drop), athlete returns with +15% increase.

**Risk**: ACWR spikes from 0.9 → 1.35 due to low ATL during recovery week.

**Mitigation**: Post-recovery week should increase +5-10% from pre-recovery baseline, NOT from recovery week.

**Example**:
- Week 3: 50km
- Week 4: 35km (recovery, -30%)
- Week 5: 55km (+10% from Week 3, NOT +57% from Week 4)

---

## Pattern 2: Multi-Sport Overload

**Scenario**: Athlete runs 40km/week + climbs 3x/week (hard sessions).

**Risk**: Systemic load is 1,800 AU (equivalent to 60km running), but ACWR only tracks running (underestimates true load).

**Mitigation**: Use multi-sport load analysis:
```bash
sce analysis load --activities activities.json --days 7 --priority equal
```

Adjust running volume if total systemic load exceeds athlete's capacity.

---

## Pattern 3: Intensity Distribution Error

**Scenario**: Athlete's easy runs are "moderate" (RPE 5-6), not true easy (RPE 3-4).

**Risk**: Chronic fatigue, no true recovery, leads to overtraining despite ACWR <1.3.

**Mitigation**: Validate 80/20 distribution:
```bash
sce analysis intensity --activities activities.json --days 28
```

If distribution is 70/30 or worse, coach athlete to slow down easy runs.

---

## Pattern 4: Long Run Domination

**Scenario**: Long run is 22km in 48km week (46% of volume, exceeds 30% guideline).

**Risk**: Single session causes excessive fatigue, other runs suffer, recovery inadequate.

**Mitigation**: Validate long run percentage:
```bash
sce guardrails long-run --duration 135 --weekly-volume 48 --pct-limit 30
```

Reduce long run or increase weekly volume to balance.

---

## Pattern 5: Session Density

**Scenario**: Tuesday tempo + Thursday intervals + Saturday long run + Sunday cycling (hard).

**Risk**: Hard sessions too close together, no recovery time.

**Mitigation**: Space quality sessions 48-72 hours apart. Check session density in `sce today` output.

**Recommended spacing**:
- 48 hours minimum between quality runs
- 24 hours after hard multi-sport session before easy run
- 48 hours after hard multi-sport session before quality run
