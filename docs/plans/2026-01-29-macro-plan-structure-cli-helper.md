# Macro Plan Structure CLI Helper Implementation Plan

**Goal:** Add a CLI helper that exports the *stored* macro plan structure into validation-ready JSON so the AI coach validates the real plan, not a manually re-entered approximation.

**Architecture:** Introduce an API-level `export_plan_structure()` that derives phase counts, weekly volumes, recovery weeks, and race week from `current_plan.yaml`, then expose it via `resilio plan export-structure` which writes JSON files for `validate-structure` and returns a JSON envelope with paths + data. Update skills/docs to use this CLI helper. This keeps the workflow CLI-only and preserves AI-driven planning while guaranteeing schema correctness.

**Tech Stack:** Python CLI (Typer), API layer (`resilio/api/plan.py`), JSON files, Markdown docs/skills.

---

### Task 1: Add API helper to export macro structure from stored plan

**Files:**

- Modify: `resilio/api/plan.py`
- Test: `tests/unit/test_api_plan.py`

**Step 1: Write the failing test (race week resolved from plan weeks)**

```python
def test_export_plan_structure_uses_race_week_from_plan(mock_repo_cls, mock_log):
    # plan.goal target_date falls inside week 9
    # expect race_week == 9
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_api_plan.py::test_export_plan_structure_uses_race_week_from_plan -v`
Expected: FAIL with "export_plan_structure not defined"

**Step 3: Write the failing test (phases/volumes/recovery derived from stored plan)**

```python
def test_export_plan_structure_derives_phases_and_volumes(mock_repo_cls, mock_log):
    # phases list has start/end weeks; weeks list has target_volume_km + is_recovery_week
    # expect phases dict counts, ordered volume list, recovery week numbers
    ...
```

**Step 4: Run test to verify it fails**

Run: `pytest tests/unit/test_api_plan.py::test_export_plan_structure_derives_phases_and_volumes -v`
Expected: FAIL (function missing)

**Step 5: Implement minimal API helper**

Add to `resilio/api/plan.py`:
- `PlanStructureExport` dataclass with:
  - `total_weeks`, `goal_type`, `race_week`
  - `phases` (dict phase -> weeks)
  - `weekly_volumes_km` (list length total_weeks ordered by week_number)
  - `recovery_weeks` (list of week numbers)
- `export_plan_structure()`:
  - Call `get_current_plan()`
  - Read `goal_type` from `plan.goal["type"]` or `plan.goal.type`
  - Read `goal_date` from `plan.goal["target_date"]` or `plan.goal.target_date`
  - Compute `race_week` by finding week where `start_date <= goal_date <= end_date`; fallback to `total_weeks`
  - Build phases dict from `plan.phases` list using `end_week - start_week + 1`
  - Build weekly volumes list from `plan.weeks` sorted by `week_number`
  - Build recovery weeks list where `is_recovery_week` is true
  - Validate data integrity:
    - `len(weeks) == total_weeks` and week numbers cover 1..total_weeks
    - if not, return `PlanError(error_type="validation", message="Plan weeks mismatch total_weeks")`
  - Return `PlanStructureExport` or `PlanError`

**Step 6: Run tests**

Run: `pytest tests/unit/test_api_plan.py::test_export_plan_structure_uses_race_week_from_plan -v`
Expected: PASS

Run: `pytest tests/unit/test_api_plan.py::test_export_plan_structure_derives_phases_and_volumes -v`
Expected: PASS

**Step 7: Commit**

```bash
git add tests/unit/test_api_plan.py resilio/api/plan.py
git commit -m "feat: export macro plan structure from stored plan"
```

---

### Task 2: Add CLI command `resilio plan export-structure`

**Files:**

- Modify: `resilio/cli/commands/plan.py`
- Modify: `resilio/api/__init__.py`

**Step 1: Write the failing CLI test (optional)**

If CLI tests are desired, add in `tests/integration/cli/`:
- Invoke Typer app with `export-structure` and assert JSON output contains `phases_file`, `weekly_volumes_file`, `recovery_weeks_file`.

If skipping CLI tests for v0, proceed to implementation.

**Step 2: Implement CLI command**

Add to `plan.py`:
- `@app.command(name="export-structure")`
- Options:
  - `--out-dir` (default: `/tmp`)
- Behavior:
  - Call `export_plan_structure()`
  - Write three JSON files in `out-dir`:
    - `plan_phases.json`
    - `weekly_volumes_list.json`
    - `recovery_weeks.json`
  - Output envelope with:
    - `total_weeks`, `goal_type`, `race_week`
    - `phases`, `weekly_volumes_km`, `recovery_weeks`
    - file paths

**Step 3: Update API exports**

Expose `export_plan_structure` in `resilio/api/__init__.py` for CLI usage.

**Step 4: Manual sanity check**

Run:
```bash
resilio plan export-structure --out-dir /tmp
```
Expected: JSON envelope + files created in `/tmp`

**Step 5: Commit**

```bash
git add resilio/cli/commands/plan.py resilio/api/__init__.py
git commit -m "feat: add resilio plan export-structure"
```

---

### Task 3: Update skills and docs to use export-structure

**Files:**

- Modify: `.claude/skills/macro-plan-create/SKILL.md`
- Modify: `docs/coaching/cli/cli_planning.md`
- Modify: `docs/coaching/cli/index.md`

**Step 1: Update macro skill**

Replace manual JSON creation with:
```bash
resilio plan export-structure --out-dir /tmp
resilio plan validate-structure \
  --total-weeks <N> \
  --goal-type <GOAL> \
  --phases /tmp/plan_phases.json \
  --weekly-volumes /tmp/weekly_volumes_list.json \
  --recovery-weeks /tmp/recovery_weeks.json \
  --race-week <RACE_WEEK>
```

**Step 2: Update CLI docs**

Add a new section for `resilio plan export-structure` with usage and outputs.
Add it to the CLI index tables.

**Step 3: Commit**

```bash
git add .claude/skills/macro-plan-create/SKILL.md docs/coaching/cli/cli_planning.md docs/coaching/cli/index.md
git commit -m "docs: use export-structure for macro validation"
```

---

### Task 4: Verify on current plan

**Files:**

- No code changes; run CLI

**Step 1: Export from current plan**

```bash
resilio plan export-structure --out-dir /tmp
```

**Expected output from `current_plan.yaml`:**
- `total_weeks`: 9
- `goal_type`: marathon
- `race_week`: 9 (race date 2026-03-28 falls in week 9)
- `phases`:
  - base: 3
  - build: 3
  - peak: 1
  - taper: 2
- `weekly_volumes_km`: [23, 28, 32, 23, 36, 40, 44, 31, 18]
- `recovery_weeks`: [4]

**Step 2: Validate structure**

```bash
resilio plan validate-structure \
  --total-weeks 9 \
  --goal-type marathon \
  --phases /tmp/plan_phases.json \
  --weekly-volumes /tmp/weekly_volumes_list.json \
  --recovery-weeks /tmp/recovery_weeks.json \
  --race-week 9
```

Expected: validation output against the *stored* macro plan.

---

### Task 5: Final consistency check

**Files:**

- Modify if needed: `CLAUDE.md` (only if it references old manual validation inputs)

**Step 1: Search for old manual instructions**

Run: `rg -n "plan_phases.json|weekly_volumes_list.json|recovery_weeks.json" .`

**Step 2: Update references to point to `resilio plan export-structure`**

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: align macro validation with export-structure"
```
