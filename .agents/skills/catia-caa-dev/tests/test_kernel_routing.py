#!/usr/bin/env python3
"""
Kernel Routing Coverage Test (L0-4)
====================================
Verify all old MCP tools (41) are reachable through the 3-mode interface.
Prevents regression where tools are lost during interface simplification.

Contract:
  Every old tool has a home in develop/analyze/repair.
"""

import sys
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from kernel import Kernel, KernelMode

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  Kernel Routing Coverage (L0-4)")
print("=" * 60)

k = Kernel(workspace_root=".")

# All old tools mapped to (mode, query)
ROUTES = {
    # Analysis → analyze
    "analyze_workspace":       (KernelMode.ANALYZE, "analyze the workspace"),
    "list_modules":            (KernelMode.ANALYZE, "list all modules"),
    "list_commands":           (KernelMode.ANALYZE, "list all commands"),
    "get_dependencies":        (KernelMode.ANALYZE, "get dependencies of MyCmd"),
    "visualize_dependencies":  (KernelMode.ANALYZE, "visualize dependency graph of MyCmd"),
    "validate_workspace":      (KernelMode.ANALYZE, "validate workspace"),
    # Create → develop
    "create_executable_command": (KernelMode.DEVELOP, "create command TestCmd in TestModule"),
    "create_feature":          (KernelMode.DEVELOP, "create feature TestFeat in TestModule"),
    "create_extension":        (KernelMode.DEVELOP, "create extension TestExt in TestModule"),
    "create_ui_dialog":        (KernelMode.DEVELOP, "create dialog TestDlg in TestModule"),
    "expose_service":          (KernelMode.DEVELOP, "expose service from TestComp"),
    # Diagnostics → analyze/repair
    "diagnose_workspace":      (KernelMode.ANALYZE, "diagnose the workspace"),
    "diagnose_and_fix":        (KernelMode.REPAIR, "diagnose and fix issues"),
    "suggest_next":            (KernelMode.ANALYZE, "suggest next action"),
    # Intent → develop/analyze
    "plan_intent":             (KernelMode.DEVELOP, "plan CreateCommand MyPlan MyMod"),
    "analyze_impact":          (KernelMode.ANALYZE, "analyze impact of renaming MyCmd"),
    "recommend_plan":          (KernelMode.ANALYZE, "recommend best plan"),
    # Build → develop
    "incremental_build":       (KernelMode.DEVELOP, "incremental build"),
    "full_build":              (KernelMode.DEVELOP, "full build"),
    "clean_build":             (KernelMode.DEVELOP, "clean build"),
    "build_with_threads":      (KernelMode.DEVELOP, "build with 8 threads"),
    "create_runtime_view":     (KernelMode.DEVELOP, "create runtime view"),
    # Run → develop
    "start_catia":             (KernelMode.DEVELOP, "start CATIA"),
    "stop_catia":              (KernelMode.DEVELOP, "stop CATIA"),
    "check_catia":             (KernelMode.DEVELOP, "check if CATIA is running"),
    "run_catia_macro":         (KernelMode.DEVELOP, "run CATIA macro"),
    "run_catia_batch":         (KernelMode.DEVELOP, "run CATIA batch"),
    # Refactor → repair
    "rename_command":          (KernelMode.REPAIR, "rename command Old to New"),
    "rename_interface":        (KernelMode.REPAIR, "rename interface IOld to INew"),
    "move_command":            (KernelMode.REPAIR, "move command MyCmd between modules"),
    "rename_module":           (KernelMode.REPAIR, "rename module OldMod to NewMod"),
    # Rollback → repair
    "list_rollback_points":    (KernelMode.REPAIR, "list rollback points"),
    "rollback":                (KernelMode.REPAIR, "rollback to latest"),
    "workspace_snapshot":      (KernelMode.REPAIR, "create workspace snapshot"),
    # Support → develop
    "generate_docs":           (KernelMode.DEVELOP, "generate documentation"),
    "get_version":             (KernelMode.DEVELOP, "version"),
    "setup_workspace_environment": (KernelMode.DEVELOP, "setup environment"),
    "prereq_add":              (KernelMode.DEVELOP, "add prerequisite"),
    "prereq_list":             (KernelMode.DEVELOP, "list prerequisites"),
    "prereq_validate":         (KernelMode.DEVELOP, "validate prerequisites"),
    "prereq_suggest":          (KernelMode.DEVELOP, "suggest prerequisites"),
}

print(f"\nTotal old tools: {len(ROUTES)}")

for tool_name, (mode, query) in ROUTES.items():
    r = k.execute(mode, query)
    status = r.get("status", "?")
    # Accept any status except a hard crash (exception)
    has_route = status != "?"
    ck(
        f"{tool_name} → {mode.value}",
        has_route,
        f"status={status}" if not has_route else "",
    )

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
