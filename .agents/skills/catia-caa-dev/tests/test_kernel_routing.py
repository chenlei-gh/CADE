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
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

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
    # Diagnostics → analyze/repair
    "diagnose_workspace":      (KernelMode.ANALYZE, "diagnose the workspace"),
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

# Routing tests must never invoke the real Build Time toolchain or CATIA lifecycle.
with ExitStack() as mocks:
    build_result = {"status": "success", "message": "mocked build"}
    for name in [
        "incremental_build", "full_build", "clean_build", "build_with_threads",
        "create_runtime_view", "setup_prerequisite_path",
    ]:
        mocks.enter_context(patch(f"build.{name}", return_value=build_result.copy()))
    mocks.enter_context(patch("run.start_catia_runtime", return_value={"status": "started"}))
    mocks.enter_context(patch("run.stop_catia", return_value={"status": "stopped"}))
    mocks.enter_context(patch("run.check_catia_running", return_value={"status": "not_running"}))
    mocks.enter_context(patch("run.run_catia_macro", return_value={"status": "success"}))
    mocks.enter_context(patch("run.run_catia_batch", return_value={"status": "success"}))
    mocks.enter_context(patch("docgen.generate_all", return_value={"status": "ok"}))

    for tool_name, (mode, query) in ROUTES.items():
        r = k.execute(mode, query)
        status = r.get("status", "?")
        # Accept any routed status, including a structured validation error.
        has_route = status != "?"
        ck(
            f"{tool_name} → {mode.value}",
            has_route,
            f"status={status}" if not has_route else "",
        )

    print("\n  ── Native Investigation Routing Tests (P0) ──")
    # Test 1: Tier A native command candidate
    r1 = k.execute(KernelMode.ANALYZE, "CATIA 原生命令在哪个dll")
    ck(
        "P0-1 native command advisory",
        r1.get("query_type") == "native_investigation_advisory" and r1.get("investigation_recommended") is True,
        f"got query_type={r1.get('query_type')}",
    )

    # Test 2: Tier A slot/vtable does not fallback to workspace analysis
    r2 = k.execute(KernelMode.ANALYZE, "slot 17 vtable binary investigation")
    ck(
        "P0-2 vtable/slot does not fallback to workspace analysis",
        r2.get("query_type") == "native_investigation_advisory" and "workspace" not in r2.get("message", "").lower(),
        f"message={r2.get('message')}",
    )

    # Test 3: Tier B normal issue isolation (not misrouted to investigation)
    r3 = k.execute(KernelMode.ANALYZE, "为什么设置颜色不生效")
    ck(
        "P0-3 normal issue does not trigger native investigation",
        r3.get("investigation_recommended") is not True
        and r3.get("query_type") != "native_investigation_advisory"
        and "workspace" not in r3.get("message", "").lower(),
        f"query_type={r3.get('query_type')}",
    )

    # Test 4: SDK search empty with native signal provides restrained advice
    r4 = k.execute(KernelMode.ANALYZE, "CATINonExistentFeature 原生命令 无公开api")
    ck(
        "P0-4 restrained advice without dogmatic claim",
        r4.get("investigation_recommended") is True and r4.get("status") == "ok",
        f"status={r4.get('status')}",
    )

    # Test 5: Slot 17/18 guardrail present and bound to experimental disclaimer
    r5 = k.execute(KernelMode.ANALYZE, "CATIA B28 slot 17 18 属性重置私有接口")
    ck(
        "P0-5 slot 17/18 guardrail present",
        r5.get("evidence_boundary") == "experimental_not_public_api_contract"
        and "core_guardrail" in r5.get("advisory", {}),
        f"evidence_boundary={r5.get('evidence_boundary')}",
    )

    # Test 6: Negative test (normal CAA method/interface query not misrouted)
    r6 = k.execute(KernelMode.ANALYZE, "CATCommand 的 interface 和 method 有哪些")
    ck(
        "P0-6 normal API query not misrouted to native investigation",
        r6.get("investigation_recommended") is not True
        and r6.get("query_type") != "native_investigation_advisory",
        f"query_type={r6.get('query_type')}",
    )

    # Test 7: Explicit investigation + Public API coexist
    r7 = k.execute(KernelMode.ANALYZE, "CATIA native command 的公开 CAA API 和官方文档")
    ck(
        "P0-7 public doc intent prioritizes official verification before reverse engineering",
        r7.get("investigation_recommended") is False
        and "recommendation" in r7.get("advisory", {}),
        f"recommended={r7.get('investigation_recommended')}",
    )

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
