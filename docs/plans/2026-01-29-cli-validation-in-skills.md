# CLI Validation Steps in Active Skills Implementation Plan

**Goal:** Make interval and plan-structure validation explicit in active skills where relevant, while keeping weekly validation as the default gate.

**Architecture:** Add conditional validation steps to `weekly-plan-generate` (intervals only when structured work/recovery bouts exist) and `macro-plan-create` (plan-structure validation using explicit phase/volume/recovery JSON inputs). Keep CLI-only workflows and avoid introducing new Python API usage.

**Tech Stack:** Markdown skills (`SKILL.md`), CLI commands (`sce plan validate-week|validate-intervals|validate-structure`).

---

### Task 1: Update weekly plan generation skill to call interval validation conditionally

**Files:**

- Modify: `.claude/skills/weekly-plan-generate/SKILL.md`

**Step 1: Add conditional validation guidance**

Add a sub-step under validation to run `sce plan validate-intervals` **only** when the weekly plan includes a structured interval/tempo session with explicit work/recovery bouts. Include a short note on preparing `/tmp/work_bouts.json` and `/tmp/recovery_bouts.json` from the planned session.

**Step 2: No tests required**

Docs-only change.

**Step 3: Commit**

```bash
git add .claude/skills/weekly-plan-generate/SKILL.md
git commit -m "docs: add conditional interval validation to weekly plan skill"
```

---

### Task 2: Update macro plan creation skill to call structure validation

**Files:**

- Modify: `.claude/skills/macro-plan-create/SKILL.md`

**Step 1: Add plan-structure validation step**

After `sce plan create-macro`, export the stored structure and validate:

```bash
sce plan export-structure --out-dir /tmp

sce plan validate-structure \
  --total-weeks <N> \
  --goal-type <GOAL> \
  --phases /tmp/plan_phases.json \
  --weekly-volumes /tmp/weekly_volumes_list.json \
  --recovery-weeks /tmp/recovery_weeks.json \
  --race-week <RACE_WEEK>
```

**Step 2: No tests required**

Docs-only change.

**Step 3: Commit**

```bash
git add .claude/skills/macro-plan-create/SKILL.md
git commit -m "docs: add plan structure validation to macro plan skill"
```
