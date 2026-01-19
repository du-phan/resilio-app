# CLI Command Reference

> **Note**: This is a **skill-specific extract** containing only commands relevant to injury risk management workflows. For comprehensive CLI documentation, see `docs/coaching/cli_reference.md`.

Quick reference for injury risk management commands.

---

## Risk Assessment

```bash
# Current risk status
sce risk assess --metrics metrics.json --recent activities.json

# 4-week forecast
sce risk forecast --weeks 4 --metrics metrics.json --plan plan.json

# Taper-specific risk (race prep)
sce risk taper-status --race-date [YYYY-MM-DD] --metrics metrics.json --recent-weeks recent.json
```

---

## Guardrails

```bash
# Volume progression check
sce guardrails progression --previous [X] --current [Y]

# Quality volume limits
sce guardrails quality-volume --t-pace [X] --i-pace [Y] --r-pace [Z] --weekly-volume [W]

# Long run validation
sce guardrails long-run --duration [M] --weekly-volume [V] --pct-limit 30

# Break return protocol
sce guardrails break-return --days [N] --ctl [X] --cross-training [level]

# Illness recovery protocol
sce guardrails illness-recovery --severity [level] --days-missed [N]
```

---

## Analysis

```bash
# Intensity distribution (80/20 check)
sce analysis intensity --activities activities.json --days 28

# Multi-sport load breakdown
sce analysis load --activities activities.json --days 7 --priority [equal|primary|secondary]

# Current metrics
sce status

# Weekly summary
sce week
```
