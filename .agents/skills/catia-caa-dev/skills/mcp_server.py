#!/usr/bin/env python3
"""CADE MCP Server — 31 tools exposing full CADE capability to AI clients."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent
sys.path.insert(0, str(SKILL_ROOT))

from actions import ActionContext


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
        "name": "analyze_workspace",
        "description": "Full workspace analysis",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "list_modules",
        "description": "List all modules",
        "inputSchema": {
            "type": "object",
            "properties": {"framework": {"type": "string"}},
        },
    },
    {
        "name": "list_commands",
        "description": "List all commands",
        "inputSchema": {"type": "object", "properties": {"module": {"type": "string"}}},
    },
    {
        "name": "get_dependencies",
        "description": "Entity dependency info",
        "inputSchema": {
            "type": "object",
            "required": ["entity"],
            "properties": {"entity": {"type": "string"}, "type": {"type": "string"}},
        },
    },
    {
        "name": "visualize_dependencies",
        "description": "Mermaid dependency diagram",
        "inputSchema": {"type": "object", "properties": {"entity": {"type": "string"}}},
    },
    {
        "name": "validate_workspace",
        "description": "Validate workspace integrity",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "create_executable_command",
        "description": "Create complete CAA command",
        "inputSchema": {
            "type": "object",
            "required": ["name", "module"],
            "properties": {
                "name": {"type": "string"},
                "module": {"type": "string"},
                "framework": {"type": "string"},
                "with_dialog": {"type": "boolean"},
                "dialog_name": {"type": "string"},
                "add_to_workbench": {"type": "string"},
                "stateful": {"type": "boolean"},
            },
        },
    },
    {
        "name": "create_feature",
        "description": "Create Feature object with factory",
        "inputSchema": {
            "type": "object",
            "required": ["name", "module"],
            "properties": {
                "name": {"type": "string"},
                "module": {"type": "string"},
                "framework": {"type": "string"},
            },
        },
    },
    {
        "name": "create_extension",
        "description": "Create data extension",
        "inputSchema": {
            "type": "object",
            "required": ["name", "target_object", "module"],
            "properties": {
                "name": {"type": "string"},
                "target_object": {"type": "string"},
                "module": {"type": "string"},
            },
        },
    },
    {
        "name": "create_ui_dialog",
        "description": "Create UI dialog",
        "inputSchema": {
            "type": "object",
            "required": ["name", "module"],
            "properties": {"name": {"type": "string"}, "module": {"type": "string"}},
        },
    },
    {
        "name": "expose_service",
        "description": "Expose component service",
        "inputSchema": {
            "type": "object",
            "required": ["component_name", "module"],
            "properties": {
                "component_name": {"type": "string"},
                "module": {"type": "string"},
                "framework": {"type": "string"},
            },
        },
    },
    {
        "name": "diagnose_workspace",
        "description": "Run full diagnostics",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "diagnose_and_fix",
        "description": "Diagnose and auto-fix",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "suggest_next",
        "description": "Suggest next action",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "incremental_build",
        "description": "mkmk -u build",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "full_build",
        "description": "mkmk -a full rebuild",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "clean_build",
        "description": "mkmk -c clean+build",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "build_with_threads",
        "description": "mkmk -j N build",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "threads": {"type": "integer", "default": 8},
            },
        },
    },
    {
        "name": "create_runtime_view",
        "description": "Create Runtime View",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "start_catia",
        "description": "Start CATIA",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "stop_catia",
        "description": "Stop CATIA (graceful then force)",
        "inputSchema": {
            "type": "object",
            "properties": {"force": {"type": "boolean", "default": False}},
        },
    },
    {
        "name": "check_catia",
        "description": "Check if CATIA running",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_catia_macro",
        "description": "Run CATScript macro",
        "inputSchema": {
            "type": "object",
            "required": ["macro"],
            "properties": {"macro": {"type": "string"}},
        },
    },
    {
        "name": "run_catia_batch",
        "description": "Run CATIA batch",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "rename_command",
        "description": "Rename command + all refs",
        "inputSchema": {
            "type": "object",
            "required": ["module", "old_name", "new_name"],
            "properties": {
                "module": {"type": "string"},
                "old_name": {"type": "string"},
                "new_name": {"type": "string"},
            },
        },
    },
    {
        "name": "rename_interface",
        "description": "Rename interface + implementors",
        "inputSchema": {
            "type": "object",
            "required": ["module", "old_name", "new_name"],
            "properties": {
                "module": {"type": "string"},
                "old_name": {"type": "string"},
                "new_name": {"type": "string"},
            },
        },
    },
    {
        "name": "move_command",
        "description": "Move command between modules",
        "inputSchema": {
            "type": "object",
            "required": ["source", "target", "command"],
            "properties": {
                "source": {"type": "string"},
                "target": {"type": "string"},
                "command": {"type": "string"},
            },
        },
    },
    {
        "name": "rename_module",
        "description": "Rename module + all refs",
        "inputSchema": {
            "type": "object",
            "required": ["framework", "old_name", "new_name"],
            "properties": {
                "framework": {"type": "string"},
                "old_name": {"type": "string"},
                "new_name": {"type": "string"},
            },
        },
    },
    {
        "name": "generate_docs",
        "description": "Auto-generate docs",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "get_version",
        "description": "CATIA/CADE version info",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_rollback_points",
        "description": "List backup points",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "rollback",
        "description": "Rollback to backup",
        "inputSchema": {
            "type": "object",
            "required": ["backup_id"],
            "properties": {"backup_id": {"type": "string"}},
        },
    },
    {
        "name": "workspace_snapshot",
        "description": "Full workspace snapshot with optional diff",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "label": {"type": "string"},
                "diff": {"type": "boolean"},
            },
        },
    },
    {
        "name": "setup_workspace_prerequisites",
        "description": "Setup workspace prerequisites (auto-detect CATIA and configure)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "catia_root": {"type": "string"},
                "detect_only": {"type": "boolean"},
            },
        },
    },
]


def handle_tool(name: str, args: dict) -> dict:
    ws = args.get("workspace", WORKSPACE)
    ctx = ActionContext(ws)
    try:
        # Analysis
        if name == "analyze_workspace":
            from actions import analyze_workspace

            return analyze_workspace(ctx)
        if name == "list_modules":
            from actions import list_modules

            return list_modules(ctx)
        if name == "list_commands":
            from actions import list_commands

            return list_commands(ctx)
        if name == "get_dependencies":
            from actions import get_dependencies

            return get_dependencies(ctx, args["entity"], args.get("type"))
        if name == "visualize_dependencies":
            from actions import visualize_dependencies

            return visualize_dependencies(ctx, args.get("entity"))
        if name == "validate_workspace":
            from actions import validate_workspace

            return validate_workspace(ctx)

        # Create
        if name == "create_executable_command":
            from intents import create_executable_command

            return create_executable_command(
                ctx,
                name=args["name"],
                module=args["module"],
                framework=args.get("framework"),
                with_dialog=args.get("with_dialog", False),
                dialog_name=args.get("dialog_name"),
                add_to_workbench=args.get("add_to_workbench"),
                stateful=args.get("stateful", False),
            )
        if name == "create_feature":
            from intents import create_feature

            return create_feature(
                ctx,
                name=args["name"],
                module=args["module"],
                framework=args.get("framework"),
            )
        if name == "create_extension":
            from intents import create_extension

            return create_extension(
                ctx,
                name=args["name"],
                target_object=args["target_object"],
                module=args["module"],
                framework=args.get("framework"),
            )
        if name == "create_ui_dialog":
            from intents import create_ui_dialog

            return create_ui_dialog(
                ctx,
                name=args["name"],
                module=args["module"],
                framework=args.get("framework"),
            )
        if name == "expose_service":
            from intents import expose_service

            return expose_service(
                ctx,
                component_name=args["component_name"],
                module=args["module"],
                framework=args.get("framework"),
            )

        # Diagnostics
        if name == "diagnose_workspace":
            from diagnostics import diagnose_workspace

            return diagnose_workspace(ctx)
        if name == "diagnose_and_fix":
            from diagnostics import diagnose_and_fix

            return diagnose_and_fix(ctx, dry_run=args.get("dry_run", True))
        if name == "suggest_next":
            from intents import suggest_next_action

            return suggest_next_action(ctx)

        # Build
        if name == "incremental_build":
            from build import incremental_build

            return incremental_build(Path(ws))
        if name == "full_build":
            from build import full_build

            return full_build(Path(ws))
        if name == "clean_build":
            from build import clean_build

            return clean_build(Path(ws))
        if name == "build_with_threads":
            from build import build_with_threads

            return build_with_threads(Path(ws), threads=args.get("threads", 8))
        if name == "create_runtime_view":
            from build import create_runtime_view

            return create_runtime_view(Path(ws))

        # Run
        if name == "start_catia":
            from run import start_catia_runtime

            return start_catia_runtime(workspace_path=ws)
        if name == "stop_catia":
            from run import stop_catia

            return stop_catia(force=args.get("force", False))
        if name == "check_catia":
            from run import check_catia_running

            return check_catia_running()
        if name == "run_catia_macro":
            from run import run_catia_macro

            return run_catia_macro(args["macro"])
        if name == "run_catia_batch":
            from run import run_catia_batch

            return run_catia_batch()

        # Refactor
        if name in (
            "rename_command",
            "rename_interface",
            "move_command",
            "rename_module",
        ):
            ctx.refresh()
            snapshot = ctx.snapshot
            if name == "rename_command":
                from refactor import rename_command

                return rename_command(
                    snapshot, args["module"], args["old_name"], args["new_name"]
                )
            if name == "rename_interface":
                from refactor import rename_interface

                return rename_interface(
                    snapshot, args["module"], args["old_name"], args["new_name"]
                )
            if name == "move_command":
                from refactor import move_command

                return move_command(
                    snapshot, args["source"], args["target"], args["command"]
                )
            if name == "rename_module":
                from refactor import rename_module

                return rename_module(
                    snapshot, args["framework"], args["old_name"], args["new_name"]
                )

        # Docs/Version/Backup
        if name == "generate_docs":
            from docgen import generate_all

            return generate_all(ws)
        if name == "get_version":
            from env import CAAEnvironment

            env = CAAEnvironment()
            env.load_config()
            return env.get_info()
        if name == "get_prerequisite":
            from build import get_prerequisite

            return get_prerequisite(Path(ws), target=args.get("target", ""))
        if name == "list_rollback_points":
            from actions import list_rollback_points

            return list_rollback_points(ctx)
        if name == "rollback":
            from actions import rollback_operation

            return rollback_operation(ctx, args["backup_id"])

        if name == "workspace_snapshot":
            label = args.get("label", "mcp_request")
            snap = ctx.refresh(label=label)
            if args.get("diff"):
                return {
                    "snapshot": snap.to_dict(),
                    "history": ctx.history.summary(),
                    "diff": ctx.history.diff_last_two(),
                }
            return {"snapshot": snap.to_dict(), "history": ctx.history.summary()}

        if name == "setup_workspace_prerequisites":
            sys.path.insert(0, str(SKILL_ROOT.parent / "tools"))
            from setup_prerequisites import (
                detect_catia_root,
                setup_workspace_prerequisites,
            )

            if args.get("detect_only"):
                catia_root = detect_catia_root()
                if catia_root:
                    return {"status": "ok", "catia_root": str(catia_root)}
                else:
                    return {"status": "error", "message": "CATIA not detected"}

            result = setup_workspace_prerequisites(
                workspace=Path(ws),
                catia_root=args.get("catia_root"),
            )
            return result

        return {"status": "error", "message": f"Unknown tool: {name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_stdio():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            req = json.loads(line)
            method = req.get("method", "")
            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "cade-mcp-server", "version": "2.0.0"},
                    },
                }
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "result": {"tools": TOOLS},
                }
            elif method == "tools/call":
                params = req.get("params", {})
                result = handle_tool(
                    params.get("name", ""), params.get("arguments", {})
                )
                resp = {
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2, default=str),
                            }
                        ]
                    },
                }
            elif method == "notifications/initialized":
                continue
            else:
                continue
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except (json.JSONDecodeError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    run_stdio()
