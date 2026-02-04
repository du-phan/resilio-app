# Troubleshooting Reference

Comprehensive troubleshooting guide for Sports Coach Engine environment setup issues.

## Contents
- [Quick Fixes](#quick-fixes) - Top 5 most common issues
- [Python Issues](#python-issues)
- [Package Installation Issues](#package-installation-issues)
- [Configuration Issues](#configuration-issues)
- [Platform-Specific Issues](#platform-specific-issues)
- [Virtual Environment Issues](#virtual-environment-issues)
- [Quick Diagnostic Checklist](#quick-diagnostic-checklist)
- [Getting Help](#getting-help)

---

## Quick Fixes

Top 5 most common issues and their solutions:

**1. sce not found after install** → Virtual environment not activated
- **Symptom**: `sce --help` returns "command not found" (exit 127)
- **Cause**: Using venv path but forgot to activate
- **Fix**: `source .venv/bin/activate`
- **Verify**: Prompt shows `(.venv)` prefix
- **Detail**: See [sce Command Not Found After Installation](#sce-command-not-found-after-installation)

**2. Permission denied during pip install** → Installing to system Python
- **Symptom**: `[Errno 13] Permission denied` when running `pip install`
- **Cause**: Virtual environment not activated (trying to modify system Python)
- **Fix**: Activate venv first, never use `sudo pip`
- **Commands**:
  ```bash
  source .venv/bin/activate  # Activate venv
  pip install -e .           # Retry install
  ```
- **Detail**: See [pip Permission Errors Without Virtual Environment](#pip-permission-errors-without-virtual-environment)

**3. python3 shows old version after install** → Shell cached old PATH
- **Symptom**: `python3 --version` still shows Python 3.10 after installing 3.11
- **Cause**: Shell hasn't refreshed PATH, or new Python not in PATH
- **Fix**: Restart terminal or run `hash -r`
- **Alternative**: Use explicit version command: `python3.11 --version`
- **Detail**: See [Multiple Python Installations Causing Conflicts](#multiple-python-installations-causing-conflicts)

**4. Mixed Poetry and venv** → Conflicting environments
- **Symptom**: `sce` works with `poetry run sce` but not standalone, or vice versa
- **Cause**: Both Poetry environment and manual .venv exist
- **Fix**: Choose one method, remove the other
- **Commands**:
  ```bash
  # Keep Poetry: rm -rf .venv
  # Keep venv: poetry env remove python
  ```
- **Detail**: See [Mixed Poetry and venv Usage](#mixed-poetry-and-venv-usage)

**5. Homebrew fails with developer tools error** (macOS) → Xcode CLT missing
- **Symptom**: `brew` commands fail with "invalid active developer path" or "command line tools" error
- **Cause**: macOS doesn't include compilation tools by default
- **Fix**: `xcode-select --install` (opens GUI installer, takes 5-10 minutes)
- **After install**: Retry Homebrew command
- **Detail**: See [macOS: Xcode Command Line Tools Missing](#macos-xcode-command-line-tools-missing)

---

## Python Issues

### Wrong Python Version Installed

**Symptom**: `python3 --version` shows version <3.11.0 (e.g., 3.9.6, 3.10.12)

**Impact**: Package installation may fail or CLI won't work

**Diagnosis**:
```bash
python3 --version
# Shows: Python 3.10.12 (example - too old)
```

**Fixes**:

**macOS**:
```bash
# Install Python 3.11 via Homebrew
brew install python@3.11

# Verify
python3 --version
# If still shows old version: PATH issue (see below)

# Check all Python installations
which -a python3
# First one in list is what 'python3' uses

# If Homebrew Python not first, update PATH
export PATH="/opt/homebrew/bin:$PATH"  # Apple Silicon
# OR
export PATH="/usr/local/bin:$PATH"     # Intel

# Make permanent
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Linux (Ubuntu/Debian)**:
```bash
# Install Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Option 1: Use explicit version command
python3.11 --version

# Option 2: Make python3 point to 3.11
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --config python3
# Choose Python 3.11 from menu
```

---

### Multiple Python Installations Causing Conflicts

**Symptom**: Different Python versions depending on how you invoke it

**Example**:
```bash
python3 --version
# Python 3.10.12

python3.11 --version
# Python 3.11.8

which python3
# /usr/bin/python3 (points to 3.10)
```

**Impact**: Confusion about which Python is being used, packages installed for wrong version

**Diagnosis**:
```bash
# See all python3 installations
which -a python3

# See what python3 symlink points to
ls -la $(which python3)

# Check Python search path
python3 -c "import sys; print(sys.executable)"
```

**Fixes**:

**Strategy 1: Use explicit version command** (safest, no system changes)
```bash
# Always use python3.11 instead of python3
python3.11 --version
python3.11 -m venv .venv
python3.11 -m pip install -e .

# Create alias for convenience (add to ~/.zshrc or ~/.bashrc)
alias python3='python3.11'
alias pip3='python3.11 -m pip'
```

**Strategy 2: Update default Python symlink** (Linux only, affects system)
```bash
# Update alternatives to prefer 3.11
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --config python3

# Verify
python3 --version  # Should now show 3.11.x
```

**Strategy 3: Update PATH** (macOS, affects current user)
```bash
# Put desired Python directory first in PATH
# Example: Prefer Homebrew Python over system Python

# Add to ~/.zshrc (macOS 10.15+) or ~/.bashrc (Linux/older macOS)
export PATH="/opt/homebrew/bin:$PATH"  # Apple Silicon Mac
# OR
export PATH="/usr/local/bin:$PATH"     # Intel Mac

# Reload shell config
source ~/.zshrc  # or ~/.bashrc

# Verify
which python3  # Should show Homebrew path now
python3 --version  # Should show desired version
```

---

### python vs python3 Command Confusion

**Symptom**: `python --version` shows Python 2.7 (ancient)

**Explanation**:
- On many systems, `python` points to legacy Python 2.7
- Python 3.x is accessed via `python3` command
- Python 2.7 reached end-of-life in 2020

**Solution**: **Always use `python3` command**
```bash
# CORRECT
python3 --version
python3 -m venv .venv
python3 -m pip install -e .

# WRONG (uses Python 2.7)
python --version  # Shows 2.7.x
```

**Exception**: Inside a virtual environment, `python` points to Python 3.x
```bash
source .venv/bin/activate
python --version  # Shows 3.11.x (venv's Python)
```

---

### Python Installed But Not in PATH

**Symptom**:
- Just installed Python 3.11
- `python3 --version` still shows old version OR "command not found"
- But Python 3.11 files exist on disk

**Diagnosis**:
```bash
# Find where Python 3.11 is installed
# macOS
find /usr/local /opt/homebrew -name python3.11 2>/dev/null

# Linux
find /usr -name python3.11 2>/dev/null

# Check current PATH
echo $PATH
# See if Python installation directory is in the list
```

**Fixes**:

**macOS (Homebrew)**:
```bash
# Add Homebrew to PATH
export PATH="/opt/homebrew/bin:$PATH"  # Apple Silicon
# OR
export PATH="/usr/local/bin:$PATH"     # Intel

# Make permanent (add to shell config)
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Restart terminal (closes all windows, reopens)
# This ensures shell fully reloads configuration
```

**Linux**:
```bash
# Check if Python 3.11 binary exists
ls -la /usr/bin/python3.11

# If exists: Create or update symlink
sudo ln -sf /usr/bin/python3.11 /usr/local/bin/python3

# Or use update-alternatives (Ubuntu/Debian)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Verify
python3 --version
```

**Universal fallback**: Use absolute path
```bash
# Find Python location
which python3.11
# Example output: /opt/homebrew/bin/python3.11

# Use absolute path for setup
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Package Installation Issues

### Poetry Not Found

**Symptom**: `poetry --version` returns "command not found"

**Context**: Poetry is optional but recommended for Sports Coach Engine

**Decision Tree**:
1. **Do you want Poetry?**
   - **Yes** → Install Poetry (see below)
   - **No** → Use venv approach instead (no Poetry needed)

**Install Poetry**:
```bash
# Official installer
curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH (follow instructions shown after install)
# Typical paths:
export PATH="$HOME/.local/bin:$PATH"  # Linux
export PATH="$HOME/.poetry/bin:$PATH"  # macOS (older Poetry)

# Make permanent (add to ~/.zshrc or ~/.bashrc)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify
poetry --version
# Should show: Poetry (version X.X.X)
```

**Skip Poetry (use venv instead)**:
```bash
# No Poetry needed - Python's built-in venv works fine
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
sce --help  # Should work
```

---

### pip Permission Errors Without Virtual Environment

**Symptom**: `pip install -e .` fails with "[Errno 13] Permission denied"

**Example Error**:
```
ERROR: Could not install packages due to an OSError: [Errno 13] Permission denied: '/usr/local/lib/python3.11/site-packages/...'
```

**Cause**: Trying to install to system Python directory (protected)

**CORRECT Fix**: Use virtual environment (always recommended)
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Now install works without sudo
pip install -e .
sce --help  # Works
```

**WRONG Fix**: Using sudo with pip
```bash
# NEVER DO THIS (installs to system Python, breaks venv)
sudo pip install -e .

# Why this is bad:
# - Installs to system Python (affects all users)
# - Can break system tools that depend on Python
# - sce command won't be in your PATH
# - Security risk (installing packages as root)
```

**If you already used sudo**: Clean up and retry
```bash
# Remove bad system install
sudo pip uninstall sports-coach-engine

# Create fresh venv
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate

# Install correctly
pip install -e .
```

---

### "sce" Command Not Found After Installation

**Symptom**:
- `poetry install` or `pip install -e .` succeeded
- `sce --help` returns "command not found" (exit 127)

**Diagnosis Steps**:

```bash
# Step 1: Check if package is installed
python3 -m pip list | grep sports-coach-engine
# If found: Package installed, PATH issue
# If not found: Install failed (check error messages above)

# Step 2: Check if venv is active (if using venv path)
echo $VIRTUAL_ENV
# Expected: /path/to/sports-coach-engine/.venv
# If empty: venv not activated

# Step 3: Find where sce is installed
find . -name sce -type f 2>/dev/null
# Common locations:
#   .venv/bin/sce (venv path)
#   ~/.cache/pypoetry/virtualenvs/.../bin/sce (Poetry path)

# Step 4: Check if sce directory is in PATH
echo $PATH | grep -o '[^:]*bin[^:]*'
# Should include venv/bin or Poetry venv bin
```

**Fixes by Cause**:

**Cause 1: Virtual environment not activated**
```bash
# Symptom: $VIRTUAL_ENV is empty
# Fix: Activate venv
source .venv/bin/activate

# Verify
echo $VIRTUAL_ENV  # Should show path
sce --help  # Should work now
```

**Cause 2: Wrong virtual environment activated**
```bash
# Symptom: $VIRTUAL_ENV points to different project
# Fix: Deactivate and activate correct one
deactivate
cd /path/to/sports-coach-engine
source .venv/bin/activate
```

**Cause 3: Package installed but PATH issue**
```bash
# Find sce location
find . -name sce -type f
# Example: ./.venv/bin/sce

# Test with absolute path
./.venv/bin/sce --help
# If works: PATH issue

# Fix: Ensure venv is activated
source .venv/bin/activate
# Activation adds .venv/bin to PATH
```

**Cause 4: Poetry path not in shell PATH**
```bash
# If using Poetry, try explicit invocation
poetry run sce --help
# If this works: Poetry venv exists, shell PATH issue

# Fix: Use poetry run prefix, or add Poetry venv to PATH
# (Advanced - usually not needed)
```

**Cause 5: Installation failed silently**
```bash
# Reinstall with verbose output
pip install --verbose -e .

# Or with Poetry
poetry install --verbose

# Check for error messages during install
```

---

### Dependency Conflicts During Installation

**Symptom**: Installation fails with "SolverProblemError" (Poetry) or "Conflict" (pip)

**Example Error (Poetry)**:
```
SolverProblemError

Because mypy (1.9.0) depends on typing-extensions (>=4.1.0)
and package requires typing-extensions (3.9.0), mypy is forbidden.
```

**Example Error (pip)**:
```
ERROR: Cannot install -r requirements.txt because these package versions have incompatible dependencies.
```

**Diagnosis**:
```bash
# Check Python version (must be ≥3.11)
python3 --version

# Check Poetry version (should be recent)
poetry --version

# Check pip version (should be recent)
pip --version
```

**Fixes**:

**Poetry**:
```bash
# Update Poetry itself
poetry self update

# Clear Poetry cache
poetry cache clear . --all

# Regenerate lock file
poetry lock --no-update

# Retry install
poetry install
```

**pip**:
```bash
# Upgrade pip first
pip install --upgrade pip

# Upgrade setuptools and wheel
pip install --upgrade setuptools wheel

# Force reinstall all dependencies
pip install --force-reinstall -e .
```

**If still fails**: Check pyproject.toml for version constraints
```bash
# Temporarily relax version constraints
# Edit pyproject.toml, change:
#   mypy = "^1.9.0"
# To:
#   mypy = ">=1.9.0"

# Retry install
poetry install  # or pip install -e .
```

---

## Configuration Issues

### Config Directory Not Created

**Symptom**: Running `sce` commands fails with "FileNotFoundError: config/"

**Diagnosis**:
```bash
# Check if config exists
ls -la config/
# Exit 2 (not found) = Need to create

# Check if sce init command works
sce init
# If fails: Package not installed correctly
```

**Fix**:
```bash
# Initialize configuration
sce init

# Verify
ls -la config/
# Should show:
#   secrets.local.yaml
#   settings.yaml
```

**If `sce init` fails**:
```bash
# Check package installed
sce --help
# If "command not found": See "sce Command Not Found" section above

# Check permissions
pwd  # Should be in sports-coach-engine directory
ls -la .  # Should have write permission

# Retry with verbose output
sce --help  # See if any error messages
```

---

### secrets.local.yaml File Malformed

**Symptom**: `sce auth` or other commands fail with YAML parsing error

**Example Error**:
```
yaml.scanner.ScannerError: while scanning for the next token
found character '\t' that cannot start any token
```

**Cause**: Invalid YAML syntax (common: tabs instead of spaces, wrong indentation)

**Diagnosis**:
```bash
# View file contents
cat config/secrets.local.yaml

# Check for tabs (YAML requires spaces)
cat -A config/secrets.local.yaml | grep '\^I'
# If shows ^I: File has tabs (invalid)
```

**Fix**:
```bash
# Backup current file
cp config/secrets.local.yaml config/secrets.local.yaml.backup

# Recreate with correct format
cat > config/secrets.local.yaml << 'EOF'
strava:
  client_id: YOUR_CLIENT_ID_HERE
  client_secret: YOUR_CLIENT_SECRET_HERE
  access_token: null
  refresh_token: null
EOF

# Important: Use 2 spaces for indentation, not tabs
# Verify
cat config/secrets.local.yaml
```

**Common YAML Mistakes**:
1. **Tabs instead of spaces**: YAML requires spaces, not tabs
2. **Wrong indentation**: Must be consistent (2 spaces per level)
3. **Missing colon**: Each key must have colon (e.g., `client_id:`)
4. **Quotes around special characters**: If value has `:` or `#`, use quotes

**Validate YAML**:
```bash
# Check if Python can parse it
python3 -c "import yaml; yaml.safe_load(open('config/secrets.local.yaml'))" && echo "Valid" || echo "Invalid"
```

---

### File Permission Issues on Unix

**Symptom**: "Permission denied" when reading/writing config files

**Diagnosis**:
```bash
# Check file permissions
ls -la config/
# Example output:
#   -rw------- 1 user user 123 Jan 20 secrets.local.yaml (owner-only read/write)
#   -rw-r--r-- 1 user user 456 Jan 20 settings.yaml (owner read/write, others read)

# Check directory permissions
ls -la . | grep config
# Example:
#   drwxr-xr-x 2 user user 4096 Jan 20 config (owner full, others read/execute)

# Check ownership
stat config/secrets.local.yaml
# Should show your user/group
```

**Fix: Make files readable/writable by owner**:
```bash
# Fix file permissions
chmod 644 config/*.yaml  # Owner read/write, others read
# Or for secrets only:
chmod 600 config/secrets.local.yaml  # Owner-only read/write (more secure)

# Fix directory permissions
chmod 755 config/  # Owner full, others read/execute

# Verify
ls -la config/
```

**Fix: Change ownership** (if files owned by wrong user):
```bash
# Check current ownership
ls -la config/secrets.local.yaml

# Change to your user
sudo chown $USER:$USER config/*.yaml

# Verify
ls -la config/
```

---

## Platform-Specific Issues

### macOS: Xcode Command Line Tools Missing

**Symptom**:
- Homebrew install fails with "developer tools" error
- Python package compilation fails

**Error Message**:
```
xcrun: error: invalid active developer path (/Library/Developer/CommandLineTools), missing xcrun at: /Library/Developer/CommandLineTools/usr/bin/xcrun
```

**Diagnosis**:
```bash
# Check if Command Line Tools installed
xcode-select -p
# If returns path: Installed
# If error: Not installed or broken
```

**Fix**:
```bash
# Install Command Line Tools
xcode-select --install

# GUI window opens - click "Install"
# Wait 5-10 minutes for download/install

# Verify
xcode-select -p
# Should return: /Library/Developer/CommandLineTools

# Retry Homebrew/Python install
brew install python@3.11
```

**If install fails with "already installed"**:
```bash
# Remove broken install
sudo rm -rf /Library/Developer/CommandLineTools

# Retry
xcode-select --install
```

---

### macOS: Homebrew Path Issues (Apple Silicon vs Intel)

**Symptom**: Homebrew installed but `brew` command not found

**Cause**: Different Homebrew locations for Apple Silicon vs Intel Macs

**Apple Silicon (M1/M2/M3)**:
- Homebrew location: `/opt/homebrew/`
- Binary path: `/opt/homebrew/bin/brew`

**Intel Mac**:
- Homebrew location: `/usr/local/homebrew/`
- Binary path: `/usr/local/bin/brew`

**Diagnosis**:
```bash
# Check CPU architecture
uname -m
# arm64 = Apple Silicon
# x86_64 = Intel

# Check if Homebrew installed
ls -la /opt/homebrew/bin/brew  # Apple Silicon
ls -la /usr/local/bin/brew     # Intel

# Check PATH
echo $PATH | grep homebrew
# Should include Homebrew bin directory
```

**Fix**:
```bash
# Add Homebrew to PATH (one-time for current session)
# Apple Silicon:
export PATH="/opt/homebrew/bin:$PATH"

# Intel:
export PATH="/usr/local/bin:$PATH"

# Make permanent (add to shell config)
# macOS 10.15+ uses zsh by default
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile  # Apple Silicon
# OR
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile     # Intel

# Reload shell config
source ~/.zprofile

# Verify
brew --version
```

---

### Linux: python3-venv Package Missing

**Symptom**: `python3 -m venv .venv` fails with "No module named venv"

**Error Message**:
```
Error: Command '['/path/to/.venv/bin/python3', '-Im', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.
```

**Cause**: On many Linux distributions, venv module is separate package

**Diagnosis**:
```bash
# Check if venv module available
python3 -m venv --help
# If fails: Module not installed

# Check Python version
python3 --version
# Example: Python 3.11.4
```

**Fix (Ubuntu/Debian)**:
```bash
# Install venv module for Python 3.11
sudo apt install python3.11-venv

# Verify
python3.11 -m venv --help
# Should show help text

# Retry venv creation
python3.11 -m venv .venv
source .venv/bin/activate
```

**Fix (CentOS/RHEL)**:
```bash
# venv usually included, but if missing:
sudo yum install python311

# Verify
python3.11 -m venv --help
```

---

### Linux: Build Tools Missing

**Symptom**: Package installation fails with compiler errors

**Example Error**:
```
error: command 'gcc' failed with exit status 1
unable to execute 'gcc': No such file or directory
```

**Cause**: Some Python packages compile C extensions, need gcc/make

**Diagnosis**:
```bash
# Check if gcc installed
which gcc
# If not found: Need to install

# Check if make installed
which make
# If not found: Need to install
```

**Fix (Ubuntu/Debian)**:
```bash
# Install build essentials
sudo apt install build-essential

# Install Python dev headers (needed for compiling Python extensions)
sudo apt install python3.11-dev

# Additional libraries (often needed)
sudo apt install libssl-dev libffi-dev

# Verify
gcc --version
make --version

# Retry package install
pip install -e .
```

**Fix (CentOS/RHEL)**:
```bash
# Install development tools group
sudo yum groupinstall "Development Tools"

# Install Python dev package
sudo yum install python311-devel

# Additional libraries
sudo yum install openssl-devel libffi-devel

# Verify
gcc --version

# Retry package install
pip install -e .
```

---

## Virtual Environment Issues

### Forgetting to Activate venv in New Terminal

**Symptom**:
- `sce` works in one terminal
- Opens new terminal → `sce` not found

**Cause**: Virtual environment activation is per-terminal-session

**Understanding**:
- Each terminal session needs venv activation
- Activation adds `.venv/bin/` to PATH (temporary)
- Closing terminal loses activation

**Solution Options**:

**Option 1: Activate manually each time** (recommended for learning)
```bash
# Navigate to project directory
cd ~/sports-coach-engine

# Activate venv
source .venv/bin/activate

# Now sce works
sce --help
```

**Option 2: Create shell alias** (convenience)
```bash
# Add to ~/.zshrc (macOS) or ~/.bashrc (Linux)
alias sce-activate='cd ~/sports-coach-engine && source .venv/bin/activate'

# Reload shell config
source ~/.zshrc  # or ~/.bashrc

# Now can activate quickly
sce-activate
```

**Option 3: Auto-activate when entering directory** (advanced)
```bash
# Add to ~/.zshrc or ~/.bashrc
function cd() {
  builtin cd "$@"
  if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
  fi
}

# Now venv activates automatically when cd into project
cd ~/sports-coach-engine  # Auto-activates venv
```

**Visual Indicator**: Activated venv shows in prompt
```bash
# Not activated:
user@hostname:~/sports-coach-engine$

# Activated:
(.venv) user@hostname:~/sports-coach-engine$
```

---

### Wrong Virtual Environment Activated

**Symptom**:
- Have multiple Python projects with venvs
- `sce` not found even though venv activated

**Diagnosis**:
```bash
# Check which venv is active
echo $VIRTUAL_ENV
# Example: /home/user/other-project/.venv (WRONG)
# Want: /home/user/sports-coach-engine/.venv

# Check current directory
pwd
# May be in wrong project directory
```

**Fix**:
```bash
# Deactivate current venv
deactivate

# Navigate to correct project
cd ~/sports-coach-engine

# Activate correct venv
source .venv/bin/activate

# Verify
echo $VIRTUAL_ENV
# Should show: /home/user/sports-coach-engine/.venv

# Test sce
sce --help  # Should work now
```

---

### Mixed Poetry and venv Usage

**Symptom**:
- Tried both Poetry and venv methods
- Confusing state (which is being used?)

**Problem**: Poetry and venv create separate virtual environments

**Diagnosis**:
```bash
# Check for Poetry venv
poetry env info
# Shows Poetry's venv location

# Check for manual venv
ls -la .venv/
# Shows manual venv if exists

# Check which is active
echo $VIRTUAL_ENV
# Shows currently active venv (if any)

# Check which sce is being used
which sce
# Shows path to sce binary
```

**Solution: Choose one method and stick with it**

**Option A: Use Poetry exclusively**
```bash
# Remove manual venv
deactivate  # If activated
rm -rf .venv

# Use Poetry for everything
poetry install
poetry run sce --help

# Or use Poetry shell (activates venv)
poetry shell
sce --help
```

**Option B: Use venv exclusively**
```bash
# Don't use poetry commands
# Use venv approach
source .venv/bin/activate
pip install -e .
sce --help
```

**Key Point**: Don't mix `poetry install` and `pip install -e .` in same project

---

## Quick Diagnostic Checklist

When troubleshooting, run through this checklist:

```bash
echo "=== Platform ==="
uname  # Darwin (macOS) or Linux?

echo "=== Python ==="
python3 --version  # ≥3.11.0?
which python3  # Correct location?

echo "=== Virtual Environment ==="
echo $VIRTUAL_ENV  # Active? Correct path?
ls -la .venv/  # Exists?

echo "=== Package ==="
sce --help  # Works? (exit 0)
which sce  # Where is it?

echo "=== Config ==="
ls -la config/  # Exists?
grep -q "YOUR_CLIENT_ID" config/secrets.local.yaml && echo "Placeholders present" || echo "Credentials set"

echo "=== PATH ==="
echo $PATH | tr ':' '\n' | grep -E '(homebrew|\.venv)'  # Includes required paths?
```

**All checks pass** → Environment ready
**Any fail** → Find corresponding section above for fix

---

## Getting Help

If you've tried troubleshooting steps and still stuck:

1. **Run diagnostic script** (from environment_checks.md)
2. **Collect error messages** (full text, not paraphrased)
3. **Note your platform** (macOS version / Linux distribution)
4. **Note Python version** (`python3 --version`)
5. **Note install method** (Poetry vs venv)
6. **Ask Codex**: Provide diagnostic output and error messages

**Example question format**:
```
I'm trying to set up Sports Coach Engine on Ubuntu 22.04.

Environment:
- Platform: Linux
- Python: 3.11.4
- Method: venv

Error:
[paste full error message]

What I've tried:
- Created venv: python3.11 -m venv .venv
- Activated: source .venv/bin/activate
- Tried install: pip install -e .

Error occurs during pip install step.
```
