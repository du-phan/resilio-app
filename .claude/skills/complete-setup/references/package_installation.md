# Package Installation

## Contents
- Method selection
- Poetry path
- venv path
- Validation loop
- Safety constraints

## Method selection

```bash
poetry --version >/dev/null 2>&1
```

- success -> Poetry path
- failure -> venv path

## Poetry path

```bash
poetry install
poetry run resilio --help
RESILIO_CMD="poetry run resilio"
```

If `poetry run resilio --help` fails, do not continue. Fix and retry.

## venv path

Requires `PYTHON_CMD` already selected and valid.

```bash
"$PYTHON_CMD" -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
resilio --help
RESILIO_CMD="resilio"
```

## Validation loop

After installation:

```bash
$RESILIO_CMD --help
```

If validation fails:

1. Inspect error
2. Apply targeted fix
3. Re-run validation
4. Continue only when validation succeeds

## Safety constraints

- Never use `sudo pip`
- Never install into system site-packages as a workaround
- Never skip activation in venv path
