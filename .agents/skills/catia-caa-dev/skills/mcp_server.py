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

SKILL_ROOT = Path(__file__).parent
sys.path.insert(0, str(SKILL_ROOT))

from kernel import Kernel, KernelMode
from token_optimizer import optimize


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
            "Create, generate, build, or deploy CAA components from natural language (EN/CN). "
            "Use for: creating commands, features, dialogs (auto-generated with command), "
            "workbenches, interfaces, extensions, modules, frameworks. "
            "Also handles: builds, CATIA startup, documentation, workspace prerequisites. "
            "The Kernel handles requirement clarification, intent detection (CN+EN), "
            "planning, code generation, static verification, and IdentityCard setup. "
            'Examples: "create command ExportBOM in MyModule.m", '
            '"创建一个设置命令SettingsCmd，放在TestModule模块中", '
            '"build the workspace", "start CATIA".'
        ),
        "inputSchema": {
            "type": "object",
            "required": ["request"],
            "properties": {
                "request": {
                    "type": "string",
                    "description": "What you want to create, in natural language.",
                },
                "workspace": {"type": "string", "description": "Optional workspace path override"},
            },
        },
    },
    {
        "name": "analyze",
        "description": (
            "Query, diagnose, or inspect the workspace. READ-ONLY — never modifies files. "
            "Use for: workspace analysis, listing modules/commands, dependency analysis, "
            "diagnostics, validation, impact analysis. Supports EN and CN requests. "
            'Examples: "analyze the workspace", "list all modules", '
            '"列出所有模块", "show dependencies of MyCmd", '
            '"diagnose module TestModule.m".'
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
            },
        },
    },
    {
        "name": "repair",
        "description": (
            "Fix, refactor, or rollback workspace issues. May modify files (with safety net). "
            "Use for: fixing diagnostics, renaming commands/interfaces/modules, "
            "moving commands between modules, rollback operations, creating snapshots. "
            "The Kernel runs diagnose -> fix -> verify loop (max 3 attempts). "
            'Examples: "fix dictionary entries", "rename command OldName to NewName in MyModule", '
            '"修复工作区问题", "rollback to latest".'
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


def handle_tool(name: str, args: dict) -> dict:
    ws = args.get("workspace", WORKSPACE)
    request = args.get("request", "")

    mode_map = {
        "develop": KernelMode.DEVELOP,
        "analyze": KernelMode.ANALYZE,
        "repair": KernelMode.REPAIR,
    }

    if name not in mode_map:
        return {"status": "error", "message": f"Unknown tool: {name}. Available: develop, analyze, repair"}

    kernel = Kernel(workspace_root=ws)
    result = kernel.execute(mode_map[name], request)
    return optimize(result)


def main():
    """MCP stdio server entry point"""
    while True:
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
                        "serverInfo": {"name": "cade", "version": "3.2.0"}
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
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": msg.get("id") if 'msg' in dir() else None,
                "error": {"code": -32603, "message": str(e)},
            }
            try:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception:
                pass


if __name__ == "__main__":
    main()
