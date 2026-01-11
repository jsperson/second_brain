#!/usr/bin/env python3
"""
Inbox Processor Wrapper
Checks for unprocessed captures before invoking Claude, reducing LLM usage.

Flow:
1. Scan Inbox for files with processed: false
2. If none found, exit early (no Claude call)
3. If found, invoke Claude /process-inbox
4. After Claude finishes, strip metadata from newly-filed notes
5. Send feedback for needs_review items

This replaces the direct Claude call in the launchd plist.
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

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
VAULT_PATH = Path(expand_path(CONFIG['paths']['vault']))
INBOX_PATH = VAULT_PATH / CONFIG['paths']['inbox']
INBOX_LOG_PATH = VAULT_PATH / "Inbox-Log.md"
CLAUDE_EXECUTABLE = expand_path(CONFIG['claude']['executable'])
PROCESS_INBOX_COMMAND = REPO_DIR / '.claude' / 'commands' / 'process-inbox.md'


# =============================================================================
# Category Helpers
# =============================================================================

def get_category_list():
    """Get list of category names for feedback messages."""
    return list(CONFIG.get('categories', {}).keys())


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
# Metadata Stripping
# =============================================================================

def get_log_line_count():
    """Get the current line count of the Inbox-Log.md file."""
    if not INBOX_LOG_PATH.exists():
        return 0
    return len(INBOX_LOG_PATH.read_text(encoding='utf-8').splitlines())


def parse_new_log_entries(start_line):
    """
    Parse new log entries added after start_line.

    Returns list of destination paths for successfully filed items.
    """
    if not INBOX_LOG_PATH.exists():
        return []

    lines = INBOX_LOG_PATH.read_text(encoding='utf-8').splitlines()
    new_lines = lines[start_line:]

    destinations = []

    # Pattern to match table rows (handles both old and new formats):
    # Old: | Time | Original | Filed To | Destination | Status |
    # New: | Time | Original | Filed To | Destination | Confidence | Status |
    # We want rows where Status is Filed, Fixed, or Reclassified
    # and Destination is a real path (not containing "(kept)")
    table_pattern = re.compile(
        r'^\|\s*[\d:]+\s*\|'              # Time column
        r'[^|]+\|'                         # Original column
        r'[^|]+\|'                         # Filed To column
        r'\s*([^|]+?)\s*\|'                # Destination column (capture group)
        r'(?:\s*[\d.]+\s*\|)?'             # Confidence column (optional)
        r'\s*(Filed|Fixed|Reclassified)\s*\|'  # Status column
    )

    for line in new_lines:
        match = table_pattern.match(line)
        if match:
            destination = match.group(1).strip()
            # Skip entries that stayed in inbox
            if '(kept)' not in destination and destination:
                # Handle Obsidian wiki-link format [[path]]
                if destination.startswith('[[') and destination.endswith(']]'):
                    destination = destination[2:-2]
                destinations.append(destination)

    return destinations


def strip_file_metadata(filepath):
    """
    Strip processing metadata from a filed note, keeping only the content.

    Removes all frontmatter, leaving just the note body.
    """
    if not filepath.exists():
        print(f"  Warning: File not found: {filepath}")
        return False

    try:
        content = filepath.read_text(encoding='utf-8')
        _, body = parse_frontmatter(content)

        # Write back just the body content
        filepath.write_text(body.strip() + '\n', encoding='utf-8')
        return True
    except Exception as e:
        print(f"  Error stripping metadata from {filepath}: {e}")
        return False


def strip_metadata_from_new_files(start_line):
    """
    Strip metadata from files that were just moved by Claude.

    Uses the Inbox-Log.md to identify which files were processed.
    """
    destinations = parse_new_log_entries(start_line)

    if not destinations:
        print("No new files to strip metadata from.")
        return 0

    print(f"Stripping metadata from {len(destinations)} file(s)...")
    stripped_count = 0

    for dest in destinations:
        # Destination is relative to vault, e.g. "Second Brain/People/Name.md"
        filepath = VAULT_PATH.parent / dest  # Go up from "Second Brain" to get full path

        # Actually the vault path is already the full path to the vault
        # and destinations start with "Second Brain/", so we need to handle this
        # Let's check if destination starts with vault folder name
        vault_name = VAULT_PATH.name  # "Second Brain"
        if dest.startswith(vault_name + "/"):
            # Strip the vault name prefix
            relative_path = dest[len(vault_name) + 1:]
            filepath = VAULT_PATH / relative_path
        else:
            filepath = VAULT_PATH / dest

        print(f"  Stripping: {filepath.name}")
        if strip_file_metadata(filepath):
            stripped_count += 1

    return stripped_count


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
    print("Invoking Claude process-inbox...")

    # Read command file directly instead of relying on skill discovery
    if not PROCESS_INBOX_COMMAND.exists():
        print(f"Error: Command file not found: {PROCESS_INBOX_COMMAND}")
        return False

    command_content = PROCESS_INBOX_COMMAND.read_text()

    try:
        result = subprocess.run(
            [CLAUDE_EXECUTABLE, '--print', '--dangerously-skip-permissions', command_content],
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

        categories = '/'.join(get_category_list())
        message = f'[SB:{guid}] Unclear: "{preview}". Reply: {categories}'
        print(f"  Sending feedback for: {filepath.name}")

        if send_imessage(recipient, message):
            update_frontmatter(filepath, {
                'feedback_sent': True,
                'feedback_sent_at': datetime.now().astimezone().isoformat()
            })
            sent_count += 1
            print(f"    Sent: {message[:60]}...")
        else:
            print(f"    Failed to send feedback")

    return sent_count


def send_confirmation_messages(start_line):
    """Send confirmation iMessages for successfully filed items."""
    feedback_config = CONFIG.get('feedback', {})
    if not feedback_config.get('confirmations', True):
        print("Confirmations disabled in config.")
        return 0

    handles = CONFIG.get('handles', [])
    if not handles:
        print("No handles configured for confirmations.")
        return 0

    recipient = handles[0]

    # Parse new log entries to find successfully filed items
    if not INBOX_LOG_PATH.exists():
        return 0

    lines = INBOX_LOG_PATH.read_text(encoding='utf-8').splitlines()
    new_lines = lines[start_line:]

    # Pattern to match table rows (handles both old and new formats):
    # Old: | Time | Original | Filed To | Destination | Status |
    # New: | Time | Original | Filed To | Destination | Confidence | Status |
    table_pattern = re.compile(
        r'^\|\s*([\d:]+)\s*\|'         # Time column (capture)
        r'\s*([^|]+?)\s*\|'             # Original column (capture)
        r'\s*([^|]+?)\s*\|'             # Filed To column (capture)
        r'\s*([^|]+?)\s*\|'             # Destination column (capture)
        r'(?:\s*[\d.]+\s*\|)?'          # Confidence column (optional, non-capture)
        r'\s*(Filed)\s*\|'              # Status column - only "Filed" status
    )

    sent_count = 0

    for line in new_lines:
        match = table_pattern.match(line)
        if match:
            original = match.group(2).strip()
            category = match.group(3).strip()

            # Send confirmation message
            # Format: [SB] ✓ category: "preview..."
            preview = original[:40]
            if len(original) > 40:
                preview += "..."
            message = f'[SB] ✓ {category}: "{preview}"'

            if send_imessage(recipient, message):
                sent_count += 1
                print(f"  Confirmed: {message}")
            else:
                print(f"  Failed to send confirmation for: {original[:30]}...")

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

        # Record log position before Claude runs
        log_start_line = get_log_line_count()

        # Step 2: Run Claude to process
        run_claude_processor()

        # Step 3: Send confirmation messages for successfully filed items
        confirmed = send_confirmation_messages(log_start_line)
        print(f"Sent {confirmed} confirmation message(s).")

    # Step 4: Send feedback for needs_review items
    # (Run this even if no unprocessed items - there might be items from a previous run)
    sent = send_feedback_messages()

    print(f"Done. Sent {sent} feedback message(s).")


if __name__ == "__main__":
    main()
