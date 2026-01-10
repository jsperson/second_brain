---
description: "Classify and route unprocessed captures from Obsidian Inbox"
auto_run: true
---

Process unprocessed captures from the Obsidian Inbox, classifying and routing them to appropriate destinations.

## Configuration

Read `~/source/second_brain/config.yaml` (and `config.local.yaml` if it exists) to get paths. The vault is at `paths.vault`.

### Category Mapping
The `categories` section maps categories to destination folders:
- **people**: `{vault}/{categories.people}` - Info about a person
- **projects**: `{vault}/{categories.projects}` - Multi-step work
- **ideas**: `{vault}/{categories.ideas}` - Thoughts, concepts
- **admin**: `{vault}/{categories.admin}` - Simple errands (alias: "tasks")

## Instructions

1. **Scan Inbox** for markdown files with `processed: false` in frontmatter

2. **For each unprocessed file**, read the content and classify it:

   **Categories** (from Nate B Jones' Second Brain guide):
   - `people` - Information about a person, relationship updates, follow-ups
   - `projects` - Multi-step work, ongoing tasks, things with next actions
   - `ideas` - Thoughts, insights, concepts to explore later
   - `admin` - Simple errands, one-off items, things with due dates (alias: "tasks")
   - `needs_review` - Unclear, could be multiple categories

3. **Handle fix commands** (files with `type: fix_command` in frontmatter):
   - Read the `target_category` from frontmatter
   - **Find target capture** using one of two methods:
     - If `reply_to_guid` is present: Search Inbox and destination folders for a file with matching `imessage_guid` in frontmatter
     - If `reply_to_guid` is absent: Use the most recent entry in `Inbox-Log.md` (fallback)
   - Move that file to the new destination based on target_category
   - Update the log entry status to "Fixed"
   - Delete the fix command file after processing

4. **Route to destination** based on classification:

   **For projects:**
   - Extract project name from content
   - Create folder `Projects/{ProjectName}/` if it doesn't exist
   - Move file to that folder
   - Rename to descriptive name

   **For ideas:**
   - Extract idea title
   - Move to `Knowledge/Ideas/{title}.md`

   **For people:**
   - Extract person's name
   - Move to `Knowledge/People/{PersonName}.md`
   - If file exists, append to it instead of overwriting

   **For admin (or tasks):**
   - Extract task name and due date if present
   - Move to `{categories.admin}/{task-name}.md` (default: `Tasks/`)

   **For needs_review:**
   - Leave in Inbox
   - Update frontmatter with `needs_review: true`

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

- **Look for keywords**: "project", "task", "idea", "remember to call [name]"
- **Projects** have multiple steps or ongoing work
- **Tasks** are single actions, often with dates
- **People** mentions a specific person with context about them
- **Ideas** are conceptual, things to think about later

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
