# Example: macOS Setup with Homebrew (Apple Silicon)

Complete conversational transcript showing the `complete-setup` skill guiding a non-technical user through environment setup on a fresh M1 MacBook.

**User Context**:
- Platform: macOS 13.5 (Ventura) on M1 MacBook Air
- No Python installed (beyond system Python 3.9)
- No Homebrew installed
- No technical background
- First time using Codex CLI

---

## Conversation Transcript

**User**: "Help me set up the Sports Coach Engine. I'm not very technical."

**Coach**: I'll guide you through this step by step! Let me first check what's already on your computer.

[Runs platform and environment detection commands]

```bash
uname  # Returns: Darwin
python3 --version  # Returns: exit code 127 (not found)
which brew  # Returns: exit code 127 (not found)
```

**Coach**:
```
Environment Check:
✓ Platform: macOS (Apple Silicon M1)
✗ Python 3.11+: Not found (need to install)
✗ Homebrew: Not found (need to install)
✗ Package: Not installed
✗ Config: Not initialized

I see you're on macOS with an M1 chip. We'll need to install a few things:

1. Homebrew (a tool that helps install other software)
2. Python 3.11 (the programming language the coaching system needs)
3. The Sports Coach Engine itself

This will take about 15-20 minutes total. Ready to start?
```

**User**: "Okay, yes!"

**Coach**: Great! First, we need Homebrew. Think of it like an app store for developer tools.

I'm going to run a command that will:
- Download Homebrew
- Ask for your computer password (the one you use to log in)
- Install it in a safe location

The command is:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

You'll see some text appear, and at some point it will ask for your password. When you type your password, **you won't see any characters appear** - that's normal for security! Just type it and press Enter.

May I run this command?

**User**: "Sure"

[Runs Homebrew installation command]

**Coach**: [After 2-3 minutes of installation output]

Great! Homebrew is installing. You should see messages about downloading and installing files. This part takes about 5-10 minutes.

[Installation completes]

**Coach**:
Perfect! Homebrew is installed. Now I need to add it to your PATH (that tells your computer where to find Homebrew).

I'm running these commands:
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
source ~/.zprofile
```

**Coach**: [After PATH setup]

Let me verify Homebrew is working:
```bash
brew --version
# Returns: Homebrew 4.2.5
```

✓ Homebrew is ready!

Now let's install Python 3.11. This is the programming language that powers the coaching system.

I'm running:
```bash
brew install python@3.11
```

This will download and install Python. Takes about 3-5 minutes.

[Python installation proceeds]

**Coach**: [After installation completes]

Python is installed! Let me verify:
```bash
python3 --version
# Returns: Python 3.11.8
```

✓ Python 3.11.8 is ready!

Now I'm checking if you have Poetry (a tool for managing Python packages):
```bash
poetry --version
# Returns: Poetry (version 1.7.1)
```

Great, you have Poetry! This will make the installation easier.

**Coach**:
Now for the main event: installing the Sports Coach Engine package itself.

I'm running:
```bash
poetry install
```

This will:
- Create a virtual environment (isolated space for the coaching system)
- Install all the required packages
- Set up the `sce` command

Takes about 30-60 seconds. You'll see a progress bar and lots of package names scroll by.

[Package installation proceeds]

**Coach**: [After poetry install completes]

Installation complete! Let me verify the `sce` command works:
```bash
sce --help
# Returns: exit code 0
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
  ✓ config/settings.yaml
  ✓ data/ directory

Next steps:
  1. Add your Strava API credentials to config/secrets.local.yaml
  2. Run: sce auth url
```

**Coach**:
Perfect! Let me run a final check to make sure everything is ready:

```bash
# Environment verification
python3 --version  # ✓ Python 3.11.8
sce --help         # ✓ exit code 0
ls config/         # ✓ Shows: secrets.local.yaml, settings.yaml
```

**Coach**:
✓ Environment Setup Complete!

Your coaching environment is ready:
  ✓ Python 3.11 installed
  ✓ Homebrew installed
  ✓ Sports Coach Engine package installed
  ✓ Configuration initialized

---

**Now let's connect to Strava and set up your athlete profile!**

To do this, I need your Strava API credentials. These allow the coaching system to read your activity history from Strava.

Have you created a Strava API application yet?

**User**: "No, I don't know how to do that."

**Coach**: No problem! I'll walk you through it. Here's what to do:

1. Open your web browser and go to: https://www.strava.com/settings/api
2. Log in to your Strava account if prompted
3. You'll see a form titled "My API Application"

Fill it out like this:
- **Application Name**: "Sports Coach Engine" (or any name you like)
- **Category**: Choose any (doesn't matter)
- **Club**: Leave blank
- **Website**: http://localhost (just a placeholder)
- **Authorization Callback Domain**: localhost

4. Click "Create" at the bottom

After you create it, you'll see:
- **Client ID**: A number like 123456
- **Client Secret**: A long string of letters and numbers

Copy both of these and paste them here in the chat. I'll save them to your local configuration file.

[From this point, the conversation transitions into the existing `first-session` skill workflow, which handles credential collection conversationally]

---

## Key Teaching Moments in This Transcript

1. **Password Invisibility**: Warned user that password won't show when typing (common confusion point)

2. **Time Expectations**: Gave realistic time estimates (15-20 minutes total) so user knows what to expect

3. **Visual Confirmation**: Used checkmarks (✓) to show progress and completion at each step

4. **Terminology Simplification**:
   - "Homebrew" = "app store for developer tools"
   - "PATH" = "tells your computer where to find Homebrew"
   - "Virtual environment" = "isolated space for the coaching system"

5. **Error Prevention**: Asked permission before running commands, explained what each would do

6. **Smooth Handoff**: Transitioned naturally into Strava API setup without explicit skill invocation

---

## Commands Run (Summary)

**Phase 1: Environment Detection**
```bash
uname
python3 --version
which brew
```

**Phase 2: Homebrew + Python Installation**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
source ~/.zprofile
brew install python@3.11
```

**Phase 3: Package Installation**
```bash
poetry --version
poetry install
```

**Phase 4: Configuration Initialization**
```bash
sce init
```

**Phase 5: Verification**
```bash
python3 --version
sce --help
ls config/
```

---

## Timeline

- **Homebrew install**: 5-10 minutes (download + installation)
- **Python install**: 3-5 minutes (via Homebrew)
- **Package install**: 30-60 seconds (Poetry)
- **Config init**: <5 seconds
- **Total**: ~10-16 minutes (most time is downloads)

---

## What User Sees vs What Happens

**User Experience**: Smooth, guided conversation with clear progress indicators

**Behind the Scenes**:
- Coach runs detection commands in parallel (Phase 1)
- Adaptive workflow: Skips steps that are already complete
- Poetry manages virtual environment automatically (invisible to user)
- Config files created with placeholder credentials
- Natural handoff to `first-session` skill for Strava setup

---

## Troubleshooting Moments (If They Occurred)

### If Xcode Command Line Tools Missing

**Error Message**: "xcrun: error: invalid active developer path"

**Coach Response**:
"I see we need the Xcode Command Line Tools first. These are development tools from Apple that Homebrew needs.

I'm running:
```bash
xcode-select --install
```

This will open a small window. Click 'Install' and wait 5-10 minutes for it to download and install. Let me know when it's done!"

[User waits for install]

**User**: "It says installation complete"

**Coach**: "Perfect! Now let's retry the Homebrew installation..."

---

### If Python Already Installed (Wrong Version)

**Detection Output**: `python3 --version` returns "Python 3.9.6"

**Coach Response**:
"I see you have Python 3.9 installed, but we need Python 3.11 or newer. Let me install the newer version via Homebrew - it will install alongside your existing Python without affecting it.

```bash
brew install python@3.11
```

[After install]

Now your system has both versions:
- `python3` → Python 3.9 (old)
- `python3.11` → Python 3.11 (new - what we'll use)

The coaching system will automatically use Python 3.11."

---

### If Python PATH Issue After Install

**Scenario**: Python 3.11 installed but `python3 --version` still shows old version

**Detection Output**: `python3 --version` returns "Python 3.10.12" after Homebrew install

**Coach Response**:
"I see Homebrew installed Python 3.11, but your shell is still using the old version. This is a PATH issue - your shell doesn't know about the new Python yet.

Let me check which Python is being used:
```bash
which python3
```
Shows: `/usr/bin/python3` (system Python, not Homebrew)

The Homebrew Python is installed at `/opt/homebrew/bin/python3` but isn't being found first. The simplest fix: close and reopen your terminal, then try again.

```bash
# Close terminal, reopen, then:
python3 --version
```

**User**: [Reopens terminal] "Now it shows Python 3.11.8!"

**Coach**: "Excellent! That fixed it. Your shell needed to refresh its PATH. Now continuing to package installation..."

---

### If Permission Denied During pip install

**Scenario**: User forgot to activate venv (if using venv path)

**Error During Installation**:
```
ERROR: Could not install packages due to an EnvironmentError: [Errno 13] Permission denied
```

**Coach Response**:
"I see a permission error. This usually means the virtual environment isn't activated.

Let me check:
```bash
echo $VIRTUAL_ENV
```
(No output - venv not active)

The venv isn't active. Let's activate it:
```bash
source .venv/bin/activate
```

See the `(.venv)` prefix in your prompt now? That means the virtual environment is active. This is important - it keeps the coaching engine's dependencies separate from your system Python.

Let's retry the install:
```bash
pip install -e .
```

**User**: [Install succeeds]

**Coach**: "✓ That worked! The package is now installed correctly."

---

### If Homebrew Installation Hangs

**Scenario**: Homebrew install appears stuck at "Downloading Command Line Tools"

**User**: "It's been downloading for 15 minutes, is this normal?"

**Coach Response**:
"The Command Line Tools download is large (several GB) and can take 15-30 minutes on slower connections. This is normal!

You can check progress by looking at the download percentage in the installer window. As long as the percentage is increasing, it's working.

If it's genuinely stuck (no progress for 10+ minutes):
1. Cancel the install (click Cancel in the window)
2. Retry: `xcode-select --install`
3. Sometimes Apple's servers are slow - retry in 30 minutes if persistent

But most commonly, it's just a large download. Let's give it a bit more time."

**User**: [10 minutes later] "It finished!"

**Coach**: "Great! Now we can continue with Homebrew..."

---

## Success Criteria Met

- ✓ User understood each step (explained in non-technical terms)
- ✓ Environment fully functional (all checks passed)
- ✓ User ready for next phase (Strava authentication)
- ✓ No context switch to external documentation
- ✓ Natural conversation flow maintained throughout
- ✓ Error recovery demonstrated (PATH issues, permissions, slow downloads)
