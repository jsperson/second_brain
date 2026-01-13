#!/usr/bin/env python3
"""
Audit Logging for Second Brain Claude Operations

Provides silent, background logging of Claude operations for security monitoring.
Logs are stored in ~/.second_brain-audit/ and rotated weekly.

Usage:
    from audit_log import audit_log

    audit_log("process_inbox", "classify", file_count=5)
    audit_log("scans_organize", "file_operation", action="move", path="scan.pdf")
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Audit log directory (outside git repo)
AUDIT_DIR = Path.home() / ".second_brain-audit"
AUDIT_DIR.mkdir(exist_ok=True)

# Current log file (rotated weekly)
def get_audit_log_path():
    """Get path to current week's audit log file."""
    week_str = datetime.now().strftime("%Y-W%W")  # e.g., "2026-W02"
    return AUDIT_DIR / f"audit-{week_str}.jsonl"


def audit_log(skill, operation, **details):
    """
    Log a Claude operation for security audit.

    Args:
        skill: Name of skill/script (e.g., "process_inbox", "news", "scans_organize")
        operation: Type of operation (e.g., "classify", "file_read", "file_write", "git_commit")
        **details: Additional context (file_path, file_count, action, etc.)

    Example:
        audit_log("process_inbox", "classify", file_count=5, result="filed")
        audit_log("scans_organize", "file_read", path="/Desktop/scans/bank-statement.pdf")
        audit_log("news", "git_push", repo="second_brain", branch="main")
    """
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "skill": skill,
            "operation": operation,
            **details
        }

        log_path = get_audit_log_path()
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')

    except Exception as e:
        # Silent failure - don't interrupt normal operation
        # But write to stderr so errors appear in launchd logs
        import sys
        print(f"Audit log error: {e}", file=sys.stderr)


def get_recent_logs(days=7):
    """
    Retrieve recent audit log entries.

    Args:
        days: Number of days to retrieve (default: 7)

    Returns:
        List of log entry dicts, newest first
    """
    logs = []

    # Get all log files, sorted newest first
    log_files = sorted(AUDIT_DIR.glob("audit-*.jsonl"), reverse=True)

    cutoff = datetime.now().timestamp() - (days * 86400)

    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = json.loads(line.strip())
                    entry_time = datetime.fromisoformat(entry['timestamp']).timestamp()

                    if entry_time >= cutoff:
                        logs.append(entry)
                    else:
                        # Files are ordered, entries within files are chronological
                        # Once we hit old entries, we can stop
                        return sorted(logs, key=lambda x: x['timestamp'], reverse=True)

        except Exception:
            continue  # Skip corrupted files

    return sorted(logs, key=lambda x: x['timestamp'], reverse=True)


def summarize_logs(days=7):
    """
    Generate a human-readable summary of recent audit logs.

    Returns:
        String summary of operations
    """
    logs = get_recent_logs(days)

    if not logs:
        return f"No audit logs found for the last {days} days."

    # Count operations by skill and type
    skill_counts = {}
    operation_counts = {}

    for entry in logs:
        skill = entry.get('skill', 'unknown')
        operation = entry.get('operation', 'unknown')

        skill_counts[skill] = skill_counts.get(skill, 0) + 1
        operation_counts[operation] = operation_counts.get(operation, 0) + 1

    summary = [
        f"Audit Log Summary (Last {days} days)",
        f"Total Operations: {len(logs)}",
        "",
        "By Skill:",
    ]

    for skill, count in sorted(skill_counts.items(), key=lambda x: x[1], reverse=True):
        summary.append(f"  {skill}: {count}")

    summary.append("")
    summary.append("By Operation:")

    for operation, count in sorted(operation_counts.items(), key=lambda x: x[1], reverse=True):
        summary.append(f"  {operation}: {count}")

    summary.append("")
    summary.append(f"Earliest: {logs[-1]['timestamp']}")
    summary.append(f"Latest: {logs[0]['timestamp']}")

    return "\n".join(summary)


if __name__ == "__main__":
    # CLI usage: python audit_log.py [days]
    import sys

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print(summarize_logs(days))
