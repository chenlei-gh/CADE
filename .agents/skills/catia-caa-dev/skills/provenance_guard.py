"""
CADE Change Provenance Guard (P3-B)
====================================
Pure-function controlled source and resource provenance comparator and snapshot collector.

Scope:
  This module provides **Controlled Source & Resource Provenance** verification for CATIA CAA workspaces.
  It tracks changes across C/C++ source code, headers, CAA build definitions (Imakefile.mk),
  framework IdentityCards, dictionaries (*.dico), and message catalogs (*.CATNls, *.CATRsc).
  It does NOT perform whole-disk arbitrary filesystem auditing (e.g. untracked temporary files,
  build artifacts under win_b64, or VCS directories are explicitly filtered out).

Guarantees:
  1. Pure analysis: zero filesystem writes, zero mutation of MaintenanceContext or build state.
  2. Scope isolation: strictly filters controlled CAA source/resource assets, ignoring build outputs (win_b64),
     temporary artifacts, logs, and vcs metadata.
  3. Semantic decoupling: working_tree_state (clean/dirty) is separated from provenance_status.
  4. Factual reporting: identifies presence of unregistered deltas without making unverified assertions
     about the external/internal identity of the modifying process.
  5. Pre-existing dirty awareness: differentiates between unedited pre-existing dirty files and
     files modified further during the task.
  6. Deterministic & serializable: all results are pure dataclasses with complete to_dict / from_dict.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


# ─── Status Enums ───────────────────────────────────────────────────


class ProvenanceAuditState:
    """State of change provenance audit execution."""

    NOT_EVALUATED = "NOT_EVALUATED"
    EVALUATED = "EVALUATED"
    FAILED = "FAILED"


class ProvenanceStatus:
    """Provenance evaluation result states."""

    PROVENANCE_VERIFIED = "provenance_verified"
    UNTRACKED_EXTERNAL = "untracked_external"
    CONFLICT = "conflict"
    DIRTY_INITIAL_BASE = "dirty_initial_base"
    CLEAN_NO_CHANGES = "clean_no_changes"


class WorkingTreeState:
    """Physical working tree delta state relative to baseline."""

    CLEAN = "clean"
    DIRTY = "dirty"


# ─── Asset Categorization ───────────────────────────────────────────


@dataclass
class AssetCategoryConfig:
    """Configurable categorization of controlled CAA source assets vs build artifacts."""

    source_extensions: Set[str] = field(
        default_factory=lambda: {
            ".cpp",
            ".cxx",
            ".c",
            ".cc",
            ".h",
            ".hpp",
            ".hxx",
            ".dico",
            ".catnls",
            ".catrsc",
        }
    )
    exact_filenames: Set[str] = field(
        default_factory=lambda: {
            "imakefile.mk",
            "identitycard.xml",
            "identitycard.h",
        }
    )
    excluded_dir_names: Set[str] = field(
        default_factory=lambda: {
            "win_b64",
            ".git",
            ".cade",
            ".agents",
            "__pycache__",
            ".vscode",
            ".idea",
        }
    )
    excluded_extensions: Set[str] = field(
        default_factory=lambda: {
            ".obj",
            ".dll",
            ".lib",
            ".ilk",
            ".pdb",
            ".exp",
            ".manifest",
            ".idb",
            ".log",
            ".err",
            ".tmp",
            ".bak",
            ".swp",
            ".pyc",
            ".backup",
            ".orig",
        }
    )


DEFAULT_ASSET_CONFIG = AssetCategoryConfig()


def is_controlled_source_asset(
    file_path: Path,
    workspace_root: Path,
    config: Optional[AssetCategoryConfig] = None,
) -> bool:
    """Determine if a file is a controlled CAA source asset.

    Filters out build artifacts (win_b64, .obj, .dll), VCS dirs (.git),
    CADE metadata (.cade), and temporary files.
    """
    cfg = config or DEFAULT_ASSET_CONFIG

    try:
        if file_path.is_absolute():
            rel = file_path.resolve().relative_to(workspace_root.resolve())
        else:
            rel = file_path
    except (ValueError, OSError):
        return False

    # Check excluded directory components
    for part in rel.parts[:-1]:
        if part.lower() in cfg.excluded_dir_names:
            return False

    file_name_lower = rel.name.lower()
    suffix_lower = rel.suffix.lower()

    if suffix_lower in cfg.excluded_extensions:
        return False

    if file_name_lower in cfg.exact_filenames:
        return True

    if suffix_lower in cfg.source_extensions:
        return True

    return False


# ─── Path & Hash Helpers ─────────────────────────────────────────────


def normalize_rel_posix_path(
    path: Union[str, Path], workspace_root: Path, strict: bool = True
) -> str:
    """Normalize a path to a workspace-relative POSIX string (e.g. 'mod.m/src/foo.cpp').

    Args:
        path: Path string or Path object (can be absolute or relative).
        workspace_root: Workspace root directory.
        strict: If True, raises ValueError if the path resolves outside workspace_root.
                If False, returns normalized POSIX string of path without containment enforcement.

    Raises:
        ValueError: If strict=True and path resolves outside workspace_root.
    """
    ws_root = workspace_root.resolve()
    raw_p = Path(path)

    # Resolve full target path
    if raw_p.is_absolute():
        resolved_p = raw_p.resolve()
    else:
        resolved_p = (ws_root / raw_p).resolve()

    try:
        rel = resolved_p.relative_to(ws_root)
    except ValueError:
        if strict:
            raise ValueError(
                f"Path '{path}' resolves to '{resolved_p}' which is outside workspace root '{ws_root}'"
            )
        rel = raw_p

    posix_str = rel.as_posix().rstrip("/")
    while posix_str.startswith("./"):
        posix_str = posix_str[2:]

    return posix_str


def compute_file_sha256(file_path: Path) -> str:
    """Compute binary SHA-256 of a file to preserve exact disk encoding (including CRLF)."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class ScanAuditStats:
    """Detailed telemetry and audit metrics for a workspace source asset scan."""

    total_files_scanned: int = 0
    controlled_assets_count: int = 0
    excluded_files_count: int = 0
    excluded_by_extension: Dict[str, int] = field(default_factory=dict)
    excluded_directories: Set[str] = field(default_factory=set)
    unknown_extensions: Dict[str, int] = field(default_factory=dict)
    scan_duration_ms: float = 0.0
    scan_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["excluded_directories"] = sorted(list(self.excluded_directories))
        return d


def capture_source_snapshot_detailed(
    workspace_root: Path,
    config: Optional[AssetCategoryConfig] = None,
    custom_filter: Optional[Callable[[Path], bool]] = None,
) -> Tuple[Dict[str, str], ScanAuditStats]:
    """Capture a snapshot of all controlled source assets with full audit telemetry.

    Returns:
        Tuple of (snapshot_dict, scan_audit_stats)
    """
    cfg = config or DEFAULT_ASSET_CONFIG
    ws_root = workspace_root.resolve()
    snapshot: Dict[str, str] = {}
    stats = ScanAuditStats()

    start_t = time.perf_counter()

    if not ws_root.exists() or not ws_root.is_dir():
        stats.scan_duration_ms = (time.perf_counter() - start_t) * 1000.0
        return snapshot, stats

    for root, dirs, files in os.walk(ws_root):
        # Record and prune excluded directories
        pruned = [d for d in dirs if d.lower() in cfg.excluded_dir_names]
        for d in pruned:
            stats.excluded_directories.add(d)
        dirs[:] = [d for d in dirs if d.lower() not in cfg.excluded_dir_names]

        for fname in files:
            stats.total_files_scanned += 1
            full_path = Path(root) / fname
            suffix_lower = full_path.suffix.lower()

            if is_controlled_source_asset(full_path, ws_root, cfg):
                if custom_filter and not custom_filter(full_path):
                    stats.excluded_files_count += 1
                    continue
                try:
                    rel_path = normalize_rel_posix_path(full_path, ws_root, strict=True)
                    snapshot[rel_path] = compute_file_sha256(full_path)
                    stats.controlled_assets_count += 1
                except (OSError, PermissionError, ValueError) as e:
                    err_msg = f"Failed to process {full_path}: {e}"
                    logger.warning(err_msg)
                    stats.scan_errors.append(err_msg)
            else:
                stats.excluded_files_count += 1
                if suffix_lower in cfg.excluded_extensions:
                    stats.excluded_by_extension[suffix_lower] = (
                        stats.excluded_by_extension.get(suffix_lower, 0) + 1
                    )
                elif suffix_lower:
                    stats.unknown_extensions[suffix_lower] = (
                        stats.unknown_extensions.get(suffix_lower, 0) + 1
                    )

    stats.scan_duration_ms = (time.perf_counter() - start_t) * 1000.0
    sorted_snapshot = {k: snapshot[k] for k in sorted(snapshot.keys())}
    return sorted_snapshot, stats


def capture_source_snapshot(
    workspace_root: Path,
    config: Optional[AssetCategoryConfig] = None,
    custom_filter: Optional[Callable[[Path], bool]] = None,
) -> Dict[str, str]:
    """Capture a snapshot of all controlled source assets in the workspace.

    Returns:
        Dict[rel_posix_path, sha256_hash]
    """
    snapshot, _ = capture_source_snapshot_detailed(
        workspace_root, config=config, custom_filter=custom_filter
    )
    return snapshot


# ─── ExpectedChange ──────────────────────────────────────────────────


@dataclass
class ExpectedChange:
    """A registered expected change originating from a CADE action/ChangeSet."""

    path: str  # Normalized POSIX relative path
    op_type: str  # "create" | "modify" | "patch" | "delete"
    expected_sha256: Optional[str] = None  # Expected content hash after operation
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "op_type": self.op_type,
            "expected_sha256": self.expected_sha256,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExpectedChange":
        return cls(
            path=d["path"],
            op_type=d.get("op_type", "modify"),
            expected_sha256=d.get("expected_sha256"),
            description=d.get("description", ""),
        )


def extract_expected_changes_from_changeset(
    changeset: Any,
    workspace_root: Path,
    post_apply_hashes: Optional[Dict[str, str]] = None,
    baseline_snapshot: Optional[Dict[str, str]] = None,
) -> List[ExpectedChange]:
    """Extract normalized ExpectedChange objects from a CADE ChangeSet.

    Consolidates multiple operations on the same path (e.g. created then patched,
    or deleted and recreated) into a single deterministic ExpectedChange representing
    the net expected outcome on disk relative to baseline.

    Args:
        changeset: A ChangeSet instance.
        workspace_root: Workspace root path.
        post_apply_hashes: Optional dict of {rel_posix_path: sha256} captured immediately
            after ChangeSet.apply() writes the files to disk.
        baseline_snapshot: Optional snapshot of the workspace at start of task,
            used to resolve delete+recreate into modify vs create.
    """
    post_hashes = post_apply_hashes or {}
    expected_map: Dict[str, ExpectedChange] = {}
    base_snap = baseline_snapshot or {}

    # 1. Created files
    if hasattr(changeset, "created"):
        for path_str in changeset.created:
            try:
                norm_path = normalize_rel_posix_path(path_str, workspace_root, strict=True)
            except ValueError:
                continue
            sha = post_hashes.get(norm_path)
            # If existed in baseline, creating it anew is net modify
            op = "modify" if norm_path in base_snap else "create"
            expected_map[norm_path] = ExpectedChange(
                path=norm_path,
                op_type=op,
                expected_sha256=sha,
                description=getattr(changeset, "action", "create"),
            )

    # 2. Modified files
    if hasattr(changeset, "modified"):
        for path_str in changeset.modified:
            try:
                norm_path = normalize_rel_posix_path(path_str, workspace_root, strict=True)
            except ValueError:
                continue
            sha = post_hashes.get(norm_path)
            if norm_path not in expected_map:
                expected_map[norm_path] = ExpectedChange(
                    path=norm_path,
                    op_type="modify",
                    expected_sha256=sha,
                    description=getattr(changeset, "action", "modify"),
                )
            else:
                if sha is not None:
                    expected_map[norm_path].expected_sha256 = sha

    # 3. Patched files (multiple patches on same file consolidate to one ExpectedChange)
    if hasattr(changeset, "patches"):
        for patch in changeset.patches:
            patch_file = getattr(patch, "file", None)
            if patch_file:
                try:
                    norm_path = normalize_rel_posix_path(patch_file, workspace_root, strict=True)
                except ValueError:
                    continue
                sha = post_hashes.get(norm_path)
                if norm_path not in expected_map:
                    expected_map[norm_path] = ExpectedChange(
                        path=norm_path,
                        op_type="patch",
                        expected_sha256=sha,
                        description=f"patch:{getattr(patch, 'operation', 'inline')}",
                    )
                else:
                    if sha is not None:
                        expected_map[norm_path].expected_sha256 = sha

    # 4. Deleted files
    if hasattr(changeset, "deleted"):
        for p in changeset.deleted:
            try:
                norm_path = normalize_rel_posix_path(p, workspace_root, strict=True)
            except ValueError:
                continue
            # If not recreated in this changeset, register delete
            if norm_path not in expected_map:
                expected_map[norm_path] = ExpectedChange(
                    path=norm_path,
                    op_type="delete",
                    expected_sha256=None,
                    description=getattr(changeset, "action", "delete"),
                )

    # Sort deterministically by path
    return [expected_map[p] for p in sorted(expected_map.keys())]


# ─── ProvenanceResult ────────────────────────────────────────────────


@dataclass
class ProvenanceResult:
    """Evaluation result of change provenance verification."""

    working_tree_state: str  # WorkingTreeState.CLEAN | DIRTY
    provenance_status: str  # ProvenanceStatus.*
    expected_changes: List[Dict[str, Any]] = field(default_factory=list)
    actual_changes: Dict[str, str] = field(default_factory=dict)  # path -> "created" | "modified" | "deleted"
    matched_changes: List[str] = field(default_factory=list)
    untracked_changes: List[str] = field(default_factory=list)
    missing_expected_changes: List[str] = field(default_factory=list)
    content_mismatches: List[Dict[str, Any]] = field(default_factory=list)
    pre_existing_dirty: List[str] = field(default_factory=list)
    pre_existing_modified_externally: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProvenanceResult":
        return cls(
            working_tree_state=d.get("working_tree_state", WorkingTreeState.CLEAN),
            provenance_status=d.get("provenance_status", ProvenanceStatus.CLEAN_NO_CHANGES),
            expected_changes=d.get("expected_changes", []),
            actual_changes=d.get("actual_changes", {}),
            matched_changes=d.get("matched_changes", []),
            untracked_changes=d.get("untracked_changes", []),
            missing_expected_changes=d.get("missing_expected_changes", []),
            content_mismatches=d.get("content_mismatches", []),
            pre_existing_dirty=d.get("pre_existing_dirty", []),
            pre_existing_modified_externally=d.get("pre_existing_modified_externally", []),
            warnings=d.get("warnings", []),
            details=d.get("details", {}),
        )


# ─── Pure-Function Comparator ─────────────────────────────────────────


def compute_change_provenance(
    baseline_snapshot: Dict[str, str],
    current_snapshot: Dict[str, str],
    expected_changes: List[ExpectedChange],
    pre_existing_dirty: Optional[List[str]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> ProvenanceResult:
    """Compare baseline snapshot, current snapshot, and registered expected changes.

    Pure function: no filesystem I/O, no mutation, no side effects.

    Args:
        baseline_snapshot: {rel_posix_path: sha256} at start of task.
        current_snapshot: {rel_posix_path: sha256} at evaluation point.
        expected_changes: Registered changes from CADE ChangeSet(s).
        pre_existing_dirty: List of normalized relative paths that were dirty before
            the task began (e.g. from git status pre-check).
        options: Optional comparator settings.

    Returns:
        ProvenanceResult containing full structured comparison facts.
    """
    dirty_initial = sorted(set(pre_existing_dirty or []))
    warnings: List[str] = []

    # 1. Compute actual delta on disk between baseline and current
    all_paths = set(baseline_snapshot.keys()) | set(current_snapshot.keys())
    actual_changes: Dict[str, str] = {}

    for p in sorted(all_paths):
        in_base = p in baseline_snapshot
        in_curr = p in current_snapshot

        if in_curr and not in_base:
            actual_changes[p] = "created"
        elif in_base and not in_curr:
            actual_changes[p] = "deleted"
        elif in_base and in_curr:
            if baseline_snapshot[p] != current_snapshot[p]:
                actual_changes[p] = "modified"

    # 2. Check pre-existing dirty files behavior during task
    pre_existing_modified_externally: List[str] = []
    expected_paths = {exp.path for exp in expected_changes}

    for p in dirty_initial:
        # Did this file undergo any change between baseline and current?
        if p in actual_changes:
            if p not in expected_paths:
                pre_existing_modified_externally.append(p)
        else:
            # File was pre-existing dirty, but NOT modified during the task
            warnings.append(
                f"File '{p}' was dirty prior to task and remained unmodified during task."
            )

    # 3. Match actual changes against expected changes
    expected_by_path: Dict[str, ExpectedChange] = {}
    for exp in expected_changes:
        if exp.path in expected_by_path:
            # Deterministic resolution: prefer the entry specifying an expected hash
            if not expected_by_path[exp.path].expected_sha256 and exp.expected_sha256:
                expected_by_path[exp.path] = exp
        else:
            expected_by_path[exp.path] = exp

    matched_changes: List[str] = []
    missing_expected_changes: List[str] = []
    content_mismatches: List[Dict[str, Any]] = []

    for exp_path in sorted(expected_by_path.keys()):
        exp = expected_by_path[exp_path]
        if exp_path not in actual_changes:
            missing_expected_changes.append(exp_path)
        else:
            act_type = actual_changes[exp_path]
            if exp.op_type == "delete":
                if act_type == "deleted":
                    matched_changes.append(exp_path)
                else:
                    content_mismatches.append(
                        {
                            "path": exp_path,
                            "reason": f"Expected delete, but file is {act_type}",
                        }
                    )
            else:  # create, modify, patch
                if act_type in ("created", "modified"):
                    if exp.expected_sha256 is not None:
                        actual_sha = current_snapshot.get(exp_path, "")
                        if actual_sha == exp.expected_sha256:
                            matched_changes.append(exp_path)
                        else:
                            content_mismatches.append(
                                {
                                    "path": exp_path,
                                    "expected_sha256": exp.expected_sha256,
                                    "actual_sha256": actual_sha,
                                }
                            )
                    else:
                        matched_changes.append(exp_path)
                else:
                    content_mismatches.append(
                        {
                            "path": exp_path,
                            "reason": f"Expected {exp.op_type}, but file is {act_type}",
                        }
                    )

    # 4. Detect untracked changes (actual changes not in expected)
    untracked_changes: List[str] = []
    for act_path in sorted(actual_changes.keys()):
        if act_path not in expected_by_path:
            untracked_changes.append(act_path)

    if untracked_changes:
        warnings.append(
            f"{len(untracked_changes)} unregistered modification(s) detected outside registered ExpectedChanges."
        )

    if pre_existing_modified_externally:
        warnings.append(
            f"{len(pre_existing_modified_externally)} pre-existing dirty file(s) modified without registration."
        )

    # 5. Evaluate provenance_status
    if untracked_changes or pre_existing_modified_externally:
        status = ProvenanceStatus.UNTRACKED_EXTERNAL
    elif missing_expected_changes or content_mismatches:
        status = ProvenanceStatus.CONFLICT
    elif len(actual_changes) > 0 and len(matched_changes) == len(actual_changes):
        status = ProvenanceStatus.PROVENANCE_VERIFIED
    else:  # No actual changes
        if dirty_initial:
            status = ProvenanceStatus.DIRTY_INITIAL_BASE
        else:
            status = ProvenanceStatus.CLEAN_NO_CHANGES

    # 6. Evaluate working_tree_state
    if not actual_changes and not dirty_initial:
        tree_state = WorkingTreeState.CLEAN
    else:
        tree_state = WorkingTreeState.DIRTY

    return ProvenanceResult(
        working_tree_state=tree_state,
        provenance_status=status,
        expected_changes=[exp.to_dict() for exp in expected_changes],
        actual_changes=actual_changes,
        matched_changes=sorted(matched_changes),
        untracked_changes=sorted(untracked_changes),
        missing_expected_changes=sorted(missing_expected_changes),
        content_mismatches=content_mismatches,
        pre_existing_dirty=dirty_initial,
        pre_existing_modified_externally=sorted(pre_existing_modified_externally),
        warnings=warnings,
        details={
            "total_actual_changes": len(actual_changes),
            "total_expected_changes": len(expected_changes),
        },
    )


# ─── Input Validation & Audit Summary Helpers ────────────────────────


_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def _is_valid_relative_posix_path(p: Any) -> bool:
    """Check if a path is a valid non-empty relative POSIX path without directory traversal."""
    if not isinstance(p, str) or not p.strip():
        return False
    # Reject Windows backslashes, absolute paths, and parent directory traversal
    if "\\" in p or p.startswith("/") or p.startswith("./"):
        return False
    parts = p.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    return True


def validate_provenance_inputs(
    baseline_snapshot: Any,
    expected_changes: Any,
    pre_existing_dirty: Optional[Any] = None,
) -> Tuple[bool, str]:
    """Strictly validate inputs before attempting provenance evaluation.

    Rules:
      1. baseline_snapshot must be a dict where keys are valid relative POSIX paths
         and values are 64-character hex SHA-256 strings.
      2. expected_changes must be a list of ExpectedChange or valid dicts containing
         'path' (relative POSIX) and 'op_type' in ('create', 'modify', 'patch', 'delete').
         If 'expected_sha256' is present and not None, it must be 64-char hex.
      3. pre_existing_dirty (if present) must be a list of valid relative POSIX paths.
      4. Missing inputs (None) or non-matching structures return (False, reason).

    Returns:
        (True, "") if all inputs are structurally valid.
        (False, reason_code) if inputs are missing or invalid.
    """
    if baseline_snapshot is None or expected_changes is None:
        return False, "missing_baseline_or_expected_changes"

    if not isinstance(baseline_snapshot, dict):
        return False, "invalid_baseline_type_not_dict"

    for path_key, sha_val in baseline_snapshot.items():
        if not _is_valid_relative_posix_path(path_key):
            return False, f"invalid_baseline_path: {path_key}"
        if not isinstance(sha_val, str) or not _SHA256_PATTERN.fullmatch(sha_val):
            return False, f"invalid_baseline_sha256: {path_key}"

    if not isinstance(expected_changes, list):
        return False, "invalid_expected_changes_type_not_list"

    valid_ops = {"create", "modify", "patch", "delete"}
    for idx, exp in enumerate(expected_changes):
        if isinstance(exp, ExpectedChange):
            p = exp.path
            op = exp.op_type
            sha = exp.expected_sha256
        elif isinstance(exp, dict):
            p = exp.get("path")
            op = exp.get("op_type")
            sha = exp.get("expected_sha256")
        else:
            return False, f"invalid_expected_change_item_at_{idx}"

        if not _is_valid_relative_posix_path(p):
            return False, f"invalid_expected_change_path_at_{idx}: {p}"
        if op not in valid_ops:
            return False, f"invalid_expected_change_op_at_{idx}: {op}"
        if sha is not None:
            if not isinstance(sha, str) or not _SHA256_PATTERN.fullmatch(sha):
                return False, f"invalid_expected_change_sha256_at_{idx}: {sha}"

    if pre_existing_dirty is not None:
        if not isinstance(pre_existing_dirty, list):
            return False, "invalid_pre_existing_dirty_type_not_list"
        for p in pre_existing_dirty:
            if not _is_valid_relative_posix_path(p):
                return False, f"invalid_pre_existing_dirty_path: {p}"

    return True, ""


def build_audit_summary(
    audit_state: str,
    reason: str,
    prov_result: Optional[ProvenanceResult] = None,
    error_type: Optional[str] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Construct a lightweight, stable, JSON-serializable audit summary dictionary.

    Guarantees:
      1. Consistent schema across all audit states (EVALUATED, NOT_EVALUATED, FAILED).
      2. No raw exceptions, absolute paths, or unescaped environment leaks.
      3. Field naming is unified to `untracked_changes` to prevent terminology drift.
      4. Zero Enum objects; all values are JSON-serializable primitives.
    """
    effective_warnings = list(warnings or [])

    if audit_state == ProvenanceAuditState.EVALUATED and prov_result is not None:
        return {
            "audit_state": ProvenanceAuditState.EVALUATED,
            "reason": reason,
            "provenance_status": prov_result.provenance_status,
            "working_tree_state": prov_result.working_tree_state,
            "untracked_changes": list(prov_result.untracked_changes),
            "untracked_change_count": len(prov_result.untracked_changes),
            "matched_change_count": len(prov_result.matched_changes),
            "missing_expected_count": len(prov_result.missing_expected_changes),
            "content_mismatch_count": len(prov_result.content_mismatches),
            "warnings": prov_result.warnings + effective_warnings,
        }

    if audit_state == ProvenanceAuditState.FAILED:
        return {
            "audit_state": ProvenanceAuditState.FAILED,
            "reason": reason,
            "provenance_status": "audit_failed",
            "working_tree_state": "unassessed",
            "error_type": error_type or "UnknownError",
            "untracked_changes": [],
            "untracked_change_count": 0,
            "matched_change_count": 0,
            "missing_expected_count": 0,
            "content_mismatch_count": 0,
            "warnings": effective_warnings or ["Provenance audit execution failed; see build log for details."],
        }

    # Default to NOT_EVALUATED
    return {
        "audit_state": ProvenanceAuditState.NOT_EVALUATED,
        "reason": reason,
        "provenance_status": "not_applicable",
        "working_tree_state": "unassessed",
        "untracked_changes": [],
        "untracked_change_count": 0,
        "matched_change_count": 0,
        "missing_expected_count": 0,
        "content_mismatch_count": 0,
        "warnings": effective_warnings,
    }
