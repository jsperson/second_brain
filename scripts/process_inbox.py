#!/usr/bin/env python3
"""
Inbox Processor Wrapper
Checks for unprocessed captures before invoking Claude, reducing LLM usage.

Flow:
1. Scan Inbox for files with processed: false
2. If none found, exit early (no Claude call)
3. If found, invoke Claude /process-inbox
4. After Claude finishes, send feedback for needs_review items

This replaces the direct Claude call in the launchd plist.
"""

import os
import subprocess
import yaml
from datetime import datetime, timezone
from pathlib import Path

# =============================================================================
# Configuration Loading
# =============================================================================

def load_config():
    """Load configuration from config files."""
    script_dir = Path(__file__).parent
    base_config_path = script_dir.parent / "config.yaml"
    local_config_path = script_dir.parent / "config.local.yaml"

    if not base_config_path.exists():
        raise FileNotFoundError(f"Config file not found: {base_config_path}")

    with open(base_config_path) as f:
        config = yaml.safe_load(f)

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

VAULT_PATH = Path(expand_path(CONFIG['paths']['vault']))
INBOX_PATH = VAULT_PATH / CONFIG['paths']['inbox']
CLAUDE_EXECUTABLE = expand_path(CONFIG['claude']['executable'])


# =============================================================================
# Frontmatter Parsing
# =============================================================================

def parse_frontmatter(content):
    """Parse YAML frontmatter from markdown content."""
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


# =============================================================================
# Inbox Checking
# =============================================================================

def find_unprocessed_items():
    """Find inbox items that need processing (processed: false)."""
    items = []

    if not INBOX_PATH.exists():
        return items

    for filepath in INBOX_PATH.glob('*.md'):
        try:
            content = filepath.read_text(encoding='utf-8')
            frontmatter, _ = parse_frontmatter(content)

            # Check if unprocessed
            if frontmatter.get('processed') == False:
                items.append(filepath)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

    return items


def find_needs_review_items():
    """Find items needing feedback (needs_review: true, no feedback_sent)."""
    items = []

    if not INBOX_PATH.exists():
        return items

    for filepath in INBOX_PATH.glob('*.md'):
        try:
            content = filepath.read_text(encoding='utf-8')
            frontmatter, body = parse_frontmatter(content)

            if frontmatter.get('needs_review') and not frontmatter.get('feedback_sent'):
                items.append((filepath, frontmatter, body))
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

    return items


# =============================================================================
# Claude Invocation
# =============================================================================

def run_claude_processor():
    """Invoke Claude to process inbox items."""
    print("Invoking Claude /process-inbox...")

    try:
        result = subprocess.run(
            [CLAUDE_EXECUTABLE, '--print', '--dangerously-skip-permissions', '/process-inbox'],
            cwd=str(VAULT_PATH),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"Claude stderr: {result.stderr}")

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("Error: Claude timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"Error running Claude: {e}")
        return False


# =============================================================================
# Feedback Sending (integrated from send_feedback.py)
# =============================================================================

def send_imessage(recipient, message):
    """Send an iMessage via AppleScript/osascript."""
    escaped_message = message.replace('\\', '\\\\').replace('"', '\\"')

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
            timeout=30
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error sending iMessage: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        print("Error sending iMessage: timeout expired")
        return False


def update_frontmatter(filepath, updates):
    """Update frontmatter fields in a markdown file."""
    content = filepath.read_text(encoding='utf-8')
    frontmatter, body = parse_frontmatter(content)

    frontmatter.update(updates)

    new_content = "---\n"
    new_content += yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    new_content += "---\n\n"
    new_content += body

    filepath.write_text(new_content, encoding='utf-8')


def send_feedback_messages():
    """Send feedback for needs_review items."""
    feedback_config = CONFIG.get('feedback', {})
    if not feedback_config.get('enabled', True):
        print("Feedback disabled in config.")
        return 0

    handles = CONFIG.get('handles', [])
    if not handles:
        print("No handles configured for feedback.")
        return 0

    recipient = handles[0]
    items = find_needs_review_items()

    if not items:
        print("No items need feedback.")
        return 0

    print(f"Sending feedback for {len(items)} item(s)...")
    sent_count = 0

    for filepath, frontmatter, body in items:
        guid = frontmatter.get('imessage_guid', 'UNKNOWN')
        preview = body.replace('\n', ' ').strip()[:50]
        if len(body.strip()) > 50:
            preview += "..."

        message = f'[SB:{guid}] Unclear: "{preview}". Reply: tasks/people/projects/ideas'
        print(f"  Sending feedback for: {filepath.name}")

        if send_imessage(recipient, message):
            update_frontmatter(filepath, {
                'feedback_sent': True,
                'feedback_sent_at': datetime.now(tz=timezone.utc).isoformat()
            })
            sent_count += 1
            print(f"    Sent: {message[:60]}...")
        else:
            print(f"    Failed to send feedback")

    return sent_count


# =============================================================================
# Main
# =============================================================================

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Inbox processor starting...")

    # Delay to ensure file writes are complete (especially with iCloud sync)
    import time
    print("Waiting 10 seconds for file sync to complete...")
    time.sleep(10)

    # Step 1: Check for unprocessed items
    unprocessed = find_unprocessed_items()

    if not unprocessed:
        print("No unprocessed items in Inbox. Skipping Claude.")
    else:
        print(f"Found {len(unprocessed)} unprocessed item(s):")
        for item in unprocessed:
            print(f"  - {item.name}")

        # Step 2: Run Claude to process
        run_claude_processor()

    # Step 3: Send feedback for needs_review items
    # (Run this even if no unprocessed items - there might be items from a previous run)
    sent = send_feedback_messages()

    print(f"Done. Sent {sent} feedback message(s).")


if __name__ == "__main__":
    main()
