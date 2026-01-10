#!/usr/bin/env python3
"""
iMessage Self-Capture Script
Monitors messages to yourself and writes them to Obsidian inbox.

Part of the Second Brain system.
Configuration is read from config.yaml in the repo root.
"""

import sqlite3
import os
import re
import yaml
from datetime import datetime, timezone
from pathlib import Path

# =============================================================================
# Configuration Loading
# =============================================================================

def load_config():
    """
    Load configuration from config files.

    Loads config.yaml as base, then merges config.local.yaml on top if it exists.
    This allows config.yaml to be committed with placeholder values while
    config.local.yaml contains actual personal settings (and is gitignored).
    """
    script_dir = Path(__file__).parent
    base_config_path = script_dir.parent / "config.yaml"
    local_config_path = script_dir.parent / "config.local.yaml"

    if not base_config_path.exists():
        raise FileNotFoundError(f"Config file not found: {base_config_path}")

    # Load base config
    with open(base_config_path) as f:
        config = yaml.safe_load(f)

    # Merge local config if it exists
    if local_config_path.exists():
        with open(local_config_path) as f:
            local_config = yaml.safe_load(f)
            config = deep_merge(config, local_config)

    return config


def deep_merge(base, override):
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def expand_path(path_str):
    """Expand ~ and environment variables in path"""
    return os.path.expanduser(os.path.expandvars(path_str))


# Load configuration
CONFIG = load_config()

# =============================================================================
# Derived Configuration
# =============================================================================

CHAT_DB = os.path.expanduser("~/Library/Messages/chat.db")
VAULT_PATH = Path(expand_path(CONFIG['paths']['vault']))
INBOX_PATH = VAULT_PATH / CONFIG['paths']['inbox']
STATE_DIR = Path(expand_path(CONFIG['paths']['state_dir']))
STATE_FILE = STATE_DIR / "last_processed"
SELF_HANDLES = CONFIG['handles']

# Fix command pattern (case insensitive)
FIX_PATTERN = re.compile(r'^fix:\s*(.+)', re.IGNORECASE)

# Apple's epoch starts at 2001-01-01
APPLE_EPOCH_OFFSET = 978307200


# =============================================================================
# Utility Functions
# =============================================================================

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
    """Fetch messages to self newer than the given timestamp.

    Returns tuples of (rowid, date, text, is_from_me, guid, reply_to_guid).
    The guid is used to identify messages for reply-based fix targeting.
    """
    conn = sqlite3.connect(CHAT_DB)
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(SELF_HANDLES))

    if since_ts:
        query = f"""
            SELECT m.ROWID, m.date, m.text, m.is_from_me, m.guid, m.reply_to_guid
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
            SELECT m.ROWID, m.date, m.text, m.is_from_me, m.guid, m.reply_to_guid
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

    Returns tuple (is_fix, target_category) where target_category is one of
    the configured categories (people, projects, ideas, admin) or None if
    not recognized.

    Uses category names from config.yaml. The 'tasks' keyword is an alias
    for 'admin' (the original Second Brain category name).
    """
    match = FIX_PATTERN.match(text.strip())
    if not match:
        return False, None

    correction = match.group(1).lower().strip()

    # Get valid categories from config
    valid_categories = list(CONFIG.get('categories', {}).keys())

    # Map various phrasings to categories
    # Keys are the canonical category names from config
    category_keywords = {
        'people': ['people', 'person', 'contact'],
        'projects': ['projects', 'project'],
        'ideas': ['ideas', 'idea'],
        'admin': ['admin', 'tasks', 'task', 'todo', 'errand'],  # 'tasks' is alias for 'admin'
    }

    for category, keywords in category_keywords.items():
        # Only use categories that are in the config
        if category in valid_categories:
            for keyword in keywords:
                if keyword in correction:
                    return True, category

    # Fix command recognized but category unclear
    return True, None


def write_capture(apple_ts, text, guid):
    """Write a single capture to the inbox as a markdown file.

    Args:
        apple_ts: Apple nanosecond timestamp
        text: Message text content
        guid: iMessage GUID for reply-based fix targeting
    """
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
imessage_guid: {guid}
type: capture
processed: false
---

{text}
"""

    filepath = INBOX_PATH / filename
    filepath.write_text(content, encoding="utf-8")
    print(f"Created: {filename}")


def write_fix_command(apple_ts, text, target_category, reply_to_guid=None):
    """
    Write a fix command file that the processor will handle.

    Args:
        apple_ts: Apple nanosecond timestamp
        text: Message text content
        target_category: The category to reclassify to
        reply_to_guid: If this is a reply to a specific message, its GUID.
                       Used for targeted fixes instead of most-recent.

    The processor will:
    1. Find the target item (by reply_to_guid if present, else most recent)
    2. Reclassify it with the target category
    3. Move it to the new destination
    4. Update Inbox-Log.md
    """
    dt = apple_timestamp_to_datetime(apple_ts)

    timestamp_str = dt.strftime("%Y-%m-%dT%H%M%S")
    filename = f"{timestamp_str}-fix-command.md"

    iso_timestamp = dt.isoformat()

    # Build reply_to_guid line if present
    reply_line = f"reply_to_guid: {reply_to_guid}\n" if reply_to_guid else ""

    # If category was recognized
    if target_category:
        content = f"""---
captured: {iso_timestamp}
source: imessage
type: fix_command
target_category: {target_category}
{reply_line}processed: false
---

{text}
"""
        target_info = f"target: {target_category}"
        if reply_to_guid:
            target_info += f", reply to: {reply_to_guid[:8]}..."
        print(f"Created fix command: {filename} ({target_info})")
    else:
        # Category not recognized - create as needs_review
        content = f"""---
captured: {iso_timestamp}
source: imessage
type: fix_command
target_category: unknown
{reply_line}processed: false
---

{text}

Note: Could not determine target category from fix command.
Valid categories: people, projects, ideas, tasks
"""
        print(f"Created fix command: {filename} (category unclear)")

    filepath = INBOX_PATH / filename
    filepath.write_text(content, encoding="utf-8")


# =============================================================================
# Main
# =============================================================================

def main():
    # Ensure inbox exists
    INBOX_PATH.mkdir(parents=True, exist_ok=True)

    # Get last processed timestamp
    last_ts = get_last_processed()

    # Fetch new messages (now includes guid and reply_to_guid)
    messages = fetch_new_messages(last_ts)

    if not messages:
        print("No new messages.")
        return

    print(f"Processing {len(messages)} new message(s)...")

    newest_ts = last_ts
    for rowid, apple_ts, text, is_from_me, guid, reply_to_guid in messages:
        # Check if this is a fix command
        is_fix, target_category = parse_fix_command(text)

        if is_fix:
            # Pass reply_to_guid for targeted fix (may be None for non-reply)
            write_fix_command(apple_ts, text, target_category, reply_to_guid)
        else:
            # Pass guid so captures can be targeted by reply-based fixes
            write_capture(apple_ts, text, guid)

        if newest_ts is None or apple_ts > newest_ts:
            newest_ts = apple_ts

    # Save state
    if newest_ts:
        save_last_processed(newest_ts)

    print("Done.")


if __name__ == "__main__":
    main()
