---
name: complete-setup
description: Sets up the Sports Coach Engine environment for non-technical users on macOS with safe, gated validation. Use when users ask to get started, install dependencies, or recover an interrupted setup session.
---

# Complete Setup (macOS only)

## Scope

This skill performs safe environment setup for beginners on **macOS only**.

If the platform is not macOS, stop and explain that non-macOS setup is deferred in this iteration.

Python support target: `>=3.11,<4.0`.

## Safety Rules (hard)

Never do these during onboarding:

- Replace or delete system Python binaries/symlinks
- Change OS-managed default Python interpreter mapping
- Require global shell aliases for `python3`
- Use `sudo pip`
- Advance to the next phase before validation passes

Always prefer explicit interpreter usage (`python3.12` or `python3.11`) over system mutation.

## Workflow Checklist

Copy and update this checklist while running setup:

```text
Setup Progress:
- [ ] Phase 1: Detection gates passed
- [ ] Phase 2: Python available (>=3.11)
- [ ] Phase 3: Package installed and `sce` runnable
- [ ] Phase 4: Config initialized
- [ ] Phase 5: Final verification + handoff
```

## Phase 1: Detection Gates (must run in order)

### Gate 1: Repo root

```bash
if [ ! -f pyproject.toml ] || [ ! -d sports_coach_engine ]; then
  echo "Not in repo root. cd into sports-coach-engine and retry."
  exit 1
fi
```

### Gate 2: Platform

```bash
uname
```

- `Darwin` -> continue
- anything else -> stop with defer message

### Gate 3: Interpreter selection (safe)

```bash
PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  PYTHON_CMD="python3"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_CMD="python3.12"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_CMD="python3.11"
fi
```

- `PYTHON_CMD` set -> Python gate passed
- empty -> run Phase 2

### Gate 4: Install path discovery

```bash
poetry --version >/dev/null 2>&1
```

- success -> Poetry path available
- failure -> venv path

### Gate 5: Package runnable check

```bash
PACKAGE_READY=false
if command -v sce >/dev/null 2>&1; then
  sce --help >/dev/null 2>&1 && PACKAGE_READY=true
elif poetry --version >/dev/null 2>&1; then
  poetry run sce --help >/dev/null 2>&1 && PACKAGE_READY=true
fi
```

### Gate 6: Config check (only after package runnable)

If package is runnable:

```bash
if command -v sce >/dev/null 2>&1; then
  sce status
else
  poetry run sce status
fi
```

- exit `0` -> config ready
- exit `2` -> config missing (run Phase 4)

## Phase 2: Python setup (macOS)

Run only when `PYTHON_CMD` is empty.

### Primary path: Homebrew

1. Ensure Homebrew exists (`which brew`)
2. Install Python (prefer 3.12, accept 3.11)

```bash
brew install python@3.12 || brew install python@3.11
```

3. Re-run interpreter selection (Gate 3)

### Fallback path: pyenv (fallback only)

Use only if Homebrew/system install is blocked (managed device, no admin rights, persistent conflicts).

```bash
brew install pyenv
pyenv install 3.12.8
pyenv local 3.12.8
PYTHON_CMD="$(pyenv which python)"
```

### Phase 2 validation

```bash
"$PYTHON_CMD" --version
"$PYTHON_CMD" -m pip --version
```

Do not continue unless both succeed.

## Phase 3: Package installation

Run only when package is not runnable.

### Path A: Poetry available

```bash
poetry install
poetry run sce --help
SCE_CMD="poetry run sce"
```

### Path B: venv (explicit interpreter)

```bash
"$PYTHON_CMD" -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
sce --help
SCE_CMD="sce"
```

Validation gate: `SCE_CMD --help` must pass before Phase 4.

## Phase 4: Config initialization

Run only when config is missing.

```bash
$SCE_CMD init
$SCE_CMD status
ls -la config/
```

Config is ready only when both files exist:

- `config/settings.yaml`
- `config/secrets.local.yaml`

## Phase 5: Final verification + handoff

```bash
"$PYTHON_CMD" --version
$SCE_CMD --help
$SCE_CMD status
ls -la config/
```

Successful completion message should include:

- Python ready (`>=3.11`)
- `sce` runnable
- config initialized

Then hand off to `first-session` for Strava credentials/auth + profile setup.

## References

- `references/environment_checks.md`
- `references/python_setup.md`
- `references/package_installation.md`
- `references/troubleshooting.md`
- `examples/example_macos_homebrew.md`
- `evaluations/`
