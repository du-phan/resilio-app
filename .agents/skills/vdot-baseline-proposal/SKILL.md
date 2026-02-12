---
name: vdot-baseline-proposal
description: Proposes a baseline VDOT and returns evidence plus a single approval prompt for the coach. Use when a macro plan needs an approved baseline VDOT.
compatibility: Codex CLI/IDE; requires local resilio CLI and repo context
---

# VDOT Baseline Proposal (Executor)

Use CLI only. Present the review directly in chat for the coach to use.

## Preconditions (block if missing)

- Goal exists (race type/date) and profile exists
- Metrics available (`resilio status`)

If missing, return a blocking checklist and stop.

## Interactivity & Feedback

- Non-interactive: do not ask the athlete questions or call approval commands.
- Return an `athlete_prompt` for the coach to ask and capture approval.
- If the athlete declines or requests changes, the coach will re-run this skill with notes; treat notes as hard constraints and generate a new proposal.
- If new constraints are provided (injury, schedule limits), assume the coach updated profile/memory before re-run.

## Metric explainer rule (athlete-facing)

If the athlete_prompt mentions any metrics, add a first-mention explainer. If multiple metrics appear together, use a single "Quick defs" line. Do not repeat unless the athlete asks or seems confused. For multi-sport athletes, add a brief clause tying the metric to total work across running + other sports (e.g., climbing/cycling).

Use this exact VDOT explainer on first mention:
"VDOT is a running fitness score based on your recent race or hard-effort times. I use it to set your training paces so your running stays matched to your current fitness alongside your other sports."

One-line definitions for other metrics:
- CTL: "CTL is your long-term training load—think of it as your 6-week fitness trend."
- ATL: "ATL is your short-term load—basically how much you've trained in the past week."
- TSB: "TSB is freshness (long-term fitness minus short-term fatigue)."
- ACWR: "ACWR compares this week to your recent average; high values mean a sudden spike."
- Readiness: "Readiness is a recovery score—higher usually means you can handle harder work."
- RPE: "RPE is your perceived effort from 1–10."

## Workflow

1. Gather evidence:

```bash
resilio profile get
resilio status
resilio vdot estimate-current --lookback-days 90  # Longer lookback for continuity analysis
resilio activity list --since 30d --sport run
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
  - Adding a PB (`resilio profile set-pb --distance 10k --time MM:SS --date YYYY-MM-DD`)
  - Running quality workouts (tempo, threshold, interval)
  - Running easy runs consistently (requires max_hr in profile)

The system will NOT provide a CTL-based guess - we need actual pace data.

3. Get pace ranges:

```bash
resilio vdot paces --vdot <VDOT>
```

4. Present directly in chat:

- Proposed VDOT + confidence + source
- Recent evidence (race or key workouts)
- Pace table (easy/tempo/interval/long)
- Single approval prompt text for the athlete
- Handoff note: coach must record approval via
  `resilio approvals approve-vdot --value <VDOT>`

## References (load only if needed)

- VDOT methodology: `docs/coaching/methodology.md`
- Pace zones reference: `references/pace_zones.md`

## Output

Return:

- `proposed_vdot`
- `athlete_prompt` (single yes/no + adjustment question)
- If blocked: `blocking_checklist`
