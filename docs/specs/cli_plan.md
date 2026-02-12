# Resilio CLI — Agent-Friendly Contract

This document specifies a portable CLI for Resilio that works reliably with Claude Code, Codex CLI, Aider-like tools, and humans. It defines the command surface, output contracts, error handling, and rollout steps. The CLI is the canonical interface; the Python API remains the implementation boundary but is not the primary user/agent contract.

## Goals and Principles

- Portable across terminals: no client-specific plumbing; works with any tool that can run shell commands.
- Non-interactive by default: never prompt; require `--interactive` to allow prompts.
- JSON-first: default to machine-readable JSON; optional text mode for humans.
- Stable schemas: every response includes `schema_version`; no ad-hoc fields.
- Idempotent and safe: commands can be rerun; no destructive defaults.
- Explicit exit codes: agents branch on exit codes, not on fragile text parsing.
- Secrets safe: never emit tokens or PII in stdout/stderr/logs.

## Global CLI Behavior

- Default output: JSON to stdout; errors to stderr; exit code communicates class of failure.
- Flags: `--format json|text` (default json), `--repo-root PATH` to override auto-detection, `--interactive` to allow prompts (otherwise forbidden), `--verbose` for extra fields in text mode.
- Env knobs (optional): `RESILIO_OUTPUT=json|text`, `RESILIO_NONINTERACTIVE=1` to hard-disable prompts, `RESILIO_LOG_LEVEL=info|debug`.
- Deterministic sorting for lists in JSON to keep outputs stable for tests/agents.
- Time and units: ISO 8601 timestamps, durations in seconds, distance in meters/kilometers, loads in AU; always document units in the payload.

## Command Surface

All commands support the global flags above.

### `resilio doctor`

- Purpose: Diagnose readiness (config, secrets, token validity, data dirs, writable paths).
- Checks should include: repo root detection, `config/settings.yaml` exists + parses, `config/secrets.local.yaml` exists + parses, Strava credentials present, token expiry/freshness, required directories exist and are writable, lock file cleanliness, Python version compatibility.
- Output `data`: `checks: [{name, status: ok|warn|error, detail}]`, `errors`, `warnings`.
- Exit codes: `0` success, `2` config/setup missing, `3` auth error, `4` network, `1` internal.

### `resilio init`

- Purpose: Create data/config dirs and copy templates; safe to rerun.
- Output `data`: `created: [paths]`, `skipped: [paths]`.
- Exit codes: `0` success, `2` when blocked by missing permissions, `1` internal.

### `resilio auth`

- Subcommands:
  - `auth url`: emit authorization URL, scopes, redirect URI.
  - `auth exchange --code CODE`: exchange code, persist tokens; redact in output.
  - `auth status`: token health and expiry.
- Exit codes: `0` success, `3` auth failure, `4` network, `2` config missing, `1` internal.

### `resilio sync`

- Purpose: Fetch Strava, normalize, RPE/load, metrics refresh; idempotent. Option `--since 14d`.
- Output `data`: `activities_fetched`, `activities_new`, `activities_updated`, `activities_skipped`, `errors`, `sync_duration_seconds`, optional `metrics_updated`, `suggestions_generated`.
- Exit codes: `0` success, `3` auth, `4` network/rate-limit, `2` config missing, `5` validation/input, `1` internal.

### `resilio status`

- Purpose: Current CTL/ATL/TSB/ACWR/readiness and intensity distribution with interpretations.
- Output `data`: `ctl`, `atl`, `tsb`, `acwr`, `readiness`, `intensity_distribution` (all with value + interpretation + units where applicable).
- Exit codes: `0` success, `2` missing data, `5` validation, `1` internal.

### `resilio today`

- Purpose: Today’s recommended workout + rationale + warnings + suggestions (M10/M11).
- While not implemented, respond with `ok=false`, `error_type="not_implemented"`, exit `6`.
- Output `data`: `workout`, `rationale`, `metrics_context`, `warnings`, `suggestions` (when implemented).
- Exit codes: `0` success, `6` not implemented, `2` missing data, `1` internal.

### `resilio plan`

- `plan show`: current plan, goal, weeks, phase, constraints applied.
- `plan regen [--goal ...]`: regenerate plan, archive old plan.
- Exit codes: `0` success, `6` not implemented, `2` missing data/config, `5` validation, `1` internal.

### `resilio profile`

- `profile get`: show profile (redact secrets).
- `profile set --field value`: patch profile fields.
- Exit codes: `0` success, `2` missing data, `5` validation, `1` internal.

## Output Envelope (All Commands)

Every command returns the same top-level shape (JSON default):

```json
{
  "schema_version": "1.0",
  "ok": true,
  "error_type": null,
  "human_summary": "short, agent-friendly summary",
  "next_steps": null,
  "data": { ... command-specific payload ... }
}
```

- `error_type` values: `config`, `auth`, `rate_limit`, `network`, `validation`, `not_implemented`, `internal`.
- `human_summary`: a single, short sentence; avoid multi-line prose; include the key value if useful.
- `next_steps`: optional guidance string for non-OK responses (e.g., “run resilio init”, “refresh token”).
- Use snake_case keys; ISO 8601 dates; durations in seconds; distances in meters/kilometers; loads in AU; document units in docs.
- Redact all secrets/tokens; never echo them.

## Schema Versioning and Compatibility

- Start at `schema_version: "1.0"`; bump major on breaking changes; keep a changelog.
- Prefer additive changes; avoid field renames/removals. If removal is necessary, carry old fields until a major bump.
- Tests should pin golden outputs per `schema_version`.

## Exit Codes

- `0` success
- `2` config/setup missing or required file absent
- `3` auth/token issue
- `4` network/rate-limit
- `5` validation/user input error
- `6` not implemented/stub
- `1` internal/unknown error

## Text Mode (Optional)

- `--format text` prints concise, single-paragraph summaries. For humans only; agents should use JSON.
- Tables/lists only when `--verbose` is passed.

## Architecture Notes

- Entry point: `[tool.poetry.scripts] resilio = "resilio.cli:app"` (Typer/Click; keep deps minimal).
- CLI is a thin shim; business logic remains in core modules.
- Shared helpers:
  - Output formatter (json/text) + envelope builder.
  - Error mapping → `error_type` + exit code.
  - Repo root resolver (`get_repo_root` with `--repo-root` override).
- Config/secrets: reuse `core/config.py`; `doctor` and `auth` surface actionable fixes.
- Idempotency: `init` safe to rerun; `sync` safe to repeat; `plan regen` archives before replace.

## Security and Redaction

- Never print tokens; show only status/expiry.
- Strip PII from logs/stdout; avoid dumping raw activity notes unless explicitly requested in text mode with `--verbose` (and still avoid secrets).
- Fail closed: if redaction uncertain, omit the field.
- Ensure error messages do not leak file contents or secrets; keep file paths minimal when revealing them is necessary for remediation.

## Agent Guidance (to mirror into README/CLAUDE.md)

- “Use `poetry run resilio ... --format json` for all operations.”
- “Do not import internal Python modules directly.”
- “Start with `resilio doctor`; then `resilio init`; then `resilio auth url/exchange`; then `resilio sync`; then `resilio status`/`resilio today`.”
- “Non-interactive by default; pass `--interactive` to allow prompts (rare).”

## Testing and Stability

- Unit tests per command: argument parsing, exit codes, envelope shape.
- Golden JSON outputs for schema stability; bump `schema_version` on breaking changes.
- Integration tests: `doctor`/`init`/`auth` in temp dirs; `sync` with mocked Strava.
- CI: `ruff`, `black`, `mypy`, `pytest`.
- Backward-compat: document changes in a CLI changelog; keep old `schema_version` handling when feasible.

## Rollout Plan

1. Scaffold CLI entrypoint + envelope/error helpers.
2. Implement `doctor` and `init` first (highest UX impact).
3. Wire `auth` to existing Strava token exchange; ensure redaction.
4. Expose `sync`/`status` via current core modules; keep `today`/`plan` returning `not_implemented` until ready.
5. Add docs updates: `README.md`, `CLAUDE.md`, and a brief `docs/cli_usage.md` with examples.
6. Add tests and CI gate.
7. When M10/M11 are ready, enable `today`/`plan` and remove the `not_implemented` path.
