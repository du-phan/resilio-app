# Macro Template Refactor Implementation Plan

**Goal:** Make macro plan creation template-first and CLI-driven: generate a blank macro template with required fields, have the AI coach fill it, then create the plan from that template. Remove the old manual JSON path and require the template schema.

**Architecture:** Add `build_macro_template()` in the API and expose `sce plan template-macro` in the CLI to emit a blank template with placeholders. Refactor `sce plan create-macro` to require the template schema (`template_version`, `total_weeks`, `volumes_km`, `workout_structure_hints`) and to reject placeholders explicitly. Update skills/docs to use the new template-first flow and remove manual JSON instructions. No backward compatibility.

**Tech Stack:** Python CLI (Typer), API layer (`sports_coach_engine/api/plan.py`), JSON templates, Markdown docs/skills.

---

### Task 1: Add API helper to build a blank macro template

**Files:**

- Modify: `sports_coach_engine/api/plan.py`
- Test: `tests/unit/test_api_plan.py`

**Step 1: Write failing test (template shape + placeholders)**

```python
def test_build_macro_template_shape():
    template = build_macro_template(3)
    assert template["template_version"] == "macro_template_v1"
    assert template["total_weeks"] == 3
    assert template["volumes_km"] == [None, None, None]
    assert len(template["workout_structure_hints"]) == 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_api_plan.py::test_build_macro_template_shape -v`
Expected: FAIL (function missing)

**Step 3: Implement minimal API helper**

Add to `sports_coach_engine/api/plan.py`:
- `build_macro_template(total_weeks: int)`
  - Validate total_weeks > 0
  - Return dict:
    - `template_version`: "macro_template_v1"
    - `total_weeks`: total_weeks
    - `volumes_km`: `[None] * total_weeks`
    - `workout_structure_hints`: list of dicts with `None` placeholders:
      - `quality.max_sessions = None`
      - `quality.types = None`
      - `long_run.emphasis = None`
      - `long_run.pct_range = [None, None]`
      - `intensity_balance.low_intensity_pct = None`

**Step 4: Run test**

Run: `pytest tests/unit/test_api_plan.py::test_build_macro_template_shape -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_api_plan.py sports_coach_engine/api/plan.py
git commit -m "feat: add macro plan template generator"
```

---

### Task 2: Add CLI command `sce plan template-macro`

**Files:**

- Modify: `sports_coach_engine/cli/commands/plan.py`
- Modify: `sports_coach_engine/api/__init__.py`

**Step 1: Implement CLI command**

Add to `plan.py`:
- `@app.command(name="template-macro")`
- Options:
  - `--total-weeks` (required)
  - `--out` (default: `/tmp/macro_template.json`)
- Behavior:
  - Call `build_macro_template(total_weeks)`
  - Write JSON to `--out`
  - Output success envelope with `template_path`, `total_weeks`, `template_version`

**Step 2: Export API helper**

Expose `build_macro_template` in `sports_coach_engine/api/__init__.py`.

**Step 3: Manual sanity check**

```bash
sce plan template-macro --total-weeks 4 --out /tmp/macro_template.json
```

Expected: file written with null placeholders.

**Step 4: Commit**

```bash
git add sports_coach_engine/cli/commands/plan.py sports_coach_engine/api/__init__.py
git commit -m "feat: add sce plan template-macro"
```

---

### Task 3: Refactor `sce plan create-macro` to require template schema

**Files:**

- Modify: `sports_coach_engine/cli/commands/plan.py`

**Step 1: Rename flag**

- Replace `--weekly-volumes-json` with `--macro-template-json`
- Update help text and internal variable names accordingly

**Step 2: Enforce template fields**

- Require `template_version == "macro_template_v1"`
- Require `total_weeks` in template matches CLI `--total-weeks`
- If missing, return validation error with next_steps: `sce plan template-macro ...`

**Step 3: Reject placeholders explicitly**

Add a placeholder scan before validating:
- Traverse `volumes_km` and `workout_structure_hints`
- If any `None` found, return error:
  - message: "Macro template contains placeholders; fill all required fields"
  - data: list of missing paths (e.g., `volumes_km[3]`, `workout_structure_hints[2].quality.max_sessions`)

**Step 4: Keep current validation logic**

- After placeholder scan, keep the existing validation: positive volumes, correct length, `WorkoutStructureHints` model validation.

**Step 5: Commit**

```bash
git add sports_coach_engine/cli/commands/plan.py
git commit -m "refactor: require macro template for create-macro"
```

---

### Task 4: Update skills + docs to use template-first macro flow

**Files:**

- Modify: `.claude/skills/macro-plan-create/SKILL.md`
- Modify: `docs/coaching/cli/cli_planning.md`
- Modify: `docs/coaching/cli/index.md`
- Modify: `docs/claude_documentation/skill_refactor_plan.md` (if it references old flag)

**Step 1: Update macro-plan-create skill**

New flow:
```bash
sce plan template-macro --total-weeks <N> --out /tmp/macro_template.json
# AI coach fills template
sce plan create-macro ... --macro-template-json /tmp/macro_template.json
sce plan export-structure --out-dir /tmp
sce plan validate-structure ...
```

**Step 2: Update CLI docs**

- Add `sce plan template-macro`
- Update `sce plan create-macro` to reference `--macro-template-json`
- Remove any manual JSON instructions

**Step 3: Commit**

```bash
git add .claude/skills/macro-plan-create/SKILL.md docs/coaching/cli/cli_planning.md docs/coaching/cli/index.md docs/claude_documentation/skill_refactor_plan.md
git commit -m "docs: template-first macro planning flow"
```

---

### Task 5: Consistency sweep

**Files:**

- Modify any remaining references to `weekly_volumes.json` or `--weekly-volumes-json`

**Step 1: Search**

Run: `rg -n "weekly_volumes.json|weekly-volumes-json|weekly volumes JSON" .`

**Step 2: Update references to template flow**

**Step 3: Commit**

```bash
git add <files>
git commit -m "chore: align macro plan docs with template flow"
```
