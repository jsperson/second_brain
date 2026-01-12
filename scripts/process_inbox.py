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
INBOX_LOG_PATH = VAULT_PATH / CONFIG['paths']['inbox_log']
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
# Claude Classification
# =============================================================================

def build_classification_prompt(text_content):
    """Build classification prompt dynamically from config categories."""
    categories = CONFIG.get('categories', {})

    category_list = "\n".join([
        f"- {name}: {cat.get('description', name)}"
        for name, cat in categories.items()
    ])

    category_names = ", ".join(categories.keys())

    return f"""Classify this text for a personal knowledge management system.

TEXT:
{text_content}

CATEGORIES:
{category_list}

Return ONLY valid JSON (no markdown, no explanation):

{{
  "category": "<one of: {category_names}, or needs_review>",
  "confidence": 0.85,
  "name": "Descriptive title for the item",
  "tags": ["relevant", "tags"]
}}

RULES:
- Confidence 0.9-1.0: Very clear classification
- Confidence 0.7-0.89: Fairly confident
- Confidence below 0.6: Use "needs_review"
- Extract dates mentioned and include in name if relevant
- For needs_review, add "reason" field explaining uncertainty
- Return ONLY the JSON object, no other text"""


def classify_with_claude(text_content):
    """Send text to Claude, get classification JSON back."""
    prompt = build_classification_prompt(text_content)

    try:
        result = subprocess.run(
            [CLAUDE_EXECUTABLE, '--print', prompt],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            print(f"Claude error: {result.stderr}")
            return None

        return parse_classification_response(result.stdout)

    except subprocess.TimeoutExpired:
        print("Error: Claude classification timed out")
        return None
    except Exception as e:
        print(f"Error calling Claude: {e}")
        return None


def parse_classification_response(response_text):
    """Parse JSON classification from Claude's response."""
    import json

    # Clean up response - remove markdown code blocks if present
    text = response_text.strip()
    if text.startswith('```'):
        # Remove markdown code fence
        lines = text.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Error parsing Claude response as JSON: {e}")
        print(f"Response was: {response_text[:200]}...")
        return None


# =============================================================================
# File Operations
# =============================================================================

def get_category_path(category):
    """Get destination path for a category from config."""
    cat_config = CONFIG.get('categories', {}).get(category, {})
    if isinstance(cat_config, str):
        return cat_config
    return cat_config.get('path', f"Second Brain/{category.title()}")


def sanitize_filename(name):
    """Create a safe filename from a name."""
    # Remove unsafe characters
    safe = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with hyphens
    safe = re.sub(r'\s+', '-', safe)
    # Limit length
    return safe[:50].strip('-')


def get_destination_path(category, name):
    """Get full destination path for a classified item."""
    category_path = get_category_path(category)
    safe_name = sanitize_filename(name)
    return VAULT_PATH / category_path / f"{safe_name}.md"


def write_file_with_frontmatter(filepath, frontmatter, body):
    """Write a markdown file with YAML frontmatter."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    content = "---\n"
    content += yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    content += "---\n\n"
    content += body

    filepath.write_text(content, encoding='utf-8')


def file_to_destination(filepath, frontmatter, body, classification):
    """Move file to destination, update frontmatter, archive original."""
    import shutil

    category = classification['category']
    name = classification.get('name', 'Untitled')
    dest_path = get_destination_path(category, name)

    # Check if destination exists, add number if so
    if dest_path.exists():
        base = dest_path.stem
        suffix = 1
        while dest_path.exists():
            dest_path = dest_path.with_name(f"{base}-{suffix}.md")
            suffix += 1

    # Update frontmatter with classification results (for archival copy)
    frontmatter.update({
        'processed': True,
        'classified_as': category,
        'destination': str(dest_path.relative_to(VAULT_PATH)),
        'classified_at': datetime.now().astimezone().isoformat(),
        'confidence': classification.get('confidence', 0.0),
        'name': name,
    })

    # Add tags if present
    if classification.get('tags'):
        frontmatter['tags'] = classification['tags']

    # Write clean body to destination (no frontmatter clutter)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(body.strip() + '\n', encoding='utf-8')
    print(f"  Filed to: {dest_path.relative_to(VAULT_PATH)}")

    # Archive original with full metadata to Processed folder
    processed_dir = INBOX_PATH / 'Processed'
    processed_dir.mkdir(parents=True, exist_ok=True)
    archive_path = processed_dir / filepath.name

    # Update the original file's frontmatter before archiving
    write_file_with_frontmatter(filepath, frontmatter, body)
    shutil.move(str(filepath), str(archive_path))

    return dest_path


def mark_needs_review(filepath, frontmatter, classification):
    """Mark a file as needing review (stays in Inbox)."""
    frontmatter.update({
        'needs_review': True,
        'classified_at': datetime.now().astimezone().isoformat(),
        'confidence': classification.get('confidence', 0.0),
    })

    if classification.get('reason'):
        frontmatter['review_reason'] = classification['reason']

    content = filepath.read_text(encoding='utf-8')
    _, body = parse_frontmatter(content)
    write_file_with_frontmatter(filepath, frontmatter, body)
    print(f"  Marked for review: {filepath.name}")


def process_capture(filepath):
    """Process a single capture file."""
    content = filepath.read_text(encoding='utf-8')
    frontmatter, body = parse_frontmatter(content)

    if not body.strip():
        print(f"  Skipping empty file: {filepath.name}")
        return None

    print(f"  Classifying: {filepath.name}")

    # Get classification from Claude
    classification = classify_with_claude(body)

    if not classification:
        print(f"  Classification failed for: {filepath.name}")
        return None

    category = classification.get('category', 'needs_review')
    confidence = classification.get('confidence', 0.0)

    print(f"    → {category} (confidence: {confidence:.2f})")

    if category == 'needs_review' or confidence < 0.6:
        classification['category'] = 'needs_review'
        mark_needs_review(filepath, frontmatter, classification)
        return {'category': 'needs_review', 'path': filepath}
    else:
        dest_path = file_to_destination(filepath, frontmatter, body, classification)
        return {
            'category': category,
            'path': dest_path,
            'name': classification.get('name', ''),
            'confidence': confidence,
            'original': body[:50]
        }


# =============================================================================
# Fix Command Processing
# =============================================================================

def find_file_by_guid(guid):
    """Find a file by its imessage_guid in Inbox or destination folders."""
    if not guid:
        return None

    # Search in Inbox
    for filepath in INBOX_PATH.glob('*.md'):
        try:
            content = filepath.read_text(encoding='utf-8')
            frontmatter, _ = parse_frontmatter(content)
            if frontmatter.get('imessage_guid') == guid:
                return filepath
        except:
            pass

    # Search in Inbox/Processed
    processed_dir = INBOX_PATH / 'Processed'
    if processed_dir.exists():
        for filepath in processed_dir.glob('*.md'):
            try:
                content = filepath.read_text(encoding='utf-8')
                frontmatter, _ = parse_frontmatter(content)
                if frontmatter.get('imessage_guid') == guid:
                    return filepath
            except:
                pass

    # Search in destination folders
    for category in CONFIG.get('categories', {}).keys():
        category_path = VAULT_PATH / get_category_path(category)
        if category_path.exists():
            for filepath in category_path.rglob('*.md'):
                try:
                    content = filepath.read_text(encoding='utf-8')
                    frontmatter, _ = parse_frontmatter(content)
                    if frontmatter.get('imessage_guid') == guid:
                        return filepath
                except:
                    pass

    return None


def process_fix_command(filepath):
    """Handle a fix command file - reclassify the target capture."""
    content = filepath.read_text(encoding='utf-8')
    frontmatter, body = parse_frontmatter(content)

    target_guid = frontmatter.get('reply_to_guid')
    target_category = frontmatter.get('target_category')

    print(f"  Processing fix command: {filepath.name}")
    print(f"    Target GUID: {target_guid}")
    print(f"    Target category: {target_category}")

    if not target_category or target_category == 'unknown':
        print(f"    Error: No valid target category specified")
        return None

    # Find target file
    target_file = find_file_by_guid(target_guid)

    if not target_file:
        print(f"    Error: Target file not found for GUID: {target_guid}")
        return None

    print(f"    Found target: {target_file.name}")

    # Read target file
    target_content = target_file.read_text(encoding='utf-8')
    target_frontmatter, target_body = parse_frontmatter(target_content)

    # Create classification result for the new category
    classification = {
        'category': target_category,
        'confidence': 1.0,  # User-specified, so full confidence
        'name': target_frontmatter.get('name', target_body.split('\n')[0][:50]),
        'tags': target_frontmatter.get('tags', [])
    }

    # Move to new destination
    dest_path = file_to_destination(target_file, target_frontmatter, target_body, classification)

    # Delete the fix command file
    filepath.unlink()
    print(f"    Fix command processed, deleted: {filepath.name}")

    return {
        'category': target_category,
        'path': dest_path,
        'fixed': True,
        'original_path': target_file
    }


# =============================================================================
# Inbox Log
# =============================================================================

def append_to_inbox_log(result):
    """Append an entry to Inbox-Log.md, inserting into correct date section."""
    if not result:
        return

    today = datetime.now().strftime('%Y%m%d')
    time_str = datetime.now().strftime('%H:%M')

    # Determine log entry values
    category = result.get('category', 'unknown')
    original = result.get('original', '')[:50].replace('|', '/')
    confidence = result.get('confidence', 0.0)

    if result.get('fixed'):
        status = 'Fixed'
        dest_str = f"[[{result['path'].relative_to(VAULT_PATH)}]]"
    elif category == 'needs_review':
        status = 'Needs Review'
        dest_str = '(kept in Inbox)'
    else:
        status = 'Filed'
        dest_str = f"[[{result['path'].relative_to(VAULT_PATH)}]]"

    # Build log entry (match existing format without Confidence column)
    entry = f"| {time_str} | {original}... | {category} | {dest_str} | {status} |"

    # Read or create log file
    if INBOX_LOG_PATH.exists():
        log_content = INBOX_LOG_PATH.read_text(encoding='utf-8')
    else:
        log_content = "# Inbox Processing Log\n\n"

    today_header = f"## {today}"

    if today_header not in log_content:
        # Insert today's section at the beginning (after title)
        lines = log_content.split('\n')
        new_lines = []
        inserted = False

        for i, line in enumerate(lines):
            new_lines.append(line)
            # Insert after the title line
            if line.startswith('# ') and not inserted:
                new_lines.append('')
                new_lines.append(today_header)
                new_lines.append('')
                new_lines.append('| Time | Original | Filed To | Destination | Status |')
                new_lines.append('|------|----------|----------|-------------|--------|')
                new_lines.append(entry)
                inserted = True

        log_content = '\n'.join(new_lines)
    else:
        # Find the today section and insert entry after the table header
        lines = log_content.split('\n')
        new_lines = []
        found_section = False
        inserted = False

        for i, line in enumerate(lines):
            new_lines.append(line)

            if line.strip() == today_header:
                found_section = True
                continue

            # Insert after the separator row (|-----|...)
            if found_section and not inserted and line.startswith('|') and '---' in line:
                new_lines.append(entry)
                inserted = True

        log_content = '\n'.join(new_lines)

    INBOX_LOG_PATH.write_text(log_content, encoding='utf-8')


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
        print("No unprocessed items in Inbox. Skipping processing.")
    else:
        print(f"Found {len(unprocessed)} unprocessed item(s):")
        for item in unprocessed:
            print(f"  - {item.name}")

        # Track results for summary
        results = {
            'filed': [],
            'needs_review': [],
            'fixed': [],
            'failed': []
        }

        # Step 2: Process each file
        for filepath in unprocessed:
            try:
                content = filepath.read_text(encoding='utf-8')
                frontmatter, _ = parse_frontmatter(content)
                file_type = frontmatter.get('type', 'capture')

                if file_type == 'fix_command':
                    # Handle fix commands
                    result = process_fix_command(filepath)
                    if result:
                        results['fixed'].append(result)
                        append_to_inbox_log(result)
                else:
                    # Handle regular captures
                    result = process_capture(filepath)
                    if result:
                        if result.get('category') == 'needs_review':
                            results['needs_review'].append(result)
                        else:
                            results['filed'].append(result)
                        append_to_inbox_log(result)
                    else:
                        results['failed'].append({'path': filepath})

            except Exception as e:
                print(f"  Error processing {filepath.name}: {e}")
                results['failed'].append({'path': filepath, 'error': str(e)})

        # Step 3: Print summary
        print("\n--- Processing Summary ---")
        print(f"  Filed: {len(results['filed'])}")
        for r in results['filed']:
            print(f"    - {r.get('name', 'Unknown')} → {r.get('category', 'unknown')}")
        print(f"  Fixed: {len(results['fixed'])}")
        print(f"  Needs Review: {len(results['needs_review'])}")
        print(f"  Failed: {len(results['failed'])}")

        # Step 4: Send confirmation messages for successfully filed items
        if results['filed']:
            handles = CONFIG.get('handles', [])
            feedback_config = CONFIG.get('feedback', {})
            if handles and feedback_config.get('confirmations', True):
                recipient = handles[0]
                confirmed = 0
                for result in results['filed']:
                    name = result.get('name', 'Unknown')[:40]
                    category = result.get('category', 'unknown')
                    message = f'[SB] ✓ {category}: "{name}"'
                    if send_imessage(recipient, message):
                        confirmed += 1
                        print(f"  Confirmed: {message}")
                print(f"Sent {confirmed} confirmation message(s).")

    # Step 5: Send feedback for needs_review items
    # (Run this even if no unprocessed items - there might be items from a previous run)
    sent = send_feedback_messages()

    print(f"Done. Sent {sent} feedback message(s).")


if __name__ == "__main__":
    main()
