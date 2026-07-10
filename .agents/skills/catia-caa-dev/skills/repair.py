"""
CAA Repair Loop
================
Automated fix-retry loop for CAA workspace issues.

Design principle:
  Try to fix automatically, but know when to stop.
  Escalate to human after max retries.

State machine:
  IN_PROGRESS → (diagnose) → FIXED | NO_ISSUES
                           ↘ FAILED → retry
                           ↘ ESCALATED (after 3 retries)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── RepairState ──────────────────────────────────────────────────


class RepairState(Enum):
    IN_PROGRESS = "in_progress"
    FIXED = "fixed"
    NO_ISSUES = "no_issues"
    ESCALATED = "escalated"
    FAILED = "failed"


# ─── RepairResult ─────────────────────────────────────────────────


@dataclass
class RepairResult:
    """Result of a repair loop execution"""
    state: RepairState
    attempts: int = 0
    fixes_applied: int = 0
    message: str = ""
    details: List[Dict[str, Any]] = field(default_factory=list)

    def is_success(self) -> bool:
        return self.state in (RepairState.FIXED, RepairState.NO_ISSUES)

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "attempts": self.attempts,
            "fixes_applied": self.fixes_applied,
            "message": self.message,
            "success": self.is_success(),
        }


# ─── RepairLoop ───────────────────────────────────────────────────


class RepairLoop:
    """
    Automated repair loop with retry.

    Flow:
      1. Diagnose the workspace
      2. If no issues → NO_ISSUES
      3. If auto-fixable issues → apply FixPlan → verify → repeat
      4. If unfixable issues after max retries → ESCALATED

    MAX_RETRIES = 3
    """

    MAX_RETRIES = 3

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        self._state = RepairState.IN_PROGRESS
        self._attempts = 0
        self._fixes_applied = 0
        self._details: List[Dict[str, Any]] = []

    def run(self) -> RepairResult:
        """
        Execute the repair loop.

        Returns:
            RepairResult with final state and stats
        """
        # Check workspace exists
        if not self.workspace_root.exists():
            return RepairResult(
                state=RepairState.NO_ISSUES,
                attempts=0,
                fixes_applied=0,
                message=f"Workspace does not exist: {self.workspace_root}",
            )

        try:
            for attempt in range(1, self.MAX_RETRIES + 1):
                self._attempts = attempt

                # Step 1: Diagnose
                diag_result = self._diagnose()
                auto_fixable = diag_result.get("auto_fixable", 0)
                total_issues = diag_result.get("total", 0)

                if total_issues == 0:
                    self._state = RepairState.NO_ISSUES
                    return RepairResult(
                        state=RepairState.NO_ISSUES,
                        attempts=attempt,
                        fixes_applied=self._fixes_applied,
                        message="No issues found in workspace.",
                    )

                if auto_fixable == 0:
                    # No auto-fixable issues — escalate immediately
                    self._state = RepairState.ESCALATED
                    return RepairResult(
                        state=RepairState.ESCALATED,
                        attempts=attempt,
                        fixes_applied=self._fixes_applied,
                        message=f"Found {total_issues} issues but none are auto-fixable. Manual intervention needed.",
                    )

                # Step 2: Apply fixes
                fix_result = self._apply_fixes(diag_result)
                fixed_count = fix_result.get("fixed", 0)
                self._fixes_applied += fixed_count
                self._details.append({
                    "attempt": attempt,
                    "issues_found": total_issues,
                    "auto_fixable": auto_fixable,
                    "fixed": fixed_count,
                })

                if fixed_count == auto_fixable:
                    # All fixable issues resolved
                    self._state = RepairState.FIXED
                    return RepairResult(
                        state=RepairState.FIXED,
                        attempts=attempt,
                        fixes_applied=self._fixes_applied,
                        message=f"Fixed all {fixed_count} auto-fixable issues in {attempt} attempt(s).",
                        details=self._details,
                    )

            # Max retries exceeded
            self._state = RepairState.ESCALATED
            return RepairResult(
                state=RepairState.ESCALATED,
                attempts=self.MAX_RETRIES,
                fixes_applied=self._fixes_applied,
                message=f"Max retries ({self.MAX_RETRIES}) exceeded. {self._fixes_applied} fixes applied. Manual review needed.",
                details=self._details,
            )

        except Exception as e:
            self._state = RepairState.FAILED
            return RepairResult(
                state=RepairState.FAILED,
                attempts=self._attempts,
                fixes_applied=self._fixes_applied,
                message=f"Repair loop failed: {e}",
            )

    # ─── Internal ──────────────────────────────────────────────

    def _diagnose(self) -> dict:
        """Run workspace diagnostics"""
        try:
            from diagnostics import DiagnosticsEngine
            from meta_model import WorkspaceSnapshot

            snapshot = WorkspaceSnapshot(root=self.workspace_root)
            engine = DiagnosticsEngine(snapshot)
            engine.run_all()
            return engine.summary()
        except ImportError:
            return {"total": 0, "auto_fixable": 0, "errors": 0, "warnings": 0}
        except Exception:
            return {"total": 0, "auto_fixable": 0, "errors": 0, "warnings": 0}

    def _apply_fixes(self, diag_result: dict) -> dict:
        """Apply auto-fixable diagnostics"""
        fixed = 0
        diagnostics = diag_result.get("diagnostics", [])
        for d in diagnostics:
            if d.get("auto_fixable") and d.get("fix_plan"):
                try:
                    self._execute_fix_plan(d["fix_plan"])
                    fixed += 1
                except Exception:
                    pass
        return {"fixed": fixed}

    def _execute_fix_plan(self, fix_plan: dict) -> None:
        """Execute a single FixPlan"""
        action = fix_plan.get("action", "")
        file = fix_plan.get("file", "")
        line = fix_plan.get("line", "")
        after_line = fix_plan.get("after_line", "")

        file_path = Path(file)
        if not file_path.exists() and action != "create_file":
            return

        if action == "create_file":
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(line or "", encoding="utf-8")
        elif action == "append_line":
            content = file_path.read_text(encoding="utf-8", errors="replace")
            if line and line not in content:
                file_path.write_text(content.rstrip() + "\n" + line + "\n", encoding="utf-8")
        elif action == "insert_line":
            content = file_path.read_text(encoding="utf-8", errors="replace")
            if after_line and after_line in content and line and line not in content:
                new_content = content.replace(after_line, after_line + "\n" + line)
                file_path.write_text(new_content, encoding="utf-8")
        elif action == "delete_line":
            content = file_path.read_text(encoding="utf-8", errors="replace")
            delete_target = fix_plan.get("delete_target", "")
            if delete_target and delete_target in content:
                new_content = content.replace(delete_target + "\n", "")
                new_content = new_content.replace(delete_target, "")
                file_path.write_text(new_content, encoding="utf-8")
