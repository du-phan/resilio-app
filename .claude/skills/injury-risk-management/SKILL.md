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

### Step 0: Load Injury History and Patterns

**Before assessing current risk, retrieve relevant injury history, training response patterns, AND recent activity notes.**

```bash
# Retrieve injury history from memories
sce memory list --type INJURY_HISTORY

# Search for pain/injury patterns in memories
sce memory search --query "injury pain soreness"

# Check load tolerance patterns
sce memory search --query "load threshold trigger"

# Check training response patterns
sce memory list --type TRAINING_RESPONSE

# NEW: Search recent activity notes for pain/injury signals
sce activity search --query "pain sore tight discomfort" --since 30d

# NEW: List recent activities with notes for context
sce activity list --since 14d --has-notes
```

**Activity notes are raw athlete input** - the AI coach interprets what's relevant:
- "right ankle felt weird" → flag right ankle for monitoring
- "stopped early due to knee pain" → immediate concern
- "felt tired but no issues" → low concern, general fatigue

**Use retrieved memories to:**
- Identify known injury-prone areas (e.g., "left knee pain after long runs >18km")
- Understand load tolerance thresholds (e.g., "lower-body load >600 AU/week triggers knee soreness")
- Detect frequency-based triggers (e.g., ">3 consecutive running days causes achilles tightness")
- Reference past injury resolution strategies (e.g., "IT band resolved with hip strengthening")

**Example application**:
```
Memory: "Right achilles tightness appears with >3 consecutive running days"
Current plan: 4 consecutive running days scheduled this week
Risk assessment: Flag this proactively - "Your plan has 4 consecutive running days. Based on your history, this may trigger right achilles tightness. Consider adding rest day on day 3."
```

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

For guidance on common injury risk decisions, see [DECISION_TREES.md](references/DECISION_TREES.md):

- ACWR elevated but athlete feels great - Proceed or adjust?
- Should I recommend rest day or downgrade workout?
- When should I trigger plan-adaptation skill?
- How do I handle multi-sport load interactions?

---

## ACWR Risk Zones

See [ACWR_ZONES.md](references/ACWR_ZONES.md) for detailed zone definitions with injury risk multipliers (7 zones from undertraining to danger).

**Key insight**: ACWR 1.3 is the inflection point. Prevention is most effective at 1.15-1.3 (before entering danger zone).

---

## Readiness Score Interpretation

See [READINESS_GUIDE.md](references/READINESS_GUIDE.md) for complete readiness zones and factors.

**Key principle**: Use readiness as a secondary safety gate beyond ACWR.
- Readiness <50 → No quality workouts, even if ACWR safe
- Readiness >70 + ACWR safe → Green light for quality

---

## Common Risk Patterns

See [RISK_PATTERNS.md](references/RISK_PATTERNS.md) for detailed analysis of 5 recognizable patterns:

1. **Post-Recovery Week Spike** - ACWR spike after recovery due to low ATL
2. **Multi-Sport Overload** - Systemic load underestimated when only tracking running
3. **Intensity Distribution Error** - Easy runs too hard (70/30 instead of 80/20)
4. **Long Run Domination** - Single session >30% of weekly volume
5. **Session Density** - Hard sessions too close together

---

## Guardrails Integration

See [GUARDRAILS.md](references/GUARDRAILS.md) for complete guardrails documentation.

**5 key guardrails** that support injury prevention:
- Volume progression (10% rule)
- Quality volume limits (Daniels' T/I/R guidelines)
- Long run caps (150min, 30% volume)
- Break return protocols
- Illness recovery protocols

---

## Risk Communication

See [COMMUNICATION.md](references/COMMUNICATION.md) for techniques on explaining injury risk effectively.

**Key principle**: Create mental models through narrative, not just numbers. Explain what metrics mean, show trends, connect to injury risk, provide clear action.

---

### Step 6: Capture Injury Risk Patterns as Memories

**After assessing risk and implementing mitigation, capture significant patterns for future reference.**

**When to capture**:
- ACWR spike pattern detected 2+ times with consistent trigger
- Athlete reports pain/discomfort with specific load threshold
- Frequency-based injury pattern observed (e.g., consecutive running days)
- Load tolerance threshold identified (e.g., weekly volume limit)
- Successful mitigation strategy that resolved injury risk

**Patterns to capture**:

1. **ACWR spike triggers** (if ACWR >1.4 triggered by specific pattern):
   ```bash
   sce memory add --type INSIGHT \
     --content "ACWR spikes above 1.4 when weekly volume increases >15% or when climbing volume adds >200 AU in same week as long run" \
     --tags "acwr:spike,volume:progression,sport:climbing,injury-risk:high" \
     --confidence high
   ```

2. **Body-specific pain patterns** (if recurring pain reported):
   ```bash
   sce memory add --type INJURY_HISTORY \
     --content "Right achilles tightness appears after 3+ consecutive running days, resolves with rest day insertion" \
     --tags "body:achilles,trigger:frequency,threshold:3-days,solution:rest" \
     --confidence high
   ```

3. **Load tolerance thresholds** (if observed):
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Lower-body load >600 AU/week triggers left knee soreness, stays comfortable below 550 AU" \
     --tags "load:lower-body,body:knee,threshold:600,safe-zone:550" \
     --confidence high
   ```

4. **Multi-sport interaction patterns** (if observed):
   ```bash
   sce memory add --type INSIGHT \
     --content "Hard climbing session (>300 AU lower-body) within 24h before long run increases knee strain risk" \
     --tags "sport:climbing,timing:24h,body:knee,risk:elevated" \
     --confidence medium
   ```

5. **Volume progression limits** (if identified):
   ```bash
   sce memory add --type TRAINING_RESPONSE \
     --content "Weekly volume increases >12% trigger ACWR spikes, 8-10% progression works well" \
     --tags "volume:progression,limit:12%,safe-zone:8-10%,acwr:safe" \
     --confidence high
   ```

6. **Successful mitigation strategies** (if injury risk resolved):
   ```bash
   sce memory add --type INJURY_HISTORY \
     --content "IT band tightness resolved with 2 rest days + hip strengthening exercises, volume capped at 45km for 3 weeks" \
     --tags "body:it-band,solution:rest,solution:strength,volume:cap,status:resolved" \
     --confidence high
   ```

**Guidelines**:
- Capture specific thresholds/numbers (e.g., "ACWR >1.4", "600 AU", "3+ days", ">15%")
- Include both problem AND solution when applicable (e.g., "trigger X causes Y, resolved with Z")
- HIGH confidence for 3+ occurrences, MEDIUM for 2 occurrences
- Tag multiple dimensions: body part, trigger type, threshold, solution
- Reference in future risk assessments to provide personalized context

**Example application in next session**:
```
Memory loaded: "Right achilles tightness after 3+ consecutive running days"
Current plan: Shows 5 consecutive running days next week
Proactive flag: "I notice your plan has 5 consecutive running days. Based on your history with right achilles tightness, let's add a rest day on day 3 or 4 to prevent issues."
```

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

For unusual injury risk situations, see [EDGE_CASES.md](references/EDGE_CASES.md):

1. **ACWR Safe but Athlete Injured** - Trust pain over metrics
2. **ACWR Elevated but Race in 10 Days** - Taper-specific decisions
3. **Low ACWR (<0.8) During Base Phase** - Detraining risk
4. **ACWR Spike After Recovery Week** - Denominator effect mitigation

---

## Related Skills

- **plan-adaptation**: Use when risk assessment indicates plan changes needed
- **daily-workout**: Use for day-to-day risk-based workout decisions
- **weekly-analysis**: Use to identify patterns contributing to risk
- **training-plan-design**: Use when replanning needed due to injury risk

---

## Additional Resources

**Decision support**:
- [Decision Trees](references/DECISION_TREES.md) - Common scenario guidance
- [Edge Cases](references/EDGE_CASES.md) - Handling unusual situations

**Reference material**:
- [ACWR Zones](references/ACWR_ZONES.md) - Detailed zone definitions
- [Readiness Guide](references/READINESS_GUIDE.md) - Daily readiness thresholds
- [Risk Patterns](references/RISK_PATTERNS.md) - 5 recognizable patterns
- [Guardrails](references/GUARDRAILS.md) - Injury prevention commands
- [Communication](references/COMMUNICATION.md) - Risk explanation techniques
- [CLI Reference](references/CLI_REFERENCE.md) - Command quick reference

**Templates**:
- [Risk Analysis Template](templates/risk_analysis.md) - Structured risk report format

**Training methodology**:
- [ACWR Research](../../../docs/coaching/methodology.md#acwr-acutechronic-workload-ratio)
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md)
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md)
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md)
- [Adaptation Triggers](../../../docs/coaching/methodology.md#adaptation-triggers)
