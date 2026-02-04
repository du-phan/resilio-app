# Example: Ubuntu Setup with APT and venv

Complete conversational transcript showing the `complete-setup` skill guiding a non-technical user through environment setup on Ubuntu 22.04 (Linux).

**User Context**:
- Platform: Ubuntu 22.04 LTS (default Python 3.10)
- No Poetry installed
- Some technical familiarity (has used Linux before)
- First time setting up Python development environment

---

## Conversation Transcript

**User**: "I want to get started with the Sports Coach Engine. Help me set it up from scratch."

**Coach**: I'll guide you through the setup! Let me check your current environment.

[Runs platform and environment detection commands]

```bash
uname  # Returns: Linux
python3 --version  # Returns: Python 3.10.12
sce --version  # Returns: exit code 127 (not found)
poetry --version  # Returns: exit code 127 (not found)
```

**Coach**:
```
Environment Check:
✓ Platform: Linux (Ubuntu/Debian)
○ Python: 3.10.12 installed (need 3.11+ for the coaching system)
✗ Package: Not installed
✗ Poetry: Not found
✗ Config: Not initialized

I see you're on Linux with Python 3.10. We need Python 3.11 or newer for the coaching system.

Here's what we'll do:
1. Install Python 3.11 (won't replace your 3.10 - they'll coexist)
2. Create a virtual environment (isolated space for the coaching system)
3. Install the Sports Coach Engine package
4. Initialize configuration

This will take about 10-15 minutes. Some commands will need 'sudo' (administrator access) - I'll explain each one. Ready?
```

**User**: "Yes, let's do it."

**Coach**: Great! First, we'll install Python 3.11.

On Ubuntu, the best way is to use the 'deadsnakes' PPA (Personal Package Archive). This is a trusted repository that provides newer Python versions for Ubuntu.

I'm going to run three commands:

**Command 1**: Add the deadsnakes PPA
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
```
This requires sudo (administrator access) - you'll need to enter your password.

May I run this?

**User**: "Yes"

[Runs command]

**Coach**: [After PPA addition]

You'll see a message about the PPA being added. Press ENTER when prompted to confirm.

[User presses ENTER]

**Coach**: Perfect! Now let's update the package list:

**Command 2**: Update package information
```bash
sudo apt update
```

This refreshes the list of available packages (takes 5-10 seconds).

[Runs apt update]

**Coach**: [After update completes]

Now for the actual Python installation:

**Command 3**: Install Python 3.11 with required modules
```bash
sudo apt install python3.11 python3.11-venv python3.11-dev
```

This installs:
- **python3.11**: The Python interpreter itself
- **python3.11-venv**: Virtual environment support (important!)
- **python3.11-dev**: Development headers (needed for some packages)

Takes 2-5 minutes. You'll see a download progress bar.

[Python installation proceeds]

**Coach**: [After installation completes]

Python 3.11 is installed! Let me verify:
```bash
python3.11 --version
# Returns: Python 3.11.8
```

✓ Python 3.11.8 is ready!

**Coach**:
Now, I noticed you don't have Poetry installed. That's totally fine - we can use Python's built-in virtual environment tool instead (it's called 'venv'). This works great and doesn't require any extra installations.

Here's what a virtual environment does: It creates an isolated space for the coaching system's packages, so they don't interfere with your system's Python or other projects. Think of it like a separate container.

Let me create one:
```bash
python3.11 -m venv .venv
```

This creates a directory called `.venv` in the current folder. Takes about 5-10 seconds.

[venv creation completes]

**Coach**:
Virtual environment created! Now we need to "activate" it. This tells your terminal to use the packages inside `.venv` instead of the system packages.

I'm running:
```bash
source .venv/bin/activate
```

**Coach**: [After activation]

See how your terminal prompt changed? It now shows `(.venv)` at the beginning:
```
(.venv) user@hostname:~/sports-coach-engine$
```

That means the virtual environment is active. Whenever you see `(.venv)`, you know you're in the right environment.

**Important**: Every time you open a new terminal, you'll need to activate the virtual environment again with:
```bash
source .venv/bin/activate
```

Got it?

**User**: "Yes, I understand. So I'll need to run that activation command each time?"

**Coach**: Exactly! It's a one-time thing per terminal session. Think of it like logging into the coaching system environment each time you open a terminal.

Now let's install the Sports Coach Engine package!

First, I'll upgrade pip (Python's package installer) to the latest version:
```bash
pip install --upgrade pip
```

This ensures we have the newest features and bug fixes. Takes about 10 seconds.

[pip upgrade completes]

**Coach**:
Now for the main installation:
```bash
pip install -e .
```

The `-e` flag means "editable mode" - this installs the package from the current directory.

This will:
- Download all required packages
- Install them in the virtual environment
- Set up the `sce` command

Takes 30-60 seconds. You'll see package names scroll by with progress bars.

[Package installation proceeds with output showing dependencies]

**Coach**: [After installation completes]

Installation complete! Let me verify the `sce` command works:
```bash
sce --version
# Returns: sports-coach-engine, version 0.4.0
```

✓ Package installed successfully!

Now let's initialize the configuration files:
```bash
sce init
```

[Config initialization output]
```
Configuration initialized successfully!

Created:
  ✓ config/secrets.local.yaml
  ✓ config/athlete_profile.yaml
  ✓ config/training_plan.yaml
  ✓ data/ directory

Next steps:
  1. Add your Strava API credentials to config/secrets.local.yaml
  2. Run: sce auth url
```

**Coach**:
Perfect! Let me run a final check to make sure everything is ready:

```bash
# Environment verification
python3 --version      # ✓ Python 3.11.8
sce --version          # ✓ sports-coach-engine, version 0.4.0
echo $VIRTUAL_ENV      # ✓ Shows: /home/user/sports-coach-engine/.venv
ls config/             # ✓ Shows: secrets.local.yaml, athlete_profile.yaml, training_plan.yaml
```

**Coach**:
✓ Environment Setup Complete!

Your coaching environment is ready:
  ✓ Python 3.11 installed
  ✓ Virtual environment created and activated
  ✓ Sports Coach Engine package installed
  ✓ Configuration initialized

**Important reminder**: When you open a new terminal in the future, remember to activate the virtual environment:
```bash
cd ~/sports-coach-engine
source .venv/bin/activate
```

Then you can use all the `sce` commands.

---

**Now let's connect to Strava and set up your athlete profile!**

To do this, I need your Strava API credentials. These allow the coaching system to read your activity history from Strava.

Have you created a Strava API application yet?

**User**: "No, what do I need to do?"

**Coach**: Here's the step-by-step process:

1. Open your web browser and go to: https://www.strava.com/settings/api
2. Log in to your Strava account if needed
3. Fill out the "My API Application" form:
   - **Application Name**: "My Coach" (or any name)
   - **Category**: Any category is fine
   - **Club**: Leave blank
   - **Website**: http://localhost
   - **Authorization Callback Domain**: localhost

4. Click "Create" at the bottom

After creating it, you'll see two important values:
- **Client ID**: A number like 123456
- **Client Secret**: A long string like "a1b2c3d4e5f6..."

Copy both of these and paste them here. I'll save them securely to your local config file (they never leave your computer).

**User**: [Pastes credentials]
```
Client ID: 123456
Client Secret: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

**Coach**: Perfect! Let me save these to your configuration:

[Writes to config/secrets.local.yaml]

```bash
# Updating config/secrets.local.yaml with credentials
```

✓ Credentials saved securely!

Now let's authenticate with Strava. I'm running:
```bash
sce auth url
```

[Command output shows authorization URL]

**Coach**:
I've generated an authorization URL. Open this link in your browser:

https://www.strava.com/oauth/authorize?client_id=123456&redirect_uri=http://localhost:8080/callback&response_type=code&scope=activity:read_all

Steps:
1. Click the link (or copy/paste into browser)
2. Log in to Strava if needed
3. Click "Authorize" to grant access
4. Your browser will show a page with a code
5. Copy that code and paste it here

[From this point, the conversation continues with the standard first-session workflow: OAuth completion, activity sync, profile setup]

---

## Key Teaching Moments in This Transcript

1. **sudo Explanation**: Explained what sudo is for non-technical users ("administrator access")

2. **Virtual Environment Concept**: Used analogy ("isolated space", "like a separate container")

3. **Visual Indicator**: Pointed out the `(.venv)` prompt prefix as confirmation of activation

4. **Future Usage Reminder**: Warned about needing to activate venv each terminal session

5. **Multiple Python Versions**: Explained that Python 3.11 installs alongside 3.10 (won't replace it)

6. **Security Reassurance**: Mentioned credentials "never leave your computer" to build trust

---

## Commands Run (Summary)

**Phase 1: Environment Detection**
```bash
uname
python3 --version
sce --version
poetry --version
```

**Phase 2: Python 3.11 Installation**
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
python3.11 --version
```

**Phase 3: Package Installation (venv path)**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

**Phase 4: Configuration Initialization**
```bash
sce init
```

**Phase 5: Verification**
```bash
python3 --version
sce --version
echo $VIRTUAL_ENV
ls config/
```

---

## Timeline

- **Python install** (apt): 2-5 minutes (download + installation)
- **venv creation**: 5-10 seconds
- **pip upgrade**: 10 seconds
- **Package install**: 30-60 seconds
- **Config init**: <5 seconds
- **Total**: ~4-7 minutes (faster than macOS due to no Homebrew setup)

---

## Differences from macOS Path

1. **Package Manager**: APT (system package manager) instead of Homebrew
2. **Sudo Required**: Linux needs sudo for system package installs; macOS Homebrew doesn't
3. **Virtual Environment**: Explicit venv creation/activation vs Poetry's automatic handling
4. **Python Command**: Used `python3.11` explicitly vs relying on `python3` symlink
5. **Visual Activation Indicator**: Emphasized `(.venv)` prompt prefix

---

## Troubleshooting Moments (If They Occurred)

### If Build Tools Missing

**Error Message**: "error: command 'gcc' failed with exit status 1"

**Coach Response**:
"I see we need some build tools. Some Python packages need to compile C code during installation.

I'm running:
```bash
sudo apt install build-essential python3.11-dev
```

This installs gcc (the compiler) and Python development headers. Takes 1-2 minutes.

[After install]

Now let's retry the package installation:
```bash
pip install -e .
```

Should work now!"

---

### If User Forgets to Activate venv Later

**User** (in new terminal): "The sce command isn't working anymore!"

**Coach Response**:
"Ah, did you activate the virtual environment in this terminal? Remember, each new terminal needs activation.

Try this:
```bash
cd ~/sports-coach-engine
source .venv/bin/activate
```

Now check:
```bash
sce --version
```

Should work now! You'll see the `(.venv)` prefix in your prompt when the environment is active."

---

### If python3-venv Package Missing

**Error Message**: "Error: Command '['/path/.venv/bin/python3', '-Im', 'ensurepip'...]' returned non-zero exit status 1"

**Coach Response**:
"Looks like the venv module is missing. This is a common issue on Ubuntu - the venv module is a separate package.

Let me install it:
```bash
sudo apt install python3.11-venv
```

[After install]

Now let's retry creating the virtual environment:
```bash
python3.11 -m venv .venv
```

Should work this time!"

---

## Adaptive Workflow Examples

### Scenario: Python 3.11 Already Installed

**Detection Output**: `python3.11 --version` returns "Python 3.11.8"

**Coach Response**:
"Great news! Python 3.11 is already installed on your system. We can skip the installation step and go straight to creating the virtual environment.

Let me create the venv:
```bash
python3.11 -m venv .venv
```

[Continues to Phase 3]"

---

### Scenario: Package Already Installed

**Detection Output**: `sce --version` returns exit code 0

**Coach Response**:
"I see the Sports Coach Engine package is already installed! Let me just verify the configuration:

```bash
ls config/
```

[If config exists]
Everything looks ready! Let's move on to connecting your Strava account.

[Skips to Phase 5/handoff]"

---

### Error Recovery Example: sce Not Found After Install

**Scenario**: User forgets to activate venv after creating it

**User Commands**:
```bash
python3.11 -m venv .venv
# [User forgets to activate]
pip install -e .
```

**Error Output**:
```
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try apt install
    python3-xyz, where xyz is the package you are trying to install.
```

**Coach Response**:
"I see you got an error about 'externally-managed-environment'. This is Ubuntu 22.04+ protecting you from accidentally modifying system Python. We need to use our virtual environment.

The issue: we created the venv but didn't activate it. Let's activate it now:

```bash
source .venv/bin/activate
```

See the `(.venv)` prefix in your prompt? That means you're now in the virtual environment - a safe sandbox for the coaching engine.

Now let's try the install again:
```bash
pip install -e .
```

**User**: [Install succeeds]

**Coach**: "✓ Perfect! Remember to always activate the venv before running sce commands."

---

### Error Recovery Example: Python Symlink Conflict

**Scenario**: `python3` points to old version after installing 3.11

**Detection Output**: `python3 --version` shows "Python 3.10.12" after `apt install python3.11`

**Coach Response**:
"I see Python 3.11 is installed, but `python3` still points to the old version. This is normal on Ubuntu - the system keeps the default Python unchanged.

We have two options:

**Option 1** (recommended): Use `python3.11` explicitly
```bash
python3.11 -m venv .venv
# Always use python3.11 command
```

**Option 2**: Update the `python3` symlink to point to 3.11
```bash
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --config python3
# Choose Python 3.11 from the menu
```

For this setup, let's use Option 2 to make it simpler going forward.

[Runs update-alternatives commands]

Now `python3` points to 3.11:
```bash
python3 --version
# Python 3.11.8
```

**User**: "Got it! So now `python3` is the new version?"

**Coach**: "Exactly! Now let's create the virtual environment..."

---

### Error Recovery Example: Missing Build Tools

**Scenario**: Package installation fails with compilation errors

**Error During pip install -e .**:
```
error: command 'gcc' failed: No such file or directory
ERROR: Failed building wheel for some-package
```

**Coach Response**:
"I see a compilation error - some Python packages need to be built from source, which requires build tools (gcc compiler, etc.).

Ubuntu doesn't include these by default. Let's install them:

```bash
sudo apt install build-essential python3.11-dev
```

This installs:
- `gcc` (C compiler)
- `make` (build tool)
- `python3.11-dev` (Python header files)

[Install completes]

Now let's retry the package install:
```bash
pip install -e .
```

**User**: [Install succeeds this time]

**Coach**: "✓ That worked! The build tools allowed those packages to compile correctly."

---

### Error Recovery Example: Forgotten venv Activation in New Terminal

**Scenario**: User opens new terminal, tries to run sce

**User (in new terminal)**:
```bash
cd ~/sports-coach-engine
sce --version
```

**Error Output**: `sce: command not found`

**Coach Response**:
"The sce command isn't found because we're in a new terminal session. Remember: virtual environments need to be activated each time you open a new terminal.

Let's activate it:
```bash
source .venv/bin/activate
```

Now try again:
```bash
sce --version
```

**User**: "It works now!"

**Coach**: "Great! You'll need to do this activation step each time you open a new terminal.

**Pro tip**: To avoid this, you can add the activation command to your shell startup file:

```bash
echo 'source ~/sports-coach-engine/.venv/bin/activate' >> ~/.bashrc
```

Then it activates automatically! But that's optional - for now, just remember to run `source .venv/bin/activate` when you need to use sce."

---

## Success Criteria Met

- ✓ User understood virtual environment concept
- ✓ User knows how to activate venv in future sessions
- ✓ Environment fully functional (all checks passed)
- ✓ User comfortable with sudo commands (explained clearly)
- ✓ Ready for Strava authentication
- ✓ No external documentation needed
- ✓ Natural conversation flow maintained
- ✓ Error recovery demonstrated (externally-managed-environment, symlinks, build tools, venv activation)
