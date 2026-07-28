# Engineering debt: make the repository-wide Ruff gate actionable

- Status: open
- Recorded: 2026-07-28
- Scope: legacy code outside the completed external-integration migration

`poetry run ruff check resilio` currently reports 618 findings. The set
includes import ordering, unused imports/locals, line length, naming style, and
undefined-name findings in legacy modules such as `core/plan.py`,
`core/repository.py`, and `schemas/workout.py`.

Do not apply a repository-wide automatic rewrite inside an unrelated feature
change. Establish a reviewed baseline, fix undefined names and other
correctness-class findings first, then shrink a temporary allowlist until the
full command is a required green gate.

The Intervals.icu migration’s changed-file Ruff scope is green; this issue must
not be used to waive lint regressions in new or modified migration modules.
