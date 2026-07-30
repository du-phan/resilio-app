# Architecture map

Resilio is a local CLI application. External systems provide recorded
activities and receive planned workouts; Resilio owns canonical history,
calculated load/readiness, coaching decisions, plans, and publication
ownership.

```text
.env.local / settings
        |
        v
integrations/intervals_icu
  client -> strict DTOs -> mappers
        |
        v
schemas <-> repositories
        |
        v
core services
  activity_sync | workout_publication | metrics | load | profile | planning
        |
        v
api
        |
        v
cli
```

## Package responsibilities

| Package | Owns | Must not own |
|---|---|---|
| `schemas` | Domain and persisted contracts | I/O, transport, API/CLI imports |
| `integrations` | HTTP, strict external DTOs, provider rendering/mapping | Athlete archive or coaching logic |
| `core` | Deterministic calculations and use-case services | CLI output or API imports |
| `api` | Stable callable use-case surface | External DTO leakage |
| `cli` | Argument parsing and JSON envelopes | Domain or transport logic |

## State ownership

| State | Authority |
|---|---|
| Completed activity history | Canonical local activity v2 archive |
| Load/readiness/daily metrics | Resilio computations |
| Athlete profile and constraints | Local profile |
| Training plan | Local plan store |
| External activity review | Hashed approval ledger plus current candidate proof |
| Historical outbound activity identity | Provider-neutral ownership ledger plus immutable run/canary receipts |
| External event identity | Local publication manifest plus remote proof |
| External raw response | Ephemeral only |

## Safety boundaries

- Activity migrations stage and reconcile before an atomic switch.
- Completed sync and historical backfill share one activity-mutation lock and
  archive/state transaction.
- Sync checkpoints advance only after archive and metrics commit.
- Ambiguous external/history matches are quarantined.
- Calendar mutations require deterministic namespace, manifest, and read-back
  ownership proof.
- Automated tests use fake transports and fake environment mappings.

The external boundary is documented in the
[Intervals.icu integration reference](intervals-icu-integration.md).
