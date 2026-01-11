#!/usr/bin/env python3
"""
Second Brain Setup Wizard
Interactive setup script that guides users through installation.

Usage:
    python3 scripts/setup.py
"""

import os
import re
import sys
import shutil
import subprocess
from pathlib import Path

# =============================================================================
# Dependency Check
# =============================================================================

REQUIRED_PACKAGES = {
    'yaml': 'pyyaml',  # import name -> pip package name
}

def check_dependencies():
    """Check and install required Python packages."""
    missing = []

    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append((import_name, pip_name))

    if not missing:
        return True

    print("Missing required Python packages:")
    for import_name, pip_name in missing:
        print(f"  - {pip_name}")

    response = input("\nInstall them now? [Y/n]: ").strip().lower()
    if response in ('', 'y', 'yes'):
        for import_name, pip_name in missing:
            print(f"Installing {pip_name}...")
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', pip_name],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"Error installing {pip_name}: {result.stderr}")
                print(f"\nPlease install manually: pip3 install {pip_name}")
                return False
            print(f"  Installed {pip_name}")
        return True
    else:
        print(f"\nPlease install manually:")
        for _, pip_name in missing:
            print(f"  pip3 install {pip_name}")
        return False

# Check dependencies before proceeding
if not check_dependencies():
    sys.exit(1)

# Now safe to import yaml
import yaml

# =============================================================================
# Constants
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
CONFIG_PATH = REPO_DIR / "config.yaml"
CONFIG_LOCAL_PATH = REPO_DIR / "config.local.yaml"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"

# Common Obsidian vault locations
OBSIDIAN_SEARCH_PATHS = [
    Path.home() / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents",
    Path.home() / "Documents" / "Obsidian",
    Path.home() / "Obsidian",
]

# =============================================================================
# Utility Functions
# =============================================================================

def print_header(text):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(step, total, description):
    """Print a step indicator."""
    print(f"\n[Step {step}/{total}] {description}")
    print("-" * 40)


def prompt(question, default=None):
    """Prompt user for input with optional default."""
    if default:
        result = input(f"{question} [{default}]: ").strip()
        return result if result else default
    return input(f"{question}: ").strip()


def confirm(question, default=True):
    """Ask yes/no question."""
    suffix = "[Y/n]" if default else "[y/N]"
    response = input(f"{question} {suffix}: ").strip().lower()
    if not response:
        return default
    return response in ('y', 'yes')


def run_command(cmd, capture=True, check=True):
    """Run a shell command."""
    try:
        result = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            capture_output=capture,
            text=True,
            check=check
        )
        return result.stdout.strip() if capture else None
    except subprocess.CalledProcessError as e:
        return None


# =============================================================================
# Detection Functions
# =============================================================================

def detect_vault_path():
    """Search for Obsidian vault in common locations."""
    for base_path in OBSIDIAN_SEARCH_PATHS:
        if base_path.exists():
            # Look for vault folders (directories with .obsidian inside)
            for item in base_path.iterdir():
                if item.is_dir() and (item / ".obsidian").exists():
                    return str(item)
            # If no .obsidian found, return first directory
            for item in base_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    return str(item)
    return None


def detect_claude_path():
    """Find Claude executable."""
    # Try which command
    result = run_command("which claude", check=False)
    if result:
        return result

    # Check common locations
    common_paths = [
        Path.home() / ".npm-global" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
        Path("/opt/homebrew/bin/claude"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)
    return None


def get_system_info():
    """Get system username and home directory."""
    return {
        'username': os.environ.get('USER', 'unknown'),
        'home': str(Path.home()),
    }


# =============================================================================
# Validation Functions
# =============================================================================

def validate_phone(phone):
    """Validate phone number format."""
    # Remove spaces and dashes for validation
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    # Should start with + and contain only digits after
    if re.match(r'^\+\d{10,15}$', cleaned):
        return cleaned
    # Allow without + if it's a valid number
    if re.match(r'^\d{10,11}$', cleaned):
        return f"+1{cleaned}" if len(cleaned) == 10 else f"+{cleaned}"
    return None


def validate_email(email):
    """Basic email validation."""
    if re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return email
    return None


def validate_path(path_str):
    """Validate that a path exists."""
    path = Path(os.path.expanduser(path_str))
    return path.exists()


# =============================================================================
# Setup Functions
# =============================================================================

def create_config_local(values):
    """Create config.local.yaml with user values."""
    config = {
        'handles': [values['phone'], values['email']],
        'paths': {
            'vault': values['vault'],
        },
        'user': {
            'username': values['username'],
            'home': values['home'],
        },
        'claude': {
            'executable': values['claude_path'],
        },
    }

    header = """# Second Brain Configuration - LOCAL OVERRIDES
# This file contains your personal settings and is NOT committed to git.
# Generated by setup.py

"""

    with open(CONFIG_LOCAL_PATH, 'w') as f:
        f.write(header)
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"  Created: {CONFIG_LOCAL_PATH}")


def create_vault_folders(vault_path):
    """Create all required folders in the vault."""
    vault = Path(vault_path)
    folders = [
        "Second Brain/Inbox/Processed",
        "Second Brain/Projects",
        "Second Brain/People",
        "Second Brain/Ideas",
        "Second Brain/Admin",
        "Second Brain/Reports",
    ]

    created = 0
    for folder in folders:
        folder_path = vault / folder
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            print(f"  Created: {folder}")
            created += 1
        else:
            print(f"  Exists:  {folder}")

    # Create Inbox-Log.md if it doesn't exist
    log_path = vault / "Second Brain" / "Inbox-Log.md"
    if not log_path.exists():
        log_path.write_text("# Inbox Processing Log\n\n")
        print(f"  Created: Second Brain/Inbox-Log.md")
        created += 1

    return created


def generate_and_install_plists():
    """Generate plists and install them."""
    # Run generate_plists.py
    print("  Generating plist files...")
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "generate_plists.py")],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"  Error generating plists: {result.stderr}")
        return False

    # Create LaunchAgents directory if needed
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    # Copy plists to LaunchAgents
    plist_files = list(SCRIPT_DIR.glob("com.secondbrain.*.plist"))
    for plist in plist_files:
        dest = LAUNCH_AGENTS_DIR / plist.name
        shutil.copy(plist, dest)
        print(f"  Installed: {plist.name}")

    # Load all plists
    print("\n  Loading launchd jobs...")
    for plist in plist_files:
        dest = LAUNCH_AGENTS_DIR / plist.name
        # Unload first (ignore errors if not loaded)
        run_command(f"launchctl unload '{dest}' 2>/dev/null", check=False)
        # Load
        result = run_command(f"launchctl load '{dest}'", check=False)
        job_name = plist.stem
        print(f"  Loaded: {job_name}")

    return True


def check_fda_permission():
    """Check if we have Full Disk Access (can read Messages.db)."""
    messages_db = Path.home() / "Library" / "Messages" / "chat.db"
    try:
        with open(messages_db, 'rb') as f:
            f.read(1)
        return True
    except PermissionError:
        return False
    except FileNotFoundError:
        # Messages.app not set up, but FDA might still be granted
        return True


def setup_automator_app(username):
    """Guide user through Automator app creation."""
    script_content = f"/usr/bin/python3 /Users/{username}/source/second_brain/scripts/imessage_capture.py"
    app_path = Path.home() / "Applications" / "iMessageCapture.app"

    print(f"\n  The capture script needs to run as an Automator app to get Full Disk Access.")
    print(f"\n  Script to use in Automator:")
    print(f"  {'-'*50}")
    print(f"  {script_content}")
    print(f"  {'-'*50}")

    # Try to copy to clipboard
    try:
        subprocess.run(
            ['pbcopy'],
            input=script_content.encode(),
            check=True
        )
        print(f"\n  (Script copied to clipboard)")
    except:
        pass

    if app_path.exists():
        print(f"\n  Automator app already exists at: {app_path}")
        if confirm("  Do you want to update it?", default=False):
            # Open in Automator
            subprocess.run(['open', '-a', 'Automator', str(app_path)])
            print("\n  Automator opened. Update the shell script and save.")
    else:
        print(f"\n  Creating Automator app at: {app_path}")
        print("\n  Steps:")
        print("  1. Automator will open")
        print("  2. Select 'Application' as the document type")
        print("  3. Search for 'Run Shell Script' and drag it to the workflow")
        print("  4. Paste the script (already in clipboard)")
        print("  5. Save as 'iMessageCapture' to ~/Applications/")

        if confirm("\n  Open Automator now?"):
            subprocess.run(['open', '-a', 'Automator'])

    input("\n  Press Enter when you've saved the Automator app...")
    return app_path.exists()


def setup_fda_permission():
    """Guide user through Full Disk Access setup."""
    print("\n  The Automator app needs Full Disk Access to read Messages.")
    print("\n  Steps:")
    print("  1. Open System Settings > Privacy & Security > Full Disk Access")
    print("  2. Click the '+' button")
    print("  3. Navigate to ~/Applications/ and select iMessageCapture.app")
    print("  4. Ensure the toggle is ON")

    if confirm("\n  Open System Settings now?"):
        subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles'])

    input("\n  Press Enter when you've granted Full Disk Access...")
    return check_fda_permission()


def check_claude_auth():
    """Check if Claude Code is authenticated."""
    claude_path = detect_claude_path()
    if not claude_path:
        return False, "Claude executable not found"

    # Try a simple command
    result = subprocess.run(
        [claude_path, '--version'],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        return False, "Claude command failed"

    return True, result.stdout.strip()


def setup_claude_token():
    """Guide user through Claude token setup."""
    print("\n  For scheduled jobs to work, Claude needs a long-lived token.")
    print("  This requires a Claude Pro or Max subscription.")

    if confirm("\n  Run 'claude setup-token' now?"):
        claude_path = detect_claude_path()
        if claude_path:
            print("\n  Follow the prompts in your browser...")
            subprocess.run([claude_path, 'setup-token'])
            return True
    return False


# =============================================================================
# Main Setup Flow
# =============================================================================

def main():
    print_header("Second Brain Setup Wizard")
    print("This wizard will guide you through setting up Second Brain.")
    print("It will configure iMessage capture, automatic classification,")
    print("and daily/weekly digests.")

    if not confirm("\nReady to begin?"):
        print("\nSetup cancelled.")
        return

    total_steps = 8
    config_values = {}

    # -------------------------------------------------------------------------
    # Step 1: Detect Environment
    # -------------------------------------------------------------------------
    print_step(1, total_steps, "Detecting Environment")

    system_info = get_system_info()
    config_values['username'] = system_info['username']
    config_values['home'] = system_info['home']
    print(f"  Username: {config_values['username']}")
    print(f"  Home: {config_values['home']}")

    vault_path = detect_vault_path()
    if vault_path:
        print(f"  Detected vault: {vault_path}")
        if not confirm("  Is this correct?"):
            vault_path = prompt("  Enter vault path")
    else:
        vault_path = prompt("  Enter your Obsidian vault path")

    vault_path = os.path.expanduser(vault_path)
    if not Path(vault_path).exists():
        print(f"  Warning: Path does not exist: {vault_path}")
        if not confirm("  Create it?"):
            print("  Please create the vault first and re-run setup.")
            return
        Path(vault_path).mkdir(parents=True, exist_ok=True)

    config_values['vault'] = vault_path

    claude_path = detect_claude_path()
    if claude_path:
        print(f"  Detected Claude: {claude_path}")
    else:
        claude_path = prompt("  Enter Claude executable path", "~/.npm-global/bin/claude")
    config_values['claude_path'] = claude_path

    # -------------------------------------------------------------------------
    # Step 2: Collect User Information
    # -------------------------------------------------------------------------
    print_step(2, total_steps, "Your Information")

    print("  Enter your iMessage handles (phone and email).")
    print("  These must match exactly what's in Messages.app.")

    while True:
        phone = prompt("\n  Phone number (e.g., +17035551234)")
        validated = validate_phone(phone)
        if validated:
            config_values['phone'] = validated
            print(f"  Validated: {validated}")
            break
        print("  Invalid format. Use: +1XXXXXXXXXX")

    while True:
        email = prompt("  Apple ID email")
        validated = validate_email(email)
        if validated:
            config_values['email'] = validated
            break
        print("  Invalid email format.")

    # -------------------------------------------------------------------------
    # Step 3: Create Configuration
    # -------------------------------------------------------------------------
    print_step(3, total_steps, "Creating Configuration")

    if CONFIG_LOCAL_PATH.exists():
        if confirm("  config.local.yaml exists. Overwrite?", default=False):
            create_config_local(config_values)
        else:
            print("  Keeping existing configuration.")
    else:
        create_config_local(config_values)

    # -------------------------------------------------------------------------
    # Step 4: Create Vault Folders
    # -------------------------------------------------------------------------
    print_step(4, total_steps, "Creating Vault Folders")

    created = create_vault_folders(config_values['vault'])
    print(f"\n  Created {created} new folder(s).")

    # -------------------------------------------------------------------------
    # Step 5: Generate and Install Plists
    # -------------------------------------------------------------------------
    print_step(5, total_steps, "Installing Launchd Jobs")

    if generate_and_install_plists():
        print("\n  All jobs installed successfully.")
    else:
        print("\n  Warning: Some jobs may not have installed correctly.")

    # -------------------------------------------------------------------------
    # Step 6: Automator App Setup
    # -------------------------------------------------------------------------
    print_step(6, total_steps, "Automator App Setup")

    setup_automator_app(config_values['username'])

    # -------------------------------------------------------------------------
    # Step 7: Permission Grants
    # -------------------------------------------------------------------------
    print_step(7, total_steps, "Permission Setup")

    if check_fda_permission():
        print("  Full Disk Access: Already granted")
    else:
        print("  Full Disk Access: Not granted")
        setup_fda_permission()
        if check_fda_permission():
            print("  Full Disk Access: Now granted")
        else:
            print("  Warning: FDA still not granted. Capture may not work.")

    # -------------------------------------------------------------------------
    # Step 8: Claude Authentication
    # -------------------------------------------------------------------------
    print_step(8, total_steps, "Claude Code Setup")

    auth_ok, auth_msg = check_claude_auth()
    if auth_ok:
        print(f"  Claude: {auth_msg}")
    else:
        print(f"  Claude: {auth_msg}")

    if confirm("  Set up long-lived token for scheduled jobs?", default=True):
        setup_claude_token()

    # -------------------------------------------------------------------------
    # Done!
    # -------------------------------------------------------------------------
    print_header("Setup Complete!")

    print("Your Second Brain is ready. Here's what's set up:\n")
    print(f"  Vault: {config_values['vault']}")
    print(f"  Handles: {config_values['phone']}, {config_values['email']}")
    print(f"  Jobs: 4 launchd jobs installed and running")

    print("\n" + "="*60)
    print("  Next Steps")
    print("="*60)
    print("""
  1. Send yourself an iMessage to test capture
  2. Wait 60 seconds for it to appear in Inbox
  3. Run diagnostics: python3 scripts/diagnose.py

  If something isn't working:
  - Check logs: ~/.imessage-capture/*.log
  - Run diagnostics: python3 scripts/diagnose.py
  - See docs/installation.md for troubleshooting
""")


if __name__ == "__main__":
    main()
