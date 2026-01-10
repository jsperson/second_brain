# Process Inbox Skill

Process unprocessed captures from the Obsidian Inbox, classifying and routing them to appropriate destinations.

## Trigger

This skill is invoked by:
- Manual command: `/process-inbox`
- Scheduled launchd job: `claude "/process-inbox"`

## Paths

- **Inbox**: `/Users/jsperson/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Inbox/`
- **Projects**: `/Users/jsperson/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Projects/`
- **Ideas**: `/Users/jsperson/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Knowledge/Ideas/`
- **People**: `/Users/jsperson/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Knowledge/People/`
- **Tasks**: `/Users/jsperson/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Tasks/`
- **Inbox Log**: `/Users/jsperson/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Inbox-Log.md`

## Instructions

1. **Scan Inbox** for markdown files with `processed: false` in frontmatter

2. **For each unprocessed file**, read the content and classify it:

   **Categories:**
   - `projects` - Multi-step work, ongoing tasks, things with next actions
   - `ideas` - Thoughts, insights, concepts to explore later
   - `people` - Information about a person, relationship updates, follow-ups
   - `tasks` - Simple errands, one-off items, things with due dates
   - `needs_review` - Unclear, could be multiple categories

3. **Handle fix commands** (files with `type: fix_command` in frontmatter):
   - Read the `target_category` from frontmatter
   - Find the most recent entry in `Inbox-Log.md`
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

   **For tasks:**
   - Extract task name and due date if present
   - Move to `Tasks/{task-name}.md`

   **For needs_review:**
   - Leave in Inbox
   - Update frontmatter with `needs_review: true`

5. **Update frontmatter** of processed file:
   ```yaml
   processed: true
   classified_as: {category}
   destination: {destination_path}
   classified_at: {ISO timestamp}
   ```

6. **Append to Inbox-Log.md**:
   - If log doesn't exist, create it with header
   - Add entry under today's date section

   Log format:
   ```markdown
   ## YYYYMMDD

   | Time | Original | Filed To | Destination | Status |
   |------|----------|----------|-------------|--------|
   | HH:MM | First 50 chars... | category | relative/path | Filed |
   ```

7. **Report summary** when done:
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
- Project name: "Q1 Report"
- Destination: `Projects/Q1-Report/`

**Input:** "What if we added dark mode to the app?"
- Category: `ideas`
- Title: "Dark mode for app"
- Destination: `Knowledge/Ideas/Dark-mode-for-app.md`

**Input:** "Sarah mentioned she's looking for a new job"
- Category: `people`
- Person: "Sarah"
- Destination: `Knowledge/People/Sarah.md`

**Input:** "Renew car registration by Jan 15"
- Category: `tasks`
- Task: "Renew car registration"
- Due date: 2026-01-15
- Destination: `Tasks/Renew-car-registration.md`

**Input:** "remember the thing"
- Category: `needs_review`
- Stays in Inbox with `needs_review: true`
