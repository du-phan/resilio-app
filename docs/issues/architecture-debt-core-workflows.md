# Architecture debt: remove `resilio/core/workflows.py`

Baseline: 1,744 lines on 2026-07-28. The module combined locks, transactions,
sync, metrics, planning, adaptation, and manual activity entry and imported the
API layer from core.

Resolved during the Intervals.icu migration: focused activity-sync,
metrics-workflow, plan-workflow, adaptation-workflow, locking, and workflow
result modules replaced it, and the old module was deleted without a re-export
facade.
