#!/usr/bin/env python3
"""
iMessage Self-Capture Script
Monitors messages to yourself and writes them to Obsidian inbox.

Part of the Second Brain system.
"""

import sqlite3
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# Configuration
CHAT_DB = os.path.expanduser("~/Library/Messages/chat.db")
INBOX_PATH = Path("/Users/jsperson/Library/Mobile Documents/iCloud~md~obsidian/Documents/scott/Inbox")
STATE_DIR = Path(os.path.expanduser("~/.imessage-capture"))
STATE_FILE = STATE_DIR / "last_processed"
SELF_HANDLES = ["+17038673475", "jsperson@gmail.com"]

# Fix command pattern (case insensitive)
FIX_PATTERN = re.compile(r'^fix:\s*(.+)', re.IGNORECASE)

# Apple's epoch starts at 2001-01-01
APPLE_EPOCH_OFFSET = 978307200


def apple_timestamp_to_datetime(apple_ts):
    """Convert Apple's nanosecond timestamp to datetime."""
    if apple_ts is None or apple_ts == 0:
        return None
    # Apple timestamps are in nanoseconds since 2001-01-01
    unix_ts = (apple_ts / 1_000_000_000) + APPLE_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc)


def datetime_to_apple_timestamp(dt):
    """Convert datetime to Apple's nanosecond timestamp."""
    unix_ts = dt.timestamp()
    return int((unix_ts - APPLE_EPOCH_OFFSET) * 1_000_000_000)


def get_last_processed():
    """Read the last processed timestamp from state file."""
    if STATE_FILE.exists():
        return int(STATE_FILE.read_text().strip())
    return None


def save_last_processed(apple_ts):
    """Save the last processed timestamp to state file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(str(apple_ts))


def fetch_new_messages(since_ts=None):
    """Fetch messages to self newer than the given timestamp."""
    conn = sqlite3.connect(CHAT_DB)
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(SELF_HANDLES))

    if since_ts:
        query = f"""
            SELECT m.ROWID, m.date, m.text, m.is_from_me
            FROM message m
            JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            JOIN chat c ON cmj.chat_id = c.ROWID
            WHERE c.chat_identifier IN ({placeholders})
              AND m.date > ?
              AND m.text IS NOT NULL
              AND m.text != ''
            ORDER BY m.date ASC
        """
        cursor.execute(query, (*SELF_HANDLES, since_ts))
    else:
        # First run - just get messages from the last hour to avoid flooding
        one_hour_ago = datetime_to_apple_timestamp(
            datetime.now(tz=timezone.utc).replace(microsecond=0)
        ) - (3600 * 1_000_000_000)
        query = f"""
            SELECT m.ROWID, m.date, m.text, m.is_from_me
            FROM message m
            JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            JOIN chat c ON cmj.chat_id = c.ROWID
            WHERE c.chat_identifier IN ({placeholders})
              AND m.date > ?
              AND m.text IS NOT NULL
              AND m.text != ''
            ORDER BY m.date ASC
        """
        cursor.execute(query, (*SELF_HANDLES, one_hour_ago))

    messages = cursor.fetchall()
    conn.close()
    return messages


def sanitize_filename(text, max_length=50):
    """Create a safe filename snippet from message text."""
    # Take first line, strip whitespace
    snippet = text.split('\n')[0].strip()
    # Remove unsafe characters
    safe_chars = "".join(c if c.isalnum() or c in " -_" else "" for c in snippet)
    # Truncate and clean up
    safe_chars = safe_chars.strip()[:max_length].strip()
    return safe_chars if safe_chars else "capture"


def parse_fix_command(text):
    """
    Check if text is a fix command and extract the target category.

    Returns tuple (is_fix, target_category) where target_category is one of:
    'people', 'projects', 'ideas', 'tasks', or None if not recognized.
    """
    match = FIX_PATTERN.match(text.strip())
    if not match:
        return False, None

    correction = match.group(1).lower().strip()

    # Map various phrasings to categories
    category_keywords = {
        'people': ['people', 'person', 'contact'],
        'projects': ['projects', 'project'],
        'ideas': ['ideas', 'idea'],
        'tasks': ['tasks', 'task', 'admin', 'todo', 'errand'],
    }

    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in correction:
                return True, category

    # Fix command recognized but category unclear
    return True, None


def write_capture(apple_ts, text):
    """Write a single capture to the inbox as a markdown file."""
    dt = apple_timestamp_to_datetime(apple_ts)

    # Create filename: timestamp + snippet
    timestamp_str = dt.strftime("%Y-%m-%dT%H%M%S")
    snippet = sanitize_filename(text)
    filename = f"{timestamp_str}-{snippet}.md"

    # Create markdown content with frontmatter
    iso_timestamp = dt.isoformat()
    content = f"""---
captured: {iso_timestamp}
source: imessage
type: capture
processed: false
---

{text}
"""

    filepath = INBOX_PATH / filename
    filepath.write_text(content, encoding="utf-8")
    print(f"Created: {filename}")


def write_fix_command(apple_ts, text, target_category):
    """
    Write a fix command file that the processor will handle.

    The processor will:
    1. Find the most recent classified item
    2. Reclassify it with the target category
    3. Move it to the new destination
    4. Update Inbox-Log.md
    """
    dt = apple_timestamp_to_datetime(apple_ts)

    timestamp_str = dt.strftime("%Y-%m-%dT%H%M%S")
    filename = f"{timestamp_str}-fix-command.md"

    iso_timestamp = dt.isoformat()

    # If category was recognized
    if target_category:
        content = f"""---
captured: {iso_timestamp}
source: imessage
type: fix_command
target_category: {target_category}
processed: false
---

{text}
"""
        print(f"Created fix command: {filename} (target: {target_category})")
    else:
        # Category not recognized - create as needs_review
        content = f"""---
captured: {iso_timestamp}
source: imessage
type: fix_command
target_category: unknown
processed: false
---

{text}

Note: Could not determine target category from fix command.
Valid categories: people, projects, ideas, tasks
"""
        print(f"Created fix command: {filename} (category unclear)")

    filepath = INBOX_PATH / filename
    filepath.write_text(content, encoding="utf-8")


def main():
    # Ensure inbox exists
    INBOX_PATH.mkdir(parents=True, exist_ok=True)

    # Get last processed timestamp
    last_ts = get_last_processed()

    # Fetch new messages
    messages = fetch_new_messages(last_ts)

    if not messages:
        print("No new messages.")
        return

    print(f"Processing {len(messages)} new message(s)...")

    newest_ts = last_ts
    for rowid, apple_ts, text, is_from_me in messages:
        # Check if this is a fix command
        is_fix, target_category = parse_fix_command(text)

        if is_fix:
            write_fix_command(apple_ts, text, target_category)
        else:
            write_capture(apple_ts, text)

        if newest_ts is None or apple_ts > newest_ts:
            newest_ts = apple_ts

    # Save state
    if newest_ts:
        save_last_processed(newest_ts)

    print("Done.")


if __name__ == "__main__":
    main()
