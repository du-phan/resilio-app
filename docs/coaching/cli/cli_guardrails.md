# Guardrails Commands

> **Quick Links**: [Back to Index](index.md) | [Core Concepts](core_concepts.md)

Volume validation and recovery planning based on Daniels' Running Formula and Pfitzinger's guidelines.

**Commands in this category:**
- `sce guardrails quality-volume` - Validate T/I/R pace volumes
- `sce guardrails progression` - Validate weekly volume progression (10% rule)
- `sce guardrails analyze-progression` - Analyze progression with rich context for AI coaching
- `sce guardrails long-run` - Validate long run limits
- `sce guardrails safe-volume` - Calculate safe volume range
- `sce guardrails break-return` - Generate return-to-training protocol
- `sce guardrails masters-recovery` - Calculate age-specific recovery adjustments
- `sce guardrails race-recovery` - Determine post-race recovery protocol
- `sce guardrails illness-recovery` - Generate return plan after illness

---

## sce guardrails quality-volume

Validate T/I/R pace volumes against Daniels' hard constraints.

**Daniels' Rules:**

- T-pace: ≤ 10% of weekly mileage
- I-pace: ≤ lesser of 10km OR 8% of weekly mileage
- R-pace: ≤ lesser of 8km OR 5% of weekly mileage

**Usage:**

```bash
sce guardrails quality-volume --t-pace 4.5 --i-pace 6.0 --r-pace 2.0 --weekly-volume 50.0
```

**Returns:** `overall_ok`, `violations[]`, pace limits and recommendations.

---

## sce guardrails progression

Validate weekly volume progression (10% rule).

**Usage:**

```bash
sce guardrails progression --previous 40.0 --current 50.0
```

**Returns:** `ok`, `increase_pct`, `safe_max_km`, violation if exceeds 10%.

---

## sce guardrails analyze-progression

Analyze volume progression with rich context for AI coaching decisions.

**Philosophy**: This command provides CONTEXT and INSIGHTS, not pass/fail decisions. Claude Code interprets the data using training methodology knowledge to make intelligent, context-aware decisions.

**Usage:**

```bash
# Basic analysis
sce guardrails analyze-progression --previous 15 --current 20

# Full context (recommended)
sce guardrails analyze-progression \
  --previous 15 \
  --current 20 \
  --ctl 27 \
  --run-days 4 \
  --age 32

# With risk factors
sce guardrails analyze-progression \
  --previous 40 \
  --current 46 \
  --age 52 \
  --recent-injury
```

**Parameters:**
- `--previous` (required): Previous week's volume in km
- `--current` (required): Current week's planned volume in km
- `--ctl` (optional): Current chronic training load
- `--run-days` (optional): Run days per week
- `--age` (optional): Athlete age (flags masters considerations)
- `--recent-injury` (optional): Flag if recent injury (<90 days)

**Returns rich context including:**
- `volume_context`: Volume classification with injury risk factor
- `traditional_10pct_rule`: Traditional 10% rule analysis
- `absolute_load_analysis`: Pfitzinger per-session guideline analysis
- `athlete_context`: CTL-based capacity analysis
- `risk_factors[]`: Identified risk factors with recommendations
- `protective_factors[]`: Factors that reduce injury risk
- `coaching_considerations[]`: Methodology-based guidance
- `methodology_references[]`: Links to training book sections

**See detailed interpretation guidance**: `.claude/skills/macro-plan-create/references/volume_progression_macro.md`

---

## sce guardrails long-run

Validate long run against weekly volume (≤30%) and duration (≤150min) limits.

**Usage:**

```bash
sce guardrails long-run --distance 18.0 --duration 135 --weekly-volume 50.0
```

**Returns:** `pct_ok`, `duration_ok`, `violations[]` with recommendations.

---

## sce guardrails safe-volume

Calculate safe weekly volume range based on current fitness (CTL) and goals.

**Usage:**

```bash
sce guardrails safe-volume --ctl 44.0 --goal half_marathon --age 52
```

**Returns:** `ctl_zone`, `recommended_start/peak_km`, masters adjustments if age 50+.

---

## sce guardrails break-return

Generate return-to-training protocol per Daniels Table 9.2.

**Usage:**

```bash
sce guardrails break-return --days 21 --ctl 44.0 --cross-training moderate
```

**Returns:** Load phases, VDOT adjustment, week-by-week schedule, red flags.

---

## sce guardrails masters-recovery

Calculate age-specific recovery adjustments (Pfitzinger).

**Usage:**

```bash
sce guardrails masters-recovery --age 52 --workout-type vo2max
```

**Returns:** Age bracket, additional recovery days by workout type.

---

## sce guardrails race-recovery

Determine post-race recovery protocol by distance and age.

**Usage:**

```bash
sce guardrails race-recovery --distance half_marathon --age 52 --effort hard
```

**Returns:** Minimum/recommended recovery days, day-by-day schedule.

---

## sce guardrails illness-recovery

Generate structured return-to-training plan after illness.

**Usage:**

```bash
sce guardrails illness-recovery --start-date 2026-01-10 --end-date 2026-01-15 --severity moderate
```

**Returns:** CTL drop estimate, day-by-day return protocol, medical consultation triggers.

---

**Navigation**: [Back to Index](index.md) | [Previous: VDOT Commands](cli_vdot.md) | [Next: Analysis Commands](cli_analysis.md)
