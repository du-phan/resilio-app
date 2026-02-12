---
name: weekly-plan-apply
description: Applies an approved weekly plan JSON to the plan store after validation. Use only after athlete approval is recorded by the main agent.
disable-model-invocation: false
context: fork
agent: weekly-planner
allowed-tools: Bash, Read, Write
argument-hint: "approved_file=<path>"
---

# Weekly Plan Apply (Executor)

Applies a previously approved weekly JSON payload.

## Preconditions (block if missing)
- Approved weekly JSON file path provided in arguments
- Approval recorded in approvals state (week number + file path)

If missing, return a blocking checklist and stop.

## Interactivity & Feedback

- Non-interactive: do not ask the athlete questions or call approval commands.
- Apply only when approvals state matches the provided file.
- If the athlete requests changes, the main agent must re-run weekly-plan-generate and record a new approval before applying.
- If any CLI command fails (exit code ≠ 0), include the error output in your response and return a blocking checklist.

## Workflow

1) Verify approval state:
```bash
resilio approvals status
```
Confirm `weekly_approval.week_number` and `weekly_approval.approved_file` match the payload.

2) Validate payload:
```bash
resilio plan validate-week --file <APPROVED_FILE>
```

3) Apply with validation gate:
```bash
resilio plan populate --from-json <APPROVED_FILE> --validate
```

4) Confirm:
```bash
resilio plan week --week <WEEK_NUMBER>
```

## References (load only if needed)
- JSON workflow: `references/json_workflow.md`

## Output
Return:
- `applied_file`
- `week_number`
- If blocked: `blocking_checklist`
