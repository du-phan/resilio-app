# Decision Trees

Decision logic for common injury risk scenarios.

---

## Q: ACWR is elevated but athlete feels great. Proceed or adjust?

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

---

## Q: Should I recommend rest day or downgrade workout?

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

---

## Q: When should I trigger plan-adaptation skill?

**Trigger plan-adaptation** when:
1. Risk level HIGH or VERY HIGH for 2+ consecutive weeks
2. Multiple weeks need adjustment (not just current week)
3. Athlete has injury symptoms (pain, persistent soreness)
4. ACWR forecast shows risk spike lasting 3+ weeks

**Use injury-risk-management** when:
- Single-week adjustment sufficient
- Proactive prevention (risk detected early)
- Education and monitoring focus

---

## Q: How do I handle multi-sport load interactions?

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
