#!/usr/bin/env python3
"""
Second Brain Upgrade Script
Handles updates when pulling new code from the repository.

Usage:
    python3 scripts/upgrade.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# =============================================================================
# Dependency Check
# =============================================================================

def check_dependencies():
    """Check required Python packages are installed."""
    try:
        __import__('yaml')
        return True
    except ImportError:
        print("Missing required package: pyyaml")
        print("\nInstall with: pip3 install pyyaml")
        print("Or run: python3 scripts/setup.py")
        return False

if not check_dependencies():
    sys.exit(1)

import yaml

# =============================================================================
# Constants
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
CONFIG_PATH = REPO_DIR / "config.yaml"
CONFIG_LOCAL_PATH = REPO_DIR / "config.local.yaml"
COMMANDS_DIR = REPO_DIR / "commands"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
CLAUDE_COMMANDS_DIR = Path.home() / ".claude" / "commands"

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

# =============================================================================
# Utility Functions
# =============================================================================

def print_header(text):
    """Print a section header."""
    print(f"\n{BOLD}{text}{RESET}")
    print("=" * 40)


def confirm(question, default=True):
    """Ask yes/no question."""
    suffix = "[Y/n]" if default else "[y/N]"
    response = input(f"{question} {suffix}: ").strip().lower()
    if not response:
        return default
    return response in ('y', 'yes')


def run_command(cmd, check=False):
    """Run a shell command."""
    try:
        result = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def load_yaml(path):
    """Load YAML file."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def get_all_keys(d, prefix=""):
    """Get all keys from nested dict as dot-notation paths."""
    keys = set()
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        keys.add(full_key)
        if isinstance(v, dict):
            keys.update(get_all_keys(v, full_key))
    return keys


def get_nested_value(d, key_path):
    """Get value from nested dict using dot notation."""
    keys = key_path.split(".")
    value = d
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return None
    return value


# =============================================================================
# Upgrade Functions
# =============================================================================

def show_version_info():
    """Show current and repo version."""
    config = load_yaml(CONFIG_PATH)
    version = config.get('version', '1.0.0')

    print(f"  Repository version: {BOLD}{version}{RESET}")
    return version


def find_new_config_options():
    """Find config options in config.yaml that aren't in config.local.yaml."""
    base_config = load_yaml(CONFIG_PATH)
    local_config = load_yaml(CONFIG_LOCAL_PATH)

    if not local_config:
        return []

    base_keys = get_all_keys(base_config)
    local_keys = get_all_keys(local_config)

    new_keys = []
    for key in sorted(base_keys - local_keys):
        # Skip keys that are just parent containers
        value = get_nested_value(base_config, key)
        if not isinstance(value, dict):
            default = value
            # Truncate long defaults
            if isinstance(default, str) and len(default) > 30:
                default = default[:27] + "..."
            new_keys.append((key, default))

    return new_keys


def regenerate_plists():
    """Regenerate plist files from config."""
    print("\n  Regenerating plists...")
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "generate_plists.py")],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"  {RED}Error:{RESET} {result.stderr}")
        return False

    print(f"  {GREEN}✓{RESET} Plists regenerated")
    return True


def reinstall_plists():
    """Copy plists to LaunchAgents and reload."""
    print("\n  Reinstalling launchd jobs...")

    plist_files = list(SCRIPT_DIR.glob("com.secondbrain.*.plist"))
    if not plist_files:
        print(f"  {YELLOW}!{RESET} No plist files found")
        return False

    # Create LaunchAgents directory if needed
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    for plist in plist_files:
        dest = LAUNCH_AGENTS_DIR / plist.name
        job_name = plist.stem

        # Unload if currently loaded (ignore errors)
        run_command(f"launchctl unload '{dest}' 2>/dev/null")

        # Copy new plist
        shutil.copy(plist, dest)

        # Load
        success, _ = run_command(f"launchctl load '{dest}'")
        if success:
            print(f"  {GREEN}✓{RESET} {job_name.replace('com.secondbrain.', '')}")
        else:
            print(f"  {YELLOW}!{RESET} {job_name.replace('com.secondbrain.', '')} (may need manual load)")

    return True


def update_claude_commands():
    """Copy commands to ~/.claude/commands/."""
    print("\n  Updating Claude commands...")

    if not COMMANDS_DIR.exists():
        print(f"  {YELLOW}!{RESET} No commands directory found")
        return False

    # Create Claude commands directory if needed
    CLAUDE_COMMANDS_DIR.mkdir(parents=True, exist_ok=True)

    command_files = list(COMMANDS_DIR.glob("*.md"))
    for cmd_file in command_files:
        dest = CLAUDE_COMMANDS_DIR / cmd_file.name
        shutil.copy(cmd_file, dest)
        print(f"  {GREEN}✓{RESET} {cmd_file.name}")

    return True


def run_diagnostics():
    """Run the diagnostic script."""
    print("\n  Running diagnostics...")

    diagnose_script = SCRIPT_DIR / "diagnose.py"
    if not diagnose_script.exists():
        print(f"  {YELLOW}!{RESET} diagnose.py not found")
        return False

    # Run diagnostics and show output
    result = subprocess.run(
        [sys.executable, str(diagnose_script)],
        text=True
    )

    return result.returncode == 0


# =============================================================================
# Main
# =============================================================================

def main():
    print_header("Second Brain Upgrade")

    # Version info
    version = show_version_info()

    # Check for new config options
    new_options = find_new_config_options()
    if new_options:
        print(f"\n  {YELLOW}New config options available:{RESET}")
        for key, default in new_options:
            print(f"    + {key} (default: {default})")
        print(f"\n  Add these to config.local.yaml if you want to customize them.")
    else:
        print(f"\n  {GREEN}✓{RESET} No new config options")

    # Confirm upgrade
    if not confirm("\nProceed with upgrade?"):
        print("\nUpgrade cancelled.")
        return

    # Regenerate plists
    print_header("Updating Components")

    if not regenerate_plists():
        print(f"\n{RED}Upgrade failed at plist generation.{RESET}")
        return

    # Reinstall plists
    if not reinstall_plists():
        print(f"\n{YELLOW}Warning: Some jobs may need manual reload.{RESET}")

    # Update Claude commands
    update_claude_commands()

    # Run diagnostics
    print_header("Diagnostics")
    run_diagnostics()

    # Done
    print_header("Upgrade Complete")
    print("""
Your Second Brain has been upgraded.

If you see any diagnostic failures:
  - Check the specific component
  - Re-run: python3 scripts/diagnose.py
  - See docs/installation.md for troubleshooting
""")


if __name__ == "__main__":
    main()
