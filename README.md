# backup-scripts

A collection of scripts to help with backing up data.

## Bitwarden

A Python script that automatically backs up your Bitwarden vault to encrypted ZIP files with rotation management.

### Prerequisites

- Python 3.6+
- Bitwarden CLI (bw) installed and available in PATH or npx is available

### Configuration

```json
{
  "BW_CLIENTID": "your_client_id",
  "BW_CLIENTSECRET": "your_client_secret",
  "BW_PASSWORD": "your_master_password",
  "BACKUP_DIR_PATH": "~/backups/bitwarden",
  "ZIP_PASSWORD": "backup_encryption_password",
  "MAX_BACKUPS": 7,
  "LOG_FILE_PATH": "~/.local/share/bw-backup/bw-backup.log"
}
```

### Usage

```bash
python3 bw-backup.py --config /path/to/config.json
```
