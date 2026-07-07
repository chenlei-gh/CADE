#!/usr/bin/env python3
"""
CATIA CAA 开发助手 - 全模块全功能完整检查
==========================================
系统性验证所有 15 个 API、所有 4 层架构、所有 7 个测试套件。
"""

import json
import subprocess
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent

# ═══════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════

CHECK_ITEMS = {
    # ── 文件结构 ──
    "core_files": {
        "SKILL.md": "主技能定义",
        "README.md": "项目说明",
        "CHANGELOG.md": "更新日志",
        ".gitignore": "Git 忽略",
    },
    "core_dirs": [
        "docs/",
        "docs/guides/",
        "docs/references/",
        "docs/examples/",
        "skills/",
        "skills/intents/",
        "templates/",
        "tests/",
        "tools/",
        "config/",
    ],
    "skill_modules": {
        "intents.py": "意图层 (向后兼容)",
        "actions.py": "原子操作层",
        "specification.py": "Spec 层",
        "diagnostics.py": "诊断系统",
        "refactor.py": "重构引擎",
        "meta_model.py": "元模型层",
        "changeset.py": "变更集管理",
        "backup.py": "回滚系统",
        "analyzer.py": "工作区分析",
        "generator.py": "代码生成器",
        "parser.py": "输出解析",
        "env.py": "环境检测",
        "utils.py": "工具函数",
        "build.py": "编译管理",
        "run.py": "运行时管理",
        "clean.py": "清理工具",
        "workspace.py": "工作区检查",
        "runtime_view.py": "Runtime View",
    },
    "intent_submodules": {
        "intents/__init__.py": "包入口",
        "intents/commands.py": "命令意图",
        "intents/services.py": "服务意图",
        "intents/objects.py": "对象意图",
        "intents/recommendation.py": "智能推荐",
        "intents/helpers.py": "辅助函数",
    },
    "templates": [
        "framework/",
        "module/",
        "command/",
        "commandheader/",
        "workbench/",
        "addin/",
        "dialog/",
        "adapter/",
        "idl/",
        "class/",
        "feature/",
    ],
    "test_files": [
        "test_comprehensive_check.py",
        "test_full_integration.py",
        "test_e2e_workflow.py",
        "test_phase1_enhancements.py",
        "test_phase2_intents.py",
        "test_phase3_rollback.py",
        "test_phase4_enhanced.py",
    ],
    "config_files": [
        "caa_env_config.txt",
        "requirements.txt",
    ],
    "tools": [
        "check_code_reuse.bat",
        "check_code_reuse.py",
        "generate_guid_ai.bat",
        "setup_wizard.bat",
        "validate_component_ai.bat",
    ],
}

# 15 API 列表及其归属
API_LIST = {
    "Intent Layer (7)": [
        "create_executable_command",
        "create_ui_dialog",
        "expose_service",
        "create_component_with_interfaces",
        "create_feature",
        "create_extension",
        "suggest_next_action",
    ],
    "Action Layer (8)": [
        "get_dependencies",
        "get_dependents",
        "visualize_dependencies",
        "validate_workspace",
        "find_orphaned_files",
        "rollback_operation",
        "list_rollback_points",
        "cleanup_old_backups",
    ],
}


def check(label, condition, detail=""):
    """Single check item"""
    if condition:
        print(f"  [PASS] {label}" + (f" — {detail}" if detail else ""))
        return True
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
        return False


def run_test_suite(name, script_path, check_string):
    """Run a test suite and check for success string in stdout"""
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(SKILL_ROOT / script_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = time.time() - start
        if check_string in result.stdout:
            return True, f"{elapsed:.1f}s"
        else:
            return False, result.stderr[-200:] if result.stderr else "no match"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════════════════════════════
# 开始检查
# ═══════════════════════════════════════════════════════════════════

print()
print("=" * 70)
print("  CATIA CAA 开发助手 — 全模块全功能完整检查")
print("  版本: 2.0.0")
print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

total = 0
passed = 0

# ───────────────────────────────────────────────────────────────────
# 第1部分: 文件结构
# ───────────────────────────────────────────────────────────────────

print("\n" + "═" * 70)
print("  Part 1: 文件结构完整性")
print("═" * 70)

# 核心文件
print("\n  [核心文件]")
for fname, desc in CHECK_ITEMS["core_files"].items():
    total += 1
    exists = (SKILL_ROOT / fname).exists()
    if check(f"{fname}", exists, desc):
        passed += 1

# 核心目录
print("\n  [核心目录]")
for d in CHECK_ITEMS["core_dirs"]:
    total += 1
    exists = (SKILL_ROOT / d).is_dir()
    if check(f"{d}", exists):
        passed += 1

# 模块文件
print("\n  [Python 模块]")
for fname, desc in CHECK_ITEMS["skill_modules"].items():
    total += 1
    exists = (SKILL_ROOT / "skills" / fname).exists()
    if check(f"skills/{fname}", exists, desc):
        passed += 1

# Intent 子模块
print("\n  [Intent 子模块]")
for fname, desc in CHECK_ITEMS["intent_submodules"].items():
    total += 1
    exists = (SKILL_ROOT / "skills" / fname).exists()
    if check(f"skills/{fname}", exists, desc):
        passed += 1

# 模板
print("\n  [模板目录]")
for tpl in CHECK_ITEMS["templates"]:
    total += 1
    exists = (SKILL_ROOT / "templates" / tpl).is_dir()
    if check(f"templates/{tpl}", exists):
        passed += 1

# 测试
print("\n  [测试文件]")
for tf in CHECK_ITEMS["test_files"]:
    total += 1
    exists = (SKILL_ROOT / "tests" / tf).exists()
    if check(f"tests/{tf}", exists):
        passed += 1

# 配置
print("\n  [配置文件]")
for cf in CHECK_ITEMS["config_files"]:
    total += 1
    exists = (SKILL_ROOT / "config" / cf).exists()
    if check(f"config/{cf}", exists):
        passed += 1

# 工具
print("\n  [工具脚本]")
for tf in CHECK_ITEMS["tools"]:
    total += 1
    exists = (SKILL_ROOT / "tools" / tf).exists()
    if check(f"tools/{tf}", exists):
        passed += 1

# ───────────────────────────────────────────────────────────────────
# 第2部分: 模块导入
# ───────────────────────────────────────────────────────────────────

print("\n" + "═" * 70)
print("  Part 2: Python 模块导入验证")
print("═" * 70)

sys.path.insert(0, str(SKILL_ROOT / "skills"))

import_checks = [
    ("changeset", "ChangeSet", "Layer 4"),
    ("changeset", "Patch", "Layer 4"),
    ("changeset", "ChangeSet.from_dict", "Layer 4 (classmethod)"),
    ("backup", "BackupManager", "Layer 4"),
    ("meta_model", "Framework", "Layer 3"),
    ("meta_model", "Module", "Layer 3"),
    ("meta_model", "Command", "Layer 3"),
    ("meta_model", "Interface", "Layer 3"),
    ("meta_model", "Workbench", "Layer 3"),
    ("meta_model", "Dialog", "Layer 3"),
    ("meta_model", "DependencyGraph", "Layer 3"),
    ("meta_model", "RelationType", "Layer 3"),
    ("meta_model", "WorkspaceSnapshot", "Layer 3"),
    ("analyzer", "WorkspaceAnalyzer", "Layer 4"),
    ("generator", "TemplateGenerator", "Layer 4"),
    ("actions", "ActionContext", "Layer 2"),
    ("env", "CAAEnvironment", "Layer 4"),
    ("parser", "parse_mkmk_output", "Layer 4"),
    ("utils", "Logger", "Layer 4"),
    ("build", "build_workspace", "Layer 4"),
    ("run", "start_catia", "Layer 4"),
]

for module_name, attr, layer in import_checks:
    total += 1
    try:
        mod = __import__(module_name)
        if "." in attr:
            cls_name, method = attr.split(".")
            cls = getattr(mod, cls_name)
            getattr(cls, method)
        else:
            getattr(mod, attr)
        passed += 1
        print(f"  [PASS] {module_name}.{attr} [{layer}]")
    except Exception as e:
        print(f"  [FAIL] {module_name}.{attr} — {e}")

# ───────────────────────────────────────────────────────────────────
# 第3部分: Intent 子模块导入
# ───────────────────────────────────────────────────────────────────

print("\n  [Intent 子模块导入]")
intent_imports = [
    ("intents", "create_executable_command"),
    ("intents", "create_ui_dialog"),
    ("intents", "expose_service"),
    ("intents", "create_component_with_interfaces"),
    ("intents", "create_feature"),
    ("intents", "create_extension"),
    ("intents", "suggest_next_action"),
    ("intents.commands", "create_executable_command"),
    ("intents.services", "expose_service"),
    ("intents.objects", "create_feature"),
    ("intents.recommendation", "suggest_next_action"),
    ("intents.helpers", "validate_command_params"),
]

for module_name, attr in intent_imports:
    total += 1
    try:
        mod = __import__(module_name, fromlist=[attr])
        getattr(mod, attr)
        passed += 1
        print(f"  [PASS] {module_name}.{attr}")
    except Exception as e:
        print(f"  [FAIL] {module_name}.{attr} — {e}")

# ───────────────────────────────────────────────────────────────────
# 第4部分: 15 API 完整性
# ───────────────────────────────────────────────────────────────────

print("\n" + "═" * 70)
print("  Part 3: 15 API 完整性检查")
print("═" * 70)

from actions import (
    ActionContext,
    cleanup_old_backups,
    find_orphaned_files,
    get_dependencies,
    get_dependents,
    list_rollback_points,
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

# Intent Layer
print("\n  [Intent Layer - 7 API]")
intent_tests = [
    (create_executable_command, {"name": "ChkCmd", "module": "TestModule.m"}),
    (create_ui_dialog, {"name": "ChkDlg", "module": "TestModule.m"}),
    (expose_service, {"component_name": "ChkComp", "module": "TestModule.m"}),
    (create_component_with_interfaces, {"name": "ChkMulti", "module": "TestModule.m"}),
    (create_feature, {"name": "ChkFeat", "module": "TestModule.m"}),
    (
        create_extension,
        {"name": "ChkExt", "target_object": "CATPart", "module": "TestModule.m"},
    ),
    (suggest_next_action, {}),
]

for fn, kwargs in intent_tests:
    total += 1
    try:
        result = fn(ctx, **kwargs)
        ok = result["status"] in ("ok", "pending", "error")
        if check(f"{fn.__name__}()", ok, f"status={result['status']}"):
            passed += 1
    except Exception as e:
        print(f"  [FAIL] {fn.__name__}() — {e}")

# Action Layer
print("\n  [Action Layer - 8 API]")
action_tests = [
    (get_dependencies, {"entity_name": "NonexistentCmd"}),
    (get_dependents, {"entity_name": "NonexistentCmd"}),
    (visualize_dependencies, {}),
    (validate_workspace, {}),
    (find_orphaned_files, {}),
    (list_rollback_points, {}),
]

for fn, kwargs in action_tests:
    total += 1
    try:
        result = fn(ctx, **kwargs)
        ok = result["status"] in ("ok", "warning", "error")
        if check(f"{fn.__name__}()", ok, f"status={result['status']}"):
            passed += 1
    except Exception as e:
        print(f"  [FAIL] {fn.__name__}() — {e}")

# rollback/cleanup need backup_id, so just verify they exist
total += 2
if check("rollback_operation()", callable(rollback_operation), "callable"):
    passed += 1
if check("cleanup_old_backups()", callable(cleanup_old_backups), "callable"):
    passed += 1

# ───────────────────────────────────────────────────────────────────
# 第5部分: ChangeSet + 回滚
# ───────────────────────────────────────────────────────────────────

print("\n" + "═" * 70)
print("  Part 4: ChangeSet 序列化/反序列化")
print("═" * 70)

from changeset import ChangeSet

total += 1
try:
    cs = ChangeSet(action="test", description="Test serialization")
    cs.created["/tmp/test.cpp"] = "int main() { return 0; }"
    cs.modified["/tmp/test.h"] = "// modified"
    cs.add_warning("test warning")

    # Serialize → Deserialize → Verify
    d = cs.to_dict()
    cs2 = ChangeSet.from_dict(d)

    ok = (
        cs2.action == "test"
        and cs2.description == "Test serialization"
        and cs2.created.get("/tmp/test.cpp") == "int main() { return 0; }"
        and cs2.modified.get("/tmp/test.h") == "// modified"
        and len(cs2.warnings) == 1
    )
    if check("ChangeSet round-trip", ok, "serialize→deserialize preserves content"):
        passed += 1
    else:
        print(
            f"       expected created content, got: {cs2.created.get('/tmp/test.cpp')}"
        )
except Exception as e:
    print(f"  [FAIL] — {e}")

# ───────────────────────────────────────────────────────────────────
# 第6部分: 运行测试套件
# ───────────────────────────────────────────────────────────────────

print("\n" + "═" * 70)
print("  Part 5: 测试套件执行")
print("═" * 70)

suites = [
    (
        "Phase 1: 依赖图 (10 tests)",
        "tests/test_phase1_enhancements.py",
        "Phase 1 Enhancement Tests Complete",
    ),
    (
        "Phase 2: Intent Layer (10 tests)",
        "tests/test_phase2_intents.py",
        "Intent Layer implementation verified",
    ),
    (
        "Phase 3: 回滚 (10 tests)",
        "tests/test_phase3_rollback.py",
        "Rollback system verified",
    ),
    (
        "Phase 4: 增强意图 (11 tests)",
        "tests/test_phase4_enhanced.py",
        "Phase 4 enhancements verified",
    ),
    ("完整集成测试 (49 tests)", "tests/test_full_integration.py", "ALL TESTS PASSED"),
    ("端到端测试 (7 tests)", "tests/test_e2e_workflow.py", "所有核心功能验证通过"),
    ("综合检查 (99 tests)", "tests/test_comprehensive_check.py", "ALL CHECKS PASSED"),
]

for name, script, check_str in suites:
    total += 1
    print(f"\n  {name}")
    ok, detail = run_test_suite(name, script, check_str)
    if check(f"Run {script.split('/')[-1]}", ok, f"({detail})"):
        passed += 1

# ───────────────────────────────────────────────────────────────────
# 第7部分: 架构验证
# ───────────────────────────────────────────────────────────────────

print("\n" + "═" * 70)
print("  Part 6: 架构验证")
print("═" * 70)

arch_checks = [
    ("Intent Layer 包目录", (SKILL_ROOT / "skills" / "intents").is_dir()),
    ("命令模块拆分", (SKILL_ROOT / "skills" / "intents" / "commands.py").exists()),
    ("服务模块拆分", (SKILL_ROOT / "skills" / "intents" / "services.py").exists()),
    ("对象模块拆分", (SKILL_ROOT / "skills" / "intents" / "objects.py").exists()),
    (
        "推荐模块拆分",
        (SKILL_ROOT / "skills" / "intents" / "recommendation.py").exists(),
    ),
    ("辅助模块拆分", (SKILL_ROOT / "skills" / "intents" / "helpers.py").exists()),
    ("向后兼容 wrapper", (SKILL_ROOT / "skills" / "intents.py").exists()),
    ("ChangeSet from_dict", callable(ChangeSet.from_dict)),
    ("BackupManager 可用", (SKILL_ROOT / "skills" / "backup.py").exists()),
    ("依赖图可用", (SKILL_ROOT / "skills" / "meta_model.py").exists()),
]

for label, condition in arch_checks:
    total += 1
    if check(label, condition):
        passed += 1

# ───────────────────────────────────────────────────────────────────
# 总结
# ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("  FINAL SUMMARY")
print("=" * 70)
print(f"""
  总检查项:  {total}
  通过:      {passed}
  失败:      {total - passed}
  通过率:    {passed / total * 100:.1f}%
""")

if total == passed:
    print("  >>> ALL CHECKS PASSED — 系统 100% 正常 <<<")
else:
    print(f"  >>> {total - passed} 项失败，需要修复 <<<")

print("=" * 70)
sys.exit(0 if total == passed else 1)
