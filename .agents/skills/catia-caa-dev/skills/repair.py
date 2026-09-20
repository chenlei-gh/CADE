"""
CAA Repair Loop
================
Automated fix-retry loop for CAA workspace issues.

Design principle:
  Try to fix automatically, but know when to stop.
  Escalate to human after max retries.

Two-phase diagnosis:
  1. Static  — naming, includes, macros (fast, no tools)
  2. Build   — mkmk compilation (slow but catches real errors)

Repair loop:
  diagnose → preview → confirm → apply → verify → repeat

Rollback: every fix is applied through its own ChangeSet, and ChangeSet.apply()
persists a BackupManager backup under <workspace>/.caa_backups before writing.
The ids land in RepairResult.backup_ids (newest last); undoing a whole run means
calling backup.rollback_operation() on them in reverse order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from changeset import ChangeSet, Patch


# ─── RepairState ──────────────────────────────────────────────────


class RepairState(Enum):
    IN_PROGRESS = "in_progress"
    FIXED = "fixed"
    NO_ISSUES = "no_issues"
    ESCALATED = "escalated"
    FAILED = "failed"
    PREVIEW = "preview"  # New: dry-run mode


# ─── RepairResult ─────────────────────────────────────────────────


@dataclass
class RepairResult:
    """Result of a repair loop execution"""
    state: RepairState
    attempts: int = 0
    fixes_applied: int = 0
    message: str = ""
    details: List[Dict[str, Any]] = field(default_factory=list)
    preview: List[Dict[str, Any]] = field(default_factory=list)  # New
    # Rollback points for the fixes this run applied, in apply order. One id
    # per fix: each fix_plan is applied through its own ChangeSet, so a run
    # that fixes N issues mints N independent BackupManager backups. Undoing
    # the whole run therefore means rolling these back in reverse order.
    # Empty when nothing was applied — do not advertise a restore path then.
    backup_ids: List[str] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)  # raw findings

    def is_success(self) -> bool:
        return self.state in (RepairState.FIXED, RepairState.NO_ISSUES)

    def to_dict(self) -> dict:
        d = {
            "state": self.state.value,
            "attempts": self.attempts,
            "fixes_applied": self.fixes_applied,
            "message": self.message,
            "success": self.is_success(),
        }
        if self.preview:
            d["preview"] = self.preview
        if self.backup_ids:
            d["backup_ids"] = self.backup_ids
        if self.details:
            d["details"] = self.details
        if self.diagnostics:
            d["diagnostics"] = self.diagnostics
        return d


# ─── RepairLoop ───────────────────────────────────────────────────


class RepairLoop:
    """
    Automated repair loop with retry.

    Flow:
      1. Static diagnosis (fast) — naming, includes, macros
      2. Build diagnosis (slow) — mkmk compilation errors
      3. If no issues → NO_ISSUES
      4. If auto-fixable issues → show preview → backup → apply → verify
      5. If unfixable after max retries → ESCALATED

    MAX_RETRIES = 3
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        workspace_root: Path,
        preview: bool = False,
        with_build: bool = False,
        entrypoint: str = "repair_cli",
        orchestrated_by_kernel: bool = False,
    ):
        self.workspace_root = Path(workspace_root)
        self._preview_mode = preview
        self._with_build = with_build  # New: run mkmk for real errors
        self._entrypoint = entrypoint
        self._orchestrated_by_kernel = orchestrated_by_kernel
        self._state = RepairState.IN_PROGRESS
        self._attempts = 0
        self._fixes_applied = 0
        self._details: List[Dict[str, Any]] = []
        # Rollback ids minted by apply() for the fixes that succeeded, in
        # order. Populated on the fly — only real ids from successful applies
        # are recorded, so an unattempted or rejected fix contributes none.
        self._backup_ids: List[str] = []

    def run(self) -> RepairResult:
        """
        Execute the repair loop.

        If preview=True, analyzes but does not modify files.
        If with_build=True, runs mkmk to find real compilation errors.

        Returns:
            RepairResult with final state and stats
        """
        if not self.workspace_root.exists():
            return RepairResult(
                state=RepairState.FAILED,
                attempts=0,
                message=f"Workspace does not exist: {self.workspace_root}",
            )

        # ── Collect issues from both sources ──
        all_diagnostics = []
        all_preview_items = []

        # Static diagnosis (always run, fast)
        static = self._diagnose_static()
        all_diagnostics.extend(static.get("diagnostics", []))

        # Build diagnosis (optional, slow but real)
        if self._with_build:
            build = self._diagnose_build()
            all_diagnostics.extend(build.get("diagnostics", []))

        # Separate auto-fixable from manual
        auto_fixable = [d for d in all_diagnostics if d.get("auto_fixable")]
        manual_only = [d for d in all_diagnostics if not d.get("auto_fixable")]
        total_issues = len(all_diagnostics)

        if total_issues == 0:
            self._state = RepairState.NO_ISSUES
            note = ""
            if not self._with_build:
                note = (
                    " (static analysis only — run with --with-build to check "
                    "real mkmk compilation)"
                )
            return RepairResult(
                state=RepairState.NO_ISSUES,
                attempts=1,
                message=f"No issues found{note}",
            )

        # ── Build preview ──
        for d in auto_fixable:
            fix_plan = d.get("fix_plan", {})
            item = {
                "problem": d.get("message", ""),
                "file": d.get("file", ""),
                "severity": d.get("severity", "error"),
                "action": fix_plan.get("action", ""),
                "will_change": fix_plan.get("file", ""),
            }
            all_preview_items.append(item)

        # ── Preview mode: return without modifying ──
        if self._preview_mode:
            self._state = RepairState.PREVIEW
            return RepairResult(
                state=RepairState.PREVIEW,
                attempts=1,
                message=(
                    f"Found {total_issues} issue(s): {len(auto_fixable)} auto-fixable, "
                    f"{len(manual_only)} require manual intervention. "
                    f"Preview only — no files modified."
                ),
                preview=all_preview_items,
                diagnostics=all_diagnostics,
            )

        # ── No auto-fixable issues ──
        if len(auto_fixable) == 0:
            self._state = RepairState.ESCALATED
            return RepairResult(
                state=RepairState.ESCALATED,
                attempts=1,
                message=(
                    f"Found {total_issues} issue(s), none are auto-fixable. "
                    f"Manual intervention needed."
                ),
                preview=all_preview_items,
                diagnostics=all_diagnostics,
            )

        # No workspace-wide snapshot is taken here: every cs.apply() below
        # creates its own BackupManager backup under <workspace>/.caa_backups
        # and returns the id, which is what rollback_operation() consumes.

        # ── Retry loop ──
        for attempt in range(1, self.MAX_RETRIES + 1):
            self._attempts = attempt

            # Apply auto-fixes via ChangeSet (P0-006 fix)
            fixed_count = 0
            for d in auto_fixable:
                if d.get("fix_plan"):
                    try:
                        cs = self._build_fix_changeset(d["fix_plan"])
                        if not cs.is_empty:
                            apply_result = cs.apply(workspace_root=self.workspace_root)
                            if apply_result.get("status") == "applied":
                                fixed_count += 1
                                rollback_id = apply_result.get("rollback_id")
                                if rollback_id:
                                    self._backup_ids.append(rollback_id)
                            else:
                                self._details.append({
                                    "attempt": attempt,
                                    "fix_plan_failed": d["fix_plan"],
                                    "apply_result": apply_result,
                                })
                    except Exception as e:
                        self._details.append({
                            "attempt": attempt,
                            "fix_plan_error": str(e),
                        })

            self._fixes_applied += fixed_count
            self._details.append({
                "attempt": attempt,
                "issues_found": total_issues,
                "auto_fixable": len(auto_fixable),
                "fixed": fixed_count,
            })

            # Verify: re-run build if requested
            if self._with_build:
                verify = self._diagnose_build()
                remaining = verify.get("diagnostics", [])
                if len(remaining) == 0:
                    self._state = RepairState.FIXED
                    return RepairResult(
                        state=RepairState.FIXED,
                        attempts=attempt,
                        fixes_applied=self._fixes_applied,
                        message=f"Fixed all {fixed_count} issue(s) in {attempt} attempt(s). Build clean.",
                        details=self._details,
                        backup_ids=list(self._backup_ids),
                    )
            elif fixed_count == len(auto_fixable):
                self._state = RepairState.FIXED
                return RepairResult(
                    state=RepairState.FIXED,
                    attempts=attempt,
                    fixes_applied=self._fixes_applied,
                    message=(
                        f"Applied {fixed_count} fix(es) in {attempt} attempt(s). "
                        "Static verification only; build verification was not run."
                    ),
                    details=self._details,
                    backup_ids=list(self._backup_ids),
                )

        # Max retries exceeded
        self._state = RepairState.ESCALATED
        # Only advertise a restore path when there is actually something to
        # restore: pointing at an id that was never minted sends the user to a
        # backup that does not exist.
        if self._backup_ids:
            restore_hint = (
                "Rollback points (undo in reverse order): "
                + ", ".join(self._backup_ids)
            )
        else:
            restore_hint = "No changes were applied; nothing to roll back."
        return RepairResult(
            state=RepairState.ESCALATED,
            attempts=self.MAX_RETRIES,
            fixes_applied=self._fixes_applied,
            message=(
                f"Max retries ({self.MAX_RETRIES}) exceeded. "
                f"{self._fixes_applied} fix(es) applied. "
                f"Manual review needed. {restore_hint}"
            ),
            details=self._details,
            backup_ids=list(self._backup_ids),
        )

    # ─── Diagnosis ────────────────────────────────────────────────

    def _diagnose_static(self) -> dict:
        """Run static workspace diagnostics (fast, no tools)"""
        try:
            from analyzer import WorkspaceAnalyzer
            from diagnostics import DiagnosticsEngine

            # WorkspaceSnapshot(root=...) alone is an EMPTY model — it does
            # not scan the disk. Diagnostics on it silently reported zero
            # issues forever. WorkspaceAnalyzer.analyze() actually discovers
            # frameworks/modules/entities, which is what the checks need.
            snapshot = WorkspaceAnalyzer(Path(self.workspace_root)).analyze()
            engine = DiagnosticsEngine(snapshot)
            engine.run_all()
            return engine.summary()
        except ImportError:
            return {"total": 0, "auto_fixable": 0, "diagnostics": []}
        except Exception:
            return {"total": 0, "auto_fixable": 0, "diagnostics": []}

    def _diagnose_build(self) -> dict:
        """
        Run mkmk build and parse compilation errors.
        Returns diagnostics in the same format as _diagnose_static().
        """
        try:
            from build import build_workspace
            from parser import parse_mkmk_output

            # Run incremental build to find errors. "-a" is required for mkmk
            # to correctly discover workspace frameworks (mkmk -u alone can
            # fail with "must be executed in a workspace containing at least
            # one framework" even when .edu directories exist).
            # skip_gate: the repair loop needs RAW mkmk output to feed
            # parse_mkmk_output/FixPlan; a gate BLOCK would starve it.
            ep = "kernel" if self._orchestrated_by_kernel else self._entrypoint
            result = build_workspace(self.workspace_root, options="-u -a",
                                     timeout=300, skip_gate=True,
                                     entrypoint=ep,
                                     orchestrated_by_kernel=self._orchestrated_by_kernel)

            # Diagnose exactly this invocation. Reading build.json here can
            # accidentally report errors from an older build.
            output = result.get("output", "")
            parsed = parse_mkmk_output(output)

            # Convert to diagnostic format. Skip cascade entries: they are
            # downstream artifacts of a root-cause error (missing .obj/.dll)
            # and pointing the fixer at them would chase the wrong file.
            diagnostics = []
            for err in parsed.get("errors", []):
                if err.get("cascade"):
                    continue
                d = {
                    "severity": err.get("severity", "error"),
                    "category": "compilation",
                    "file": err.get("file", ""),
                    "line": err.get("line", 0),
                    "code": err.get("code", ""),
                    "message": err.get("message", ""),
                    "auto_fixable": self._is_auto_fixable(
                        err.get("code", ""), err.get("message", "")
                    ),
                    "fix_plan": self._suggest_fix(
                        err.get("code", ""), err.get("message", ""), err.get("file", "")
                    ),
                }
                diagnostics.append(d)

            if not diagnostics and result.get("status") not in ("success", "ok"):
                diagnostics.append({
                    "severity": "error",
                    "category": "build",
                    "file": "",
                    "line": 0,
                    "code": "",
                    "message": result.get("message", "Build failed without parseable output"),
                    "auto_fixable": False,
                    "fix_plan": None,
                })

            return {
                "total": len(diagnostics),
                "auto_fixable": len([d for d in diagnostics if d.get("auto_fixable")]),
                "diagnostics": diagnostics,
            }
        except ImportError:
            return {"total": 0, "auto_fixable": 0, "diagnostics": []}
        except Exception as e:
            return {
                "total": 0, "auto_fixable": 0,
                "diagnostics": [{
                    "severity": "error",
                    "category": "build",
                    "message": f"Build diagnosis failed: {e}",
                    "auto_fixable": False,
                }],
            }

    def _is_auto_fixable(self, code: str, message: str) -> bool:
        """Determine if a compilation error is auto-fixable"""
        # C2653: not a class/namespace — fixable by adding MacDeclareHeader
        if "C2653" in code:
            return True
        # C1083: missing header file — fixable if we know the missing header
        if "C1083" in code:
            return True
        # C2039: not a member — possibly fixable (e.g. Undo→ExecuteUndo)
        if "C2039" in code:
            return True
        # Missing include directives
        if "undeclared" in message.lower() or "未定义" in message:
            return True
        return False

    def _suggest_fix(self, code: str, message: str, file: str) -> Optional[dict]:
        """Generate a FixPlan from a compilation error"""
        if "C2653" in code:
            return {
                "action": "append_line",
                "file": file,
                "description": f"Add MacDeclareHeader before the first use of the header class",
                "line": '#include "CATCommandHeader.h"\nMacDeclareHeader(QuickCmdHdr);',
                "after_line": '#include "CATCreateWorkshop.h"',
            }
        if "C1083" in code and "ConfigDlg.h" in message:
            return {
                "action": "create_file",
                "file": file.replace("src/", "LocalInterfaces/").replace(
                    Path(file).name, "ConfigDlg.h"
                ),
                "description": "Create missing ConfigDlg.h header",
                "line": '// See CADE knowledge/ui/dialog.md for template',
            }
        return None

    # ─── Fix Execution ─────────────────────────────────────────────

    def _build_fix_changeset(self, fix_plan: dict) -> ChangeSet:
        """Build a ChangeSet from a FixPlan (P0-006 fix).

        No direct file writes — all changes are collected into a ChangeSet
        and applied safely with path validation, backup, and rollback support.
        """
        action_name = fix_plan.get("action", "")
        file = fix_plan.get("file", "")
        line = fix_plan.get("line", "")
        after_line = fix_plan.get("after_line", "")

        file_path = Path(file)
        if not file_path.is_absolute():
            file_path = self.workspace_root / file_path

        cs = ChangeSet(
            action=f"repair:{action_name}",
            description=fix_plan.get("description", f"Auto-fix: {action_name} on {file}"),
        )

        if action_name == "create_file":
            if not file_path.exists():
                cs.add_create(file_path, line or "")

        elif action_name == "append_line":
            if file_path.exists() and line:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                if line not in content:
                    cs.add_patch(Patch(
                        file=file_path,
                        operation="append",
                        target="",
                        content=line,
                    ))

        elif action_name == "insert_line":
            if file_path.exists() and after_line and line:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                if after_line in content and line not in content:
                    cs.add_patch(Patch(
                        file=file_path,
                        operation="insert_after",
                        target=after_line,
                        content=line,
                    ))

        elif action_name == "delete_line":
            if file_path.exists():
                delete_target = fix_plan.get("delete_target", "")
                if delete_target:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    lines = content.split("\n")
                    for i, ln in enumerate(lines, start=1):
                        if delete_target in ln:
                            cs.add_patch(Patch(
                                file=file_path,
                                operation="delete_lines",
                                target=delete_target,
                                content="",
                                line_start=i,
                                line_end=i,
                            ))
                            break

        elif action_name == "delete_file":
            # Orphaned-file removal (diagnostics._check_orphaned emits
            # FixAction.DELETE_FILE with auto_fixable=True). Without this
            # branch the ChangeSet stayed empty, so the run burned its retries
            # and escalated while the orphan survived. Deleting is the one
            # operation with no in-memory fallback: _deleted_backups lives on
            # this ChangeSet, which is discarded right after apply(). The only
            # way back is the BackupManager entry apply() persists, which is
            # why run() records its rollback_id.
            if file_path.exists():
                cs.add_delete(file_path)

        return cs
