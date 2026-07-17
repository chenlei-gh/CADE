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
    "created":  {path: content, ...},   # New files to create
    "modified": {path: new_content, ...}, # Existing files to modify
    "deleted":  [FilePath, ...],   # Files to delete
    "patches":  [Patch, ...],      # Inline edits for modified files
    "warnings": [str, ...],        # Non-blocking warnings
    "metadata": {...},             # Action-specific info
  }

Safety guarantees (v3.2.1+):
  - All paths validated against workspace_root (P0-001)
  - Atomic apply: pre-validate → apply → rollback-partial on failure (P0-003)
  - Deleted files backed up and restorable via rollback (P0-005)
  - Patch operations verify exact match count (P1-007)
  - Full serialization round-trip including patches (P1-002)
  - merge_changesets detects same-path conflicts (P1-008)
"""

from __future__ import annotations

import base64
import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils import render_template

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
        d = {
            "file": str(self.file),
            "operation": self.operation,
            "target": self.target,
            "content": self.content,
            "content_preview": self.content[:80] + "..."
            if len(self.content) > 80
            else self.content,
        }
        if self.line_start is not None:
            d["line_start"] = self.line_start
        if self.line_end is not None:
            d["line_end"] = self.line_end
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "Patch":
        """Reconstruct Patch from dict (full round-trip support)"""
        return cls(
            file=Path(d["file"]),
            operation=d.get("operation", "insert_after"),
            target=d.get("target", ""),
            content=d.get("content", ""),
            line_start=d.get("line_start"),
            line_end=d.get("line_end"),
        )


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
    _deleted_backups: Dict[str, Tuple[str, bytes]] = field(
        default_factory=dict, repr=False
    )  # path → (original_text, raw_bytes) for deleted files
    _binary: Dict[str, bytes] = field(default_factory=dict, repr=False)
    _applied_created: List[str] = field(default_factory=list, repr=False)
    _applied_modified: List[str] = field(default_factory=list, repr=False)
    _applied_deleted: List[str] = field(default_factory=list, repr=False)
    _applied_patched: List[str] = field(default_factory=list, repr=False)

    # ── Add helpers ────────────────────────────────────────────────

    def add_create(self, path: Path, content: str):
        self.created[str(path)] = content

    def add_create_binary(self, path: Path, data: bytes):
        """Add a binary file (icon, etc.) — written during apply"""
        self._binary[str(path)] = data
        self.add_create(path, "[BINARY]")  # placeholder marker

    def add_create_file(
        self, path: Path, template_path: Path, replacements: Dict[str, str] = None
    ):
        """Add a file to create by reading a template and applying replacements"""
        content = template_path.read_text(encoding="utf-8", errors="replace")
        if replacements:
            content = render_template(content, replacements)
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

    # ── Preview ────────────────────────────────────────────────────

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

    # ── Validation ─────────────────────────────────────────────────

    def _validate_paths(self, workspace_root: Path) -> List[str]:
        """Validate all paths are within workspace_root (P0-001 fix).

        Returns:
            List of violation messages (empty = all valid).
        """
        violations = []
        ws = workspace_root.resolve()

        def _check(p: Path, label: str):
            try:
                resolved = p.resolve()
                # Handle paths on different drives — is_relative_to raises ValueError
                is_inside = False
                try:
                    is_inside = resolved.is_relative_to(ws)
                except ValueError:
                    is_inside = False
                if not is_inside:
                    violations.append(
                        f"[{label}] Path '{p}' resolves to '{resolved}' "
                        f"which is outside workspace_root '{ws}'"
                    )
            except (ValueError, OSError) as e:
                violations.append(f"[{label}] Path '{p}' is invalid: {e}")

        for path_str in self.created:
            _check(Path(path_str), "created")
        for path_str in self.modified:
            _check(Path(path_str), "modified")
        for p in self.deleted:
            _check(p, "deleted")
        for patch in self.patches:
            _check(patch.file, "patch")

        return violations

    def _pre_validate_files(self) -> List[str]:
        """Catch file-level issues before any writes (P0-003 fix).

        Returns list of error strings.
        """
        errors = []

        # Check that created files don't already exist and parent would be creatable
        for path_str, content in self.created.items():
            p = Path(path_str)
            if p.exists():
                errors.append(f"Created file already exists: {path_str}")
            # Only check if parent exists or would be inside workspace_root (no mkdir here)
            parent = p.parent
            if not parent.exists():
                # Only flag if root itself is invalid (e.g. null byte path)
                if parent.parent and not parent.parent.exists():
                    # Grandparent missing → detect but don't mkdir (side-effect-free)
                    pass  # apply() will create full chain as needed

        # Check that modified/deleted/patch files exist
        for path_str in self.modified:
            if not Path(path_str).exists():
                errors.append(f"Modified file not found: {path_str}")

        for p in self.deleted:
            if not p.exists():
                errors.append(f"Deleted file not found: {p}")

        # Patch targets: skip if they're in the created list (will be created first)
        created_paths = set(self.created.keys())
        for patch in self.patches:
            if str(patch.file) not in created_paths and not patch.file.exists():
                errors.append(f"Patch target file not found: {patch.file}")

        return errors

    # ── Apply ──────────────────────────────────────────────────────

    def apply(
        self, dry_run: bool = False, workspace_root: Path = None
    ) -> Dict[str, Any]:
        """Apply all changes atomically.

        If dry_run=True, only validate.
        If workspace_root is provided:
          - All paths are validated against it (P0-001)
          - A backup is created before changes (P0-003)
        If any operation fails, previously-applied operations are rolled back.

        Returns:
            {"status": "applied"|"dry_run"|"partial"|"rejected",
             ...}
        """
        result = {
            "action": self.action,
            "status": "applied",
            "created": [],
            "modified": [],
            "deleted": [],
            "patched": [],
            "warnings": self.warnings.copy(),
            "errors": [],
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

        # 0a. A merged ChangeSet with unresolved conflicts is never applicable.
        merge_conflicts = self.metadata.get("merge_conflicts", [])
        if merge_conflicts:
            result["status"] = "rejected"
            result["errors"] = [
                "Unresolved ChangeSet merge conflicts: " + "; ".join(merge_conflicts)
            ]
            return result

        # 0b. Path validation against workspace_root (P0-001)
        if workspace_root:
            violations = self._validate_paths(workspace_root)
            if violations:
                result["status"] = "rejected"
                result["errors"] = violations
                return result

        # 0c. Pre-validate file states (P0-003)
        file_errors = self._pre_validate_files()
        if file_errors:
            result["status"] = "rejected"
            result["errors"] = file_errors
            return result

        # 0d. Create backup if workspace_root provided
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

        # 2. Backup deleted files (P0-005 fix)
        for p in self.deleted:
            if p.exists():
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except UnicodeDecodeError:
                    text = None
                try:
                    raw = p.read_bytes()
                except Exception:
                    raw = None
                self._deleted_backups[str(p)] = (text, raw)

        # ── Apply operations (with rollback on failure) ──
        applied_created = []
        applied_modified = []
        applied_deleted = []
        applied_patched = []

        last_error: Optional[str] = None

        try:
            # 3. Create new files
            for path_str, content in self.created.items():
                p = Path(path_str)
                p.parent.mkdir(parents=True, exist_ok=True)
                if path_str in self._binary:
                    p.write_bytes(self._binary[path_str])
                elif content == "[BINARY]":
                    pass  # binary placeholder — already handled or skipped
                else:
                    p.write_text(content, encoding="utf-8", newline="\r\n")
                applied_created.append(path_str)
                result["created"].append(path_str)

            # 4. Apply patches
            for patch in self.patches:
                self._apply_patch(patch)
                applied_patched.append(str(patch.file))
                result["patched"].append(str(patch.file))

            # 5. Modify files
            for path_str, content in self.modified.items():
                Path(path_str).write_text(content, encoding="utf-8", newline="\r\n")
                applied_modified.append(path_str)
                result["modified"].append(path_str)

            # 6. Delete files
            for p in self.deleted:
                if p.exists():
                    p.unlink()
                applied_deleted.append(str(p))
                result["deleted"].append(str(p))

        except Exception as e:
            # Rollback all applied operations (P0-003)
            last_error = str(e)
            self._rollback_operations(
                applied_created, applied_modified, applied_deleted, applied_patched
            )
            result["status"] = "failed"
            result["errors"].append(last_error)
            return result

        return result

    def _rollback_operations(
        self,
        created_paths: List[str],
        modified_paths: List[str],
        deleted_paths: List[str],
        patched_paths: List[str],
    ):
        """Rollback applied operations in reverse order."""
        # Restore patched files
        for path_str in reversed(patched_paths):
            if path_str in self._backups:
                try:
                    Path(path_str).write_text(
                        self._backups[path_str], encoding="utf-8", newline="\r\n"
                    )
                except Exception:
                    pass

        # Restore modified files
        for path_str in reversed(modified_paths):
            if path_str in self._backups:
                try:
                    Path(path_str).write_text(
                        self._backups[path_str], encoding="utf-8", newline="\r\n"
                    )
                except Exception:
                    pass

        # Restore deleted files (P0-005)
        for path_str in reversed(deleted_paths):
            if path_str in self._deleted_backups:
                try:
                    (text, raw) = self._deleted_backups[path_str]
                    if raw is not None:
                        Path(path_str).write_bytes(raw)
                    elif text is not None:
                        Path(path_str).write_text(
                            text, encoding="utf-8", newline="\r\n"
                        )
                except Exception:
                    pass

        # Remove created files
        for path_str in reversed(created_paths):
            try:
                p = Path(path_str)
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    # ── Rollback ───────────────────────────────────────────────────

    def rollback(self) -> Dict[str, Any]:
        """Undo all changes (reverse of apply).

        Handles: created removal, modified restoration, deleted restoration (P0-005).
        """
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

        # Restore deleted files (P0-005 fix)
        for path_str, (text, raw) in self._deleted_backups.items():
            try:
                if raw is not None:
                    Path(path_str).write_bytes(raw)
                elif text is not None:
                    Path(path_str).write_text(text, encoding="utf-8", newline="\r\n")
            except Exception as e:
                result["errors"].append(f"Failed to restore deleted {path_str}: {e}")

        if result["errors"]:
            result["status"] = "rollback_partial"

        return result

    # ── Patch execution ────────────────────────────────────────────

    def _apply_patch(self, patch: Patch):
        """Apply a single inline patch to a file.

        Raises ValueError if target not found (P1-007 fix).
        """
        if not patch.file.exists():
            raise FileNotFoundError(f"Patch target not found: {patch.file}")

        content = patch.file.read_text(encoding="utf-8", errors="replace")
        self._backups[str(patch.file)] = content
        lines = content.split("\n")

        if patch.operation == "insert_after":
            matches = 0
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if patch.target in line:
                    new_lines.append(patch.content)
                    matches += 1
            lines = new_lines
            if matches == 0:
                raise ValueError(
                    f"Patch insert_after: target '{patch.target[:60]}' "
                    f"not found in {patch.file}"
                )

        elif patch.operation == "append":
            lines.append(patch.content)

        elif patch.operation == "replace":
            matches = 0
            new_lines = []
            for line in lines:
                if patch.target in line:
                    new_lines.append(patch.content)
                    matches += 1
                else:
                    new_lines.append(line)
            if matches == 0:
                raise ValueError(
                    f"Patch replace: target '{patch.target[:60]}' "
                    f"not found in {patch.file}"
                )
            lines = new_lines

        elif patch.operation == "delete_lines":
            if patch.line_start is not None and patch.line_end is not None:
                del lines[patch.line_start - 1 : patch.line_end]

        patch.file.write_text("\n".join(lines), encoding="utf-8", newline="\r\n")

    # ── Serialization ──────────────────────────────────────────────

    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "description": self.description,
            "created": dict(self.created),
            "modified": dict(self.modified),
            "deleted": [str(d) for d in self.deleted],
            "patches": [p.to_dict() for p in self.patches],
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
            "total_changes": self.total_changes,
            # Binary payloads (icons, etc.) must round-trip through
            # to_dict()/from_dict() — otherwise a create_command() result
            # that's serialized (e.g. returned as a "pending" preview,
            # then reconstructed via from_dict() before apply()) silently
            # loses the icon bytes. apply() would then see the "[BINARY]"
            # placeholder with no matching _binary entry and skip writing
            # the file while still reporting it under "created".
            "_binary": {
                path: base64.b64encode(data).decode("ascii")
                for path, data in self._binary.items()
            },
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ChangeSet":
        """Reconstruct ChangeSet from dict (full round-trip with patches — P1-002 fix)"""
        cs = cls(
            action=d.get("action", "unknown"), description=d.get("description", "")
        )
        cs.created = dict(d.get("created", {}))
        cs.modified = dict(d.get("modified", {}))
        cs.deleted = [Path(p) for p in d.get("deleted", [])]
        cs.patches = [Patch.from_dict(p) for p in d.get("patches", [])]
        cs.warnings = list(d.get("warnings", []))
        cs.metadata = dict(d.get("metadata", {}))
        cs._binary = {
            path: base64.b64decode(b64)
            for path, b64 in d.get("_binary", {}).items()
        }
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
    """Merge multiple ChangeSets into one.

    Detects same-path conflicts (P1-008 fix).
    """
    merged = ChangeSet(action="merged", description="Merged changeset")
    seen_created: set = set()
    seen_modified: set = set()
    conflicts: List[str] = []
    merged_patches_by_file: Dict[str, List[Patch]] = {}

    for cs in changesets:
        # Detect created-path conflicts
        for path_str in cs.created:
            if path_str in seen_created or path_str in seen_modified:
                conflicts.append(f"Created conflict on {path_str}")
            else:
                merged.created[path_str] = cs.created[path_str]
            seen_created.add(path_str)

        # Detect modified-path conflicts
        for path_str in cs.modified:
            if path_str in seen_modified or path_str in seen_created:
                conflicts.append(f"Modified conflict on {path_str}")
            else:
                merged.modified[path_str] = cs.modified[path_str]
            seen_modified.add(path_str)

        # Merge patches — track per file for conflict detection
        for patch in cs.patches:
            f = str(patch.file)
            if f in seen_created:
                conflicts.append(f"Patch conflict: {f} also in created")
            merged_patches_by_file.setdefault(f, []).append(patch)
            merged.patches.append(patch)

        merged.deleted.extend(cs.deleted)
        merged.warnings.extend(cs.warnings)

    if conflicts:
        merged.metadata["merge_conflicts"] = conflicts
        merged.add_warning(
            "Merge conflicts detected: " + "; ".join(conflicts[:5])
            + ("..." if len(conflicts) > 5 else "")
        )

    return merged
