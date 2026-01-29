# Environment Checks Reference

This reference provides comprehensive validation commands and troubleshooting steps for verifying the Sports Coach Engine environment.

## Contents
- [Check Commands](#check-commands)
- [Validation Workflows](#validation-workflows)
- [Common Errors & Fixes](#common-errors--fixes)
- [PATH Troubleshooting](#path-troubleshooting)
- [Summary Checklist](#summary-checklist)

---

## Check Commands

### Platform Detection

```bash
# Identify operating system
uname
# Returns:
#   "Darwin" = macOS
#   "Linux" = Linux
#   Other = Unsupported platform

# More detailed platform info (optional)
uname -a
# Shows: kernel version, architecture (x86_64, arm64)

# macOS-specific: Check if Apple Silicon or Intel
uname -m
# arm64 = Apple Silicon (M1/M2/M3)
# x86_64 = Intel Mac
```

**Why This Matters**:
- Install commands differ between macOS and Linux
- Python locations differ (Homebrew paths vary by architecture)
- Package managers differ (brew vs apt vs yum)

---

### Python Version Check

```bash
# Check Python 3 version
python3 --version
# Expected: "Python 3.11.x" or "Python 3.12.x"
# Exit codes:
#   0 = Python found
#   127 = Command not found
#   Other = Unusual error

# Check Python location
which python3
# macOS (Homebrew, Apple Silicon): /opt/homebrew/bin/python3
# macOS (Homebrew, Intel): /usr/local/bin/python3
# macOS (system): /usr/bin/python3
# Linux: /usr/bin/python3 or /usr/local/bin/python3

# Check all Python installations
which -a python3
# Shows all python3 commands in PATH (if multiple versions installed)

# Verify pip availability
python3 -m pip --version
# Expected: "pip X.X.X from ... (python 3.11)"
# If missing: python3-pip package not installed
```

**Version Requirements**:
- **Minimum**: Python 3.11.0
- **Recommended**: Python 3.11.x (latest patch)
- **Supported**: Python 3.12.x
- **NOT supported**: Python 3.10.x or earlier

**Common Version Check Issues**:
1. **Multiple Python versions**:
   - `python3 --version` shows old version
   - Fix: Check `which python3` - may need to update PATH or use explicit version (`python3.11`)

2. **python vs python3**:
   - `python --version` may show Python 2.7 (legacy)
   - Always use `python3` command explicitly

3. **Version installed but not in PATH**:
   - `python3 --version` returns 127 (not found)
   - But Python 3.11 is installed
   - Fix: Add to PATH or create symlink (see python_setup.md)

---

### Package Manager Detection

```bash
# Check if Poetry is available
poetry --version
# Expected: "Poetry (version X.X.X)"
# Exit code:
#   0 = Poetry installed
#   127 = Not found (use venv path instead)

# Check if Homebrew is available (macOS)
which brew
# Exit code:
#   0 = Homebrew installed
#   127 = Not found (need to install for Python)

# Check if APT is available (Linux - Ubuntu/Debian)
which apt
# Exit code: 0 = available, 127 = not found

# Check if YUM is available (Linux - CentOS/RHEL)
which yum
# Exit code: 0 = available, 127 = not found

# Check if DNF is available (Linux - Fedora, newer RHEL)
which dnf
# Exit code: 0 = available, 127 = not found
```

**Why Package Manager Detection Matters**:
- Determines installation method (Poetry vs venv)
- Determines Python install command (brew vs apt vs yum)
- Helps provide platform-specific guidance

---

### Virtual Environment Check

```bash
# Check if virtual environment is active (venv path only)
echo $VIRTUAL_ENV
# Expected (if activated): /path/to/sports-coach-engine/.venv
# Empty (if not activated): (no output)

# Visual indicator in prompt
# When active: (.venv) user@hostname:~/sports-coach-engine$
# When not active: user@hostname:~/sports-coach-engine$

# Check if .venv directory exists
ls -la .venv/
# Exit code:
#   0 = .venv exists (created via python3 -m venv .venv)
#   2 = Not found (need to create)

# Check if venv has sce command installed
ls -la .venv/bin/sce
# Exit code:
#   0 = sce installed in venv
#   2 = Not installed (need to run pip install -e .)
```

**Critical Understanding**:
- Poetry manages virtual environments automatically (hidden from user)
- venv requires explicit activation: `source .venv/bin/activate`
- Each new terminal session requires re-activation (venv only)

---

### Package Installation Check

```bash
# Primary check: Can sce command run?
sce --version
# Expected: "sports-coach-engine, version X.X.X"
# Exit codes:
#   0 = Installed and working
#   2 = Installed but config missing (proceed to sce init)
#   127 = Command not found (not installed or venv not activated)

# If sce not found, check installation location
which sce
# Poetry: /path/to/poetry/virtualenvs/.../bin/sce
# venv: /path/to/sports-coach-engine/.venv/bin/sce
# Not found: (no output, exit 1)

# Alternative: Try running via Poetry explicitly (if using Poetry)
poetry run sce --version
# This works even if sce not in PATH

# Check if package is installed in Python environment
python3 -m pip list | grep sports-coach-engine
# Expected: "sports-coach-engine    X.X.X    /path/to/project"
# If found: Package installed (sce PATH issue)
# If not found: Package not installed (need to run install command)
```

**Exit Code Interpretation**:
- **0 (success)**: Package working correctly, proceed to config check
- **2 (config missing)**: Package installed but `sce init` not run yet
- **127 (not found)**: Either:
  - Package not installed yet (need Poetry install or pip install -e .)
  - venv not activated (need source .venv/bin/activate)
  - PATH issue (package installed but shell can't find it)

---

### Configuration Check

```bash
# Check if config directory exists
ls -la config/
# Expected files:
#   secrets.local.yaml
#   athlete_profile.yaml
#   training_plan.yaml
# Exit code:
#   0 = Config directory exists
#   2 = Not found (need to run sce init)

# Check if secrets file has placeholder or real credentials
cat config/secrets.local.yaml | grep -v "YOUR_"
# If output is minimal: Still has placeholders (need first-session)
# If output has values: Real credentials already configured

# Check if secrets file is readable
test -r config/secrets.local.yaml && echo "Readable" || echo "Not readable"
# "Readable" = Good
# "Not readable" = Permission issue (need chmod 644)

# Check if athlete profile exists
test -f config/athlete_profile.yaml && echo "Exists" || echo "Not found"
# "Exists" = Profile may be configured
# "Not found" = Need to create profile (first-session)
```

**Common Config Issues**:
1. **Directory exists but files missing**:
   - `sce init` was interrupted
   - Fix: Run `sce init` again (safe to re-run)

2. **Permission denied when reading files**:
   - File permissions too restrictive
   - Fix: `chmod 644 config/*.yaml`

3. **Secrets file has real credentials**:
   - DO NOT overwrite (preserve existing auth)
   - Skip config initialization, proceed to first-session

---

## Validation Workflows

### Complete Environment Validation Sequence

Run these checks in order to diagnose environment state:

```bash
# 1. Platform check
echo "Platform: $(uname)"

# 2. Python version check
python3 --version && echo "✓ Python OK" || echo "✗ Python issue"

# 3. Python location
echo "Python location: $(which python3)"

# 4. Package installation check
sce --version && echo "✓ Package OK" || echo "✗ Package issue (exit code: $?)"

# 5. Config check
ls config/ >/dev/null 2>&1 && echo "✓ Config exists" || echo "✗ Config missing"

# 6. Virtual environment check (if using venv)
[ -n "$VIRTUAL_ENV" ] && echo "✓ venv active: $VIRTUAL_ENV" || echo "○ venv not active (OK if using Poetry)"

# Complete summary
echo "---"
echo "Environment Status:"
python3 --version
sce --version
ls -la config/ 2>/dev/null | head -n 5
```

### Quick Diagnostic Script

Save this as `/tmp/check_env.sh` for quick validation:

```bash
#!/bin/bash
echo "=== Sports Coach Engine Environment Check ==="
echo ""

# Platform
echo "Platform: $(uname)"
echo ""

# Python
echo -n "Python: "
if python3 --version 2>/dev/null; then
    PY_VERSION=$(python3 --version | awk '{print $2}')
    PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
    PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        echo "✓ Version OK ($PY_VERSION >= 3.11)"
    else
        echo "✗ Version too old ($PY_VERSION < 3.11)"
    fi
else
    echo "✗ Not found"
fi
echo "Location: $(which python3)"
echo ""

# Package
echo -n "Package: "
if sce --version 2>/dev/null; then
    echo "✓ Installed and working"
elif [ $? -eq 2 ]; then
    echo "○ Installed but config missing (run: sce init)"
else
    echo "✗ Not found (not installed or venv not activated)"
fi
echo ""

# Config
echo -n "Config: "
if [ -d config/ ]; then
    echo "✓ Directory exists"
    ls config/*.yaml 2>/dev/null | while read f; do echo "  - $(basename $f)"; done
else
    echo "✗ Not found (run: sce init)"
fi
echo ""

# Virtual environment (if applicable)
if [ -n "$VIRTUAL_ENV" ]; then
    echo "venv: ✓ Active ($VIRTUAL_ENV)"
else
    echo "venv: ○ Not active (OK if using Poetry)"
fi
echo ""

echo "=== Summary ==="
if python3 --version 2>/dev/null && [ $(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null) \> "3.10" ] && sce --version 2>/dev/null; then
    echo "✓ Environment ready for first-session"
else
    echo "✗ Environment needs setup (use complete-setup skill)"
fi
```

**Usage**:
```bash
bash /tmp/check_env.sh
```

---

## Common Errors & Fixes

### Error: "command not found: python3"

**Symptom**: Running `python3 --version` returns exit code 127

**Causes**:
1. Python not installed
2. Python installed but not in PATH

**Fixes**:
1. **Install Python** (see python_setup.md for platform-specific instructions)
2. **Check PATH**:
   ```bash
   # Find where Python is installed
   find /usr -name python3 2>/dev/null
   find /opt -name python3 2>/dev/null

   # Add to PATH (example for Homebrew on Apple Silicon)
   export PATH="/opt/homebrew/bin:$PATH"

   # Make permanent by adding to shell config
   echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
   source ~/.zshrc
   ```

---

### Error: "command not found: sce"

**Symptom**: Running `sce --version` returns exit code 127

**Causes** (in order of likelihood):
1. Package not installed yet
2. Virtual environment not activated (if using venv)
3. Package installed but PATH issue

**Diagnostic Steps**:
```bash
# Check if package is installed
python3 -m pip list | grep sports-coach-engine

# If found: Package installed, PATH issue
# If not found: Package not installed

# Check if venv is active
echo $VIRTUAL_ENV

# If empty and using venv: Need to activate
# If shows path: venv active, check if sce in venv/bin/
```

**Fixes**:
1. **Package not installed**:
   ```bash
   # Poetry path
   poetry install

   # venv path
   source .venv/bin/activate
   pip install -e .
   ```

2. **venv not activated**:
   ```bash
   source .venv/bin/activate
   sce --version  # Should work now
   ```

3. **PATH issue**:
   ```bash
   # Find where sce is installed
   find . -name sce -type f 2>/dev/null

   # If found in .venv/bin/sce: Activate venv
   # If found elsewhere: Add to PATH or use full path
   ```

4. **Try Poetry explicit invocation** (if using Poetry):
   ```bash
   poetry run sce --version
   # If this works: PATH issue, not installation issue
   ```

---

### Error: "[Errno 13] Permission denied"

**Symptom**: Running `pip install` fails with permission error

**Causes**:
1. Trying to install to system Python without sudo (correct - don't use sudo)
2. Virtual environment not activated

**Fixes**:
1. **Activate virtual environment first**:
   ```bash
   source .venv/bin/activate
   pip install -e .  # Now works without sudo
   ```

2. **If using Poetry**: Poetry manages permissions automatically
   ```bash
   poetry install  # Never needs sudo
   ```

3. **NEVER use sudo with pip in venv context**:
   ```bash
   # WRONG (installs to system Python, not venv)
   sudo pip install -e .

   # RIGHT (installs to venv)
   source .venv/bin/activate
   pip install -e .
   ```

---

### Error: "FileNotFoundError: config/"

**Symptom**: Running `sce` commands fails with missing config directory

**Cause**: Configuration not initialized yet

**Fix**:
```bash
# Create config structure
sce init

# Verify
ls -la config/
# Should show: secrets.local.yaml, athlete_profile.yaml, training_plan.yaml
```

---

### Error: "No module named venv"

**Symptom**: Running `python3 -m venv .venv` fails

**Cause**: python3-venv package not installed (Linux only)

**Fix (Ubuntu/Debian)**:
```bash
sudo apt install python3.11-venv

# Then retry
python3 -m venv .venv
```

**Fix (other Linux)**:
```bash
# CentOS/RHEL
sudo yum install python311

# Fedora
sudo dnf install python3.11
```

---

## PATH Troubleshooting

### Understanding PATH

The PATH environment variable tells your shell where to look for commands.

```bash
# View current PATH
echo $PATH
# Example: /usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin

# Commands are searched left-to-right
# First match wins
```

### Common PATH Issues

**Issue 1: Homebrew Python not in PATH (macOS)**
```bash
# Symptom: python3 --version shows old system Python
# Fix: Add Homebrew to PATH

# Apple Silicon
export PATH="/opt/homebrew/bin:$PATH"

# Intel Mac
export PATH="/usr/local/bin:$PATH"

# Make permanent
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Issue 2: Multiple Python versions, wrong one is default**
```bash
# Check all Python installations
which -a python3

# Use specific version explicitly
python3.11 --version

# Or update symlink (Linux)
sudo update-alternatives --config python3
```

**Issue 3: venv not in PATH after activation**
```bash
# Symptom: Activated venv but sce still not found
# Diagnostic: Check if activation worked
echo $VIRTUAL_ENV  # Should show path
echo $PATH | grep .venv  # Should show .venv/bin

# Fix: Deactivate and reactivate
deactivate
source .venv/bin/activate
```

---

## Summary Checklist

Use this quick checklist for environment validation:

- [ ] Platform identified (`uname` returns Darwin or Linux)
- [ ] Python 3.11+ installed (`python3 --version` shows ≥3.11.0)
- [ ] Python in PATH (`which python3` shows location)
- [ ] pip available (`python3 -m pip --version` works)
- [ ] Package manager available (Poetry or venv capability)
- [ ] sce command works (`sce --version` returns exit 0)
- [ ] Config directory exists (`ls config/` returns exit 0)
- [ ] Virtual environment active if using venv (`echo $VIRTUAL_ENV` shows path)

**All checks pass** → Ready for first-session
**Any checks fail** → See corresponding section above for fixes
