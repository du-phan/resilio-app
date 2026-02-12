# Complete-Setup Evaluations (macOS only)

This evaluation set validates safety-first onboarding for non-technical macOS users.

## Active scenarios

- `fresh_macos_m1.json`
- `partial_setup_recovery.json`
- `macos_pyenv_fallback.json`

## Quality gates

1. Uses deterministic detection order
2. Never uses forbidden system-mutation patterns
3. Verifies each phase before proceeding
4. Supports adaptive skip behavior for completed phases
5. Provides clear handoff to first-session
