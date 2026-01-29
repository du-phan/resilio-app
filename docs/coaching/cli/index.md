# CLI Command Index

> **Quick Start**: New to the CLI? Start with [Core Concepts](core_concepts.md)

Complete reference for Sports Coach Engine command-line interface, optimized for focused reading.

## Most Used Commands (90% of coaching sessions)

```bash
sce auth status          # Check auth → [Auth Commands](cli_auth.md)
sce sync                 # Import activities → [Data Commands](cli_data.md)
sce status               # Current metrics → [Metrics Commands](cli_metrics.md)
sce dates today          # Date context → [Date Commands](cli_dates.md)
sce today                # Today's workout → [Metrics Commands](cli_metrics.md)
sce week                 # Weekly summary → [Metrics Commands](cli_metrics.md)
sce profile get          # View profile → [Profile Commands](cli_profile.md)
sce plan week --next     # Next week's plan → [Planning Commands](cli_planning.md)
```

## Command Categories

### Session Initialization
- [**Authentication**](cli_auth.md) - OAuth flow, token management (`sce auth`)
- [**Data Management**](cli_data.md) - Init, sync, activity import (`sce init`, `sce sync`)
- [**Dates**](cli_dates.md) - Date utilities for planning (`sce dates`)

### Daily Coaching
- [**Metrics & Status**](cli_metrics.md) - Current metrics, daily workouts, weekly summaries (`sce status`, `sce today`, `sce week`)
- [**Activity Search**](cli_activity.md) - List and search activity notes (`sce activity list`, `sce activity search`)
- [**Memory**](cli_memory.md) - Injury history, preferences, insights (`sce memory`)

### Profile & Goals
- [**Profile Management**](cli_profile.md) - Create, update, sports, analyze (`sce profile`)
- [**Goal Setting**](cli_planning.md#sce-goal-set) - Set/validate goals (`sce goal set`, `sce goal validate`)

### Training Plans
- [**Planning**](cli_planning.md) - Macro plans, weekly validation, plan updates (`sce plan`)
- [**Approvals**](cli_planning.md#sce-approvals-status) - Approval state for plan apply (`sce approvals`)
- [**VDOT & Pacing**](cli_vdot.md) - Calculate, predict, adjust paces (`sce vdot`)

### Safety & Validation
- [**Risk Assessment**](cli_risk.md) - Injury risk, forecasting, taper status (`sce risk`)
- [**Guardrails**](cli_guardrails.md) - Volume limits, progression checks (`sce guardrails`)
- [**Analysis**](cli_analysis.md) - Intensity, gaps, load distribution, capacity (`sce analysis`)

### Race Management
- [**Race Commands**](cli_race.md) - Add performances, list history, import from Strava (`sce race`)

## Quick Lookup by Command

| Command | Category | File |
|---------|----------|------|
| `sce auth {url\|exchange\|status}` | Auth | [cli_auth.md](cli_auth.md) |
| `sce init` | Data | [cli_data.md](cli_data.md) |
| `sce sync [--since]` | Data | [cli_data.md](cli_data.md) |
| `sce status` | Metrics | [cli_metrics.md](cli_metrics.md) |
| `sce today [--date]` | Metrics | [cli_metrics.md](cli_metrics.md) |
| `sce week` | Metrics | [cli_metrics.md](cli_metrics.md) |
| `sce profile {create\|get\|set\|...}` | Profile | [cli_profile.md](cli_profile.md) |
| `sce goal set --type --date` | Planning | [cli_planning.md](cli_planning.md#sce-goal-set) |
| `sce goal validate` | Planning | [cli_planning.md](cli_planning.md#sce-goal-validate) |
| `sce plan {show\|week\|populate\|validate-week\|...}` | Planning | [cli_planning.md](cli_planning.md) |
| `sce approvals {status\|approve-vdot\|approve-week\|approve-macro}` | Planning | [cli_planning.md](cli_planning.md#sce-approvals-status) |
| `sce vdot {calculate\|paces\|predict\|...}` | VDOT | [cli_vdot.md](cli_vdot.md) |
| `sce activity {list\|search}` | Activity | [cli_activity.md](cli_activity.md) |
| `sce dates {today\|next-monday\|week-boundaries\|validate}` | Dates | [cli_dates.md](cli_dates.md) |
| `sce memory {add\|list\|search}` | Memory | [cli_memory.md](cli_memory.md) |
| `sce analysis {intensity\|gaps\|load\|capacity}` | Analysis | [cli_analysis.md](cli_analysis.md) |
| `sce risk {assess\|forecast\|...}` | Risk | [cli_risk.md](cli_risk.md) |
| `sce guardrails {progression\|...}` | Guardrails | [cli_guardrails.md](cli_guardrails.md) |
| `sce plan validate-week` | Planning | [cli_planning.md](cli_planning.md#sce-plan-validate-week) |
| `sce plan validate-intervals` | Planning | [cli_planning.md](cli_planning.md#sce-plan-validate-intervals) |
| `sce plan validate-structure` | Planning | [cli_planning.md](cli_planning.md#sce-plan-validate-structure) |
| `sce plan export-structure` | Planning | [cli_planning.md](cli_planning.md#sce-plan-export-structure) |
| `sce plan template-macro` | Planning | [cli_planning.md](cli_planning.md#sce-plan-template-macro) |
| `sce race {add\|list\|import-from-strava}` | Race | [cli_race.md](cli_race.md) |

## By Use Case

- **"How do I authenticate?"** → [Authentication Guide](cli_auth.md)
- **"What should I do today?"** → [`sce today`](cli_metrics.md#sce-today)
- **"How was my week?"** → [`sce week`](cli_metrics.md#sce-week) + [Analysis Commands](cli_analysis.md)
- **"Am I at risk of injury?"** → [`sce risk assess`](cli_risk.md#sce-risk-assess)
- **"Show me my training plan"** → [`sce plan show`](cli_planning.md#sce-plan-show)
- **"What are my training paces?"** → [`sce vdot paces`](cli_vdot.md#sce-vdot-paces)
- **"Find activities with ankle pain"** → [`sce activity search --query "ankle"`](cli_activity.md#sce-activity-search)
- **"Record past injury"** → [`sce memory add --type INJURY_HISTORY`](cli_memory.md#sce-memory-add)
- **"What day is this date?"** → [`sce dates validate`](cli_dates.md#sce-dates-validate)

## All Commands Reference

| Command | Purpose | Details |
|---------|---------|---------|
| **`sce init`** | Initialize data directories | [Data](cli_data.md#sce-init) |
| **`sce sync [--since 14d]`** | Import from Strava | [Data](cli_data.md#sce-sync) |
| **`sce status`** | Get current training metrics | [Metrics](cli_metrics.md#sce-status) |
| **`sce today [--date YYYY-MM-DD]`** | Get workout recommendation | [Metrics](cli_metrics.md#sce-today) |
| **`sce week`** | Get weekly summary | [Metrics](cli_metrics.md#sce-week) |
| **`sce goal set --type --date [--time]`** | Set race goal | [Planning](cli_planning.md#sce-goal-set) |
| **`sce goal validate`** | Validate existing goal | [Planning](cli_planning.md#sce-goal-validate) |
| **`sce auth url`** | Get OAuth URL | [Auth](cli_auth.md#sce-auth-url) |
| **`sce auth exchange --code`** | Exchange auth code | [Auth](cli_auth.md#sce-auth-exchange) |
| **`sce auth status`** | Check token validity | [Auth](cli_auth.md#sce-auth-status) |
| **`sce activity list [--since 30d]`** | List activities with notes | [Activity](cli_activity.md#sce-activity-list) |
| **`sce activity search --query`** | Search activity notes | [Activity](cli_activity.md#sce-activity-search) |
| **`sce memory add --type --content`** | Add structured memory | [Memory](cli_memory.md#sce-memory-add) |
| **`sce memory list [--type]`** | List memories | [Memory](cli_memory.md#sce-memory-list) |
| **`sce memory search --query`** | Search memories | [Memory](cli_memory.md#sce-memory-search) |
| **`sce profile get`** | Get athlete profile | [Profile](cli_profile.md#sce-profile-get) |
| **`sce profile set --field value`** | Update profile | [Profile](cli_profile.md#sce-profile-set) |
| **`sce profile create`** | Create new profile | [Profile](cli_profile.md#sce-profile-create) |
| **`sce profile add-sport`** | Add sport constraint | [Profile](cli_profile.md#sce-profile-add-sport) |
| **`sce profile remove-sport`** | Remove sport | [Profile](cli_profile.md#sce-profile-remove-sport) |
| **`sce profile list-sports`** | List all sports | [Profile](cli_profile.md#sce-profile-list-sports) |
| **`sce profile edit`** | Open in $EDITOR | [Profile](cli_profile.md#sce-profile-edit) |
| **`sce profile analyze`** | Analyze Strava history | [Profile](cli_profile.md#sce-profile-analyze) |
| **`sce plan show`** | Get current plan | [Planning](cli_planning.md#sce-plan-show) |
| **`sce plan week [--next\|--week N]`** | Get specific week(s) | [Planning](cli_planning.md#sce-plan-week) |
| **`sce plan create-macro`** | Generate macro plan | [Planning](cli_planning.md#sce-plan-create-macro) |
| **`sce plan populate`** | Add/update weekly workouts | [Planning](cli_planning.md#sce-plan-populate) |
| **`sce plan validate-week`** | Validate weekly plan JSON | [Planning](cli_planning.md#sce-plan-validate-week) |
| **`sce plan validate-intervals`** | Validate interval structure | [Planning](cli_planning.md#sce-plan-validate-intervals) |
| **`sce plan validate-structure`** | Validate plan structure | [Planning](cli_planning.md#sce-plan-validate-structure) |
| **`sce plan export-structure`** | Export macro structure JSON | [Planning](cli_planning.md#sce-plan-export-structure) |
| **`sce plan template-macro`** | Generate macro template JSON | [Planning](cli_planning.md#sce-plan-template-macro) |
| **`sce plan update-from`** | Replace plan weeks from a point | [Planning](cli_planning.md#sce-plan-update-from) |
| **`sce plan save-review`** | Save plan review markdown | [Planning](cli_planning.md#sce-plan-save-review) |
| **`sce plan append-week`** | Append weekly summary to log | [Planning](cli_planning.md#sce-plan-append-week) |
| **`sce plan assess-period`** | Assess completed period | [Planning](cli_planning.md#sce-plan-assess-period) |
| **`sce plan suggest-run-count`** | Suggest run count | [Planning](cli_planning.md#sce-plan-suggest-run-count) |
| **`sce dates today`** | Today's date context | [Dates](cli_dates.md#sce-dates-today) |
| **`sce dates next-monday`** | Next Monday | [Dates](cli_dates.md#sce-dates-next-monday) |
| **`sce dates week-boundaries`** | Week boundaries | [Dates](cli_dates.md#sce-dates-week-boundaries) |
| **`sce dates validate`** | Validate weekday | [Dates](cli_dates.md#sce-dates-validate) |
| **`sce vdot calculate`** | Calculate VDOT from race | [VDOT](cli_vdot.md#sce-vdot-calculate) |
| **`sce vdot paces`** | Get training pace zones | [VDOT](cli_vdot.md#sce-vdot-paces) |
| **`sce vdot predict`** | Predict race times | [VDOT](cli_vdot.md#sce-vdot-predict) |
| **`sce vdot six-second`** | Apply six-second rule | [VDOT](cli_vdot.md#sce-vdot-six-second) |
| **`sce vdot adjust`** | Adjust for conditions | [VDOT](cli_vdot.md#sce-vdot-adjust) |
| **`sce vdot estimate-current`** | Estimate from workouts | [VDOT](cli_vdot.md#sce-vdot-estimate-current) |
| **`sce race add`** | Add race performance | [Race](cli_race.md#sce-race-add) |
| **`sce race list`** | List race history | [Race](cli_race.md#sce-race-list) |
| **`sce race import-from-strava`** | Auto-detect races | [Race](cli_race.md#sce-race-import-from-strava) |
| **`sce guardrails quality-volume`** | Validate T/I/R volumes | [Guardrails](cli_guardrails.md#sce-guardrails-quality-volume) |
| **`sce guardrails progression`** | Validate progression | [Guardrails](cli_guardrails.md#sce-guardrails-progression) |
| **`sce guardrails analyze-progression`** | Analyze context | [Guardrails](cli_guardrails.md#sce-guardrails-analyze-progression) |
| **`sce guardrails long-run`** | Validate long run | [Guardrails](cli_guardrails.md#sce-guardrails-long-run) |
| **`sce guardrails safe-volume`** | Calculate safe range | [Guardrails](cli_guardrails.md#sce-guardrails-safe-volume) |
| **`sce guardrails break-return`** | Plan return after break | [Guardrails](cli_guardrails.md#sce-guardrails-break-return) |
| **`sce guardrails masters-recovery`** | Age-specific recovery | [Guardrails](cli_guardrails.md#sce-guardrails-masters-recovery) |
| **`sce guardrails race-recovery`** | Post-race recovery | [Guardrails](cli_guardrails.md#sce-guardrails-race-recovery) |
| **`sce guardrails illness-recovery`** | Illness recovery | [Guardrails](cli_guardrails.md#sce-guardrails-illness-recovery) |
| **`sce analysis intensity`** | Validate 80/20 | [Analysis](cli_analysis.md#sce-analysis-intensity) |
| **`sce analysis gaps`** | Detect gaps | [Analysis](cli_analysis.md#sce-analysis-gaps) |
| **`sce analysis load`** | Multi-sport breakdown | [Analysis](cli_analysis.md#sce-analysis-load) |
| **`sce analysis capacity`** | Check capacity | [Analysis](cli_analysis.md#sce-analysis-capacity) |
| **`sce risk assess`** | Assess injury risk | [Risk](cli_risk.md#sce-risk-assess) |
| **`sce risk recovery-window`** | Estimate recovery | [Risk](cli_risk.md#sce-risk-recovery-window) |
| **`sce risk forecast`** | Forecast stress | [Risk](cli_risk.md#sce-risk-forecast) |
| **`sce risk taper-status`** | Verify taper | [Risk](cli_risk.md#sce-risk-taper-status) |

## Error Handling & Patterns

See [Core Concepts](core_concepts.md) for:
- JSON response structure
- Exit codes (0-5)
- Error handling patterns
- Using `jq` for parsing

---

**Navigation**: [Core Concepts](core_concepts.md) | [Auth](cli_auth.md) | [Data](cli_data.md) | [Metrics](cli_metrics.md) | [Dates](cli_dates.md) | [Profile](cli_profile.md) | [Planning](cli_planning.md) | [VDOT](cli_vdot.md) | [Activity](cli_activity.md) | [Memory](cli_memory.md) | [Analysis](cli_analysis.md) | [Risk](cli_risk.md) | [Guardrails](cli_guardrails.md) | [Race](cli_race.md)
