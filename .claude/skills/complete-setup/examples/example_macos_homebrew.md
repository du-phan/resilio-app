# Example: Fresh macOS setup (safe path)

## Scenario

- Platform: macOS
- User: non-technical
- Python: missing/too old
- Goal: complete setup safely

## Conversation Flow (abridged)

### 1) Detection summary

Coach checks, then summarizes:

```text
Environment Check (macOS):
- Python: missing
- Package: missing
- Config: missing
Next: install Python, then package, then config.
```

### 2) Python install via Homebrew

```bash
brew install python@3.12 || brew install python@3.11
```

Interpreter selection:

```bash
PYTHON_CMD="python3"   # if now >=3.11
# else explicit python3.12 or python3.11
```

Validation:

```bash
"$PYTHON_CMD" --version
"$PYTHON_CMD" -m pip --version
```

### 3) Package install (Poetry or venv)

Poetry path:

```bash
poetry install
poetry run sce --help
SCE_CMD="poetry run sce"
```

venv path:

```bash
"$PYTHON_CMD" -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
sce --help
SCE_CMD="sce"
```

### 4) Config init

```bash
$SCE_CMD init
$SCE_CMD status
```

### 5) Final verification

```bash
"$PYTHON_CMD" --version
$SCE_CMD --help
$SCE_CMD status
ls -la config/
```

## Safety notes demonstrated

- No system Python rewiring
- No symlink mutation
- No global alias requirement
- No `sudo pip`

## Optional fallback: Homebrew blocked -> pyenv

```bash
brew install pyenv
pyenv install 3.12.8
pyenv local 3.12.8
PYTHON_CMD="$(pyenv which python)"
```

Then continue with standard package/config phases.
