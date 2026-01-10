# Second Brain Installation Guide

This guide walks through setting up the Second Brain system on a fresh Mac or migrating from an existing installation.

## Prerequisites

- **macOS** (tested on macOS 15+)
- **Claude Code** installed and authenticated
- **Obsidian** with iCloud sync enabled
- **Messages.app** signed in with your Apple ID

## Part 1: Obsidian Vault Setup

### 1.1 Create Required Folders

Create these folders in your Obsidian vault if they don't exist:

```bash
VAULT="/Users/jsperson/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott"

mkdir -p "$VAULT/Inbox"
mkdir -p "$VAULT/Tasks"
mkdir -p "$VAULT/Knowledge/Ideas"
mkdir -p "$VAULT/Knowledge/People"
```

### 1.2 Create Inbox Log

Create the classification log file:

```bash
cat > "$VAULT/Inbox-Log.md" << 'EOF'
# Inbox Log

Classification audit trail for Second Brain captures.

---

EOF
```

## Part 2: iMessage Capture Setup

### 2.1 Create the Automator App

The capture script needs Full Disk Access to read Messages database. We use an Automator app as a wrapper.

1. Open **Automator** (`/Applications/Automator.app`)
2. Create a new **Application**
3. Add a **Run Shell Script** action
4. Set shell to `/bin/bash`
5. Paste this script:
   ```bash
   /usr/bin/python3 /Users/jsperson/source/second_brain/scripts/imessage_capture.py
   ```
6. Save as `iMessageCapture.app` to `~/Applications/`

### 2.2 Grant Full Disk Access

1. Open **System Settings** → **Privacy & Security** → **Full Disk Access**
2. Click **+** and add `~/Applications/iMessageCapture.app`
3. Ensure it's toggled **on**

### 2.3 Install the Launchd Job

```bash
# Copy plist to LaunchAgents
cp ~/source/second_brain/scripts/com.jsperson.imessage-capture.plist ~/Library/LaunchAgents/

# Load the job
launchctl load ~/Library/LaunchAgents/com.jsperson.imessage-capture.plist

# Verify it's running
launchctl list | grep imessage-capture
```

### 2.4 Test Capture

1. Send yourself an iMessage (any text)
2. Wait 60 seconds
3. Check the Inbox folder for a new `.md` file
4. Check logs if issues: `tail ~/.imessage-capture/launchd-error.log`

## Part 3: Install Claude Code Skills

### 3.1 Copy Skills to Claude Config

```bash
# Create skills directory if needed
mkdir -p ~/.claude/skills

# Copy skills
cp ~/source/second_brain/skills/*.md ~/.claude/skills/
```

### 3.2 Verify Skills

Open Claude Code and try:
```
/process-inbox
```

It should recognize the skill and show the instructions.

## Part 4: Inbox Processor Setup (Optional)

The inbox processor runs Claude Code on a schedule to classify captures automatically.

**Note:** This requires Claude Code to be able to run non-interactively. Test first:

```bash
claude --print "/process-inbox"
```

If this works, proceed:

### 4.1 Install Processor Launchd Job

```bash
cp ~/source/second_brain/scripts/com.jsperson.inbox-processor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jsperson.inbox-processor.plist
```

### 4.2 Verify

Check logs after 5 minutes:
```bash
tail ~/.imessage-capture/inbox-processor.log
```

## Part 5: Digest Setup (Optional)

### 5.1 Daily Digest

Runs at 7:00 AM daily:

```bash
cp ~/source/second_brain/scripts/com.jsperson.daily-digest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jsperson.daily-digest.plist
```

### 5.2 Weekly Review

Runs Sunday at 4:00 PM:

```bash
cp ~/source/second_brain/scripts/com.jsperson.weekly-review.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jsperson.weekly-review.plist
```

## Part 6: Migration from claude_life

If you have an existing installation in `~/source/claude_life/scripts/`:

### 6.1 Stop Existing Jobs

```bash
launchctl unload ~/Library/LaunchAgents/com.jsperson.imessage-capture.plist
```

### 6.2 Update Automator App

1. Open `~/Applications/iMessageCapture.app` in Automator
2. Update the script path to:
   ```bash
   /usr/bin/python3 /Users/jsperson/source/second_brain/scripts/imessage_capture.py
   ```
3. Save

### 6.3 Install New Plist

```bash
cp ~/source/second_brain/scripts/com.jsperson.imessage-capture.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jsperson.imessage-capture.plist
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

1. Ensure message starts with `fix:` (case insensitive)
2. Check `Inbox-Log.md` has recent entries
3. Verify processor is running

## Uninstall

To remove Second Brain automation:

```bash
# Stop all jobs
launchctl unload ~/Library/LaunchAgents/com.jsperson.imessage-capture.plist
launchctl unload ~/Library/LaunchAgents/com.jsperson.inbox-processor.plist
launchctl unload ~/Library/LaunchAgents/com.jsperson.daily-digest.plist
launchctl unload ~/Library/LaunchAgents/com.jsperson.weekly-review.plist

# Remove plists
rm ~/Library/LaunchAgents/com.jsperson.*.plist

# Remove Automator app
rm -rf ~/Applications/iMessageCapture.app

# Remove state files (optional)
rm -rf ~/.imessage-capture/

# Remove skills (optional)
rm ~/.claude/skills/process-inbox.md
rm ~/.claude/skills/daily-digest.md
rm ~/.claude/skills/weekly-review.md
```

## Configuration Reference

### iMessage Handles

Edit `scripts/imessage_capture.py` to change monitored handles:

```python
SELF_HANDLES = ["+17038673475", "jsperson@gmail.com"]
```

### Schedule Intervals

Edit the plist files to change timing:

- **Capture**: `StartInterval` in seconds (default: 60)
- **Processor**: `StartInterval` in seconds (default: 300)
- **Daily Digest**: `StartCalendarInterval` Hour/Minute
- **Weekly Review**: `StartCalendarInterval` Weekday/Hour/Minute

### Obsidian Paths

Edit `CLAUDE.md` and skill files if your vault is in a different location.
