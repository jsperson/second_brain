#!/usr/bin/env python3
"""
Second Brain Diagnostic Tool
Checks all components and reports their status.

Usage:
    python3 scripts/diagnose.py
"""

import os
import subprocess
import yaml
from pathlib import Path

# =============================================================================
# Constants
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
CONFIG_PATH = REPO_DIR / "config.yaml"
CONFIG_LOCAL_PATH = REPO_DIR / "config.local.yaml"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
STATE_DIR = Path.home() / ".imessage-capture"

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

# =============================================================================
# Utility Functions
# =============================================================================

def check_mark(passed):
    """Return colored check or X mark."""
    if passed:
        return f"{GREEN}✓{RESET}"
    return f"{RED}✗{RESET}"


def warn_mark():
    """Return yellow warning mark."""
    return f"{YELLOW}!{RESET}"


def print_header(text):
    """Print a section header."""
    print(f"\n{BOLD}{text}{RESET}")


def run_command(cmd, check=False):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            capture_output=True,
            text=True,
            check=check,
            timeout=10
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def load_config():
    """Load merged configuration."""
    if not CONFIG_PATH.exists():
        return None

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    if CONFIG_LOCAL_PATH.exists():
        with open(CONFIG_LOCAL_PATH) as f:
            local = yaml.safe_load(f)
            config = deep_merge(config, local)

    return config


def deep_merge(base, override):
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def expand_path(path_str):
    """Expand ~ and environment variables."""
    return os.path.expanduser(os.path.expandvars(path_str))


# =============================================================================
# Check Functions
# =============================================================================

def check_configuration():
    """Check configuration files."""
    results = []

    # config.yaml
    passed = CONFIG_PATH.exists()
    results.append((passed, "config.yaml exists"))

    # config.local.yaml
    passed = CONFIG_LOCAL_PATH.exists()
    results.append((passed, "config.local.yaml exists"))

    if not CONFIG_LOCAL_PATH.exists():
        return results, None

    # Load and validate config
    config = load_config()
    if not config:
        results.append((False, "Configuration could not be loaded"))
        return results, None

    # Vault path
    vault_path = config.get('paths', {}).get('vault', '')
    vault_path = expand_path(vault_path)
    passed = Path(vault_path).exists()
    short_path = vault_path.replace(str(Path.home()), "~")
    results.append((passed, f"Vault path valid: {short_path}"))

    # Handles
    handles = config.get('handles', [])
    passed = len(handles) >= 1
    results.append((passed, f"Handles configured: {len(handles)} entries"))

    return results, config


def check_folders(config):
    """Check vault folders exist."""
    results = []

    if not config:
        return results

    vault_path = expand_path(config.get('paths', {}).get('vault', ''))
    if not vault_path:
        return results

    vault = Path(vault_path)
    folders = [
        "Second Brain/Inbox",
        "Second Brain/Inbox/Processed",
        "Second Brain/Projects",
        "Second Brain/People",
        "Second Brain/Ideas",
        "Second Brain/Admin",
        "Second Brain/Reports",
    ]

    for folder in folders:
        passed = (vault / folder).exists()
        results.append((passed, folder.split("/")[-1] + " exists"))

    return results


def check_permissions():
    """Check required permissions."""
    results = []

    # Full Disk Access - try to read Messages.db
    messages_db = Path.home() / "Library" / "Messages" / "chat.db"
    try:
        with open(messages_db, 'rb') as f:
            f.read(1)
        passed = True
    except PermissionError:
        passed = False
    except FileNotFoundError:
        passed = True  # Messages not set up, but FDA might be granted
    results.append((passed, "Full Disk Access: " + ("granted" if passed else "NOT granted")))

    # Messages Automation - harder to check directly
    # We'll just note it as a warning
    results.append((None, "Messages Automation: check manually if feedback fails"))

    return results


def check_launchd_jobs():
    """Check launchd jobs are loaded and running."""
    results = []

    jobs = [
        "com.secondbrain.imessage-capture",
        "com.secondbrain.inbox-processor",
        "com.secondbrain.daily-digest",
        "com.secondbrain.weekly-review",
    ]

    for job in jobs:
        # Check if plist exists
        plist_path = LAUNCH_AGENTS_DIR / f"{job}.plist"
        if not plist_path.exists():
            results.append((False, f"{job}: plist not found"))
            continue

        # Check if loaded
        success, output = run_command(f"launchctl list | grep {job}")
        if success and job in output:
            # Parse status from launchctl output
            parts = output.split()
            if len(parts) >= 2:
                pid = parts[0]
                status = parts[1]
                if pid == "-":
                    state = "loaded (not running)"
                else:
                    state = f"running (PID {pid})"
                results.append((True, f"{job.replace('com.secondbrain.', '')}: {state}"))
            else:
                results.append((True, f"{job.replace('com.secondbrain.', '')}: loaded"))
        else:
            results.append((False, f"{job.replace('com.secondbrain.', '')}: not loaded"))

    return results


def check_claude():
    """Check Claude Code installation and authentication."""
    results = []

    # Find Claude executable
    success, output = run_command("which claude")
    if success and output:
        results.append((True, f"Claude executable: {output}"))

        # Check version
        success, version = run_command(f"'{output}' --version")
        if success:
            results.append((True, f"Claude version: {version.split()[0] if version else 'unknown'}"))
        else:
            results.append((False, "Claude version check failed"))
    else:
        results.append((False, "Claude executable not found"))

    # Check credentials file
    creds_file = Path.home() / ".claude" / ".credentials.json"
    if creds_file.exists():
        results.append((True, "Claude credentials file exists"))
    else:
        results.append((None, "Claude credentials file not found (may use OAuth)"))

    return results


def check_automator_app():
    """Check Automator app exists."""
    results = []

    app_path = Path.home() / "Applications" / "iMessageCapture.app"
    passed = app_path.exists()
    results.append((passed, f"Automator app: {'found' if passed else 'NOT found'}"))

    return results


def check_logs():
    """Check log files for recent errors."""
    results = []

    log_files = [
        ("launchd.log", "Capture log"),
        ("launchd-error.log", "Capture errors"),
        ("inbox-processor.log", "Processor log"),
        ("inbox-processor-error.log", "Processor errors"),
    ]

    for filename, description in log_files:
        log_path = STATE_DIR / filename
        if log_path.exists():
            size = log_path.stat().st_size
            if "error" in filename.lower() and size > 0:
                # Check last few lines for errors
                try:
                    content = log_path.read_text()[-500:]
                    if "Error" in content or "error" in content:
                        results.append((None, f"{description}: has recent errors"))
                    else:
                        results.append((True, f"{description}: {size} bytes"))
                except:
                    results.append((True, f"{description}: {size} bytes"))
            else:
                results.append((True, f"{description}: {size} bytes"))
        else:
            results.append((None, f"{description}: not found"))

    return results


# =============================================================================
# Main
# =============================================================================

def main():
    print(f"\n{BOLD}Second Brain Diagnostics{RESET}")
    print("=" * 40)

    all_passed = True
    warnings = 0

    # Configuration
    print_header("Configuration")
    results, config = check_configuration()
    for passed, message in results:
        if passed is None:
            print(f"  {warn_mark()} {message}")
            warnings += 1
        else:
            print(f"  {check_mark(passed)} {message}")
            if not passed:
                all_passed = False

    # Folders
    print_header("Folders")
    results = check_folders(config)
    for passed, message in results:
        print(f"  {check_mark(passed)} {message}")
        if not passed:
            all_passed = False

    # Automator App
    print_header("Automator App")
    results = check_automator_app()
    for passed, message in results:
        print(f"  {check_mark(passed)} {message}")
        if not passed:
            all_passed = False

    # Permissions
    print_header("Permissions")
    results = check_permissions()
    for passed, message in results:
        if passed is None:
            print(f"  {warn_mark()} {message}")
            warnings += 1
        else:
            print(f"  {check_mark(passed)} {message}")
            if not passed:
                all_passed = False

    # Launchd Jobs
    print_header("Launchd Jobs")
    results = check_launchd_jobs()
    for passed, message in results:
        print(f"  {check_mark(passed)} {message}")
        if not passed:
            all_passed = False

    # Claude Code
    print_header("Claude Code")
    results = check_claude()
    for passed, message in results:
        if passed is None:
            print(f"  {warn_mark()} {message}")
            warnings += 1
        else:
            print(f"  {check_mark(passed)} {message}")
            if not passed:
                all_passed = False

    # Logs
    print_header("Logs")
    results = check_logs()
    for passed, message in results:
        if passed is None:
            print(f"  {warn_mark()} {message}")
            warnings += 1
        else:
            print(f"  {check_mark(passed)} {message}")

    # Summary
    print("\n" + "=" * 40)
    if all_passed and warnings == 0:
        print(f"{GREEN}{BOLD}All checks passed!{RESET}")
    elif all_passed:
        print(f"{YELLOW}{BOLD}All checks passed with {warnings} warning(s){RESET}")
    else:
        print(f"{RED}{BOLD}Some checks failed{RESET}")
        print("\nTroubleshooting:")
        print("  - Run: python3 scripts/setup.py")
        print("  - Check: docs/installation.md")
        print("  - Logs: ~/.imessage-capture/")

    print()


if __name__ == "__main__":
    main()
