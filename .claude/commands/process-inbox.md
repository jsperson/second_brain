---
description: "Classify and route unprocessed captures from Obsidian Inbox"
auto_run: true
---

Process unprocessed captures from the Obsidian Inbox, classifying and routing them to appropriate destinations.

## Configuration

Read `~/source/second_brain/config.yaml` (and `config.local.yaml` if it exists) to get paths and categories.

### Category Mapping
Categories are defined in `config.yaml` under the `categories` section. Each category has:
- `path`: Destination folder relative to vault
- `keywords`: Words that trigger this category in fix commands (used by Python scripts)
- `description`: What belongs in this category (use this for classification decisions)

**Read the config file** to get the current list of categories and their descriptions.
Users can add custom categories or override defaults in `config.local.yaml`.

## Instructions

1. **Scan Inbox** for markdown files with `processed: false` in frontmatter

2. **For each unprocessed file**, read the content and classify it:

   **Categories**: Read from `config.yaml` categories section.
   - For each category, use its `description` field to determine what belongs there
   - If the content clearly matches a category's description, use that category
   - If unclear which category fits, classify as `needs_review`
   - `needs_review` - Special status for unclear items (not a destination category)

3. **Handle fix commands** (files with `type: fix_command` in frontmatter):

   Fix commands are created two ways:
   - **Reply to message**: Any iMessage reply to a previous capture (natural language: "tasks", "move to people", etc.)
   - **Legacy prefix**: Non-reply message starting with "fix:" (e.g., "fix: projects")

   Processing steps:
   - Read the `target_category` from frontmatter
   - **Find target capture** using one of two methods:
     - If `reply_to_guid` is present: Search Inbox and destination folders for a file with matching `imessage_guid` in frontmatter
     - If `reply_to_guid` is absent: Use the most recent entry in `Inbox-Log.md` (fallback)
   - Move that file to the new destination based on target_category
   - Update the log entry status to "Fixed"
   - Delete the fix command file after processing

4. **Route to destination** based on classification:

   Get the destination path from `categories.{category}.path` in config.

   **General routing:**
   - Extract a descriptive name from the content
   - Move to `{category_path}/{descriptive-name}.md`
   - For categories that group items (like projects), create a subfolder if appropriate

   **Special handling for people:**
   - If file exists for that person, append to it instead of overwriting

   **For needs_review:**
   - Leave in Inbox (do not move or archive)
   - Update frontmatter with `needs_review: true`
   - Do NOT set `feedback_sent` (the feedback script handles this)
   - After processing, `send_feedback.py` will send an iMessage asking for clarification
   - User can reply to the feedback message to classify the capture

5. **Archive original file**:
   - Create `Inbox/Processed/` folder if it doesn't exist
   - Move the original capture file from `Inbox/` to `Inbox/Processed/`
   - This keeps the Inbox clean while preserving the original for reference
   - Skip this step for `needs_review` items (they stay in Inbox)

6. **Update frontmatter** of processed file:
   ```yaml
   processed: true
   classified_as: {category}
   destination: {destination_path}
   classified_at: {ISO timestamp}
   ```

7. **Append to Inbox-Log.md**:
   - If log doesn't exist, create it with header
   - Add entry under today's date section

   Log format:
   ```markdown
   ## YYYYMMDD

   | Time | Original | Filed To | Destination | Status |
   |------|----------|----------|-------------|--------|
   | HH:MM | First 50 chars... | category | relative/path | Filed |
   ```

8. **Report summary** when done:
   - Number of items processed
   - Number filed to each category
   - Any items left in needs_review

## Classification Guidelines

- **Read config.yaml** to get current categories and their descriptions
- **Match content to descriptions**: Use each category's `description` field to decide where content belongs
- **Look for explicit signals**: Keywords, names, dates, action items
- **When uncertain**: Use `needs_review` rather than guessing

## Examples

**Input:** "Project: finish the Q1 report by Friday"
- Category: `projects`
- Destination: `Projects/Q1-Report/`

**Input:** "What if we added dark mode to the app?"
- Category: `ideas`
- Destination: `Knowledge/Ideas/Dark-mode-for-app.md`

**Input:** "Sarah mentioned she's looking for a new job"
- Category: `people`
- Destination: `Knowledge/People/Sarah.md`

**Input:** "Renew car registration by Jan 15"
- Category: `admin`
- Destination: `Tasks/Renew-car-registration.md`

**Input:** "remember the thing"
- Category: `needs_review`
- Stays in Inbox with `needs_review: true`

$ARGUMENTS
