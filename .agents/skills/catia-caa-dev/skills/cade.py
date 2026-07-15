#!/usr/bin/env python3
"""
CADE — CATIA CAA Development Kernel CLI
=========================================
Unified command-line interface for all CADE tools.

Usage:
  cade develop <request> [--workspace path]
                                   # Full development pipeline (自然语言→代码)

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

  cade plan <type> <name> <module> [--fw framework]
                                   # Generate development plan
  cade impact <entity> <type> <op>  # Analyze change impact
  cade optimize [plans...]          # Recommend best plan
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent
sys.path.insert(0, str(SKILL_ROOT))


def _kernel(capability: str, text: str) -> dict:
    """Route CLI command through Kernel."""
    from kernel import Kernel, KernelMode
    mode_map = {"develop": KernelMode.DEVELOP, "analyze": KernelMode.ANALYZE, "repair": KernelMode.REPAIR}
    # Find workspace from --workspace flag or use default
    ws = _get_default_ws()
    for i, a in enumerate(sys.argv):
        if a in ("--workspace", "-w") and i + 1 < len(sys.argv):
            ws = sys.argv[i + 1]
            break
    k = Kernel(workspace_root=ws)
    return k.execute(mode_map[capability], text)


def _print_kernel(r: dict):
    """Print Kernel result in CLI-friendly format."""
    status = r.get("status", "?")
    msg = r.get("message", "")
    print(f"[{status}] {msg}")
    # Show clarification questions if present
    if r.get("data") and isinstance(r["data"], dict):
        questions = r["data"].get("questions", [])
        if questions:
            print()
            for q in questions:
                opts = "/".join(q.get("options", []))
                print(f"  ? {q.get('question', '')} [{opts}]")
    # Show verification results
    verify = r.get("verification", {})
    if verify:
        print(f"  Verification: {verify.get('error_count', 0)} errors, {verify.get('files_checked', 0)} files")
    # Show extras applied
    extras = r.get("extras_applied", {})
    if extras:
        applied = []
        if extras.get("deps_added"): applied.append(f"deps: {', '.join(extras['deps_added'])}")
        if extras.get("refs_added"): applied.append(f"refs: {len(extras['refs_added'])} injected")
        if applied: print(f"  Extras: {'; '.join(applied)}")


def main():
    if len(sys.argv) < 2:
        print_help()
        return

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    if cmd == "build":
        cmd_build(args)
    elif cmd == "develop":
        cmd_develop(args)
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
    elif cmd == "plan":
        cmd_plan(args)
    elif cmd == "impact":
        cmd_impact(args)
    elif cmd == "optimize":
        cmd_optimize(args)
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


# ─── Develop ───────────────────────────────────────────────────────


def cmd_develop(args):
    """Full development pipeline: natural language → code.
    Usage: cade develop "创建一个设置命令SettingsCmd，放在TestModule模块" --workspace D:/test
    """
    if not args:
        print("Usage: cade develop <natural language request> [--workspace path]")
        print()
        print("Examples:")
        print('  cade develop "create command HelloCmd in MyModule"')
        print('  cade develop "创建一个设置命令SettingsCmd，放在TestModule模块中"')
        print('  cade develop "analyze the workspace" --workspace D:/myproject')
        return

    # Separate flags from the natural language request
    opts = _get_flags(args)
    flag_keywords = {"--workspace", "-w", "--mode", "-m"}
    text_parts = [a for a in args if a not in flag_keywords and (not a.startswith("--") or a in ("--dialog",))]
    # Also skip values that follow flags
    skip_next = False
    filtered = []
    for i, a in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if a in ("--workspace", "-w", "--mode", "-m"):
            skip_next = True
            continue
        if a.startswith("--") and a not in ("--dialog",):
            skip_next = True
            continue
        filtered.append(a)
    text = " ".join(filtered)

    if not text.strip():
        print("Error: please provide a natural language request")
        return

    # Detect mode: contains analysis/comprehension keywords → analyze
    analyze_kw = ("analyze", "list", "show", "check", "inspect", "validate", "diagnos",
                  "分析", "列出", "显示", "检查", "验证", "诊断")
    repair_kw = ("fix", "repair", "修复", "恢复")
    text_lower = text.lower()
    if any(kw in text_lower for kw in analyze_kw):
        result = _kernel("analyze", text)
    elif any(kw in text_lower for kw in repair_kw):
        result = _kernel("repair", text)
    else:
        result = _kernel("develop", text)
    _print_kernel(result)


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
    """Create via Kernel — all types routed through develop()."""
    if not args:
        print("Usage: cade create <type> <name> <module> [options]")
        print("  type: command | feature | extension | workbench | dialog | interface | module | framework")
        return
    sub = args[0].lower()
    name = args[1] if len(args) > 1 else ""
    module = args[2] if len(args) > 2 else "MyModule.m"
    opts = _get_flags(args)
    dialog = "--dialog" in opts or "-d" in opts
    wb = None
    for i, a in enumerate(args):
        if a in ("--wb", "--workbench") and i + 1 < len(args):
            wb = args[i + 1]

    if not name:
        print("Error: name is required")
        return

    # Build natural language request
    extra = ""
    if sub == "command" and dialog:
        extra = " with dialog"
        if wb:
            extra += f" and add to workbench {wb}"
    if sub == "feature":
        extra = " with factory"

    text = f"create {sub} {name} in {module}{extra}"
    result = _kernel("develop", text)
    _print_kernel(result)


# ─── Analyze ──────────────────────────────────────────────────────


def cmd_analyze(args):
    """Analyze via Kernel — routes through analyze()."""
    opts = _get_flags(args)
    if "--modules" in opts:
        text = "list all modules"
    elif "--commands" in opts:
        text = "list all commands"
    elif "--deps" in opts:
        idx = args.index("--deps")
        entity = args[idx + 1] if idx + 1 < len(args) else ""
        text = f"show dependencies of {entity}"
    elif "--graph" in opts:
        entity = next((args[i + 1] for i, a in enumerate(args) if a == "--graph" and i + 1 < len(args) and not args[i + 1].startswith("--")), None)
        text = f"visualize dependency graph of {entity}" if entity else "visualize dependency graph"
    else:
        text = "analyze the workspace"
    result = _kernel("analyze", text)
    _print_kernel(result)
    # Print diagram if present
    data = result.get("data", {})
    if isinstance(data, dict) and data.get("diagram"):
        print(data["diagram"])
    # Print references if present
    refs = result.get("references", data.get("references", []))
    if refs:
        for r in refs[:5]:
            print(f"  - {r}")


# ─── Diagnose / Fix ───────────────────────────────────────────────


def cmd_diagnose(args):
    """Diagnose via Kernel — routes through analyze()."""
    ws = _get_ws(args)
    text = f"diagnose the workspace {ws}" if ws else "diagnose the workspace"
    result = _kernel("analyze", text)
    _print_kernel(result)


def cmd_fix(args):
    """Fix via Kernel — routes through repair()."""
    result = _kernel("repair", "fix workspace issues")
    _print_kernel(result)


def cmd_validate(args):
    """Validate via Kernel — routes through analyze()."""
    result = _kernel("analyze", "validate workspace")
    _print_kernel(result)


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
    """Refactor via Kernel — routes through repair()."""
    if not args:
        print("Usage: cade refactor rename <old> <new> --module <m>")
        print("       cade refactor move <cmd> --from <m1> --to <m2>")
        return
    sub = args[0].lower()
    if sub == "rename":
        old = args[1] if len(args) > 1 else ""
        new = args[2] if len(args) > 2 else ""
        module = _parse_flag(args, "--module", "-m")
        text = f"rename command {old} to {new} in {module}" if module else f"rename {old} to {new}"
        result = _kernel("repair", text)
        _print_kernel(result)
    elif sub == "move":
        cmd_name = args[1] if len(args) > 1 else ""
        src = _parse_flag(args, "--from")
        tgt = _parse_flag(args, "--to")
        text = f"move command {cmd_name} from {src} to {tgt}"
        result = _kernel("repair", text)
        _print_kernel(result)
    else:
        print(f"Unknown refactor op: {sub}")


def cmd_rollback(args):
    """Rollback via Kernel — routes through repair()."""
    if "--list" in args or "-l" in args:
        result = _kernel("repair", "list rollback points")
        _print_kernel(result)
    elif "--id" in args:
        bid = args[args.index("--id") + 1] if args.index("--id") + 1 < len(args) else ""
        result = _kernel("repair", f"rollback to {bid}")
        _print_kernel(result)
    else:
        result = _kernel("repair", "list rollback points")
        _print_kernel(result)


def cmd_expose(args):
    """Expose via Kernel — routes through develop()."""
    comp = args[0] if args else input("Component name: ")
    mod = args[1] if len(args) > 1 else input("Module name: ")
    text = f"expose service from {comp} in {mod}"
    result = _kernel("develop", text)
    _print_kernel(result)


def cmd_suggest(args):
    """Suggest via Kernel — routes through analyze()."""
    result = _kernel("analyze", "suggest next action")
    _print_kernel(result)


def cmd_plan(args):
    """Generate a development plan from intent."""
    if len(args) < 3:
        print("Usage: cade plan <type> <name> <module> [--fw framework]")
        return
    from intent import Intent, IntentType, plan
    i = Intent(
        type=IntentType(args[0]),
        name=args[1],
        module=args[2],
        framework=_get_flag(args, "--fw") or "MyFramework",
    )
    result = plan(i)
    _print_result(result.to_dict())


def cmd_impact(args):
    """Analyze impact of a change."""
    if len(args) < 3:
        print("Usage: cade impact <entity_name> <type> <operation>")
        return
    from intent import analyze
    result = analyze(entity_name=args[0], entity_type=args[1], operation=args[2])
    _print_result(result.to_dict())


def cmd_optimize(args):
    """Recommend best plan from alternatives."""
    from intent import recommend
    result = recommend([])
    print(result or "No plans to optimize.")


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
    """Snapshot via Kernel — routes through repair()."""
    if "--diff" in args or "-d" in args:
        result = _kernel("repair", "show snapshot diff")
    elif "--history" in args:
        result = _kernel("repair", "show snapshot history")
    else:
        result = _kernel("repair", "create workspace snapshot")
    _print_kernel(result)


# ─── Version / Test ───────────────────────────────────────────────


def cmd_version():
    from env import CAAEnvironment

    env = CAAEnvironment()
    env.load_config()
    info = env.get_info()
    print(f"CADE v3.0.0 — CATIA CAA Development Kernel")
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
