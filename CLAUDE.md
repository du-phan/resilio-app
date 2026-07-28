# Claude Code guidance

Use [AGENTS.md](AGENTS.md) as the repository entry point and
[the shared agent workflow](docs/guides/development/agent-workflow.md) for
engineering, coaching, data-safety, date, weather, and approval rules.

Claude-specific notes:

- `.agents/skills` is authoritative. `.claude/skills` is a validated mirror
  for Claude Code discovery.
- Use the Bash tool for CLI checks and keep one Python environment for the
  entire session.
- The main conversation owns athlete questions and approvals. Executor skills
  are non-interactive.
- Present generated plan reviews inline to the athlete. Never direct an
  athlete to a temporary file.
- For weekly-plan approval, build the athlete-facing workout table from the
  generated JSON, then apply only the exact approved file.

Useful references:

- [Documentation index](docs/index.md)
- [Architecture map](docs/reference/architecture-map.md)
- [Coaching CLI index](docs/coaching/cli/index.md)
- [Coaching methodology](docs/coaching/methodology.md)

## Vault

Project folder: `/Users/duphan/Projects/my-obsidian-vault/projects/resilio-app/`
- `brief.md` — strategic summary, hard constraints, what Claude should know
- `status.md` — current development state and active work
- `decisions/` — 4 load-bearing decisions (interaction model, coaching style, week boundaries, load model)

Global context: `/Users/duphan/Projects/my-obsidian-vault/_global/context.md`
