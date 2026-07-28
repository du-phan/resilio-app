---
name: first-session
description: Onboard new athletes with complete setup workflow including authentication, activity sync, profile creation, goal setting, and constraints discussion. Use when athlete requests "let's get started", "set up my profile", "new athlete onboarding", or "first time using the system".
---

# First session

Guide the athlete from account validation through a data-grounded profile,
goal, constraints, and the planning approval sequence. Keep athlete language
natural: never expose skill names, commands, tools, or local file paths.

## Prerequisite

The CLI must be runnable. If it is not, use the complete setup procedure first.
Do not mix Poetry and virtual-environment commands in one session.

## 1. Validate the account

Run `resilio auth status`.

If the key is missing, ask the athlete for their personal Intervals.icu API
key from the Intervals.icu settings page. Save only:

```text
INTERVALS_ICU_API_KEY=<key>
```

in `.env.local` with file mode `0600`, then retry validation. Never echo,
inspect, or include the key in a report. Authentication and authorization
rejections are distinct from missing configuration; explain the relevant
outcome without showing response bodies.

Tell athletes using the free account that they should log in at least once
every 90 days; a dormant account stops processing new files.

## 2. Import and establish the factual baseline

Run `resilio sync`, followed immediately by `resilio profile analyze`.

Report:

- created, linked, updated, unchanged, hidden, ambiguous, and quarantined
  counts from the sync response;
- the actual `synced_data_start`, `synced_data_end`, and `data_window_days`;
- whether the run is complete or partial.

Never claim a fixed history duration. A partial run is useful but must be
identified plainly. Ambiguous or invalid rows remain under review and must not
be described as imported.

Completed Garmin, Wahoo, manually entered, climbing, bouldering, yoga,
strength, and other activities are recorded in Intervals.icu and then
normalized locally. Rock climbing and bouldering both contribute to `climb`.

## 3. Review data before asking factual questions

Run:

```bash
resilio dates today
resilio status
resilio profile get
resilio memory list --type INJURY_HISTORY
resilio performance baseline
```

Use imported activity facts for consistency, gaps, training frequency, sport
distribution, recent volume, heart-rate observations, and performance clues.
Ask only for context the data cannot supply.

For a notable training gap, ask one contextual question and wait:

> I noticed a gap from DATE to DATE. Was that injury, illness, planned rest,
> or something else?

Record material injury, illness, schedule, motivation, and preference facts
through the memory/profile surfaces after the athlete confirms them.

## 4. Collect and confirm the profile

Factual inputs may be batched:

- name and age;
- running experience;
- known maximum and resting heart rate;
- typical training days and session-duration limits;
- home location for weather planning.

Use the athlete-facing prompt: “Where do you usually train?” Store a city or
region sufficient for the forecast command; do not ask the athlete to supply
forecast conditions. Persist the confirmed value with the profile
`--weather-location` option.

Then discuss one context topic at a time:

- recurring injuries or current pain;
- motivation;
- running priority relative to other sports;
- fixed sport sessions and recovery constraints.

`other_sports` must match the observed activity distribution for every sport
above the configured significance threshold. `running_priority` is only the
conflict strategy. Validate the profile after changes.

## 5. Set and validate the goal

Collect goal type, race date, and target time as free-form factual inputs. Use
the goal command so feasibility is evaluated against the performance baseline
and weeks available. Present concrete evidence and alternatives when the goal
is ambitious; wait for the athlete’s choice before planning.

Follow [goal validation](references/goal_validation.md).

## 6. Explain metrics once

On first mention, use plain language:

- VDOT: running fitness estimate used to set appropriate paces.
- CTL: longer-term fitness from recent total training load.
- ATL: short-term fatigue.
- TSB: fitness minus fatigue, a freshness/form signal.
- ACWR: recent load relative to the longer-term baseline.
- Readiness: combined current capacity signal.
- RPE: perceived effort on a 1–10 scale.

For multi-sport athletes, say that load includes running plus their other
sports. Do not repeat definitions unless asked.

## 7. Planning approvals

Use this exact ownership sequence:

1. Propose the evidence-backed baseline VDOT.
2. Athlete approves the value.
3. Create and present the complete macro plan review inline.
4. Athlete approves the macro plan.
5. Generate and present the exact weekly JSON contents.
6. Athlete approves that weekly proposal.
7. Apply and verify the approved file.

Executor procedures never ask questions or approve their own proposals. Any
revision is a new proposal.

Before any day-specific schedule recommendation, compute the week boundary and
fetch the weekly forecast. Never ask the athlete for the forecast.

## Completion

Onboarding is complete only when:

- account access is valid;
- sync/profile coverage and any partial state were reported accurately;
- profile and actual sport distribution validate;
- injury history and constraints are recorded;
- the goal is saved and feasibility discussed;
- the athlete has approved the VDOT and macro plan;
- the first weekly plan is generated, approved, applied, and verified.
