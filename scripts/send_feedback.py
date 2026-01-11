#!/usr/bin/env python3
"""
Send Feedback Script
Sends iMessage notifications for captures that need manual classification.

Part of the Second Brain system.
Runs after /process-inbox to notify user of needs_review items.

IMPORTANT: Requires automation permissions. If messages fail to send:
1. Open System Preferences > Privacy & Security > Automation
2. Find Terminal (or the app running this script)
3. Enable "Messages" permission
4. You may also need to add to "Accessibility" in Privacy settings
"""

import os
import re
import subprocess
import yaml
from datetime import datetime
from pathlib import Path

# =============================================================================
# Configuration Loading
# =============================================================================

def load_config():
    """
    Load configuration from config files.

    Loads config.yaml as base, then merges config.local.yaml on top if it exists.
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

VAULT_PATH = Path(expand_path(CONFIG['paths']['vault']))
INBOX_PATH = VAULT_PATH / CONFIG['paths']['inbox']
SELF_HANDLES = CONFIG['handles']

# Use first handle as recipient for feedback messages
FEEDBACK_RECIPIENT = SELF_HANDLES[0] if SELF_HANDLES else None

# Feedback settings (with defaults)
FEEDBACK_CONFIG = CONFIG.get('feedback', {})
FEEDBACK_ENABLED = FEEDBACK_CONFIG.get('enabled', True)


# =============================================================================
# iMessage Sending
# =============================================================================

def send_imessage(recipient, message):
    """
    Send an iMessage via AppleScript/osascript.

    Args:
        recipient: Phone number or email to send to
        message: Text message to send

    Returns:
        True if sent successfully, False otherwise
    """
    # Escape special characters for AppleScript
    escaped_message = message.replace('\\', '\\\\').replace('"', '\\"')

    # Note: We activate Messages first and add delays to ensure it's ready
    applescript = f'''
    tell application "Messages"
        activate
        delay 1
        set targetService to id of 1st account whose service type = iMessage
        set targetBuddy to participant "{recipient}" of account id targetService
        send "{escaped_message}" to targetBuddy
    end tell
    '''

    try:
        subprocess.run(
            ['osascript', '-e', applescript],
            check=True,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error sending iMessage: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        print("Error sending iMessage: timeout expired")
        return False


# =============================================================================
# Frontmatter Parsing
# =============================================================================

def parse_frontmatter(content):
    """
    Parse YAML frontmatter from markdown content.

    Returns tuple of (frontmatter_dict, body_text).
    """
    if not content.startswith('---'):
        return {}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].strip()
        return frontmatter or {}, body
    except yaml.YAMLError:
        return {}, content


def update_frontmatter(filepath, updates):
    """
    Update frontmatter fields in a markdown file.

    Args:
        filepath: Path to the markdown file
        updates: Dictionary of fields to add/update
    """
    content = filepath.read_text(encoding='utf-8')
    frontmatter, body = parse_frontmatter(content)

    # Apply updates
    frontmatter.update(updates)

    # Rebuild content
    new_content = "---\n"
    new_content += yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    new_content += "---\n\n"
    new_content += body

    filepath.write_text(new_content, encoding='utf-8')


# =============================================================================
# Feedback Logic
# =============================================================================

def find_needs_review_items():
    """
    Find inbox items that need feedback.

    Returns list of (filepath, frontmatter, body) tuples for items with:
    - needs_review: true
    - No feedback_sent field (or feedback_sent: false)
    """
    items = []

    if not INBOX_PATH.exists():
        return items

    for filepath in INBOX_PATH.glob('*.md'):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)

        # Check if needs review and hasn't had feedback sent
        if frontmatter.get('needs_review') and not frontmatter.get('feedback_sent'):
            items.append((filepath, frontmatter, body))

    return items


def create_feedback_message(frontmatter, body):
    """
    Create the feedback message to send to user.

    Format: [SB:{guid}] Unclear: "{preview}". Reply: tasks/people/projects/ideas

    Args:
        frontmatter: Parsed frontmatter dict
        body: Body text of the capture

    Returns:
        Formatted feedback message string
    """
    guid = frontmatter.get('imessage_guid', 'UNKNOWN')

    # Get preview of body text (first 50 chars, single line)
    preview = body.replace('\n', ' ').strip()[:50]
    if len(body.strip()) > 50:
        preview += "..."

    message = f'[SB:{guid}] Unclear: "{preview}". Reply: tasks/people/projects/ideas'
    return message


def process_needs_review():
    """
    Process all needs_review items and send feedback messages.

    Returns count of feedback messages sent.
    """
    if not FEEDBACK_ENABLED:
        print("Feedback disabled in config.")
        return 0

    if not FEEDBACK_RECIPIENT:
        print("No feedback recipient configured (no handles).")
        return 0

    items = find_needs_review_items()

    if not items:
        print("No items need feedback.")
        return 0

    print(f"Found {len(items)} item(s) needing feedback...")
    sent_count = 0

    for filepath, frontmatter, body in items:
        message = create_feedback_message(frontmatter, body)
        print(f"Sending feedback for: {filepath.name}")

        if send_imessage(FEEDBACK_RECIPIENT, message):
            # Update frontmatter to mark feedback as sent
            update_frontmatter(filepath, {
                'feedback_sent': True,
                'feedback_sent_at': datetime.now().astimezone().isoformat()
            })
            sent_count += 1
            print(f"  Sent: {message[:60]}...")
        else:
            print(f"  Failed to send feedback for {filepath.name}")

    return sent_count


# =============================================================================
# Main
# =============================================================================

def main():
    print("Checking for items needing feedback...")
    sent = process_needs_review()
    print(f"Done. Sent {sent} feedback message(s).")


if __name__ == "__main__":
    main()
