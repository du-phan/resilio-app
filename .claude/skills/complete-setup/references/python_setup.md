# Python Setup (macOS only)

## Contents
- Target versions
- Primary path (Homebrew)
- Fallback path (pyenv)
- Validation
- Safety constraints

## Target versions

- Minimum: Python 3.11.0
- Supported: Python 3.11.x and 3.12.x
- Preferred for new installs: 3.12.x

## Primary path: Homebrew

### Prerequisite

```bash
which brew
```

If missing, install Homebrew first.

### Install Python

```bash
brew install python@3.12 || brew install python@3.11
```

### Select interpreter safely

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

## Fallback path: pyenv (fallback only)

Use this only when Homebrew/system Python installation is blocked.

### Install and use pyenv

```bash
brew install pyenv
pyenv install 3.12.8
pyenv local 3.12.8
PYTHON_CMD="$(pyenv which python)"
```

### Minimal shell init (only if pyenv command unavailable after install)

```bash
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc
```

## Validation

```bash
"$PYTHON_CMD" --version
"$PYTHON_CMD" -m pip --version
```

Both commands must succeed.

## Safety constraints

Do not use these patterns:

- Replacing `/usr/bin/python3`
- Any OS-level command that repoints the default `python3`
- Global aliasing of `python3`

Always select and use an explicit interpreter command instead.
