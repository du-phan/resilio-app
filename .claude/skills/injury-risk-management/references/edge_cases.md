# Edge Cases

Handling unusual injury risk situations.

---

## Edge Case 1: ACWR Safe but Athlete Injured

**Problem**: ACWR 1.10 (safe), but athlete reports knee pain.

**Explanation**: ACWR tracks load spikes, not absolute load capacity. Athlete may have underlying biomechanical issue, previous injury, or environmental factor (e.g., cambered road).

**Action**:
- Don't override subjective pain signals
- Rest or reduce until pain-free
- Check for non-load factors (shoes, surface, form)
- Consider referral to PT if persistent

**Key**: ACWR is a risk indicator, not a guarantee. Always trust athlete's pain reports over metrics.

---

## Edge Case 2: ACWR Elevated but Race in 10 Days

**Problem**: ACWR 1.38, but half marathon in 10 days (taper phase).

**Decision**:
- If due to taper (ATL dropping faster than CTL): Proceed with taper
- If due to training spike: Adjust taper to be more conservative
- Check `sce risk taper-status` for taper-specific risk assessment

**Action**: Extra recovery days during taper, reduce taper runs if needed.

---

## Edge Case 3: Low ACWR (<0.8) During Base Phase

**Problem**: ACWR 0.75, athlete feels undertrained.

**Explanation**: ACWR <0.8 indicates training load is below athlete's adapted capacity. Detraining risk (fitness loss) > injury risk.

**Action**: Increase volume gradually (+10% per week) to bring ACWR to 1.0-1.15 (optimal adaptation zone).

**Note**: Low ACWR is a signal to increase training load, not a risk flag.

---

## Edge Case 4: ACWR Spike After Recovery Week

**Problem**: Recovery week → ACWR jumps to 1.4 when returning to normal volume.

**Explanation**: ATL drops during recovery week, creating denominator effect (high acute load ÷ low chronic baseline = high ACWR).

**Action**: Post-recovery week should be +5-10% from pre-recovery baseline, NOT +X% from recovery week. This prevents artificial ACWR spike.

**Example**:
- Week 3: 50km (pre-recovery)
- Week 4: 35km (recovery)
- Week 5: 52-55km (+5-10% from Week 3, not from Week 4)
