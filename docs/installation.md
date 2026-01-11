# Second Brain Installation Guide

This guide walks through setting up the Second Brain system on a fresh Mac or migrating from an existing installation.

## Prerequisites

- **macOS** (tested on macOS 15+)
- **Claude Code** installed and authenticated
- **Obsidian** with iCloud sync enabled
- **Messages.app** signed in with your Apple ID
- **Python 3** with PyYAML (`pip3 install pyyaml`)

## Part 0: Configuration

Before installing, create your local configuration file.

### 0.1 Create config.local.yaml

```bash
cd ~/source/second_brain
cp config.yaml config.local.yaml
```

### 0.2 Edit config.local.yaml

Update these values with your personal settings:

```yaml
# Your iMessage handles
handles:
  - "+15551234567"           # Your phone number
  - "your.email@icloud.com"  # Your Apple ID email

# Your Obsidian vault path
paths:
  vault: "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/YOUR_VAULT"

# Your macOS username
user:
  username: "yourusername"
  home: "/Users/yourusername"
```

You can also customize:
- `frequencies.capture_interval` - How often to check for messages (seconds)
- `frequencies.processor_interval` - How often to classify (seconds)
- `schedule.daily_digest.hour/minute` - Daily digest time
- `schedule.weekly_review.*` - Weekly review time

### 0.3 Generate Plists

After editing config.local.yaml, regenerate the launchd plists:

```bash
python3 scripts/generate_plists.py
```

## Part 1: Obsidian Vault Setup

### 1.1 Create Required Folders

Create these folders in your Obsidian vault if they don't exist:

```bash
# Set VAULT to match your paths.vault from config.local.yaml
VAULT="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/YOUR_VAULT"

mkdir -p "$VAULT/Second Brain/Inbox/Processed"
mkdir -p "$VAULT/Second Brain/Projects"
mkdir -p "$VAULT/Second Brain/People"
mkdir -p "$VAULT/Second Brain/Ideas"
mkdir -p "$VAULT/Second Brain/Admin"
```

### 1.2 Create Inbox Log (Optional)

The processor will create this automatically, but you can create it manually:

```bash
touch "$VAULT/Second Brain/Inbox-Log.md"
```

## Part 2: iMessage Capture Setup

### 2.1 Create the Automator App

The capture script needs Full Disk Access to read Messages database. We use an Automator app as a wrapper.

1. Open **Automator** (`/Applications/Automator.app`)
2. Create a new **Application**
3. Add a **Run Shell Script** action
4. Set shell to `/bin/bash`
5. Paste this script (replace YOUR_USERNAME with your macOS username):
   ```bash
   /usr/bin/python3 /Users/YOUR_USERNAME/source/second_brain/scripts/imessage_capture.py
   ```
6. Save as `iMessageCapture.app` to `~/Applications/`

### 2.2 Grant Full Disk Access

1. Open **System Settings** → **Privacy & Security** → **Full Disk Access**
2. Click **+** and add `~/Applications/iMessageCapture.app`
3. Ensure it's toggled **on**

### 2.3 Install the Launchd Job

```bash
# Copy plist to LaunchAgents
cp ~/source/second_brain/scripts/com.secondbrain.imessage-capture.plist ~/Library/LaunchAgents/

# Load the job
launchctl load ~/Library/LaunchAgents/com.secondbrain.imessage-capture.plist

# Verify it's running
launchctl list | grep imessage-capture
```

### 2.4 Test Capture

1. Send yourself an iMessage (any text)
2. Wait 60 seconds
3. Check the Inbox folder for a new `.md` file
4. Check logs if issues: `tail ~/.imessage-capture/launchd-error.log`

## Part 3: Install Claude Code Commands

### 3.1 Copy Commands to Claude Config

```bash
# Copy commands
cp ~/source/second_brain/commands/*.md ~/.claude/commands/
```

### 3.2 Verify Commands

Open Claude Code and try:
```
/process-inbox
```

It should recognize the command and show the instructions.

## Part 4: Inbox Processor Setup (Optional)

The inbox processor runs on a schedule to classify captures automatically. It uses a Python wrapper (`process_inbox.py`) that:
- Checks for unprocessed items before invoking Claude (reduces LLM usage)
- Sends feedback iMessages for unclear captures
- Only calls Claude when there's actual work to do

**Note:** This requires Claude Code to be able to run non-interactively. Test first:

```bash
claude --print "/process-inbox"
```

If this works, proceed:

### 4.1 Grant Messages Automation Permission

The feedback feature sends iMessages via AppleScript. The first time it runs, macOS may prompt for permission. If messages fail to send:

1. Open **System Settings** → **Privacy & Security** → **Automation**
2. Find **Terminal** (or the app running the script)
3. Enable the **Messages** checkbox

### 4.2 Install Processor Launchd Job

```bash
cp ~/source/second_brain/scripts/com.secondbrain.inbox-processor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.secondbrain.inbox-processor.plist
```

### 4.3 Verify

Check logs after 5 minutes:
```bash
tail ~/.imessage-capture/inbox-processor.log
```

If the inbox is empty, you should see:
```
No unprocessed items in Inbox. Skipping Claude.
```

## Part 5: Digest Setup (Optional)

### 5.1 Daily Digest

Runs at 7:00 AM daily:

```bash
cp ~/source/second_brain/scripts/com.secondbrain.daily-digest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.secondbrain.daily-digest.plist
```

### 5.2 Weekly Review

Runs Sunday at 4:00 PM:

```bash
cp ~/source/second_brain/scripts/com.secondbrain.weekly-review.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.secondbrain.weekly-review.plist
```

## Part 6: Migration from claude_life

If you have an existing installation in `~/source/claude_life/scripts/`:

### 6.1 Stop Existing Jobs

```bash
launchctl unload ~/Library/LaunchAgents/com.secondbrain.imessage-capture.plist
```

### 6.2 Update Automator App

1. Open `~/Applications/iMessageCapture.app` in Automator
2. Update the script path to (replace YOUR_USERNAME):
   ```bash
   /usr/bin/python3 /Users/YOUR_USERNAME/source/second_brain/scripts/imessage_capture.py
   ```
3. Save

### 6.3 Install New Plist

```bash
cp ~/source/second_brain/scripts/com.secondbrain.imessage-capture.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.secondbrain.imessage-capture.plist
```

### 6.4 Verify Migration

```bash
# Check job is running
launchctl list | grep imessage-capture

# Send test message and verify capture
tail -f ~/.imessage-capture/launchd.log
```

## Troubleshooting

### "authorization denied" Error

Full Disk Access not granted to the Automator app. See Part 2.2.

### Captures Not Appearing

1. Check job is running: `launchctl list | grep imessage-capture`
2. Check logs: `tail ~/.imessage-capture/launchd-error.log`
3. Verify Inbox path exists and is writable
4. Ensure Messages.app shows the conversation to yourself

### Classification Not Running

1. Verify Claude Code is installed: `which claude`
2. Test manually: `claude --print "/process-inbox"`
3. Check processor logs: `tail ~/.imessage-capture/inbox-processor-error.log`

### Fix Command Not Working

1. **Reply-based fix (recommended):** Reply to the original message with the category
   - Any reply is automatically treated as a fix command
   - Use natural language: `tasks`, `move to people`, `should be ideas`
2. **Legacy fix:** Send new message starting with `fix:` (fixes most recent)
3. Check `Inbox-Log.md` has recent entries
4. Verify processor is running

### Feedback Messages Not Sending

1. Check **System Settings** → **Privacy & Security** → **Automation**
2. Ensure Terminal has permission to control Messages
3. Test manually: `osascript -e 'tell application "Messages" to activate'`
4. Check logs: `tail ~/.imessage-capture/inbox-processor-error.log`

## Uninstall

To remove Second Brain automation:

```bash
# Stop all jobs
launchctl unload ~/Library/LaunchAgents/com.secondbrain.imessage-capture.plist
launchctl unload ~/Library/LaunchAgents/com.secondbrain.inbox-processor.plist
launchctl unload ~/Library/LaunchAgents/com.secondbrain.daily-digest.plist
launchctl unload ~/Library/LaunchAgents/com.secondbrain.weekly-review.plist

# Remove plists
rm ~/Library/LaunchAgents/com.secondbrain.*.plist

# Remove Automator app
rm -rf ~/Applications/iMessageCapture.app

# Remove state files (optional)
rm -rf ~/.imessage-capture/

# Remove commands (optional)
rm ~/.claude/commands/process-inbox.md
rm ~/.claude/commands/daily-digest.md
rm ~/.claude/commands/weekly-review.md
```

## Configuration Reference

All configuration is done in `config.yaml` (defaults) or `config.local.yaml` (your overrides).

### iMessage Handles

Edit `config.local.yaml`:

```yaml
handles:
  - "+15551234567"
  - "your.email@icloud.com"
```

### Schedule Intervals

Edit `config.local.yaml` and regenerate plists:

```yaml
frequencies:
  capture_interval: 60      # seconds between iMessage checks
  processor_interval: 300   # seconds between classifications

schedule:
  daily_digest:
    hour: 7
    minute: 0
  weekly_review:
    weekday: 0    # 0=Sunday
    hour: 16
    minute: 0
```

Then regenerate and reinstall:
```bash
python3 scripts/generate_plists.py
cp scripts/*.plist ~/Library/LaunchAgents/
# Reload any running jobs
```

### Claude Executable Path

If `which claude` returns a different path than `~/.npm-global/bin/claude`, add to `config.local.yaml`:

```yaml
claude:
  executable: "/path/to/your/claude"
```
