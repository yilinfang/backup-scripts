#!/usr/bin/env python3

import argparse
import json
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
    LOG_FILE = os.path.expanduser(config["LOG_FILE"])

# Ensure log directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


# Function to log messages
def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"{timestamp} - {message}"
    print(log_message)
    with open(LOG_FILE, "a") as log_file:
        log_file.write(log_message + "\n")


# Ensure the backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)


# Check if a command exists
def is_command_available(command):
    return shutil.which(command) is not None


# Ensure Bitwarden CLI is installed
if not is_command_available("bw"):
    log(
        "ERROR: Bitwarden CLI (bw) could not be found in default PATH. Please install it."
    )
    # show default path in log
    log(f"INFO: Default PATH: {os.environ['PATH']}")
    # export /usr/local/bin/ to PATH
    os.environ["PATH"] += os.pathsep + "/usr/local/bin"
    # export /opt/homebrew/bin/ to PATH
    os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"
    log(f"INFO: Updated PATH: {os.environ['PATH']}")
    if not is_command_available("bw"):
        log("ERROR: Bitwarden CLI (bw) is still not available.")
        exit(1)
else:
    log("INFO: Bitwarden CLI (bw) is available.")

# Log in to Bitwarden
log("INFO: Logging into Bitwarden...")
login_env = os.environ.copy()
login_env["BW_CLIENTID"] = BW_CLIENTID
login_env["BW_CLIENTSECRET"] = BW_CLIENTSECRET
if subprocess.run(["bw", "login", "--apikey"], env=login_env).returncode != 0:
    log("ERROR: Failed to login to Bitwarden")
    exit(1)

# Unlock the vault
log("INFO: Unlocking the vault...")
unlock_env = os.environ.copy()
unlock_env["BW_PASSWORD"] = BW_PASSWORD
result = subprocess.run(
    ["bw", "unlock", "--passwordenv", "BW_PASSWORD", "--raw"],
    capture_output=True,
    text=True,
    env=unlock_env,
)
if result.returncode != 0:
    log("ERROR: Failed to unlock the vault")
    exit(1)
session = result.stdout.strip()
log("INFO: Vault unlocked successfully.")

# Sync the vault
log("INFO: Syncing the vault...")
if subprocess.run(["bw", "sync", "--session", session]).returncode != 0:
    log("ERROR: Failed to sync the vault")
    exit(1)

# Export the vault
timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
backup_file = os.path.join(SCRIPT_DIR, f"bitwarden_backup_{timestamp}.json")
encrypted_backup_file = os.path.join(BACKUP_DIR, f"bitwarden_backup_{timestamp}.zip")
log(f"INFO: Exporting vault to {backup_file}...")
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
    log("ERROR: Failed to export the vault")
    exit(1)

# Encrypt the backup
log(f"INFO: Encrypting backup to {encrypted_backup_file}...")
if (
    subprocess.run(
        ["zip", "-P", ZIP_PASSWORD, "-j", encrypted_backup_file, backup_file]
    ).returncode
    != 0
):
    log("ERROR: Failed to encrypt the backup")
    exit(1)
os.remove(backup_file)
log("INFO: Plain backup file removed after encryption.")

# Log out from Bitwarden
log("INFO: Logging out from Bitwarden...")
if subprocess.run(["bw", "logout"]).returncode != 0:
    log("ERROR: Failed to log out from Bitwarden")
    exit(1)

# Cleanup old backups
log("INFO: Cleaning up old backups...")
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
        log(f"INFO: Deleted old backup: {old_backup}")
else:
    log("INFO: No old backups to delete.")

log("INFO: Backup completed successfully.")
