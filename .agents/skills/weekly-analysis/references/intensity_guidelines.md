# Intensity Distribution Guidelines (80/20 Principle)

## Core Philosophy

**Elite endurance athletes spend ~80% of training at low intensity.** This maximizes aerobic development while minimizing injury risk and allowing recovery for quality sessions.

The 80/20 principle is grounded in decades of research and elite athlete training patterns. It's not arbitrary - it's how the best endurance athletes in the world train.

## Intensity Zones

### Low Intensity (80% of volume)
- **Zones**: Z1-Z2
- **RPE**: 3-5 (conversational pace)
- **Purpose**: Build aerobic base, capillary density, mitochondrial function
- **Key characteristic**: You can talk in full sentences
- **Common mistake**: Running these too hard

### Moderate+High Intensity (20% of volume)
- **Zones**: Z3-Z5
- **RPE**: 7-9 (tempo to intervals)
- **Purpose**: Lactate threshold, VO2max, race-specific fitness
- **Types**: Tempo runs, intervals, threshold work, race-pace efforts

## Common Violations

### 1. Moderate-Intensity Rut
**Pattern**: 65% easy, 35% moderate+hard

**Problem**: Everything ends up at medium effort (RPE 5-6) - the "gray zone"
- Too hard to build aerobic base
- Not hard enough for quality adaptations
- Accumulates fatigue without performance gains

**Fix**: Polarize training - make easy truly easy, hard truly hard

### 2. Easy Runs Too Fast
**Pattern**: 75% easy, 25% hard (closer, but easy runs at RPE 6)

**Problem**: "Easy" runs are actually tempo pace
- Prevents recovery for quality sessions
- Increases injury risk
- Reduces capacity for hard efforts

**Fix**: Slow down easy runs by 30-60 seconds per km

### 3. Poor Polarization
**Pattern**: Lots of RPE 6 efforts (neither easy nor hard)

**Problem**: Training lacks clear separation between intensity zones
- Chronic fatigue
- Diminished adaptation signals
- Harder to recover

**Fix**: Binary approach - RPE 3-4 or RPE 8-9, nothing in between

## Interpretation Zones

From `sce analysis intensity`:

- **≥75% low intensity**: Compliant (excellent)
- **70-74% low intensity**: Borderline (acceptable)
- **60-69% low intensity**: Moderate-intensity rut (concerning)
- **<60% low intensity**: Severe imbalance (high risk)

## Why 80/20 Works

### Physiological Adaptations from Easy Volume
1. **Capillary density**: More blood vessels to muscles
2. **Mitochondrial function**: Better aerobic energy production
3. **Fat oxidation**: Improved endurance fuel utilization
4. **Economy**: More efficient running mechanics
5. **Recovery capacity**: Faster adaptation between hard sessions

### The Role of Hard Training
- **20% hard work provides the stimulus** for race-specific fitness
- **80% easy work provides the foundation** to absorb that stimulus
- Without the foundation, hard work just breaks you down

## Common Coaching Scenarios

### Athlete Says: "Easy runs feel too slow"
**Response**: "That's normal - you're used to running medium-hard all the time. Give it 2 weeks and you'll notice:
1. You recover faster between runs
2. Quality sessions feel more manageable
3. Overall volume increases without fatigue
4. Injury risk drops

The 'too slow' feeling is a sign you're doing it right."

### Athlete Says: "But I feel good, I want to go faster"
**Response**: "That's the trap - feeling good on an easy run means it's working. Save that energy for the quality sessions where it matters. Easy runs aren't about fitness gains - they're about building durability and preparing you to crush the hard sessions."

### Athlete Says: "My average pace is dropping"
**Response**: "That's actually good! Your *easy pace* should be slow. Your *hard pace* should be fast. We want a big separation between the two. Average pace is meaningless - it's the distribution that matters."

## Detailed Decision Tree: Intensity Violations

### Q: Distribution is 65% easy, 35% moderate+hard (Moderate-Intensity Rut)

**Step 1: Diagnose the problem**
```bash
# Review actual paces vs prescribed zones
sce analysis intensity --activities [FILE] --days 7 --detail
```

Look for:
- Easy runs at RPE 5-6 (should be 3-4)
- Lack of true easy efforts
- Lack of true hard efforts

**Step 2: Explain to athlete**
```
Your intensity distribution this week was 65/35 (should be ~80/20). This means too much moderate-intensity work (RPE 5-6) - the "gray zone".

Why this matters:
- Moderate intensity doesn't provide enough stimulus for adaptation (not hard enough)
- But it's too hard to recover from (not easy enough)
- Result: Fatigue accumulates without performance gains

Looking at your runs:
- Tuesday easy: 6:00/km pace → RPE 6 (should be RPE 3-4 at 6:45-7:15/km)
- Thursday easy: 5:45/km pace → RPE 6 (should be RPE 3-4)
- Your "easy" runs are actually tempo pace
```

**Step 3: Provide specific pace targets**
```bash
# Get prescribed easy pace from VDOT
sce vdot paces --vdot [ATHLETE_VDOT]
```

**Step 4: Set next week's plan**
```
Next week:
- Slow down easy runs to conversational pace (you should be able to talk in full sentences)
- Target: 6:45-7:15/km for easy (based on your VDOT 48)
- Check: If you can't talk easily, slow down
- This will feel "too slow" at first - that's normal. Easy runs build aerobic base without fatigue.
```

**Step 5: Check compliance next week**
Follow up in next weekly review to ensure athlete adjusted pace.

### Q: Athlete consistently runs easy pace too fast (3+ weeks)

**Capture as memory**:
```bash
sce memory add --type TRAINING_RESPONSE \
  --content "Easy runs consistently 0.5-1.0 min/km too fast (RPE 6 instead of 4)" \
  --tags "intensity:easy,violation:pace,pattern:consistent" \
  --confidence high
```

**Consider deeper intervention**:
1. Review motivation: Is athlete ego-driven about pace?
2. Education: Send 80/20 reading material
3. Accountability: Require HR data for easy runs
4. Adjustment: Prescribe heart rate caps (not pace) for easy days

## Research Foundation

**Key Studies**:
- Seiler & Kjerland (2006): Elite runners spend 75-80% of training at low intensity
- Esteve-Lanao et al. (2007): 80/20 group improved more than 65/35 group
- Stoggl & Sperlich (2014): Polarized training superior to threshold-focused

**Elite athlete patterns**:
- Marathon world record holders: ~80% easy, ~20% hard
- Olympic medalists across endurance sports: Similar distribution
- Recreational athletes: Often 60% easy, 40% moderate+hard (wrong)

## Additional Resources

- **Matt Fitzgerald's 80/20 Running**: Complete book in [docs/training_books/80_20_matt_fitzgerald.md](../../../docs/training_books/80_20_matt_fitzgerald.md)
- **Seiler's Talk Faster Podcast**: Discussion of intensity distribution research
