# backup-scripts

A collection of enhanced scripts to help with backing up data with advanced management features.

## Features

- **Encrypted Backups**: All backups are encrypted with password-protected ZIP files
- **Backup Verification**: Automatic integrity checking and checksum verification
- **Metadata Tracking**: Detailed metadata stored for each backup (size, checksum, timestamp)
- **Smart Rotation**: Simple count-based or advanced retention policies (daily/weekly/monthly)
- **Backup Management**: CLI utility for listing, inspecting, and verifying backups
- **Configuration Validation**: Automatic validation of configuration files
- **Comprehensive Logging**: Detailed logging to both file and console

## Bitwarden Backup

A Python script that automatically backs up your Bitwarden vault to encrypted ZIP files with rotation management.

### Prerequisites

- Python 3.6+
- Bitwarden CLI (bw) installed and available in PATH or npx is available
- `zip` and `unzip` commands available in PATH

### Configuration

```json
{
  "BW_CLIENTID": "your_client_id",
  "BW_CLIENTSECRET": "your_client_secret",
  "BW_PASSWORD": "your_master_password",
  "BACKUP_DIR_PATH": "~/backups/bitwarden",
  "ZIP_PASSWORD": "backup_encryption_password",
  "MAX_BACKUPS": 7,
  "VERIFY_BACKUPS": true,
  "RETENTION_POLICY": {
    "daily": 7,
    "weekly": 4,
    "monthly": 12
  },
  "LOG_FILE_PATH": "~/.local/share/bw-backup/bw-backup.log"
}
```

#### Configuration Options

- `BW_CLIENTID` (required): Bitwarden API client ID
- `BW_CLIENTSECRET` (required): Bitwarden API client secret
- `BW_PASSWORD` (required): Bitwarden master password
- `BACKUP_DIR_PATH` (required): Directory where backups will be stored
- `ZIP_PASSWORD` (required): Password for encrypting backup ZIP files
- `MAX_BACKUPS` (required): Maximum number of backups to keep (used if RETENTION_POLICY is not set)
- `VERIFY_BACKUPS` (optional): Automatically verify backups after creation (default: `true`)
- `RETENTION_POLICY` (optional): Advanced retention policy with daily/weekly/monthly settings
- `LOG_FILE_PATH` (optional): Path to log file (default: `~/.local/share/bw-backup/bw-backup.log`)

### Usage

```bash
python3 bw-backup.py --config /path/to/config.json
```

## Obsidian Backup

A Python script that automatically backs up your Obsidian vault to encrypted ZIP files with rotation management.

### Prerequisites

- Python 3.6+
- `zip` and `unzip` commands available in PATH

### Configuration

```json
{
  "VAULT_PATH": "~/Documents/ObsidianVault",
  "BACKUP_DIR_PATH": "~/backups/obsidian",
  "ZIP_PASSWORD": "backup_encryption_password",
  "MAX_BACKUPS": 7,
  "VERIFY_BACKUPS": true,
  "RETENTION_POLICY": {
    "daily": 7,
    "weekly": 4,
    "monthly": 12
  },
  "LOG_FILE_PATH": "~/.local/share/ob-backup/ob-backup.log"
}
```

#### Configuration Options

- `VAULT_PATH` (required): Path to Obsidian vault directory
- `BACKUP_DIR_PATH` (required): Directory where backups will be stored
- `ZIP_PASSWORD` (required): Password for encrypting backup ZIP files
- `MAX_BACKUPS` (required): Maximum number of backups to keep (used if RETENTION_POLICY is not set)
- `VERIFY_BACKUPS` (optional): Automatically verify backups after creation (default: `true`)
- `RETENTION_POLICY` (optional): Advanced retention policy with daily/weekly/monthly settings
- `LOG_FILE_PATH` (optional): Path to log file (default: `~/.local/share/ob-backup/ob-backup.log`)

### Usage

```bash
python3 ob-backup.py --config /path/to/config.json
```

## Backup Manager

A CLI utility for managing and inspecting backups.

### Usage

#### List all backups

```bash
python3 utils/backup_manager.py --config /path/to/config.json --type bitwarden list
python3 utils/backup_manager.py --config /path/to/config.json --type obsidian list
```

#### Get detailed information about a backup

```bash
python3 utils/backup_manager.py --config /path/to/config.json --type bitwarden info --filename bitwarden_backup_2024-01-15-10-30-00.zip
```

#### Verify all backups

```bash
python3 utils/backup_manager.py --config /path/to/config.json --type bitwarden verify
python3 utils/backup_manager.py --config /path/to/config.json --type obsidian verify
```

## Retention Policies

### Simple Rotation (Default)

When `RETENTION_POLICY` is not specified, the script uses simple rotation based on `MAX_BACKUPS`. It keeps the N most recent backups and deletes older ones.

### Advanced Retention Policy

When `RETENTION_POLICY` is specified, the script uses a more sophisticated rotation strategy:

- **Daily backups**: Keep all backups from the last N days
- **Weekly backups**: Keep one backup per week for the last N weeks
- **Monthly backups**: Keep one backup per month for the last N months

Example:

```json
{
  "RETENTION_POLICY": {
    "daily": 7, // Keep all backups from last 7 days
    "weekly": 4, // Keep one backup per week for last 4 weeks
    "monthly": 12 // Keep one backup per month for last 12 months
  }
}
```

The script ensures at least `MAX_BACKUPS` backups are always kept, even if the retention policy would delete more.

## Backup Metadata

Each backup has associated metadata stored in `.backup_metadata.json` in the backup directory:

- **filename**: Backup filename
- **path**: Full path to backup file
- **timestamp**: Timestamp from filename
- **created_at**: ISO format creation timestamp
- **size**: File size in bytes
- **checksum**: SHA256 checksum of the backup file
- **verified**: Whether the backup has been verified

## Architecture

The scripts use a shared `utils/` package that provides:

- `utils/backup_utils.py`: Core backup management utilities
  - `BackupManager`: Core backup management class
  - `setup_logging()`: Centralized logging configuration
  - `validate_config()`: Configuration validation
- `utils/backup_manager.py`: CLI utility for managing backups

This architecture reduces code duplication and ensures consistent behavior across all backup scripts. The `utils/` directory contains reusable components that can be easily extended or modified.
