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
├── skills/                  # Claude Code skill definitions
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

When classifying captures, use these categories:

- **projects**: Multi-step work, ongoing tasks, things with next actions
  - Route to: `Projects/{ProjectName}/`
  - Create new project folders as needed

- **ideas**: Thoughts, insights, concepts to explore later
  - Route to: `Knowledge/Ideas/{title}.md`

- **people**: Information about a person, relationship updates, follow-ups
  - Route to: `Knowledge/People/{PersonName}.md`

- **tasks**: Simple errands, one-off items, things with due dates
  - Route to: `Tasks/{task-name}.md`

- **needs_review**: Unclear classification, low confidence
  - Leave in: `Inbox/` with `needs_review: true` in frontmatter

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
destination: Projects/Q1-Report/
classified_at: 2026-01-10T06:38:00+00:00
---
```

## Date Format

Use YYYYMMDD format for dates in content (e.g., `20260110`).
Use ISO 8601 for timestamps in frontmatter.

## Skills

The following skills are available:

- `/process-inbox` - Classify and route unprocessed captures
- `/daily-digest` - Generate daily summary of tasks, projects, people
- `/weekly-review` - Generate weekly review with patterns and insights

## Fix Mechanism

Users can correct misclassifications by sending "fix: category" via iMessage.

**Targeted fix (recommended):** Reply to the specific message you want to fix:
- Long-press or swipe on the message in iMessage
- Reply with `fix: tasks` (or another category)
- The system uses the `reply_to_guid` to find the matching capture by `imessage_guid`

**Fallback fix:** Send as a new message (fixes most recent):
- `fix: people` - Reclassify most recent item as people
- `fix: projects` - Reclassify as projects
- `fix: ideas` - Reclassify as ideas
- `fix: tasks` - Reclassify as tasks

## Development Notes

- Scripts run via launchd with Automator app wrappers (for Full Disk Access)
- The Automator app at `~/Applications/iMessageCapture.app` must have FDA granted
- State is tracked in `~/.imessage-capture/last_processed`
- Logs are written to `~/.imessage-capture/launchd.log` and `launchd-error.log`
