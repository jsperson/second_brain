#!/usr/bin/env python3
"""
Generate launchd plist files from config.yaml

Run this script after modifying config.yaml to regenerate the plist files.
Then reinstall the plists using the installation guide.

Usage:
    python3 scripts/generate_plists.py
"""

import yaml
import os
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


# =============================================================================
# Plist Templates
# =============================================================================

IMESSAGE_CAPTURE_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jsperson.imessage-capture</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>{automator_app}</string>
    </array>

    <!-- Run every {capture_interval} seconds -->
    <key>StartInterval</key>
    <integer>{capture_interval}</integer>

    <!-- Also run immediately when loaded (at boot/login) -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Logging -->
    <key>StandardOutPath</key>
    <string>{state_dir}/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>{state_dir}/launchd-error.log</string>

    <!-- Restart if it crashes -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
</dict>
</plist>
'''

INBOX_PROCESSOR_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jsperson.inbox-processor</string>

    <key>ProgramArguments</key>
    <array>
        <string>{claude_executable}</string>
        <string>--print</string>
        <string>/process-inbox</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{repo_dir}</string>

    <!-- Run every {processor_interval} seconds -->
    <key>StartInterval</key>
    <integer>{processor_interval}</integer>

    <!-- Also run immediately when loaded -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Logging -->
    <key>StandardOutPath</key>
    <string>{state_dir}/inbox-processor.log</string>
    <key>StandardErrorPath</key>
    <string>{state_dir}/inbox-processor-error.log</string>

    <!-- Environment for Claude -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>{home}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{claude_dir}</string>
    </dict>
</dict>
</plist>
'''

DAILY_DIGEST_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jsperson.daily-digest</string>

    <key>ProgramArguments</key>
    <array>
        <string>{claude_executable}</string>
        <string>--print</string>
        <string>/daily-digest</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{repo_dir}</string>

    <!-- Run at {digest_hour}:{digest_minute:02d} every day -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{digest_hour}</integer>
        <key>Minute</key>
        <integer>{digest_minute}</integer>
    </dict>

    <!-- Logging -->
    <key>StandardOutPath</key>
    <string>{state_dir}/daily-digest.log</string>
    <key>StandardErrorPath</key>
    <string>{state_dir}/daily-digest-error.log</string>

    <!-- Environment for Claude -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>{home}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{claude_dir}</string>
    </dict>
</dict>
</plist>
'''

WEEKLY_REVIEW_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jsperson.weekly-review</string>

    <key>ProgramArguments</key>
    <array>
        <string>{claude_executable}</string>
        <string>--print</string>
        <string>/weekly-review</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{repo_dir}</string>

    <!-- Run at {review_hour}:{review_minute:02d} on weekday {review_weekday} (0=Sunday) -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>{review_weekday}</integer>
        <key>Hour</key>
        <integer>{review_hour}</integer>
        <key>Minute</key>
        <integer>{review_minute}</integer>
    </dict>

    <!-- Logging -->
    <key>StandardOutPath</key>
    <string>{state_dir}/weekly-review.log</string>
    <key>StandardErrorPath</key>
    <string>{state_dir}/weekly-review-error.log</string>

    <!-- Environment for Claude -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>{home}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{claude_dir}</string>
    </dict>
</dict>
</plist>
'''


# =============================================================================
# Main
# =============================================================================

def main():
    config = load_config()

    # Compute paths
    script_dir = Path(__file__).parent
    repo_dir = script_dir.parent
    state_dir = expand_path(config['paths']['state_dir'])
    automator_app = expand_path(config['paths']['automator_app'])
    claude_executable = expand_path(config['claude']['executable'])
    claude_dir = str(Path(claude_executable).parent)
    home = config['user']['home']

    # Common template values
    values = {
        'repo_dir': str(repo_dir),
        'state_dir': state_dir,
        'automator_app': automator_app,
        'claude_executable': claude_executable,
        'claude_dir': claude_dir,
        'home': home,
        'capture_interval': config['frequencies']['capture_interval'],
        'processor_interval': config['frequencies']['processor_interval'],
        'digest_hour': config['schedule']['daily_digest']['hour'],
        'digest_minute': config['schedule']['daily_digest']['minute'],
        'review_weekday': config['schedule']['weekly_review']['weekday'],
        'review_hour': config['schedule']['weekly_review']['hour'],
        'review_minute': config['schedule']['weekly_review']['minute'],
    }

    # Generate plists
    plists = [
        ('com.jsperson.imessage-capture.plist', IMESSAGE_CAPTURE_TEMPLATE),
        ('com.jsperson.inbox-processor.plist', INBOX_PROCESSOR_TEMPLATE),
        ('com.jsperson.daily-digest.plist', DAILY_DIGEST_TEMPLATE),
        ('com.jsperson.weekly-review.plist', WEEKLY_REVIEW_TEMPLATE),
    ]

    for filename, template in plists:
        content = template.format(**values)
        output_path = script_dir / filename
        output_path.write_text(content)
        print(f"Generated: {filename}")

    print(f"\nPlists generated in {script_dir}")
    print("\nTo install, run:")
    print("  cp scripts/*.plist ~/Library/LaunchAgents/")
    print("  launchctl load ~/Library/LaunchAgents/com.jsperson.*.plist")


if __name__ == "__main__":
    main()
