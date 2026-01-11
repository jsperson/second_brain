#!/usr/bin/env python3
"""
Second Brain Uninstall Script
Removes automation components while preserving user data.

Usage:
    python3 scripts/uninstall.py
"""

import os
import shutil
import subprocess
from pathlib import Path

# =============================================================================
# Constants
# =============================================================================

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
STATE_DIR = Path.home() / ".imessage-capture"
AUTOMATOR_APP = Path.home() / "Applications" / "iMessageCapture.app"

PLIST_FILES = [
    "com.secondbrain.imessage-capture.plist",
    "com.secondbrain.inbox-processor.plist",
    "com.secondbrain.daily-digest.plist",
    "com.secondbrain.weekly-review.plist",
]

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


def confirm(question, default=False):
    """Ask yes/no question."""
    suffix = "[y/N]" if not default else "[Y/n]"
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
        return result.returncode == 0
    except:
        return False


# =============================================================================
# Uninstall Functions
# =============================================================================

def unload_launchd_jobs():
    """Unload all launchd jobs."""
    print("\nUnloading launchd jobs...")
    unloaded = 0

    for plist_name in PLIST_FILES:
        plist_path = LAUNCH_AGENTS_DIR / plist_name
        if plist_path.exists():
            job_name = plist_name.replace(".plist", "")
            if run_command(f"launchctl unload '{plist_path}'"):
                print(f"  {GREEN}✓{RESET} Unloaded: {job_name}")
                unloaded += 1
            else:
                print(f"  {YELLOW}!{RESET} Could not unload: {job_name} (may not be running)")

    return unloaded


def remove_plist_files():
    """Remove plist files from LaunchAgents."""
    print("\nRemoving plist files...")
    removed = 0

    for plist_name in PLIST_FILES:
        plist_path = LAUNCH_AGENTS_DIR / plist_name
        if plist_path.exists():
            try:
                plist_path.unlink()
                print(f"  {GREEN}✓{RESET} Removed: {plist_name}")
                removed += 1
            except Exception as e:
                print(f"  {RED}✗{RESET} Failed to remove {plist_name}: {e}")
        else:
            print(f"  {YELLOW}-{RESET} Not found: {plist_name}")

    return removed


def remove_automator_app():
    """Remove Automator app."""
    print("\nRemoving Automator app...")

    if AUTOMATOR_APP.exists():
        try:
            shutil.rmtree(AUTOMATOR_APP)
            print(f"  {GREEN}✓{RESET} Removed: {AUTOMATOR_APP}")
            return True
        except Exception as e:
            print(f"  {RED}✗{RESET} Failed to remove: {e}")
            return False
    else:
        print(f"  {YELLOW}-{RESET} Not found: {AUTOMATOR_APP}")
        return True


def remove_state_files():
    """Remove state directory."""
    print("\nRemoving state files...")

    if STATE_DIR.exists():
        try:
            shutil.rmtree(STATE_DIR)
            print(f"  {GREEN}✓{RESET} Removed: {STATE_DIR}")
            return True
        except Exception as e:
            print(f"  {RED}✗{RESET} Failed to remove: {e}")
            return False
    else:
        print(f"  {YELLOW}-{RESET} Not found: {STATE_DIR}")
        return True


# =============================================================================
# Main
# =============================================================================

def main():
    print_header("Second Brain Uninstall")

    print("""
This will remove the automation components:

  {BOLD}WILL REMOVE:{RESET}
  • Launchd jobs (4 plists from ~/Library/LaunchAgents/)
  • Automator app (~/Applications/iMessageCapture.app)
  • State files (~/.imessage-capture/)

  {GREEN}WILL PRESERVE:{RESET}
  • All your notes and captures
  • Inbox-Log.md
  • Vault folder structure
  • config.local.yaml (your configuration)
  • The second_brain repository itself
""".format(BOLD=BOLD, RESET=RESET, GREEN=GREEN))

    if not confirm("Proceed with uninstall?"):
        print("\nUninstall cancelled.")
        return

    # Unload jobs first (must be done before removing plists)
    unload_launchd_jobs()

    # Remove plist files
    remove_plist_files()

    # Remove Automator app
    remove_automator_app()

    # Remove state files
    if confirm("\nRemove state files (logs and last-processed timestamp)?", default=True):
        remove_state_files()
    else:
        print("  Keeping state files.")

    # Summary
    print_header("Uninstall Complete")

    print("""
Second Brain automation has been removed.

Your notes and data are untouched:
  • Vault folders and files preserved
  • config.local.yaml preserved

To reinstall later:
  python3 scripts/setup.py
""")


if __name__ == "__main__":
    main()
