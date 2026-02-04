# Python Setup Reference

Comprehensive guide for installing Python 3.11+ on macOS and Linux platforms.

## Contents
- [macOS Installation](#macos-installation)
- [Linux Installation](#linux-installation)
- [Version Comparison Table](#version-comparison-table)
- [Installation Time Estimates](#installation-time-estimates)
- [Verification Checklist](#verification-checklist)

---

## macOS Installation

### Prerequisites: Xcode Command Line Tools

**Required for**: Compiling Python packages, using Homebrew

```bash
# Check if already installed
xcode-select -p
# If returns path (e.g., /Library/Developer/CommandLineTools): Already installed
# If returns error: Need to install

# Install Command Line Tools
xcode-select --install
# Opens GUI installer - follow prompts
# Takes 5-10 minutes to download and install

# Verify installation
xcode-select -p
# Should return: /Library/Developer/CommandLineTools
```

**Common Issue**: "Can't install the software because it is not currently available from the Software Update server"
- **Cause**: Already installed or partial install
- **Fix**: Try `sudo rm -rf /Library/Developer/CommandLineTools` then retry install

---

### Homebrew Installation

**What is Homebrew**: Package manager for macOS (like app store for developer tools)

**Check if already installed**:
```bash
which brew
# Exit 0 (found): Already installed, skip to Python installation
# Exit 127 (not found): Need to install Homebrew first
```

**Install Homebrew**:
```bash
# Run official installer
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Follow prompts:
# - Press RETURN to continue
# - Enter your password when asked (for sudo)
# - Wait for download and installation (5-10 minutes)

# IMPORTANT: After install completes, installer shows commands to add Homebrew to PATH
# Example output:
#   ==> Next steps:
#   - Run these two commands in your terminal to add Homebrew to your PATH:
#       echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
#       eval "$(/opt/homebrew/bin/brew shellenv)"

# Copy and paste those commands (they differ for Apple Silicon vs Intel)

# Verify Homebrew is working
brew --version
# Should show: Homebrew X.X.X
```

**Homebrew Locations**:
- **Apple Silicon (M1/M2/M3)**: `/opt/homebrew/`
- **Intel Mac**: `/usr/local/homebrew/`

**Common Issue**: "brew: command not found" after install
- **Cause**: Shell not restarted or PATH not configured
- **Fix**: Close terminal, open new one, try `brew --version` again
- **Or**: Run the "add to PATH" commands shown at end of install

---

### Python 3.11 Installation via Homebrew

```bash
# Install Python 3.11 (or 3.12 if available)
brew install python@3.11

# Installation includes:
# - Python 3.11.x interpreter
# - pip package manager
# - venv module (for virtual environments)

# Takes 2-5 minutes depending on internet speed

# Verify installation
python3 --version
# Expected: Python 3.11.x (e.g., 3.11.8)

# Check installation location
which python3
# Apple Silicon: /opt/homebrew/bin/python3
# Intel Mac: /usr/local/bin/python3

# Verify pip is available
python3 -m pip --version
# Expected: pip X.X.X from /opt/homebrew/lib/python3.11/site-packages/pip (python 3.11)
```

**If python3 --version shows old version** (e.g., system Python 3.9):
```bash
# Check all Python installations
which -a python3

# Example output:
# /opt/homebrew/bin/python3  (Homebrew - want this one)
# /usr/bin/python3          (System Python - avoid)

# Homebrew should be first in PATH
echo $PATH
# Should start with /opt/homebrew/bin or /usr/local/bin

# If system Python is first, update PATH
export PATH="/opt/homebrew/bin:$PATH"  # Apple Silicon
# OR
export PATH="/usr/local/bin:$PATH"     # Intel

# Make permanent
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify
python3 --version  # Should now show 3.11.x
```

**Multiple Python versions installed**:
```bash
# Use explicit version command
python3.11 --version  # Explicitly use 3.11

# Create alias for convenience (add to ~/.zshrc)
alias python3=python3.11

# Or update default symlink
brew link --overwrite python@3.11
```

---

### Alternative: Python.org Official Installer

**Use if**: Homebrew unavailable or unwanted, need official Python

**Download**:
1. Go to https://www.python.org/downloads/
2. Download "macOS 64-bit universal2 installer" for Python 3.11.x
3. Open .pkg file, follow installer prompts

**Installation location**: `/Library/Frameworks/Python.framework/Versions/3.11/`

**Post-install**:
```bash
# Verify
python3 --version
# Should show Python 3.11.x

# Check location
which python3
# Should show: /usr/local/bin/python3

# Verify pip
python3 -m pip --version
```

**Pros vs Homebrew**:
- ✓ Simpler (no Homebrew dependency)
- ✓ Official Python distribution
- ✗ No automatic updates (manual download for patches)
- ✗ No package management for other tools

---

### macOS Shell Configuration

**Default Shell by Version**:
- macOS 10.15+ (Catalina and newer): **zsh** (default)
- macOS 10.14 and older: **bash**

**Check your shell**:
```bash
echo $SHELL
# /bin/zsh = zsh (use ~/.zshrc)
# /bin/bash = bash (use ~/.bash_profile)
```

**Configuration Files**:
- **zsh**: `~/.zshrc` - Loaded every time you open a terminal
- **bash**: `~/.bash_profile` - Loaded for login shells

**Adding Homebrew to PATH** (if not done during install):
```bash
# For zsh (macOS 10.15+)
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
source ~/.zshrc

# For bash (older macOS)
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.bash_profile
source ~/.bash_profile
```

---

### macOS Troubleshooting

**Issue: "xcode-select: error: command line tools are already installed"**
- **When**: Running `xcode-select --install`
- **Meaning**: Already installed, proceed to Homebrew/Python
- **Verify**: `xcode-select -p` should return path

**Issue: "certificate verify failed" during brew install**
- **Cause**: System clock wrong or corporate proxy
- **Fix**: Check system time in Settings, or use `brew install --ignore-dependencies python@3.11`

**Issue: Python 3.11 installed but python3 still shows 3.9**
- **Cause**: System Python has priority in PATH
- **Fix**: Update PATH (see "If python3 --version shows old version" above)

**Issue: "Operation not permitted" during brew install**
- **Cause**: macOS System Integrity Protection (SIP) blocking
- **Fix**: Install to user directory or check SIP status with `csrutil status`

**Issue: Multiple Python versions causing conflicts**
- **Symptom**: `python3` points to different version than expected
- **Fix**:
  ```bash
  # See all python3 commands
  which -a python3

  # Use explicit version
  python3.11 --version

  # Update Homebrew links
  brew unlink python@3.9  # If old version linked
  brew link python@3.11
  ```

---

## Linux Installation

### Ubuntu/Debian (APT Package Manager)

**Default Python versions** (as of 2024):
- Ubuntu 24.04: Python 3.12 (no install needed)
- Ubuntu 22.04 LTS: Python 3.10 (need to upgrade to 3.11+)
- Ubuntu 20.04 LTS: Python 3.8 (need to upgrade to 3.11+)
- Debian 12: Python 3.11 (no install needed)
- Debian 11: Python 3.9 (need to upgrade to 3.11+)

**Check current version**:
```bash
python3 --version
# If ≥3.11.0: No install needed, skip this section
# If <3.11.0: Follow steps below
```

**Install Python 3.11 from deadsnakes PPA**:

```bash
# Step 1: Add deadsnakes PPA (trusted Python builds for Ubuntu)
sudo add-apt-repository ppa:deadsnakes/ppa
# Press ENTER when prompted
# Requires sudo password

# Step 2: Update package list
sudo apt update

# Step 3: Install Python 3.11 with venv and dev packages
sudo apt install python3.11 python3.11-venv python3.11-dev

# Packages explained:
# - python3.11: Python interpreter
# - python3.11-venv: Virtual environment support (CRITICAL)
# - python3.11-dev: Headers for compiling Python packages

# Takes 2-5 minutes

# Step 4: Verify installation
python3.11 --version
# Should show: Python 3.11.x
```

**Make python3 point to Python 3.11** (optional but recommended):

```bash
# Current state: python3 points to old version (e.g., 3.10)
python3 --version  # Shows 3.10.x

# Update alternatives to use 3.11 as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# If multiple versions, choose which is default
sudo update-alternatives --config python3
# Shows menu like:
#   Selection    Path                Priority
#   0            /usr/bin/python3.10  1
#   1            /usr/bin/python3.11  1
# Enter "1" to choose Python 3.11

# Verify
python3 --version  # Should now show 3.11.x
```

**Install pip for Python 3.11**:
```bash
# Usually installed automatically, but verify
python3.11 -m pip --version

# If not found, install manually
sudo apt install python3.11-distutils
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Verify
python3.11 -m pip --version
```

---

### CentOS/RHEL (YUM Package Manager)

**Default Python versions**:
- CentOS 9 Stream / RHEL 9: Python 3.9 (need to upgrade)
- CentOS 8 Stream / RHEL 8: Python 3.6 (need to upgrade)
- CentOS 7: Python 2.7 or 3.6 (need to upgrade)

**Install Python 3.11**:

```bash
# CentOS 9 / RHEL 9
sudo yum install python311 python311-devel

# CentOS 8 / RHEL 8 (may need EPEL repository)
sudo yum install epel-release
sudo yum install python311 python311-devel

# Verify
python3.11 --version
# Should show: Python 3.11.x

# Create python3 symlink (if needed)
sudo alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Verify
python3 --version  # Should show 3.11.x
```

**Install pip**:
```bash
python3.11 -m ensurepip --upgrade
python3.11 -m pip --version
```

---

### Fedora (DNF Package Manager)

**Fedora typically has recent Python** (Fedora 38+: Python 3.11+ default)

```bash
# Check current version
python3 --version

# If need to install 3.11+
sudo dnf install python3.11 python3.11-devel

# Verify
python3.11 --version
```

---

### Linux Build Tools (Required for Some Packages)

**Why needed**: Some Python packages compile C extensions during install

**Ubuntu/Debian**:
```bash
# Install build essentials (gcc, make, etc.)
sudo apt install build-essential

# Install additional libraries (often needed)
sudo apt install libssl-dev libffi-dev python3.11-dev
```

**CentOS/RHEL**:
```bash
# Install development tools
sudo yum groupinstall "Development Tools"

# Install additional libraries
sudo yum install openssl-devel libffi-devel python311-devel
```

**Fedora**:
```bash
sudo dnf groupinstall "Development Tools"
sudo dnf install openssl-devel libffi-devel python3.11-devel
```

---

### Linux Symlink Management

**Understanding Python symlinks**:
- `/usr/bin/python3` → Points to default Python 3.x
- `/usr/bin/python3.11` → Explicit Python 3.11
- `/usr/bin/python` → May point to Python 2.7 (legacy)

**Update default Python 3 to 3.11**:

```bash
# Method 1: update-alternatives (Ubuntu/Debian)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --config python3

# Method 2: alternatives (CentOS/RHEL)
sudo alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo alternatives --config python3

# Method 3: Manual symlink (all distros, use cautiously)
sudo rm /usr/bin/python3  # Remove old symlink
sudo ln -s /usr/bin/python3.11 /usr/bin/python3  # Create new symlink

# Verify
python3 --version  # Should show 3.11.x
ls -la /usr/bin/python3  # Should point to python3.11
```

**Warning about changing system Python**:
- Some system tools rely on specific Python version
- Safer to use `python3.11` explicitly in scripts
- Or use virtual environments (recommended)

---

### Linux Troubleshooting

**Issue: "No module named venv"**
- **Symptom**: `python3.11 -m venv .venv` fails
- **Cause**: python3.11-venv package not installed
- **Fix**: `sudo apt install python3.11-venv` (Ubuntu/Debian)

**Issue: "No module named pip"**
- **Symptom**: `python3.11 -m pip` fails
- **Cause**: pip not installed for Python 3.11
- **Fix**:
  ```bash
  # Ubuntu/Debian
  sudo apt install python3.11-distutils
  curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

  # CentOS/RHEL
  python3.11 -m ensurepip --upgrade
  ```

**Issue: "E: Unable to locate package python3.11"**
- **Symptom**: `apt install python3.11` fails
- **Cause**: deadsnakes PPA not added (Ubuntu) or wrong repo (Debian)
- **Fix**:
  ```bash
  # Ubuntu: Add deadsnakes PPA
  sudo add-apt-repository ppa:deadsnakes/ppa
  sudo apt update
  sudo apt install python3.11

  # Debian: Use backports or compile from source
  ```

**Issue: Permission errors compiling packages later**
- **Symptom**: `error: command 'gcc' failed` during pip install
- **Cause**: Build tools not installed
- **Fix**: `sudo apt install build-essential python3.11-dev`

**Issue: Multiple Python versions causing conflicts**
- **Symptom**: `python3 --version` shows different version than expected
- **Fix**: Use explicit version (`python3.11`) or update alternatives (see Symlink Management)

---

## Version Comparison Table

| Platform | Default Python | Install Method | Post-Install Command |
|----------|---------------|----------------|---------------------|
| macOS (any) | 3.9.x (system) | `brew install python@3.11` | `python3 --version` |
| Ubuntu 24.04 | 3.12.x | No install needed | `python3 --version` |
| Ubuntu 22.04 | 3.10.x | `sudo apt install python3.11 python3.11-venv` | `python3.11 --version` |
| Ubuntu 20.04 | 3.8.x | `sudo apt install python3.11 python3.11-venv` | `python3.11 --version` |
| Debian 12 | 3.11.x | No install needed | `python3 --version` |
| Debian 11 | 3.9.x | `sudo apt install python3.11 python3.11-venv` | `python3.11 --version` |
| CentOS 9 | 3.9.x | `sudo yum install python311` | `python3.11 --version` |
| Fedora 38+ | 3.11+ | No install needed | `python3 --version` |

---

## Installation Time Estimates

- **Xcode Command Line Tools** (macOS): 5-10 minutes
- **Homebrew installation** (macOS): 5-10 minutes
- **Python via Homebrew** (macOS): 2-5 minutes
- **Python via APT** (Ubuntu/Debian): 2-5 minutes
- **Python via YUM** (CentOS/RHEL): 3-7 minutes
- **Total first-time setup** (macOS, no Homebrew): 15-25 minutes
- **Total first-time setup** (Linux): 5-15 minutes

---

## Verification Checklist

After installation, verify these work:

```bash
# Python version (must be ≥3.11.0)
python3 --version

# Python location (should be Homebrew on macOS, /usr/bin on Linux)
which python3

# pip available
python3 -m pip --version

# venv module available (critical for virtual environments)
python3 -m venv --help

# Can create test venv
python3 -m venv /tmp/test_venv
source /tmp/test_venv/bin/activate
python --version  # Should match python3 version
deactivate
rm -rf /tmp/test_venv
```

**All checks pass** → Ready to proceed to package installation (Phase 3)

**Any checks fail** → See troubleshooting section for your platform
