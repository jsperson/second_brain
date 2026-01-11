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

# Feedback message pattern - extracts original GUID from [SB:GUID] marker
FEEDBACK_PATTERN = re.compile(r'\[SB:([A-F0-9-]+)\]', re.IGNORECASE)

# Apple's epoch starts at 2001-01-01
APPLE_EPOCH_OFFSET = 978307200


# =============================================================================
# Category Helpers
# =============================================================================

def get_category_path(category):
    """Get destination path for a category."""
    cat_config = CONFIG.get('categories', {}).get(category, {})
    if isinstance(cat_config, str):
        return cat_config  # Legacy format: direct path string
    return cat_config.get('path', f"Second Brain/{category.title()}")


def get_category_keywords():
    """Build keyword-to-category mapping from config."""
    keyword_map = {}
    for category, cat_config in CONFIG.get('categories', {}).items():
        if isinstance(cat_config, dict):
            keywords = cat_config.get('keywords', [category])
        else:
            keywords = [category]  # Legacy format
        for keyword in keywords:
            keyword_map[keyword.lower()] = category
    return keyword_map


def get_category_list():
    """Get list of category names for feedback messages."""
    return list(CONFIG.get('categories', {}).keys())


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

    Returns tuples of (rowid, date, text, is_from_me, guid, thread_originator_guid).
    - guid: This message's unique identifier
    - thread_originator_guid: For inline replies, the GUID of the message being replied to
    """
    conn = sqlite3.connect(CHAT_DB)
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(SELF_HANDLES))

    if since_ts:
        query = f"""
            SELECT m.ROWID, m.date, m.text, m.is_from_me, m.guid, m.thread_originator_guid
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
            SELECT m.ROWID, m.date, m.text, m.is_from_me, m.guid, m.thread_originator_guid
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


def is_system_message(text):
    """
    Check if message is a system message (should be ignored).

    System messages start with [SB marker and include:
    - Feedback requests: [SB:GUID] Unclear: "..."
    - Report notifications: [SB] Daily digest ready: ...
    """
    return text and text.startswith('[SB')


def get_fix_target_guid(thread_originator_guid):
    """
    Determine the actual target GUID for a fix command.

    When a user replies to a message, the reply's thread_originator_guid
    points to the parent message. If the parent is a feedback message
    (contains [SB:GUID]), we need to extract and return the embedded
    original capture GUID instead.

    Args:
        thread_originator_guid: GUID of the message being replied to

    Returns:
        The GUID to use as the fix target:
        - If parent is a feedback message: the embedded original GUID
        - Otherwise: the thread_originator_guid itself (direct reply to capture)
    """
    if not thread_originator_guid:
        return None

    # Fetch parent message text from database
    # Note: Messages sent via AppleScript may have text in attributedBody instead of text
    conn = sqlite3.connect(CHAT_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT text, attributedBody FROM message WHERE guid = ?", (thread_originator_guid,))
    row = cursor.fetchone()
    conn.close()

    if row:
        # Try text column first
        if row[0]:
            match = FEEDBACK_PATTERN.search(row[0])
            if match:
                return match.group(1)

        # Fall back to attributedBody (used by AppleScript-sent messages)
        if row[1]:
            try:
                # attributedBody is a blob, decode and search for pattern
                decoded = row[1].decode('utf-8', errors='ignore')
                match = FEEDBACK_PATTERN.search(decoded)
                if match:
                    return match.group(1)
            except Exception:
                pass

    # Parent is not a feedback message - return it directly
    return thread_originator_guid


def parse_fix_command(text):
    """
    Check if text is a fix command using the legacy 'fix:' prefix.

    Returns tuple (is_fix, target_category) where target_category is one of
    the configured categories (people, projects, ideas, admin) or None if
    not recognized.

    This handles the 'fix: category' syntax for non-reply fix commands.
    """
    match = FIX_PATTERN.match(text.strip())
    if not match:
        return False, None

    correction = match.group(1)
    target_category = parse_category_from_text(correction)
    return True, target_category


def parse_category_from_text(text):
    """
    Parse natural language to extract target category from config.

    Handles various phrasings:
    - Direct category names and their configured keywords
    - Phrases: "move to X", "should be X", "this is an X", "put in X"

    Keywords are loaded from config.yaml categories section.
    Returns the canonical category name or None if not recognized.
    """
    normalized = text.lower().strip()

    # Build keyword map from config
    keyword_to_category = get_category_keywords()

    # Try phrase patterns first (more specific)
    phrase_patterns = [
        r'move\s+(?:it\s+)?to\s+(\w+)',       # "move to tasks", "move it to people"
        r'should\s+(?:be|go\s+to)\s+(\w+)',   # "should be projects", "should go to ideas"
        r'this\s+is\s+(?:an?\s+)?(\w+)',      # "this is a task", "this is an idea"
        r'put\s+(?:it\s+)?in\s+(\w+)',        # "put in admin", "put it in projects"
        r'file\s+(?:as|under)\s+(\w+)',       # "file as ideas", "file under projects"
    ]

    for pattern in phrase_patterns:
        match = re.search(pattern, normalized)
        if match:
            keyword = match.group(1)
            if keyword in keyword_to_category:
                return keyword_to_category[keyword]

    # Fall back to direct keyword match
    for keyword, category in keyword_to_category.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', normalized):
            return category

    return None


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


def write_fix_command(apple_ts, text, target_category, guid, reply_to_guid=None):
    """
    Write a fix command file that the processor will handle.

    Args:
        apple_ts: Apple nanosecond timestamp
        text: Message text content
        target_category: The category to reclassify to
        guid: This fix command's own iMessage GUID
        reply_to_guid: If this is an inline reply, the GUID of the message being
                       replied to (from thread_originator_guid). Used for targeted
                       fixes instead of most-recent.

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

    # Build reply_to_guid line if present (for targeted fixes)
    reply_line = f"reply_to_guid: {reply_to_guid}\n" if reply_to_guid else ""

    # If category was recognized
    if target_category:
        content = f"""---
captured: {iso_timestamp}
source: imessage
imessage_guid: {guid}
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
        categories = get_category_list()
        content = f"""---
captured: {iso_timestamp}
source: imessage
imessage_guid: {guid}
type: fix_command
target_category: unknown
{reply_line}processed: false
---

{text}

Note: Could not determine target category from text: "{text}"
Valid categories: {', '.join(categories)}
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
    for rowid, apple_ts, text, is_from_me, guid, thread_originator_guid in messages:
        # Skip system messages (feedback requests, report notifications)
        if is_system_message(text):
            print(f"Skipping system message: {text[:40]}...")
            if newest_ts is None or apple_ts > newest_ts:
                newest_ts = apple_ts
            continue

        # Check for reply first - any reply is a fix command
        if thread_originator_guid is not None:
            # Reply to a previous message - resolve actual target GUID
            # (handles replies to feedback messages by extracting embedded GUID)
            target_guid = get_fix_target_guid(thread_originator_guid)
            target_category = parse_category_from_text(text)
            write_fix_command(apple_ts, text, target_category, guid, target_guid)
        else:
            # Not a reply - check for legacy "fix:" prefix
            is_fix, target_category = parse_fix_command(text)
            if is_fix:
                write_fix_command(apple_ts, text, target_category, guid, None)
            else:
                # Regular capture
                write_capture(apple_ts, text, guid)

        if newest_ts is None or apple_ts > newest_ts:
            newest_ts = apple_ts

    # Save state
    if newest_ts:
        save_last_processed(newest_ts)

    print("Done.")


if __name__ == "__main__":
    main()
