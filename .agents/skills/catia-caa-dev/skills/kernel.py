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

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Kernel execution telemetry — append-only JSONL, same shape as build_gate's
# log so monthly stats can answer "where does the agent fail/rework most?"
_KERNEL_LOG = Path(__file__).resolve().parent.parent / "cache" / "kernel_log.jsonl"
# Rotate the log once it exceeds this size: keep one prior generation
# (kernel_log.jsonl.1) so the file cannot grow unbounded (it reached 2MB+
# with no consumer-based pruning in sight).
_KERNEL_LOG_MAX_BYTES = 5 * 1024 * 1024


def _log_kernel(record: dict) -> None:
    """Append one telemetry record. Fail-silent: telemetry never breaks execution."""
    try:
        _KERNEL_LOG.parent.mkdir(parents=True, exist_ok=True)
        record.setdefault("time", datetime.now().isoformat(timespec="seconds"))
        if _KERNEL_LOG.exists() and _KERNEL_LOG.stat().st_size > _KERNEL_LOG_MAX_BYTES:
            rotated = Path(str(_KERNEL_LOG) + ".1")
            try:
                if rotated.exists():
                    rotated.unlink()
                _KERNEL_LOG.rename(rotated)
            except OSError:
                pass  # rotation is best-effort; keep appending either way
        with open(_KERNEL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


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
        return {k: v for k, v in d.items() if v is False or v}  # strip empty but keep boolean False


# ─── Kernel ───────────────────────────────────────────────────────


class Kernel:
    """
    CADE Development Kernel — unified execution entry point.

    AI-facing: 3 modes (DEVELOP, ANALYZE, REPAIR)
    Internal: state machine + module dispatch
    """

    def __init__(self, workspace_root: str = None):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()
        self._state = KernelState.IDLE

    @property
    def retrieval(self):
        """Unified retrieval facade — loaded once per process."""
        if not getattr(self, '_retrieval_attempted', False):
            self._retrieval_attempted = True
            try:
                from retrieval import get_retrieval
                self._retrieval_facade = get_retrieval(Path(__file__).parent.parent)
            except Exception:
                self._retrieval_facade = None
        return getattr(self, '_retrieval_facade', None)

    @property
    def catalog(self):
        """Shared CatalogIndex from the retrieval facade — loaded once per
        process, then reused by _is_knowledge_query / _lookup_knowledge /
        _consult_knowledge. Goes through get_retrieval() rather than
        CatalogIndex.load() so the facade owns the index lifecycle
        (see docs/architecture/retrieval.md, Mandatory Entry Point)."""
        r = self.retrieval
        if r is not None:
            try:
                return r.catalog
            except Exception:
                return None
        return None

    # ─── Public API ────────────────────────────────────────────

    def execute(self, mode: KernelMode, request: str, preview: bool = False,
                detail: bool = False) -> dict:
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
        t0 = time.perf_counter()
        result: dict

        try:
            if mode == KernelMode.DEVELOP:
                result = self._handle_develop(request, policy, preview=preview)
            elif mode == KernelMode.ANALYZE:
                result = self._handle_analyze(request, policy, detail=detail)
            elif mode == KernelMode.REPAIR:
                result = self._handle_repair(request, policy)
            else:
                result = KernelResult(
                    status="error", mode=mode.value,
                    message=f"Unknown mode: {mode}",
                ).to_dict()
        except Exception as e:
            self._state = KernelState.FAILED
            result = KernelResult(
                status="error", mode=mode.value, state=self._state.value,
                message=str(e),
            ).to_dict()

        _log_kernel({
            "kind": "run",
            "mode": mode.value,
            "status": result.get("status", "?"),
            "end_state": self._state.value,
            "multi_intent": bool(result.get("multi_intent")),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
        })
        return result

    # ─── Mode Handlers ─────────────────────────────────────────

    def _handle_develop(self, request: str, policy: ModePolicy, preview: bool = False) -> dict:
        """DEVELOP mode: Requirement → Intent → Plan → Generate → Verify"""
        self._state = KernelState.CLARIFYING
        request_lower = request.lower()

        # Phase 0.5: Brownfield Maintenance Routing (v3.2.2 P1)
        try:
            from actions import ActionContext
            ctx = ActionContext(str(self.workspace_root))
            m_info = self._parse_maintenance_request(request, ctx)
            if m_info:
                target_mod = m_info["module"]
                analysis_res = self._analyze_target_module(target_mod, ctx, request, maintenance_info=m_info)
                self._state = KernelState.COMPLETED
                analysis_data = analysis_res.get("data", {}) or analysis_res
                problem_desc = m_info.get("problem_description", "")

                guidance = [
                    f"1. Target module confirmed: {target_mod.name} (framework: {target_mod.framework.name if target_mod.framework else 'unknown'}).",
                ]
                active_build_errs = analysis_data.get("active_build_errors", [])
                if active_build_errs:
                    guidance.append(f"2. [CRITICAL] {len(active_build_errs)} active compiler/linker error(s) from previous build. Address these L0 direct evidence issues first.")
                elif problem_desc:
                    guidance.append(f"2. Focus area: '{problem_desc}'. See relevant_locations ({len(analysis_data.get('relevant_locations', []))} found) and failure_patterns.")
                else:
                    guidance.append("2. Inspect files, symbols, and diagnostic/verification findings in the module.")

                v_summary = analysis_data.get("verification", {}).get("summary", {})
                code_errs = v_summary.get("code_errors", 0)
                ui_errs = v_summary.get("ui_findings", 0)
                if code_errs or ui_errs:
                    guidance.append(f"3. Address {code_errs} code issue(s) and {ui_errs} UI failure pattern(s) identified.")
                else:
                    guidance.append("3. Make necessary edits in source/header files (zero destructive changes applied by CADE).")

                guidance.append("4. Trigger Kernel build via develop('build') or 'cade build'.")
                guidance.append("5. Verify runtime behavior with CATIA runtime view.")

                return KernelResult(
                    status="ok",
                    mode="develop",
                    state=self._state.value,
                    message=f"Identified brownfield maintenance for module {target_mod.name}. Provided source, build, diagnostic, verification, and knowledge analysis.",
                    data={
                        "task_type": "maintain_existing_module",
                        "target_module": target_mod.name,
                        "problem_description": problem_desc,
                        "analysis": analysis_data,
                        "relevant_locations": analysis_data.get("relevant_locations", []),
                        "active_build_errors": analysis_data.get("active_build_errors", []),
                        "task_id": analysis_data.get("task_id", ""),
                        "verification": analysis_data.get("verification", {}),
                        "failure_patterns": analysis_data.get("failure_patterns", []),
                        "guidance": guidance,
                    }
                ).to_dict()
        except Exception:
            pass

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
            self._state = KernelState.FAILED
            return KernelResult(
                status="error", mode="develop", state=self._state.value,
                message=f"Cannot build development plan for: {request}",
            ).to_dict()

        self._state = KernelState.GENERATING
        result = self._execute_develop_plan(plan, preview=preview)

        if isinstance(result, dict) and result.get("status") in ("error", "blocked"):
            self._state = KernelState.FAILED
            return KernelResult(
                status="error", mode="develop",
                state=self._state.value,
                message=result.get("message", "Development failed."),
                data=result,
            ).to_dict()

        # Phase 2.2: Knowledge grounding — only when evidence demand is TARGETED.
        # Pure scaffolds (framework, module, component, interface, bare command)
        # have self-contained templates and skip grounding, eliminating
        # gratuitous Catalog searches and irrelevant doc injection (T1~T3).
        evidence_demand = self._determine_evidence_demand(plan, request)
        if evidence_demand != "none":
            knowledge_refs, matched_entries = self._consult_knowledge(request)
            if knowledge_refs:
                result["knowledge_refs"] = knowledge_refs

            # Phase 2.3: Auto-inject knowledge CONTENT so every caller generates
            # against verified API patterns. Skipped in preview (nothing generated yet).
            # Reuses matched_entries from Phase 2.2 to eliminate duplicate Catalog searches.
            if not preview and matched_entries:
                try:
                    ref_ids = {r["id"] for r in knowledge_refs if r.get("id")}
                    ranked = [e for e in matched_entries if e.id in ref_ids]
                    if ranked:
                        result["knowledge_content"] = self._read_knowledge_files(
                            ranked, max_files=2, max_chars_per_file=8000,
                            max_total_chars=12000)
                except Exception:
                    pass  # grounding is best-effort, never blocks develop

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
                # Surface violations as a top-level, impossible-to-miss field.
                # Agents that skip the 'verification' blob still trip over this.
                if verify_result.get("error_count", 0) > 0:
                    result["verification_failed"] = True
                    result["verification_errors"] = [
                        i for i in verify_result.get("issues", [])
                        if i.get("severity") == "error"
                    ][:5]

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

    def _handle_analyze(self, request: str, policy: ModePolicy, detail: bool = False) -> dict:
        """ANALYZE mode: Knowledge search / diagnostics / workspace (read-only)"""
        self._state = KernelState.PLANNING
        request_lower = request.lower()

        # ── Path 0: Native Investigation Advisory (Tier A Explicit Candidate) ──
        # Evaluated before Diagnostics/Dependency so that queries like
        # "verify native command vtable" or "check CATIA native command DLL"
        # are not hijacked by workspace diagnostics or dependency analyzers.
        investigation_result = self._try_native_investigation_advisory(request)
        if investigation_result:
            self._state = KernelState.COMPLETED
            return investigation_result

        # ── Path 0.5: Module-scoped Deep Analysis (Brownfield Targeted View) ──
        try:
            from actions import ActionContext
            ctx = ActionContext(str(self.workspace_root))
            m_info = self._parse_maintenance_request(request, ctx)
            target_mod = m_info["module"] if m_info else self._find_target_module(request, ctx)
            if target_mod:
                mod_analysis = self._analyze_target_module(target_mod, ctx, request, maintenance_info=m_info)
                self._state = KernelState.COMPLETED
                return mod_analysis
        except Exception:
            pass

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

        # ── Path 3a: Header / Framework structural query (HeaderMap authoritative index) ──
        header_result = self._try_header_lookup(request)
        if header_result:
            self._state = KernelState.COMPLETED
            return header_result

        # ── Path 3b: Interface / Method structural query (MethodIndex authoritative index) ──
        method_result = self._try_method_lookup(request)
        if method_result:
            self._state = KernelState.COMPLETED
            return method_result

        # ── Path 3c: General Knowledge / API query (Catalog semantic search) ──
        if self._is_knowledge_query(request_lower):
            result = self._lookup_knowledge(request_lower, include_content=detail)
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
                entrypoint="kernel",
                orchestrated_by_kernel=True,
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

    def _determine_evidence_demand(self, plan: dict, request: str) -> str:
        """Determine knowledge evidence demand for DEVELOP pipeline.

        Returns:
            "none": Scaffold/boilerplate generation with self-contained templates.
                    No external API knowledge grounding needed (eliminates redundant
                    Catalog queries and context pollution).
            "targeted": Request involves specific CAA domain concepts (selection,
                        color, BRep, geometry, etc.) that benefit from verified
                        API pattern injection.
        """
        intent_data = plan.get("intent", {}) if plan else {}
        intent_type = intent_data.get("type", "")

        # 1. Deterministic structural scaffolds: always "none"
        if intent_type in ("CreateFramework", "CreateModule", "CreateComponent", "CreateInterface"):
            return "none"

        # 2. Command / Dialog: check if specific domain API evidence is requested
        domain_triggers = (
            "select", "pick", "filter", "color", "vis", "render",
            "brep", "topo", "geom", "curve", "surface", "mesh",
            "feature", "part", "product", "asm", "assembly", "constraint",
            "update", "recompute", "persist", "stream", "container",
            "drafting", "drawing", "view", "sheet", "ref",
            "选择", "过滤", "颜色", "渲染", "拓扑", "几何", "曲面", "网格",
            "特征", "装配", "约束", "更新", "持久化", "工程图", "参考",
        )
        req_lower = request.lower()
        if any(trigger in req_lower for trigger in domain_triggers):
            return "targeted"

        # Pure command/dialog scaffolds without domain features are self-contained
        if intent_type in ("CreateCommand", "CreateCommandWithDialog", "CreateDialog"):
            return "none"

        return "none"

    def _try_header_lookup(self, request: str) -> Optional[dict]:
        """Check if request is an authoritative header/framework lookup (HeaderMap)."""
        import re
        request_lower = request.lower()

        # Pattern 1: explicit .h file mentioned, e.g. "CATIVisProperties.h 在哪个 Framework"
        h_match = re.search(r'\b([A-Za-z0-9_]+)\.h\b', request, re.IGNORECASE)
        stem = None
        if h_match:
            stem = h_match.group(1)
        elif any(kw in request_lower for kw in ("header", "头文件")) and any(
            kw in request_lower for kw in ("framework", "框架", "module", "模块", "which", "where", "哪", "属于", "位于")
        ):
            # Pattern 2: "CATIVisProperties 头文件在哪个框架"
            id_match = re.search(r'\b(CAT[A-Z0-9][A-Za-z0-9_]*)\b', request)
            if id_match:
                stem = id_match.group(1)

        if not stem:
            return None

        # Check if query intent relates to header location / framework attribution
        header_intent = (
            h_match is not None
            or any(kw in request_lower for kw in ("framework", "框架", "module", "模块", "which", "where", "哪", "属于", "位于", "header", "头文件"))
        )
        if not header_intent:
            return None

        r = self.retrieval
        if not r:
            return None

        try:
            hm = r.header_map
            hit = hm.lookup(stem) if hm else None
        except Exception:
            hit = None

        if hit:
            mod, fw = hit
            return KernelResult(
                status="ok", mode="analyze", state=self._state.value,
                message=f"{stem}.h belongs to Framework '{fw}' (Module '{mod}').",
                data={
                    "query_type": "header_lookup",
                    "header": f"{stem}.h",
                    "framework": fw,
                    "module": mod,
                },
            ).to_dict()

        # If explicit .h was queried with location intent, early stop with not found instead of falling through
        if h_match and any(kw in request_lower for kw in ("framework", "框架", "module", "模块", "which", "where", "哪", "属于", "位于")):
            return KernelResult(
                status="ok", mode="analyze", state=self._state.value,
                message=f"Header '{stem}.h' was not found in HeaderMap index.",
                data={
                    "query_type": "header_lookup",
                    "header": f"{stem}.h",
                    "matched": "not_found",
                },
            ).to_dict()

        return None

    def _try_method_lookup(self, request: str) -> Optional[dict]:
        """Check if request is an authoritative interface/method query (MethodIndex)."""
        import re
        request_lower = request.lower()

        # Check intent: querying methods of a type
        method_keywords = (
            "method", "methods", "方法", "函数", "有哪些方法", "包含哪些方法",
            "包含什么方法", "提供的方法", "接口方法", "api", "apis"
        )
        if not any(kw in request_lower for kw in method_keywords):
            return None

        # Extract candidate CAA type name: typically CAT[A-Z0-9]\w+ or PascalCase
        type_candidates = re.findall(r'\b(CAT[A-Z0-9][A-Za-z0-9_]*)\b', request)
        if not type_candidates:
            m = re.search(r'(?:methods?\s+of|method\s+in)\s+([A-Za-z0-9_]+)', request, re.IGNORECASE)
            if m:
                type_candidates = [m.group(1)]

        if not type_candidates:
            return None

        r = self.retrieval
        if not r:
            return None

        try:
            mi = r.method_index
            if not mi:
                return None
        except Exception:
            return None

        for cand in type_candidates:
            if mi.has_type(cand):
                methods = mi.methods_of(cand)
                return KernelResult(
                    status="ok", mode="analyze", state=self._state.value,
                    message=f"Found {len(methods)} methods for {cand}.",
                    data={
                        "query_type": "method_lookup",
                        "type": cand,
                        "methods": methods,
                        "count": len(methods),
                    },
                ).to_dict()

        return None

    # ─── Native Investigation (Tier A Advisory) ─────────────────

    _NATIVE_INVESTIGATION_SIGNALS = (
        "native command", "native commands", "private interface", "private interfaces",
        "vtable", "virtual table", "reverse engineering", "undocumented api", "no public api",
        "原生命令", "私有接口", "非公开接口", "虚表", "虚函数表", "槽位", "逆向",
        "无公开api", "官方文档查不到",
    )
    _PUBLIC_DOC_SIGNALS = (
        "公开", "官方", "文档", "public", "official", "caadoc", "documentation", "doc",
    )

    def _has_native_investigation_signal(self, request: str) -> bool:
        """Check if request contains explicit Tier A native investigation signals."""
        import re
        req_lower = request.lower()
        for sig in self._NATIVE_INVESTIGATION_SIGNALS:
            if sig in req_lower:
                return True
        if re.search(r'\bslots?\b', req_lower):
            return True
        return False

    def _try_native_investigation_advisory(self, request: str) -> Optional[dict]:
        """Check if request warrants a native investigation advisory (Tier A candidate)."""
        if not self._has_native_investigation_signal(request):
            return None

        req_lower = request.lower()
        has_negative_public = any(neg in req_lower for neg in ("无公开", "非公开", "没有公开", "no public", "without public", "查不到"))
        has_public_intent = not has_negative_public and any(sig in req_lower for sig in self._PUBLIC_DOC_SIGNALS)

        ref_line = "| pb.native_command_investigation | playbooks/pb_native_command_investigation.md | 原生命令逆向调查方法论 | - |"
        references = [ref_line]

        if has_public_intent:
            public_refs = []
            try:
                if self.catalog:
                    entries = self.catalog.search(request, max_results=5)
                    public_refs = [
                        e.raw_line for e in entries
                        if e.raw_line and "pb.native_command_investigation" not in e.raw_line
                    ]
            except Exception:
                pass

            return KernelResult(
                status="ok",
                mode="analyze",
                state=self._state.value,
                message="Native investigation advisory: verify official CAA API and documentation first.",
                data={
                    "query_type": "native_investigation_advisory",
                    "intent_confidence": "candidate",
                    "investigation_recommended": False,
                    "evidence_boundary": "experimental_not_public_api_contract",
                    "playbook": "pb.native_command_investigation",
                    "file": "playbooks/pb_native_command_investigation.md",
                    "advisory": {
                        "trigger_reason": "Query mentions native command alongside public API/documentation intent.",
                        "recommendation": "Verify official CAA documentation first before escalating to reverse engineering.",
                        "investigation_ladder": [
                            "P0 官方 API 检索与 CAADoc 查阅",
                            "P1 官方用例与头文件确认",
                            "P2 已知 Knowledge / Playbook 方案",
                            "P3 原生命令标识与所属 DLL 定位",
                            "P4 二进制/虚表/符号深入排查",
                        ],
                        "core_guardrail": "核心原则：逆向工程证据（如虚表槽位/Slot）是经验性事实证据，不是 Dassault Systèmes 官方 API 合同，不保证跨版本兼容。",
                    },
                    "references": public_refs + references,
                },
            ).to_dict()

        return KernelResult(
            status="ok",
            mode="analyze",
            state=self._state.value,
            message="Native investigation advisory: pb.native_command_investigation",
            data={
                "query_type": "native_investigation_advisory",
                "intent_confidence": "explicit",
                "investigation_recommended": True,
                "evidence_boundary": "experimental_not_public_api_contract",
                "playbook": "pb.native_command_investigation",
                "file": "playbooks/pb_native_command_investigation.md",
                "advisory": {
                    "trigger_reason": "Query indicates native behavior or private interface investigation.",
                    "entry_criteria": [
                        "1. 确认官方 CAA 确无公开方案（已查 CAADoc、头文件、.dico）",
                        "2. 原生 UI 行为明确存在且可稳定复现",
                        "3. 收益明确且了解私有二进制维护风险",
                    ],
                    "investigation_ladder": [
                        "P0 官方 API 检索",
                        "P1 官方用例/文档确认",
                        "P2 已知 Knowledge / Playbook",
                        "P3 原生命令标识与所属 DLL 定位",
                        "P4 二进制/虚表/符号深入排查",
                    ],
                    "core_guardrail": "核心原则：逆向工程证据（如虚表槽位/Slot）是经验性事实证据，不是 Dassault Systèmes 官方 API 合同，不保证跨版本兼容。",
                },
                "references": references,
            },
        ).to_dict()

    # ─── Targeted Module / Brownfield Analysis ─────────────────

    def _parse_maintenance_request(self, request: str, ctx) -> Optional[dict]:
        """Structure natural language request for brownfield maintenance:
        1. Identify whether targeting an existing workspace module (or entity in it)
        2. Detect maintenance / troubleshooting / verification / review intent
        3. Extract the clean problem description
        4. Guard against destructive generator invocation
        """
        try:
            snap = ctx.snapshot
            if not snap or not snap.frameworks:
                return None
        except Exception:
            return None

        import re
        request_lower = request.lower()

        # 1. Intent check: MUST have explicit maintenance/troubleshooting/inspection/verification keywords
        maint_keywords = (
            "maintain", "fix", "troubleshoot", "debug", "issue", "bug", "crash",
            "error", "leak", "problem", "inspect", "analyze", "audit", "review",
            "verify", "lint", "check", "exception", "fault",
            "维护", "排查", "修复", "调试", "解决", "问题", "缺陷", "崩溃",
            "报错", "异常", "泄露", "卡死", "不显示", "闪退", "分析", "检查",
            "校验", "规范", "审查"
        )
        has_maint_intent = any(kw in request_lower for kw in maint_keywords)
        if not has_maint_intent:
            return None

        # Check for explicit greenfield creation markers that indicate the user wants to
        # generate a brand-new component (e.g. "create command FooCmd", "新建命令 FooCmd")
        # unless combined with explicit maintenance verbs like "fix", "maintain", "排查".
        greenfield_pattern = r'\b(?:create|make|generate|add|build|export|新建|创建|生成|新增|添加)\b'
        has_explicit_create = bool(re.search(greenfield_pattern, request, re.IGNORECASE))
        has_fix_override = any(kw in request_lower for kw in ("fix", "maintain", "修复", "维护", "排查", "调试", "verify", "检查", "lint"))
        if has_explicit_create and not has_fix_override:
            return None

        # 2. Module candidate matching
        target_mod = None
        matched_token = ""
        matched_by = ""

        # 1a. Explicit *.m token (e.g. CAABOMToolCmd.m)
        m_matches = re.findall(r'([A-Za-z0-9_]+\.m)\b', request, re.IGNORECASE)
        for m_name in m_matches:
            mod = snap.get_module(m_name)
            if not mod:
                for fw in snap.frameworks:
                    for m in fw.modules:
                        if m.name.lower() == m_name.lower():
                            mod = m
                            break
                    if mod:
                        break
            if mod:
                target_mod = mod
                matched_token = m_name
                matched_by = "dot_m"
                break

        # 1b. Look for preceding keyword: module <name>, maintain <name>, 模块 <name>, 维护 <name>, 修复 <name>, 排查 <name>
        if not target_mod:
            kw_match = re.search(
                r'(?:module|maintain|fix|troubleshoot|verify|inspect|check|模块|维护|修复|排查|检查|分析|调试)\s*[:：\s]?\s*([A-Za-z0-9_]+(?:\.m)?)',
                request,
                re.IGNORECASE
            )
            if kw_match:
                candidate = kw_match.group(1)
                cand_name = candidate if candidate.endswith(".m") else candidate + ".m"
                mod = snap.get_module(cand_name)
                if not mod:
                    for fw in snap.frameworks:
                        for m in fw.modules:
                            if m.name.lower() == cand_name.lower() or m.bare_name.lower() == candidate.lower():
                                mod = m
                                break
                        if mod:
                            break
                if mod:
                    target_mod = mod
                    matched_token = candidate
                    matched_by = "keyword_prefix"

        # 1c. Test alphanumeric tokens in request against all module bare_names/names
        if not target_mod:
            words = re.findall(r'[A-Za-z0-9_]+', request)
            for w in words:
                if len(w) < 3:
                    continue
                for fw in snap.frameworks:
                    for m in fw.modules:
                        if m.bare_name.lower() == w.lower() or m.name.lower() == w.lower():
                            target_mod = m
                            matched_token = w
                            matched_by = "word_module_match"
                            break
                    if target_mod:
                        break
                if target_mod:
                    break

        # 1d. Entity-to-module mapping: check if request mentions a Dialog, Command, Interface, or file in an existing module
        if not target_mod:
            words = re.findall(r'[A-Za-z0-9_]+', request)
            for w in words:
                if len(w) < 4:
                    continue
                w_lower = w.lower()
                for fw in snap.frameworks:
                    for m in fw.modules:
                        # Check commands
                        for c in m.commands:
                            if c.name.lower() == w_lower:
                                target_mod = m
                                matched_token = w
                                matched_by = "entity_command"
                                break
                        if target_mod:
                            break
                        # Check dialogs
                        for d in m.dialogs:
                            if d.name.lower() == w_lower:
                                target_mod = m
                                matched_token = w
                                matched_by = "entity_dialog"
                                break
                        if target_mod:
                            break
                        # Check interfaces
                        for iface in m.interfaces:
                            if iface.name.lower() == w_lower:
                                target_mod = m
                                matched_token = w
                                matched_by = "entity_interface"
                                break
                        if target_mod:
                            break
                        # Check source or header files
                        if m.src_dir_path().exists():
                            for sf in m.src_dir_path().glob("*.*"):
                                if sf.stem.lower() == w_lower:
                                    target_mod = m
                                    matched_token = w
                                    matched_by = "source_file"
                                    break
                        if target_mod:
                            break
                        if m.local_interfaces_dir().exists():
                            for hf in m.local_interfaces_dir().glob("*.*"):
                                if hf.stem.lower() == w_lower:
                                    target_mod = m
                                    matched_token = w
                                    matched_by = "header_file"
                                    break
                        if target_mod:
                            break
                    if target_mod:
                        break
                if target_mod:
                    break

        if not target_mod:
            return None

        # 3. Check verification intent specifically
        verify_keywords = ("verify", "lint", "check", "校验", "规范", "语法", "代码检查")
        is_verify_only = any(kw in request_lower for kw in verify_keywords) and not any(
            kw in request_lower for kw in ("fix", "maintain", "修复", "维护", "重构", "修改", "崩溃", "crash")
        )

        # 4. Extract clean problem description
        problem_desc = request
        if matched_token:
            problem_desc = re.sub(re.escape(matched_token), ' ', problem_desc, flags=re.IGNORECASE)
        problem_desc = re.sub(r'\b(?:module|in|for|the|of|issue|bug|problem|with)\b', ' ', problem_desc, flags=re.IGNORECASE)
        problem_desc = re.sub(r'[，。、：:；;？！?!（）()\[\]{}"\'`]', ' ', problem_desc)
        action_prefixes = (
            "maintain", "fix", "troubleshoot", "debug", "inspect", "analyze", "verify", "lint", "check",
            "维护", "排查", "修复", "调试", "分析", "检查", "校验", "模块"
        )
        for act in action_prefixes:
            problem_desc = re.sub(rf'^\s*{re.escape(act)}\s*', ' ', problem_desc, flags=re.IGNORECASE)
        problem_desc = " ".join(problem_desc.split()).strip()

        return {
            "module": target_mod,
            "target_module": target_mod.name,
            "problem_description": problem_desc,
            "is_verify_only": is_verify_only,
            "action": "verify" if is_verify_only else "maintain",
            "matched_by": matched_by,
            "confidence": "high",
        }

    def _find_target_module(self, request: str, ctx) -> Optional[Any]:
        """Find a Module in workspace matching the request, or None."""
        m_info = self._parse_maintenance_request(request, ctx)
        if m_info:
            return m_info["module"]

        try:
            snap = ctx.snapshot
            if not snap or not snap.frameworks:
                return None
        except Exception:
            return None

        import re
        m_matches = re.findall(r'([A-Za-z0-9_]+\.m)\b', request, re.IGNORECASE)
        for m_name in m_matches:
            mod = snap.get_module(m_name)
            if mod:
                return mod
            for fw in snap.frameworks:
                for m in fw.modules:
                    if m.name.lower() == m_name.lower():
                        return m

        kw_match = re.search(r'\b(?:module|maintain)\s+([A-Za-z0-9_]+(?:\.m)?)\b', request, re.IGNORECASE)
        if kw_match:
            candidate = kw_match.group(1)
            for m_name in (candidate, candidate + ".m" if not candidate.endswith(".m") else candidate):
                mod = snap.get_module(m_name)
                if mod:
                    return mod
                for fw in snap.frameworks:
                    for m in fw.modules:
                        if m.name.lower() == m_name.lower() or m.bare_name.lower() == candidate.lower():
                            return m

        if any(kw in request.lower() for kw in ("analyze", "inspect", "check", "maintain", "debug", "audit", "review")):
            words = re.findall(r'\b[A-Za-z0-9_]+\b', request)
            for w in words:
                if len(w) < 3:
                    continue
                for fw in snap.frameworks:
                    for m in fw.modules:
                        if m.bare_name.lower() == w.lower() or m.name.lower() == w.lower():
                            return m

        return None

    def _locate_relevant_code(self, mod, problem_desc: str, request: str) -> list:
        """
        Locate relevant files, symbols, callbacks and line numbers for the
        problem description. If no problem description is provided, surface
        key entry-point declarations and lifecycle methods.
        """
        locations = []
        try:
            search_files = []
            if mod.src_dir_path().exists():
                search_files.extend(sorted([f for f in mod.src_dir_path().glob("*") if f.is_file() and f.suffix.lower() in (".cpp", ".c", ".cxx")]))
            if mod.local_interfaces_dir().exists():
                search_files.extend(sorted([f for f in mod.local_interfaces_dir().glob("*") if f.is_file() and f.suffix.lower() in (".h", ".hpp")]))
            if mod.public_interfaces_dir().exists():
                search_files.extend(sorted([f for f in mod.public_interfaces_dir().glob("*") if f.is_file() and f.suffix.lower() in (".h", ".hpp")]))

            if not search_files:
                return []

            import re
            combined_text = f"{problem_desc} {request}"
            ascii_words = [w for w in re.findall(r'[A-Za-z0-9_]+', combined_text) if len(w) >= 3 and w.lower() not in ("module", "the", "and", "for", "with", "this", "from")]
            concept_patterns = []
            combined_lower = combined_text.lower()
            if any(k in combined_lower for k in ("dialog", "dlg", "panel", "对话框", "窗口", "面板")):
                concept_patterns.extend(["CATDlgDialog", "CATDlgFrame", "BuildWindow", "Dlg"])
            if any(k in combined_lower for k in ("close", "cancel", "关闭", "退出", "取消")):
                concept_patterns.extend(["GetWindCloseNotification", "Cancel", "Desactivate", "Close", "Destroy"])
            if any(k in combined_lower for k in ("ok", "apply", "确定", "应用")):
                concept_patterns.extend(["GetDiaOKNotification", "GetDiaAPPLYNotification", "OkNotification"])
            if any(k in combined_lower for k in ("crash", "leak", "dump", "崩溃", "闪退", "内存", "泄露", "卡死")):
                concept_patterns.extend(["SetAccessChild", "SetHideStatus", "NULL", "Release", "delete", "Desactivate", "Cancel"])
            if any(k in combined_lower for k in ("table", "list", "column", "表格", "列表", "列宽", "自适应")):
                concept_patterns.extend(["CATDlgList", "CATDlgMultiList", "Column", "Item", "Editor", "Model"])
            if any(k in combined_lower for k in ("button", "btn", "按钮")):
                concept_patterns.extend(["CATDlgPushButton", "GetPushBActivateNotification", "PushButton"])
            if any(k in combined_lower for k in ("export", "excel", "zip", "导出")):
                concept_patterns.extend(["Export", "Excel", "Zip", "Save"])
            if any(k in combined_lower for k in ("command", "cmd", "命令")):
                concept_patterns.extend(["CATStateCommand", "CATCommand", "BuildGraph", "Activate", "Desactivate"])

            all_search_terms = set(ascii_words + concept_patterns)

            def _rel_or_str(p: Path) -> str:
                try:
                    return str(p.relative_to(self.workspace_root))
                except Exception:
                    return str(p)

            scored_hits = []

            for f in search_files:
                f_name = f.name
                f_rel = _rel_or_str(f)
                try:
                    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue

                file_hit_score = 0
                for term in all_search_terms:
                    if term.lower() in f_name.lower():
                        file_hit_score += 5

                current_class = ""
                current_method = ""

                for idx, line in enumerate(lines, start=1):
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.startswith("//") or line_stripped.startswith("/*"):
                        continue

                    m_cls = re.match(r'class\s+([A-Za-z0-9_]+)\s*(?::\s*public\s+([A-Za-z0-9_]+))?', line_stripped)
                    if m_cls:
                        current_class = m_cls.group(1)

                    m_mth = re.match(r'(?:[A-Za-z0-9_:]+\s+)?([A-Za-z0-9_]+::[A-Za-z0-9_]+)\s*\(', line_stripped)
                    if m_mth:
                        current_method = m_mth.group(1)

                    enclosing_symbol = current_method or current_class or f_name

                    matched_terms = []
                    for term in all_search_terms:
                        if term.lower() in line_stripped.lower():
                            matched_terms.append(term)

                    is_callback = "AddCallback" in line_stripped or "GetWindCloseNotification" in line_stripped or "Notification" in line_stripped
                    is_lifecycle = any(k in line_stripped for k in ("BuildWindow", "BuildGraph", "Activate", "Cancel", "Desactivate", "Destructor"))
                    is_class_decl = bool(m_cls)

                    line_score = len(matched_terms) * 10
                    if is_callback:
                        line_score += 8
                    if is_lifecycle:
                        line_score += 6
                    if is_class_decl:
                        line_score += 4
                    line_score += file_hit_score

                    if matched_terms or ((is_callback or is_lifecycle or is_class_decl) and not problem_desc):
                        reasons = []
                        if matched_terms:
                            reasons.append(f"matches {', '.join(matched_terms[:3])}")
                        if is_callback:
                            reasons.append("event callback")
                        if is_lifecycle:
                            reasons.append("lifecycle method")
                        if is_class_decl:
                            reasons.append("class declaration")

                        snippet = line_stripped[:120]
                        scored_hits.append((
                            line_score,
                            {
                                "file": f_rel,
                                "line": idx,
                                "symbol": enclosing_symbol,
                                "snippet": snippet,
                                "reason": "; ".join(reasons) if reasons else "relevant structure",
                            }
                        ))

            scored_hits.sort(key=lambda x: x[0], reverse=True)

            seen = set()
            for _, hit in scored_hits:
                key = (hit["file"], hit["line"])
                if key not in seen:
                    seen.add(key)
                    locations.append(hit)
                    if len(locations) >= 12:
                        break

        except Exception:
            pass

        return locations

    @staticmethod
    def _parse_imakefile(imakefile_path: Path) -> dict:
        """Extract basic build config from Imakefile.mk"""
        if not imakefile_path or not imakefile_path.exists():
            return {}
        try:
            content = imakefile_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {}

        lines = content.splitlines()
        unfolded = []
        buf = ""
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("#"):
                continue
            if line_str.endswith("\\"):
                buf += line_str[:-1] + " "
            else:
                buf += line_str
                if buf:
                    unfolded.append(buf.strip())
                buf = ""
        if buf:
            unfolded.append(buf.strip())

        built_type = None
        link_with = []
        sys_libs = []

        import re
        for entry in unfolded:
            m_type = re.match(r'BUILT_OBJECT_TYPE\s*=\s*(.+)', entry, re.IGNORECASE)
            if m_type:
                built_type = m_type.group(1).strip()
            m_link = re.match(r'LINK_WITH\s*=\s*(.+)', entry, re.IGNORECASE)
            if m_link:
                link_with = [item for item in m_link.group(1).split() if item]
            m_sys = re.match(r'SYS_LIBS\s*=\s*(.+)', entry, re.IGNORECASE)
            if m_sys:
                sys_libs = [item for item in m_sys.group(1).split() if item]

        return {
            "built_object_type": built_type,
            "link_with": link_with,
            "sys_libs": sys_libs,
        }

    def _analyze_target_module(self, mod, ctx, request: str, maintenance_info: Optional[dict] = None) -> dict:
        """Produce deep, read-only analysis of a specific existing module."""
        # 1. Source files and headers
        src_files = []
        if mod.src_dir_path().exists():
            src_files = sorted([f for f in mod.src_dir_path().glob("*") if f.is_file() and f.suffix.lower() in (".cpp", ".c", ".cxx")])

        local_headers = []
        if mod.local_interfaces_dir().exists():
            local_headers = sorted([f for f in mod.local_interfaces_dir().glob("*") if f.is_file() and f.suffix.lower() in (".h", ".hpp")])

        pub_headers = []
        if mod.public_interfaces_dir().exists():
            pub_headers = sorted([f for f in mod.public_interfaces_dir().glob("*") if f.is_file() and f.suffix.lower() in (".h", ".hpp")])

        imakefile_p = mod.imakefile_path()

        def _rel_or_str(p: Path) -> str:
            try:
                return str(p.relative_to(self.workspace_root))
            except Exception:
                return str(p)

        files_info = {
            "src": [_rel_or_str(f) for f in src_files],
            "local_interfaces": [_rel_or_str(f) for f in local_headers],
            "public_interfaces": [_rel_or_str(f) for f in pub_headers],
            "imakefile": _rel_or_str(imakefile_p) if imakefile_p.exists() else None,
        }

        # 2. Build configuration from Imakefile.mk
        build_config = self._parse_imakefile(imakefile_p)

        # 3. Entities
        entities_info = {
            "commands": [c.name for c in mod.commands],
            "dialogs": [d.name for d in mod.dialogs],
            "interfaces": [i.name for i in mod.interfaces],
            "components": [c.name for c in mod.components],
        }

        # 4. Filter diagnostics
        module_diags = []
        workspace_diags = []
        try:
            from diagnostics import diagnose_workspace
            diag_summary = diagnose_workspace(ctx)
            all_diags = diag_summary.get("diagnostics", [])

            mod_names = {mod.name.lower(), mod.bare_name.lower()}
            for c in mod.commands:
                mod_names.add(c.name.lower())
            for d in mod.dialogs:
                mod_names.add(d.name.lower())
            for i in mod.interfaces:
                mod_names.add(i.name.lower())
            for c in mod.components:
                mod_names.add(c.name.lower())

            for d in all_diags:
                ent = (d.get("entity") or "").lower()
                fix_file = ""
                if d.get("fix_plan"):
                    fix_file = str(d["fix_plan"].get("file") or "").lower()

                if (ent and ent in mod_names) or (mod.name.lower() in fix_file):
                    module_diags.append(d)
                else:
                    workspace_diags.append(d)
        except Exception:
            pass

        # 5. Problem description, maintenance context, and critical code locations
        problem_desc = maintenance_info.get("problem_description", "") if maintenance_info else ""
        
        maint_ctx = None
        active_build_errors = []
        try:
            from maintenance_context import load_context, save_context, MaintenanceContext, generate_task_id
            maint_ctx = load_context(ctx.workspace_root, mod.name)
            if not maint_ctx:
                task_id = generate_task_id(str(ctx.workspace_root), mod.name, request)
                maint_ctx = MaintenanceContext(
                    task_id=task_id,
                    workspace=str(ctx.workspace_root),
                    target_module=mod.name,
                    original_request=request,
                    problem_description=problem_desc,
                )
            active_build_errors = maint_ctx.unresolved_build_errors
        except Exception:
            maint_ctx = None
            active_build_errors = []

        relevant_locations = self._locate_relevant_code(mod, problem_desc, request)

        # Prepend L0 direct build errors if present
        if active_build_errors:
            l0_locations = []
            for b_err in active_build_errors:
                l0_locations.append({
                    "file": b_err.get("file") or f"{mod.name} (linker)",
                    "line": b_err.get("line") or 0,
                    "symbol": f"[{b_err.get('code') or 'BUILD_ERR'}]",
                    "context": b_err.get("message") or b_err.get("raw", ""),
                    "reason": f"L0 Direct Build Evidence ({b_err.get('kind', 'compiler_error')})",
                    "level": "L0",
                })
            relevant_locations = l0_locations + relevant_locations

        # 6. Problem-Aware Knowledge & Failure Patterns
        knowledge_refs = {}
        failure_patterns = []
        try:
            q_terms = [mod.bare_name]
            if problem_desc:
                q_terms.append(problem_desc)
            if mod.dialogs or any("dlg" in f.lower() for f in files_info.get("src", [])):
                q_terms.append("dialog")
            elif mod.commands:
                q_terms.append("command")

            lookup_query = " ".join(q_terms)
            knowledge_refs = self._lookup_knowledge(lookup_query)

            refs = knowledge_refs.get("references", [])
            for r in refs:
                if "failure_patterns" in r or "fp_" in r:
                    failure_patterns.append(r)

            if problem_desc and not failure_patterns and self.catalog:
                fp_query = f"failure pattern {problem_desc}"
                fp_entries = self.catalog.search(fp_query, max_results=5)
                for e in fp_entries:
                    if getattr(e, "category", "") == "failure_pattern" or "failure_patterns" in getattr(e, "file", ""):
                        if e.raw_line not in failure_patterns:
                            failure_patterns.append(e.raw_line)
        except Exception:
            pass

        # 7. Targeted Single-Module Verification (Static Code + UI Lint)
        verification_data = {}
        total_code_errors = 0
        total_code_warnings = 0
        total_ui_findings = 0
        files_verified = 0
        try:
            from verifier import CodeVerifier
            from ui_lint import UILinter

            skill_root = Path(__file__).parent.parent
            verifier = CodeVerifier(skill_root=skill_root)
            code_res = verifier.verify_module(mod.path)

            linter = UILinter()
            ui_findings = linter.lint_module(Path(mod.path))

            code_dict = code_res.to_dict()
            ui_dict = [f.to_dict() for f in ui_findings]

            total_code_errors = code_res.error_count
            total_code_warnings = code_res.warning_count
            total_ui_findings = len(ui_findings)
            files_verified = code_res.files_checked

            ui_errors = sum(1 for f in ui_findings if f.severity == "error")
            ui_warnings = sum(1 for f in ui_findings if f.severity == "warning")

            verification_data = {
                "status": "clean" if (total_code_errors + ui_errors == 0 and total_code_warnings + ui_warnings == 0) else "has_issues",
                "summary": {
                    "files_checked": files_verified,
                    "code_errors": total_code_errors,
                    "code_warnings": total_code_warnings,
                    "ui_findings": total_ui_findings,
                    "ui_errors": ui_errors,
                    "ui_warnings": ui_warnings,
                    "total_issues": total_code_errors + total_code_warnings + total_ui_findings,
                },
                "code_issues": code_dict.get("issues", []),
                "ui_findings": ui_dict,
            }
        except Exception as e:
            verification_data = {"status": "error", "message": str(e)}

        self._state = KernelState.COMPLETED

        # Persist updated context snapshot
        if maint_ctx:
            try:
                maint_ctx.candidate_locations = relevant_locations[:15]
                maint_ctx.verification_findings = verification_data.get("code_issues", [])
                save_context(maint_ctx)
            except Exception:
                pass

        if maintenance_info and maintenance_info.get("is_verify_only"):
            msg = f"Targeted verification for module {mod.name}: {files_verified} files checked, {total_code_errors} error(s), {total_code_warnings} warning(s), {total_ui_findings} UI finding(s)."
        elif problem_desc:
            msg = f"Targeted maintenance analysis for module {mod.name} on '{problem_desc}': {len(src_files)} sources, {len(relevant_locations)} key location(s), {len(failure_patterns)} failure pattern(s)."
        else:
            msg = f"Targeted analysis for module {mod.name}: {len(src_files)} sources, {len(module_diags)} diagnostics, {total_code_errors + total_ui_findings} verification issue(s)."

        return KernelResult(
            status="ok",
            mode="analyze",
            state=self._state.value,
            message=msg,
            data={
                "target_module": mod.name,
                "framework": mod.framework.name if mod.framework else None,
                "path": str(mod.path),
                "problem_description": problem_desc,
                "files": files_info,
                "build_config": build_config,
                "entities": entities_info,
                "relevant_locations": relevant_locations,
                "active_build_errors": active_build_errors,
                "task_id": maint_ctx.task_id if maint_ctx else "",
                "verification": verification_data,
                "diagnostics": {
                    "module_specific": module_diags,
                    "workspace_scope": workspace_diags,
                },
                "knowledge": knowledge_refs,
                "failure_patterns": failure_patterns,
            }
        ).to_dict()

    def _execute_develop_plan(self, plan: dict, preview: bool = False) -> dict:
        """Execute a development plan via existing actions"""
        intent_data = plan.get("intent", {})
        intent_type = intent_data.get("type", "")
        name = intent_data.get("name", "")
        module = intent_data.get("module", "MyModule.m")
        framework = intent_data.get("framework", "MyFramework")

        try:
            from actions import (
                ActionContext,
                create_dialog,
                create_framework,
                create_interface,
                create_module,
                create_workbench,
                create_component,
            )
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
            elif intent_type == "CreateFramework":
                result = create_framework(ctx, name=name)
            elif intent_type == "CreateModule":
                result = create_module(ctx, framework_name=framework, module_name=name)
            elif intent_type == "CreateWorkbench":
                result = create_workbench(ctx, name=name, framework=framework)
            elif intent_type == "CreateInterface":
                result = create_interface(ctx, name=name, module=module, framework=framework)
            elif intent_type == "CreateDialog":
                result = create_dialog(ctx, name=name, module=module, framework=framework)
            elif intent_type == "CreateComponent":
                result = create_component(ctx, name=name, module=module, framework=framework)
            else:
                return {"status": "error", "message": f"Unsupported or unavailable intent: {intent_type}"}

            # If action returned error or blocked, preserve status directly (do not mask as pending)
            if isinstance(result, dict) and result.get("status") in ("error", "blocked"):
                return result
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
                    # Surface rollback_id so the user/agent can undo this batch.
                    # Without this, the backup exists but nobody knows its ID.
                    rb = apply_result.get("rollback_id")
                    if rb:
                        result["rollback_id"] = rb
                        result["message"] += f" [rollback_id: {rb}]"
                else:
                    result["status"] = "error"
                    result["message"] = (
                        "Generated but failed to apply: "
                        + "; ".join(apply_result.get("errors", []) or [apply_result.get("status", "unknown")])
                    )

            return result
        except ImportError as e:
            return {"status": "error", "message": f"Required module not available: {e}"}

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
        # Bare dialog/对话框 is CreateDialog. Command+dialog is already
        # handled above ("with dialog" / "带对话框"). Do not map the
        # dialog keyword itself to CreateCommandWithDialog — that made
        # `cade create dialog` generate a command instead of a dialog.
        mapping = [
            # Chinese keywords (most specific in CN context)
            ("对话框", "CreateDialog"),
            ("命令", "CreateCommand"),
            ("特征", "CreateFeature"),
            ("扩展", "CreateExtension"),
            ("接口", "CreateInterface"),
            ("工作台", "CreateWorkbench"),
            ("组件", "CreateComponent"),
            ("模块", "CreateModule"),
            ("框架", "CreateFramework"),
            # English keywords (check with word boundaries to avoid substring matches)
        ]
        en_mapping = [
            ("dialog", "CreateDialog"),
            ("command", "CreateCommand"),
            ("feature", "CreateFeature"),
            ("extension", "CreateExtension"),
            ("interface", "CreateInterface"),
            ("workbench", "CreateWorkbench"),
            ("component", "CreateComponent"),
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
        "s_ok", "failure", "crash", "bug", "失败", "报错", "未改变", "不生效", "不显示",
    )
    _KNOWLEDGE_QUESTION_WORDS = (
        "how do", "how to", "how does", "what is", "what are", "what does",
        "where is", "which ", "when ", "why ", "why does", "why is",
        "为什么", "为何", "怎么", "如何", "何为", "怎样",
    )

    def _is_knowledge_query(self, request: str) -> bool:
        """Detect if this is a knowledge/API question, not a workspace operation"""
        import re
        if self._has_native_investigation_signal(request):
            return True
        # Check built-in keywords (short ones use word-boundary)
        for kw in self._KNOWLEDGE_KW:
            if len(kw) <= 2:
                if re.search(r'\b' + re.escape(kw) + r'\b', request):
                    return True
            elif kw in request:
                return True
        # Check alias keys via CatalogIndex (Chinese synonyms not in _KNOWLEDGE_KW)
        try:
            if self.catalog and self.catalog.has_alias_match(request):
                return True
        except Exception:
            pass
        # Check question patterns
        return any(request.startswith(q) for q in self._KNOWLEDGE_QUESTION_WORDS)

    def _lookup_knowledge(self, request: str, include_content: bool = False) -> dict:
        """
        Search knowledge base via CatalogIndex (unified model).
        Alias expansion and keyword matching handled internally.

        include_content: also inline the full text of the top-ranked knowledge
        files (with a size budget) so the caller gets answers in ONE round
        trip instead of search -> read -> maybe-grep -> read-again.
        """
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
        entries = []
        try:
            if self.catalog:
                entries = self.catalog.search(request, max_results=10)
                results = [e.raw_line for e in entries]
        except Exception:
            pass

        # Step 3: Build response
        summary_parts = []
        if domain_hint and domain_hint != "general":
            summary_parts.append(f"Domain: {domain_hint}")
        if results:
            summary_parts.append(f"Found {len(results)} references")

        guide = ""
        try:
            if self.catalog:
                guide = self.catalog.reading_guide(entries, request)
        except Exception:
            pass

        out = {
            "summary": "; ".join(summary_parts) if summary_parts else "Knowledge base searched",
            "domain": domain_hint,
            "references": results,
            "reading_guide": guide,
            "hint": "Read files in reading_guide order. For official docs, see CAADoc via knowledge/frameworks/.",
        }
        if include_content and entries:
            out["content"] = self._read_knowledge_files(entries)
        return out

    def _read_knowledge_files(self, entries, max_files: int = 3,
                              max_chars_per_file: int = 12000,
                              max_total_chars: int = 24000) -> list:
        """Inline the top-ranked knowledge files, bounded by a size budget.

        Returns [{file, id, title, content, truncated}] in ranked order.
        Reading is best-effort: a missing/unreadable file is skipped, never
        fatal. Budgets keep the MCP/CLI payload from blowing up on large docs.
        """
        skill_root = Path(__file__).parent.parent
        content = []
        total = 0
        for e in entries[:max_files]:
            if not e.file or e.file.endswith("/"):
                continue
            path = skill_root / e.file
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            truncated = False
            if len(text) > max_chars_per_file:
                text = text[:max_chars_per_file]
                truncated = True
            if total + len(text) > max_total_chars:
                break
            total += len(text)
            content.append({
                "file": e.file,
                "id": e.id,
                "title": e.title,
                "content": text,
                "truncated": truncated,
            })
        return content

    def _consult_knowledge(self, request: str) -> tuple[list, list]:
        """Lightweight knowledge grounding for the develop pipeline.

        Returns (refs, matched_entries) so callers can inspect refs and
        reuse matched_entries without re-querying the Catalog.
        Kept deliberately small (max 3 refs) — this is traceability, not
        a full knowledge dump. Failures are silent (never block develop).
        """
        try:
            if not self.catalog:
                return [], []
            entries = self.catalog.search(request, max_results=3)
            if not entries:
                return [], []
            # Enrich with verified APIs from the registry where possible
            try:
                from api_registry import get_registry
                registry = get_registry(Path(__file__).parent.parent)
            except Exception:
                registry = None
            refs = []
            for e in entries:
                ref = {"id": e.id, "file": e.file, "title": e.title}
                if registry and e.file:
                    # APIs whose source file matches this entry
                    src_name = Path(e.file).name
                    apis = sorted(a for a, s in registry.api_source.items()
                                  if s.endswith(f":{src_name}"))[:8]
                    if apis:
                        ref["apis"] = apis
                refs.append(ref)
            return refs, entries
        except Exception:
            return [], []

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
                r = (full_build(ws, entrypoint="kernel", orchestrated_by_kernel=True) if "full" in request else
                     clean_build(ws, entrypoint="kernel", orchestrated_by_kernel=True) if "clean" in request else
                     build_with_threads(ws, n, entrypoint="kernel", orchestrated_by_kernel=True) if "thread" in request else
                     incremental_build(ws, entrypoint="kernel", orchestrated_by_kernel=True))
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
                r = start_catia_runtime(workspace_path=str(self.workspace_root), entrypoint="kernel", orchestrated_by_kernel=True)
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message="CATIA started.", data=r if isinstance(r, dict) else {}).to_dict()
            # Dev: build + run in one step. Word-boundary match: a bare
            # substring test ("dev" in request) hijacked any request merely
            # containing "dev" ("develop a dialog", "DeviceCmd") into a
            # mkmk build + CATIA launch before intent detection could run.
            import re
            if re.search(r"\bdev\b", request) or ("build" in request and "run" in request):
                r_build = incremental_build(ws, entrypoint="kernel", orchestrated_by_kernel=True)
                r_run = start_catia_runtime(workspace_path=str(self.workspace_root), entrypoint="kernel", orchestrated_by_kernel=True) if r_build.get("status") == "success" else None
                self._state = KernelState.COMPLETED
                return KernelResult(status="ok", mode="develop", state=self._state.value,
                    message=f"Build: {r_build.get('message','')}; Run: {r_run.get('message','')}" if r_run else r_build.get('message',''),
                    data={"build": r_build, "run": r_run}).to_dict()
            if "stop catia" in request or "kill catia" in request:
                r = stop_catia(entrypoint="kernel", orchestrated_by_kernel=True)
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
