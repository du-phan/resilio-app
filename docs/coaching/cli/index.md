# Coaching CLI index

All athlete-facing commands return JSON envelopes unless a command explicitly
offers a table format.

## Session and data

- `resilio init` — initialize local directories, settings, and `.env.local`
- `resilio auth status` — validate external account access
- `resilio sync [--full] [--confirm-deletions]` — import completed activities
- `resilio sync --status` — inspect lock/progress/checkpoint state
- `resilio activity-review list|approve|exclude-duplicate` — inspect,
  approve conservative historical matches, or exclude a proven second
  recording of an already-linked activity
- `resilio activity-review quarantines|acknowledge-quarantine` — inspect
  validation exclusions and acknowledge one exact failure fingerprint
- `resilio activity-review deletions` — inspect locally retained activities
  whose external IDs returned `404` before confirming tombstones
- `resilio activity ...` — list, search, export, or inspect segments
- `resilio metrics recompute` — regenerate local daily/weekly metrics
- `resilio profile ...` — inspect, analyze, update, and validate the profile

## Coaching and planning

- `resilio status`, `today`, `week`
- `resilio dates ...`
- `resilio weather week --start YYYY-MM-DD`
- `resilio memory ...`
- `resilio performance ...`, `vdot ...`, `goal ...`
- `resilio plan ...`, `approvals ...`
- `resilio analysis ...`, `guardrails ...`

## Calendar publication and migration

- `resilio workout publish|publish-plan|delete`
- `resilio activity-migration status|dry-run|apply|rollback`

References:

- [Account validation](cli_auth.md)
- [Completed-activity sync](cli_sync.md)
- [Activity commands](cli_activity.md)
- [Historical activity backfill](cli_activity_backfill.md)
- [Data authority](cli_data.md)
- [Local data structure](cli_data_structure.md)
- [Planning and publication](cli_planning.md)
- [Dates](cli_dates.md)
- [Weather](cli_weather.md)
- [Core concepts](core_concepts.md)
