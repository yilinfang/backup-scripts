#!/usr/bin/env python3

import argparse
import json
import logging
import os
import sys

from utils.backup_utils import BackupManager, setup_logging, validate_config


def main(args):
    config_file_path = os.path.abspath(args.config)

    with open(config_file_path, "r") as f:
        config = json.load(f)

    # Validate configuration
    required_keys = ["VAULT_PATH", "BACKUP_DIR_PATH", "ZIP_PASSWORD", "MAX_BACKUPS"]
    is_valid, error_msg = validate_config(config, required_keys)
    if not is_valid:
        logging.error(f"Configuration validation failed: {error_msg}")
        sys.exit(1)

    vault_path = os.path.expanduser(config["VAULT_PATH"])
    backup_dir_path = os.path.expanduser(config["BACKUP_DIR_PATH"])
    zip_password = config["ZIP_PASSWORD"]
    max_backups = config["MAX_BACKUPS"]
    log_file_path = config.get(
        "LOG_FILE_PATH",
        os.path.expanduser("~/.local/share/ob-backup/ob-backup.log"),
    )
    verify_backups = config.get("VERIFY_BACKUPS", True)
    retention_policy = config.get("RETENTION_POLICY")

    # Setup logging
    setup_logging(log_file_path, level=logging.INFO)

    # Validate vault path exists
    if not os.path.exists(vault_path):
        logging.error(f"Vault path does not exist: {vault_path}")
        sys.exit(1)

    if not os.path.isdir(vault_path):
        logging.error(f"Vault path is not a directory: {vault_path}")
        sys.exit(1)

    # Initialize backup manager
    backup_manager = BackupManager(
        backup_dir=backup_dir_path,
        backup_prefix="obsidian_backup",
        zip_password=zip_password,
        max_backups=max_backups,
        verify_backups=verify_backups,
        retention_policy=retention_policy,
    )

    try:
        # Create encrypted backup using BackupManager
        logging.info(f"Creating backup of vault: {vault_path}...")
        try:
            backup_path, metadata = backup_manager.create_encrypted_backup(
                vault_path, is_file=False
            )
            logging.info(
                f"Backup created successfully: {metadata['filename']} "
                f"({metadata['size']} bytes, checksum: {metadata['checksum'][:16]}...)"
            )
        except Exception as e:
            logging.error(f"Failed to create encrypted backup: {e}")
            sys.exit(1)

        # Rotate backups
        logging.info("Rotating backups...")
        backup_manager.rotate_backups()

        logging.info("Backup completed successfully.")
    except Exception as e:
        logging.error(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Obsidian Backup Script")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the configuration JSON file",
    )
    args = parser.parse_args()
    main(args)
