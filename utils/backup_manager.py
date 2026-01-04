#!/usr/bin/env python3
"""
Backup Manager CLI - Utility for managing and inspecting backups.
"""

import argparse
import json
import os
import sys
from datetime import datetime

from .backup_utils import BackupManager, setup_logging


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def list_backups(backup_manager: BackupManager):
    """List all backups."""
    backups = backup_manager.list_backups()
    if not backups:
        print("No backups found.")
        return

    print(f"\nFound {len(backups)} backup(s):\n")
    print(f"{'Filename':<50} {'Size':<12} {'Created':<20} {'Verified':<8}")
    print("-" * 90)

    for backup in backups:
        filename = backup["filename"]
        size = format_size(backup["size"])
        created = backup.get("created_at", "Unknown")
        if created != "Unknown":
            try:
                dt = datetime.fromisoformat(created)
                created = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        verified = "✓" if backup.get("verified", False) else "✗"
        print(f"{filename:<50} {size:<12} {created:<20} {verified:<8}")


def show_backup_info(backup_manager: BackupManager, filename: str):
    """Show detailed information about a specific backup."""
    info = backup_manager.get_backup_info(filename)
    if not info:
        print(f"Backup not found: {filename}")
        sys.exit(1)

    print(f"\nBackup Information: {filename}\n")
    print(f"  Path:       {info['path']}")
    print(f"  Size:       {format_size(info['size'])}")
    print(f"  Created:    {info.get('created_at', 'Unknown')}")
    print(f"  Timestamp:  {info.get('timestamp', 'Unknown')}")
    print(f"  Checksum:   {info.get('checksum', 'Not calculated')}")
    print(f"  Verified:   {'Yes' if info.get('verified', False) else 'No'}")


def verify_backups(backup_manager: BackupManager):
    """Verify integrity of all backups."""
    print("Verifying backups...")
    results = backup_manager.verify_all_backups()

    verified = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\nVerification Results: {verified}/{total} backups verified\n")

    for filename, is_valid in results.items():
        status = "✓ Valid" if is_valid else "✗ Invalid"
        print(f"  {filename:<50} {status}")

    if verified < total:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Backup Manager - Manage and inspect backups"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the configuration JSON file",
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["bitwarden", "obsidian"],
        required=True,
        help="Type of backup (bitwarden or obsidian)",
    )
    parser.add_argument(
        "action",
        choices=["list", "info", "verify"],
        help="Action to perform",
    )
    parser.add_argument(
        "--filename",
        type=str,
        help="Backup filename (required for 'info' action)",
    )

    args = parser.parse_args()

    # Load configuration
    config_file_path = os.path.abspath(args.config)
    with open(config_file_path, "r") as f:
        config = json.load(f)

    # Determine backup prefix and directory
    if args.type == "bitwarden":
        backup_prefix = "bitwarden_backup"
        backup_dir = os.path.expanduser(config["BACKUP_DIR_PATH"])
    else:  # obsidian
        backup_prefix = "obsidian_backup"
        backup_dir = os.path.expanduser(config["BACKUP_DIR_PATH"])

    zip_password = config["ZIP_PASSWORD"]
    max_backups = config.get("MAX_BACKUPS", 7)
    retention_policy = config.get("RETENTION_POLICY")

    # Setup logging
    log_file_path = config.get(
        "LOG_FILE_PATH",
        os.path.expanduser(f"~/.local/share/{args.type}-backup/backup-manager.log"),
    )
    setup_logging(log_file_path, level=30)  # WARNING level for CLI

    # Create backup manager
    backup_manager = BackupManager(
        backup_dir=backup_dir,
        backup_prefix=backup_prefix,
        zip_password=zip_password,
        max_backups=max_backups,
        verify_backups=False,  # Don't auto-verify in CLI
        retention_policy=retention_policy,
    )

    # Execute action
    if args.action == "list":
        list_backups(backup_manager)
    elif args.action == "info":
        if not args.filename:
            print("Error: --filename is required for 'info' action")
            sys.exit(1)
        show_backup_info(backup_manager, args.filename)
    elif args.action == "verify":
        verify_backups(backup_manager)


if __name__ == "__main__":
    main()
