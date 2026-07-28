# API layer

The Python API is the presentation-neutral boundary between core services and
the Typer CLI. API modules may depend on schemas and core services. They must
not leak external DTOs or implement transport/domain logic.

## Current surfaces

- `resilio.api.sync.sync_activities` validates configuration, owns the
  Intervals.icu client lifecycle, invokes checkpointed activity sync, and
  returns a typed report/error.
- `resilio.api.publication.publish_workout`, `publish_plan_workouts`, and
  `delete_published_workout` locate local plan workouts and invoke the
  ownership-safe publication service. Plan reconciliation reports stale
  manifest records without deleting them.
- `resilio.api.profile`, `coach`, `plan`, and `vdot` expose provider-neutral
  local coaching operations.
- `resilio.api.reconciliation` exposes current-candidate-bound match approvals
  and exact-fingerprint validation-quarantine acknowledgements.

The CLI converts API results to stable JSON envelopes. Missing credentials,
authentication rejection, authorization rejection, rate limiting, transport,
invalid external payload, unsupported sport, reconciliation ambiguity, and
publication safety are distinct outcomes.

## Dependency rules

```text
schemas <- integrations/mappers <- repositories/core services <- API <- CLI
```

- Core never imports API or CLI.
- API and CLI never pass external DTOs into load, metrics, profile, coaching,
  or planning.
- Tests inject fake environment mappings and clients.
- Automated tests cannot contact a live network.

## Safety

- API errors are redacted and contain no keys, authorization headers, raw
  personal payloads, or credential-bearing URLs.
- Sync switches only a validated staged archive and recomputes metrics before
  advancing a complete checkpoint.
- Calendar changes require a local manifest and matching remote UID/external
  ID; deletion targets one exact event.
- Completed-workout links require an exact owned event ID. Date/sport/time
  candidates remain report-only.
- There is no active direct local manual-entry API. Manual sessions are
  recorded in Intervals.icu and then imported.
