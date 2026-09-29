#!/usr/bin/env python3
"""CADE MCP Server — 3 modes exposing full CADE capability to AI clients.

v3.0: All internal tools collapsed into 3 Kernel modes:
  develop — create/generate (Command, may modify files)
  analyze — query/diagnose (Query, read-only)
  repair  — fix/refactor (Command, may modify with recovery)

The Kernel handles internal dispatch — AI never needs to know
about individual tools.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).parent
sys.path.insert(0, str(SKILL_ROOT))

from kernel import Kernel, KernelMode
from token_optimizer import optimize


def _force_utf8_stdio() -> None:
    """Pin the stdio JSON-RPC channel to UTF-8 in both directions.

    MCP over stdio is UTF-8, but Windows Python defaults stdin/stdout to the
    console code page (cp936/GBK). That produced two failures for CJK input:
    a request was rejected outright (``'gbk' codec can't decode byte ...``),
    or — worse — silently decoded as mojibake (``分析当前工作区`` became
    ``鍒嗘瀽褰撳墠宸ヤ綔鍖`` plus a lone surrogate) while ``json.loads`` still
    succeeded, so the Kernel ran on a corrupted request. Output was affected
    too: the ``ensure_ascii=False`` response raised ``'gbk' codec can't
    encode character`` for any glyph outside cp936 (e.g. an emoji in a
    diagnostic), which killed the reply.

    stdin is strict so a protocol violation fails loudly instead of being
    acted on as garbage. stdout/stderr use ``replace`` because a response
    must still be emitted whatever the payload contains. Idempotent, and a
    no-op where ``reconfigure`` is unavailable (very old Python or streams
    a host has already wrapped).
    """
    for stream, errors in ((sys.stdin, "strict"),
                           (sys.stdout, "replace"),
                           (sys.stderr, "replace")):
        try:
            stream.reconfigure(encoding="utf-8", errors=errors)
        except (AttributeError, ValueError, OSError):
            pass


def _get_default_workspace():
    """Read workspace: env CADE_WORKSPACE > config > cwd"""
    import os

    if os.environ.get("CADE_WORKSPACE"):
        return os.environ["CADE_WORKSPACE"]
    from env import CAAEnvironment

    env = CAAEnvironment()
    if env.load_config():
        return env.config.get("WORKSPACE", os.getcwd())
    return os.getcwd()


WORKSPACE = _get_default_workspace()

TOOLS = [
    {
        "name": "develop",
        "description": (
            "Create, generate, build, or deploy CATIA CAA V5/B28 components from natural language (EN/CN). "
            "Use for: creating CAA commands, dialogs (CATDlgDialog/CATDlgNotify), workbenches, "
            "features, interfaces, extensions, modules, and frameworks. "
            "Also handles: full/incremental workspace builds, CATIA (CNEXT) runtime startup, and prerequisite setup. "
            "Kernel automatically generates compliant CAA C++ source/headers, Imakefile.mk, and IdentityCard, "
            "with automatic rollback snapshots before applying changes. "
            "To apply one already-generated ChangeSet, pass that object as changeset and omit request. "
            "To execute an authorized build, run, macro, or batch, pass execute_plan and omit request. "
            "request, changeset, and execute_plan are mutually exclusive. "
            'Examples: "create command ExportBOM in CAABOMToolCmd.m", '
            '"在 CAABOMToolCmd.m 中创建对话框面板", "build workspace", "start CATIA".'
        ),
        "inputSchema": {
            "type": "object",
            # request XOR changeset is enforced in handle_tool. JSON Schema
            # draft used here cannot express that mutual exclusion.
            "required": [],
            "properties": {
                "request": {
                    "type": "string",
                    "description": (
                        "What you want to create, in natural language. "
                        "Mutually exclusive with changeset."
                    ),
                },
                "workspace": {"type": "string", "description": "Optional workspace path override"},
                "preview": {
                    "type": "boolean",
                    "description": (
                        "If true, generate the ChangeSet but do NOT apply it to disk. "
                        "The returned changeset is the authorization object for this "
                        "generation. To apply that exact object, call develop again with "
                        "changeset set to it and without request. Do not re-run the "
                        "natural-language request and treat that as confirmation. "
                        "Ignored when changeset is set."
                    ),
                    "default": False,
                },
                "changeset": {
                    "type": "object",
                    "description": (
                        "A serialized ChangeSet previously returned by develop(preview=true). "
                        "Applies that object only. Does not re-enter Kernel.execute, and does "
                        "not run extras, IdentityCard, or build. Mutually exclusive with request."
                    ),
                },
                "execute_plan": {
                    "type": "object",
                    "description": (
                        "A serialized ExecutionPlan previously returned by develop(preview=true). "
                        "Authorizes and executes an external process (build, start_catia, stop_catia, macro, batch). "
                        "Does not re-enter Kernel.execute. Mutually exclusive with request and changeset."
                    ),
                },
            },
        },
    },
    {
        "name": "analyze",
        "description": (
            "Query, diagnose, or inspect CATIA CAA V5/B28 workspaces and API knowledge. READ-ONLY — never modifies files. "
            "Use for: (1) Official CAA API/interfaces/patterns retrieval (CATIProduct, CATCommand, undo/redo, topological operators). "
            "(2) Active build error (L0 compiler/linker evidence) and brownfield maintenance analysis. "
            "(3) Workspace structure, module dependency, and IdentityCard diagnostics. "
            "Set detail=true for CAA knowledge queries to inline authoritative documentation and code examples. "
            'Examples: "what is CATIProduct and how to traverse assembly (detail=true)", '
            '"排查 CAABOMToolCmd.m 中列宽刷新与构建错误", "list all modules and dependencies", "diagnose workspace".'
        ),
        "inputSchema": {
            "type": "object",
            "required": ["request"],
            "properties": {
                "request": {
                    "type": "string",
                    "description": "What you want to analyze or query, in natural language.",
                },
                "workspace": {"type": "string", "description": "Optional workspace path override"},
                "detail": {
                    "type": "boolean",
                    "description": (
                        "Knowledge queries only: inline the top-ranked knowledge file content "
                        "in the response. Default false returns references + reading_guide only."
                    ),
                    "default": False,
                },
            },
        },
    },
    {
        "name": "repair",
        "description": (
            "Fix, refactor, or rollback CATIA CAA V5/B28 workspace issues with safety snapshots. May modify files. "
            "Use for: fixing mkmk compiler/linker errors, resolving missing dictionary (.dico) entries, "
            "safe renaming or moving of CAA commands/interfaces/modules, and rolling back prior modifications. "
            "The Kernel runs diagnose -> fix -> verify loop with byte-level rollback protection. "
            'Examples: "fix dictionary entries for BOMTool", "rename command OldCmd to NewCmd in CAABOMToolCmd.m", '
            '"修复编译错误 C2065", "rollback to latest".'
        ),
        "inputSchema": {
            "type": "object",
            "required": ["request"],
            "properties": {
                "request": {
                    "type": "string",
                    "description": "What you want to fix, in natural language.",
                },
                "workspace": {"type": "string", "description": "Optional workspace path override"},
            },
        },
    },
]


def _reject(operation: str, message: str) -> dict:
    return {"status": "error", "operation": operation, "message": message}


def _apply_authorized_changeset(ws: str, changeset) -> dict:
    """Apply one serialized ChangeSet. Never re-enters Kernel.execute.

    P1 only. Does not check workspace baseline (P2), fold extras into the
    ChangeSet (P3a), authorize IdentityCard (P3b), or authorize a build (P4).
    """
    if not isinstance(changeset, dict):
        return _reject("apply", "changeset must be the serialized ChangeSet object")
    kernel = Kernel(workspace_root=ws)
    applied = kernel._apply_changeset_dict(changeset)
    if applied.get("status") == "applied":
        result = {
            "status": "ok",
            "operation": "apply",
            "apply_status": "applied",
            "message": "Applied the supplied ChangeSet",
        }
        if applied.get("rollback_id"):
            result["rollback_id"] = applied["rollback_id"]
        # optimize() keeps status/message/rollback_id but drops unknown keys.
        # Stamp the apply contract after it so this is not reported as develop.
        optimized = optimize(result)
        optimized["operation"] = "apply"
        optimized["apply_status"] = "applied"
        return optimized
    errors = applied.get("errors") or [applied.get("message") or applied.get("status") or "apply failed"]
    return {
        "status": "error",
        "operation": "apply",
        "apply_status": applied.get("status", "error"),
        "message": "; ".join(str(e) for e in errors),
        "errors": errors,
    }


# Actions whose Kernel result carries a P5.3 runtime verification envelope
# (execution/verification) at top level. Deliberately NOT "runtime_view": the
# Kernel runtime_view action is a build action (create_runtime_view) that emits
# no P5.3 envelope. "execution"/"verification" are also used as top-level keys
# by build.py with a DIFFERENT status domain, so forwarding is gated by action
# AND by envelope shape to avoid pulling a build envelope into the execute
# result (see _forward_p53_envelopes).
_P53_ENVELOPE_ACTIONS = ("start_catia", "stop_catia")
_P53_EXECUTION_STATUSES = ("completed", "error", "timeout")
_P53_VERIFICATION_STATUSES = ("not_run", "observed", "passed", "failed")


def _forward_p53_envelopes(executed: dict, action: str) -> dict:
    """Return the P5.3 envelopes to forward, or {} if none qualify.

    Restricted to P5.3 envelope-enabled actions, and additionally validated by
    status domain so a same-named build.py envelope (execution.status in
    success/failed/error) is never forwarded as a P5.3 envelope.
    """
    if not isinstance(executed, dict) or action not in _P53_ENVELOPE_ACTIONS:
        return {}
    exec_env = executed.get("execution")
    ver_env = executed.get("verification")
    if not isinstance(exec_env, dict) or not isinstance(ver_env, dict):
        return {}
    if exec_env.get("status") not in _P53_EXECUTION_STATUSES:
        return {}
    if ver_env.get("status") not in _P53_VERIFICATION_STATUSES:
        return {}
    return {"execution": exec_env, "verification": ver_env}


def _execute_authorized_plan(ws: str, execute_plan: Any) -> dict:
    """Execute one serialized ExecutionPlan. Never re-enters Kernel.execute."""
    if not isinstance(execute_plan, dict):
        return _reject("execute", "execute_plan must be the serialized ExecutionPlan object")
    kernel = Kernel(workspace_root=ws)
    executed = kernel._execute_plan_dict(execute_plan)
    action = execute_plan.get("action", "")
    forwarded = _forward_p53_envelopes(executed, action)
    if executed.get("status") in ("ok", "success"):
        result = {
            "status": "ok",
            "operation": "execute",
            "execution_status": executed.get("status", "ok"),
            "action": action,
            "message": executed.get("message", "Execution complete"),
            "data": executed.get("data", {}),
        }
        optimized = optimize(result)
        optimized["operation"] = "execute"
        optimized["execution_status"] = executed.get("status", "ok")
        optimized["action"] = action
        # optimize() strips top-level keys not in _PASSTHROUGH_KEYS, so the P5.3
        # envelopes are re-attached here rather than added to that global set
        # (which would also leak build.py's differently-shaped envelopes).
        optimized.update(forwarded)
        return optimized
    errors = executed.get("errors") or [executed.get("message") or executed.get("status") or "execution failed"]
    res_err = {
        "status": "error",
        "operation": "execute",
        "execution_status": executed.get("status", "error"),
        "action": action,
        "message": "; ".join(str(e) for e in errors),
        "errors": errors,
    }
    res_err.update(forwarded)
    return res_err


def handle_tool(name: str, args: dict) -> dict:
    ws = args.get("workspace", WORKSPACE)
    request_val = args.get("request")
    has_request = isinstance(request_val, str) and bool(request_val.strip())
    has_changeset = "changeset" in args and args.get("changeset") is not None
    has_execute_plan = "execute_plan" in args and args.get("execute_plan") is not None

    mode_map = {
        "develop": KernelMode.DEVELOP,
        "analyze": KernelMode.ANALYZE,
        "repair": KernelMode.REPAIR,
    }

    if name not in mode_map:
        return {"status": "error", "message": f"Unknown tool: {name}. Available: develop, analyze, repair"}

    if has_changeset and name != "develop":
        return _reject("apply", "changeset is only accepted by develop")
    if has_execute_plan and name != "develop":
        return _reject("execute", "execute_plan is only accepted by develop")

    if name == "develop":
        count = sum(1 for x in (has_request, has_changeset, has_execute_plan) if x)
        if count == 0:
            return _reject("develop", "develop requires exactly one of request, changeset, or execute_plan")
        if count > 1:
            op = "execute" if has_execute_plan else "apply"
            return _reject(op, "request, changeset, and execute_plan are mutually exclusive")
        if has_changeset:
            return _apply_authorized_changeset(ws, args.get("changeset"))
        if has_execute_plan:
            return _execute_authorized_plan(ws, args.get("execute_plan"))

    request = args.get("request", "")
    kernel = Kernel(workspace_root=ws)
    preview = bool(args.get("preview", False)) if name == "develop" else False
    detail = bool(args.get("detail", False)) if name == "analyze" else False
    result = kernel.execute(mode_map[name], request, preview=preview, detail=detail)

    if isinstance(result, dict) and result.get("status") == "pending_execution":
        optimized = optimize(result)
        optimized["status"] = "pending_execution"
        if "execute_plan" in result:
            optimized["execute_plan"] = result["execute_plan"]
        return optimized

    # A knowledge query with detail=true inlines file content that must reach
    # the caller verbatim. Knowledge results are FLATTENED (content at top
    # level, not under data), and 'auto' strips everything but ok/status on
    # success — bypass optimization to preserve the payload.
    if name == "analyze" and isinstance(result, dict) and result.get("content"):
        return result
    return optimize(result)


def main():
    """MCP stdio server entry point"""
    _force_utf8_stdio()
    while True:
        msg_id = None
        try:
            line = sys.stdin.readline()
            if not line:
                break

            msg = json.loads(line)
            msg_id = msg.get("id")
            method = msg.get("method", "")

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "cade", "version": "3.2.1"}
                    },
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": TOOLS},
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            elif method == "tools/call":
                tool_name = msg["params"]["name"]
                tool_args = msg["params"].get("arguments", {})
                result = handle_tool(tool_name, tool_args)
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
                }
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()

            elif method == "notifications/initialized":
                pass  # ack silently

        except json.JSONDecodeError:
            continue
        except UnicodeDecodeError as e:
            # stdin is strict UTF-8 (see _force_utf8_stdio). Reaching here means
            # the host sent bytes that are not valid UTF-8 — previously this
            # either crashed the read or, under GBK, decoded into mojibake that
            # json.loads happily accepted. Report it instead of guessing.
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32700,
                    "message": f"Request is not valid UTF-8: {e}",
                },
            }
            try:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception:
                pass
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": str(e)},
            }
            try:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception:
                pass


if __name__ == "__main__":
    main()
