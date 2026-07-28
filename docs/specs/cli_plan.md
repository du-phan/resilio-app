# CLI architecture

The Typer CLI is a thin JSON-envelope presentation layer over the Python API
and provider-neutral core services.

## Rules

- Commands parse arguments, call API/core read surfaces, serialize one
  envelope, and select an exit code.
- Domain calculations and HTTP requests do not live in command modules.
- Credentials come only from `.env.local` through `load_config`.
- Missing credentials, rejected authentication/authorization, rate limiting,
  invalid payloads, partial sync, and safety failures remain distinguishable.
- Athlete-facing output never exposes keys, raw payloads, internal file paths,
  or obsolete implementation vocabulary.

## Main command groups

`auth`, `sync`, `activity`, `metrics`, `profile`, `status`, `week`, `today`,
`dates`, `weather`, `memory`, `performance`, `vdot`, `goal`, `plan`,
`approvals`, `analysis`, `guardrails`, `workout`, and `activity-migration`.

The generated `--help` output is the command/option authority. Narrative usage
is indexed in [the coaching CLI guide](../coaching/cli/index.md).
