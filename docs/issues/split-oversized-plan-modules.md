# Split oversized plan modules

- Status: open
- Scope: `resilio/api/plan.py`, `resilio/core/plan.py`, and
  `resilio/cli/commands/plan.py`

The plan API, core service, and CLI modules exceed the repository's
1,500-line hard limit. They are temporarily protected by a shrinking
architecture-test allowlist, so they may not grow beyond their recorded
baselines.

Refactor by responsibility, not by arbitrary line ranges:

- core: generation, validation, progression, matching, and persistence;
- API: queries, approvals, generation, and publication orchestration;
- CLI: coherent command groups that delegate through the API boundary.

The target structure must preserve `schemas -> core -> API -> CLI` dependency
direction, avoid compatibility re-export facades, and keep each new module
below the 800-line warning threshold. Remove each allowlist entry as soon as
its original module falls below the hard limit.
