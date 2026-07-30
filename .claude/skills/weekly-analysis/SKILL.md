---
name: weekly-analysis
description: Review one Monday-Sunday training week or a mid-week check-in using typed Intervals.icu-native coaching context, exact owned-workout adherence, separate run and other-sport exposure, recovery signals, and evidence coverage. Use for “how was my week?”, “how is this week going?”, or single-week plan adherence.
---

# Analyze one week

Keep the response in athlete language and distinguish facts from coaching
judgment.

## Workflow

1. Resolve the Monday and Sunday with:

   ```bash
   poetry run resilio dates week-boundaries --start <DATE>
   ```

2. Set `as_of` to the earlier of today and the week’s Sunday. Never include
   future activities or wellness observations.

3. Fetch:

   ```bash
   poetry run resilio coach context \
     --week-start <MONDAY> \
     --as-of <AS_OF_DATE>
   ```

4. Read `source_evidence_coverage.status` and declared exclusions before
   interpretation. State incomplete, unavailable, or complete-with-exclusions
   evidence explicitly. Read `adherence.status` separately; `no_plan` and
   `unavailable` are not zero adherence. Never replace missing evidence with
   zero or an estimate.

## Interpretation

- Adherence: use only provider-paired completion identities. Do not infer a
  match from date, sport, title, distance, or duration. For a mid-week review,
  count only workouts due through `as_of`; future sessions are not missed.
- Run exposure: report sessions, exact duration, distance in kilometers,
  elevation gain in meters, longest-run distance, and native aerobic load only
  when fully covered. If any run lacks distance or elevation, preserve the
  missing aggregate and report the coverage count.
- Other sports: report sessions, duration, and native aerobic load separately.
  Do not convert them to running equivalents or apply sport multipliers.
- Intensity: report source measurement method, covered seconds, coverage
  percent, measurement unit, provider zone identifiers/bounds, analysis
  settings SHA-256, and provider zone distributions. Do not label anonymous
  provider zone IDs as low/moderate/high without the corresponding sport
  settings. Report due planned low/moderate/high duration seconds separately
  from measured execution.
- Native activity analysis: preserve aerobic load, relative intensity, and
  TRIMP when present. Polarization is raw activity evidence only; never average
  activity values into a week or use an unlinked value to classify intensity.
  Decoupling with `provider_unknown` coupling basis is raw display-only. Do not
  apply a universal cutoff or compare variable-terrain, interval, and steady
  sessions as equivalent. Never reconstruct a missing metric.
- Training state: describe provider fitness, fatigue, form, and ramp values as
  trends or context. Do not turn one value into a prescription.
- Recovery: discuss each available sleep, resting-heart-rate, HRV, soreness,
  fatigue, stress, mood, motivation, hydration, injury, or provider-readiness
  observation separately. Retain each signal’s observation date, age, temporary
  flag, 28-day personal median, and sample count. Do not create a composite
  score.
- Safety: current pain, worsening injury signals, systemic illness, or severe
  symptoms override performance optimization and warrant conservative advice
  or professional assessment.

## Output

Cover:

- the exact review window and whether it is partial;
- due/completed/unmatched adherence;
- run and other-sport exposure;
- key session execution supported by synchronized facts;
- intensity and recovery evidence with coverage limitations;
- one or two evidence-linked patterns;
- practical next steps that remain consistent with the plan’s primary
  methodology.

Do not mutate the plan or log a partial week.
