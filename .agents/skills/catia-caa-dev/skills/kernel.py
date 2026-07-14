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
        request_lower = request.lower()

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
        result = self._execute_develop_plan(plan)

        # Phase 2.5: Apply cross-domain extras (data_extension, imakefile deps)
        if extras and any(extras.values()):
            apply_result = self._apply_extras(plan, extras)
            if apply_result:
                result["extras_applied"] = apply_result

        # Phase 3: Static verification of generated code
        verify_result = self._verify_generated_code(plan)
        if verify_result and verify_result.get("files_checked", 0) > 0:
            result["verification"] = verify_result

        # Phase 3.5: Ensure IdentityCard (prevent mkmk build failures)
        ic_ok = self._ensure_identity_card(plan)
        if ic_ok:
            result["identity_card"] = ic_ok

        self._state = KernelState.COMPLETED
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
        ic_h = fw_dir / "IdentityCard" / "IdentityCard.h"
        if not ic_h.exists():
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
        return any(kw in request for kw in self._KNOWLEDGE_KW) or \
               any(request.startswith(q) for q in self._KNOWLEDGE_QUESTION_WORDS)

    def _lookup_knowledge(self, request: str) -> dict:
        """
        Search knowledge base for relevant information.

        Uses catalog/index.yaml for fast keyword→file mapping,
        with alias expansion for Chinese synonyms and terminology variants.
        """
        skill_root = Path(__file__).parent.parent
        catalog_file = skill_root / "catalog" / "index.yaml"

        results = []
        domain_hint = ""

        # Step 1: Expand aliases (Chinese synonyms → English keywords)
        aliases = self._load_aliases(catalog_file)
        expanded_request = request
        for alias, keywords in aliases.items():
            if alias in request:
                expanded_request += " " + keywords

        # Step 2: Detect domain from request
        try:
            from requirements import RequirementsClarifier
            clarifier = RequirementsClarifier()
            domain_hint = clarifier._detect_domain(request)
        except Exception:
            pass

        # Step 3: Search catalog index for keyword matches (with alias expansion)
        if catalog_file.exists():
            catalog_content = catalog_file.read_text(encoding="utf-8", errors="replace")
            # Skip aliases table for matching
            parts = catalog_content.split("## 别名映射")
            search_content = parts[0] if len(parts) > 1 else catalog_content
            search_content += "\n" + (parts[1].split("## 索引")[0] if len(parts) > 1 and "## 索引" in parts[1] else "")
            for line in search_content.split("\n"):
                line_lower = line.lower()
                if "|" not in line_lower:
                    continue
                # Match: check if any request keyword (or expanded alias) appears
                if any(kw in line_lower for kw in expanded_request.split() if len(kw) >= 3):
                    results.append(line.strip())
                    if len(results) >= 10:
                        break

        # Step 4: Build domain-aware response
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

    def _load_aliases(self, catalog_file: Path) -> dict:
        """Parse aliases section from catalog/index.yaml.
        Returns dict mapping alias (Chinese) → expanded keywords (English)."""
        aliases = {}
        if not catalog_file.exists():
            return aliases
        try:
            content = catalog_file.read_text(encoding="utf-8", errors="replace")
            in_aliases = False
            for line in content.split("\n"):
                if "## 别名映射" in line:
                    in_aliases = True
                    continue
                if in_aliases:
                    if line.startswith("## ") and "别名" not in line:
                        break
                    if "|" in line and not line.strip().startswith("|"):
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 3:
                            alias = parts[1].strip()
                            keywords = parts[2].strip()
                            aliases[alias] = keywords
        except Exception:
            pass
        return aliases

    # ─── Build / Run / Support Routing ─────────────────────────

    def _handle_build_run(self, request: str) -> Optional[dict]:
        """Route build, run, setup, version, doc, and prerequisite operations. Returns None if no match."""
        from typing import Optional
        self._state = KernelState.GENERATING

        # Build
        try:
            from build import incremental_build, full_build, clean_build, build_with_threads, create_runtime_view
            ws = self.workspace_root
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
                message="CADE v3.0.0", data={"version": "3.0.0"}).to_dict()
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
