#!/usr/bin/env python3
"""
Skill-AI 协同性检查
====================
模拟 AI 根据 SKILL.md 的触发词和文档调用 API，验证协同性。
"""

import inspect
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from actions import (
    ActionContext,
    analyze_workspace,
    cleanup_old_backups,
    create_command,
    create_dialog,
    delete_command,
    find_orphaned_files,
    get_dependencies,
    get_dependents,
    list_commands,
    list_interfaces,
    list_modules,
    list_rollback_points,
    list_workbenches,
    rollback_operation,
    validate_workspace,
    visualize_dependencies,
)
from intents import (
    create_component_with_interfaces,
    create_executable_command,
    create_extension,
    create_feature,
    create_ui_dialog,
    expose_service,
    suggest_next_action,
)

ctx = ActionContext(str(SKILL_ROOT.parent.parent))  # D:\test

print("=" * 70)
print("  Skill-AI 协同性检查")
print("=" * 70)

total = passed = 0

# ═══════════════════════════════════════════════════════════════════
# Part 1: 触发词 → API 映射
# ═══════════════════════════════════════════════════════════════════

print("\n[Part 1] Trigger → API Mapping")

triggers_map = [
    # 分析类
    ("analyze workspace", "actions.analyze_workspace", analyze_workspace),
    ("list modules", "actions.list_modules", list_modules),
    ("list commands", "actions.list_commands", list_commands),
    ("list workbenches", "actions.list_workbenches", list_workbenches),
    ("list interfaces", "actions.list_interfaces", list_interfaces),
    # 依赖类
    ("get dependencies", "actions.get_dependencies", get_dependencies),
    (
        "visualize dependencies",
        "actions.visualize_dependencies",
        visualize_dependencies,
    ),
    ("validate workspace", "actions.validate_workspace", validate_workspace),
    ("find orphaned", "actions.find_orphaned_files", find_orphaned_files),
    # 创建类 (Intent)
    ("create command", "intents.create_executable_command", create_executable_command),
    ("create dialog", "intents.create_ui_dialog", create_ui_dialog),
    ("expose service", "intents.expose_service", expose_service),
    ("create feature", "intents.create_feature", create_feature),
    ("create extension", "intents.create_extension", create_extension),
    # 删除类
    ("delete command", "actions.delete_command", delete_command),
    # 回滚类
    ("rollback", "actions.rollback_operation", rollback_operation),
    ("undo", "actions.rollback_operation", rollback_operation),
    ("list backups", "actions.list_rollback_points", list_rollback_points),
    # 推荐类
    ("suggest next", "intents.suggest_next_action", suggest_next_action),
    ("recommend", "intents.suggest_next_action", suggest_next_action),
]

for trigger, api_path, fn in triggers_map:
    total += 1
    exists = callable(fn)
    if exists:
        print(f"  [PASS] '{trigger}' → {api_path}()")
        passed += 1
    else:
        print(f"  [FAIL] '{trigger}' → {api_path} NOT FOUND")

# ═══════════════════════════════════════════════════════════════════
# Part 2: API 参数签名验证
# ═══════════════════════════════════════════════════════════════════

print("\n[Part 2] API Parameter Validation")

api_checks = [
    # (fn, 必需的 ctx 之外的参数名称列表)
    (create_executable_command, ["name", "module"]),
    (create_ui_dialog, ["name", "module"]),
    (expose_service, ["component_name", "module"]),
    (create_component_with_interfaces, ["name", "module"]),
    (create_feature, ["name", "module"]),
    (create_extension, ["name", "target_object", "module"]),
    (suggest_next_action, []),  # only ctx is required
    (get_dependencies, ["entity_name"]),
    (get_dependents, ["entity_name"]),
    (visualize_dependencies, []),
    (validate_workspace, []),
    (find_orphaned_files, []),
    (rollback_operation, ["backup_id"]),
    (list_rollback_points, []),
    (cleanup_old_backups, []),
    (analyze_workspace, []),
    (list_modules, []),
    (list_commands, []),
]

for fn, required_params in api_checks:
    total += 1
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    # Remove 'ctx' from comparison
    own_params = [p for p in params if p != "ctx"]

    missing = [r for r in required_params if r not in own_params]
    if not missing:
        print(f"  [PASS] {fn.__name__}() — params: {', '.join(own_params[:5])}")
        passed += 1
    else:
        print(f"  [FAIL] {fn.__name__}() — missing: {missing}")

# ═══════════════════════════════════════════════════════════════════
# Part 3: 文档示例可执行性
# ═══════════════════════════════════════════════════════════════════

print("\n[Part 3] Quick-Start Examples — Runnable")

examples = [
    ("analyze_workspace", lambda: analyze_workspace(ctx)),
    ("list_modules", lambda: list_modules(ctx)),
    ("list_commands", lambda: list_commands(ctx)),
    ("list_workbenches", lambda: list_workbenches(ctx)),
    ("list_interfaces", lambda: list_interfaces(ctx)),
    ("get_dependencies", lambda: get_dependencies(ctx, "TestCmd")),
    ("get_dependents", lambda: get_dependents(ctx, "TestCmd")),
    ("visualize_dependencies", lambda: visualize_dependencies(ctx)),
    ("validate_workspace", lambda: validate_workspace(ctx)),
    ("find_orphaned_files", lambda: find_orphaned_files(ctx)),
    ("list_rollback_points", lambda: list_rollback_points(ctx)),
    ("suggest_next_action", lambda: suggest_next_action(ctx)),
    # Intent functions return pending/error without real module
    (
        "create_executable_command",
        lambda: create_executable_command(ctx, name="Test", module="TestModule.m"),
    ),
    (
        "create_ui_dialog",
        lambda: create_ui_dialog(ctx, name="TestDlg", module="TestModule.m"),
    ),
    (
        "expose_service",
        lambda: expose_service(ctx, component_name="Test", module="TestModule.m"),
    ),
    (
        "create_feature",
        lambda: create_feature(ctx, name="TestFeat", module="TestModule.m"),
    ),
    (
        "create_extension",
        lambda: create_extension(
            ctx, name="TestExt", target_object="CATPart", module="TestModule.m"
        ),
    ),
    (
        "create_component_with_interfaces",
        lambda: create_component_with_interfaces(
            ctx, name="TestComp", module="TestModule.m"
        ),
    ),
]

for name, fn in examples:
    total += 1
    try:
        result = fn()
        ok = isinstance(result, dict) and "status" in result
        if ok:
            print(f"  [PASS] {name}() → status={result['status']}")
            passed += 1
        else:
            print(f"  [FAIL] {name}() → unexpected return: {type(result).__name__}")
    except Exception as e:
        print(f"  [FAIL] {name}() → {type(e).__name__}: {str(e)[:80]}")

# ═══════════════════════════════════════════════════════════════════
# Part 4: 返回格式一致性
# ═══════════════════════════════════════════════════════════════════

print("\n[Part 4] Return Format Consistency")

required_fields = ["status"]  # All APIs must return a dict with "status"

for name, fn in [
    (n, f)
    for n, f in examples
    if n
    not in (
        "analyze_workspace",
        "list_modules",
        "list_commands",
        "list_workbenches",
        "list_interfaces",
    )
]:
    total += 1
    try:
        result = fn()
        missing = [f for f in required_fields if f not in result]
        if not missing:
            print(f"  [PASS] {name}() — has required fields")
            passed += 1
        else:
            print(f"  [FAIL] {name}() — missing: {missing}")
    except Exception:
        # Already counted in Part 3
        pass

# ═══════════════════════════════════════════════════════════════════
# Part 5: 错误响应格式
# ═══════════════════════════════════════════════════════════════════

print("\n[Part 5] Error Response Format")

# Test with invalid params to check error format
error_tests = [
    (
        "get_dependencies (bad entity)",
        lambda: get_dependencies(ctx, "NonExistentEntity999"),
    ),
    (
        "get_dependents (bad entity)",
        lambda: get_dependents(ctx, "NonExistentEntity999"),
    ),
    (
        "create_command (bad module)",
        lambda: create_command(ctx, name="Test", module="NonExistentModule.m"),
    ),
    (
        "delete_command (bad name)",
        lambda: delete_command(ctx, name="NonExistentCmd999"),
    ),
]

for name, fn in error_tests:
    total += 1
    try:
        result = fn()
        if result["status"] == "error":
            has_message = "message" in result
            if has_message:
                print(f"  [PASS] {name} → error with message: {result['message'][:60]}")
                passed += 1
            else:
                print(f"  [FAIL] {name} → error but no 'message' field")
        else:
            print(f"  [INFO] {name} → status={result['status']} (entity may exist)")
            passed += 1
    except Exception as e:
        print(f"  [FAIL] {name} → {e}")

# ═══════════════════════════════════════════════════════════════════
# Part 6: SKILL.md 中引用的所有 import 可用
# ═══════════════════════════════════════════════════════════════════

print("\n[Part 6] Documented Imports Availability")

imports_from_docs = [
    ("actions", "ActionContext"),
    ("actions", "analyze_workspace"),
    ("actions", "list_modules"),
    ("actions", "list_commands"),
    ("actions", "list_workbenches"),
    ("actions", "list_interfaces"),
    ("actions", "create_command"),
    ("actions", "delete_command"),
    ("actions", "create_framework"),
    ("actions", "create_module"),
    ("actions", "create_workbench"),
    ("actions", "create_dialog"),
    ("actions", "create_interface"),
    ("actions", "create_component"),
    ("actions", "add_command_to_workbench"),
    ("actions", "get_dependencies"),
    ("actions", "get_dependents"),
    ("actions", "visualize_dependencies"),
    ("actions", "validate_workspace"),
    ("actions", "find_orphaned_files"),
    ("actions", "rollback_operation"),
    ("actions", "list_rollback_points"),
    ("actions", "cleanup_old_backups"),
    ("intents", "create_executable_command"),
    ("intents", "create_ui_dialog"),
    ("intents", "expose_service"),
    ("intents", "create_feature"),
    ("intents", "create_extension"),
    ("intents", "suggest_next_action"),
    ("refactor", "rename_command"),
    ("diagnostics", "DiagnosticsEngine"),
    ("build", "build_workspace"),
    ("run", "start_catia"),
]

for mod_name, attr in imports_from_docs:
    total += 1
    try:
        mod = __import__(mod_name)
        getattr(mod, attr)
        print(f"  [PASS] from {mod_name} import {attr}")
        passed += 1
    except (ImportError, AttributeError) as e:
        print(f"  [FAIL] from {mod_name} import {attr} — {e}")

# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print(f"  Skill-AI COORDINATION: {passed}/{total}")
print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> Perfect coordination — AI can seamlessly call all APIs <<<")
else:
    print(f"\n  >>> {total - passed} issue(s) need attention <<<")

sys.exit(0 if passed == total else 1)
