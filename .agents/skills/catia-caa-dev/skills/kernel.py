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
    DEVELOP = "develop"    # Creates/modifies files, auto-applies (backup+rollback safety)
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
        # Auto-applies with backup/rollback safety (same model as REPAIR).
        # A ChangeSet is still generated first (needs_preview stays True so
        # callers can inspect result["apply_result"]["preview"] after the
        # fact), but nothing is left sitting in "pending" state — see
        # _execute_develop_plan()/_apply_changeset_dict().
        read_only=False, needs_preview=True, needs_confirm=False,
        needs_rollback=True, auto_apply=True,
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

    def execute(self, mode: KernelMode, request: str, preview: bool = False) -> dict:
        """
        Unified execution entry point.

        Args:
            mode: DEVELOP | ANALYZE | REPAIR
            request: Natural language request from AI/user
            preview: If True (DEVELOP mode only), generate the ChangeSet but
                     do NOT apply it to the workspace. The caller can inspect
                     the returned 'changeset' and 'preview' fields, then
                     decide whether to apply via a follow-up non-preview call
                     (or roll back). Enables the review-then-apply workflow
                     that makes rollback actually usable.

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
                return self._handle_develop(request, policy, preview=preview)
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

    def _handle_develop(self, request: str, policy: ModePolicy, preview: bool = False) -> dict:
        """DEVELOP mode: Requirement → Intent → Plan → Generate → Verify"""
        self._state = KernelState.CLARIFYING
        request_lower = request.lower()

        # Phase 0: Multi-Intent Decomposition (v3.1) — BEFORE clarification
        # Split compound requests first so clarification doesn't short-circuit.
        try:
            from requirements import MultiIntentDecomposer
            decomposer_multi = MultiIntentDecomposer()
            sub_intents = decomposer_multi.decompose(request)
            if len(sub_intents) > 1:
                return self._handle_multi_develop(request, sub_intents, policy, preview=preview)
        except ImportError:
            pass

        # Phase 1: Requirement Analysis
        clarification = None
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

        # Phase 1.3: Requirements Decomposer — extract cross-domain extras
        extras = {}
        if clarification:
            try:
                from requirements import RequirementsDecomposer
                decomposer = RequirementsDecomposer()
                extras = decomposer.enhance(clarification)
            except ImportError:
                pass


        # Phase 1.5: Build / Run / Setup operations (no plan needed)
        build_run_result = self._handle_build_run(request_lower)
        if build_run_result:
            return build_run_result

        # Phase 2: Intent → Plan → Generate
        self._state = KernelState.PLANNING
        plan = self._build_develop_plan(request)

        if plan is None:
            return KernelResult(
                status="error", mode="develop",
                message=f"Cannot build development plan for: {request}",
            ).to_dict()

        self._state = KernelState.GENERATING
        result = self._execute_develop_plan(plan, preview=preview)

        # Phase 2.5: Apply cross-domain extras (data_extension, imakefile deps)
        if not preview and extras and any(extras.values()):
            apply_result = self._apply_extras(plan, extras)
            if apply_result:
                result["extras_applied"] = apply_result

        # Phase 3: Static verification of generated code (skip in preview mode
        # since no files exist yet)
        if not preview:
            verify_result = self._verify_generated_code(plan)
            if verify_result and verify_result.get("files_checked", 0) > 0:
                result["verification"] = verify_result

        # Phase 3.5: Ensure IdentityCard (prevent mkmk build failures)
        # Skip in preview mode: no files on disk yet to inspect
        if not preview:
            ic_ok = self._ensure_identity_card(plan)
            if ic_ok:
                result["identity_card"] = ic_ok

        self._state = KernelState.COMPLETED
        if preview:
            # In preview mode, surface a clear message and keep the raw
            # changeset in the payload so the caller can inspect/diff it.
            result["preview_mode"] = True
            # Remove status/message from data to avoid overwriting the
            # "preview" status/message when to_dict() merges data.
            result_for_data = {k: v for k, v in result.items() if k not in ("status", "message")}
            return KernelResult(
                status="preview", mode="develop",
                state=self._state.value,
                message=(
                    "Preview: ChangeSet generated but NOT applied. "
                    "Review data.changeset / data.preview, then either "
                    "re-run without --preview to apply, or discard."
                ),
                data=result_for_data,
            ).to_dict()
        return KernelResult(
            status=result.get("status", "ok"), mode="develop",
            state=self._state.value,
            message=result.get("message", "Development completed."),
            data=result,
        ).to_dict()

    def _handle_analyze(self, request: str, policy: ModePolicy) -> dict:
        """ANALYZE mode: Knowledge search / diagnostics / workspace (read-only)"""
        self._state = KernelState.PLANNING
        request_lower = request.lower()

        # ── Path 1: Diagnostics ──
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

        # ── Path 2: Dependency / entity query (before knowledge — more specific) ──
        if any(kw in request_lower for kw in ("depend", "impact", "graph", "visualiz")):
            try:
                from actions import ActionContext, get_dependencies, visualize_dependencies
                import re
                ctx = ActionContext(str(self.workspace_root))
                entity_match = re.search(r'(?:of|for)\s+(\w+)', request)
                entity = entity_match.group(1) if entity_match else None
                if entity and "graph" in request_lower:
                    dep_result = visualize_dependencies(ctx, entity)
                else:
                    dep_result = get_dependencies(ctx, entity or "", "command")
                self._state = KernelState.COMPLETED
                return KernelResult(
                    status="ok", mode="analyze", state=self._state.value,
                    message=f"Dependency analysis for {entity or 'workspace'}.",
                    data=dep_result if isinstance(dep_result, dict) else {"result": str(dep_result)},
                ).to_dict()
            except ImportError:
                pass

        # ── Path 3: Knowledge / API query ──
        if self._is_knowledge_query(request_lower):
            result = self._lookup_knowledge(request_lower)
            if result:
                self._state = KernelState.COMPLETED
                return KernelResult(
                    status="ok", mode="analyze", state=self._state.value,
                    message=f"Knowledge lookup: {result.get('summary', '')}",
                    data=result,
                ).to_dict()

        # ── Path 4: Default — workspace analysis ──
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
        """REPAIR mode: Refactor / Diagnose / Fix / Rollback"""
        self._state = KernelState.REPAIRING
        request_lower = request.lower()

        # ── Refactor operations ──
        if any(kw in request_lower for kw in ("rename", "move", "refactor")):
            try:
                from actions import ActionContext
                ctx = ActionContext(str(self.workspace_root))
                ctx.refresh()
                snapshot = ctx.snapshot
                # Extract params
                import re
                rename_match = re.search(r'rename\s+(?:command\s+)?(\w+)\s+to\s+(\w+)\s+(?:in\s+)?(\w+(?:\.\w+)?)?', request)
                move_match = re.search(r'move\s+(?:command\s+)?(\w+)\s+(?:from\s+)?(\w+(?:\.\w+)?)\s+(?:to\s+)?(\w+(?:\.\w+)?)', request)
                if rename_match:
                    from refactor import rename_command
                    old, new, mod = rename_match.groups()
                    result = rename_command(snapshot, mod or "", old, new)
                    self._state = KernelState.COMPLETED
                    return KernelResult(status="ok", mode="repair", state=self._state.value,
                        message=result.get("message", f"Renamed {old} -> {new}"), data=result).to_dict()
                if move_match:
                    from refactor import move_command
                    cmd, src, tgt = move_match.groups()
                    result = move_command(snapshot, src, tgt, cmd)
                    self._state = KernelState.COMPLETED
                    return KernelResult(status="ok", mode="repair", state=self._state.value,
                        message=result.get("message", f"Moved {cmd}"), data=result).to_dict()
            except ImportError:
                pass

        # ── Rollback operations ──
        if any(kw in request_lower for kw in ("rollback", "list rollback", "backup")):
            try:
                from actions import ActionContext, list_rollback_points, rollback_operation
                ctx = ActionContext(str(self.workspace_root))
                import re
                id_match = re.search(r'(?:to|id)\s+(\w+)', request)
                if id_match:
                    result = rollback_operation(ctx, id_match.group(1))
                else:
                    result = list_rollback_points(ctx)
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="repair", state=self._state.value,
                    message=str(result.get("message", "")), data=result).to_dict()
            except ImportError:
                pass

        # ── Default: Diagnose + Fix loop ──
        # Check if user wants preview mode
        preview_mode = any(kw in request_lower for kw in ("preview", "dry-run", "dry_run", "--preview"))
        # Check if user wants build diagnosis
        with_build = any(kw in request_lower for kw in ("build", "compile", "mkmk", "--build"))

        try:
            from repair import RepairLoop
            loop = RepairLoop(
                workspace_root=self.workspace_root,
                preview=preview_mode,
                with_build=with_build,
            )
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

    # ─── Multi-Intent Handler (v3.1) ───────────────────────────

    def _handle_multi_develop(self, request: str, sub_intents: list,
                               policy: ModePolicy, preview: bool = False) -> dict:
        """
        Handle compound requests with multiple sub-intents.
        Each sub-intent goes through the full develop pipeline independently.
        """
        self._state = KernelState.PLANNING
        all_results = []

        for i, si in enumerate(sub_intents):
            sub_request = si.description or si.goal
            try:
                plan = self._build_develop_plan(sub_request)
                if plan is None:
                    all_results.append({
                        "sub_intent": si.to_dict(),
                        "status": "skipped",
                        "message": f"Cannot build plan for: {sub_request}",
                    })
                    continue

                self._state = KernelState.GENERATING
                result = self._execute_develop_plan(plan, preview=preview)

                # Apply extras for this sub-intent (skip in preview mode)
                if not preview:
                    try:
                        from requirements import RequirementsClarifier, RequirementsDecomposer
                        clarifier = RequirementsClarifier()
                        sub_clarification = clarifier.analyze(sub_request)
                        decomposer = RequirementsDecomposer()
                        extras = decomposer.enhance(sub_clarification)
                        if extras and any(extras.values()):
                            self._apply_extras(plan, extras)
                            result["extras_applied"] = True
                    except ImportError:
                        pass

                # Verify & ensure IdentityCard (skip in preview mode)
                if not preview:
                    verify_result = self._verify_generated_code(plan)
                    if verify_result and verify_result.get("files_checked", 0) > 0:
                        result["verification"] = verify_result
                    ic_ok = self._ensure_identity_card(plan)
                    if ic_ok:
                        result["identity_card"] = ic_ok

                all_results.append({
                    "sub_intent": si.to_dict(),
                    "status": result.get("status", "ok"),
                    "message": result.get("message", ""),
                    "data": result,
                })
            except Exception as e:
                all_results.append({
                    "sub_intent": si.to_dict(),
                    "status": "error",
                    "message": str(e),
                })

        self._state = KernelState.COMPLETED
        ok_count = sum(1 for r in all_results if r.get("status") == "ok")

        if preview:
            return KernelResult(
                status="preview",
                mode="develop", state=self._state.value,
                message=(
                    f"Preview: {len(all_results)} ChangeSets generated but NOT applied. "
                    "Review data.results, then re-run without --preview to apply."
                ),
                data={
                    "multi_intent": True,
                    "preview_mode": True,
                    "total": len(all_results),
                    "completed": ok_count,
                    "results": all_results,
                },
            ).to_dict()

        return KernelResult(
            status="ok" if ok_count == len(all_results) else "partial",
            mode="develop", state=self._state.value,
            message=f"Multi-intent: {ok_count}/{len(all_results)} sub-intents completed.",
            data={
                "multi_intent": True,
                "total": len(all_results),
                "completed": ok_count,
                "results": all_results,
            },
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

        # Auto-detect framework if not specified (prefer .edu with modules)
        if not framework:
            try:
                from analyzer import WorkspaceAnalyzer
                snap = WorkspaceAnalyzer(self.workspace_root).analyze()
                # Prefer frameworks that have modules
                for fw in snap.frameworks:
                    if fw.modules:
                        framework = fw.name
                        break
                if not framework:
                    for fw in snap.frameworks:
                        framework = fw.name
                        break
            except Exception:
                pass

        intent = Intent(
            type=itype,
            name=name,
            module=(module or "MyModule") + ("" if (module or "").endswith(".m") else ".m"),
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

    def _execute_develop_plan(self, plan: dict, preview: bool = False) -> dict:
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
                # CreateCommandWithDialog must actually generate the dialog
                # (files + BuildGraph wiring); otherwise the button opens nothing.
                result = create_executable_command(
                    ctx, name=name, module=module, framework=framework,
                    with_dialog="Dialog" in intent_type,
                )
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
            if not isinstance(result, dict):
                return {"status": "ok", "message": str(result)}

            # DEVELOP mode auto-applies by default (same safety model as REPAIR:
            # backup-then-apply, see backup.BackupManager). Actions return
            # status="pending" with a serialized ChangeSet — that is a preview
            # format, not a final state. Applying here is what actually turns
            # generated code into files on disk; without this step every
            # develop request via CLI/MCP would silently stop at "pending"
            # and downstream phases (extras, verification, IdentityCard) would
            # no-op because the files never existed.
            # When preview=True, skip the apply step entirely and surface the
            # serialized ChangeSet for the caller to review (the whole point
            # of preview mode: allow inspect-then-decide, which is what makes
            # rollback usable in practice).
            if result.get("status") == "pending" and result.get("changeset") and not preview:
                apply_result = self._apply_changeset_dict(result["changeset"])
                result["apply_result"] = apply_result
                if apply_result.get("status") == "applied":
                    result["status"] = "ok"
                    result["message"] = result.get("message", "") + " (applied)"
                else:
                    result["status"] = "error"
                    result["message"] = (
                        "Generated but failed to apply: "
                        + "; ".join(apply_result.get("errors", []) or [apply_result.get("status", "unknown")])
                    )

            return result
        except ImportError:
            return {"status": "pending", "message": f"Plan ready: {intent_type} {name} in {module}"}

    def _apply_changeset_dict(self, changeset_dict: dict) -> dict:
        """Reconstruct a serialized ChangeSet and apply it to the workspace.

        This is the step that turns a 'pending' preview (as returned by
        actions.py/intents/*) into real files on disk, with the same
        backup-before-apply / rollback-on-failure safety as REPAIR mode
        (see backup.BackupManager, changeset.ChangeSet.apply).
        """
        try:
            from changeset import ChangeSet
            cs = ChangeSet.from_dict(changeset_dict)
            return cs.apply(workspace_root=self.workspace_root)
        except Exception as e:
            return {"status": "error", "errors": [str(e)]}

    # ─── Intent Detection ──────────────────────────────────────

    def _detect_intent_type(self, request: str) -> str:
        """Detect IntentType from natural language request (EN + CN)"""
        import re

        # Modifiers that sit AFTER the module separator (e.g.
        # "create command X in M with dialog") are lost when splitting into
        # intent_part — check the full request for them first.
        if ("with dialog" in request or "with a dialog" in request or "带对话框" in request) and (
            "command" in request or "命令" in request
        ):
            return "CreateCommandWithDialog"

        # Extract intent-relevant portion (before module/framework specification)
        # "创建X命令在Y模块" → intent part is "创建X命令"
        intent_part = request
        for sep in (' 在', ' 到', ' in ', ' into ', ' 放在', ' 放到', ' 于'):
            idx = request.find(sep)
            if idx > 0:
                intent_part = request[:idx]
                break

        # Order matters: more specific matches first
        # Chinese keywords first (more specific in CN context)
        # English keywords with word-boundary check (avoid substring matches like testmodule→module)
        mapping = [
            # Chinese keywords (most specific in CN context)
            ("对话框", "CreateCommandWithDialog"),
            ("命令", "CreateCommand"),
            ("特征", "CreateFeature"),
            ("扩展", "CreateExtension"),
            ("接口", "CreateInterface"),
            ("工作台", "CreateWorkbench"),
            ("模块", "CreateModule"),
            ("框架", "CreateFramework"),
            # English keywords (check with word boundaries to avoid substring matches)
        ]
        en_mapping = [
            ("dialog", "CreateCommandWithDialog"),
            ("command", "CreateCommand"),
            ("feature", "CreateFeature"),
            ("extension", "CreateExtension"),
            ("interface", "CreateInterface"),
            ("workbench", "CreateWorkbench"),
            ("module", "CreateModule"),
            ("framework", "CreateFramework"),
        ]
        # Try intent part first (CN keywords)
        for keyword, intent_type in mapping:
            if keyword in intent_part:
                return intent_type
        # Try intent part with EN keywords (word-boundary aware)
        for keyword, intent_type in en_mapping:
            if re.search(r'\b' + keyword + r'\b', intent_part):
                return intent_type
        # Fallback: check full request (CN)
        for keyword, intent_type in mapping:
            if keyword in request:
                return intent_type
        # Fallback: check full request (EN)
        for keyword, intent_type in en_mapping:
            if re.search(r'\b' + keyword + r'\b', request):
                return intent_type
        return "CreateCommand"  # default

    def _extract_entities(self, request: str) -> tuple:
        """Extract (name, module, framework) from natural language request (EN + CN)"""
        import re

        # ASCII-only identifier: [A-Za-z][A-Za-z0-9_]* (NOT \w — includes CJK in Python 3)
        ID = r'[A-Za-z][A-Za-z0-9_]*'
        QID = ID + r'(?:\.' + ID + r')?'  # qualified: Module.m or Framework.edu

        name = None
        module = None
        framework = None

        # Extract intent-relevant portion (before module/framework specification)
        intent_part = request
        # Try spaced separators first
        for sep in (' 在', ' 到', ' in ', ' into ', ' 放在', ' 放到', ' 于'):
            idx = request.find(sep)
            if idx > 0:
                intent_part = request[:idx]
                break
        # CN without spaces: remove "在<Module>模块" / "到<Module>" tail
        if intent_part == request:
            # Pattern: <location_word><ModuleName>模块
            m = re.search(r'(?:在|到|放在|放到)\s*(' + QID + r')\s*(?:模块|中|里)?', request)
            if m:
                intent_part = request[:m.start()]

        # ── Name patterns (scoped to intent_part) ──
        CN_TYPES = r'(?:命令|对话框|特征|工作台|模块|框架)'
        # EN: "create command <Name>" / "make a <Name>"
        m = re.search(r'(?:create|make|generate)\s+(?:a\s+)?' + ID + r'\s+(' + ID + ')', intent_part)
        if m:
            name = m.group(1)
        # CN: "<CamelCase>命令" / "叫<CamelCase>的命令"
        if not name:
            m = re.search(r'(?:叫|名为)?\s*(' + ID + r')\s*(?:的)?\s*' + CN_TYPES, intent_part)
            if m:
                # Exclude names that look like module specs
                if not m.group(1).lower().endswith('module'):
                    name = m.group(1)
        # CN: "命令<CamelCase>" (type before name)
        if not name:
            m = re.search(CN_TYPES + r'\s*(' + ID + ')', intent_part)
            if m:
                name = m.group(1)
        # CN: "创建<Name>命令" (verb + name + optional type)
        if not name:
            m = re.search(r'(?:创建|新建|生成|添加|增加)\s*(?:一个|新的)?\s*' + CN_TYPES + r'?\s*(' + ID + ')', intent_part)
            if m:
                name = m.group(1)

        # ── Module patterns ──
        # EN: "in <Module>" / "module <Module>"
        m = re.search(r'(?:in|into|module)\s+(' + QID + ')', request, re.IGNORECASE)
        if m:
            module = m.group(1)
        # CN: "在<Module>模块" / "<Module>模块中" / "放在<Module>模块"
        if not module:
            m = re.search(r'(?:在|放到|放在|到)\s*(' + QID + r')\s*模块', request)
            if m:
                module = m.group(1)
        # CN: "到<Module>" (without 模块, e.g., "添加对话框X到Module")
        if not module:
            m = re.search(r'(?:在|放到|放在|到)\s*(' + QID + r')(?:\s|$)', request)
            if m and m.group(1) not in ('一个', '新的'):
                module = m.group(1)
        if not module:
            m = re.search(r'(' + QID + r')\s*模块\s*(?:中|里|内)', request)
            if m:
                module = m.group(1)

        # ── Framework patterns ──
        # EN: "framework <Framework>" / "fw <Framework>"
        m = re.search(r'(?:framework|fw)\s+(' + QID + ')', request, re.IGNORECASE)
        if m:
            framework = m.group(1)
        # CN: "框架<Framework>" / "<Framework>框架"
        if not framework:
            m = re.search(r'框架\s*(?:叫|是|为)?\s*(' + QID + ')', request)
            if m:
                framework = m.group(1)
        if not framework:
            m = re.search(r'(' + QID + r')\s*框架', request)
            if m:
                framework = m.group(1)

        return name, module, framework

    def _apply_extras(self, plan: dict, extras: dict) -> dict:
        """
        Apply cross-domain extras: generate extra components and update dependencies.

        Handles:
          - extra_components: data_extension → create context menu extension files
          - imakefile_deps: add frameworks to LINK_WITH
          - playbooks: inject as code comments for AI reference
          - capabilities: inject as code comments for AI reference
        """
        applied = {"components": [], "deps_added": [], "refs_added": []}
        intent_data = plan.get("intent", {})
        name = intent_data.get("name", "")
        module = intent_data.get("module", "MyModule.m")
        framework = intent_data.get("framework", "MyFramework")

        if not name or not module:
            return applied

        module_path = self.workspace_root / module
        if not module_path.exists():
            return applied

        # Apply imakefile dependencies
        if extras.get("imakefile_deps"):
            imakefile = module_path / "Imakefile.mk"
            if imakefile.exists():
                content = imakefile.read_text(encoding="utf-8", errors="replace")
                for dep in extras["imakefile_deps"]:
                    if dep not in content:
                        # Add to LINK_WITH or append new deps
                        if "LINK_WITH" in content:
                            new_content = content.replace(
                                "LINK_WITH =", f"LINK_WITH = {dep}"
                            ) if "LINK_WITH =" in content and "LINK_WITH = " not in content.split("LINK_WITH =")[-1].split("\n")[0].strip() else content
                            if dep not in new_content:
                                lines = new_content.split("\n")
                                for i, line in enumerate(lines):
                                    if line.strip().startswith("LINK_WITH"):
                                        lines[i] = line.rstrip() + " " + dep
                                        break
                                new_content = "\n".join(lines)
                            imakefile.write_text(new_content, encoding="utf-8")
                            applied["deps_added"].append(dep)

        # Inject playbook/capability references as comments in the main .cpp
        refs = []
        if extras.get("playbooks"):
            refs.append(f"// CADE Playbooks: {', '.join(extras['playbooks'])}")
        if extras.get("capabilities"):
            refs.append(f"// CADE Capabilities: {', '.join(extras['capabilities'])}")
        if extras.get("knowledge_refs"):
            refs.append(f"// CADE Knowledge: {', '.join(extras['knowledge_refs'])}")
        if extras.get("pattern_refs"):
            refs.append(f"// CADE Patterns: {', '.join(extras['pattern_refs'])}")
        if extras.get("extra_components"):
            refs.append(f"// CADE Extra Components: {', '.join(extras['extra_components'])}")

        if refs and name:
            src_dir = module_path / "src"
            cpp_file = src_dir / f"{name}.cpp"
            if cpp_file.exists():
                content = cpp_file.read_text(encoding="utf-8", errors="replace")
                if "CADE Playbooks" not in content:
                    for r in refs:
                        if r not in content:
                            # Insert after the last #include
                            lines = content.split("\n")
                            last_include = 0
                            for i, line in enumerate(lines):
                                if line.strip().startswith("#include"):
                                    last_include = i
                            if last_include >= 0:
                                lines.insert(last_include + 1, r)
                                cpp_file.write_text("\n".join(lines), encoding="utf-8")
                                applied["refs_added"].append(r)

        return applied

    def _verify_generated_code(self, plan: dict) -> dict:
        """Run static code verification on generated files if module exists."""
        try:
            from verifier import CodeVerifier
            intent_data = plan.get("intent", {})
            module_name = intent_data.get("module", "")
            if not module_name:
                return {}
            module_path = self.workspace_root / module_name
            if not module_path.exists():
                return {}
            verifier = CodeVerifier()
            result = verifier.verify_module(module_path)
            return result.to_dict()
        except ImportError:
            return {}
        except Exception:
            return {}

    def _ensure_identity_card(self, plan: dict) -> dict:
        """Ensure IdentityCard is created so mkmk build won't fail.
        Auto-runs mkCreateIC if Build Time env is available."""
        intent_data = plan.get("intent", {})
        framework = intent_data.get("framework", "")
        if not framework:
            return {}
        fw_name = framework if framework.endswith(".edu") else framework + ".edu"
        fw_dir = self.workspace_root / fw_name
        if not fw_dir.exists():
            return {}
        ic = fw_dir / "IdentityCard" / "IdentityCard.xml"
        if not ic.exists():
            ic = fw_dir / "IdentityCard" / "IdentityCard.h"
        if not ic.exists():
            return {}
        # Check if mkCreateIC already run
        ic_dir = fw_dir / "IdentityCard"
        has_binary = ic_dir.exists() and any(
            f.suffix in (".obj", "") and "IdentityCard" in f.name
            for f in ic_dir.iterdir()
        )
        if has_binary:
            return {"status": "ok", "message": "IdentityCard already up to date."}
        try:
            from build import create_identity_card
            base = framework.replace(".edu", "")
            result = create_identity_card(self.workspace_root, base)
            ok = result.get("status") == "success"
            return {
                "status": "created" if ok else "pending",
                "message": "IdentityCard auto-created." if ok else
                    f"Run manually: mkCreateIC {base}",
            }
        except ImportError:
            return {"status": "pending", "message": f"Run: mkCreateIC {framework.replace('.edu', '')}"}
        except Exception as e:
            return {"status": "pending", "message": f"IdentityCard: {e}"}

    # ─── Knowledge Lookup ──────────────────────────────────────

    # Keywords that suggest knowledge/API query (not workspace operation)
    _KNOWLEDGE_KW = (
        "fillet", "hole", "chamfer", "pad", "pocket",
        "product", "assembly", "constraint", "bom",
        "dialog", "ui", "layout", "toolbar", "menu", "workbench",
        "context menu", "右键", "undo", "redo", "update mechanism",
        "selection", "viewer", "gsd", "surface", "drawing", "fta",
        "annotation", "tolerance", "命名", "规范", "生命周期",
        "api", "interface", "class", "method", "function",
        "pattern", "example", "tutorial", "documentation", "reference",
        "implement", "explain", "describe",
    )
    _KNOWLEDGE_QUESTION_WORDS = (
        "how do", "how to", "how does", "what is", "what are", "what does",
        "where is", "which ", "when ",
    )

    def _is_knowledge_query(self, request: str) -> bool:
        """Detect if this is a knowledge/API question, not a workspace operation"""
        import re
        # Check built-in keywords (short ones use word-boundary)
        for kw in self._KNOWLEDGE_KW:
            if len(kw) <= 2:
                if re.search(r'\b' + re.escape(kw) + r'\b', request):
                    return True
            elif kw in request:
                return True
        # Check alias keys via CatalogIndex (Chinese synonyms not in _KNOWLEDGE_KW)
        try:
            from catalog import CatalogIndex
            catalog = CatalogIndex.load(Path(__file__).parent.parent)
            if catalog.has_alias_match(request):
                return True
        except Exception:
            pass
        # Check question patterns
        return any(request.startswith(q) for q in self._KNOWLEDGE_QUESTION_WORDS)

    def _lookup_knowledge(self, request: str) -> dict:
        """
        Search knowledge base via CatalogIndex (unified model).
        Alias expansion and keyword matching handled internally.
        """
        skill_root = Path(__file__).parent.parent
        results = []
        domain_hint = ""

        # Step 1: Detect domain
        try:
            from requirements import RequirementsClarifier
            clarifier = RequirementsClarifier()
            domain_hint = clarifier._detect_domain(request)
        except Exception:
            pass

        # Step 2: Search via CatalogIndex (handles alias expansion internally)
        try:
            from catalog import CatalogIndex
            catalog = CatalogIndex.load(skill_root)
            entries = catalog.search(request, max_results=10)
            results = [e.raw_line for e in entries]
        except Exception:
            pass

        # Step 3: Build response
        summary_parts = []
        if domain_hint and domain_hint != "general":
            summary_parts.append(f"Domain: {domain_hint}")
        if results:
            summary_parts.append(f"Found {len(results)} references")

        return {
            "summary": "; ".join(summary_parts) if summary_parts else "Knowledge base searched",
            "domain": domain_hint,
            "references": results,
            "hint": "For detailed API code, check knowledge/ files matched above. For official docs, see CAADoc via knowledge/frameworks/.",
        }

    # ─── Build / Run / Support Routing ─────────────────────────

    def _handle_build_run(self, request: str) -> Optional[dict]:
        """Route build, run, setup, version, doc, and prerequisite operations. Returns None if no match."""
        from typing import Optional
        self._state = KernelState.GENERATING

        # Build
        try:
            from build import incremental_build, full_build, clean_build, build_with_threads, create_runtime_view, setup_prerequisite_path
            ws = self.workspace_root

            # Setup prerequisite path (auto-link to CATIA installation)
            if any(kw in request for kw in ("setup prereq", "setup workspace", "init workspace")):
                r = setup_prerequisite_path(ws)
                self._state = KernelState.COMPLETED
                return KernelResult(status=r.get("status", "ok"), mode="develop", state=self._state.value,
                    message="Workspace prerequisites configured.", data=r if isinstance(r, dict) else {}).to_dict()

            if any(kw in request for kw in ("build", "compile", "mkmk")):
                import re
                n = int(re.search(r'(\d+)\s*thread', request).group(1)) if re.search(r'(\d+)\s*thread', request) else 8
                r = (full_build(ws) if "full" in request else
                     clean_build(ws) if "clean" in request else
                     build_with_threads(ws, n) if "thread" in request else
                     incremental_build(ws))
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message=r.get("message", "Build complete."), data=r if isinstance(r, dict) else {}).to_dict()
            if "runtime view" in request or "runtimeview" in request:
                r = create_runtime_view(ws)
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message="Runtime view created.", data=r if isinstance(r, dict) else {}).to_dict()
        except ImportError:
            pass

        # Run
        try:
            from run import start_catia_runtime, stop_catia, check_catia_running, run_catia_macro, run_catia_batch
            if "start catia" in request or "launch catia" in request:
                r = start_catia_runtime(workspace_path=str(self.workspace_root))
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message="CATIA started.", data=r if isinstance(r, dict) else {}).to_dict()
            # Dev: build + run in one step
            if "dev" in request or ("build" in request and "run" in request):
                r_build = incremental_build(ws)
                r_run = start_catia_runtime(workspace_path=str(self.workspace_root)) if r_build.get("status") == "success" else None
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message=f"Build: {r_build.get('message','')}; Run: {r_run.get('message','')}" if r_run else r_build.get('message',''),
                    data={"build": r_build, "run": r_run}).to_dict()
            if "stop catia" in request or "kill catia" in request:
                r = stop_catia()
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message="CATIA stopped.").to_dict()
            if "catia running" in request or "check catia" in request:
                r = check_catia_running()
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message=r.get("status", "checked") if isinstance(r, dict) else str(r)).to_dict()
            if "macro" in request:
                import re
                m = re.search(r'([\w.-]+\.CATScript)', request)
                r = run_catia_macro(m.group(1) if m else request)
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message="Macro executed.").to_dict()
            if "batch" in request:
                r = run_catia_batch()
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message="Batch executed.").to_dict()
        except ImportError:
            pass

        # Setup / Version / Docs / Prereq
        if any(kw in request for kw in ("setup", "configure", "environment", "detect catia")):
            try:
                from env import CAAEnvironment
                env = CAAEnvironment(); env.load_config()
                info = env.get_info()
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message=f"CATIA: {info.get('catia_version', 'unknown')}", data=info).to_dict()
            except ImportError:
                pass
        if "version" in request:
            self._state = KernelState.COMPLETED
            return KernelResult(status="ok", mode="develop", state=self._state.value,
                message="CADE v3.2.1", data={"version": "3.2.1"}).to_dict()
        if any(kw in request for kw in ("docs", "documentation", "generate doc")):
            try:
                from docgen import generate_all
                generate_all(str(self.workspace_root))
            except ImportError:
                pass
            self._state = KernelState.COMPLETED
            return KernelResult(status="ok", mode="develop", state=self._state.value,
                message="Documentation generated.").to_dict()
        if "prereq" in request or "prerequisite" in request:
            self._state = KernelState.COMPLETED
            return KernelResult(status="ok", mode="develop", state=self._state.value,
                message="Prerequisites: use 'cade prereq' CLI for full management.").to_dict()

        return None
