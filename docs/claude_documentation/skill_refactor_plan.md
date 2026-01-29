# Claude Coach Skill/Subagent Refactor Plan

## Goals
- Eliminate athlete-dialog deadlocks by keeping all questions/approvals in the main agent.
- Make macro creation non-interactive and deterministic; weekly planning follows the same generate → approve → apply loop (Week 1 same as Week N).
- Control context bloat by using forked skills plus lightweight subagents that preload only the needed skills.
- Align docs/schema/skills so macro plan is created first; workouts are generated one week at a time when due.

## Implementation Status (as of 2026-01-23)
**Done**
- New executor skills + subagents (vdot-baseline-proposal, macro-plan-create, weekly-plan-generate, weekly-plan-apply).
- Legacy monolithic skills archived; CLAUDE.md aligned to split flow.
- CLI helpers: `sce plan status`, `sce plan next-unpopulated`, `sce plan validate-macro`, `sce plan populate --validate`.
- `sce plan generate-week` implemented (CLI scaffold for intent-based weekly JSON).
- Approval state schema + CLI commands (`sce approvals …`) with hard gates:
  - `create-macro` requires approved baseline VDOT.
  - `plan populate` requires matching weekly approval (week + file path).
- Weekday indexing standardized to 0=Mon..6=Sun across active skills/docs/tests.

**Remaining (non-blocking for v0)**
- Review doc versioning (`_vN` suffix) when regenerated same day.
- Optional CLI enhancements: `sce coach context`, `sce plan diff-week`, `sce plan lock/unlock`, `sce plan schema`, `sce plan export --macro --format json`.

## Scope / Non-Goals
**In scope**
- Skill/subagent refactor for macro + weekly planning.
- CLI-first workflows and new CLI commands to support them.
- Approval state handling; review docs in `/tmp/` for macro only (VDOT + weekly reviews are chat-only).

**Out of scope (for now)**
- Changing training methodology rules in the Python engine.
- Building a GUI or web app for athlete interaction.
- Full redesign of the profile/memory system.

## Guiding Principles
- CLI-first: skills interact **only** via `sce` CLI (no direct Python engine calls).
- Executor skills/subagents do computation and, when needed, write artifacts; they never ask the athlete anything.
- Main agent owns dialogue, approvals, and state handoff (e.g., approved VDOT, weekly JSON payloads).
- Macro plan defines the structure and baseline intensity; weekly plans may adjust volume within explicit bounds and must not save without approval.
- Guardrails > algorithms: use CLI metrics + coaching judgment; keep heuristics descriptive (rationales), not hard-coded formulas.
- Date correctness is enforced via `sce dates` commands; no mental date math.

## Non-Negotiable Invariants
- All athlete-facing questions and approvals happen in the main agent context only.
- No skill writes plan data without an explicit approval state recorded by the main agent.
- Macro plan is created before any weekly workouts are generated.
- Week 1 generation uses the same workflow as any other week (no special casing).
- CLI-only: if a capability is missing, extend the CLI rather than calling Python directly.

## Dependencies / Preconditions
- `sce` CLI available via `poetry run sce` (preferred in this repo) and returns JSON for all commands.
- Data directories initialized (`sce init`) and synced (`sce sync`) before planning.
- Profile includes goal type/date/time and constraints (run days, max session length).
- Plan storage uses `data/plans/current_plan.yaml` (no direct edits by skills).

## Definitions (for consistent language)
- **Macro plan**: phase structure + weekly target volumes + workout-structure hints (e.g., tempo/threshold presence), but no detailed workouts.
- **Weekly plan**: detailed workouts for a single week (intent-based JSON).
- **Apply**: the act of persisting an approved weekly plan to the plan store via CLI.
- **Unpopulated week**: a plan week whose `workouts` list is empty.

## Target Architecture
1) Main agent (orchestrator)
   - Collects athlete data/goals, asks all questions, records approvals.
   - Invokes executor skills explicitly (slash commands), passes required inputs, and applies outputs only after approval.

2) Executor skills (forked)
   - Non-interactive; tools: Bash/Read/Write only.
   - Emit structured outputs + review markdowns in `/tmp/` for the main agent to present.

3) Specialist subagents (for context control)
   - Preload only the skill(s) needed for the task; clean window reduces prompt bloat.
   - Non-interactive; same contract as executor skills.

## Subagent Routing Rules (Context Control)
- Default to subagents when: the conversation is long, the main agent already holds a lot of plan context, or multiple prior approvals exist.
- Prefer direct skill invocation only for short sessions (e.g., first 5–10 turns) or when the task is trivial.
- Never chain subagents; the main agent is the only router.

## Data Contracts (approval-safe)
**Approval state file (`data/state/approvals.json`)**
- `approved_baseline_vdot`
- `vdot_approval_ts`
- `macro_approved` (bool) + `macro_approval_ts`
- `weekly_approval` object:
  - `week_number`
  - `approved_at`
  - `approved_file` (path to approved weekly JSON)

**Weekly payload integrity (v0)**
- `weekly-plan-generate` emits a weekly JSON file and records its path.
- Main agent stores the approved file path in approvals state and passes that exact file to `sce plan populate`.

**Plan state fields**
- `baseline_vdot`, `current_vdot`, `vdot_history[]`
- `plan_state.last_populated_week` (or derived by CLI helper)

## Skills (contracts)
- `vdot-baseline-proposal` (new)
  - Inputs: profile/status/races via CLI; optional overrides.
  - Outputs: proposed_vdot, pace table, evidence summary, athlete prompt text (presented in chat).
  - Blockers: fail if required profile/goal data missing.

- `macro-plan-create` (new)
  - Inputs: approved `baseline_vdot` (required), goal type/date/time, CTL, start date, constraints.
  - Actions: guardrails safe-volume → create-macro → validate → write `/tmp/macro_plan_review_YYYY_MM_DD.md`.
  - Blockers: abort if baseline_vdot not provided.

- `weekly-plan-generate` (new split)
  - Inputs: plan context, current metrics, next-week index (first unpopulated week); baseline/current VDOT from plan state.
  - Outputs: proposed week JSON (not applied), rationale, guardrail interpretation, athlete prompt (presented in chat).
  - Rules: default volume deviation band ±5–10% vs macro target; outside band must be flagged with rationale and must be escalated to macro-adjust unless coach explicitly overrides with justification recorded.
  - If `sce plan generate-week` exists: call it and capture output JSON. If not, generate JSON in-skill using CLI outputs + guardrails only.

- `weekly-plan-apply` (new)
  - Inputs: approved week JSON payload.
  - Purpose: safe, non-interactive write. All coaching validation happens earlier in `weekly-plan-generate`; this step only performs mechanical safety checks before persisting.
  - Actions: run `sce plan validate-week --file` and ensure 0 critical errors (warnings allowed); then populate plan; confirm with `sce plan show`. No athlete-facing prompts.
  - Blockers: refuse if payload missing/invalid or invariants fail; return errors to main agent to rerun generate with fixes.

- Optional `macro-plan-adjust` (later): apply athlete-requested tweaks without full regeneration.

## Approval Protocol (main agent only)
1) VDOT approval:
   - Present the VDOT review directly in chat.
   - Ask a single structured prompt (e.g., “Do these easy/tempo paces feel right?”).
   - Record `approved_baseline_vdot` and approval timestamp.
2) Macro approval:
   - Present `/tmp/macro_plan_review_YYYY_MM_DD.md`.
   - Record `macro_approved = true`.
3) Weekly approval (repeats each week):
   - Present the weekly review directly in chat.
   - Record approved week number and approved JSON file path.

## Subagents (to manage large context)
- `vdot-analyst` (haiku/sonnet): tools Bash/Read; preload `vdot-baseline-proposal`; no AskUserQuestion.
- `macro-planner` (sonnet): tools Bash/Read/Write; preload `macro-plan-create`.
- `weekly-planner` (sonnet): tools Bash/Read/Write; preload `weekly-plan-generate` and `weekly-plan-apply`.
Notes:
- Subagents are invoked explicitly by the main agent; they do not spawn further subagents.
- Keep skill bodies concise so preload doesn’t reintroduce bloat.

## Subagent Config Templates (project-level)
**vdot-analyst**
```
---
name: vdot-analyst
description: Computes baseline VDOT proposal and review summary
tools: Read, Grep, Glob, Bash
skills:
  - vdot-baseline-proposal
model: sonnet
---
```

**macro-planner**
```
---
name: macro-planner
description: Creates macro plan skeleton and review doc
tools: Read, Grep, Glob, Bash, Write
skills:
  - macro-plan-create
model: sonnet
---
```

**weekly-planner**
```
---
name: weekly-planner
description: Generates and applies weekly plans (non-interactive)
tools: Read, Grep, Glob, Bash, Write
skills:
  - weekly-plan-generate
  - weekly-plan-apply
model: sonnet
---
```

## Data & Schema Updates
- Plan fields: `baseline_vdot`, `current_vdot`, `vdot_history[] {week, vdot, source, confidence}`.
- State helper: `data/state/approvals.json` to persist approved decisions between skills (e.g., APPROVED_BASELINE_VDOT, approved_week_payload).
- Plan state: `plan_state.last_populated_week` (or derive via CLI helper) to avoid relying on `weeks[-1]` in the macro skeleton.
- Review docs: macro only; version if regenerated same day (suffix `_vN`); always surface latest path to the main agent.
- Approval state machine (recommended): `vdot_proposed` → `vdot_approved` → `macro_created` → `macro_approved` → `week_generated` → `week_approved` → `week_applied`.
- Integrity: store the approved weekly JSON file path in approvals state; `weekly-plan-apply` must use that exact file when writing.

## Workflow (macro → weekly, context-safe)
1) Intake (main agent):
   - Confirm goal/race/constraints; remind athlete macro first, workouts weekly.
   - Decide subagent: use `vdot-analyst` if context is large; otherwise main agent invokes the skill directly.
2) VDOT baseline:
   - Invoke `vdot-baseline-proposal` in subagent or forked skill.
   - Main agent asks athlete the generated prompt once; store APPROVED_BASELINE_VDOT in state.
3) Macro creation:
   - Invoke `macro-plan-create` (prefer `macro-planner` subagent if context is heavy).
   - Main agent presents macro review doc; get approval; store macro approval state.
4) Weekly cycle (Week 1 and beyond):
   - Determine next unpopulated week (CLI helper).
   - Invoke `weekly-plan-generate` (via `weekly-planner` subagent if context large).
   - Main agent presents weekly review/prompt in chat; on approval, invoke `weekly-plan-apply` to write.
   - Repeat weekly; no workouts generated during macro stage.

## Error Handling & Recovery
- If any CLI command returns non-zero, stop and return a blocking checklist to the main agent.
- If weekly validation fails, regenerate with adjusted parameters (do not apply).
- If macro validation fails, adjust volumes/phases and regenerate macro before proceeding.
- If approvals state is missing or file path mismatches, re-present plan for approval.

## Robustness Fixes
- Use CLI JSON outputs (all `sce` commands return JSON); never parse YAML in skills.
- NEXT_WEEK = first week with empty workouts (or CLI helper), not `weeks[-1]` from macro skeleton.
- Preflight every executor: profile completeness, goal present, plan existence, date validations; if missing, return blocking checklist, no writes.
- Enforce date rules via `sce dates` commands only.
- For races not ~16 weeks away: branch to compressed/extended macro logic; document expectation changes.
- Subagent hygiene: keep skill text concise; preload only required skills; avoid chaining subagents.

## CLI Gaps to Close (add or extend commands)
All items below are implemented:
- `sce plan next-unpopulated` and `sce plan status` return the first unpopulated week number and dates.
- `sce plan generate-week` generates weekly workout JSON (aligned with docs and progressive disclosure).
- `sce plan validate-macro` validates macro skeleton invariants and phase coverage.
- `sce plan validate-week --file <json>` is the unified weekly validator.
- `sce plan populate --from-json` supports `--validate` and enforces approval gating.

## CLI Improvements (detailed, CLI-first)
### Must Add (workflow-blocking)
1) `sce plan next-unpopulated` **DONE**
   - **Purpose**: Return the first week with empty workouts (week_number, dates, phase, target_volume_km, recovery flag).
   - **Reason**: Avoids scanning macro skeleton or loading full plan; fixes incorrect `weeks[-1]` logic.
   - **Output**: `{week_number, start_date, end_date, phase, target_volume_km, is_recovery_week}`.

2) `sce plan status` **DONE**
   - **Purpose**: Small, summary payload for routing decisions.
   - **Output**: plan_start/end, baseline_vdot, current_vdot, last_populated_week, next_unpopulated_week, phases, recovery_weeks, run_days, conflict_policy.
   - **Reason**: Replaces multiple CLI calls and reduces context bloat.

3) `sce plan create-macro --baseline-vdot` **DONE**
   - **Purpose**: Store approved baseline VDOT in macro plan at creation.
   - **Reason**: Prevents manual edits; keeps plan self-contained for weekly generation.

4) `sce plan generate-week` **DONE**
   - **Purpose**: Generate a single week’s workouts from macro context and current VDOT.
   - **Reason**: Already documented as primary workflow; missing in CLI implementation.

5) `sce plan populate --from-json <payload> [--validate]` **DONE**
   - **Purpose**: Atomic, CLI-only write for weekly plans using the existing command.
   - **Reason**: Avoids command proliferation; validation flag adds safety without extra commands.

### Should Add (robustness + safety)
6) `sce plan validate-macro` **DONE**
   - **Purpose**: Validate macro structure (phase lengths, recovery cadence, peak placement, volume trajectory).
   - **Reason**: Avoids constructing manual JSON for `sce plan validate-structure`.

7) `sce plan export --macro --format json`
   - **Purpose**: Export macro plan in JSON for `generate-week` input (if `generate-week` requires JSON).
   - **Reason**: Plan source is YAML; avoid manual conversion in skills.

8) `sce plan populate --validate` **DONE**
   - **Purpose**: Run `plan validate-week` logic inside populate and block on critical violations.
   - **Reason**: Ensures apply step always re-checks invariants (date alignment, volume, minimum durations).

9) `sce plan week --next-unpopulated`
   - **Purpose**: Alternative to `next-unpopulated` for teams that want everything under `plan week`.
   - **Reason**: Maintains consistency with existing `sce plan week --next`.

### Nice to Have (context efficiency + clarity)
10) `sce coach context`
   - **Purpose**: Aggregate `profile get`, `status`, `plan status`, `goal`, `memory list --type INJURY_HISTORY`.
   - **Reason**: Reduces tool calls and context size; ideal for subagent inputs.

11) `sce plan diff-week --week N --candidate <json>`
   - **Purpose**: Show delta vs current plan week for review.
   - **Reason**: Supports athlete explanation without manual diffing.

12) `sce plan lock` / `sce plan unlock`
   - **Purpose**: Prevent plan edits after macro approval unless explicitly unlocked.
   - **Reason**: Enforces approval discipline.

13) Weekday numbering consistency fix
   - **Action**: Standardize on `day_of_week` = 0–6 (0=Mon, 6=Sun) across schema, CLI outputs, and docs.
   - **Reason**: Current schema and AGENTS.md use 0=Mon; avoid conflicting ISO-1–7 references.

14) `sce plan schema`
   - **Purpose**: Return current plan JSON schema version and required fields.
   - **Reason**: Helps validators and future CLI compatibility.

## Current Codebase Observations (align plan to reality)
- CLI uses `sce plan validate-week --file <json>` (unified weekly validator).
- CLI has `sce plan populate --from-json <json> --validate` with approval gating via `sce approvals approve-week`.
- `sce plan generate-week` exists and scaffolds intent-based weekly JSON (pattern is still AI-decided).
- `sce plan revert-week` is documented but not implemented; recommend removing from docs/CLI to reduce command clutter.
- `sce plan week --next` returns next calendar week, not the next unpopulated week.
- Schema uses `day_of_week` as 0–6; docs/skills standardized to 0=Mon..6=Sun to avoid off-by-one errors.

## Command Surface Management (avoid tool confusion)
1) Define a **Core Command Set** (10–15 commands) used in 90% of sessions.
   - Example core set: `sce auth status`, `sce sync`, `sce status`, `sce week`, `sce plan status`,
     `sce plan next-unpopulated`, `sce plan generate-week`, `sce plan validate-week`,
     `sce plan populate`, `sce vdot paces`, `sce guardrails analyze-progression`.
   - Document this list at the top of CLI index and in each skill.

2) Create **task-specific command palettes** per skill.
   - Each skill includes a short “Commands used in this skill” list.
   - Subagents preload only those skills; this constrains the visible command surface.

3) Prefer **aggregators** over many micro-calls.
   - `sce plan status` and `sce coach context` reduce the number of commands the agent must remember.
   - Keep aggregator payloads small and stable (versioned).

4) Separate **core vs advanced** commands in docs.
   - Advanced commands appear in a “Use only if needed” section to reduce cognitive load.
   - Skills reference advanced commands only when necessary.

5) Add **example sequences** to every skill.
   - 1–2 minimal command flows per skill teach the correct usage pattern.
   - Example sequences should mirror the exact approvals flow (generate → validate → apply).

6) Enforce **CLI-only discipline** in skills/subagents.
   - `allowed-tools` restricted to Bash/Read/Write.
   - Explicitly forbid reading/writing plan files directly in skills.

## Best-Practice Compliance (docs/claude_documentation)
1) Skill authoring (per `agent_skill_best_practices.md`)
   - Keep SKILL.md concise; move long examples to `examples/` and link to them.
   - Use third-person descriptions in YAML frontmatter (required for discovery).
   - Match freedom to fragility: strict step lists for fragile workflows; guidance for coaching judgment.
   - Test skills with multiple models (Haiku/Sonnet) to ensure clarity under shorter context.

2) Skill structure (per `extend_claude_with_skills.md`)
   - Always include frontmatter with `name`, `description`, `disable-model-invocation: true`.
   - Use `context: fork` for executor skills and keep tool access minimal (`allowed-tools`).
   - Add optional `argument-hint` for required inputs to reduce invocation errors.
   - Prefer supporting files (`templates/`, `examples/`, `references/`) over long inline content.

3) Subagent usage (per `create_custom_sub_agents.md`)
   - Subagents preload skills explicitly (skills are not inherited).
   - Use subagents only for execution; no athlete dialogue or nested delegation.
   - Keep subagent prompts minimal and focused; use tool allowlists.

## Acceptance Criteria (implementation-ready)
- Macro creation: `sce plan create-macro` runs with baseline VDOT stored and passes `sce plan validate-macro`. **DONE**
- Weekly generation: `sce plan generate-week` + `sce plan validate-week` produce zero critical issues. **READY FOR TESTING**
- Apply step: `sce plan populate` runs only after explicit approval recorded in state. **DONE**
- No skill performs direct file edits of plan YAML.
- Week 1 is generated via the same weekly workflow as Week N.
- Subagent runs produce no athlete-facing questions.

## Risk Register (and mitigations)
- **CLI missing / not on PATH** → Document install path; fail fast with clear instruction.
- **Approval file mismatch** → Re-present plan for approval; regenerate if needed.
- **Schema drift between CLI and skills** → Use `sce plan schema` to validate fields; keep skills minimal.
- **Weekday numbering mismatch** → Standardize on 0=Mon..6=Sun in schema, CLI outputs, and docs; add validation checks in apply step.
- **Model variance (Haiku vs Sonnet)** → Test skills on both; keep instructions concise and deterministic.

## Backward Compatibility / Rollout
- Keep existing skills functional during migration; mark deprecated in docs.
- Introduce new CLI commands behind stable flags; fall back to existing commands if unavailable.
- Phase rollout:
  1) Add CLI commands (no behavior change to existing flows).
  2) Add new skills and subagents; run in parallel with old flows.
  3) Switch main agent to new skills; deprecate old skill usage.

## Testing Matrix
- Models: Haiku + Sonnet for each new skill.
- Scenarios:
  - No recent race (VDOT estimated from training).
  - Recent race present (VDOT from race).
  - Recovery week generation.
  - Injury/illness adjustment.
  - Macro plan <16 weeks or >16 weeks.

## Migration Steps
1) Add new skills (vdot proposal, macro create, weekly generate/apply) with `disable-model-invocation: true` and clear argument hints.
2) Archive legacy monolithic macro-planning skill (now split into vdot proposal + macro create).
3) Archive legacy weekly planning skill that performed in-skill saves; delegate to `weekly-plan-apply`.
4) Fix week detection and YAML parsing logic in weekly workflows.
5) Remove obsolete CLI references (e.g., `revert-week`) from docs; do not add new redundant commands.
6) Align `CLAUDE.md` to the new flow and the “macro first, weeks one-at-a-time” rule.
7) Add schema/state helpers and document the approval handoff convention.
8) Add approvals CLI commands and enforce approval gates in `create-macro` and `plan populate`. **DONE**

## Detailed Implementation Steps
1) Skill scaffolding (files + frontmatter)
   - Create skill folders:
     - `.claude/skills/vdot-baseline-proposal/`
     - `.claude/skills/macro-plan-create/`
     - `.claude/skills/weekly-plan-generate/`
     - `.claude/skills/weekly-plan-apply/`
   - Add `SKILL.md` to each with:
     - `disable-model-invocation: true`
     - `context: fork`
     - `allowed-tools: Bash, Read` (add Write only if the skill outputs files)
     - concise description + argument-hint for required inputs

2) Subagent definitions (context control)
   - Add `.claude/agents/` files (project-level) for:
     - `vdot-analyst` (preload vdot skill)
     - `macro-planner` (preload macro skill)
     - `weekly-planner` (preload weekly generate/apply)
   - Ensure each subagent:
     - uses `tools: Read, Grep, Glob, Bash` plus Write if needed
     - has no AskUserQuestion
     - includes `skills:` list only (no extra context)

3) Split macro workflow
   - `vdot-baseline-proposal`:
     - run CLI: `sce race list`, `sce vdot estimate-current`, `sce activity list` (as needed)
     - compute proposed VDOT and paces via `sce vdot paces`
     - present review directly in chat with evidence + athlete prompt
   - `macro-plan-create`:
     - require `baseline_vdot` input (fail-fast if missing)
     - run CLI: `sce dates next-monday`, `sce status`, `sce guardrails safe-volume`
     - `sce plan create-macro` then `sce plan show`
     - write `/tmp/macro_plan_review_YYYY_MM_DD.md`

4) Split weekly workflow
   - `weekly-plan-generate`:
     - find next unpopulated week via CLI (`sce plan next-unpopulated` or `sce plan status`)
     - run guardrails (`sce guardrails analyze-progression`)
     - generate weekly JSON (no writes) and present review directly in chat
   - `weekly-plan-apply`:
     - verify approved file path matches approvals state
     - validate dates and schema (`sce plan validate-week --file`)
     - apply via CLI (`sce plan populate --from-json` with `--validate` if available)

5) CLI gap closure (if missing)
   - Add/extend CLI commands:
     - `sce plan next-unpopulated`
     - `sce plan generate-week`
     - `sce plan validate-macro`
     - `sce plan validate-week --file` (already exists; ensure documented)
     - `sce plan populate --from-json` (extend with `--validate`)
   - Update skill steps to use these commands once available

6) Documentation alignment
   - Update `CLAUDE.md` to reflect split skills and week-at-a-time generation
   - Add a short “Approval Handoff Contract” section for main agent use

7) State tracking
   - Create `data/state/approvals.json` structure
  - Store: approved VDOT, macro approval timestamp, approved weekly JSON file path

## Validation Plan
- Happy-path dry run: VDOT proposal → approval → macro create → approval → weekly generate/apply for Week 1.
- Negative tests: missing baseline_vdot must abort macro-create; weekly generate must flag >10% macro deviation; apply must reject invalid dates/schema.
- Regression: ensure macro review docs are produced and paths reported to the main agent; confirm no workouts are written during macro creation; ensure weekly reviews are presented in chat.
- Subagent routing test: long-context conversation should still run cleanly using subagents with no athlete questions emitted from subagent output.
