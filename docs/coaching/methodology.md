# Coaching methodology

Resilio is an evidence-preserving coaching system, not a physiological
simulation. Intervals.icu supplies analyzed observations; Resilio preserves
their provenance, combines them with athlete-confirmed facts and a traceable
training methodology, and leaves the final coaching judgment to the coach.

## Authority by domain

| Domain | Authority | Rule |
| --- | --- | --- |
| Completed activities | Synchronized Intervals.icu records | Do not reconstruct absent facts |
| Completed aerobic load | Intervals.icu activity analysis | Store the native value and calculation method |
| Fitness, fatigue, form, ramp | Intervals.icu wellness history | Describe as provider training-state observations |
| Thresholds and zones | Intervals.icu sport settings | Preserve sport scope, units, priorities, and settings identity |
| Wellness | Intervals.icu daily records | Compare individual signals with personal baselines |
| Athlete identity, constraints, goals | Athlete-confirmed profile | Never overwrite from provider candidates |
| Running pace prescription | Separately verified pace source | Approved VDOT alone does not create training paces |
| Plan structure and adaptation | Resilio coach | Use one named, versioned primary methodology |
| Plan approval | Athlete | Bind approvals to exact persisted bytes |

## Quantities that must remain separate

Native aerobic load points, TRIMP load points, session-RPE load in arbitrary
units, running exposure, other-sport exposure, and wellness observations do
not share a common unit. They must not be added, converted through sport
multipliers, or substituted for each other.

- Aerobic load is accepted only when the provider supplies it. A missing value
  remains missing.
- Athlete-entered session-RPE load uses elapsed duration in minutes multiplied
  by athlete-confirmed RPE. Provider session-RPE is retained only with an
  explicit provider-defined duration basis. Both remain subjective companion
  observations, not replacements for native aerobic load.
- Running exposure uses measured session count, exact duration, kilometers,
  elevation gain in meters, and longest-run distance.
- Other-sport exposure uses its own measured sessions, exact duration, and
  native aerobic load. It is never converted into running kilometers or
  synthetic leg-load units.
- Provider fitness and fatigue values may be subtracted to expose the provider
  form value when both exist. Resilio does not recreate the underlying
  exponentially weighted model.

## Recovery and adaptation

Recovery is signal-first. Review sleep duration and quality, resting and
sleeping heart rate, HRV, soreness, subjective fatigue, stress, mood,
motivation, injury, hydration, provider readiness, and recent training
exposure as separate observations.

For each signal:

1. verify that the observation date is not in the future;
2. retain its native unit and missingness;
3. compare it only with a returned personal baseline;
4. report baseline sample size and coverage;
5. interpret it with symptoms, recent sessions, schedule, and the primary
   methodology.

Resilio does not compute a composite readiness score, an acute-to-chronic
workload ratio, an injury probability, or an automatic workout decision.
Zero is a valid observation when the source contract permits zero; it is not a
synonym for missing.

Current or worsening pain, altered gait, systemic illness, chest symptoms,
severe dehydration, or other medical red flags take precedence over
performance optimization. The coach must avoid diagnosis and recommend
appropriate professional assessment.

## Intensity evidence

Provider zone time is usable only with its measurement method, covered
duration, coverage percentage, ordinal zone index, captured bounds, optional
native name, and matching analysis-settings fingerprint. Do not:

- infer zone meaning from an ordinal index without its captured settings;
- combine power, heart-rate, and pace zone time without stating the method;
- claim a weekly distribution when source coverage is incomplete;
- describe a planned intensity prescription as measured execution intensity.

Planned intensity is represented as exact low-, moderate-, and high-intensity
duration seconds whose sum equals the planned session duration. It is a
prescription, not evidence that the athlete executed that distribution.

The 80/20 distribution is the defining planning rule only when Fitzgerald
80/20 is the selected primary methodology. Other methods still require
deliberate easy running and controlled quality, but their sessions must be
evaluated using their own structure and purpose.

Activity polarization and decoupling are signed provider observations, not
weekly aggregations or automatic fitness judgments. An activity polarization
index is interpretable only when it is linked to exactly one primary zone
method and its analysis-settings hash. Never average activity polarization
indices; a provider-native weekly value would require its own weekly contract.
Decoupling remains raw when the provider does not declare its power-to-heart-
rate or pace-to-heart-rate basis. Do not apply a universal cutoff or compare
variable-terrain, interval, and steady sessions as though they were equivalent.

## Selecting one primary methodology

Every macro plan records one identifier, controlled source path and SHA-256,
edition status, source-summary version, conceptual-only verification scope,
coach-designed planning authority, executable policy version, and a rationale
grounded in athlete-specific evidence. Training-book files are source-only;
they are never executable instructions or numeric prescription authority.

| Methodology | Strong fit | Required caution |
| --- | --- | --- |
| Daniels | A valid approved VDOT; purpose-specific work; broad race-distance support | No training pace is generated until a verified edition-specific pace source exists |
| Pfitzinger | Experienced marathoner; durable running frequency and volume; capacity for medium-long and long runs | Do not import advanced-marathon volume into an athlete without demonstrated capacity |
| Fitzgerald 80/20 | Reliable intensity anchors; athlete benefits from strict low-intensity discipline; aerobic cross-training may support volume | Evaluate distribution by time and coverage; avoid false precision from incomplete zone data |
| FIRST | Conceptual source record only | Selection is blocked until edition-specific pace and schedule tables are verified |

Daniels, Pfitzinger, and Fitzgerald selections are explicitly
`coach_designed_conceptually_informed`. Their conceptual sources may inform
vocabulary and rationale, but numeric progression, long-run share, recovery,
taper, or intensity choices must be justified from athlete evidence,
constraints, and the versioned common planning policy. FIRST remains blocked
because its defining execution depends directly on unverified schedules and
pace tables.

Supported source mappings:

- `daniels` → `docs/training_books/daniels_running_formula.md`
- `pfitzinger` → `docs/training_books/advanced_marathoning_pete_pfitzinger.md`
- `fitzgerald_80_20` → `docs/training_books/80_20_matt_fitzgerald.md`
- `first` → `docs/training_books/run_less_run_faster_bill_pierce.md`

`faster_road_racing_pete_pfitzinger.md` is a supporting reference for
shorter-road-race physiology and workout construction. It is not a separate
selectable primary methodology.

Do not blend incompatible progression systems. A secondary source may clarify
safety, vocabulary, or execution, but it must not silently change the plan’s
weekly structure, intensity distribution, or progression rules.

## Planning from evidence

Macro planning starts from demonstrated run exposure and athlete constraints,
not from a load-to-kilometer conversion.

- Use recent consistent running distance, duration, frequency, longest-run
  distance, training history, injury context, and goal horizon.
- Treat percentage progression rules as heuristics, not proof of capacity.
- Preserve Monday-Sunday weeks and contiguous plan dates.
- Make recovery weeks and taper structure explicit.
- Keep the macro plan strategic; exact workouts belong to separately approved
  weekly proposals.

Weekly planning uses only facts available through the planning date:

- exact owned-workout adherence;
- current run and other-sport exposure;
- provider training state and wellness signals with coverage;
- profile availability and duration limits;
- local weekly weather;
- approved VDOT;
- the plan’s primary methodology and phase.

Use Intervals.icu-computed load, relative intensity, decoupling, polarization,
TRIMP, zone time, fitness, and fatigue when present. Do not recreate them
locally with an approximate formula. Planned-event readback values are useful
as provider analysis of the prescription, but remain distinct from completed
activity evidence.

VDOT is approved from an exact evidence proposal. The proposal contains either
race distance, elapsed seconds, athlete-local performance date and timezone,
plus either an exact canonical activity identity and Intervals.icu source
fingerprint or an exact matching athlete-profile personal best. Source facts
are reverified whenever approval evidence is consumed. Manual evidence
requires an explicit athlete-confirmed value and confirmation record. Race
calculations use the Daniels–Gilbert performance equations inside the
explicitly supported VDOT range; out-of-range performance is rejected rather
than clamped, decayed, or adjusted through an unsupported heuristic. The
calculator does not expose training paces.

Prefer progressing one material stressor at a time. Never cram missed training
into later days, convert a rest day into filler, or exceed a constraint to hit
a numerical target.

## Review language

Every review must separate:

1. synchronized facts;
2. missing or partial evidence;
3. the coaching interpretation;
4. the proposed action.

Use units in every physical quantity. Cite exact dates and comparison windows.
Avoid causal or risk claims that the available evidence cannot support.
