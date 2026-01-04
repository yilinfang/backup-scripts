#!/usr/bin/env python3

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

from utils.backup_utils import BackupManager, setup_logging, validate_config


# Check if a command exists
def is_command_available(command):
    return shutil.which(command) is not None


# Determine which bw command to use
def get_bw_command():
    if is_command_available("bw"):
        logging.info("Using locally installed Bitwarden CLI (bw).")
        return ["bw"]
    elif is_command_available("npx"):
        logging.info("Using Bitwarden CLI via npx (npx @bitwarden/cli).")
        return ["npx", "--yes", "@bitwarden/cli"]
    else:
        logging.error(
            "Neither bw nor npx is available. Please install Bitwarden CLI or npx."
        )
        sys.exit(1)


def main(args):
    config_file_path = os.path.abspath(args.config)

    with open(config_file_path, "r") as f:
        config = json.load(f)

    # Validate configuration
    required_keys = [
        "BW_CLIENTID",
        "BW_CLIENTSECRET",
        "BW_PASSWORD",
        "BACKUP_DIR_PATH",
        "ZIP_PASSWORD",
        "MAX_BACKUPS",
    ]
    is_valid, error_msg = validate_config(config, required_keys)
    if not is_valid:
        logging.error(f"Configuration validation failed: {error_msg}")
        sys.exit(1)

    bw_clientid = config["BW_CLIENTID"]
    bw_clientsecret = config["BW_CLIENTSECRET"]
    bw_password = config["BW_PASSWORD"]
    backup_dir_path = os.path.expanduser(config["BACKUP_DIR_PATH"])
    zip_password = config["ZIP_PASSWORD"]
    max_backups = config["MAX_BACKUPS"]
    log_file_path = config.get(
        "LOG_FILE_PATH",
        os.path.expanduser("~/.local/share/bw-backup/bw-backup.log"),
    )
    verify_backups = config.get("VERIFY_BACKUPS", True)
    retention_policy = config.get("RETENTION_POLICY")

    # Setup logging
    setup_logging(log_file_path, level=logging.INFO)

    # Initialize backup manager
    backup_manager = BackupManager(
        backup_dir=backup_dir_path,
        backup_prefix="bitwarden_backup",
        zip_password=zip_password,
        max_backups=max_backups,
        verify_backups=verify_backups,
        retention_policy=retention_policy,
    )

    # Ensure the backup directory exists
    os.makedirs(backup_dir_path, exist_ok=True)

    # Create temporary directory for intermediate files
    temp_dir = tempfile.mkdtemp(prefix="bw-backup-")
    logging.info(f"Using temporary directory: {temp_dir}")

    try:
        # Get the appropriate bw command
        bw_cmd = get_bw_command()

        # Log in to Bitwarden
        logging.info("Logging into Bitwarden...")
        login_env = os.environ.copy()
        login_env["BW_CLIENTID"] = bw_clientid
        login_env["BW_CLIENTSECRET"] = bw_clientsecret
        if (
            subprocess.run(bw_cmd + ["login", "--apikey"], env=login_env).returncode
            != 0
        ):
            logging.error("Failed to login to Bitwarden")
            sys.exit(1)

        # Unlock the vault
        logging.info("Unlocking the vault...")
        unlock_env = os.environ.copy()
        unlock_env["BW_PASSWORD"] = bw_password
        result = subprocess.run(
            bw_cmd + ["unlock", "--passwordenv", "BW_PASSWORD", "--raw"],
            capture_output=True,
            text=True,
            env=unlock_env,
        )
        if result.returncode != 0:
            logging.error("Failed to unlock the vault")
            sys.exit(1)
        session = result.stdout.strip()
        logging.info("Vault unlocked successfully.")

        # Sync the vault
        logging.info("Syncing the vault...")
        if subprocess.run(bw_cmd + ["sync", "--session", session]).returncode != 0:
            logging.error("Failed to sync the vault")
            sys.exit(1)

        # Export the vault
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        backup_file = os.path.join(temp_dir, f"bitwarden_backup_{timestamp}.json")
        logging.info(f"Exporting vault to {backup_file}...")
        if (
            subprocess.run(
                bw_cmd
                + [
                    "export",
                    "--output",
                    backup_file,
                    "--format",
                    "json",
                    "--session",
                    session,
                ]
            ).returncode
            != 0
        ):
            logging.error("Failed to export the vault")
            sys.exit(1)

        # Create encrypted backup using BackupManager
        logging.info("Creating encrypted backup...")
        try:
            backup_path, metadata = backup_manager.create_encrypted_backup(
                backup_file, is_file=True
            )
            logging.info(
                f"Backup created successfully: {metadata['filename']} "
                f"({metadata['size']} bytes, checksum: {metadata['checksum'][:16]}...)"
            )
        except Exception as e:
            logging.error(f"Failed to create encrypted backup: {e}")
            sys.exit(1)
        finally:
            # Remove plain backup file
            if os.path.exists(backup_file):
                os.remove(backup_file)
                logging.info("Plain backup file removed after encryption.")

        # Log out from Bitwarden
        logging.info("Logging out from Bitwarden...")
        if subprocess.run(bw_cmd + ["logout"]).returncode != 0:
            logging.error("Failed to log out from Bitwarden")
            sys.exit(1)

        # Rotate backups
        logging.info("Rotating backups...")
        backup_manager.rotate_backups()

        logging.info("Backup completed successfully.")
    finally:
        # Clean up temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.info(f"Cleaned up temporary directory: {temp_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bitwarden Backup Script")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the configuration JSON file",
    )
    args = parser.parse_args()
    main(args)
