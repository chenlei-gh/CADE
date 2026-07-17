"""
CATIA CAA Backup and Rollback System
=====================================
Manage operation backups and rollback functionality.

Design principle:
  Every operation that modifies files creates a backup first.
  Users can rollback to any previous state.

Features:
  - Automatic backup before apply
  - Rollback to any backup point
  - List all available backups
  - Automatic cleanup of old backups
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from changeset import ChangeSet


class BackupManager:
    """Manage operation backups and rollback"""

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        self.backup_dir = self.workspace_root / ".caa_backups"
        self.backup_dir.mkdir(exist_ok=True)

    def create_backup(self, changeset: ChangeSet) -> str:
        """
        Create backup before applying changeset.

        Args:
            changeset: ChangeSet to backup

        Returns:
            backup_id: Unique backup identifier (timestamp)
        """
        backup_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[
            :17
        ]  # Include microseconds
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(parents=True, exist_ok=True)

        # Backup files that will be modified
        backed_up_files = []
        for file_path_str in changeset.modified.keys():
            file_path = Path(file_path_str)
            if file_path.exists():
                # Preserve directory structure
                rel_path = (
                    file_path.relative_to(self.workspace_root)
                    if file_path.is_absolute()
                    else file_path
                )
                backup_file = backup_path / "modified" / rel_path
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, backup_file)
                backed_up_files.append(str(rel_path))

        # Backup files that will be deleted
        for file_path in changeset.deleted:
            if file_path.exists():
                rel_path = (
                    file_path.relative_to(self.workspace_root)
                    if file_path.is_absolute()
                    else file_path
                )
                backup_file = backup_path / "deleted" / rel_path
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, backup_file)

        # Create manifest
        manifest = {
            "backup_id": backup_id,
            "timestamp": datetime.now().isoformat(),
            "action": changeset.action,
            "description": changeset.description,
            "created": list(changeset.created.keys()),
            "modified": list(changeset.modified.keys()),
            "deleted": [str(p) for p in changeset.deleted],
            "backed_up_files": backed_up_files,
        }

        manifest_file = backup_path / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return backup_id

    def rollback(self, backup_id: str) -> Dict:
        """
        Rollback to a specific backup.

        Args:
            backup_id: Backup identifier (validated for safety — P0-002)

        Returns:
            {
                "status": "success" | "error",
                "message": "...",
                "restored": {...}
            }
        """
        err = self._validate_backup_id(backup_id)
        if err:
            return {"status": "error", "message": err}

        backup_path = self.backup_dir / backup_id

        if not backup_path.exists():
            return {
                "status": "error",
                "message": f"Backup '{backup_id}' not found",
                "available_backups": [b["backup_id"] for b in self.list_backups()],
            }

        # Read manifest
        manifest_file = backup_path / "manifest.json"
        if not manifest_file.exists():
            return {
                "status": "error",
                "message": f"Backup '{backup_id}' is corrupted (missing manifest)",
            }

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        restored = {
            "deleted_created_files": [],
            "restored_modified_files": [],
            "restored_deleted_files": [],
        }

        # 1. Delete files that were created
        for created_file in manifest["created"]:
            file_path = self.workspace_root / created_file
            if file_path.exists():
                file_path.unlink()
                restored["deleted_created_files"].append(created_file)

        # 2. Restore modified files
        modified_dir = backup_path / "modified"
        if modified_dir.exists():
            for backup_file in modified_dir.rglob("*"):
                if backup_file.is_file():
                    rel_path = backup_file.relative_to(modified_dir)
                    target_file = self.workspace_root / rel_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, target_file)
                    restored["restored_modified_files"].append(str(rel_path))

        # 3. Restore deleted files
        deleted_dir = backup_path / "deleted"
        if deleted_dir.exists():
            for backup_file in deleted_dir.rglob("*"):
                if backup_file.is_file():
                    rel_path = backup_file.relative_to(deleted_dir)
                    target_file = self.workspace_root / rel_path
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, target_file)
                    restored["restored_deleted_files"].append(str(rel_path))

        return {
            "status": "success",
            "message": f"Successfully rolled back to {backup_id}",
            "backup_id": backup_id,
            "action": manifest["action"],
            "restored": restored,
        }

    def list_backups(self) -> List[Dict]:
        """
        List all available backups.

        Returns:
            List of backup manifests sorted by timestamp (newest first)
        """
        backups = []

        if not self.backup_dir.exists():
            return backups

        for backup_path in self.backup_dir.iterdir():
            if backup_path.is_dir():
                manifest_file = backup_path / "manifest.json"
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                            backups.append(manifest)
                    except Exception:
                        # Skip corrupted backups
                        pass

        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return backups

    def _validate_backup_id(self, backup_id: str) -> Optional[str]:
        """Validate backup_id is safe — rejects path traversal (P0-002 fix).

        Returns error message string if invalid, None if valid.
        """
        import re

        # Must match timestamp-like format: repair_YYYYMMDD_HHMMSS
        # or numeric timestamp YYYYMMDD_HHMMSS[_micro]
        if not re.match(r'^[a-zA-Z0-9_.]{8,40}$', backup_id):
            return f"Invalid backup_id format: '{backup_id}'. Expected: timestamp pattern."

        # Reject path separators and traversal
        if "/" in backup_id or "\\" in backup_id or ".." in backup_id:
            return f"Invalid backup_id (path separators): '{backup_id}'"

        # Ensure resolved path is within backup_dir
        backup_path = (self.backup_dir / backup_id).resolve()
        try:
            if not backup_path.is_relative_to(self.backup_dir.resolve()):
                return f"Invalid backup_id (outside backup dir): '{backup_id}'"
        except ValueError:
            return f"Invalid backup_id (cross-drive): '{backup_id}'"

        return None

    def delete_backup(self, backup_id: str) -> Dict:
        """
        Delete a specific backup.

        Args:
            backup_id: Backup identifier (timestamp format only)

        Returns:
            {"status": "success" | "error", "message": "..."}
        """
        err = self._validate_backup_id(backup_id)
        if err:
            return {"status": "error", "message": err}

        backup_path = self.backup_dir / backup_id

        if not backup_path.exists():
            return {"status": "error", "message": f"Backup '{backup_id}' not found"}

        shutil.rmtree(backup_path)

        return {"status": "success", "message": f"Backup '{backup_id}' deleted"}

    def cleanup_old_backups(self, keep_count: int = 10) -> Dict:
        """
        Delete old backups, keeping only the most recent ones.

        Args:
            keep_count: Number of backups to keep

        Returns:
            {"status": "success", "deleted": [...], "kept": [...]}
        """
        backups = self.list_backups()

        deleted = []
        kept = []

        for i, backup in enumerate(backups):
            backup_id = backup["backup_id"]
            if i < keep_count:
                kept.append(backup_id)
            else:
                self.delete_backup(backup_id)
                deleted.append(backup_id)

        return {
            "status": "success",
            "message": f"Kept {len(kept)} backups, deleted {len(deleted)}",
            "deleted": deleted,
            "kept": kept,
        }


# ═══════════════════════════════════════════════════════════════════
#  Rollback API Functions
# ═══════════════════════════════════════════════════════════════════


def rollback_operation(workspace_root: Path, backup_id: str) -> Dict:
    """
    Rollback to a specific backup point.

    Args:
        workspace_root: Workspace root directory
        backup_id: Backup identifier (e.g., "20260707_143022")

    Returns:
        {
            "status": "success",
            "message": "Successfully rolled back to ...",
            "backup_id": "...",
            "action": "create_command",
            "restored": {
                "deleted_created_files": [...],
                "restored_modified_files": [...],
                "restored_deleted_files": [...]
            }
        }
    """
    backup_mgr = BackupManager(workspace_root)
    return backup_mgr.rollback(backup_id)


def list_rollback_points(workspace_root: Path) -> Dict:
    """
    List all available rollback points.

    Args:
        workspace_root: Workspace root directory

    Returns:
        {
            "status": "ok",
            "backups": [
                {
                    "backup_id": "20260707_143022",
                    "timestamp": "2026-07-07T14:30:22",
                    "action": "create_executable_command",
                    "description": "...",
                    "created": [...],
                    "modified": [...]
                }
            ],
            "count": 5
        }
    """
    backup_mgr = BackupManager(workspace_root)
    backups = backup_mgr.list_backups()

    return {
        "status": "ok",
        "backups": backups,
        "count": len(backups),
        "message": f"Found {len(backups)} rollback points",
    }


def cleanup_backups(workspace_root: Path, keep_count: int = 10) -> Dict:
    """
    Clean up old backups.

    Args:
        workspace_root: Workspace root directory
        keep_count: Number of recent backups to keep

    Returns:
        {
            "status": "success",
            "message": "...",
            "deleted": [...],
            "kept": [...]
        }
    """
    backup_mgr = BackupManager(workspace_root)
    return backup_mgr.cleanup_old_backups(keep_count)


# ═══════════════════════════════════════════════════════════════════
#  CLI (for testing)
# ═══════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python backup.py <command> [args...]")
        print("\nCommands:")
        print("  list                     - List all rollback points")
        print("  rollback <backup_id>     - Rollback to backup")
        print("  cleanup [keep_count]     - Clean up old backups")
        sys.exit(1)

    command = sys.argv[1]
    workspace = Path(".")

    if command == "list":
        result = list_rollback_points(workspace)
        print(json.dumps(result, indent=2))

    elif command == "rollback":
        if len(sys.argv) < 3:
            print("Usage: rollback <backup_id>")
            sys.exit(1)
        backup_id = sys.argv[2]
        result = rollback_operation(workspace, backup_id)
        print(json.dumps(result, indent=2))

    elif command == "cleanup":
        keep_count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        result = cleanup_backups(workspace, keep_count)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
