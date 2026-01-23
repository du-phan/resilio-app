---
name: weekly-planning
description: Deprecated wrapper for weekly planning. Use weekly-plan-generate and weekly-plan-apply instead.
disable-model-invocation: true
allowed-tools: Read
---

# Weekly Planning (Deprecated)

This skill is deprecated. Use the executor skills instead:

- `weekly-plan-generate` to create the weekly JSON + present review in chat
- `weekly-plan-apply` to validate and persist an approved weekly plan

This keeps all athlete dialogue and approvals in the main agent and enforces the generate → approve → apply loop.
