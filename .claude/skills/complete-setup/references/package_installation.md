# Package Installation Reference

## Contents
- [Installation Method Selection](#installation-method-selection)
- [Path A: Poetry Installation](#path-a-poetry-installation)
- [Path B: venv Installation](#path-b-venv-installation)
- [Mixed State Detection](#mixed-state-detection)
- [Validation and Verification](#validation-and-verification)
- [Troubleshooting Command Not Found](#troubleshooting-command-not-found)

---

## Installation Method Selection

Determine which method to use based on Poetry availability:

```bash
poetry --version
# Exit 0 = available → Use Path A (Poetry)
# Exit 127 = not found → Use Path B (venv)
```

**Recommendation**: Poetry if available (manages dependencies + venv automatically)

**Key Differences**:

| Aspect | Poetry | venv |
|--------|--------|------|
| Dependency management | Automatic via poetry.lock | Manual via requirements.txt |
| Virtual environment | Created automatically | Manual creation required |
| Installation command | `poetry install` | `pip install -e .` |
| Running commands | `sce` or `poetry run sce` | `sce` (after activation) |
| Setup complexity | Lower (one command) | Higher (multiple steps) |
| Activation required | No (automatic) | Yes (`source .venv/bin/activate`) |

---

## Path A: Poetry Installation

### Poetry Advantages

- **Dependency Management**: Automatically resolves and installs all dependencies from `poetry.lock`
- **Virtual Environment**: Creates and manages venv automatically - no manual activation needed
- **Reproducibility**: Lock file ensures everyone gets same dependency versions
- **Developer Experience**: Single command setup, automatic PATH management

### Installation Steps

```bash
# Step 1: Verify Poetry is available
poetry --version
# Expected: Poetry (version 1.x.x)

# Step 2: Install all dependencies (including sports-coach-engine)
poetry install
# This command:
# - Creates/activates a virtual environment automatically (if not exists)
# - Reads pyproject.toml for project metadata
# - Reads poetry.lock for exact dependency versions
# - Installs all dependencies in isolated environment
# - Installs sports-coach-engine in editable mode
# - Takes 30-60 seconds typically

# Step 3: Verify sce command is available
sce --help
# Expected exit code: 0

# Alternative verification (if sce not in PATH yet)
poetry run sce --help
# This explicitly runs sce inside Poetry's virtual environment
```

### Success Indicators

After `poetry install` completes successfully, you should see:

1. **Progress Output**:
   ```
   Creating virtualenv sports-coach-engine in /path/to/.venv
   Installing dependencies from lock file

   Package operations: 45 installs, 0 updates, 0 removals

     • Installing certifi (2023.x.x)
     • Installing charset-normalizer (3.x.x)
     ...
     • Installing sports-coach-engine (1.x.x)
   ```

2. **No Error Messages**: Check for:
   - ❌ "SolverProblemError" (dependency conflict)
   - ❌ "Lock file is not compatible" (poetry.lock out of sync)
   - ❌ "Command not found: poetry" (Poetry not installed)

3. **Command Verification**:
   ```bash
   sce --help
   # Returns exit code 0
   ```

### Common Poetry Issues

#### Issue 1: poetry.lock out of sync

**Symptom**: Error message during `poetry install`:
```
Error: The lock file is not compatible with the current version of Poetry.
```

**Cause**: poetry.lock was created with different Poetry version or pyproject.toml changed

**Fix**:
```bash
# Regenerate lock file without updating dependencies
poetry lock --no-update

# Then retry install
poetry install
```

---

#### Issue 2: Dependency conflicts

**Symptom**: SolverProblemError during installation:
```
SolverProblemError
  Because package-a (1.0.0) depends on package-b (>=2.0.0)
  and package-c (1.0.0) depends on package-b (<2.0.0), ...
```

**Cause**: Incompatible dependency versions in dependency tree

**Fixes**:
1. **Check Python version** (most common cause):
   ```bash
   python3 --version
   # Must be ≥3.11.0
   ```
   If Python <3.11, upgrade Python first (see python_setup.md)

2. **Update Poetry itself**:
   ```bash
   poetry self update
   # Updates to latest Poetry version
   ```

3. **Clear Poetry cache** (rare):
   ```bash
   poetry cache clear pypi --all
   poetry install
   ```

---

#### Issue 3: sce not found after install

**Symptom**: `sce --help` returns "command not found" (exit code 127)

**Possible Causes & Fixes**:

**Cause A: PATH not updated** (shell needs restart)
```bash
# Try explicit invocation first
poetry run sce --help
# If this works, PATH is the issue

# Fix: Restart terminal
# Or add Poetry's bin to PATH manually
export PATH="$HOME/.local/bin:$PATH"  # Linux
export PATH="$HOME/Library/Application Support/pypoetry/venv/bin:$PATH"  # macOS
```

**Cause B: Installation failed silently**
```bash
# Re-run install with verbose output
poetry install -vvv
# Check output for errors
```

**Cause C: Wrong virtual environment active**
```bash
# Check which venv Poetry is using
poetry env info
# Should show path to project's .venv

# If wrong venv, remove and recreate
poetry env remove python
poetry install
```

---

#### Issue 4: Poetry not installed (wrong path chosen)

**Symptom**: `poetry --version` returns "command not found"

**Clarification**: This means Poetry is NOT available, so you should use **Path B (venv)** instead. Don't try to install Poetry mid-setup - it adds complexity and potential failure points. Use the built-in venv approach.

**User Message**: "Poetry isn't available on your system. No problem - we'll use Python's built-in venv instead, which works just as well."

---

## Path B: venv Installation

### venv Advantages

- **Built-in**: No extra tools required (included in Python 3.3+)
- **Universal**: Works anywhere Python is installed
- **Simple**: Standard Python tool with predictable behavior
- **Lightweight**: Minimal overhead, fast environment creation

### Installation Steps

```bash
# Step 1: Create virtual environment
python3 -m venv .venv
# Creates .venv/ directory with isolated Python environment
# Directory contains: bin/, lib/, include/, pyvenv.cfg
# Takes 5-10 seconds

# Step 2: Activate virtual environment
source .venv/bin/activate
# For bash/zsh on macOS/Linux (standard shells)
# Fish shell: source .venv/bin/activate.fish
# Csh/tcsh: source .venv/bin/activate.csh

# Step 3: Visual confirmation
# Your terminal prompt should now show (.venv) prefix
# Example BEFORE: "user@hostname:~/sports-coach-engine$"
# Example AFTER:  "(.venv) user@hostname:~/sports-coach-engine$"

# Step 4: Upgrade pip (important for some dependencies)
pip install --upgrade pip
# Ensures latest pip version for reliable installs
# Avoids: "Could not find a version that satisfies the requirement"

# Step 5: Install sports-coach-engine in editable mode
pip install -e .
# The -e flag means "editable" - installs from current directory
# Allows code changes to take effect without reinstall
# Reads setup.py or pyproject.toml for dependencies
# Takes 30-60 seconds typically

# Step 6: Verify sce command is available
sce --help
# Expected exit code: 0
```

### Virtual Environment Activation

**CRITICAL**: The `source .venv/bin/activate` step is **essential**. Without it:

- ❌ `sce` command will not be found (exit 127)
- ❌ `pip install` may fail with permission errors
- ❌ Packages install to system Python instead of isolated environment
- ❌ User will see "command not found: sce" error

**Teaching Moment for Non-Technical Users**:

"The (.venv) prefix in your prompt means the virtual environment is active. This keeps the coaching engine's dependencies separate from your system Python - like a sandbox. You'll need to activate it each time you open a new terminal:

```bash
cd ~/sports-coach-engine
source .venv/bin/activate
```

Think of it like starting a car - you need to 'turn on' the virtual environment before using sce."

**Visual Indicators**:

✓ **Activated**: Prompt shows `(.venv) user@hostname:~/sports-coach-engine$`
✗ **Not Activated**: Prompt shows `user@hostname:~/sports-coach-engine$` (no prefix)

**Check Programmatically**:
```bash
echo $VIRTUAL_ENV
# Activated: Shows /path/to/sports-coach-engine/.venv
# Not activated: Empty (no output)
```

### Common venv Issues

#### Issue 1: Permission errors during pip install

**Symptom**: "[Errno 13] Permission denied" when running `pip install -e .`

**Example Error**:
```
ERROR: Could not install packages due to an EnvironmentError: [Errno 13] Permission denied: '/usr/local/lib/python3.11/site-packages/...'
```

**Cause**: Virtual environment not activated (trying to install to system Python, which is protected)

**Fix**:
```bash
# Step 1: Check if venv is active
echo $VIRTUAL_ENV
# If empty → not activated

# Step 2: Check prompt for (.venv) prefix
# If missing → not activated

# Step 3: Activate venv
source .venv/bin/activate

# Step 4: Verify activation
echo $VIRTUAL_ENV
# Should now show: /path/to/sports-coach-engine/.venv

# Step 5: Retry install
pip install -e .
```

**NEVER use `sudo pip`**: This installs to system Python and bypasses venv entirely. If you see "Permission denied", the solution is always to activate venv, never to use sudo.

---

#### Issue 2: sce not found after install

**Symptom**: `sce --help` returns "command not found" (exit code 127)

**Possible Causes & Fixes**:

**Cause A: Virtual environment not activated**
```bash
# Check activation status
echo $VIRTUAL_ENV
# Empty → not activated

# Check prompt
# No (.venv) prefix → not activated

# Fix: Activate venv
source .venv/bin/activate

# Retry command
sce --help
```

**Cause B: Wrong venv activated**
```bash
# Check which venv is active
echo $VIRTUAL_ENV
# Should show: /path/to/sports-coach-engine/.venv

# If different path, deactivate and activate correct one
deactivate
cd /path/to/sports-coach-engine
source .venv/bin/activate
```

**Cause C: Install failed silently**
```bash
# Re-run install and watch for errors
pip install -e .

# Check for error messages like:
# - "Could not find a version that satisfies..."
# - "No matching distribution found..."
# - "Command errored out with exit status 1"

# If errors appear, see troubleshooting.md
```

**Cause D: sce not in PATH** (rare)
```bash
# Check if sce exists but isn't in PATH
ls -la .venv/bin/sce
# If exists → PATH issue

# Fix: Check PATH includes venv/bin
echo $PATH | grep .venv
# Should show .venv/bin in PATH

# If missing, reactivate venv
deactivate
source .venv/bin/activate
```

---

#### Issue 3: No module named venv

**Symptom**: `python3 -m venv .venv` fails with:
```
/usr/bin/python3: No module named venv
```

**Cause**: python3-venv package not installed (Linux only - common on Ubuntu/Debian)

**Fix**:
```bash
# Ubuntu/Debian
sudo apt install python3.11-venv

# CentOS/RHEL (venv included by default)
# Not applicable

# Verify fix
python3 -m venv --help
# Should show venv usage info

# Retry venv creation
python3 -m venv .venv
```

---

#### Issue 4: Forgetting to activate venv in new terminal

**Symptom**: `sce` works initially, then fails when opening new terminal

**Cause**: Each terminal session is independent - venv activation doesn't persist

**Temporary Fix** (for each session):
```bash
cd ~/sports-coach-engine
source .venv/bin/activate
```

**Permanent Fix** (activate automatically):

**Option A: Shell Startup Script** (bash/zsh)
```bash
# Add to ~/.bashrc or ~/.zshrc
if [ -d "$HOME/sports-coach-engine/.venv" ]; then
  source "$HOME/sports-coach-engine/.venv/bin/activate"
fi
```

**Option B: Shell Alias**
```bash
# Add to ~/.bashrc or ~/.zshrc
alias coach='cd ~/sports-coach-engine && source .venv/bin/activate'

# Usage: Type `coach` in any terminal to activate
```

**Option C: direnv** (advanced - auto-activate on cd)
```bash
# Install direnv (macOS)
brew install direnv

# Add to shell config
eval "$(direnv hook bash)"  # or zsh

# Create .envrc in project
echo 'source .venv/bin/activate' > .envrc
direnv allow

# Now activates automatically when cd into directory
```

---

## Mixed State Detection

**Problem**: Both Poetry environment and manual .venv exist, causing command ambiguity

**Symptoms**:
- `sce` works with `poetry run sce` but not standalone
- `which sce` shows Poetry path, but venv is active
- Conflicting dependency versions between environments

**Detection Script**:

```bash
has_poetry_env=false
has_manual_venv=false

# Check for Poetry environment
if poetry env info >/dev/null 2>&1; then
  has_poetry_env=true
  poetry_path=$(poetry env info --path 2>/dev/null)
  echo "Poetry environment detected: $poetry_path"
fi

# Check for manual venv
if [ -d .venv ]; then
  has_manual_venv=true
  echo "Manual .venv detected: $(pwd)/.venv"
fi

# Check for conflict
if $has_poetry_env && $has_manual_venv; then
  echo ""
  echo "⚠️  WARNING: Mixed state detected!"
  echo "Both Poetry environment and manual .venv exist."
  echo "This can cause command conflicts and dependency issues."
  echo ""
  echo "Recommendation: Choose one method and remove the other."
fi
```

**Fix - Choose One Method**:

**Option 1: Keep Poetry** (recommended if Poetry available)
```bash
# Remove manual venv
deactivate  # If currently activated
rm -rf .venv

# Use Poetry exclusively
poetry install
sce --help  # Or: poetry run sce --help
```

**Option 2: Keep Manual venv** (if Poetry not needed)
```bash
# Remove Poetry environment
poetry env remove python

# Activate manual venv
source .venv/bin/activate
sce --help
```

**Why This Matters**:
- Different venvs have different dependency installations
- Commands may use different Python interpreters
- Debugging becomes confusing (which environment has the issue?)
- Wastes disk space (duplicate dependencies)

---

## Validation and Verification

### After Installation (Both Paths)

Run these checks to confirm successful installation:

```bash
# Check 1: sce command works
sce --help
# MUST return exit code 0

# Check 2: sce is in PATH
which sce
# Poetry path: Shows poetry's venv path (e.g., ~/.cache/pypoetry/virtualenvs/.../bin/sce)
# venv path: Shows .venv/bin/sce
# Not found: Returns exit 1 (installation failed)

# Check 3: Python interpreter location
which python
# Should point to venv Python, NOT system Python
# Poetry: ~/.cache/pypoetry/virtualenvs/.../bin/python
# venv: /path/to/sports-coach-engine/.venv/bin/python
# System (BAD): /usr/bin/python or /usr/local/bin/python

# Check 4: Virtual environment active (venv path only)
echo $VIRTUAL_ENV
# venv path: Should show /path/to/sports-coach-engine/.venv
# Poetry path: Empty (Poetry manages activation differently)
# Not activated (venv path): Empty (PROBLEM - activate venv)
```

### Validation Checklist

Before proceeding to Phase 4 (Configuration), verify:

- [ ] `sce --help` returns exit code 0
- [ ] `which sce` shows path inside virtual environment (not system)
- [ ] `which python` shows venv Python (not system)
- [ ] If using venv path: `echo $VIRTUAL_ENV` shows .venv path
- [ ] If using venv path: Prompt shows `(.venv)` prefix

### If Validation Fails

**Exit code meanings**:
- **0**: Success - command worked
- **127**: Command not found - sce not installed or venv not activated
- **Other**: Unexpected error - see troubleshooting.md

**Next steps**:
1. Re-run installation commands
2. Check for error messages in output
3. See [Troubleshooting Command Not Found](#troubleshooting-command-not-found) below
4. If still failing, see `troubleshooting.md` for comprehensive debugging

---

## Troubleshooting Command Not Found

### Quick Diagnostic Script

Run this diagnostic to identify the issue:

```bash
echo "=== Environment Diagnostic ==="
echo ""

# Platform
echo "Platform: $(uname)"

# Python version
echo "Python: $(python3 --version 2>&1)"

# Installation method check
echo ""
echo "Installation Method:"
if command -v poetry >/dev/null 2>&1; then
  echo "  Poetry: Available ($(poetry --version))"
  poetry env info 2>&1 | head -5
else
  echo "  Poetry: Not available"
fi

if [ -d .venv ]; then
  echo "  Manual venv: Exists"
else
  echo "  Manual venv: Not found"
fi

# Virtual environment status
echo ""
echo "Virtual Environment:"
if [ -n "$VIRTUAL_ENV" ]; then
  echo "  Active: Yes ($VIRTUAL_ENV)"
else
  echo "  Active: No"
fi

# sce command check
echo ""
echo "sce Command:"
if command -v sce >/dev/null 2>&1; then
  echo "  Found: Yes ($(which sce))"
  echo "  Help: $(sce --help 2>&1 | head -n 1)"
else
  echo "  Found: No"

  # Check if sce exists in .venv
  if [ -f .venv/bin/sce ]; then
    echo "  Exists in .venv: Yes (but not in PATH)"
    echo "  → Fix: source .venv/bin/activate"
  else
    echo "  Exists in .venv: No"
    echo "  → Fix: pip install -e . (with venv activated)"
  fi
fi

# PATH check
echo ""
echo "PATH includes:"
echo "$PATH" | tr ':' '\n' | grep -E '(\.venv|poetry)' || echo "  (no venv paths found)"
```

### Common Failure Patterns

**Pattern 1**: sce exists in .venv but not found
- **Cause**: Virtual environment not activated
- **Fix**: `source .venv/bin/activate`

**Pattern 2**: sce works with `poetry run` but not standalone
- **Cause**: PATH not updated by Poetry
- **Fix**: Restart terminal or use `poetry run sce` consistently

**Pattern 3**: sce not found, .venv/bin/sce doesn't exist
- **Cause**: Installation failed
- **Fix**: Re-run `pip install -e .` (with venv activated)

**Pattern 4**: sce found but wrong version
- **Cause**: Multiple installations (system + venv)
- **Fix**: Check `which sce` → should point to venv, not system

### Links to Full Troubleshooting

For comprehensive debugging of installation issues:

- **Environment checks**: See `environment_checks.md`
- **Python installation issues**: See `python_setup.md`
- **Package installation errors**: See `troubleshooting.md#package-installation-issues`
- **Configuration problems**: See `troubleshooting.md#configuration-issues`

---

## Summary

This reference covers both Poetry and venv installation paths in depth. Key takeaways:

1. **Choose method based on Poetry availability** - don't install Poetry mid-setup
2. **Virtual environment activation is critical** for venv path
3. **Mixed states cause conflicts** - choose one method and stick with it
4. **Validation confirms success** - don't proceed until `sce --help` works
5. **Common issues are predictable** - most failures due to activation or PATH

For troubleshooting specific error messages, see `troubleshooting.md`.
