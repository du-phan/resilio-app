---
name: vdot-baseline-proposal
description: Proposes a baseline VDOT and returns evidence plus a single approval prompt for the main agent. Use when a macro plan needs an approved baseline VDOT.
disable-model-invocation: true
context: fork
agent: vdot-analyst
allowed-tools: Bash, Read
argument-hint: "[notes]"
---

# VDOT Baseline Proposal (Executor)

Use CLI only. Present the review directly in chat for the main agent to use.

## Preconditions (block if missing)

- Goal exists (race type/date) and profile exists
- Metrics available (`sce status`)

If missing, return a blocking checklist and stop.

## Interactivity & Feedback

- Non-interactive: do not ask the athlete questions or call approval commands.
- Return an `athlete_prompt` for the main agent to ask and capture approval.
- If the athlete declines or requests changes, the main agent will re-run this skill with notes; treat notes as hard constraints and generate a new proposal.
- If new constraints are provided (injury, schedule limits), assume the main agent updated profile/memory before re-run.
- If any CLI command fails (exit code ≠ 0), include the error output in your response and return a blocking checklist.

**Metric explainer rule**: See CLAUDE.md "Metric one-liners" for first-mention definitions. Include them in athlete_prompt if metrics are mentioned.

## Workflow

1. Gather evidence:

```bash
sce profile get          # Includes personal_bests section
sce status
sce vdot estimate-current --lookback-days 90  # Longer lookback for continuity analysis
sce activity list --since 30d --sport run
```

**NEW: Understanding estimate-current output:**
- `source` field explains estimation method (e.g., "race_decay_adjusted (75% continuity)")
- `confidence`: HIGH (recent race/3+ workouts), MEDIUM (decay + validation), LOW (single workout/easy pace)
- May include HR-detected easy runs if max_hr is in profile
- Training continuity score shown when using race decay
- Clear error message if insufficient data (no CTL-based fallback)

2. Choose a baseline VDOT:

Strategy (automatic via `vdot estimate-current`):
- **Recent race (<90 days)**: Use race VDOT directly (HIGH confidence)
- **Older race (≥90 days)**: Apply continuity-aware decay
  - Analyzes actual training breaks (not just elapsed time)
  - Validates with recent pace data (quality + HR-based easy runs)
  - Uses Daniels' Table 9.2 decay methodology
- **No race**: Use pace analysis (quality workouts → HR-detected easy runs)
- **Insufficient data**: Return error asking athlete to establish baseline via:
  - Adding a PB (`sce profile set-pb --distance 10k --time MM:SS --date YYYY-MM-DD`)
  - Running quality workouts (tempo, threshold, interval)
  - Running easy runs consistently (requires max_hr in profile)

The system will NOT provide a CTL-based guess - we need actual pace data.

3. Get pace ranges:

```bash
sce vdot paces --vdot <VDOT>
```

4. Present directly in chat:

- Proposed VDOT + confidence + source
- Recent evidence (race or key workouts)
- Pace table (easy/tempo/interval/long)
- Single approval prompt text for the athlete
- Handoff note: main agent must record approval via
  `sce approvals approve-vdot --value <VDOT>`

## References (load only if needed)

- VDOT methodology: `docs/coaching/methodology.md`
- Pace zones reference: `references/pace_zones.md`

## Output

Return:

- `proposed_vdot`
- `athlete_prompt` (single yes/no + adjustment question)
- If blocked: `blocking_checklist`
