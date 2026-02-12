# Troubleshooting (macOS only)

## Contents
- Python not found
- Python too old
- Homebrew unavailable
- `sce` not found
- Config missing
- Forbidden fixes

## Python not found

### Symptoms

- `python3 --version` fails
- `python3.12 --version` fails
- `python3.11 --version` fails

### Fix

1. Install via Homebrew (`python@3.12`, fallback `python@3.11`)
2. Re-run interpreter selection
3. Validate with `"$PYTHON_CMD" --version`

## Python too old

### Symptoms

`python3 --version` reports `<3.11`

### Fix

- Keep system Python unchanged
- Install supported Python via Homebrew
- Use explicit `PYTHON_CMD` for venv creation and package install

## Homebrew unavailable or blocked

### Symptoms

- Homebrew install disallowed on managed device
- Homebrew commands blocked

### Fix

Use pyenv fallback:

```bash
brew install pyenv
pyenv install 3.12.8
pyenv local 3.12.8
PYTHON_CMD="$(pyenv which python)"
```

## `sce` not found after install

### Poetry path

```bash
poetry run sce --help
```

If this works, use Poetry runner (`SCE_CMD="poetry run sce"`).

### venv path

```bash
echo "$VIRTUAL_ENV"
source .venv/bin/activate
sce --help
```

## Config missing

If package command works but config missing:

```bash
$SCE_CMD init
$SCE_CMD status
```

## Forbidden fixes (do not use)

- deleting `/usr/bin/python3`
- creating/replacing system `python3` symlinks
- using OS alternatives tooling to switch the default `python3`
- setting global shell aliases for `python3`
- `sudo pip ...`
