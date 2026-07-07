"""
CATIA CAA ChangeSet System
==========================
Preview-before-apply pattern for all workspace modifications.

Design principle:
  Every action produces a ChangeSet first.
  AI reviews the ChangeSet before applying.
  All actions are reversible (rollback).

ChangeSet structure:
  {
    "created":  [FilePath, ...],   # New files to create
    "modified": [FilePath, ...],   # Existing files to modify
    "deleted":  [FilePath, ...],   # Files to delete
    "patches":  {FilePath: Patch}, # Inline edits for modified files
    "warnings": [str, ...],        # Non-blocking warnings
    "metadata": {...},             # Action-specific info
  }
"""

from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Patch ───────────────────────────────────────────────────────


@dataclass
class Patch:
    """A single inline edit to an existing file"""

    file: Path
    operation: str  # "insert_after" | "replace" | "append" | "delete_lines"
    target: str  # line marker or regex
    content: str  # content to insert/replace
    line_start: Optional[int] = None
    line_end: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "file": str(self.file),
            "operation": self.operation,
            "target": self.target,
            "content_preview": self.content[:80] + "..."
            if len(self.content) > 80
            else self.content,
        }


# ─── ChangeSet ───────────────────────────────────────────────────


@dataclass
class ChangeSet:
    """Preview-before-apply change log for a development action"""

    action: str  # "create_command", "delete_module", etc.
    description: str

    created: Dict[str, str] = field(default_factory=dict)  # path → content
    modified: Dict[str, str] = field(default_factory=dict)  # path → new_content
    deleted: List[Path] = field(default_factory=list)
    patches: List[Patch] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    _backups: Dict[str, str] = field(default_factory=dict, repr=False)

    def add_create(self, path: Path, content: str):
        self.created[str(path)] = content

    def add_create_file(
        self, path: Path, template_path: Path, replacements: Dict[str, str] = None
    ):
        """Add a file to create by reading a template and applying replacements"""
        content = template_path.read_text(encoding="utf-8", errors="replace")
        if replacements:
            for k, v in replacements.items():
                content = content.replace(k, v)
        self.add_create(path, content)

    def add_modify(self, path: Path, new_content: str):
        self.modified[str(path)] = new_content

    def add_delete(self, path: Path):
        self.deleted.append(path)

    def add_patch(self, patch: Patch):
        self.patches.append(patch)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    @property
    def is_empty(self) -> bool:
        return not (self.created or self.modified or self.deleted or self.patches)

    @property
    def total_changes(self) -> int:
        return (
            len(self.created)
            + len(self.modified)
            + len(self.deleted)
            + len(self.patches)
        )

    def preview(self) -> str:
        """Human-readable preview of the ChangeSet"""
        lines = [f"ChangeSet: {self.action}", f"  {self.description}", ""]

        if self.created:
            lines.append(f"  ══ Created ({len(self.created)} files) ══")
            for p in self.created:
                lines.append(f"    + {p}")

        if self.modified:
            lines.append(f"  ══ Modified ({len(self.modified)} files) ══")
            for p in self.modified:
                lines.append(f"    ~ {p}")

        if self.patches:
            lines.append(f"  ══ Patches ({len(self.patches)}) ══")
            for p in self.patches:
                lines.append(f"    ⟳ {p.to_dict()['file']}: {p.operation}")

        if self.deleted:
            lines.append(f"  ══ Deleted ({len(self.deleted)} files) ══")
            for p in self.deleted:
                lines.append(f"    - {p}")

        if self.warnings:
            lines.append(f"  ══ Warnings ({len(self.warnings)}) ══")
            for w in self.warnings:
                lines.append(f"    ⚠ {w}")

        return "\n".join(lines)

    def apply(
        self, dry_run: bool = False, workspace_root: Path = None
    ) -> Dict[str, Any]:
        """Apply all changes. If dry_run=True, only validate.

        If workspace_root is provided, a backup is automatically created
        before applying changes, and rollback_id is included in the result.
        """
        result = {
            "action": self.action,
            "status": "applied",
            "created": [],
            "modified": [],
            "deleted": [],
            "patched": [],
            "warnings": self.warnings.copy(),
            "rollback_id": None,
        }

        if dry_run:
            result["status"] = "dry_run"
            result["preview"] = {
                "created": list(self.created.keys()),
                "modified": list(self.modified.keys()),
                "deleted": [str(d) for d in self.deleted],
                "patches": [p.to_dict() for p in self.patches],
            }
            return result

        # 0. Create backup if workspace_root provided
        if workspace_root:
            try:
                from backup import BackupManager

                bm = BackupManager(workspace_root)
                result["rollback_id"] = bm.create_backup(self)
            except ImportError:
                pass  # backup module not available, skip

        # 1. Backup modified files
        for path_str in self.modified:
            p = Path(path_str)
            if p.exists():
                self._backups[path_str] = p.read_text(
                    encoding="utf-8", errors="replace"
                )

        # 2. Create new files
        for path_str, content in self.created.items():
            try:
                p = Path(path_str)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8", newline="\r\n")
                result["created"].append(path_str)
            except Exception as e:
                result["warnings"].append(f"Failed to create {path_str}: {e}")

        # 3. Apply patches
        for patch in self.patches:
            try:
                self._apply_patch(patch)
                result["patched"].append(str(patch.file))
            except Exception as e:
                result["warnings"].append(f"Failed to patch {patch.file}: {e}")

        # 4. Modify files
        for path_str, content in self.modified.items():
            try:
                Path(path_str).write_text(content, encoding="utf-8", newline="\r\n")
                result["modified"].append(path_str)
            except Exception as e:
                result["warnings"].append(f"Failed to modify {path_str}: {e}")

        # 5. Delete files
        for p in self.deleted:
            try:
                if p.exists():
                    p.unlink()
                    result["deleted"].append(str(p))
            except Exception as e:
                result["warnings"].append(f"Failed to delete {p}: {e}")

        return result

    def rollback(self) -> Dict[str, Any]:
        """Undo all changes (reverse of apply)"""
        result = {
            "action": f"rollback:{self.action}",
            "status": "rolled_back",
            "errors": [],
        }

        # Restore modified files from backups
        for path_str, original in self._backups.items():
            try:
                Path(path_str).write_text(original, encoding="utf-8", newline="\r\n")
            except Exception as e:
                result["errors"].append(f"Failed to restore {path_str}: {e}")

        # Remove created files
        for path_str in self.created:
            try:
                p = Path(path_str)
                if p.exists():
                    p.unlink()
            except Exception as e:
                result["errors"].append(f"Failed to remove {path_str}: {e}")

        # Re-create deleted files (from backups if available)
        # Note: full file recovery from delete not supported without external backup

        return result

    def _apply_patch(self, patch: Patch):
        """Apply a single inline patch to a file"""
        if not patch.file.exists():
            raise FileNotFoundError(f"Patch target not found: {patch.file}")

        content = patch.file.read_text(encoding="utf-8", errors="replace")
        self._backups[str(patch.file)] = content
        lines = content.split("\n")

        if patch.operation == "insert_after":
            for i, line in enumerate(lines):
                if patch.target in line:
                    lines.insert(i + 1, patch.content)
                    break

        elif patch.operation == "append":
            lines.append(patch.content)

        elif patch.operation == "replace":
            new_lines = []
            for line in lines:
                if patch.target in line:
                    new_lines.append(patch.content)
                else:
                    new_lines.append(line)
            lines = new_lines

        elif patch.operation == "delete_lines":
            if patch.line_start is not None and patch.line_end is not None:
                del lines[patch.line_start - 1 : patch.line_end]

        patch.file.write_text("\n".join(lines), encoding="utf-8", newline="\r\n")

    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "description": self.description,
            "created": dict(self.created),  # Preserve path → content
            "modified": dict(self.modified),  # Preserve path → content
            "deleted": [str(d) for d in self.deleted],
            "patches": [p.to_dict() for p in self.patches],
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
            "total_changes": self.total_changes,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ChangeSet":
        """Reconstruct ChangeSet from dict (reverse of to_dict)"""
        cs = cls(
            action=d.get("action", "unknown"), description=d.get("description", "")
        )
        cs.created = dict(d.get("created", {}))
        cs.modified = dict(d.get("modified", {}))
        cs.deleted = [Path(p) for p in d.get("deleted", [])]
        cs.patches = []  # Patches can't be fully reconstructed from dict
        cs.warnings = list(d.get("warnings", []))
        cs.metadata = dict(d.get("metadata", {}))
        return cs

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ─── Helpers ─────────────────────────────────────────────────────


def diff_content(old: str, new: str, context: int = 3) -> str:
    """Generate a unified diff between old and new content"""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines, fromfile="before", tofile="after", n=context
    )
    return "".join(diff)


def merge_changesets(*changesets: ChangeSet) -> ChangeSet:
    """Merge multiple ChangeSets into one"""
    merged = ChangeSet(action="merged", description="Merged changeset")
    for cs in changesets:
        merged.created.update(cs.created)
        merged.modified.update(cs.modified)
        merged.deleted.extend(cs.deleted)
        merged.patches.extend(cs.patches)
        merged.warnings.extend(cs.warnings)
    return merged
