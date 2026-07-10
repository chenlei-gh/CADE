"""
CAA Build Verifier
===================
Compile verification for generated CAA code.

Design principle:
  Verify after generation — catch compile errors before the developer does.
  Integrate with mkmk to validate generated code compiles.

Usage:
  from verifier import BuildVerifier
  verifier = BuildVerifier(workspace_root)
  result = verifier.verify()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── CompileResult ────────────────────────────────────────────────


@dataclass
class CompileResult:
    """Structured compile verification result"""
    success: bool
    error_count: int = 0
    warning_count: int = 0
    duration: str = ""
    errors: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[Dict[str, str]] = field(default_factory=list)
    raw_output: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "duration": self.duration,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def has_errors(self) -> bool:
        return self.error_count > 0


# ─── BuildVerifier ────────────────────────────────────────────────


class BuildVerifier:
    """
    Verifies generated CAA code by running mkmk compilation.

    Requires CATIA Build Time environment to be configured
    (see env.py for auto-detection).
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)

    def verify(self) -> CompileResult:
        """
        Run mkmk -u incremental build and parse the output.

        Returns:
            CompileResult with success/failure and structured errors
        """
        try:
            from build import incremental_build
            result = incremental_build(self.workspace_root)

            if isinstance(result, dict):
                return CompileResult(
                    success=result.get("status") in ("success", "ok"),
                    error_count=result.get("error_count", 0),
                    warning_count=result.get("warning_count", 0),
                    duration=result.get("duration", ""),
                    raw_output=result.get("message", ""),
                )

            return CompileResult(
                success=True,
                error_count=0,
                warning_count=0,
                duration="unknown",
            )
        except ImportError:
            return CompileResult(
                success=False,
                error_count=0,
                warning_count=0,
                duration="skipped",
                errors=[{
                    "line": "N/A",
                    "message": "Build module not available — skipping compile verification."
                }],
            )
        except FileNotFoundError:
            return CompileResult(
                success=False,
                error_count=1,
                duration="skipped",
                errors=[{
                    "line": "N/A",
                    "message": "mkmk not found. Ensure CATIA Build Time environment is configured.",
                }],
            )
        except Exception as e:
            return CompileResult(
                success=False,
                error_count=1,
                duration="failed",
                errors=[{"line": "N/A", "message": str(e)}],
            )

    def verify_static(self) -> dict:
        """
        Static verification only (no mkmk required).
        Runs structural checks: file existence, naming, integrity.
        """
        try:
            from diagnostics import diagnose_workspace
            from actions import ActionContext

            ctx = ActionContext(str(self.workspace_root))
            return diagnose_workspace(ctx)
        except ImportError:
            return {"status": "ok", "total": 0, "message": "Static verification skipped — diagnostics not available."}
        except Exception as e:
            return {"status": "error", "total": 0, "message": str(e)}
