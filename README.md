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
| Projects | `Projects/{Name}/` | Multi-step work, ongoing tasks |
| Ideas | `Knowledge/Ideas/` | Thoughts, concepts to explore |
| People | `Knowledge/People/` | Contact info, relationship notes |
| Tasks | `Tasks/` | Simple errands, items with due dates |
| Unclear | `Inbox/` (stays) | Low confidence, needs human review |

## Components

### Scripts

- **imessage_capture.py** - Monitors Messages database, writes captures to Obsidian Inbox
- **Launchd plists** - Schedule automation jobs

### Claude Code Skills

- **/process-inbox** - Classify and route unprocessed captures
- **/daily-digest** - Generate daily summary (tasks, projects, people)
- **/weekly-review** - Generate weekly review with patterns

### Automation Schedule

| Job | Frequency | Purpose |
|-----|-----------|---------|
| iMessage Capture | Every 1 min | Capture new messages |
| Inbox Processor | Every 5 min | Classify and route |
| Daily Digest | 7:00 AM | Morning summary |
| Weekly Review | Sunday 4 PM | Week in review |

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
- Reply with `fix: tasks` (or the correct category)
- This targets that specific capture, even if it's not the most recent

**Option 2: Send a new message (fixes most recent)**
```
fix: should be tasks
```

The capture will be reclassified and moved to the correct destination.

### Manual Commands

Run skills directly in Claude Code:
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
├── scripts/
│   ├── imessage_capture.py
│   ├── com.jsperson.imessage-capture.plist
│   ├── com.jsperson.inbox-processor.plist
│   ├── com.jsperson.daily-digest.plist
│   └── com.jsperson.weekly-review.plist
├── skills/
│   ├── process-inbox.md
│   ├── daily-digest.md
│   └── weekly-review.md
└── docs/
    └── installation.md
```

## Obsidian Vault Structure

```
scott/
├── Inbox/                  # Captures land here
├── Inbox-Log.md           # Classification audit log
├── Projects/              # Active projects
├── Knowledge/
│   ├── Ideas/             # Ideas and concepts
│   └── People/            # Contact notes
├── Tasks/                 # Actionable items
└── ...
```

## Dependencies

- **macOS** - Uses Messages.app database and launchd
- **Claude Code** - For classification and skills
- **Obsidian** - Note storage (iCloud synced)
- **Automator** - App wrapper for Full Disk Access

## Installation

See [docs/installation.md](docs/installation.md) for detailed setup instructions.

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

## Credits

Based on the "Second Brain Build Guide" concept, adapted for:
- iMessage (instead of Slack)
- Obsidian (instead of Notion)
- Claude Code (instead of Zapier)
