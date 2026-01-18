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

**Core concept**: Injury risk is multifactorial - training load spikes, inadequate recovery, intensity errors, multi-sport interactions all contribute.

---

## Core Workflow

### Step 0: Load Injury History and Patterns

**Before assessing current risk, retrieve relevant history AND recent activity notes.**

```bash
# Retrieve injury history from memories
sce memory list --type INJURY_HISTORY
sce memory search --query "injury pain soreness"
sce memory search --query "load threshold trigger"
sce memory list --type TRAINING_RESPONSE

# Search recent activity notes for pain/injury signals
sce activity search --query "pain sore tight discomfort" --since 30d
sce activity list --since 14d --has-notes
```

**Use retrieved memories to**:
- Identify injury-prone areas (e.g., "left knee pain after long runs >18km")
- Understand load tolerance thresholds
- Detect frequency-based triggers (e.g., ">3 consecutive days causes achilles tightness")
- Reference past injury resolution strategies

**Example application**:
```
Memory: "Right achilles tightness after 3+ consecutive running days"
Current plan: 4 consecutive running days scheduled
Action: Flag proactively - "Your plan has 4 consecutive days. Based on history, consider rest day on day 3."
```

---

### Step 1: Assess Current Risk

```bash
sce risk assess --metrics metrics.json --recent activities.json
```

**Parse key fields**:
- `overall_risk`: low / moderate / high / very_high
- `risk_score`: 0-100 (higher = more risk)
- `acwr.zone`: safe / caution / danger
- `contributing_factors`: List of risk contributors with severity
- `red_flags`: Immediate concerns requiring action
- `recommendations`: Specific mitigation steps

---

### Step 2: Understand Risk Factors

**Contributing factors** (common types):

| Factor | Severity | Typical Causes |
|--------|----------|----------------|
| **volume_increase** | low/moderate/high | Violates 10% rule |
| **acwr_spike** | moderate/high | ACWR >1.3 (caution) or >1.5 (danger) |
| **session_density** | moderate/high | Hard sessions too close together |
| **inadequate_recovery** | moderate/high | TSB consistently <-20 |
| **intensity_distribution** | low/moderate | Too much moderate/hard (violates 80/20) |
| **multi_sport_conflict** | low/moderate | Climbing/cycling before quality run |
| **long_run_excessive** | moderate/high | Long run >30% weekly volume or >150min |
| **quality_volume_high** | moderate/high | Exceeds Daniels limits (T>10%, I>8%, R>5%) |
| **readiness_low** | moderate/high | Readiness <50 consistently |
| **injury_history** | moderate/high | Previous injury in same area |

**Severity interpretation**:
- **Low**: Monitor, no immediate action
- **Moderate**: Adjust training within 1-2 days
- **High**: Immediate action required (rest/downgrade/move workout)

**For complete factor analysis**: See [references/RISK_PATTERNS.md](references/RISK_PATTERNS.md)

---

### Step 3: Forecast Future Risk

```bash
sce risk forecast --weeks 4 --metrics metrics.json --plan plan.json
```

**Returns week-by-week projections**:
- `projected_ctl`, `projected_acwr`, `projected_tsb`
- `risk_level` per week
- `peak_risk_week`: Week with highest injury risk
- `warnings`: Specific concerns
- `recommendations`: Proactive adjustments

**Use forecast to**:
- Identify upcoming risk spikes
- Validate recovery week placement
- Adjust plan before problems occur

---

### Step 4: Present Risk Analysis

**Create risk report** (`/tmp/injury_risk_report_YYYY_MM_DD.md`) using template at [templates/risk_analysis.md](templates/risk_analysis.md).

**Structure**:
1. **Current Risk Status**: Overall risk level, key metrics (ACWR/TSB/CTL/Readiness)
2. **Contributing Factors**: Each factor with severity, issue, impact, evidence
3. **Red Flags**: Immediate concerns (if any)
4. **4-Week Risk Forecast**: Table showing CTL, ACWR, risk level per week
5. **Mitigation Recommendations**: Immediate / short-term / long-term actions
6. **Monitoring Plan**: Metrics to track, frequency, warning signs

**Present to athlete**:
- Summarize key findings (2-3 sentences)
- Highlight most important metric (usually ACWR)
- Explain "why this matters" in plain language
- Reference actual data (not generic advice)
- Provide actionable next steps

---

### Step 5: Implement Mitigation Strategy

**Based on risk level, choose appropriate action:**

#### Risk Level: LOW (Score 0-25, ACWR <1.15)

**Action**: Monitor and continue

**Message**: "Your injury risk is low. ACWR 1.08 (safe), CTL building steadily at 44. Continue current approach, check back weekly."

**No plan changes needed**.

#### Risk Level: MODERATE (Score 26-50, ACWR 1.15-1.3)

**Action**: Proactive adjustment

**Options to present** (use AskUserQuestion):
- **Option A**: Add recovery day
- **Option B**: Downgrade next quality session
- **Option C**: Insert recovery week early

**Message template**:
> "Your ACWR is 1.22 (approaching caution at 1.3). Contributing factor: Volume increased 12% (exceeds 10% rule).
>
> I recommend [Option] because [rationale]. What would you prefer?"

#### Risk Level: HIGH (Score 51-75, ACWR 1.3-1.5)

**Action**: Immediate adjustment required

**Recommended approach**:
1. This week: Reduce volume 20-30% (easy runs only)
2. Next week: Resume at 90% of current volume
3. Monitor closely: Check readiness daily

**Message** (strong recommendation):
> "Your ACWR is 1.38 (caution zone - injury risk 1.5-2x baseline). Strongly recommend reducing volume this week to 30km (from planned 42km).
>
> Rationale: ATL 58 AU significantly higher than CTL 42. This spike increases risk.
>
> Proposed: Replace tempo with easy 30min run, shorten long run 18→12km. Brings ACWR to 1.15 by next week.
>
> Does this work?"

#### Risk Level: VERY HIGH (Score 76-100, ACWR >1.5)

**Action**: Immediate rest or drastic reduction

**Recommended approach**:
1. This week: Rest 2-3 days OR easy runs only (20-30min, RPE 2-3)
2. Next week: 50% volume reduction, easy only
3. Week 3: Gradual buildup (+10%/week)
4. Re-assess plan: Use plan-adaptation skill

**Message** (directive):
> "⚠️ Your ACWR is 1.62 (danger zone - injury risk 2-4x baseline). Immediate action required.
>
> Current state: ATL 68 AU, CTL 42 AU, ACWR 1.62
> Contributing factors: [List]
>
> Recommend 2 rest days this week, then easy 20-30min runs only. Continuing at current load significantly increases injury probability.
>
> After rest, we'll adjust your plan conservatively. Minor setback now better than major injury later."

**For detailed mitigation strategies**: See [references/COMMUNICATION.md](references/COMMUNICATION.md)

---

### Step 6: Capture Injury Risk Patterns as Memories

**After assessing risk and implementing mitigation, capture significant patterns.**

**When to capture**:
- ACWR spike pattern detected 2+ times with consistent trigger
- Athlete reports pain/discomfort with specific load threshold
- Frequency-based injury pattern observed
- Load tolerance threshold identified
- Successful mitigation strategy resolved injury risk

**Examples**:

```bash
# ACWR spike trigger
sce memory add --type INSIGHT \
  --content "ACWR spikes above 1.4 when weekly volume increases >15% or climbing adds >200 AU same week as long run" \
  --tags "acwr:spike,volume:progression,sport:climbing,injury-risk:high" \
  --confidence high

# Body-specific pain pattern
sce memory add --type INJURY_HISTORY \
  --content "Right achilles tightness after 3+ consecutive running days, resolves with rest day insertion" \
  --tags "body:achilles,trigger:frequency,threshold:3-days,solution:rest" \
  --confidence high

# Load tolerance threshold
sce memory add --type TRAINING_RESPONSE \
  --content "Lower-body load >600 AU/week triggers left knee soreness, comfortable below 550 AU" \
  --tags "load:lower-body,body:knee,threshold:600,safe-zone:550" \
  --confidence high
```

**Guidelines**:
- Capture specific thresholds/numbers
- Include both problem AND solution when applicable
- HIGH confidence for 3+ occurrences, MEDIUM for 2
- Tag multiple dimensions: body part, trigger, threshold, solution

---

## Quick Decision Trees

### Q: ACWR elevated but athlete feels great - Proceed or adjust?
1. Trust data over feelings - ACWR is predictive (leading indicator)
2. Feeling good doesn't mean no injury risk
3. Recommend proactive adjustment (reduce by 10-20%)
4. Re-assess after adjustment

### Q: Should I recommend rest day or downgrade workout?
- **ACWR 1.15-1.25**: Downgrade quality to easy (maintains routine)
- **ACWR 1.25-1.35**: Add rest day (drops ATL faster)
- **ACWR >1.35**: Both - rest day + downgrade next quality
- **Consider athlete preference** if in gray zone (1.2-1.3)

### Q: When should I trigger plan-adaptation skill?
- Risk forecast shows persistent high risk (2+ consecutive weeks)
- Athlete has multiple red flags
- Current plan structure fundamentally flawed
- Injury already occurred, need replanning

### Q: How do I handle multi-sport load interactions?
1. Check systemic vs lower-body load breakdown
2. Identify sport contributing most to spike
3. Present trade-off: Reduce running OR reduce other sport
4. Respect athlete's priority setting

**For complete decision guidance**: See [references/DECISION_TREES.md](references/DECISION_TREES.md)

---

## Key Reference Links

**ACWR Risk Zones**: [references/ACWR_ZONES.md](references/ACWR_ZONES.md) - 7 zones from undertraining to danger with injury risk multipliers

**Readiness Interpretation**: [references/READINESS_GUIDE.md](references/READINESS_GUIDE.md) - Complete zones, use readiness as secondary safety gate beyond ACWR

**Common Risk Patterns**: [references/RISK_PATTERNS.md](references/RISK_PATTERNS.md) - 5 recognizable patterns:
1. Post-Recovery Week Spike
2. Multi-Sport Overload
3. Intensity Distribution Error
4. Long Run Domination
5. Session Density

**Guardrails Integration**: [references/GUARDRAILS.md](references/GUARDRAILS.md) - 5 key guardrails:
- Volume progression (10% rule)
- Quality volume limits (Daniels' T/I/R)
- Long run caps (150min, 30% volume)
- Break return protocols
- Illness recovery protocols

**Risk Communication**: [references/COMMUNICATION.md](references/COMMUNICATION.md) - Techniques for explaining risk effectively through narrative mental models

---

## Additional Resources

**Decision support**:
- [Decision Trees](references/DECISION_TREES.md) - Common scenario guidance
- [Edge Cases](references/EDGE_CASES.md) - ACWR safe but injured, ACWR elevated near race, low ACWR detraining, post-recovery spike

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
- [ACWR Research](../../../docs/coaching/methodology.md#acwr-acutechronic-workload-ratio) - Complete zones, research basis
- [80/20 Running](../../../docs/training_books/80_20_matt_fitzgerald.md) - Intensity distribution and injury risk
- [Advanced Marathoning](../../../docs/training_books/advanced_marathoning_pete_pfitzinger.md) - Volume progression protocols
- [Daniels' Running Formula](../../../docs/training_books/daniel_running_formula.md) - Quality volume limits
- [Adaptation Triggers](../../../docs/coaching/methodology.md#adaptation-triggers) - Complete trigger definitions

---

## Related Skills

- **plan-adaptation**: Use when risk assessment indicates plan changes needed
- **daily-workout**: Use for day-to-day risk-based workout decisions
- **weekly-analysis**: Use to identify patterns contributing to risk
- **training-plan-design**: Use when replanning needed due to injury risk
