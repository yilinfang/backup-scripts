#!/usr/bin/env python3

import argparse
import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime

parser = argparse.ArgumentParser(description="Bitwarden Backup Script")
parser.add_argument(
    "--config",
    type=str,
    required=True,
    help="Path to the configuration JSON file",
)
args = parser.parse_args()

config_file_path = os.path.abspath(args.config)

with open(config_file_path, "r") as f:
    config = json.load(f)
    bw_clientid = config["BW_CLIENTID"]
    bw_clientsecret = config["BW_CLIENTSECRET"]
    bw_password = config["BW_PASSWORD"]
    backup_dir_path = os.path.expanduser(config["BACKUP_DIR_PATH"])
    zip_password = config["ZIP_PASSWORD"]
    max_backups = config["MAX_BACKUPS"]
    log_file_path = config.get(
        "LOG_FILE_PATH", os.path.expanduser("~/.local/share/bw-backup/bw-backup.log")
    )

# Ensure log directory exists
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file_path), logging.StreamHandler()],
)

# Ensure the backup directory exists
os.makedirs(backup_dir_path, exist_ok=True)

# Create temporary directory for intermediate files
temp_dir = tempfile.mkdtemp(prefix="bw-backup-")
logging.info(f"Using temporary directory: {temp_dir}")


# Check if a command exists
def is_command_available(command):
    return shutil.which(command) is not None


try:
    # Ensure Bitwarden CLI is installed
    if not is_command_available("bw"):
        logging.error("Bitwarden CLI (bw) not available. Please install it first.")
    else:
        logging.info("Bitwarden CLI (bw) is available.")

    # Log in to Bitwarden
    logging.info("Logging into Bitwarden...")
    login_env = os.environ.copy()
    login_env["BW_CLIENTID"] = bw_clientid
    login_env["BW_CLIENTSECRET"] = bw_clientsecret
    if subprocess.run(["bw", "login", "--apikey"], env=login_env).returncode != 0:
        logging.error("Failed to login to Bitwarden")
        exit(1)

    # Unlock the vault
    logging.info("Unlocking the vault...")
    unlock_env = os.environ.copy()
    unlock_env["BW_PASSWORD"] = bw_password
    result = subprocess.run(
        ["bw", "unlock", "--passwordenv", "BW_PASSWORD", "--raw"],
        capture_output=True,
        text=True,
        env=unlock_env,
    )
    if result.returncode != 0:
        logging.error("Failed to unlock the vault")
        exit(1)
    session = result.stdout.strip()
    logging.info("Vault unlocked successfully.")

    # Sync the vault
    logging.info("Syncing the vault...")
    if subprocess.run(["bw", "sync", "--session", session]).returncode != 0:
        logging.error("Failed to sync the vault")
        exit(1)

    # Export the vault
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    backup_file = os.path.join(temp_dir, f"bitwarden_backup_{timestamp}.json")
    encrypted_backup_file = os.path.join(
        backup_dir_path, f"bitwarden_backup_{timestamp}.zip"
    )
    logging.info(f"Exporting vault to {backup_file}...")
    if (
        subprocess.run(
            [
                "bw",
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
        exit(1)

    # Encrypt the backup
    logging.info(f"Encrypting backup to {encrypted_backup_file}...")
    if (
        subprocess.run(
            ["zip", "-P", zip_password, "-j", encrypted_backup_file, backup_file]
        ).returncode
        != 0
    ):
        logging.error("Failed to encrypt the backup")
        exit(1)
    os.remove(backup_file)
    logging.info("Plain backup file removed after encryption.")

    # Log out from Bitwarden
    logging.info("Logging out from Bitwarden...")
    if subprocess.run(["bw", "logout"]).returncode != 0:
        logging.error("Failed to log out from Bitwarden")
        exit(1)

    # Cleanup old backups
    logging.info("Cleaning up old backups...")
    backup_files = sorted(
        [
            f
            for f in os.listdir(backup_dir_path)
            if f.startswith("bitwarden_backup_") and f.endswith(".zip")
        ],
        key=lambda x: os.path.getmtime(os.path.join(backup_dir_path, x)),
    )
    if len(backup_files) > max_backups:
        for old_backup in backup_files[: len(backup_files) - max_backups]:
            os.remove(os.path.join(backup_dir_path, old_backup))
            logging.info(f"Deleted old backup: {old_backup}")
    else:
        logging.info("No old backups to delete.")

    logging.info("Backup completed successfully.")
finally:
    # Clean up temporary directory
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        logging.info(f"Cleaned up temporary directory: {temp_dir}")
