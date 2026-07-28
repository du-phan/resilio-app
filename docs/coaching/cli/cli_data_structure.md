# Local data structure

All paths are relative to the repository root and are ignored where they may
contain athlete or credential data.

```text
.env.local
config/settings.yaml
data/
  activities/YYYY-MM/<local_activity_id>.yaml
  athlete/
  metrics/daily/
  metrics/weekly/
  plans/
  state/
    activity_sync.json
    activity_quarantine_acknowledgements.json
    sync-runs/<run-id>/
    workout_completions.json
    workout_publications.json
  backups/activity-v2/<run-id>/
  migrations/activity-v2/<run-id>/
```

Activity files validate only as `resilio.activity` schema version 2. Filenames
use immutable hashed local IDs, so two same-sport activities in the same minute
cannot overwrite one another.

Raw external payloads are never persisted in the archive. Sync-run reports
contain sanitized decisions and deterministic artifacts. Migration backups are
permission-restricted, hash-manifested, and outside any path switched during
apply.

Profile, metrics, plans, sync state, publication manifests, and activities
form one coordinated state set for backup and rollback.
