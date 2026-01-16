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
