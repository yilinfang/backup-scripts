#!/usr/bin/env python3

import argparse
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser(description="Bitwarden Backup Script")
parser.add_argument(
    "--config",
    type=str,
    required=True,
    help="Path to the configuration JSON file",
)
args = parser.parse_args()

CONFIG_FILE = os.path.abspath(args.config)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)
    BW_CLIENTID = config["BW_CLIENTID"]
    BW_CLIENTSECRET = config["BW_CLIENTSECRET"]
    BW_PASSWORD = config["BW_PASSWORD"]
    BACKUP_DIR = os.path.expanduser(config["BACKUP_DIR"])
    ZIP_PASSWORD = config["ZIP_PASSWORD"]
    MAX_BACKUPS = config["MAX_BACKUPS"]
    LOG_FILE = config.get("LOG_FILE", os.path.join(SCRIPT_DIR, "log", "bw-backup.log"))

# Ensure log directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

# Ensure the backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)


# Check if a command exists
def is_command_available(command):
    return shutil.which(command) is not None


# Ensure Bitwarden CLI is installed
if not is_command_available("bw"):
    logging.error(
        "Bitwarden CLI (bw) could not be found in default PATH. Please install it."
    )
    logging.info(f"Default PATH: {os.environ['PATH']}")
    os.environ["PATH"] += os.pathsep + "/usr/local/bin"
    os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"
    logging.info(f"Updated PATH: {os.environ['PATH']}")
    if not is_command_available("bw"):
        logging.error("Bitwarden CLI (bw) is still not available.")
        exit(1)
else:
    logging.info("Bitwarden CLI (bw) is available.")

# Log in to Bitwarden
logging.info("Logging into Bitwarden...")
login_env = os.environ.copy()
login_env["BW_CLIENTID"] = BW_CLIENTID
login_env["BW_CLIENTSECRET"] = BW_CLIENTSECRET
if subprocess.run(["bw", "login", "--apikey"], env=login_env).returncode != 0:
    logging.error("Failed to login to Bitwarden")
    exit(1)

# Unlock the vault
logging.info("Unlocking the vault...")
unlock_env = os.environ.copy()
unlock_env["BW_PASSWORD"] = BW_PASSWORD
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
backup_file = os.path.join(SCRIPT_DIR, f"bitwarden_backup_{timestamp}.json")
encrypted_backup_file = os.path.join(BACKUP_DIR, f"bitwarden_backup_{timestamp}.zip")
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
        ["zip", "-P", ZIP_PASSWORD, "-j", encrypted_backup_file, backup_file]
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
        for f in os.listdir(BACKUP_DIR)
        if f.startswith("bitwarden_backup_") and f.endswith(".zip")
    ],
    key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
)
if len(backup_files) > MAX_BACKUPS:
    for old_backup in backup_files[: len(backup_files) - MAX_BACKUPS]:
        os.remove(os.path.join(BACKUP_DIR, old_backup))
        logging.info(f"Deleted old backup: {old_backup}")
else:
    logging.info("No old backups to delete.")

logging.info("Backup completed successfully.")
