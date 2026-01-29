---
name: weekly-plan-apply
description: Applies an approved weekly plan JSON to the plan store after validation. Use only after athlete approval is recorded by the main agent.
disable-model-invocation: true
context: fork
agent: weekly-planner
allowed-tools: Bash, Read, Write
argument-hint: "approved_file=<path>"
---

# Weekly Plan Apply (Executor)

Non-interactive. Applies a previously approved weekly JSON payload.

## Preconditions (block if missing)
- Approved weekly JSON file path provided in arguments
- Approval recorded in approvals state (week number + file path)

If missing, return a blocking checklist and stop.

## Workflow

1) Verify approval state:
```bash
sce approvals status
```
Confirm `weekly_approval.week_number` and `weekly_approval.approved_file` match the payload.

2) Validate payload:
```bash
sce plan validate-week --file <APPROVED_FILE>
```

3) Apply with validation gate:
```bash
sce plan populate --from-json <APPROVED_FILE> --validate
```

4) Confirm:
```bash
sce plan week --week <WEEK_NUMBER>
```

## References (load only if needed)
- JSON workflow: `references/json_workflow.md`

## Output
Return:
- `applied_file`
- `week_number`
