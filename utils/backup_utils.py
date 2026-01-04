#!/usr/bin/env python3
"""
Shared utilities for backup scripts.
Provides common functionality for backup management, verification, and rotation.
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BackupManager:
    """Manages backup operations including creation, verification, and rotation."""

    def __init__(
        self,
        backup_dir: str,
        backup_prefix: str,
        zip_password: str,
        max_backups: int = 7,
        verify_backups: bool = True,
        retention_policy: Optional[Dict] = None,
    ):
        """
        Initialize the BackupManager.

        Args:
            backup_dir: Directory where backups are stored
            backup_prefix: Prefix for backup filenames
            zip_password: Password for encrypted ZIP files
            max_backups: Maximum number of backups to keep (simple rotation)
            verify_backups: Whether to verify backups after creation
            retention_policy: Advanced retention policy (e.g., {"daily": 7, "weekly": 4, "monthly": 12})
        """
        self.backup_dir = os.path.expanduser(backup_dir)
        self.backup_prefix = backup_prefix
        self.zip_password = zip_password
        self.max_backups = max_backups
        self.verify_backups = verify_backups
        self.retention_policy = retention_policy or {}
        self.metadata_file = os.path.join(self.backup_dir, ".backup_metadata.json")

        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_encrypted_backup(
        self, source_path: str, is_file: bool = True
    ) -> Tuple[str, Dict]:
        """
        Create an encrypted ZIP backup.

        Args:
            source_path: Path to file or directory to backup
            is_file: True if source_path is a file, False if directory

        Returns:
            Tuple of (backup_file_path, metadata_dict)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        backup_filename = f"{self.backup_prefix}_{timestamp}.zip"
        backup_path = os.path.join(self.backup_dir, backup_filename)

        # Create temporary directory for intermediate files
        temp_dir = tempfile.mkdtemp(prefix="backup-")
        try:
            if is_file:
                # For files, copy to temp dir first
                temp_source = os.path.join(temp_dir, os.path.basename(source_path))
                shutil.copy2(source_path, temp_source)
                zip_source = temp_source
                zip_cwd = temp_dir
            else:
                # For directories, copy to temp dir
                temp_source = os.path.join(
                    temp_dir, os.path.basename(source_path.rstrip("/"))
                )
                shutil.copytree(source_path, temp_source)
                zip_source = os.path.basename(temp_source)
                zip_cwd = temp_dir

            # Create encrypted ZIP
            zip_args = ["zip", "-P", self.zip_password, "-r", backup_path]
            if is_file:
                zip_args.append("-j")  # Junk paths for single file
            zip_args.append(zip_source)

            result = subprocess.run(
                zip_args, cwd=zip_cwd, capture_output=True, text=True
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to create encrypted backup: {result.stderr}"
                )

            # Get backup metadata
            backup_size = os.path.getsize(backup_path)
            checksum = self._calculate_checksum(backup_path)

            metadata = {
                "filename": backup_filename,
                "path": backup_path,
                "timestamp": timestamp,
                "created_at": datetime.now().isoformat(),
                "size": backup_size,
                "checksum": checksum,
                "verified": False,
            }

            # Verify backup if requested
            if self.verify_backups:
                if self.verify_backup_integrity(backup_path):
                    metadata["verified"] = True
                    logging.info(f"Backup verified successfully: {backup_filename}")
                else:
                    logging.warning(f"Backup verification failed: {backup_filename}")
                    # Optionally remove failed backup
                    # os.remove(backup_path)
                    # raise RuntimeError("Backup verification failed")

            # Save metadata
            self._save_metadata(metadata)

            return backup_path, metadata

        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def verify_backup_integrity(self, backup_path: str) -> bool:
        """
        Verify the integrity of a backup file.

        Args:
            backup_path: Path to the backup file

        Returns:
            True if backup is valid, False otherwise
        """
        if not os.path.exists(backup_path):
            logging.error(f"Backup file does not exist: {backup_path}")
            return False

        # Test ZIP integrity
        result = subprocess.run(
            ["unzip", "-t", "-P", self.zip_password, backup_path],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logging.error(f"ZIP integrity check failed: {result.stderr}")
            return False

        return True

    def _calculate_checksum(self, file_path: str, algorithm: str = "sha256") -> str:
        """Calculate checksum of a file."""
        hash_obj = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    def _save_metadata(self, metadata: Dict):
        """Save backup metadata to JSON file."""
        all_metadata = self._load_metadata()
        all_metadata[metadata["filename"]] = metadata
        with open(self.metadata_file, "w") as f:
            json.dump(all_metadata, f, indent=2)

    def _load_metadata(self) -> Dict:
        """Load backup metadata from JSON file."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Failed to load metadata: {e}")
                return {}
        return {}

    def list_backups(self) -> List[Dict]:
        """List all backups with their metadata."""
        all_metadata = self._load_metadata()
        backups = []

        # Get all backup files
        backup_files = [
            f
            for f in os.listdir(self.backup_dir)
            if f.startswith(self.backup_prefix) and f.endswith(".zip")
        ]

        for backup_file in backup_files:
            backup_path = os.path.join(self.backup_dir, backup_file)
            if backup_file in all_metadata:
                metadata = all_metadata[backup_file].copy()
            else:
                # Generate metadata for files not in metadata file
                metadata = {
                    "filename": backup_file,
                    "path": backup_path,
                    "timestamp": self._extract_timestamp(backup_file),
                    "created_at": datetime.fromtimestamp(
                        os.path.getmtime(backup_path)
                    ).isoformat(),
                    "size": os.path.getsize(backup_path),
                    "checksum": None,
                    "verified": False,
                }

            # Update size if it changed
            if os.path.exists(backup_path):
                metadata["size"] = os.path.getsize(backup_path)
                backups.append(metadata)

        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return backups

    def _extract_timestamp(self, filename: str) -> str:
        """Extract timestamp from backup filename."""
        # Format: prefix_YYYY-MM-DD-HH-MM-SS.zip
        try:
            parts = filename.replace(".zip", "").split("_")
            if len(parts) >= 2:
                return "_".join(parts[1:])
        except Exception:
            pass
        return ""

    def rotate_backups(self):
        """
        Rotate backups based on retention policy or simple max_backups.

        If retention_policy is set, uses advanced rotation.
        Otherwise, uses simple max_backups rotation.
        """
        if self.retention_policy:
            self._rotate_with_policy()
        else:
            self._rotate_simple()

    def _rotate_simple(self):
        """Simple rotation: keep only the N most recent backups."""
        backups = self.list_backups()
        if len(backups) > self.max_backups:
            backups_to_delete = backups[self.max_backups :]
            for backup in backups_to_delete:
                backup_path = backup["path"]
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                    logging.info(f"Deleted old backup: {backup['filename']}")
                    # Remove from metadata
                    self._remove_from_metadata(backup["filename"])

    def _rotate_with_policy(self):
        """Advanced rotation based on retention policy."""
        backups = self.list_backups()
        if not backups:
            return

        # Group backups by date
        now = datetime.now()
        to_keep = []
        to_delete = []

        for backup in backups:
            try:
                created = datetime.fromisoformat(backup["created_at"])
                age_days = (now - created).days

                # Determine which category this backup falls into
                if age_days == 0:
                    # Today's backup - always keep
                    to_keep.append(backup)
                elif age_days <= self.retention_policy.get("daily", 0):
                    # Daily backups
                    to_keep.append(backup)
                elif age_days <= self.retention_policy.get("daily", 0) + (
                    self.retention_policy.get("weekly", 0) * 7
                ):
                    # Weekly backups - keep one per week
                    week_num = age_days // 7
                    if week_num not in [b.get("week_num") for b in to_keep]:
                        backup["week_num"] = week_num
                        to_keep.append(backup)
                    else:
                        to_delete.append(backup)
                else:
                    # Monthly backups - keep one per month
                    month_num = age_days // 30
                    if month_num not in [b.get("month_num") for b in to_keep]:
                        backup["month_num"] = month_num
                        to_keep.append(backup)
                    else:
                        to_delete.append(backup)

            except Exception as e:
                logging.warning(f"Error processing backup {backup['filename']}: {e}")
                to_delete.append(backup)

        # Ensure we keep at least max_backups
        if len(to_keep) < self.max_backups:
            # Add more recent backups to keep list
            remaining = [b for b in backups if b not in to_keep and b not in to_delete]
            to_keep.extend(remaining[: self.max_backups - len(to_keep)])

        # Delete backups not in keep list
        for backup in backups:
            if backup not in to_keep:
                backup_path = backup["path"]
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                    logging.info(f"Deleted old backup: {backup['filename']}")
                    self._remove_from_metadata(backup["filename"])

    def _remove_from_metadata(self, filename: str):
        """Remove a backup from metadata file."""
        all_metadata = self._load_metadata()
        if filename in all_metadata:
            del all_metadata[filename]
            with open(self.metadata_file, "w") as f:
                json.dump(all_metadata, f, indent=2)

    def get_backup_info(self, filename: str) -> Optional[Dict]:
        """Get detailed information about a specific backup."""
        backups = self.list_backups()
        for backup in backups:
            if backup["filename"] == filename:
                return backup
        return None

    def verify_all_backups(self) -> Dict[str, bool]:
        """Verify integrity of all backups."""
        backups = self.list_backups()
        results = {}
        for backup in backups:
            backup_path = backup["path"]
            if os.path.exists(backup_path):
                results[backup["filename"]] = self.verify_backup_integrity(backup_path)
            else:
                results[backup["filename"]] = False
        return results


def setup_logging(log_file_path: str, level: int = logging.INFO):
    """
    Setup logging configuration.

    Args:
        log_file_path: Path to log file
        level: Logging level
    """
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s.%(msecs)03d [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler(log_file_path), logging.StreamHandler()],
        force=True,  # Override any existing configuration
    )


def validate_config(
    config: Dict, required_keys: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Validate configuration dictionary.

    Args:
        config: Configuration dictionary
        required_keys: List of required keys

    Returns:
        Tuple of (is_valid, error_message)
    """
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        return False, f"Missing required configuration keys: {', '.join(missing_keys)}"

    # Validate paths
    if "BACKUP_DIR_PATH" in config:
        backup_dir = os.path.expanduser(config["BACKUP_DIR_PATH"])
        parent_dir = os.path.dirname(backup_dir)
        if parent_dir and not os.path.exists(parent_dir):
            return False, f"Parent directory does not exist: {parent_dir}"

    # Validate max_backups
    if "MAX_BACKUPS" in config:
        try:
            max_backups = int(config["MAX_BACKUPS"])
            if max_backups < 1:
                return False, "MAX_BACKUPS must be at least 1"
        except (ValueError, TypeError):
            return False, "MAX_BACKUPS must be a valid integer"

    return True, None
