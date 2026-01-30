---
name: complete-setup
description: Conversational environment setup for non-technical users on macOS and Linux. Handles Python 3.11+ verification, package installation via Poetry or venv, config initialization, and seamless handoff to first-session. Activates when user requests "help me get started", "I'm not technical", "setup from scratch", or "I need to install this".
allowed-tools: Bash, Read, Write, AskUserQuestion
argument-hint: ""
---

# Complete Setup Skill

## Overview

**Purpose**: Conversational environment setup for non-technical users.

**What this skill does**:
- Verifies Python 3.11+ (guides install if needed)
- Installs Sports Coach Engine package (Poetry or venv)
- Initializes config structure (`sce init`)
- Validates environment readiness
- Hands off to `first-session` for Strava auth and profile

**Platform support**: macOS, Linux (Ubuntu/Debian, CentOS/RHEL). **NOT supported**: Windows (including WSL)

**Adaptive workflow**: Detects environment state and only executes necessary phases. Skips completed steps (e.g., if Python 3.11+ present, skip Phase 2).

**What first-session handles**: Strava credentials, OAuth flow, profile setup (not duplicated here)

---

## Workflow - Phase 1: Environment Detection

**Goal**: Determine which phases needed based on environment state.

### WSL Detection (Critical - MUST run first)

```bash
# Block WSL1 and WSL2 before platform detection
if [ -f /proc/sys/fs/binfmt_misc/WSLInterop ] || [ -d /mnt/c ] && grep -qiE '(microsoft|WSL)' /proc/version 2>/dev/null; then
  echo "❌ Windows Subsystem for Linux (WSL) detected but not supported"
  echo "Please use native Linux or macOS"
  exit 1
fi
```

### Detection Commands (run in parallel after WSL check)

```bash
uname                  # Platform: "Darwin" (macOS) or "Linux"
python3 --version      # Exit 0 + ≥3.11 → skip Phase 2 | Exit 127 → run Phase 2
sce --version          # Exit 0 → skip Phase 3 | Exit 127 → run Phase 3 | Exit 2 → skip to Phase 4
ls -la config/         # Exit 0 → skip Phase 4 | Exit 2 → run Phase 4
```

### Decision Logic

- **Python**: Exit 0 + ≥3.11 → skip Phase 2 | Otherwise → run Phase 2
- **Package**: Exit 0 → skip Phase 3 | Exit 2 → skip to Phase 4 | Exit 127 → run Phase 3
- **Config**: Exit 0 → skip Phase 4 | Exit 2 → run Phase 4

### Output Summary

```
Environment Check:
✓ Platform: macOS (Apple Silicon)
✗ Python: Not found (need to install)
✗ Package: Not installed
✗ Config: Not initialized
```

---

## Workflow - Phase 2: Python Setup

**Conditional**: Skip if Python ≥3.11 detected in Phase 1.

### Install Python 3.11+

**macOS**:
- **Recommended**: Use Homebrew for Python installation
  - Check availability: `which brew` (exit 0 = available)
  - If missing: Install Homebrew first → [python_setup.md#macos-installation](references/python_setup.md#macos-installation)
  - Install Python: `brew install python@3.11`
  - Common issues: Xcode CLT missing (`xcode-select --install`), PATH updates
- **Alternative**: Python.org official installer (simpler but less flexible)

**Linux**:
- **Ubuntu/Debian**: deadsnakes PPA → `sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.11 python3.11-venv`
  - See [python_setup.md#linux-installation](references/python_setup.md#linux-installation) for full commands
- **CentOS/RHEL**: `sudo yum install python311 python311-devel`
- Common issues: python3-venv missing, permission errors, symlink conflicts

### Validation

```bash
python3 --version  # Must show ≥3.11.0
python3 -m pip --version  # Verify pip available
```

**If fails - see specific sections**:
- Python not found: [troubleshooting.md#python-installed-but-not-in-path](references/troubleshooting.md#python-installed-but-not-in-path)
- Wrong version: [troubleshooting.md#wrong-python-version-installed](references/troubleshooting.md#wrong-python-version-installed)
- Multiple versions: [troubleshooting.md#multiple-python-installations-causing-conflicts](references/troubleshooting.md#multiple-python-installations-causing-conflicts)

---

## Workflow - Phase 3: Package Installation

**Conditional**: Skip if `sce --version` works (exit 0 or 2).

### Determine Installation Method

```bash
poetry --version
# Exit 0 → Use Poetry | Exit 127 → Use venv
```

### Path A: Poetry

```bash
poetry install  # Creates venv, installs dependencies, installs sce
sce --version   # Verify (or: poetry run sce --version)
```

**Success**: Output shows "Installing dependencies", no errors, `sce --version` works (exit 0)

**Common issues**: See [package_installation.md#path-a-poetry-installation](references/package_installation.md#path-a-poetry-installation)
- poetry.lock out of sync → `poetry lock --no-update && poetry install`
- Dependency conflicts → Check Python ≥3.11, update Poetry
- sce not found → Try `poetry run sce --version` or restart terminal

### Path B: venv

```bash
python3 -m venv .venv            # Create virtual environment
source .venv/bin/activate        # Activate (CRITICAL - check for (.venv) prefix in prompt)
pip install --upgrade pip        # Upgrade pip
pip install -e .                 # Install package in editable mode
sce --version                    # Verify
```

**CRITICAL**: `source .venv/bin/activate` is essential. Without it:
- sce not found (exit 127)
- Permission errors during pip install

**Teaching moment**: "The (.venv) prefix means the virtual environment is active - like a sandbox for dependencies. Activate each time you open a new terminal: `source .venv/bin/activate`"

**Common issues**: See [package_installation.md#path-b-venv-installation](references/package_installation.md#path-b-venv-installation)
- Permission denied → venv not activated (check prompt for (.venv) prefix)
- sce not found → Check `echo $VIRTUAL_ENV` shows path, retry activation
- No module named venv (Linux) → `sudo apt install python3.11-venv`

### Validation Loop

```bash
# Validate installation
sce --version  # MUST return exit 0 and show version string

# If validation fails (exit ≠ 0):
# 1. Identify issue (see diagnostic commands in package_installation.md)
# 2. Apply fix (activate venv, retry install, check PATH)
# 3. Re-validate (loop until exit 0)
# 4. Only proceed to Phase 4 when validation passes
```

**Diagnostic commands**:
```bash
which sce         # Check if sce in PATH
echo $VIRTUAL_ENV # Check venv active (venv path only)
```

**If validation fails - see specific sections**:
- sce not found: [package_installation.md#troubleshooting-command-not-found](references/package_installation.md#troubleshooting-command-not-found)
- Permission errors: [package_installation.md#issue-1-permission-errors-during-pip-install](references/package_installation.md#issue-1-permission-errors-during-pip-install)
- Dependency conflicts: [package_installation.md#issue-2-dependency-conflicts](references/package_installation.md#issue-2-dependency-conflicts)

---

## Workflow - Phase 4: Configuration Initialization

**Conditional**: Skip if `config/` directory exists.

### Run sce init

```bash
sce init  # Creates config/, data/ directories and YAML templates
```

**Expected output**: Confirmation message showing created files (secrets.local.yaml, athlete_profile.yaml, training_plan.yaml)

### Verification

```bash
ls -la config/  # Should show YAML files
cat config/secrets.local.yaml  # Should have placeholder credentials
```

**If secrets.local.yaml has real credentials** (not placeholders): Skip this phase (don't overwrite)

**If validation fails - see specific sections**:
- Config init failed: [troubleshooting.md#config-directory-not-created](references/troubleshooting.md#config-directory-not-created)
- YAML malformed: [troubleshooting.md#secretslocalyaml-malformed](references/troubleshooting.md#secretslocalyaml-malformed)

---

## Workflow - Phase 5: Verification & Handoff

### Final Validation

```bash
python3 --version      # ✓ Python 3.11+
sce --version          # ✓ Package installed
ls -la config/         # ✓ Config directory exists
echo $VIRTUAL_ENV      # ✓ venv active (if using venv path)
```

**Success message**:
```
✓ Environment Setup Complete!

Your coaching environment is ready:
  ✓ Python 3.11+ installed
  ✓ Sports Coach Engine package installed
  ✓ Configuration initialized

Next: Let's connect to Strava and set up your athlete profile...
```

### Seamless Handoff to first-session

**Transition**: "Now that your environment is ready, let's get your Strava data connected. I'll need your Strava API credentials - have you created a Strava API application yet?"

**If no**: Guide to https://www.strava.com/settings/api → Create application → Copy Client ID/Secret

**What first-session handles**:
1. Credential collection and save to config/secrets.local.yaml
2. OAuth flow (`sce auth url`)
3. Activity sync (`sce sync`) — then a brief overview: activities synced, time span (weeks/months), and whether rate limit was hit
4. Profile setup (name, age, max HR, sports)
5. Goal setting and constraints

---

## Adaptive Workflow Logic

Phase 1 detection determines which phases run:
- **Python ≥3.11** → Skip Phase 2
- **sce works (exit 0/2)** → Skip Phase 3
- **config/ exists** → Skip Phase 4
- **All ready** → Direct to Phase 5 handoff

---

## Common Issues

For troubleshooting, see [Quick Fixes](references/troubleshooting.md#quick-fixes) for the top 5 issues, or browse the full [Troubleshooting Reference](references/troubleshooting.md).

---

## Success Criteria

**Environment is ready when all these are true**:

1. ✓ Python 3.11+ responds to `python3 --version` (exit code 0)
2. ✓ `sce --version` returns version string (exit code 0)
3. ✓ `config/` directory exists with secrets.local.yaml
4. ✓ Virtual environment active (if using venv path) - prompt shows `(.venv)`
5. ✓ User understands next steps (Strava credentials)

**Ready to hand off to first-session when**:

- User asks about Strava connection
- User is ready to provide API credentials
- All environment checks pass

---

## Additional Resources

**Reference Files** (for deep dives):

- `references/environment_checks.md` - Validation commands and troubleshooting
- `references/python_setup.md` - Platform-specific Python installation details
- `references/troubleshooting.md` - Comprehensive error resolution guide

**Example Workflows**:

- `examples/example_macos_homebrew.md` - Complete macOS setup transcript (Homebrew + Poetry)
- `examples/example_ubuntu_apt.md` - Complete Ubuntu setup transcript (APT + venv)

**Related Skills**:

- `first-session` - Strava authentication and athlete profile setup (automatic handoff)

**External Documentation**:

- Python installation: https://www.python.org/downloads/
- Homebrew (macOS): https://brew.sh/
- Poetry: https://python-poetry.org/docs/
- Strava API setup: https://www.strava.com/settings/api
