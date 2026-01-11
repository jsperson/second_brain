# Second Brain

A personal knowledge management system that captures thoughts via iMessage and automatically classifies and routes them to Obsidian.

## Overview

This system implements the "Second Brain" workflow:

1. **Capture** - Send a thought to yourself via iMessage (5 seconds)
2. **Classify** - Claude Code automatically categorizes the capture
3. **Route** - Content is filed to the appropriate Obsidian folder
4. **Review** - Daily and weekly digests surface what matters

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   iMessage  │────▶│   Inbox/    │────▶│ Claude Code │────▶│ Destination │
│  to self    │     │  (capture)  │     │ (classify)  │     │   folder    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                                                            │
       │                    ┌─────────────┐                        │
       └───────────────────▶│  fix: xxx   │────────────────────────┘
           (corrections)    └─────────────┘
```

## Categories

| Category | Destination | Description |
|----------|-------------|-------------|
| Projects | `Second Brain/Projects/` | Multi-step work, ongoing tasks |
| Ideas | `Second Brain/Ideas/` | Thoughts, concepts to explore |
| People | `Second Brain/People/` | Contact info, relationship notes |
| Admin | `Second Brain/Admin/` | Simple errands, items with due dates |
| Unclear | `Second Brain/Inbox/` (stays) | Low confidence, needs human review |

## Components

### Scripts

- **imessage_capture.py** - Monitors Messages database, writes captures to Obsidian Inbox
- **process_inbox.py** - Wrapper that checks for work before invoking Claude (reduces LLM usage)
- **send_feedback.py** - Sends iMessage feedback for unclear captures (integrated into process_inbox.py)
- **generate_plists.py** - Generates launchd plists from config

### Claude Code Commands

- **/process-inbox** - Classify and route unprocessed captures
- **/daily-digest** - Generate daily summary (tasks, projects, people)
- **/weekly-review** - Generate weekly review with patterns

### Automation Schedule

| Job | Frequency | Purpose |
|-----|-----------|---------|
| iMessage Capture | Every 1 min | Capture new messages |
| Inbox Processor | Every 5 min | Check for work, classify, send feedback |
| Daily Digest | 7:00 AM | Morning summary |
| Weekly Review | Sunday 4 PM | Week in review |

**Note:** The Inbox Processor only invokes Claude when there are unprocessed items, minimizing LLM usage during idle periods.

## Quick Start

### Capture a Thought

Just send yourself an iMessage:
```
Project: finish the Q1 report by Friday
```

The system will:
1. Capture it to `Inbox/`
2. Classify it as "projects"
3. Route to `Projects/Q1-Report/`
4. Log to `Inbox-Log.md`

### Correct a Mistake

If the AI misclassifies, you can fix it via iMessage:

**Option 1: Reply to the message (recommended)**
- Long-press or swipe on the misclassified message in iMessage
- Reply with the target category using natural language:
  - Direct: `tasks`, `people`, `projects`, `ideas`
  - Phrases: `move to tasks`, `should be people`, `this is an idea`
- No "fix:" prefix needed - any reply is automatically a fix command
- This targets that specific capture, even if it's not the most recent

**Option 2: Send a new message (fixes most recent)**
```
fix: tasks
```

The capture will be reclassified and moved to the correct destination.

### Unclear Captures (Feedback Loop)

When the AI can't confidently classify a capture, it marks it as `needs_review` and sends you an iMessage:

```
[SB:ABC123...] Unclear: "remember the thing". Reply: tasks/people/projects/ideas
```

Simply reply with the category (e.g., "tasks") and the capture will be classified and routed.

### Manual Commands

Run commands directly in Claude Code:
```
/process-inbox    # Process pending captures now
/daily-digest     # Generate daily summary now
/weekly-review    # Generate weekly review now
```

## File Structure

```
second_brain/
├── CLAUDE.md              # Claude Code instructions
├── README.md              # This file
├── config.yaml            # Base configuration
├── config.local.yaml      # Your personal overrides (gitignored)
├── scripts/
│   ├── setup.py                  # Interactive setup wizard
│   ├── diagnose.py               # Diagnostic tool
│   ├── uninstall.py              # Clean uninstall (preserves data)
│   ├── imessage_capture.py       # Capture iMessages to Inbox
│   ├── process_inbox.py          # Wrapper: check for work, invoke Claude, send feedback
│   ├── send_feedback.py          # Send iMessage for unclear items
│   ├── generate_plists.py        # Generate launchd plists from config
│   └── *.plist                   # Generated launchd job definitions
├── commands/
│   ├── process-inbox.md
│   ├── daily-digest.md
│   └── weekly-review.md
└── docs/
    └── installation.md
```

## Obsidian Vault Structure

```
YourVault/
└── Second Brain/
    ├── Inbox/              # Captures land here
    │   └── Processed/      # Archived after classification
    ├── Inbox-Log.md        # Classification audit log
    ├── Projects/           # Multi-step work
    ├── People/             # Contact notes
    ├── Ideas/              # Thoughts and concepts
    └── Admin/              # Simple tasks and errands
```

## Dependencies

- **macOS** - Uses Messages.app database and launchd
- **Claude Code** - For classification and commands
- **Obsidian** - Note storage (iCloud synced)
- **Automator** - App wrapper for Full Disk Access

## Installation

### Quick Start (Recommended)

Run the interactive setup wizard:

```bash
cd ~/source/second_brain
python3 scripts/setup.py
```

The wizard will guide you through:
- Detecting your Obsidian vault and Claude installation
- Configuring your iMessage handles
- Creating required folders
- Installing automation jobs
- Setting up permissions

### Diagnostics

If something isn't working, run the diagnostic tool:

```bash
python3 scripts/diagnose.py
```

### Manual Installation

For step-by-step manual installation, see [docs/installation.md](docs/installation.md).

### Uninstall

To remove automation (preserves your notes and data):

```bash
python3 scripts/uninstall.py
```

## Configuration

All settings are in `config.yaml`, with personal overrides in `config.local.yaml` (gitignored).

### Setup

1. Copy values you need to override into `config.local.yaml`
2. Edit `config.local.yaml` with your personal settings
3. Run `python3 scripts/generate_plists.py` to regenerate launchd plists

### Configurable Settings

| Setting | Config Key | Description |
|---------|------------|-------------|
| **Handles** | `handles` | Phone numbers and emails to monitor |
| **Vault Path** | `paths.vault` | Your Obsidian vault location |
| **Capture Interval** | `frequencies.capture_interval` | Seconds between iMessage checks |
| **Processor Interval** | `frequencies.processor_interval` | Seconds between classifications |
| **Daily Digest Time** | `schedule.daily_digest.hour/minute` | When to generate daily digest |
| **Weekly Review Time** | `schedule.weekly_review.*` | When to generate weekly review |

### Example config.local.yaml

```yaml
handles:
  - "+15551234567"
  - "your.email@icloud.com"

paths:
  vault: "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/MyVault"

user:
  username: "yourusername"
  home: "/Users/yourusername"
```

### Customizing Folder Structure

By default, all folders live under `Second Brain/` in your vault. To use a different structure, override the paths in `config.local.yaml`.

**Change the master folder:**

```yaml
paths:
  inbox: "My PKM/Inbox"
  inbox_log: "My PKM/Inbox-Log.md"

categories:
  people: "My PKM/People"
  projects: "My PKM/Projects"
  ideas: "My PKM/Ideas"
  admin: "My PKM/Tasks"
```

**Use existing Obsidian folders:**

```yaml
categories:
  people: "Contacts"
  projects: "Work/Projects"
  ideas: "Notes/Ideas"
  admin: "Tasks"
```

**Map to PARA method folders:**

```yaml
categories:
  projects: "1 - Projects"
  ideas: "3 - Resources/Ideas"
  people: "3 - Resources/People"
  admin: "2 - Areas/Tasks"
```

After changing folder paths:
1. Create the folders in your vault if they don't exist
2. Run `python3 scripts/generate_plists.py` to regenerate plists
3. Reload the capture job: `launchctl unload ~/Library/LaunchAgents/com.secondbrain.imessage-capture.plist && launchctl load ~/Library/LaunchAgents/com.secondbrain.imessage-capture.plist`

## Troubleshooting

### Captures not appearing

1. Check launchd job is running:
   ```bash
   launchctl list | grep imessage-capture
   ```

2. Check logs:
   ```bash
   tail ~/.imessage-capture/launchd-error.log
   ```

3. Verify Full Disk Access for Automator app

### Classification not running

1. Verify Claude Code is installed and authenticated
2. Check inbox processor logs
3. Ensure Inbox has files with `processed: false`

### Fix command not working

1. Ensure message starts with `fix:` (case insensitive)
2. For reply-based fixes: verify the original message was captured (has `imessage_guid` in frontmatter)
3. For fallback fixes: check there's a recent entry in Inbox-Log.md to fix
4. Verify capture script detected the fix command (check logs)

### Claude Code login keeps expiring

If scheduled jobs (daily-digest, inbox-processor) fail because Claude Code authentication expires:

1. **Set up a long-lived token** (requires Claude Pro or Max subscription):
   ```bash
   claude setup-token
   ```
   This generates a persistent OAuth token stored in `~/.claude/.credentials.json`.

2. **Verify it works**:
   ```bash
   claude --print "test"
   ```

3. **Ensure no API key override**: If you have `ANTHROPIC_API_KEY` set in your environment, Claude Code will use API billing instead of your subscription. Remove it if you want to use your subscription.

The long-lived token will keep your scheduled jobs authenticated without requiring browser-based re-login.

## Credits

Based on the [Second Brain Build Guide](https://natesnewsletter.substack.com/p/bridge-the-ai-implementation-gap) by [Nate B. Jones](https://natesnewsletter.substack.com/).

Adapted for a local-first approach:
- iMessage (instead of Slack)
- Obsidian (instead of Notion)
- Claude Code (instead of Zapier + Claude API)
