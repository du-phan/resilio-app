# Environment Checks (macOS only)

## Contents
- Phase order
- Core checks
- Interpreter selection
- Readiness checklist

## Phase order

Run checks in this order only:

1. Repo root check
2. Platform check
3. Interpreter check/selection
4. Package runnable check
5. Config check (only if package runnable)

## Core checks

### 1) Repo root

```bash
[ -f pyproject.toml ] && [ -d resilio ]
```

### 2) Platform

```bash
uname
# Expected: Darwin
```

If not Darwin, stop setup immediately and defer.

### 3) Interpreter check

```bash
python3 --version
python3.12 --version
python3.11 --version
```

Target: `>=3.11,<4.0`.

### 4) Interpreter selection

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

### 5) Package runnable check

```bash
if command -v resilio >/dev/null 2>&1; then
  resilio --help
elif poetry --version >/dev/null 2>&1; then
  poetry run resilio --help
else
  false
fi
```

### 6) Config check (only after package runnable)

```bash
resilio status
# or: poetry run resilio status
```

Interpretation:

- `0` -> config ready
- `2` -> config missing

## Readiness checklist

Environment is ready when all pass:

- [ ] `uname` is `Darwin`
- [ ] `PYTHON_CMD` resolved and version is >= 3.11
- [ ] `resilio --help` (or `poetry run resilio --help`) succeeds
- [ ] `config/settings.yaml` exists
- [ ] `config/secrets.local.yaml` exists
- [ ] `resilio status` (or `poetry run resilio status`) succeeds

## Safety reminders

Never resolve version conflicts by mutating system Python symlinks or aliases.
Use explicit interpreter commands instead.
