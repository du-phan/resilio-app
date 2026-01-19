# Guardrails Integration

All guardrails commands that support injury prevention.

---

## Volume Progression

```bash
sce guardrails progression --previous 40 --current 48
```

**Use**: Validate weekly volume increases don't exceed 10% rule.

**Returns**: `ok` (Boolean), `increase_pct`, `safe_max_km`, `violation` (if exceeded)

**When to use**: Before planning next week's volume, after unplanned volume increases

---

## Quality Volume Limits

```bash
sce guardrails quality-volume --t-pace 5.0 --i-pace 4.0 --r-pace 2.0 --weekly-volume 50.0
```

**Use**: Ensure T/I/R volumes respect Daniels' limits.

**Returns**: `overall_ok`, `violations` (list), `pace_limits` (recommended maximums)

**Daniels' limits**:
- T-pace (Threshold): ≤10% of weekly volume
- I-pace (Interval): ≤8% of weekly volume
- R-pace (Repetition): ≤5% of weekly volume

**When to use**: When designing or reviewing quality workout weeks

---

## Long Run Caps

```bash
sce guardrails long-run --duration 135 --weekly-volume 55 --pct-limit 30
```

**Use**: Validate long run doesn't exceed duration (150min) or percentage (30%) limits.

**Returns**: `pct_ok`, `duration_ok`, `violations`

**Pfitzinger guidelines**:
- Maximum duration: 150 minutes (fatigue accumulation)
- Maximum percentage: 30% of weekly volume (session dominance)

**When to use**: When planning long runs, if athlete reports excessive fatigue after long runs

---

## Break Return

```bash
sce guardrails break-return --days 21 --ctl 44 --cross-training moderate
```

**Use**: Calculate safe return volume after training break.

**Returns**: `recommended_start_volume_km`, `buildup_weeks`, `progression_rate_pct`

**When to use**: After illness, injury, or vacation (>7 days off)

---

## Illness Recovery

```bash
sce guardrails illness-recovery --severity moderate --days-missed 7
```

**Use**: Determine safe return protocol after illness.

**Returns**: `can_resume_immediately`, `recommended_easy_days`, `volume_reduction_pct`

**Severity levels**:
- `minor`: Above-neck symptoms (sniffles, sore throat)
- `moderate`: Below-neck but no fever (body aches, fatigue)
- `severe`: Fever, flu, significant illness

**When to use**: When athlete reports illness or returns from illness

---

## Integration with Risk Assessment

**All guardrails inform risk mitigation recommendations**. Use them proactively:
- Before planning adjustments
- When explaining rationale to athlete
- To validate proposed modifications
- As evidence for conservative recommendations
