#!/usr/bin/env python3
"""
CADE — CATIA CAA Development Engine CLI
=========================================
Unified command-line interface for all CADE tools.

Usage:
  cade build [workspace]           # Incremental build (mkmk -u)
  cade build --full [workspace]    # Full rebuild
  cade build --clean [workspace]   # Clean + build
  cade build --threads 8 [ws]      # Multi-threaded build

  cade run [workspace]             # Start CATIA
  cade run --stop                  # Stop CATIA
  cade run --macro path.CATScript  # Run macro
  cade run --status                # Check if running

  cade create command <name> <module> [--dialog] [--wb name]
  cade create feature <name> <module>
  cade create extension <name> <target> <module>

  cade analyze [workspace]         # Full workspace analysis
  cade analyze --modules           # List modules
  cade analyze --commands          # List commands
  cade analyze --deps <entity>     # Dependency info
  cade analyze --graph [entity]    # Mermaid diagram

  cade diagnose [workspace]        # Diagnose issues
  cade fix [workspace]             # Diagnose + auto-fix

  cade docs [workspace]            # Generate documentation
  cade rv [workspace]              # Create Runtime View

  cade refactor rename <old> <new> --module <m>
  cade refactor move <cmd> --from <m1> --to <m2>

  cade setup [workspace]           # Setup workspace environment
  cade setup --detect              # Detect CATIA installation
  cade setup --show                # Show current configuration

  cade prereq add <fw> <component> [--visibility Public]
  cade prereq remove <fw> <component>
  cade prereq list <framework>     # List prerequisites
  cade prereq validate [workspace] # Validate dependencies
  cade prereq suggest <module>     # Suggest prerequisites
  cade prereq init <framework>     # Add default prerequisites

  cade version                     # Show version info
  cade test [--quick]              # Run test suite
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent
sys.path.insert(0, str(SKILL_ROOT))


def main():
    if len(sys.argv) < 2:
        print_help()
        return

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    if cmd == "build":
        cmd_build(args)
    elif cmd == "run":
        cmd_run(args)
    elif cmd == "create":
        cmd_create(args)
    elif cmd == "analyze":
        cmd_analyze(args)
    elif cmd == "diagnose":
        cmd_diagnose(args)
    elif cmd == "fix":
        cmd_fix(args)
    elif cmd == "validate":
        cmd_validate(args)
    elif cmd == "docs":
        cmd_docs(args)
    elif cmd == "rv":
        cmd_runtime_view(args)
    elif cmd == "refactor":
        cmd_refactor(args)
    elif cmd == "rollback":
        cmd_rollback(args)
    elif cmd == "snapshot":
        cmd_snapshot(args)
    elif cmd == "expose":
        cmd_expose(args)
    elif cmd == "suggest":
        cmd_suggest(args)
    elif cmd == "prereq":
        cmd_prereq_manager(args)
    elif cmd == "setup":
        cmd_setup(args)
    elif cmd == "version":
        cmd_version()
    elif cmd == "test":
        cmd_test(args)
    elif cmd in ("help", "-h", "--help"):
        print_help()
    else:
        print(f"Unknown command: {cmd}")
        print_help()


# ─── Build ────────────────────────────────────────────────────────


def cmd_build(args):
    from build import (
        build_with_threads,
        clean_build,
        debug_build,
        full_build,
        incremental_build,
    )

    ws = _get_ws(args)
    opts = _get_flags(args)

    if "--full" in opts or "-a" in opts:
        result = full_build(Path(ws))
    elif "--clean" in opts or "-c" in opts:
        result = clean_build(Path(ws))
    elif "--debug" in opts or "-g" in opts:
        result = debug_build(Path(ws))
    elif "--threads" in opts:
        idx = args.index("--threads") if "--threads" in args else args.index("-j")
        n = int(args[idx + 1]) if idx + 1 < len(args) else 8
        result = build_with_threads(Path(ws), n)
    else:
        result = incremental_build(Path(ws))

    _print_result(result)


# ─── Run ──────────────────────────────────────────────────────────


def cmd_run(args):
    from run import (
        check_catia_running,
        run_catia_batch,
        run_catia_macro,
        start_catia_runtime,
        stop_catia,
    )

    ws = _get_ws(args)
    opts = _get_flags(args)

    if "--stop" in opts:
        result = stop_catia(force="--force" in opts)
    elif "--status" in opts:
        result = check_catia_running()
    elif "--macro" in opts:
        idx = args.index("--macro")
        path = args[idx + 1] if idx + 1 < len(args) else ""
        result = run_catia_macro(path)
    elif "--batch" in opts:
        result = run_catia_batch()
    else:
        result = start_catia_runtime(workspace_path=ws)

    _print_result(result)


# ─── Create ───────────────────────────────────────────────────────


def cmd_create(args):
    if not args:
        print("Usage: cade create <type> <name> <module> [options]")
        print("Types: command, feature, extension")
        return

    sub = args[0].lower()
    from actions import ActionContext

    ws = _get_ws(args[1:])
    ctx = ActionContext(ws)
    opts = _get_flags(args)

    if sub == "command":
        from intents import create_executable_command

        name = args[1] if len(args) > 1 else input("Command name: ")
        module = args[2] if len(args) > 2 else input("Module name: ")
        result = create_executable_command(
            ctx,
            name=name,
            module=module,
            with_dialog="--dialog" in opts,
            add_to_workbench=opts.get("--wb") or opts.get("--workbench"),
        )
        _print_result(result)

    elif sub == "feature":
        from intents import create_feature

        name = args[1] if len(args) > 1 else input("Feature name: ")
        module = args[2] if len(args) > 2 else input("Module name: ")
        result = create_feature(ctx, name=name, module=module)
        _print_result(result)

    elif sub == "extension":
        from intents import create_extension

        name = args[1] if len(args) > 1 else input("Extension name: ")
        target = args[2] if len(args) > 2 else input("Target object: ")
        module = args[3] if len(args) > 3 else input("Module name: ")
        result = create_extension(ctx, name=name, target_object=target, module=module)
        _print_result(result)

    else:
        print(f"Unknown create type: {sub}")


# ─── Analyze ──────────────────────────────────────────────────────


def cmd_analyze(args):
    from actions import (
        ActionContext,
        analyze_workspace,
        get_dependencies,
        list_commands,
        list_modules,
        visualize_dependencies,
    )

    ws = _get_ws(args)
    ctx = ActionContext(ws)
    opts = _get_flags(args)

    if "--modules" in opts:
        result = list_modules(ctx)
        if result["status"] == "ok":
            for m in result.get("modules", []):
                print(f"  {m['name']} ({m.get('framework', '?')})")

    elif "--commands" in opts:
        result = list_commands(ctx)
        if result["status"] == "ok":
            for c in result.get("commands", []):
                print(f"  {c['name']} ({c.get('module', '?')})")

    elif "--deps" in opts:
        idx = args.index("--deps")
        entity = args[idx + 1] if idx + 1 < len(args) else ""
        result = get_dependencies(ctx, entity)
        _print_result(result)

    elif "--graph" in opts:
        entity = None
        if "--graph" in args:
            idx = args.index("--graph")
            if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
                entity = args[idx + 1]
        result = visualize_dependencies(ctx, entity)
        if "diagram" in result:
            print(result["diagram"])
        else:
            _print_result(result)

    else:
        result = analyze_workspace(ctx)
        _print_result(result)


# ─── Diagnose / Fix ───────────────────────────────────────────────


def cmd_diagnose(args):
    from actions import ActionContext
    from diagnostics import diagnose_workspace

    ws = _get_ws(args)
    ctx = ActionContext(ws)
    result = diagnose_workspace(ctx)
    _print_result(result)


def cmd_fix(args):
    from actions import ActionContext
    from diagnostics import diagnose_and_fix

    ws = _get_ws(args)
    ctx = ActionContext(ws)
    opts = _get_flags(args)
    dry_run = "--apply" not in opts
    result = diagnose_and_fix(ctx, dry_run=dry_run)
    _print_result(result)


def cmd_validate(args):
    from actions import ActionContext, validate_workspace

    ws = _get_ws(args)
    ctx = ActionContext(ws)
    result = validate_workspace(ctx)
    _print_result(result)


# ─── Docs ─────────────────────────────────────────────────────────


def cmd_docs(args):
    from docgen import generate_all

    ws = _get_ws(args)
    output = None
    if "-o" in args:
        idx = args.index("-o")
        output = args[idx + 1] if idx + 1 < len(args) else None
    result = generate_all(ws, output)
    _print_result(result)


# ─── Runtime View ─────────────────────────────────────────────────


def cmd_runtime_view(args):
    from build import create_runtime_view

    ws = _get_ws(args)
    result = create_runtime_view(Path(ws))
    _print_result(result)


# ─── Refactor ─────────────────────────────────────────────────────


def cmd_refactor(args):
    if not args:
        print("Usage: cade refactor <op> [options]")
        return

    from actions import ActionContext
    from refactor import move_command, rename_command, rename_interface

    ws = _get_ws(args)
    ctx = ActionContext(ws)
    ctx.refresh()
    snapshot = ctx.snapshot
    sub = args[0].lower()

    if sub == "rename":
        old = args[1] if len(args) > 1 else ""
        new = args[2] if len(args) > 2 else ""
        module = _parse_flag(args, "--module", "-m")
        result = (
            rename_command(snapshot, module, old, new)
            if module
            else {"status": "error", "message": "--module required"}
        )
        _print_result(result)

    elif sub == "move":
        cmd_name = args[1] if len(args) > 1 else ""
        src = _parse_flag(args, "--from")
        tgt = _parse_flag(args, "--to")
        result = move_command(snapshot, src, tgt, cmd_name)
        _print_result(result)

    else:
        print(f"Unknown refactor op: {sub}")


def cmd_rollback(args):
    from actions import ActionContext, list_rollback_points, rollback_operation

    ws = _get_ws(args)
    ctx = ActionContext(ws)
    if "--list" in args or "-l" in args:
        result = list_rollback_points(ctx)
        for b in result.get("backups", [])[:10]:
            print(f"  {b['backup_id']}  {b['action']}")
    elif "--id" in args:
        bid = args[args.index("--id") + 1] if args.index("--id") + 1 < len(args) else ""
        result = rollback_operation(ctx, bid)
        _print_result(result)
    else:
        result = list_rollback_points(ctx)
        _print_result(result)


def cmd_expose(args):
    from actions import ActionContext
    from intents import expose_service

    ws = _get_ws(args)
    ctx = ActionContext(ws)
    comp = args[0] if args else input("Component name: ")
    mod = args[1] if len(args) > 1 else input("Module name: ")
    result = expose_service(ctx, component_name=comp, module=mod)
    _print_result(result)


def cmd_suggest(args):
    from actions import ActionContext
    from intents import suggest_next_action

    ws = _get_ws(args)
    ctx = ActionContext(ws)
    result = suggest_next_action(ctx)
    _print_result(result)


def cmd_prereq_manager(args):
    """Manage framework prerequisites (AddPrereqComponent)."""
    import subprocess
    import sys

    # Get script path
    script = SKILL_ROOT.parent / "tools" / "prerequisites_manager.py"

    # Forward all arguments to the script
    cmd = [sys.executable, str(script)] + args

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


def cmd_get_prereq(args):
    """Get prerequisite info (mkGetPreq wrapper)."""
    from build import get_prerequisite

    ws = _get_ws(args)
    target = args[0] if args else ""
    result = get_prerequisite(Path(ws), target=target)
    _print_result(result)


def cmd_setup(args):
    """Setup workspace environment."""
    import subprocess
    import sys

    # Get script path
    script = SKILL_ROOT.parent / "tools" / "setup_environment.py"

    # Forward all arguments to the script
    cmd = [sys.executable, str(script)] + args

    try:
        result = subprocess.run(cmd, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


def cmd_snapshot(args):
    from actions import ActionContext

    ws = _get_ws(args)
    ctx = ActionContext(ws)
    opts = _get_flags(args)

    if "--diff" in opts:
        ctx.refresh(label="snapshot")
        diff = ctx.history.diff_last_two()
        _print_result(diff)
    elif "--history" in opts:
        _print_result(ctx.history.summary())
    else:
        snap = ctx.refresh(label="snapshot")
        _print_result(snap.to_dict())


# ─── Version / Test ───────────────────────────────────────────────


def cmd_version():
    from env import CAAEnvironment

    env = CAAEnvironment()
    env.load_config()
    info = env.get_info()
    print(f"CADE v2.0.0 — CATIA CAA Development Engine")
    print(f"  CATIA: {info.get('catia_version', 'unknown')}")
    print(f"  Install: {info.get('catia_install', 'unknown')}")
    print(f"  Architecture: {info.get('caa_platform', 'unknown')}")
    if "caa_version_label" in info:
        print(f"  Detected: {info['caa_version_label']}")


def cmd_test(args):
    import subprocess

    quick = "--quick" in args
    runner = SKILL_ROOT / "tests" / "test_master.py"
    if runner.exists():
        cmd = [sys.executable, str(runner)]
        if quick:
            cmd.append("--quick")
        subprocess.run(cmd)
    else:
        print("Test runner not found")


# ─── Helpers ──────────────────────────────────────────────────────


def _get_default_ws():
    """Get default workspace: env CADE_WORKSPACE > config > D:/test"""
    import os

    if os.environ.get("CADE_WORKSPACE"):
        return os.environ["CADE_WORKSPACE"]
    from env import CAAEnvironment

    env = CAAEnvironment()
    if env.load_config():
        return env.config.get("WORKSPACE", os.getcwd())
    return os.getcwd()


def _get_ws(args) -> str:
    """Extract workspace path from args — first non-flag arg, or config default"""
    for a in args:
        if not a.startswith("-"):
            return a
    return _get_default_ws()


def _get_flags(args) -> dict:
    """Parse flags into a dict: --flag → True, --key value → value"""
    flags = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                flags[key] = args[i + 1]
                i += 1
            else:
                flags[key] = True
        i += 1
    return flags


def _parse_flag(args, *names) -> str:
    """Get the value of a named flag"""
    for name in names:
        if name in args:
            idx = args.index(name)
            if idx + 1 < len(args):
                return args[idx + 1]
    return ""


def _print_result(result):
    """Pretty-print result"""
    if isinstance(result, dict):
        import json

        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
    else:
        print(result)


def print_help():
    print(__doc__)


if __name__ == "__main__":
    main()
