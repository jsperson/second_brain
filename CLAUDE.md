# CLAUDE.md

This file provides guidance to Claude Code when working with the Second Brain system.

## Project Overview

This repository contains the Second Brain automation system - a personal knowledge management pipeline that:
1. Captures thoughts via iMessage to self
2. Classifies captures using Claude Code
3. Routes to appropriate Obsidian folders (Projects, Ideas, People, Tasks)
4. Provides daily/weekly digests

## Repository Structure

```
second_brain/
├── scripts/                 # Python scripts and launchd plists
│   ├── imessage_capture.py  # Captures iMessages to Obsidian Inbox
│   └── *.plist              # Launchd job definitions
├── commands/                # Claude Code command definitions
│   ├── process-inbox.md     # Classify and route inbox items
│   ├── daily-digest.md      # Generate daily summary
│   └── weekly-review.md     # Generate weekly review
└── docs/                    # Documentation
```

## Configuration

All paths, handles, and schedules are configured in:
- `config.yaml` - Base configuration (committed, with placeholder values)
- `config.local.yaml` - Personal overrides (gitignored, with actual values)

The scripts load both files, with local overrides taking precedence.

## Key Paths

Paths are defined in `config.yaml` under the `paths` section:

| Config Key | Purpose |
|------------|---------|
| `paths.vault` | Obsidian vault root |
| `paths.inbox` | Inbox folder (relative to vault) |
| `paths.projects` | Projects folder |
| `paths.ideas` | Ideas folder |
| `paths.people` | People folder |
| `paths.tasks` | Tasks folder |
| `paths.inbox_log` | Inbox log filename |
| `paths.state_dir` | State and logs directory |

## Classification Categories

Categories are mapped to destination folders in `config.yaml` under the `categories` section.
These are the original categories from Nate B Jones' Second Brain Build Guide:

| Category | Default Folder | Description |
|----------|----------------|-------------|
| `people` | `Second Brain/People/` | Info about a person, relationship updates |
| `projects` | `Second Brain/Projects/` | Multi-step work, ongoing tasks |
| `ideas` | `Second Brain/Ideas/` | Thoughts, insights, concepts |
| `admin` | `Second Brain/Admin/` | Simple errands, one-off items (alias: "tasks") |
| `needs_review` | `Second Brain/Inbox/` (stays) | Unclear classification, low confidence |

To customize where categories are routed, edit `config.local.yaml`:

```yaml
categories:
  people: "My Custom/People"
  projects: "My Custom/Projects"
  ideas: "My Custom/Ideas"
  admin: "My Custom/Tasks"
```

## Frontmatter Conventions

### Unprocessed capture (in Inbox):
```yaml
---
captured: 2026-01-10T06:33:00+00:00
source: imessage
imessage_guid: 4414CCC3-0A91-465F-A529-41620B9363CD
type: capture
processed: false
---
```

The `imessage_guid` field stores the unique iMessage identifier, enabling reply-based fix targeting.

### Processed capture (after classification):
```yaml
---
captured: 2026-01-10T06:33:00+00:00
source: imessage
imessage_guid: 4414CCC3-0A91-465F-A529-41620B9363CD
type: capture
processed: true
classified_as: projects
destination: Second Brain/Projects/Q1-Report/
classified_at: 2026-01-10T06:38:00+00:00
---
```

## Date Format

Use YYYYMMDD format for dates in content (e.g., `20260110`).
Use ISO 8601 for timestamps in frontmatter.

## Commands

The following commands are available:

- `/process-inbox` - Classify and route unprocessed captures
- `/daily-digest` - Generate daily summary of tasks, projects, people
- `/weekly-review` - Generate weekly review with patterns and insights

## Fix Mechanism

Users can correct misclassifications via iMessage in two ways:

**Reply-based fix (recommended):** Reply to the specific message you want to fix:
- Long-press or swipe on the message in iMessage
- Reply with the target category using natural language:
  - Direct: `tasks`, `people`, `projects`, `ideas`
  - Phrases: `move to tasks`, `should be people`, `this is an idea`
- No "fix:" prefix needed - any reply is automatically treated as a fix command
- The system uses the `reply_to_guid` to find the matching capture by `imessage_guid`

**Legacy fix (fixes most recent):** Send as a new message with "fix:" prefix:
- `fix: people` - Reclassify most recent item as people
- `fix: projects` - Reclassify as projects
- `fix: ideas` - Reclassify as ideas
- `fix: admin` or `fix: tasks` - Reclassify as admin (both work)

## Development Notes

- Scripts run via launchd with Automator app wrappers (for Full Disk Access)
- The Automator app at `~/Applications/iMessageCapture.app` must have FDA granted
- State is tracked in `~/.imessage-capture/last_processed`
- Logs are written to `~/.imessage-capture/launchd.log` and `launchd-error.log`
