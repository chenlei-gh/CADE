#!/usr/bin/env python3
"""
CATIA CAA 开发技能 - 完整功能检查
===================================
全面验证所有功能、文档、测试和工作流

检查项：
1. 文件结构完整性
2. Python 模块导入
3. 测试套件执行
4. 工作区分析功能
5. 模板生成功能
6. 编译功能
7. 运行时功能
8. 文档链接有效性
9. 配置文件有效性
10. 工具脚本可用性
"""

import json
import os
import subprocess
import sys
from pathlib import Path


# 颜色输出
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_success(msg):
    print(f"[PASS] {msg}")


def print_error(msg):
    print(f"[FAIL] {msg}")


def print_warning(msg):
    print(f"[WARN] {msg}")


def print_info(msg):
    print(f"[INFO] {msg}")


def print_header(msg):
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}\n")


# 统计
stats = {"total": 0, "passed": 0, "failed": 0, "warnings": 0}


def check(description, test_func):
    """执行检查项"""
    stats["total"] += 1
    try:
        result = test_func()
        if result:
            stats["passed"] += 1
            print_success(description)
            return True
        else:
            stats["failed"] += 1
            print_error(description)
            return False
    except Exception as e:
        stats["failed"] += 1
        print_error(f"{description}: {str(e)}")
        return False


def warn(description, test_func):
    """执行警告级检查"""
    try:
        result = test_func()
        if not result:
            stats["warnings"] += 1
            print_warning(description)
            return False
        else:
            print_info(f"{description} - OK")
            return True
    except Exception as e:
        stats["warnings"] += 1
        print_warning(f"{description}: {str(e)}")
        return False


# 设置路径
SKILL_ROOT = Path(__file__).parent.parent  # 父目录的父目录才是根目录
sys.path.insert(0, str(SKILL_ROOT / "skills"))

print_header("CATIA CAA 开发技能 - 完整功能检查")
print(f"检查路径: {SKILL_ROOT}")
print(f"Python 版本: {sys.version.split()[0]}")

# ============================================================================
# 第一部分：文件结构检查
# ============================================================================

print_header("第一部分：文件结构检查")

# 1.1 核心文件
print("\n【核心文件】")
core_files = ["SKILL.md", "README.md", "CHANGELOG.md", ".gitignore"]

for file in core_files:
    check(f"核心文件: {file}", lambda f=file: (SKILL_ROOT / f).exists())

# 1.2 核心目录
print("\n【核心目录】")
core_dirs = [
    "docs",
    "docs/guides",
    "docs/references",
    "docs/examples",
    "skills",
    "templates",
    "tests",
    "tools",
    "config",
]

for dir in core_dirs:
    check(f"目录: {dir}/", lambda d=dir: (SKILL_ROOT / d).is_dir())

# 1.3 文档文件
print("\n【文档文件】")
doc_files = {
    "guides": [
        "AI_GUIDE.md",
        "GETTING_STARTED.md",
        "BUILD_RUN_TIME_USAGE_GUIDE.md",
        "DEPLOYMENT_GUIDE.md",
        "DICTIONARY_GUIDE.md",
        "TROUBLESHOOTING_FLOWCHART.md",
        "FAQ.md",
    ],
    "references": [
        "ARCHITECTURE.md",
        "CAA_REFERENCE.md",
        "CGM_REFERENCE.md",
        "COMMAND_QUICK_REFERENCE.md",
        "DIALOG_QUICK_REFERENCE.md",
        "QUICK_REFERENCE.md",
        "CHEAT_SHEET.md",
        "QUICK_DECISION_TREE.md",
    ],
    "examples": [
        "EXAMPLE_COMMAND.md",
        "EXAMPLE_DIALOG.md",
        "EXAMPLE_EXTENSION.md",
        "EXAMPLE_MULTI_INTERFACE.md",
        "EXAMPLE_CALCULATOR.md",
        "AI_WORKFLOW_EXAMPLES.md",
    ],
}

for category, files in doc_files.items():
    print(f"\n  {category.upper()}:")
    for file in files:
        check(
            f"  {file}",
            lambda f=file, c=category: (SKILL_ROOT / "docs" / c / f).exists(),
        )

# 1.4 Python 模块
print("\n【Python 模块】")
python_modules = [
    "actions.py",
    "analyzer.py",
    "changeset.py",
    "meta_model.py",
    "specification.py",
    "diagnostics.py",
    "refactor.py",
    "generator.py",
    "env.py",
    "parser.py",
    "utils.py",
    "build.py",
    "run.py",
    "clean.py",
    "workspace.py",
    "runtime_view.py",
]

for module in python_modules:
    check(f"模块: {module}", lambda m=module: (SKILL_ROOT / "skills" / m).exists())

# 1.5 测试文件
print("\n【测试文件】")
test_files = ["test_full_integration.py", "test_e2e_workflow.py"]

for test in test_files:
    check(f"测试: {test}", lambda t=test: (SKILL_ROOT / "tests" / t).exists())

# 1.6 配置文件
print("\n【配置文件】")
config_files = ["caa_env_config.txt", "requirements.txt"]

for config in config_files:
    check(f"配置: {config}", lambda c=config: (SKILL_ROOT / "config" / c).exists())

# ============================================================================
# 第二部分：Python 模块导入检查
# ============================================================================

print_header("第二部分：Python 模块导入检查")

modules_to_import = [
    ("env", "CAAEnvironment"),
    ("parser", "parse_mkmk_output"),
    ("utils", "Logger"),
    ("build", "build_workspace"),
    ("run", "start_catia"),
    ("clean", "clean_workspace"),
    ("workspace", "check_workspace"),
    ("runtime_view", "check_runtime_view"),
    ("specification", "CommandSpec"),
    ("diagnostics", "DiagnosticsEngine"),
    ("refactor", "rename_command"),
    ("generator", "TemplateGenerator"),
    ("meta_model", "Framework"),
    ("analyzer", "WorkspaceAnalyzer"),
    ("changeset", "ChangeSet"),
    ("actions", "ActionContext"),
]

for module_name, item_name in modules_to_import:

    def test_import(mn=module_name, in_=item_name):
        try:
            module = __import__(mn)
            return hasattr(module, in_)
        except ImportError:
            return False

    check(f"导入: {module_name}.{item_name}", test_import)

# ============================================================================
# 第三部分：单元测试执行
# ============================================================================

print_header("第三部分：单元测试执行")


def run_test_file(test_file):
    """运行测试文件"""
    try:
        result = subprocess.run(
            [sys.executable, str(SKILL_ROOT / "tests" / test_file)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(SKILL_ROOT),
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


check(
    "执行单元测试: test_full_integration.py",
    lambda: run_test_file("test_full_integration.py"),
)
check(
    "执行端到端测试: test_e2e_workflow.py",
    lambda: run_test_file("test_e2e_workflow.py"),
)

# ============================================================================
# 第四部分：核心功能检查
# ============================================================================

print_header("第四部分：核心功能检查")

print("\n【工作区分析】")
try:
    from pathlib import Path

    from analyzer import WorkspaceAnalyzer

    # 测试空工作区
    temp_ws = SKILL_ROOT / "temp_test_ws"
    temp_ws.mkdir(exist_ok=True)

    wa = WorkspaceAnalyzer(temp_ws)
    snapshot = wa.analyze()

    check("分析器初始化", lambda: wa is not None)
    check("生成快照", lambda: snapshot is not None)
    check("快照包含 frameworks", lambda: hasattr(snapshot, "frameworks"))

    # 清理
    import shutil

    if temp_ws.exists():
        shutil.rmtree(temp_ws)

except Exception as e:
    print_error(f"工作区分析检查失败: {str(e)}")

print("\n【模板生成】")
try:
    from generator import TemplateGenerator

    tg = TemplateGenerator()
    templates = tg.get_available_templates()

    check("模板生成器初始化", lambda: tg is not None)
    check("列出模板", lambda: len(templates) > 0)
    check("模板数量 >= 20", lambda: len(templates) >= 20)

except Exception as e:
    print_error(f"模板生成检查失败: {str(e)}")

print("\n【变更集管理】")
try:
    from changeset import ChangeSet

    cs = ChangeSet(action="test", description="Test changeset")
    preview = cs.preview()

    check("变更集创建", lambda: cs is not None)
    check("变更集预览", lambda: preview is not None)
    check("变更集序列化", lambda: cs.to_dict() is not None)

except Exception as e:
    print_error(f"变更集检查失败: {str(e)}")

# ============================================================================
# 第五部分：命令行工具检查
# ============================================================================

print_header("第五部分：命令行工具检查")

print("\n【编译工具】")


def check_build_help():
    try:
        result = subprocess.run(
            [sys.executable, str(SKILL_ROOT / "skills" / "build.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "usage" in result.stdout.lower()
    except:
        return False


check("build.py --help", check_build_help)

print("\n【运行时工具】")


def check_run_help():
    try:
        result = subprocess.run(
            [sys.executable, str(SKILL_ROOT / "skills" / "run.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "usage" in result.stdout.lower()
    except:
        return False


check("run.py --help", check_run_help)

print("\n【清理工具】")


def check_clean_help():
    try:
        result = subprocess.run(
            [sys.executable, str(SKILL_ROOT / "skills" / "clean.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "usage" in result.stdout.lower()
    except:
        return False


check("clean.py --help", check_clean_help)

# ============================================================================
# 第六部分：文档链接有效性检查
# ============================================================================

print_header("第六部分：文档链接有效性检查")


def check_doc_links(doc_file):
    """检查文档中的内部链接"""
    import re

    content = doc_file.read_text(encoding="utf-8")
    # 查找 markdown 链接
    links = re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", content)

    broken = []
    for text, link in links:
        if link.startswith("http"):
            continue  # 跳过外部链接
        if link.startswith("#"):
            continue  # 跳过锚点

        # 检查相对路径
        link_path = doc_file.parent / link
        if not link_path.exists():
            broken.append((text, link))

    return len(broken) == 0, broken


print("\n【核心文档链接】")
core_docs = ["README.md", "SKILL.md"]
for doc in core_docs:
    doc_path = SKILL_ROOT / doc
    if doc_path.exists():
        valid, broken = check_doc_links(doc_path)
        if valid:
            check(f"{doc} 链接有效", lambda: True)
        else:
            print_warning(f"{doc} 有 {len(broken)} 个失效链接")
            for text, link in broken[:3]:
                print(f"    - [{text}]({link})")

# ============================================================================
# 第七部分：模板完整性检查
# ============================================================================

print_header("第七部分：模板完整性检查")

template_types = [
    "framework",
    "module",
    "command",
    "commandheader",
    "workbench",
    "addin",
    "dialog",
    "adapter",
    "idl",
    "class",
    "feature",
]

templates_dir = SKILL_ROOT / "templates"
for ttype in template_types:
    check(f"模板: {ttype}/", lambda t=ttype: (templates_dir / t).is_dir())

# ============================================================================
# 第八部分：配置文件有效性检查
# ============================================================================

print_header("第八部分：配置文件有效性检查")

print("\n【环境配置】")
env_config = SKILL_ROOT / "config" / "caa_env_config.txt"
if env_config.exists():
    content = env_config.read_text()
    check("包含 CATIA_INSTALL", lambda: "CATIA_INSTALL" in content)
    check("包含 CATIA_VERSION", lambda: "CATIA_VERSION" in content)
else:
    print_error("环境配置文件不存在")

print("\n【Requirements】")
req_file = SKILL_ROOT / "config" / "requirements.txt"
warn("requirements.txt 存在", lambda: req_file.exists())

# ============================================================================
# 第九部分：工具脚本检查
# ============================================================================

print_header("第九部分：工具脚本检查")

tools_dir = SKILL_ROOT / "tools"
if tools_dir.exists():
    tool_files = list(tools_dir.glob("*"))
    print(f"发现 {len(tool_files)} 个工具文件")
    for tool in tool_files[:5]:
        print_info(f"  - {tool.name}")
else:
    print_error("tools/ 目录不存在")

# ============================================================================
# 测试总结
# ============================================================================

print_header("测试总结")

print(f"\n总计检查项: {stats['total']}")
print(f"[PASS] 通过: {stats['passed']}")
print(f"[FAIL] 失败: {stats['failed']}")
print(f"[WARN] 警告: {stats['warnings']}")

pass_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
print(f"\n通过率: {pass_rate:.1f}%")

if stats["failed"] == 0:
    print(f"\n>>> ALL CHECKS PASSED ({stats['total']}/{stats['total']}) <<<")
    sys.exit(0)
else:
    print(f"\n>>> {stats['failed']} CHECK(S) FAILED <<<")
    sys.exit(1)
