# Planning and publication

Training plans remain local and follow the required VDOT → macro → weekly
approval sequence documented in the shared agent workflow.

Every publishable planned workout has a required sport and a typed recursive
`structured_workout`. Steps may be steady, ramp, or repeat; durations use
seconds, metres, or a lap-button variant with nominal duration; targets use
unit-explicit pace, heart rate, or power.

```bash
resilio workout publish --id <local-workout-id> [--time HH:MM]
resilio workout publish-plan [--from YYYY-MM-DD]
resilio workout delete --id <local-workout-id>
```

Rest days and unstructured workouts are never published. Publication uses a
deterministic UID and `resilio:v1:workout:` external-ID namespace. A local
manifest plus remote UID/external-ID read-back proves ownership before update,
reschedule, or deletion.

`publish-plan` reconciles every structured workout on or after the selected
date. Unchanged workouts are no-ops; a workout or sport-settings change updates
the same owned event. Workouts present only in the publication manifest are
reported as stale and are never deleted automatically. A partial result lists
per-workout errors while retaining each previously verified mutation.

Pace targets require threshold pace and pace zones. Power targets require FTP.
Mixed target modes and lap-button steps fail closed for Wahoo. Garmin and
Wahoo forward approximately the next seven days; their upload filters must
include the sport, and Wahoo-related timezones must agree.

Completed activities carrying an exact calendar-event pairing are linked to
the local workout in a provider-neutral completion manifest. When no exact
pair is available, a unique date/sport/time candidate is report-only and never
changes either record.
