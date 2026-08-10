# Athlete-managed sports

Resilio prescribes running and accounts for every physical activity. It does
not schedule or publish non-running sessions.

Two authorities stay separate:

- synchronized completed activities are factual observed exposure;
- profile entries are athlete-confirmed expectations about future
  participation.

An athlete-managed sport has one participation pattern:

- `flexible_weekly` records only an expected session count. The athlete chooses
  every date, so the run planner must not invent one;
- `recurring_weekly` records durable weekdays and whether running on the same
  day is allowed. A prohibited same-day setting is a hard run-placement
  constraint.

Both patterns retain typical session duration, athlete-reported typical
intensity, active or paused state, and optional context. A single discriminated
priority says whether running, balanced training, or one active
athlete-managed sport wins when recovery evidence requires a tradeoff.

Macro and assessment plans contain run targets and empty
`running_workouts` skeletons. Exact weekly proposals contain only running
workouts. Each proposal references an immutable planning context and includes
one auditable consideration for every configured athlete-managed sport and
every non-running sport observed in that context. The consideration binds exact
recent activity IDs and records its effect on run volume, frequency, intensity,
day placement, recovery spacing, or explicitly no adjustment.

Changing a planning-relevant expectation or priority invalidates the active
plan through the coordinated profile/planning transaction. Pausing or removing
the sport named by an athlete-managed-sport-first priority first requires a
new valid priority; the profile never persists an impossible reference.
