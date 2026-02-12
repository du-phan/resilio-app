# CLI Command Index

> **Quick Start**: New to the CLI? Start with [Core Concepts](core_concepts.md)

Complete reference for Resilio command-line interface, optimized for focused reading.

## Most Used Commands (90% of coaching sessions)

```bash
resilio auth status          # Check auth → [Auth Commands](cli_auth.md)
resilio sync                 # Import activities (smart sync) → [Sync Commands](cli_sync.md)
resilio status               # Current metrics → [Metrics Commands](cli_metrics.md)
resilio dates today          # Date context → [Date Commands](cli_dates.md)
resilio today                # Today's workout → [Metrics Commands](cli_metrics.md)
resilio week                 # Weekly summary → [Metrics Commands](cli_metrics.md)
resilio profile get          # View profile → [Profile Commands](cli_profile.md)
resilio plan week --next     # Next week's plan → [Planning Commands](cli_planning.md)
```

## Command Categories

### Session Initialization
- [**Authentication**](cli_auth.md) - OAuth flow, token management (`resilio auth`)
- [**Sync**](cli_sync.md) - Smart sync, Strava activity import (`resilio sync`)
- [**Data Management**](cli_data.md) - Init, activity import (`resilio init`)
- [**Data Structure**](cli_data_structure.md) - Understanding activity storage organization
- [**Dates**](cli_dates.md) - Date utilities for planning (`resilio dates`)

### Daily Coaching
- [**Metrics & Status**](cli_metrics.md) - Current metrics, daily workouts, weekly summaries (`resilio status`, `resilio today`, `resilio week`)
- [**Activity Search**](cli_activity.md) - List and search activity notes (`resilio activity list`, `resilio activity search`)
- [**Memory**](cli_memory.md) - Injury history, preferences, insights (`resilio memory`)

### Profile & Goals
- [**Profile Management**](cli_profile.md) - Create, update, sports, analyze (`resilio profile`)
- [**Goal Setting**](cli_planning.md#resilio-goal-set) - Set/validate goals (`resilio goal set`, `resilio goal validate`)

### Training Plans
- [**Planning**](cli_planning.md) - Macro plans, weekly validation, plan updates (`resilio plan`)
- [**Approvals**](cli_planning.md#resilio-approvals-status) - Approval state for plan apply (`resilio approvals`)
- [**VDOT & Pacing**](cli_vdot.md) - Calculate, predict, adjust paces (`resilio vdot`)

### Safety & Validation
- [**Risk Assessment**](cli_risk.md) - Injury risk, forecasting, taper status (`resilio risk`)
- [**Guardrails**](cli_guardrails.md) - Volume limits, progression checks (`resilio guardrails`)
- [**Analysis**](cli_analysis.md) - Intensity, gaps, load distribution, capacity (`resilio analysis`)

### Personal Bests
- [**Profile Commands**](cli_profile.md) - Set PBs with `resilio profile set-pb`

## Quick Lookup by Command

| Command | Category | File |
|---------|----------|------|
| `resilio auth {url\|exchange\|status}` | Auth | [cli_auth.md](cli_auth.md) |
| `resilio init` | Data | [cli_data.md](cli_data.md) |
| `resilio sync [--since]` | Sync | [cli_sync.md](cli_sync.md) |
| `resilio status` | Metrics | [cli_metrics.md](cli_metrics.md) |
| `resilio today [--date]` | Metrics | [cli_metrics.md](cli_metrics.md) |
| `resilio week` | Metrics | [cli_metrics.md](cli_metrics.md) |
| `resilio profile {create\|get\|set\|...}` | Profile | [cli_profile.md](cli_profile.md) |
| `resilio goal set --type --date` | Planning | [cli_planning.md](cli_planning.md#resilio-goal-set) |
| `resilio goal validate` | Planning | [cli_planning.md](cli_planning.md#resilio-goal-validate) |
| `resilio plan {show\|week\|populate\|validate-week\|...}` | Planning | [cli_planning.md](cli_planning.md) |
| `resilio approvals {status\|approve-vdot\|approve-week\|approve-macro}` | Planning | [cli_planning.md](cli_planning.md#resilio-approvals-status) |
| `resilio vdot {calculate\|paces\|predict\|...}` | VDOT | [cli_vdot.md](cli_vdot.md) |
| `resilio activity {list\|search}` | Activity | [cli_activity.md](cli_activity.md) |
| `resilio dates {today\|next-monday\|week-boundaries\|validate}` | Dates | [cli_dates.md](cli_dates.md) |
| `resilio memory {add\|list\|search}` | Memory | [cli_memory.md](cli_memory.md) |
| `resilio analysis {intensity\|gaps\|load\|capacity}` | Analysis | [cli_analysis.md](cli_analysis.md) |
| `resilio risk {assess\|forecast\|...}` | Risk | [cli_risk.md](cli_risk.md) |
| `resilio guardrails {progression\|...}` | Guardrails | [cli_guardrails.md](cli_guardrails.md) |
| `resilio plan validate-week` | Planning | [cli_planning.md](cli_planning.md#resilio-plan-validate-week) |
| `resilio plan validate-intervals` | Planning | [cli_planning.md](cli_planning.md#resilio-plan-validate-intervals) |
| `resilio plan validate-structure` | Planning | [cli_planning.md](cli_planning.md#resilio-plan-validate-structure) |
| `resilio plan export-structure` | Planning | [cli_planning.md](cli_planning.md#resilio-plan-export-structure) |
| `resilio plan template-macro` | Planning | [cli_planning.md](cli_planning.md#resilio-plan-template-macro) |
| `resilio profile set-pb --distance --time --date` | Profile | [cli_profile.md](cli_profile.md) |

## By Use Case

- **"How do I authenticate?"** → [Authentication Guide](cli_auth.md)
- **"What should I do today?"** → [`resilio today`](cli_metrics.md#resilio-today)
- **"How was my week?"** → [`resilio week`](cli_metrics.md#resilio-week) + [Analysis Commands](cli_analysis.md)
- **"Am I at risk of injury?"** → [`resilio risk assess`](cli_risk.md#resilio-risk-assess)
- **"Show me my training plan"** → [`resilio plan show`](cli_planning.md#resilio-plan-show)
- **"What are my training paces?"** → [`resilio vdot paces`](cli_vdot.md#resilio-vdot-paces)
- **"Find activities with ankle pain"** → [`resilio activity search --query "ankle"`](cli_activity.md#resilio-activity-search)
- **"Record past injury"** → [`resilio memory add --type INJURY_HISTORY`](cli_memory.md#resilio-memory-add)
- **"What day is this date?"** → [`resilio dates validate`](cli_dates.md#resilio-dates-validate)

## All Commands Reference

| Command | Purpose | Details |
|---------|---------|---------|
| **`resilio init`** | Initialize data directories | [Data](cli_data.md#resilio-init) |
| **`resilio sync [--since 14d]`** | Import from Strava | [Data](cli_data.md#resilio-sync) |
| **`resilio status`** | Get current training metrics | [Metrics](cli_metrics.md#resilio-status) |
| **`resilio today [--date YYYY-MM-DD]`** | Get workout recommendation | [Metrics](cli_metrics.md#resilio-today) |
| **`resilio week`** | Get weekly summary | [Metrics](cli_metrics.md#resilio-week) |
| **`resilio goal set --type [--date|--horizon-weeks] [--time]`** | Set goal | [Planning](cli_planning.md#resilio-goal-set) |
| **`resilio goal validate`** | Validate existing goal | [Planning](cli_planning.md#resilio-goal-validate) |
| **`resilio auth url`** | Get OAuth URL | [Auth](cli_auth.md#resilio-auth-url) |
| **`resilio auth exchange --code`** | Exchange auth code | [Auth](cli_auth.md#resilio-auth-exchange) |
| **`resilio auth status`** | Check token validity | [Auth](cli_auth.md#resilio-auth-status) |
| **`resilio activity list [--since 30d]`** | List activities with notes | [Activity](cli_activity.md#resilio-activity-list) |
| **`resilio activity search --query`** | Search activity notes | [Activity](cli_activity.md#resilio-activity-search) |
| **`resilio memory add --type --content`** | Add structured memory | [Memory](cli_memory.md#resilio-memory-add) |
| **`resilio memory list [--type]`** | List memories | [Memory](cli_memory.md#resilio-memory-list) |
| **`resilio memory search --query`** | Search memories | [Memory](cli_memory.md#resilio-memory-search) |
| **`resilio profile get`** | Get athlete profile | [Profile](cli_profile.md#resilio-profile-get) |
| **`resilio profile set --field value`** | Update profile | [Profile](cli_profile.md#resilio-profile-set) |
| **`resilio profile create`** | Create new profile | [Profile](cli_profile.md#resilio-profile-create) |
| **`resilio profile add-sport`** | Add sport constraint | [Profile](cli_profile.md#resilio-profile-add-sport) |
| **`resilio profile remove-sport`** | Remove sport | [Profile](cli_profile.md#resilio-profile-remove-sport) |
| **`resilio profile list-sports`** | List all sports | [Profile](cli_profile.md#resilio-profile-list-sports) |
| **`resilio profile edit`** | Open in $EDITOR | [Profile](cli_profile.md#resilio-profile-edit) |
| **`resilio profile analyze`** | Analyze Strava history | [Profile](cli_profile.md#resilio-profile-analyze) |
| **`resilio plan show`** | Get current plan | [Planning](cli_planning.md#resilio-plan-show) |
| **`resilio plan week [--next\|--week N]`** | Get specific week(s) | [Planning](cli_planning.md#resilio-plan-week) |
| **`resilio plan create-macro`** | Generate macro plan | [Planning](cli_planning.md#resilio-plan-create-macro) |
| **`resilio plan populate`** | Add/update weekly workouts | [Planning](cli_planning.md#resilio-plan-populate) |
| **`resilio plan validate-week`** | Validate weekly plan JSON | [Planning](cli_planning.md#resilio-plan-validate-week) |
| **`resilio plan validate-intervals`** | Validate interval structure | [Planning](cli_planning.md#resilio-plan-validate-intervals) |
| **`resilio plan validate-structure`** | Validate plan structure | [Planning](cli_planning.md#resilio-plan-validate-structure) |
| **`resilio plan export-structure`** | Export macro structure JSON | [Planning](cli_planning.md#resilio-plan-export-structure) |
| **`resilio plan template-macro`** | Generate macro template JSON | [Planning](cli_planning.md#resilio-plan-template-macro) |
| **`resilio plan update-from`** | Replace plan weeks from a point | [Planning](cli_planning.md#resilio-plan-update-from) |
| **`resilio plan save-review`** | Save plan review markdown | [Planning](cli_planning.md#resilio-plan-save-review) |
| **`resilio plan append-week`** | Append weekly summary to log | [Planning](cli_planning.md#resilio-plan-append-week) |
| **`resilio plan assess-period`** | Assess completed period | [Planning](cli_planning.md#resilio-plan-assess-period) |
| **`resilio plan suggest-run-count`** | Suggest run count | [Planning](cli_planning.md#resilio-plan-suggest-run-count) |
| **`resilio dates today`** | Today's date context | [Dates](cli_dates.md#resilio-dates-today) |
| **`resilio dates next-monday`** | Next Monday | [Dates](cli_dates.md#resilio-dates-next-monday) |
| **`resilio dates week-boundaries`** | Week boundaries | [Dates](cli_dates.md#resilio-dates-week-boundaries) |
| **`resilio dates validate`** | Validate weekday | [Dates](cli_dates.md#resilio-dates-validate) |
| **`resilio vdot calculate`** | Calculate VDOT from race | [VDOT](cli_vdot.md#resilio-vdot-calculate) |
| **`resilio vdot paces`** | Get training pace zones | [VDOT](cli_vdot.md#resilio-vdot-paces) |
| **`resilio vdot predict`** | Predict race times | [VDOT](cli_vdot.md#resilio-vdot-predict) |
| **`resilio vdot six-second`** | Apply six-second rule | [VDOT](cli_vdot.md#resilio-vdot-six-second) |
| **`resilio vdot adjust`** | Adjust for conditions | [VDOT](cli_vdot.md#resilio-vdot-adjust) |
| **`resilio vdot estimate-current`** | Estimate from workouts | [VDOT](cli_vdot.md#resilio-vdot-estimate-current) |
| **`resilio profile set-pb`** | Set personal best | [Profile](cli_profile.md#resilio-profile-set-pb) |
| **`resilio guardrails quality-volume`** | Validate T/I/R volumes | [Guardrails](cli_guardrails.md#resilio-guardrails-quality-volume) |
| **`resilio guardrails progression`** | Validate progression | [Guardrails](cli_guardrails.md#resilio-guardrails-progression) |
| **`resilio guardrails analyze-progression`** | Analyze context | [Guardrails](cli_guardrails.md#resilio-guardrails-analyze-progression) |
| **`resilio guardrails long-run`** | Validate long run | [Guardrails](cli_guardrails.md#resilio-guardrails-long-run) |
| **`resilio guardrails feasible-volume`** | Validate feasibility | [Guardrails](cli_guardrails.md#resilio-guardrails-feasible-volume) |
| **`resilio guardrails safe-volume`** | Calculate safe range | [Guardrails](cli_guardrails.md#resilio-guardrails-safe-volume) |
| **`resilio guardrails break-return`** | Plan return after break | [Guardrails](cli_guardrails.md#resilio-guardrails-break-return) |
| **`resilio guardrails masters-recovery`** | Age-specific recovery | [Guardrails](cli_guardrails.md#resilio-guardrails-masters-recovery) |
| **`resilio guardrails race-recovery`** | Post-race recovery | [Guardrails](cli_guardrails.md#resilio-guardrails-race-recovery) |
| **`resilio guardrails illness-recovery`** | Illness recovery | [Guardrails](cli_guardrails.md#resilio-guardrails-illness-recovery) |
| **`resilio analysis intensity`** | Validate 80/20 | [Analysis](cli_analysis.md#resilio-analysis-intensity) |
| **`resilio analysis gaps`** | Detect gaps | [Analysis](cli_analysis.md#resilio-analysis-gaps) |
| **`resilio analysis load`** | Multi-sport breakdown | [Analysis](cli_analysis.md#resilio-analysis-load) |
| **`resilio analysis capacity`** | Check capacity | [Analysis](cli_analysis.md#resilio-analysis-capacity) |
| **`resilio risk assess`** | Assess training risk | [Risk](cli_risk.md#resilio-risk-assess) |
| **`resilio risk recovery-window`** | Estimate recovery | [Risk](cli_risk.md#resilio-risk-recovery-window) |
| **`resilio risk forecast`** | Forecast stress | [Risk](cli_risk.md#resilio-risk-forecast) |
| **`resilio risk taper-status`** | Verify taper | [Risk](cli_risk.md#resilio-risk-taper-status) |

## Error Handling & Patterns

See [Core Concepts](core_concepts.md) for:
- JSON response structure
- Exit codes (0-5)
- Error handling patterns
- Using `jq` for parsing

---

**Navigation**: [Core Concepts](core_concepts.md) | [Auth](cli_auth.md) | [Data](cli_data.md) | [Metrics](cli_metrics.md) | [Dates](cli_dates.md) | [Profile](cli_profile.md) | [Planning](cli_planning.md) | [VDOT](cli_vdot.md) | [Activity](cli_activity.md) | [Memory](cli_memory.md) | [Analysis](cli_analysis.md) | [Risk](cli_risk.md) | [Guardrails](cli_guardrails.md)
