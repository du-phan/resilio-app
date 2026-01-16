---
name: injury-risk-management
description: Proactive injury risk assessment and mitigation strategies. Use when athlete asks "Am I at risk?", "injury probability", "too much training?", "should I be concerned about [metric]?", or when you detect elevated ACWR (>1.3), rapid volume increases, or concerning adaptation triggers.
allowed-tools: Bash, Read, Write, AskUserQuestion
context: fork
agent: general-purpose
---

# Injury Risk Management

## Overview

This skill provides **proactive injury risk assessment** and **evidence-based mitigation strategies** to prevent overuse injuries before they occur.

**Philosophy**: The best injury is the one that never happens. Use data (ACWR, CTL trends, adaptation triggers) to identify risk early and adjust training before breakdown occurs.

**Core concept**: Injury risk is multifactorial - training load spikes, inadequate recovery, intensity errors, multi-sport interactions, and environmental factors all contribute. This skill integrates all signals into actionable recommendations.

---

## Core Workflow

### Step 1: Assess Current Risk

**Run risk assessment**:
```bash
sce risk assess --metrics metrics.json --recent activities.json
```

**Returns**:
```json
{
  "ok": true,
  "data": {
    "overall_risk": "low",
    "risk_score": 12,
    "acwr": {
      "value": 1.15,
      "zone": "safe",
      "interpretation": "Training load is well-balanced"
    },
    "contributing_factors": [
      {
        "factor": "volume_increase",
        "severity": "low",
        "description": "Weekly volume increased 8% (within 10% rule)"
      }
    ],
    "red_flags": [],
    "recommendations": [
      "Continue current training approach",
      "Monitor ACWR weekly to maintain <1.3"
    ]
  }
}
```

**Parse key fields**:
- `overall_risk`: low / moderate / high / very_high
- `risk_score`: 0-100 (higher = more risk)
- `acwr.zone`: safe / caution / danger
- `contributing_factors`: List of risk contributors
- `red_flags`: Immediate concerns requiring action
- `recommendations`: Specific mitigation steps

---

### Step 2: Understand Risk Factors

**Contributing factors** (from risk assess output):

| Factor | Severity | Description | Typical Causes |
|--------|----------|-------------|----------------|
| **volume_increase** | low/moderate/high | Weekly volume increased too rapidly | Violates 10% rule |
| **acwr_spike** | moderate/high | ACWR >1.3 (caution) or >1.5 (danger) | Sudden training load increase |
| **session_density** | moderate/high | Hard sessions too close together | Back-to-back quality workouts |
| **inadequate_recovery** | moderate/high | TSB consistently <-20 | Overreaching without recovery weeks |
| **intensity_distribution** | low/moderate | Too much moderate/hard intensity | Violates 80/20 rule |
| **multi_sport_conflict** | low/moderate | Climbing/cycling before quality run | Lower-body fatigue accumulation |
| **long_run_excessive** | moderate/high | Long run >30% of weekly volume or >150min | Single session dominates week |
| **quality_volume_high** | moderate/high | T-pace >10%, I-pace >8%, R-pace >5% | Daniels limits exceeded |
| **readiness_low** | moderate/high | Readiness <50 consistently | Fatigue, illness, stress |
| **injury_history** | moderate/high | Previous injury in same area | Re-injury risk elevated |

**Severity interpretation**:
- **Low**: Monitor, no immediate action needed
- **Moderate**: Adjust training within 1-2 days
- **High**: Immediate action required (rest, downgrade, or move workout)

---

### Step 3: Forecast Future Risk

**Project risk across upcoming weeks**:
```bash
sce risk forecast --weeks 4 --metrics metrics.json --plan plan.json
```

**Returns**:
```json
{
  "ok": true,
  "data": {
    "forecast": [
      {
        "week": 1,
        "projected_ctl": 46.2,
        "projected_atl": 52.1,
        "projected_tsb": -5.9,
        "projected_acwr": 1.13,
        "risk_level": "low",
        "notes": "Normal progression"
      },
      {
        "week": 2,
        "projected_ctl": 48.8,
        "projected_atl": 58.3,
        "projected_tsb": -9.5,
        "projected_acwr": 1.19,
        "risk_level": "low",
        "notes": "Build week - monitor closely"
      },
      {
        "week": 3,
        "projected_ctl": 51.6,
        "projected_atl": 64.7,
        "projected_tsb": -13.1,
        "projected_acwr": 1.25,
        "risk_level": "moderate",
        "notes": "ACWR approaching caution zone"
      },
      {
        "week": 4,
        "projected_ctl": 52.3,
        "projected_atl": 45.6,
        "projected_tsb": 6.7,
        "projected_acwr": 0.87,
        "risk_level": "low",
        "notes": "Recovery week - risk drops"
      }
    ],
    "peak_risk_week": 3,
    "warnings": [
      "Week 3: ACWR reaches 1.25 (approaching caution zone)"
    ],
    "recommendations": [
      "Schedule recovery week after Week 3",
      "Monitor readiness closely during Week 3",
      "Consider moving Week 3 quality session if readiness <50"
    ]
  }
}
```

**Key fields**:
- `forecast`: Week-by-week projections
- `peak_risk_week`: Week with highest injury risk
- `warnings`: Specific concerns to address
- `recommendations`: Proactive adjustments

**Use forecast to**:
- Identify upcoming risk spikes
- Validate recovery week placement
- Adjust plan before problems occur

---

### Step 4: Present Risk Analysis

**Create risk report** (`/tmp/injury_risk_report_YYYY_MM_DD.md`):

```markdown
# Injury Risk Assessment

**Date**: [YYYY-MM-DD]
**Athlete**: [Name]
**Current Phase**: [Base/Build/Peak/Taper]

---

## Current Risk Status

**Overall Risk**: [LOW/MODERATE/HIGH/VERY HIGH]
**Risk Score**: [X/100]

**Key Metrics**:
- **ACWR**: [Value] ([Zone]: [Interpretation])
- **TSB**: [Value] ([Interpretation])
- **CTL**: [Value] ([Trend])
- **Readiness**: [Value] ([Interpretation])

---

## Contributing Factors

[If none, state "No significant risk factors detected"]

### [Factor Name] - [Severity]
**Issue**: [Description]
**Impact**: [Explanation of how this increases injury risk]
**Evidence**: [Specific data - ACWR value, volume increase %, etc.]

[Repeat for each contributing factor]

---

## Red Flags

[If none, state "No immediate red flags"]

- [Red flag 1 with specific concern]
- [Red flag 2 with specific concern]

---

## 4-Week Risk Forecast

| Week | CTL | ACWR | Risk Level | Notes |
|------|-----|------|------------|-------|
| 1    | [X] | [Y]  | [Level]    | [Notes] |
| 2    | [X] | [Y]  | [Level]    | [Notes] |
| 3    | [X] | [Y]  | [Level]    | **[Warning if applicable]** |
| 4    | [X] | [Y]  | [Level]    | [Notes] |

**Peak Risk**: Week [N] (ACWR [Value])

---

## Mitigation Recommendations

### Immediate Actions (This Week)
1. [Action 1 with specific guidance]
2. [Action 2 with specific guidance]

### Short-Term Adjustments (Next 2-4 Weeks)
1. [Adjustment 1 with rationale]
2. [Adjustment 2 with rationale]

### Long-Term Strategy
1. [Strategy 1]
2. [Strategy 2]

---

## Monitoring Plan

**Check these metrics**:
- [Metric 1]: [Target range/threshold]
- [Metric 2]: [Target range/threshold]

**Frequency**: [Daily / Weekly]

**Warning signs to watch**:
- [Sign 1: e.g., "Persistent soreness >48 hours"]
- [Sign 2: e.g., "Readiness <35 for 3+ consecutive days"]
- [Sign 3: e.g., "Pain that changes running form"]

---

## Next Steps

[Choose appropriate action based on risk level]

**If risk is LOW**:
- Continue current training
- Monitor weekly with `sce status` and `sce week`
- Re-assess if metrics change significantly

**If risk is MODERATE**:
- [Specific adjustment needed]
- Use AskUserQuestion to present options
- Re-run risk forecast after adjustment

**If risk is HIGH**:
- Immediate downgrade or rest recommended
- Present options with clear trade-offs
- Consider plan adaptation (use plan-adaptation skill)
```

**Present to athlete**:
- Summarize key findings (2-3 sentences)
- Highlight most important metric (usually ACWR)
- Explain "why this matters" in plain language
- Reference actual data (not generic advice)
- Provide actionable next steps

---

### Step 5: Implement Mitigation Strategy

Based on risk level, choose appropriate action:

#### Risk Level: LOW (Score 0-25, ACWR <1.15)

**Action**: Monitor and continue

**Messaging**:
> "Your injury risk is low. ACWR is 1.08 (safe zone), CTL is building steadily at 44, and recovery patterns are good. Continue your current training approach and check back weekly."

**No plan changes needed**.

#### Risk Level: MODERATE (Score 26-50, ACWR 1.15-1.3)

**Action**: Proactive adjustment

**Options to present** (use AskUserQuestion):

**Option A**: Add recovery day
- Skip one easy run this week
- Reduces ACWR to <1.15 by end of week
- No impact on quality sessions

**Option B**: Downgrade next quality session
- Convert Thursday tempo to easy run
- Maintains volume, reduces intensity load
- Preserves long run on weekend

**Option C**: Insert recovery week early
- Drop volume 30% this week
- Next week resume normal progression
- Slight delay in CTL buildup

**Messaging template**:
> "Your ACWR is 1.22 (approaching caution zone at 1.3). Contributing factor: You increased volume 12% last week (exceeds 10% rule).
>
> I recommend [Option A/B/C] because [specific rationale based on athlete's context].
>
> What would you prefer?"

#### Risk Level: HIGH (Score 51-75, ACWR 1.3-1.5)

**Action**: Immediate adjustment required

**Recommended approach**:
1. **This week**: Reduce volume by 20-30% (easy runs only, no quality)
2. **Next week**: Resume at 90% of current volume
3. **Monitor closely**: Check readiness daily

**Use AskUserQuestion** ONLY if athlete pushes back. Otherwise, present as strong recommendation:

> "Your ACWR is 1.38 (caution zone - injury risk 1.5-2x baseline). I strongly recommend reducing volume this week to 30km (down from planned 42km).
>
> Rationale: Your ATL (acute load) is 58 AU, significantly higher than your 42-day average (CTL 42). This spike increases injury risk.
>
> Proposed adjustment:
> - Replace Thursday tempo with easy 30min run
> - Shorten Saturday long run from 18km to 12km
> - Keep other easy runs as planned
>
> This will bring ACWR back to 1.15 (safe) by next week while maintaining fitness.
>
> Does this work for you?"

#### Risk Level: VERY HIGH (Score 76-100, ACWR >1.5)

**Action**: Immediate rest or drastic reduction

**Recommended approach**:
1. **This week**: Rest 2-3 days OR easy runs only (RPE 2-3, 20-30min)
2. **Next week**: 50% volume reduction, easy runs only
3. **Week 3**: Gradual buildup (+10% per week)
4. **Re-assess plan**: Use plan-adaptation skill for replanning

**Messaging** (directive, not optional):

> "⚠️ Your ACWR is 1.62 (danger zone - injury risk 2-4x baseline). Immediate action is required.
>
> I recommend taking 2 rest days this week, then resuming with easy 20-30min runs only.
>
> Current state:
> - ATL: 68 AU (7-day average)
> - CTL: 42 AU (42-day average)
> - ACWR: 1.62 (very high risk)
> - Contributing factors: [List from risk assess]
>
> Continuing at current load significantly increases injury probability. Let's reset training load and rebuild safely.
>
> After 2 rest days, we'll adjust your plan using a conservative buildup. This protects your long-term goal - a minor setback now is better than a major injury later."

---

## Decision Trees

### Q: ACWR is elevated but athlete feels great. Proceed or adjust?

**Factors to consider**:
1. **How elevated?**
   - 1.3-1.35: Small violation, feel often accurate
   - 1.35-1.5: Moderate violation, injury risk real even if asymptomatic
   - >1.5: High violation, feel is unreliable

2. **What's causing it?**
   - Recent illness return: Be cautious (immune system compromised)
   - Volume spike: Adjust (tissue needs time to adapt)
   - Multi-sport load: Check lower-body load specifically

3. **Athlete history**:
   - Recent injury: Err on caution
   - Clean injury history + high CTL: More tolerance for ACWR 1.3-1.35
   - Newer athlete (<1 year training): Strict adherence to ACWR <1.3

**Decision**:
- ACWR 1.3-1.35 + feels great + experienced + no red flags → Proceed with monitoring
- ACWR >1.35 OR any red flags → Adjust regardless of feel

**Use risk forecast** to check if current ACWR is temporary spike or ongoing pattern.

### Q: Should I recommend rest day or downgrade workout?

**Rest day** when:
- Readiness <35 (very low)
- TSB <-25 (overreached)
- Multiple red flags (ACWR + low readiness + TSB)
- Athlete reports pain or persistent soreness

**Downgrade workout** when:
- Readiness 35-50 (low to moderate)
- ACWR 1.3-1.4 (caution zone)
- Single risk factor (e.g., volume increase but readiness OK)
- Athlete feels fatigued but not ill/injured

**Proceed with modification** when:
- Readiness 50-70 (moderate)
- ACWR 1.15-1.3 (borderline)
- Option: Reduce workout duration or intensity slightly

### Q: When should I trigger plan-adaptation skill?

**Trigger plan-adaptation** when:
1. Risk level HIGH or VERY HIGH for 2+ consecutive weeks
2. Multiple weeks need adjustment (not just current week)
3. Athlete has injury symptoms (pain, persistent soreness)
4. ACWR forecast shows risk spike lasting 3+ weeks

**Use injury-risk-management** when:
- Single-week adjustment sufficient
- Proactive prevention (risk detected early)
- Education and monitoring focus

### Q: How do I handle multi-sport load interactions?

**Check lower-body load specifically**:
```bash
sce analysis load --activities activities.json --days 7 --priority equal
```

**Returns**:
- Systemic load by sport
- Lower-body load by sport
- Fatigue flags

**Interpretation**:
- High climbing systemic load + low climbing lower-body load → Easy run OK, quality run may struggle
- High cycling lower-body load → Delay quality run by 48 hours
- Swimming (minimal lower-body) → No running impact

**Mitigation**:
- Rearrange weekly schedule (see training-plan-design/references/MULTI_SPORT.md)
- Adjust running intensity if multi-sport systemic load high
- Consider other sport as recovery week equivalent if running volume drops

---

## ACWR Risk Zones (Detailed)

| ACWR Range | Zone | Injury Risk | Action Required | Example Scenario |
|------------|------|-------------|-----------------|------------------|
| 0.5-0.8 | Undertraining | Low injury, high detraining risk | Increase load gradually | Returning from break, CTL dropping |
| 0.8-1.0 | Low-normal | Baseline risk | Continue, monitor trends | Steady training, no spikes |
| 1.0-1.15 | Optimal | Baseline risk | Continue, good adaptation zone | Progressive buildup during base phase |
| 1.15-1.3 | Safe-high | Baseline risk | Monitor closely, no action unless sustained | Post-recovery week, temporary spike |
| 1.3-1.4 | Caution | 1.5x baseline risk | Proactive adjustment within 3-7 days | Volume increased 12%, feeling good |
| 1.4-1.5 | High caution | 2x baseline risk | Immediate adjustment (downgrade or rest) | Back-to-back hard weeks, no recovery |
| >1.5 | Danger | 2-4x baseline risk | Immediate rest or drastic reduction | Sudden volume spike, illness return |

**Key insight**: ACWR 1.3 is the inflection point where injury risk starts climbing significantly. Prevention is most effective at 1.15-1.3 (before entering danger zone).

---

## Readiness Score Interpretation

| Readiness | Interpretation | Action |
|-----------|----------------|--------|
| <35 | Very low | Rest or very easy (20min RPE 2) |
| 35-50 | Low | Easy run only, no quality |
| 50-70 | Moderate | Proceed with caution, consider downgrade |
| 70-85 | Good | Proceed as planned |
| >85 | Excellent | Ideal for quality workout |

**Factors affecting readiness**:
- Sleep quality
- Resting heart rate (elevated = low readiness)
- Subjective wellness (mood, energy, soreness)
- Recent training load (TSB)

**Use readiness as gate**:
- Readiness <50 → No quality workouts, even if ACWR safe
- Readiness >70 + ACWR safe → Green light for quality

---

## Common Risk Patterns

### Pattern 1: Post-Recovery Week Spike

**Scenario**: After recovery week (30% volume drop), athlete returns with +15% increase.

**Risk**: ACWR spikes from 0.9 → 1.35 due to low ATL during recovery week.

**Mitigation**: Post-recovery week should increase +5-10% from pre-recovery baseline, NOT from recovery week.

**Example**:
- Week 3: 50km
- Week 4: 35km (recovery, -30%)
- Week 5: 55km (+10% from Week 3, NOT +57% from Week 4)

### Pattern 2: Multi-Sport Overload

**Scenario**: Athlete runs 40km/week + climbs 3x/week (hard sessions).

**Risk**: Systemic load is 1,800 AU (equivalent to 60km running), but ACWR only tracks running (underestimates true load).

**Mitigation**: Use multi-sport load analysis:
```bash
sce analysis load --activities activities.json --days 7 --priority equal
```

Adjust running volume if total systemic load exceeds athlete's capacity.

### Pattern 3: Intensity Distribution Error

**Scenario**: Athlete's easy runs are "moderate" (RPE 5-6), not true easy (RPE 3-4).

**Risk**: Chronic fatigue, no true recovery, leads to overtraining despite ACWR <1.3.

**Mitigation**: Validate 80/20 distribution:
```bash
sce analysis intensity --activities activities.json --days 28
```

If distribution is 70/30 or worse, coach athlete to slow down easy runs.

### Pattern 4: Long Run Domination

**Scenario**: Long run is 22km in 48km week (46% of volume, exceeds 30% guideline).

**Risk**: Single session causes excessive fatigue, other runs suffer, recovery inadequate.

**Mitigation**: Validate long run percentage:
```bash
sce guardrails long-run --duration 135 --weekly-volume 48 --pct-limit 30
```

Reduce long run or increase weekly volume to balance.

### Pattern 5: Session Density

**Scenario**: Tuesday tempo + Thursday intervals + Saturday long run + Sunday cycling (hard).

**Risk**: Hard sessions too close together, no recovery time.

**Mitigation**: Space quality sessions 48-72 hours apart. Check session density in `sce today` output.

---

## Guardrails Integration

**All guardrails commands support injury prevention**:

### Volume Progression
```bash
sce guardrails progression --previous 40 --current 48
```

**Use**: Validate weekly volume increases don't exceed 10% rule.

**Returns**: `ok` (Boolean), `increase_pct`, `safe_max_km`, `violation` (if exceeded)

### Quality Volume Limits
```bash
sce guardrails quality-volume --t-pace 5.0 --i-pace 4.0 --r-pace 2.0 --weekly-volume 50.0
```

**Use**: Ensure T/I/R volumes respect Daniels' limits.

**Returns**: `overall_ok`, `violations` (list), `pace_limits` (recommended maximums)

### Long Run Caps
```bash
sce guardrails long-run --duration 135 --weekly-volume 55 --pct-limit 30
```

**Use**: Validate long run doesn't exceed duration (150min) or percentage (30%) limits.

**Returns**: `pct_ok`, `duration_ok`, `violations`

### Break Return
```bash
sce guardrails break-return --days 21 --ctl 44 --cross-training moderate
```

**Use**: Calculate safe return volume after training break.

**Returns**: `recommended_start_volume_km`, `buildup_weeks`, `progression_rate_pct`

### Illness Recovery
```bash
sce guardrails illness-recovery --severity moderate --days-missed 7
```

**Use**: Determine safe return protocol after illness.

**Returns**: `can_resume_immediately`, `recommended_easy_days`, `volume_reduction_pct`

**All guardrails inform risk mitigation recommendations**.

---

## Visualization: Risk Trajectory

When presenting risk to athlete, use narrative to create mental model:

**Example**:
> "Think of your training load as a curve. Your CTL (fitness) is climbing steadily at 44. Your ATL (fatigue) spiked to 58 this week due to the long run + climbing comp. The gap between these two numbers gives us ACWR: 58 ÷ 44 = 1.32.
>
> When ACWR is 0.8-1.3, your body adapts well. When it crosses 1.3, injury risk increases because fatigue is outpacing your body's ability to recover.
>
> Right now, you're at 1.32 - just over the threshold. One more hard week would push you to 1.4-1.5 (high risk). But if we back off slightly this week, you'll drop back to 1.15 by next week, and we can resume normal progression safely."

**Key elements**:
- Explain what the metrics mean (not just numbers)
- Show the trend (where you're heading)
- Connect to injury risk (why it matters)
- Provide clear action (what to do)

---

## Training Methodology References

**ACWR Research**:
- [Coaching Methodology - ACWR](../../../docs/coaching/methodology.md#acwr-acutechronic-workload-ratio) - Complete ACWR zones, research basis, interpretation

**Injury Prevention**:
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md) - Intensity distribution errors and injury risk
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Volume progression and recovery protocols
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - Quality volume limits

**Adaptation Triggers**:
- [Coaching Methodology - Adaptation](../../../docs/coaching/methodology.md#adaptation-triggers) - Complete trigger definitions and thresholds

---

## Edge Cases

### Edge Case 1: ACWR Safe but Athlete Injured

**Problem**: ACWR 1.10 (safe), but athlete reports knee pain.

**Explanation**: ACWR tracks load spikes, not absolute load capacity. Athlete may have underlying biomechanical issue, previous injury, or environmental factor (e.g., cambered road).

**Action**:
- Don't override subjective pain signals
- Rest or reduce until pain-free
- Check for non-load factors (shoes, surface, form)
- Consider referral to PT if persistent

**Key**: ACWR is a risk indicator, not a guarantee. Always trust athlete's pain reports over metrics.

### Edge Case 2: ACWR Elevated but Race in 10 Days

**Problem**: ACWR 1.38, but half marathon in 10 days (taper phase).

**Decision**:
- If due to taper (ATL dropping faster than CTL): Proceed with taper
- If due to training spike: Adjust taper to be more conservative
- Check `sce risk taper-status` for taper-specific risk assessment

**Action**: Extra recovery days during taper, reduce taper runs if needed.

### Edge Case 3: Low ACWR (<0.8) During Base Phase

**Problem**: ACWR 0.75, athlete feels undertrained.

**Explanation**: ACWR <0.8 indicates training load is below athlete's adapted capacity. Detraining risk (fitness loss) > injury risk.

**Action**: Increase volume gradually (+10% per week) to bring ACWR to 1.0-1.15 (optimal adaptation zone).

### Edge Case 4: ACWR Spike After Recovery Week

**Problem**: Recovery week → ACWR jumps to 1.4 when returning to normal volume.

**Explanation**: ATL drops during recovery week, creating denominator effect (low CTL ÷ low ATL = high ACWR).

**Action**: Post-recovery week should be +5-10% from pre-recovery, NOT +X% from recovery week. This prevents artificial ACWR spike.

---

## Related Skills

- **plan-adaptation**: Use when risk assessment indicates plan changes needed
- **daily-workout**: Use for day-to-day risk-based workout decisions
- **weekly-analysis**: Use to identify patterns contributing to risk
- **training-plan-design**: Use when replanning needed due to injury risk

---

## CLI Command Reference

**Risk Assessment**:
```bash
sce risk assess --metrics metrics.json --recent activities.json
sce risk forecast --weeks 4 --metrics metrics.json --plan plan.json
sce risk taper-status --race-date [YYYY-MM-DD] --metrics metrics.json --recent-weeks recent.json
```

**Guardrails**:
```bash
sce guardrails progression --previous [X] --current [Y]
sce guardrails quality-volume --t-pace [X] --i-pace [Y] --r-pace [Z] --weekly-volume [W]
sce guardrails long-run --duration [M] --weekly-volume [V] --pct-limit 30
sce guardrails break-return --days [N] --ctl [X] --cross-training [level]
sce guardrails illness-recovery --severity [level] --days-missed [N]
```

**Analysis**:
```bash
sce analysis intensity --activities activities.json --days 28
sce analysis load --activities activities.json --days 7 --priority [equal|primary|secondary]
sce status
sce week
```

---

## Output Template

After completing risk assessment, provide structured output:

```
# Injury Risk Assessment Summary

**Overall Risk**: [LOW/MODERATE/HIGH/VERY HIGH]
**Risk Score**: [X/100]
**ACWR**: [Value] ([Zone])

**Key Findings**:
- [Finding 1 with specific data]
- [Finding 2 with specific data]

**Contributing Factors**:
[If none, state "No significant risk factors"]
- [Factor 1]: [Severity] - [Brief description]
- [Factor 2]: [Severity] - [Brief description]

**Recommendations**:
[Specific, actionable steps with rationale]
1. [Recommendation 1]
2. [Recommendation 2]

**Monitoring**:
- [What to watch]: [Threshold/target]
- [Check frequency]: [Daily/Weekly]

**Next Assessment**: [When to re-run risk assessment]
```

---

## Testing Injury Risk Management

**Manual test scenarios**:

1. ACWR 1.08 (safe) → Should return "low risk, continue training"
2. ACWR 1.25 (borderline) → Should return "moderate risk, monitor closely"
3. ACWR 1.38 (caution) → Should return "high risk, immediate adjustment"
4. ACWR 1.58 (danger) → Should return "very high risk, rest or drastic reduction"
5. Multi-sport overload → Should detect via load analysis
6. Intensity distribution error → Should detect via 80/20 analysis
7. Post-recovery week spike → Should recognize and adjust recommendation

**Success criteria**:
- Risk level aligns with ACWR zones
- Contributing factors correctly identified
- Recommendations are specific (not generic)
- Athlete understands why risk matters
- Mitigation strategies are actionable
