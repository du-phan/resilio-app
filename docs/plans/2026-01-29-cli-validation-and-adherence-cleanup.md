# CLI Validation + Adherence Cleanup Implementation Plan

**Goal:** Remove `sce analysis adherence` end-to-end and make weekly plan validation explicit in the CLI while consolidating validation commands under the plan/goal namespaces.

**Architecture:** Delete adherence analysis from core/API/CLI and strip all references from skills/docs/specs. Rename the weekly JSON validator to `sce plan validate-week`, move interval + plan structure validation into the `plan` namespace, and remove the `validation` CLI group to eliminate naming collisions.

**Tech Stack:** Python (Typer CLI), Pydantic schemas, Markdown docs.

---

### Task 1: Remove adherence analysis from core + schemas

**Files:**
- Modify: `sports_coach_engine/core/analysis/weekly.py`
- Modify: `sports_coach_engine/core/analysis/__init__.py`
- Modify: `sports_coach_engine/schemas/analysis.py`

**Step 1: Update tests to expect removal (failing test)**
- In `tests/unit/test_analysis_api.py`, remove the adherence fixtures + tests and update the module docstring count.

**Step 2: Run test to verify it fails before code changes**
- Run: `pytest tests/unit/test_analysis_api.py -v`
- Expected: FAIL with missing symbol/import errors after test edits.

**Step 3: Remove core adherence implementation**
- Delete `analyze_week_adherence` from `sports_coach_engine/core/analysis/weekly.py`.
- Remove exports from `sports_coach_engine/core/analysis/__init__.py`.

**Step 4: Remove adherence schemas**
- Delete `WorkoutTypeAdherence` and `WeekAdherenceAnalysis` from `sports_coach_engine/schemas/analysis.py`.

**Step 5: Re-run tests**
- Run: `pytest tests/unit/test_analysis_api.py -v`
- Expected: PASS.

**Step 6: Commit**
```
git add sports_coach_engine/core/analysis/weekly.py \
  sports_coach_engine/core/analysis/__init__.py \
  sports_coach_engine/schemas/analysis.py \
  tests/unit/test_analysis_api.py

git commit -m "remove: drop adherence analysis core + schemas"
```

---

### Task 2: Remove adherence from API + CLI

**Files:**
- Modify: `sports_coach_engine/api/analysis.py`
- Modify: `sports_coach_engine/api/__init__.py`
- Modify: `sports_coach_engine/cli/commands/analysis.py`

**Step 1: Remove API wrapper + exports**
- Delete `api_analyze_week_adherence` from `sports_coach_engine/api/analysis.py`.
- Remove `api_analyze_week_adherence` from `sports_coach_engine/api/__init__.py`.

**Step 2: Remove CLI command**
- Delete the `sce analysis adherence` command in `sports_coach_engine/cli/commands/analysis.py`.
- Update the command list in the module docstring.

**Step 3: Re-run tests**
- Run: `pytest tests/unit/test_analysis_api.py -v`
- Expected: PASS.

**Step 4: Commit**
```
git add sports_coach_engine/api/analysis.py \
  sports_coach_engine/api/__init__.py \
  sports_coach_engine/cli/commands/analysis.py

git commit -m "remove: drop adherence analysis API + CLI"
```

---

### Task 3: Remove adherence references from skills/docs/specs

**Files:**
- Modify: `.claude/skills/weekly-plan-generate/SKILL.md`
- Modify: `.claude/skills/weekly-analysis/SKILL.md`
- Modify: `.claude/skills/weekly-plan-generate/references/volume_progression_weekly.md`
- Modify: `docs/coaching/cli/cli_analysis.md`
- Modify: `docs/coaching/cli/index.md`
- Modify: `docs/coaching/scenarios.md`
- Modify: `docs/specs/api_layer.md`

**Step 1: Skills**
- Remove `sce analysis adherence` from `weekly-plan-generate`.
- In `weekly-analysis`, replace adherence step with `sce week` summary only.

**Step 2: Skill references**
- Remove or rewrite `sce analysis adherence` mentions in `volume_progression_weekly.md` (use `sce week` or remove the step entirely).

**Step 3: Docs**
- Remove `sce analysis adherence` section from `docs/coaching/cli/cli_analysis.md` and update command list.
- Remove `sce analysis adherence` from `docs/coaching/cli/index.md` and any example lists.
- Update `docs/coaching/scenarios.md` to replace adherence CLI example with `sce week`.
- Remove adherence API entry from `docs/specs/api_layer.md`.

**Step 4: Commit**
```
git add .claude/skills/weekly-plan-generate/SKILL.md \
  .claude/skills/weekly-analysis/SKILL.md \
  .claude/skills/weekly-plan-generate/references/volume_progression_weekly.md \
  docs/coaching/cli/cli_analysis.md \
  docs/coaching/cli/index.md \
  docs/coaching/scenarios.md \
  docs/specs/api_layer.md

git commit -m "docs: remove adherence analysis references"
```

---

### Task 4: Rename weekly validator and consolidate validation commands

**Files:**
- Modify: `sports_coach_engine/cli/commands/plan.py`
- Delete: `sports_coach_engine/cli/commands/validation.py`
- Modify: `sports_coach_engine/cli/__init__.py`
- Modify: `docs/coaching/cli/cli_planning.md`
- Modify: `docs/coaching/cli/index.md`
- Modify: `docs/claude_documentation/skill_refactor_plan.md`
- Modify: `.claude/skills/weekly-plan-generate/SKILL.md`
- Modify: `.claude/skills/weekly-plan-apply/references/json_workflow.md`

**Step 1: Rename weekly validator**
- In `sports_coach_engine/cli/commands/plan.py`, rename the command:
  - `@app.command(name="validate")` → `@app.command(name="validate-week")`
  - Update help text/examples and any internal references (e.g., populate `--validate` help).

**Step 2: Move validation commands into plan**
- Copy command logic from `sports_coach_engine/cli/commands/validation.py` into `plan.py` as:
  - `sce plan validate-intervals`
  - `sce plan validate-structure`
- Remove the standalone validation command group by deleting `validation.py`.

**Step 3: Update CLI registration**
- Remove `validation` registration from `sports_coach_engine/cli/__init__.py`.

**Step 4: Docs + skills**
- Update `docs/coaching/cli/cli_planning.md` to list:
  - `sce plan validate-week`
  - `sce plan validate-intervals`
  - `sce plan validate-structure`
- Remove `docs/coaching/cli/cli_validation.md` (or replace with a stub pointing to `cli_planning.md`).
- Update `docs/coaching/cli/index.md` to remove `validation` category and point to plan validators.
- Update `.claude/skills/weekly-plan-generate/SKILL.md` and `.claude/skills/weekly-plan-apply/references/json_workflow.md` to use `sce plan validate-week`.
- Update `docs/claude_documentation/skill_refactor_plan.md` to replace `sce plan validate` with `sce plan validate-week`.

**Step 5: Commit**
```
git add sports_coach_engine/cli/commands/plan.py \
  sports_coach_engine/cli/__init__.py \
  docs/coaching/cli/cli_planning.md \
  docs/coaching/cli/index.md \
  docs/claude_documentation/skill_refactor_plan.md \
  .claude/skills/weekly-plan-generate/SKILL.md \
  .claude/skills/weekly-plan-apply/references/json_workflow.md

git rm sports_coach_engine/cli/commands/validation.py

git commit -m "cli: consolidate validation under plan namespace"
```

---

### Task 5: Consistency sweep

**Files:**
- Modify: any hits from grep

**Step 1: Grep for leftovers**
- Run: `rg -n "analysis adherence" .`
- Run: `rg -n "sce validation" .`
- Run: `rg -n "plan validate" .`

**Step 2: Fix any remaining references**
- Replace with `sce plan validate-week` or `sce week` as appropriate.

**Step 3: Final smoke check**
- Run: `rg -n "validate-week" .`
- Expected: docs + skills align with new command name.

**Step 4: Commit**
```
git add .

git commit -m "chore: finalize adherence removal and validation rename references"
```

---

### Task 6: (Optional) Focused CLI smoke checks

**Step 1:** `sce plan validate-week --help`
**Step 2:** `sce plan validate-structure --help`
**Step 3:** `sce plan validate-intervals --help`

Expected: commands are discoverable and correctly namespaced.

