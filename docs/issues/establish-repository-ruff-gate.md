# Establish a repository-wide Ruff gate

- Status: open
- Scope: existing source outside newly changed files

Repository-wide Ruff is not yet a green required check. New and modified
Python files must pass Ruff, but pre-existing findings still include import
ordering, unused names, line length, and naming violations.

The 2026-07-30 audit reports 837 findings across `resilio` and `tests`: 490
line-length findings, 141 import-order findings, 116 unused imports, and 90
other findings. The other group includes seven undefined names and fifteen
redefinitions, which are correctness-priority work.

Resolve correctness-class findings first, then formatting and naming issues in
reviewable responsibility-based changes. Do not hide findings with broad
global ignores or an unbounded baseline. The completion condition is a green
`poetry run ruff check resilio tests` command enforced by the normal
verification workflow.
