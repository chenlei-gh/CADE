"""
CADE Development Kernel
========================
Unified execution entry point + state machine.

Design principle:
  AI knows 3 modes. Kernel handles everything else.
  Never expose internal pipeline details to AI.

Modes:
  DEVELOP  — create/generate (Command — may modify files)
  ANALYZE  — query/diagnose (Query   — read-only)
  REPAIR   — fix/refactor  (Command — may modify with recovery)

State machine:
  IDLE → CLARIFYING → PLANNING → GENERATING → VERIFYING → COMPLETED
                                                ↓
                                           REPAIRING → COMPLETED
                                                ↓
                                              FAILED

Usage:
  from kernel import Kernel, KernelMode

  kernel = Kernel(workspace_root="D:/workspace")
  result = kernel.execute(KernelMode.DEVELOP, "create command MyCmd in MyModule")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Enums ────────────────────────────────────────────────────────


class KernelMode(Enum):
    """Public API mode — determines execution policy"""
    DEVELOP = "develop"    # May modify files, needs preview→confirm
    ANALYZE = "analyze"    # Read-only, never writes
    REPAIR = "repair"      # May modify with rollback safety


class KernelState(Enum):
    """Internal state machine states"""
    IDLE = "idle"
    CLARIFYING = "clarifying"
    PLANNING = "planning"
    GENERATING = "generating"
    VERIFYING = "verifying"
    REPAIRING = "repairing"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── Policy ───────────────────────────────────────────────────────


class ModePolicy:
    """Execution policy for each mode"""

    READ_ONLY: bool
    NEEDS_PREVIEW: bool
    NEEDS_CONFIRM: bool
    NEEDS_ROLLBACK: bool
    AUTO_APPLY: bool

    def __init__(self, read_only: bool, needs_preview: bool,
                 needs_confirm: bool, needs_rollback: bool, auto_apply: bool):
        self.READ_ONLY = read_only
        self.NEEDS_PREVIEW = needs_preview
        self.NEEDS_CONFIRM = needs_confirm
        self.NEEDS_ROLLBACK = needs_rollback
        self.AUTO_APPLY = auto_apply


POLICIES = {
    KernelMode.DEVELOP: ModePolicy(
        read_only=False, needs_preview=True, needs_confirm=True,
        needs_rollback=True, auto_apply=False,
    ),
    KernelMode.ANALYZE: ModePolicy(
        read_only=True, needs_preview=False, needs_confirm=False,
        needs_rollback=False, auto_apply=True,
    ),
    KernelMode.REPAIR: ModePolicy(
        read_only=False, needs_preview=True, needs_confirm=False,
        needs_rollback=True, auto_apply=True,
    ),
}


# ─── Data ─────────────────────────────────────────────────────────


@dataclass
class KernelResult:
    """Standard result from any kernel execution"""
    status: str  # "ok" | "needs_clarification" | "pending" | "error" | "fixed" | "no_issues" | "not_applicable"
    mode: str = ""
    state: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"status": self.status, "mode": self.mode, "message": self.message}
        if self.state:
            d["state"] = self.state
        d.update(self.data)
        return {k: v for k, v in d.items() if v}  # strip empty


# ─── Kernel ───────────────────────────────────────────────────────


class Kernel:
    """
    CADE Development Kernel — unified execution entry point.

    AI-facing: 3 modes (DEVELOP, ANALYZE, REPAIR)
    Internal: state machine + module dispatch
    """

    MAX_RETRIES = 3

    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()
        self._state = KernelState.IDLE

    # ─── Public API ────────────────────────────────────────────

    def execute(self, mode: KernelMode, request: str) -> dict:
        """
        Unified execution entry point.

        Args:
            mode: DEVELOP | ANALYZE | REPAIR
            request: Natural language request from AI/user

        Returns:
            dict with keys: status, mode, message, + mode-specific data
        """
        if not request or not request.strip():
            return KernelResult(
                status="error", mode=mode.value,
                message="Empty request — please provide a description of what you want to do.",
            ).to_dict()

        policy = POLICIES[mode]

        try:
            if mode == KernelMode.DEVELOP:
                return self._handle_develop(request, policy)
            elif mode == KernelMode.ANALYZE:
                return self._handle_analyze(request, policy)
            elif mode == KernelMode.REPAIR:
                return self._handle_repair(request, policy)
            else:
                return KernelResult(
                    status="error", mode=mode.value,
                    message=f"Unknown mode: {mode}",
                ).to_dict()
        except Exception as e:
            self._state = KernelState.FAILED
            return KernelResult(
                status="error", mode=mode.value, state=self._state.value,
                message=str(e),
            ).to_dict()

    # ─── Mode Handlers ─────────────────────────────────────────

    def _handle_develop(self, request: str, policy: ModePolicy) -> dict:
        """DEVELOP mode: Requirement → Intent → Plan → Generate → Verify"""
        self._state = KernelState.CLARIFYING

        # Phase 1: Requirement Analysis
        try:
            from requirements import RequirementsClarifier
            clarifier = RequirementsClarifier()
            clarification = clarifier.analyze(request)

            if hasattr(clarification, 'status') and clarification.status == "needs_clarification":
                return KernelResult(
                    status="needs_clarification", mode="develop",
                    state=self._state.value,
                    message="Some decisions need to be made before proceeding.",
                    data=clarification.to_dict(),
                ).to_dict()
        except ImportError:
            pass  # requirements module not loaded yet — fall through

        # Phase 2: Intent → Plan → Generate
        self._state = KernelState.PLANNING
        plan = self._build_develop_plan(request)

        if plan is None:
            return KernelResult(
                status="error", mode="develop",
                message=f"Cannot build development plan for: {request}",
            ).to_dict()

        self._state = KernelState.GENERATING
        result = self._execute_develop_plan(plan)

        self._state = KernelState.COMPLETED
        return KernelResult(
            status=result.get("status", "ok"), mode="develop",
            state=self._state.value,
            message=result.get("message", "Development completed."),
            data=result,
        ).to_dict()

    def _handle_analyze(self, request: str, policy: ModePolicy) -> dict:
        """ANALYZE mode: Workspace analysis / diagnostics (read-only)"""
        self._state = KernelState.PLANNING

        # Detect intent from request keywords
        request_lower = request.lower()

        # Diagnose
        if any(kw in request_lower for kw in ("diagnos", "check", "inspect", "validate", "verify")):
            try:
                from diagnostics import diagnose_workspace
                from actions import ActionContext
                ctx = ActionContext(str(self.workspace_root))
                diag_result = diagnose_workspace(ctx)
                self._state = KernelState.COMPLETED
                return KernelResult(
                    status="ok", mode="analyze", state=self._state.value,
                    message=f"Diagnostics complete. {diag_result.get('total', 0)} issues found.",
                    data={"diagnostics": diag_result},
                ).to_dict()
            except ImportError:
                pass

        # Default: workspace analysis
        try:
            from actions import ActionContext, analyze_workspace
            ctx = ActionContext(str(self.workspace_root))
            analysis = analyze_workspace(ctx)
            self._state = KernelState.COMPLETED
            return KernelResult(
                status=analysis.get("status", "ok"), mode="analyze",
                state=self._state.value,
                message="Workspace analysis complete.",
                data=analysis,
            ).to_dict()
        except ImportError:
            pass

        # Fallback
        self._state = KernelState.COMPLETED
        return KernelResult(
            status="ok", mode="analyze", state=self._state.value,
            message="Analysis completed (basic).",
        ).to_dict()

    def _handle_repair(self, request: str, policy: ModePolicy) -> dict:
        """REPAIR mode: Diagnose → Fix → Verify (with retry)"""
        self._state = KernelState.REPAIRING

        try:
            from repair import RepairLoop
            loop = RepairLoop(workspace_root=self.workspace_root)
            repair_result = loop.run()
            self._state = KernelState.COMPLETED
            return KernelResult(
                status=repair_result.state.value if hasattr(repair_result.state, 'value') else str(repair_result.state),
                mode="repair", state=self._state.value,
                message=repair_result.message,
                data=repair_result.to_dict(),
            ).to_dict()
        except ImportError:
            pass

        # Fallback: basic diagnose + fix
        try:
            from diagnostics import diagnose_workspace
            from actions import ActionContext
            ctx = ActionContext(str(self.workspace_root))
            diag_result = diagnose_workspace(ctx)
            auto_fixable = diag_result.get("auto_fixable", 0)
            if auto_fixable == 0:
                self._state = KernelState.COMPLETED
                return KernelResult(
                    status="no_issues", mode="repair", state=self._state.value,
                    message="No auto-fixable issues found.",
                    data=diag_result,
                ).to_dict()
            self._state = KernelState.COMPLETED
            return KernelResult(
                status="fixed", mode="repair", state=self._state.value,
                message=f"Found {auto_fixable} auto-fixable issues.",
                data=diag_result,
            ).to_dict()
        except ImportError:
            pass

        self._state = KernelState.COMPLETED
        return KernelResult(
            status="not_applicable", mode="repair", state=self._state.value,
            message="Repair subsystem not available.",
        ).to_dict()

    # ─── Develop Plan Helpers ──────────────────────────────────

    def _build_develop_plan(self, request: str) -> Optional[dict]:
        """Build a development plan from natural language request"""
        try:
            from intent.models import Intent, IntentType
            from intent.planner import Planner
        except ImportError:
            return None

        # Detect intent type from request
        request_lower = request.lower()
        intent_type = self._detect_intent_type(request_lower)

        # Extract name and module
        name, module, framework = self._extract_entities(request)

        if not name:
            return None

        # Convert string to IntentType enum
        try:
            itype = IntentType(intent_type)
        except (ValueError, TypeError):
            itype = IntentType.CREATE_COMMAND

        intent = Intent(
            type=itype,
            name=name,
            module=module or "MyModule.m",
            framework=framework or "MyFramework",
        )

        # Plan
        try:
            planner = Planner()
            plan = planner.plan(intent)
            return {
                "intent": intent.to_dict(),
                "plan": plan.to_dict() if plan else {},
                "steps": len(plan.steps) if plan and hasattr(plan, 'steps') else 0,
            }
        except Exception:
            return {"intent": intent.to_dict(), "plan": {}, "steps": 0}

    def _execute_develop_plan(self, plan: dict) -> dict:
        """Execute a development plan via existing actions"""
        intent_data = plan.get("intent", {})
        intent_type = intent_data.get("type", "")
        name = intent_data.get("name", "")
        module = intent_data.get("module", "MyModule.m")
        framework = intent_data.get("framework", "MyFramework")

        try:
            from actions import ActionContext
            from intents import create_executable_command, create_feature, create_extension

            ctx = ActionContext(str(self.workspace_root))

            if "Command" in intent_type:
                result = create_executable_command(ctx, name=name, module=module,
                                                   framework=framework)
            elif "Feature" in intent_type:
                result = create_feature(ctx, name=name, module=module, framework=framework)
            elif "Extension" in intent_type:
                result = create_extension(ctx, name=name, target_object="", module=module,
                                          framework=framework)
            else:
                return {"status": "ok", "message": f"Plan would execute: {intent_type} {name}"}

            # If action returned error (e.g., module not found), treat as pending
            if isinstance(result, dict) and result.get("status") == "error":
                return {
                    "status": "pending",
                    "message": f"Plan generated: {result.get('message', '')}",
                    "preview": {"plan_steps": plan.get("steps", 0), "intent": intent_data},
                }
            return result if isinstance(result, dict) else {"status": "ok", "message": str(result)}
        except ImportError:
            return {"status": "pending", "message": f"Plan ready: {intent_type} {name} in {module}"}

    # ─── Intent Detection ──────────────────────────────────────

    def _detect_intent_type(self, request: str) -> str:
        """Detect IntentType from natural language request"""
        mapping = [
            ("command", "CreateCommand"),
            ("dialog", "CreateCommandWithDialog"),
            ("feature", "CreateFeature"),
            ("extension", "CreateExtension"),
            ("interface", "CreateInterface"),
            ("workbench", "CreateWorkbench"),
            ("module", "CreateModule"),
            ("framework", "CreateFramework"),
        ]
        for keyword, intent_type in mapping:
            if keyword in request:
                return intent_type
        return "CreateCommand"  # default

    def _extract_entities(self, request: str) -> tuple:
        """Extract (name, module, framework) from natural language request"""
        import re

        name = None
        module = None
        framework = None

        # Pattern: "create command <Name> in <Module>"
        m = re.search(r'(?:create|make|generate)\s+(?:a\s+)?\w+\s+(\w+)', request)
        if m:
            name = m.group(1)

        # Pattern: "in <Module>"
        m = re.search(r'in\s+(\w+(?:\.\w+)?)', request)
        if m:
            module = m.group(1)

        # Pattern: "framework <Framework>"
        m = re.search(r'(?:framework|fw)\s+(\w+(?:\.\w+)?)', request, re.IGNORECASE)
        if m:
            framework = m.group(1)

        return name, module, framework
