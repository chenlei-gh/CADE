#!/usr/bin/env python3
"""
CADE — CATIA CAA Development Kernel CLI
=========================================
Unified command-line interface for all CADE tools.

Usage:
  cade develop <request> [--workspace path]
                                   # Full development pipeline (自然语言→代码)
  cade develop <request> --preview # Generate ChangeSet but do NOT apply
                                   # (review-then-apply; makes rollback usable)

  cade build [workspace]           # Incremental build (mkmk -u)
  cade build --full [workspace]    # Full rebuild
  cade build --clean [workspace]   # Clean + build
  cade build --threads 8 [ws]      # Multi-threaded build

  cade dev <workspace>              # Build + Run in one command

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
  cade verify [module]             # Targeted code & UI verification for module
  cade feedback <module> --symptom "..." [--expected "..."] [--actual "..."]
                                   # Record developer observation from CATIA runtime
  cade validate [workspace]        # Validate workspace

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
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent
sys.path.insert(0, str(SKILL_ROOT))


def _kernel(capability: str, text: str, workspace: str = None, preview: bool = False, detail: bool = False) -> dict:
    """Route CLI command through Kernel for the explicitly selected workspace."""
    from kernel import Kernel, KernelMode
    mode_map = {"develop": KernelMode.DEVELOP, "analyze": KernelMode.ANALYZE, "repair": KernelMode.REPAIR}
    # Explicit positional workspace takes priority, then --workspace, then default.
    ws = workspace or _get_default_ws()
    for i, a in enumerate(sys.argv):
        if a in ("--workspace", "-w") and i + 1 < len(sys.argv):
            ws = sys.argv[i + 1]
            break
    k = Kernel(workspace_root=ws)
    return k.execute(mode_map[capability], text, preview=preview, detail=detail)


def _print_kernel(r: dict):
    """Print Kernel result in CLI-friendly format."""
    status = r.get("status", "?")
    msg = r.get("message", "")
    print(f"[{status}] {msg}")

    data = r.get("data", {})
    if not isinstance(data, dict):
        data = {}

    maint_status = data.get("maintenance_context_status")
    maint_reason = data.get("maintenance_context_reason")
    task_id = data.get("task_id")
    target_mod = data.get("target_module")
    ctx_path = data.get("context_path")

    if maint_status in ("CREATED", "UPDATED", "REUSED_ACTIVE"):
        print("======================================================================")
        status_label = "REUSED EXISTING ACTIVE TASK" if maint_status == "REUSED_ACTIVE" else maint_status
        print(f"Maintenance Context: {status_label}")
        print(f"  Task ID:   {task_id}")
        print(f"  Module:    {target_mod}")
        if ctx_path:
            print(f"  Storage:   {ctx_path}")
        if maint_status == "REUSED_ACTIVE" and maint_reason:
            print(f"  Note:      {maint_reason}")
        print("======================================================================")
        print("Next Recommended Actions:")
        print(f"  1. Verify code & UI rules:")
        print(f"     cade verify {target_mod}")
        print(f"  2. Build in maintenance mode (Context-Aware Build):")
        print(f"     cade build -m {target_mod}")
        print(f"  3. Run and test in CATIA:")
        print(f"     cade run")
        print(f"  4. Record runtime feedback:")
        print(f"     cade feedback {target_mod} --symptom \"<observation>\"")
        print("======================================================================")
    elif maint_status == "INACTIVE_TASK_EXISTS":
        raw_st = str(data.get("status", "INACTIVE")).upper()
        print("======================================================================")
        print(f"[WARN] Maintenance Context: PREVIOUS TASK IS {raw_st}")
        print(f"  Task ID:   {task_id}")
        print(f"  Module:    {target_mod}")
        print(f"  Note:      {maint_reason}")
        print(f"  Action:    To start a new maintenance task on {target_mod}, archive or remove:")
        if ctx_path:
            print(f"             {ctx_path}")
        print("======================================================================")
    elif maint_status == "ERROR":
        print(f"[WARN] Maintenance Context Error: {maint_reason}")
    elif maint_status == "NOT_CREATED" and maint_reason:
        print(f"Maintenance Context: NOT CREATED (Reason: {maint_reason})")

    # In preview mode, make it explicit how to proceed
    if status == "preview":
        data = r.get("data", {})
        cs = data.get("changeset") if isinstance(data, dict) else None
        n_ops = len(cs.get("operations", [])) if isinstance(cs, dict) else 0
        print(f"  ChangeSet contains {n_ops} operation(s). To apply, re-run the same command without --preview.")
        print(f"  (If you apply and want to undo, use: cade rollback --id latest)")
    # Show clarification questions if present
    if r.get("data") and isinstance(r["data"], dict):
        questions = r["data"].get("questions", [])
        if questions:
            print()
            for q in questions:
                opts = "/".join(q.get("options", []))
                print(f"  ? {q.get('question', '')} [{opts}]")
    # Show structured diagnostics. Kernel nests the diagnostics summary under
    # data.diagnostics; direct callers may return the summary as data itself.
    data = r.get("data", {})
    diag = r.get("diagnostics")
    if diag is None and isinstance(data, dict):
        diag = data.get("diagnostics", data)
    if isinstance(diag, dict):
        for item in diag.get("diagnostics", []):
            if isinstance(item, dict):
                print(f"  [{item.get('severity', 'info')}] {item.get('problem') or item.get('message', '')}")
    # Show verification results
    verify = r.get("verification", {})
    if not verify and isinstance(data, dict):
        verify = data.get("verification", {})
    if isinstance(verify, dict) and verify:
        summary = verify.get("summary", {})
        if summary:
            print(f"  Verification: {summary.get('code_errors', 0)} error(s), {summary.get('code_warnings', 0)} warning(s), {summary.get('ui_findings', 0)} UI finding(s) across {summary.get('files_checked', 0)} file(s)")
        elif "error_count" in verify:
            print(f"  Verification: {verify.get('error_count', 0)} errors, {verify.get('files_checked', 0)} files")
        for issue in verify.get("code_issues", verify.get("issues", []))[:5]:
            if isinstance(issue, dict):
                loc = f"{issue.get('file', '')}:{issue.get('line', '')}"
                print(f"    [{issue.get('severity', 'warning')}] {loc} - {issue.get('message', '')}")
        for f in verify.get("ui_findings", [])[:5]:
            if isinstance(f, dict):
                loc = f"{f.get('file', '')}:{f.get('line', '')}"
                print(f"    [UI-{f.get('severity', 'warning')}] {loc} - {f.get('problem', '')} ({f.get('fix_hint', '')})")

    # Show active build errors (L0 Direct Evidence) if any
    active_errs = r.get("active_build_errors", data.get("active_build_errors", []) if isinstance(data, dict) else [])
    if active_errs:
        print("  Active Build Errors (L0 Direct Evidence):")
        for err in active_errs[:5]:
            if isinstance(err, dict):
                f_name = err.get("file") or "linker"
                l_num = f":{err.get('line')}" if err.get("line") else ""
                c_code = f" [{err.get('code')}]" if err.get("code") else ""
                print(f"    • [L0] {f_name}{l_num}{c_code} - {err.get('message', '')}")

    # Show recorded human runtime feedback (distinct from compiler/build evidence)
    rt_feedbacks = r.get("runtime_feedback", data.get("runtime_feedback", []) if isinstance(data, dict) else [])
    if rt_feedbacks:
        print("  Recorded Runtime Feedback (Human Observation - Not Compiler Fact):")
        for fb in rt_feedbacks[-3:]:
            if isinstance(fb, dict):
                fb_time = fb.get("timestamp", "")[:19].replace("T", " ")
                b_id = f" [Build Ref: {fb.get('build_id')}]" if fb.get("build_id") else ""
                print(f"    • [{fb_time}]{b_id} Symptom: {fb.get('symptom', '')}")
                if fb.get("actual"):
                    print(f"      Actual:   {fb.get('actual')}")
                if fb.get("expected"):
                    print(f"      Expected: {fb.get('expected')}")
                if fb.get("steps"):
                    steps_preview = "; ".join(fb.get("steps")[:2])
                    print(f"      Steps:    {steps_preview}")

    # Show relevant code locations
    locations = r.get("relevant_locations", data.get("relevant_locations", []) if isinstance(data, dict) else [])
    if locations:
        print("  Relevant Locations:")
        for loc in locations[:5]:
            if isinstance(loc, dict):
                print(f"    • {loc.get('file', '')}:{loc.get('line', '')} [{loc.get('symbol', '')}] - {loc.get('snippet', '')}")

    # Show failure patterns
    fps = r.get("failure_patterns", data.get("failure_patterns", []) if isinstance(data, dict) else [])
    if fps:
        print("  Related Failure Patterns:")
        for fp in fps[:3]:
            print(f"    • {fp}")

    # Show guidance
    guidance = r.get("guidance", data.get("guidance", []) if isinstance(data, dict) else [])
    if guidance:
        print()
        print("  Guidance:")
        for g in guidance:
            print(f"    {g}")
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
        sys.exit(0)

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]
    rc = 0

    if cmd == "build":
        rc = cmd_build(args)
    elif cmd == "dev":
        rc = cmd_dev(args)
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
    elif cmd == "verify":
        cmd_verify(args)
    elif cmd == "feedback":
        rc = cmd_feedback(args)
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
    elif cmd == "plan":
        cmd_plan(args)
    elif cmd == "impact":
        cmd_impact(args)
    elif cmd == "prereq":
        cmd_prereq_manager(args)

    elif cmd == "setup":
        cmd_setup(args)
    elif cmd == "version":
        cmd_version()
    elif cmd == "health":
        rc = cmd_health(args)
    elif cmd == "test":
        rc = cmd_test(args)
    elif cmd in ("help", "-h", "--help"):
        print_help()
    else:
        print(f"Unknown command: {cmd}")
        print_help()
        rc = 1

    sys.exit(rc)


# ─── Develop ───────────────────────────────────────────────────────


def cmd_develop(args):
    """Full development pipeline: natural language → code.
    Usage: cade develop "创建一个设置命令SettingsCmd，放在TestModule模块" --workspace D:/test
           cade develop "..." --workspace D:/test --preview   # Generate but do NOT apply
    """
    if not args:
        print("Usage: cade develop <natural language request> [--workspace path] [--preview]")
        print()
        print("Options:")
        print("  --preview   Generate the ChangeSet but do NOT apply it to the workspace.")
        print("              Review data.changeset in the output, then re-run without")
        print("              --preview to actually apply, or discard. Enables a")
        print("              review-then-apply workflow that makes rollback usable.")
        print()
        print("Examples:")
        print('  cade develop "create command HelloCmd in MyModule"')
        print('  cade develop "create command HelloCmd in MyModule" --preview')
        print('  cade develop "创建一个设置命令SettingsCmd，放在TestModule模块中"')
        print('  cade develop "analyze the workspace" --workspace D:/myproject')
        return

    # Separate flags from the natural language request
    opts = _get_flags(args)
    preview = "--preview" in opts
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
        if a == "--preview":
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
        result = _kernel("develop", text, preview=preview)
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
    from maintenance_context import get_module_context_status

    ws = _get_ws(args)
    opts = _get_flags(args)

    target_mod = None
    if "-m" in args:
        idx = args.index("-m")
        if idx + 1 < len(args):
            target_mod = args[idx + 1]
    elif "--module" in args:
        idx = args.index("--module")
        if idx + 1 < len(args):
            target_mod = args[idx + 1]

    task_id = _parse_flag(args, "--task-id", "--task") or None

    status_info = None
    if target_mod:
        status_info = get_module_context_status(ws, target_mod, requested_task_id=task_id)
        if status_info.get("mode") == "error":
            print(f"[ERROR] {status_info.get('error')}")
            print("Build aborted to prevent attaching results to an incorrect task context.")
            return 1
        elif status_info.get("mode") == "maintenance":
            print("======================================================================")
            print("[MODE] MAINTENANCE (Context-Aware Build)")
            print(f"[CONTEXT] {status_info.get('context_path')}")
            print(f"[TASK] {status_info.get('task_id')}")
            print(f"[MODULE] {status_info.get('target_module')}")
            print("[NOTE] Build outcome will be automatically associated with this active task.")
            print("======================================================================")
        else:
            print("======================================================================")
            print("[MODE] STANDALONE (Independent Build)")
            print(f"[WARN] No active maintenance context found for module '{target_mod}'.")
            print("[WARN] Build result will NOT be attached to any maintenance history.")
            print(f"[HINT] To track as a maintenance task, run first:")
            print(f"       cade analyze \"排查/修复 {target_mod} <问题描述>\" --workspace \"{ws}\"")
            print("======================================================================")
    else:
        print("[MODE] STANDALONE (Independent Build, workspace-level)")

    if "--full" in opts or "-a" in opts:
        result = full_build(Path(ws), entrypoint="cade_cli", orchestrated_by_kernel=False, target_module=target_mod)
    elif "--clean" in opts or "-c" in opts:
        result = clean_build(Path(ws), entrypoint="cade_cli", orchestrated_by_kernel=False, target_module=target_mod)
    elif "--debug" in opts or "-g" in opts:
        result = debug_build(Path(ws), entrypoint="cade_cli", orchestrated_by_kernel=False, target_module=target_mod)
    elif "--threads" in opts:
        idx = args.index("--threads") if "--threads" in args else args.index("-j")
        n = int(args[idx + 1]) if idx + 1 < len(args) else 8
        result = build_with_threads(Path(ws), n, entrypoint="cade_cli", orchestrated_by_kernel=False, target_module=target_mod)
    else:
        result = incremental_build(Path(ws), entrypoint="cade_cli", orchestrated_by_kernel=False, target_module=target_mod)

    bid = result.get("build_id") if isinstance(result, dict) else None
    if bid:
        if status_info and status_info.get("mode") == "maintenance":
            print(f"\n[BUILD] Build ID: {bid} (attached to task {status_info.get('task_id')})")
        else:
            print(f"\n[BUILD] Build ID: {bid} (standalone build, not attached)")

    return _print_result(result)


def cmd_dev(args):
    """Build then run — one-command development cycle.
    Usage: cade dev <workspace>
    """
    from build import incremental_build
    from run import start_catia_runtime

    ws = _get_ws(args)
    if not ws:
        print("Error: workspace path required")
        return 1

    print(f"[build] {ws}")
    build_result = incremental_build(Path(ws), entrypoint="cade_cli", orchestrated_by_kernel=False)
    if build_result.get("status") != "success":
        _print_result(build_result)
        return 1
    print(f"[run] {ws}")
    return _print_result(start_catia_runtime(workspace_path=ws, entrypoint="cade_cli", orchestrated_by_kernel=False))


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
        result = stop_catia(force="--force" in opts, entrypoint="cade_cli", orchestrated_by_kernel=False)
    elif "--status" in opts:
        result = check_catia_running()
    elif "--macro" in opts:
        idx = args.index("--macro")
        path = args[idx + 1] if idx + 1 < len(args) else ""
        result = run_catia_macro(path, workspace_path=ws)
    elif "--batch" in opts:
        result = run_catia_batch()
    else:
        result = start_catia_runtime(workspace_path=ws, entrypoint="cade_cli", orchestrated_by_kernel=False)

    return _print_result(result)


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
    detail = "--detail" in opts
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
        ws = _parse_flag(args, "--workspace", "-w")
        non_flags = []
        skip_next = False
        for a in args:
            if skip_next:
                skip_next = False
                continue
            if a in ("--workspace", "-w"):
                skip_next = True
                continue
            if a.startswith("-"):
                continue
            non_flags.append(a)
        if non_flags:
            first = non_flags[0]
            if " " in first or any('\u4e00' <= ch <= '\u9fff' for ch in first) or len(non_flags) > 1:
                if not ws and len(non_flags) > 1 and (":" in non_flags[-1] or "/" in non_flags[-1] or "\\" in non_flags[-1]):
                    ws = non_flags[-1]
                    text = " ".join(non_flags[:-1])
                else:
                    text = " ".join(non_flags)
            else:
                text = f"analyze module {first}"
                if not ws and len(non_flags) > 1:
                    ws = non_flags[1]
        else:
            text = "analyze the workspace"
    result = _kernel("analyze", text, workspace=ws, detail=detail)
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
    guide = result.get("reading_guide", data.get("reading_guide", ""))
    if guide:
        print(f"  阅读顺序: {guide}")
    # --detail: print inlined knowledge content (flattened to top level)
    for item in result.get("content", []):
        print(f"\n=== {item['file']} (id: {item['id']}) ===")
        print(item["content"])
        if item.get("truncated"):
            print("... [truncated]")


# ─── Diagnose / Fix ───────────────────────────────────────────────


def cmd_diagnose(args):
    """Diagnose via Kernel — routes through analyze()."""
    ws = _get_ws(args)
    text = f"diagnose the workspace {ws}" if ws else "diagnose the workspace"
    result = _kernel("analyze", text, workspace=ws)
    _print_kernel(result)


def cmd_fix(args):
    """Fix via Kernel — routes through repair()."""
    result = _kernel("repair", "fix workspace issues")
    _print_kernel(result)


def cmd_validate(args):
    """Validate via Kernel — routes through analyze()."""
    result = _kernel("analyze", "validate workspace")
    _print_kernel(result)


def cmd_verify(args):
    """Verify code standards and UI failure patterns via Kernel.
    Usage: cade verify [module_name] [--workspace path]
    """
    ws = _parse_flag(args, "--workspace", "-w")
    non_flags = []
    skip_next = False
    for a in args:
        if skip_next:
            skip_next = False
            continue
        if a in ("--workspace", "-w"):
            skip_next = True
            continue
        if a.startswith("-"):
            continue
        non_flags.append(a)

    target = ""
    if non_flags:
        target = non_flags[0]
        if not ws and len(non_flags) > 1:
            ws = non_flags[1]
    if not ws:
        ws = _get_default_ws()

    text = f"verify module {target}" if target else "verify workspace"
    result = _kernel("analyze", text, workspace=ws)
    _print_kernel(result)


def cmd_feedback(args):
    """Record or inspect human runtime observations from CATIA for a maintenance module.
    Usage:
      cade feedback <module> --symptom "..." [--expected "..."] [--actual "..."] [--steps "..."] [--build-id "..."] [--workspace path]
      cade feedback <module> --list [--workspace path]
    """
    from maintenance_context import record_runtime_feedback, load_context

    ws = _parse_flag(args, "--workspace", "-w")
    if not ws:
        ws = _get_default_ws()

    symptom = _parse_flag(args, "--symptom", "-s")
    expected = _parse_flag(args, "--expected", "-e") or ""
    actual = _parse_flag(args, "--actual", "-a") or ""
    steps_raw = _parse_flag(args, "--steps") or ""
    build_id = _parse_flag(args, "--build-id", "-b")
    reporter = _parse_flag(args, "--reporter") or ""
    list_mode = "--list" in args or "-l" in args

    # Find positional module name
    non_flags = []
    skip_next = False
    flag_keys = ("--workspace", "-w", "--symptom", "-s", "--expected", "-e", "--actual", "-a", "--steps", "--build-id", "-b", "--reporter")
    for a in args:
        if skip_next:
            skip_next = False
            continue
        if a in flag_keys:
            skip_next = True
            continue
        if a in ("--list", "-l"):
            continue
        if a.startswith("-"):
            continue
        non_flags.append(a)

    target = non_flags[0] if non_flags else ""
    if not target:
        print("Error: Target module is required for runtime feedback.")
        print("Usage: cade feedback <module> --symptom \"...\" [--workspace path]")
        return 1

    resolved_module = target if target.endswith(".m") else f"{target}.m"

    if list_mode:
        ctx = load_context(ws, resolved_module)
        if not ctx or not ctx.runtime_feedback:
            print(f"No runtime feedback recorded for module {resolved_module}.")
            return 0
        print(f"Recorded Runtime Feedback for {resolved_module} ({len(ctx.runtime_feedback)} observation(s)):")
        for fb in ctx.runtime_feedback:
            fb_time = fb.get("timestamp", "")[:19].replace("T", " ")
            fb_id = fb.get("feedback_id", "")
            b_tag = f" [Build Ref: {fb.get('build_id')}]" if fb.get("build_id") else ""
            print(f"  • [{fb_id}] {fb_time}{b_tag}")
            print(f"    Symptom:  {fb.get('symptom', '')}")
            if fb.get("expected"):
                print(f"    Expected: {fb.get('expected')}")
            if fb.get("actual"):
                print(f"    Actual:   {fb.get('actual')}")
            if fb.get("steps"):
                print(f"    Steps:    {'; '.join(fb.get('steps'))}")
        return 0

    if not symptom:
        print("Error: --symptom is required when recording runtime feedback.")
        print("Usage: cade feedback <module> --symptom \"...\" [--workspace path]")
        return 1

    steps = [s.strip() for s in steps_raw.split(";") if s.strip()] if steps_raw else []

    res_ctx = record_runtime_feedback(
        workspace_root=ws,
        target_module=resolved_module,
        symptom=symptom,
        steps=steps,
        expected=expected,
        actual=actual,
        build_id=build_id,
        reporter=reporter,
    )

    if not res_ctx:
        print(f"Failed to record runtime feedback for {resolved_module} (workspace inaccessible or invalid input).")
        return 1

    last_fb = res_ctx.last_feedback or {}
    fb_id = last_fb.get("feedback_id", "")
    print(f"[ok] Runtime feedback recorded for {resolved_module}:")
    print(f"  Feedback ID: {fb_id}")
    print(f"  Symptom:     {symptom}")
    if actual:
        print(f"  Actual:      {actual}")
    if expected:
        print(f"  Expected:    {expected}")
    if build_id:
        known_bids = {b.get("build_id") for b in res_ctx.build_results if b.get("build_id")}
        if build_id in known_bids:
            print(f"  Build Ref:   {build_id} (recorded CADE build record)")
        else:
            print(f"  Build Ref:   {build_id} (unverified reference: not found in local build records)")
    print(f"  Task ID:     {res_ctx.task_id}")
    print("  Note: Recorded purely as subjective developer observation, distinct from L0 build evidence.")
    return 0


# ─── Docs ─────────────────────────────────────────────────────────


def cmd_docs(args):
    from docgen import generate_all

    ws = _get_ws(args)
    output = None
    if "-o" in args:
        idx = args.index("-o")
        output = args[idx + 1] if idx + 1 < len(args) else None
    result = generate_all(ws, output)
    return _print_result(result)


# ─── Runtime View ─────────────────────────────────────────────────


def cmd_runtime_view(args):
    from build import create_runtime_view

    ws = _get_ws(args)
    result = create_runtime_view(Path(ws))
    return _print_result(result)


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


def cmd_plan(args):
    """Generate a development plan from intent."""
    if len(args) < 3:
        print("Usage: cade plan <type> <name> <module> [--fw framework]")
        return
    from intent import Intent, IntentType, plan
    # Map user-friendly names to IntentType values
    type_map = {
        "command": IntentType.CREATE_COMMAND,
        "cmd": IntentType.CREATE_COMMAND,
        "feature": IntentType.CREATE_FEATURE,
        "dialog": IntentType.CREATE_DIALOG,
        "workbench": IntentType.CREATE_WORKBENCH,
        "wb": IntentType.CREATE_WORKBENCH,
        "interface": IntentType.CREATE_INTERFACE,
        "component": IntentType.CREATE_COMPONENT,
        "extension": IntentType.CREATE_EXTENSION,
        "cmd_dialog": IntentType.CREATE_COMMAND_WITH_DIALOG,
        "feature_factory": IntentType.CREATE_FEATURE_WITH_FACTORY,
    }
    intent_type = type_map.get(args[0].lower(), None)
    if not intent_type:
        print(f"Unknown type: {args[0]}. Valid: {', '.join(type_map.keys())}")
        return
    flags = _get_flags(args)
    i = Intent(
        type=intent_type,
        name=args[1],
        module=args[2],
        framework=flags.get("--fw", "MyFramework"),
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


def cmd_health(args):
    """Diagnose workspace and environment health.
    Usage: cade health [workspace]
    """
    from build import validate_workspace, diagnose_environment
    ws = _get_ws(args)

    print("=== Environment ===")
    diag = diagnose_environment()
    for c in diag["checks"]:
        print(f"  [{'OK' if c['ok'] else 'FAIL'}] {c['name']}")

    if ws:
        print(f"\n=== Workspace: {ws} ===")
        health = validate_workspace(Path(ws))
        for i in health["issues"]:
            print(f"  [FAIL] {i}")
        for w in health.get("warnings", []):
            print(f"  [WARN] {w}")
        if not health["issues"]:
            print("  [OK] Workspace structure valid")

    if diag["issues"]:
        print(f"\nIssues: {len(diag['issues'])}")


def cmd_version():
    from env import CAAEnvironment

    env = CAAEnvironment()
    env.load_config()
    info = env.get_info()
    print(f"CADE v3.2.1 — CATIA CAA Development Kernel")
    print(f"  CATIA: {info.get('catia_version', 'unknown')}")
    print(f"  Install: {info.get('catia_install', 'unknown')}")
    print(f"  Architecture: {info.get('caa_platform', 'unknown')}")
    if "caa_version_label" in info:
        print(f"  Detected: {info['caa_version_label']}")


def cmd_test(args):
    import subprocess

    quick = "--quick" in args
    # tests/ lives at the skill root (sibling of skills/), not under skills/.
    runner = SKILL_ROOT.parent / "tests" / "test_master.py"
    if runner.exists():
        cmd = [sys.executable, str(runner)]
        if quick:
            cmd.append("--quick")
        # P3-005 fix: propagate return code
        result = subprocess.run(cmd)
        return result.returncode
    else:
        print("Test runner not found")
        return 1


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
    ws = _parse_flag(args, "--workspace", "-w")
    if ws:
        return ws
    skip_values = {"-m", "--module", "-j", "--threads", "--task-id", "--task", "-o", "--output", "--deps", "--graph"}
    skip_next = False
    for a in args:
        if skip_next:
            skip_next = False
            continue
        if a in skip_values:
            skip_next = True
            continue
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


def _print_result(result) -> int:
    """Pretty-print result and return exit code (P2-003 fix)."""
    if isinstance(result, dict):
        import json
        # Build results carry the full raw mkmk log in "output" (needed by
        # the repair loop's Python API). On the CLI that log is noise — the
        # structured errors/warnings are already parsed — so swap it for a
        # tail + the on-disk build.log path. Only dicts that actually look
        # like build results (have "output") are touched.
        if "output" in result:
            from build import slim_result_for_cli
            result = slim_result_for_cli(result)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
        # Derive exit code from status
        status = result.get("status", "")
        if status in ("success", "passed", "ok", "applied", "rolled_back", "no_issues"):
            return 0
        if status == "preview" or status == "dry_run":
            return 0
        return 1
    else:
        print(result)
        return 0


def print_help():
    print(__doc__)


if __name__ == "__main__":
    main()
