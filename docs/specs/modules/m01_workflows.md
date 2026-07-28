# Core workflow services

The former workflow monolith is replaced by responsibility-based modules.
There is no compatibility re-export.

| Module/package | Responsibility |
|---|---|
| `core/activity_sync` | Windowing, strict reconciliation, staging, checkpointing, archive commit |
| `core/activity_migration` | One-time validated backup, candidate, reconciliation, apply, rollback |
| `core/workout_publication` | Structured rendering, ownership proof, event mutation |
| `core/metrics_workflow.py` | Deterministic metric regeneration |
| `core/plan_workflow.py` | Plan transactions |
| `core/adaptation_workflow.py` | Adaptation orchestration |
| `core/locking.py` | Exclusive operation locks |

Core services depend on schemas, repositories, and narrow integration
protocols/clients. They do not import API or CLI. API owns client/config
lifecycle; CLI owns parsing and JSON envelopes.

Activity sync stages and validates unambiguous changes, atomically switches the
archive, regenerates metrics from the earliest change, then advances complete
state only when the run is not partial. Ambiguous and invalid records are
reported without silent fallback.

Manual activities have one active source: Intervals.icu. Historical local
manual records remain immutable historical imports.
