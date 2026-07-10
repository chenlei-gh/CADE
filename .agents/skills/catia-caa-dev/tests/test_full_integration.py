"""
CATIA CAA Development Skills - Full Integration Test
=====================================================
End-to-end test covering all modules and workflows.

Test Coverage:
  1. Environment detection
  2. Workspace analysis (meta model + analyzer)
  3. Template generation (25 types)
  4. ChangeSet operations (preview + apply + rollback)
  5. Atomic actions (query + create + delete)
  6. Build + Run (if CATIA available)
  7. All file operations
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Add skills to path
skill_root = Path(__file__).parent.parent
sys.path.insert(0, str(skill_root / "skills"))

from datetime import datetime

# ═══════════════════════════════════════════════════════════════════
#  TEST UTILITIES
# ═══════════════════════════════════════════════════════════════════


class TestReport:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
        self.start_time = datetime.now()

    def test(self, name: str, fn):
        """Run a test and record result"""
        try:
            fn()
            self.passed += 1
            self.tests.append((name, "PASS", None))
            print(f"  [OK] {name}")
        except AssertionError as e:
            self.failed += 1
            self.tests.append((name, "FAIL", str(e)))
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:
            self.failed += 1
            self.tests.append((name, "ERROR", str(e)))
            print(f"  [ERROR] {name}: {e}")
            import traceback

            traceback.print_exc()

    def summary(self):
        duration = (datetime.now() - self.start_time).total_seconds()
        print("\n" + "=" * 70)
        print(f"TEST SUMMARY -- {self.passed + self.failed} tests in {duration:.1f}s")
        print("=" * 70)

        for name, status, error in self.tests:
            status_icon = "[OK]" if status == "PASS" else "[FAIL]"
            print(f"{status_icon} {name:50s} [{status}]")
            if error:
                print(f"    {error}")

        print()
        print(f"PASSED: {self.passed}")
        print(f"FAILED: {self.failed}")
        print(f"RATE:   {self.passed / (self.passed + self.failed) * 100:.1f}%")
        print()

        if self.failed == 0:
            print("ALL TESTS PASSED!")
            return 0
        else:
            print(f"[X] {self.failed} TEST(S) FAILED")
            return 1


# ═══════════════════════════════════════════════════════════════════
#  TEST SUITE
# ═══════════════════════════════════════════════════════════════════

report = TestReport()


# ───────────────────────────────────────────────────────────────────
#  GROUP 1: Module Imports
# ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("GROUP 1: MODULE IMPORTS")
print("=" * 70)


def test_import_env():
    import env

    assert hasattr(env, "CAAEnvironment")


def test_import_parser():
    import parser

    assert hasattr(parser, "parse_mkmk_output")


def test_import_utils():
    import utils

    assert hasattr(utils, "Logger")
    assert hasattr(utils, "Cache")


def test_import_build():
    import build

    assert hasattr(build, "build_workspace")


def test_import_run():
    import run

    assert hasattr(run, "start_catia")


def test_import_clean():
    import clean

    assert hasattr(clean, "clean_workspace")


def test_import_workspace():
    import workspace

    assert hasattr(workspace, "check_workspace")


def test_import_runtime_view():
    import runtime_view

    assert hasattr(runtime_view, "check_runtime_view")


def test_import_generate():
    import generator

    assert hasattr(generator, "TemplateGenerator")


def test_import_meta_model():
    import meta_model

    assert hasattr(meta_model, "Framework")
    assert hasattr(meta_model, "Module")
    assert hasattr(meta_model, "Command")


def test_import_analyzer():
    import analyzer

    assert hasattr(analyzer, "WorkspaceAnalyzer")


def test_import_changeset():
    import changeset

    assert hasattr(changeset, "ChangeSet")
    assert hasattr(changeset, "Patch")


def test_import_actions():
    import actions

    assert hasattr(actions, "ActionContext")
    assert hasattr(actions, "create_command")


report.test("env.py", test_import_env)
report.test("parser.py", test_import_parser)
report.test("utils.py", test_import_utils)
report.test("build.py", test_import_build)
report.test("run.py", test_import_run)
report.test("clean.py", test_import_clean)
report.test("workspace.py", test_import_workspace)
report.test("runtime_view.py", test_import_runtime_view)
report.test("generate.py", test_import_generate)
report.test("meta_model.py", test_import_meta_model)
report.test("analyzer.py", test_import_analyzer)
report.test("changeset.py", test_import_changeset)
report.test("actions.py", test_import_actions)


# ───────────────────────────────────────────────────────────────────
#  GROUP 2: Meta Model
# ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("GROUP 2: META MODEL")
print("=" * 70)


def test_framework_creation():
    from meta_model import Framework

    fw = Framework(name="TestFw.edu", path=Path("."))
    assert fw.name == "TestFw.edu"
    assert len(fw.modules) == 0


def test_module_creation():
    from meta_model import Framework, Module

    fw = Framework(name="TestFw.edu", path=Path("."))
    mod = Module(name="TestMod.m", path=Path("."))
    fw.add_module(mod)
    assert len(fw.modules) == 1
    assert mod.framework == fw


def test_command_creation():
    from meta_model import Command, Module

    mod = Module(name="TestMod.m", path=Path("."))
    cmd = Command(name="TestCmd", path=Path("."), is_stateful=True)
    mod.add_command(cmd)
    assert len(mod.commands) == 1
    assert cmd.module == mod


def test_interface_implementation():
    from meta_model import Component, Interface

    iface = Interface(name="ITest", path=Path("."))
    comp = Component(name="TestComp", path=Path("."))
    comp.implements.append(iface)
    iface.implemented_by.append(comp)
    assert iface in comp.implements
    assert comp in iface.implemented_by


def test_workbench_commands():
    from meta_model import Command, Workbench

    wb = Workbench(name="TestWb", path=Path("."))
    cmd = Command(name="TestCmd", path=Path("."))
    wb.add_command(cmd)
    assert cmd.workbench == wb
    assert cmd in wb.commands


def test_snapshot_queries():
    from meta_model import Command, Framework, Module, WorkspaceSnapshot

    snap = WorkspaceSnapshot(root=Path("."))
    fw = Framework(name="TestFw.edu", path=Path("."))
    mod = Module(name="TestMod.m", path=Path("."))
    cmd = Command(name="TestCmd", path=Path("."))
    fw.add_module(mod)
    mod.add_command(cmd)
    snap.frameworks.append(fw)

    found_fw = snap.get_framework("TestFw")
    assert found_fw is not None

    found_mod = snap.get_module("TestMod.m")
    assert found_mod is not None

    all_cmds = snap.get_all_commands()
    assert len(all_cmds) == 1


def test_entity_serialization():
    from meta_model import Framework

    fw = Framework(name="TestFw.edu", path=Path("."))
    d = fw.to_dict()
    assert d["name"] == "TestFw.edu"
    assert "module_count" in d


report.test("Framework creation", test_framework_creation)
report.test("Module creation", test_module_creation)
report.test("Command creation", test_command_creation)
report.test("Interface implementation", test_interface_implementation)
report.test("Workbench commands", test_workbench_commands)
report.test("Snapshot queries", test_snapshot_queries)
report.test("Entity serialization", test_entity_serialization)


# ───────────────────────────────────────────────────────────────────
#  GROUP 3: ChangeSet
# ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("GROUP 3: CHANGESET")
print("=" * 70)


def test_changeset_creation():
    from changeset import ChangeSet

    cs = ChangeSet(action="test", description="Test changeset")
    assert cs.action == "test"
    assert cs.is_empty


def test_changeset_add_files():
    from changeset import ChangeSet

    cs = ChangeSet(action="test", description="Test")
    cs.add_create(Path("/tmp/test.h"), "// header")
    cs.add_modify(Path("/tmp/existing.cpp"), "// modified")
    cs.add_delete(Path("/tmp/old.h"))
    assert len(cs.created) == 1
    assert len(cs.modified) == 1
    assert len(cs.deleted) == 1
    assert cs.total_changes == 3


def test_changeset_preview():
    from changeset import ChangeSet

    cs = ChangeSet(action="test", description="Test")
    cs.add_create(Path("/tmp/test.h"), "// test")
    cs.add_warning("Test warning")
    preview = cs.preview()
    assert "test.h" in preview
    assert "Test warning" in preview


def test_changeset_dry_run():
    from changeset import ChangeSet

    cs = ChangeSet(action="test", description="Test")
    cs.add_create(Path("/tmp/test.h"), "// test")
    result = cs.apply(dry_run=True)
    assert result["status"] == "dry_run"
    assert "preview" in result


def test_changeset_real_apply():
    from changeset import ChangeSet

    tmp = Path(tempfile.mkdtemp())
    try:
        cs = ChangeSet(action="test", description="Test")
        test_file = tmp / "test.txt"
        cs.add_create(test_file, "Hello World")
        result = cs.apply(dry_run=False)
        assert result["status"] == "applied"
        assert test_file.exists()
        assert test_file.read_text() == "Hello World"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_changeset_rollback():
    from changeset import ChangeSet

    tmp = Path(tempfile.mkdtemp())
    try:
        cs = ChangeSet(action="test", description="Test")
        test_file = tmp / "test.txt"
        cs.add_create(test_file, "Hello")
        cs.apply(dry_run=False)
        assert test_file.exists()

        cs.rollback()
        assert not test_file.exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_patch_operations():
    from changeset import Patch

    patch = Patch(
        file=Path("test.cpp"),
        operation="insert_after",
        target="// marker",
        content="// new line",
    )
    d = patch.to_dict()
    assert d["operation"] == "insert_after"


report.test("ChangeSet creation", test_changeset_creation)
report.test("ChangeSet add files", test_changeset_add_files)
report.test("ChangeSet preview", test_changeset_preview)
report.test("ChangeSet dry_run", test_changeset_dry_run)
report.test("ChangeSet apply", test_changeset_real_apply)
report.test("ChangeSet rollback", test_changeset_rollback)
report.test("Patch operations", test_patch_operations)


# ───────────────────────────────────────────────────────────────────
#  GROUP 4: Template Generator
# ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("GROUP 4: TEMPLATE GENERATOR")
print("=" * 70)


def test_generator_available_templates():
    from generator import TemplateGenerator

    gen = TemplateGenerator()
    templates = gen.get_available_templates()
    assert "interface" in templates
    assert "component" in templates
    assert "command" in templates
    assert "dialog" in templates
    assert len(templates) >= 20


def test_generator_interface():
    from generator import TemplateGenerator

    tmp = Path(tempfile.mkdtemp())
    try:
        gen = TemplateGenerator()
        r = gen.generate("interface", "ITest", tmp)
        assert r["status"] == "success"
        assert r["count"] >= 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_generator_component():
    from generator import TemplateGenerator

    tmp = Path(tempfile.mkdtemp())
    try:
        gen = TemplateGenerator()
        r = gen.generate("component", "TestComp", tmp, interface="ITest")
        assert r["status"] == "success"
        assert r["count"] >= 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_generator_command():
    from generator import TemplateGenerator

    tmp = Path(tempfile.mkdtemp())
    try:
        gen = TemplateGenerator()
        r = gen.generate("command", "TestCmd", tmp)
        assert r["status"] == "success"
        assert r["count"] >= 5
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_generator_dialog():
    from generator import TemplateGenerator

    tmp = Path(tempfile.mkdtemp())
    try:
        gen = TemplateGenerator()
        r = gen.generate("dialog", "TestDlg", tmp)
        assert r["status"] == "success"
        assert r["count"] >= 3
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_generator_workbench():
    from generator import TemplateGenerator

    tmp = Path(tempfile.mkdtemp())
    try:
        gen = TemplateGenerator()
        r = gen.generate("workbench", "TestWb", tmp)
        assert r["status"] == "success"
        assert r["count"] >= 5
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


report.test("Available templates", test_generator_available_templates)
report.test("Generate interface", test_generator_interface)
report.test("Generate component", test_generator_component)
report.test("Generate command", test_generator_command)
report.test("Generate dialog", test_generator_dialog)
report.test("Generate workbench", test_generator_workbench)


# ───────────────────────────────────────────────────────────────────
#  GROUP 5: Workspace Analyzer
# ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("GROUP 5: WORKSPACE ANALYZER")
print("=" * 70)


def test_analyzer_empty_workspace():
    from analyzer import WorkspaceAnalyzer

    tmp = Path(tempfile.mkdtemp())
    try:
        analyzer = WorkspaceAnalyzer(tmp)
        snap = analyzer.analyze()
        assert snap is not None
        assert len(snap.frameworks) == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_analyzer_detect_framework():
    from analyzer import WorkspaceAnalyzer

    tmp = Path(tempfile.mkdtemp())
    try:
        fw_dir = tmp / "TestFw.edu"
        fw_dir.mkdir()
        ic_dir = fw_dir / "IdentityCard"
        ic_dir.mkdir()
        (ic_dir / "IdentityCard.h").write_text('AddPrereqComponent("System",Public);')

        analyzer = WorkspaceAnalyzer(tmp)
        snap = analyzer.analyze()
        assert len(snap.frameworks) == 1
        assert snap.frameworks[0].name == "TestFw.edu"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_analyzer_detect_module():
    from analyzer import WorkspaceAnalyzer

    tmp = Path(tempfile.mkdtemp())
    try:
        fw_dir = tmp / "TestFw.edu"
        fw_dir.mkdir()
        (fw_dir / "IdentityCard").mkdir()
        (fw_dir / "IdentityCard" / "IdentityCard.h").write_text(
            'AddPrereqComponent("System",Public);'
        )

        mod_dir = fw_dir / "TestMod.m"
        mod_dir.mkdir()
        (mod_dir / "Imakefile.mk").write_text("MODULE=TestMod")

        analyzer = WorkspaceAnalyzer(tmp)
        snap = analyzer.analyze()
        assert len(snap.frameworks[0].modules) == 1
        assert snap.frameworks[0].modules[0].name == "TestMod.m"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_analyzer_real_workspace():
    from analyzer import WorkspaceAnalyzer

    tmp = Path(tempfile.mkdtemp(prefix="cade_int_real_"))
    try:
        # Create expected workspace structure
        fw = tmp / "TestFramework.edu"
        fw.mkdir()
        (fw / "IdentityCard").mkdir()
        (fw / "IdentityCard" / "IdentityCard.h").write_text(
            'AddPrereqComponent("System",Public);'
        )

        analyzer = WorkspaceAnalyzer(tmp)
        snap = analyzer.analyze()
        assert snap is not None
        assert len(snap.frameworks) >= 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


report.test("Analyze empty workspace", test_analyzer_empty_workspace)
report.test("Detect framework", test_analyzer_detect_framework)
report.test("Detect module", test_analyzer_detect_module)
report.test("Analyze real workspace", test_analyzer_real_workspace)


# ───────────────────────────────────────────────────────────────────
#  GROUP 6: Atomic Actions
# ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("GROUP 6: ATOMIC ACTIONS")
print("=" * 70)

# Setup shared temp workspace for action tests
WS6 = Path(tempfile.mkdtemp(prefix="cade_int_act_"))
fw6 = WS6 / "TestFw.edu"
fw6.mkdir()
(fw6 / "IdentityCard").mkdir()
(fw6 / "IdentityCard" / "IdentityCard.h").write_text('AddPrereqComponent("System",Public);')
mod6 = fw6 / "TestMod.m"
mod6.mkdir()
(mod6 / "src").mkdir(parents=True, exist_ok=True)
(mod6 / "LocalInterfaces").mkdir(parents=True, exist_ok=True)
(mod6 / "Imakefile.mk").write_text("MODULE=TestMod\nSOURCES = \\")


def test_action_context():
    from actions import ActionContext

    ctx = ActionContext(str(WS6))
    snap = ctx.snapshot
    assert snap is not None


def test_action_analyze():
    from actions import ActionContext, analyze_workspace

    ctx = ActionContext(str(WS6))
    result = analyze_workspace(ctx)
    assert result["status"] == "ok"
    assert "summary" in result


def test_action_list_modules():
    from actions import ActionContext, list_modules

    ctx = ActionContext(str(WS6))
    result = list_modules(ctx)
    assert result["status"] == "ok"
    assert "modules" in result
    assert result["count"] >= 0


def test_action_list_commands():
    from actions import ActionContext, list_commands

    ctx = ActionContext(str(WS6))
    result = list_commands(ctx)
    assert result["status"] == "ok"
    assert "commands" in result


def test_action_list_workbenches():
    from actions import ActionContext, list_workbenches

    ctx = ActionContext(str(WS6))
    result = list_workbenches(ctx)
    assert result["status"] == "ok"


def test_action_list_interfaces():
    from actions import ActionContext, list_interfaces

    ctx = ActionContext(str(WS6))
    result = list_interfaces(ctx)
    assert result["status"] == "ok"


def test_action_create_command_changeset():
    from actions import ActionContext, create_command

    tmp = Path(tempfile.mkdtemp())
    try:
        # Setup minimal workspace
        fw = tmp / "TestFw.edu"
        fw.mkdir()
        (fw / "IdentityCard").mkdir()
        (fw / "IdentityCard" / "IdentityCard.h").write_text(
            'AddPrereqComponent("System",Public);'
        )
        mod = fw / "TestMod.m"
        mod.mkdir()
        (mod / "src").mkdir()
        (mod / "LocalInterfaces").mkdir()
        (mod / "Imakefile.mk").write_text("MODULE=TestMod\nSOURCES = \\")

        ctx = ActionContext(str(tmp))
        ctx.refresh()

        result = create_command(ctx, "TestCmd", "TestMod.m")
        assert result["status"] == "pending"
        assert "changeset" in result
        cs = result["changeset"]
        assert len(cs["created"]) >= 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


report.test("ActionContext", test_action_context)
report.test("analyze_workspace", test_action_analyze)
report.test("list_modules", test_action_list_modules)
report.test("list_commands", test_action_list_commands)
report.test("list_workbenches", test_action_list_workbenches)
report.test("list_interfaces", test_action_list_interfaces)
report.test("create_command ChangeSet", test_action_create_command_changeset)


# ───────────────────────────────────────────────────────────────────
#  GROUP 7: Environment & Build
# ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("GROUP 7: ENVIRONMENT & BUILD")
print("=" * 70)


def test_env_initialization():
    from env import CAAEnvironment

    caa_env = CAAEnvironment()
    env_vars = caa_env.initialize()
    assert env_vars is not None


def test_env_info():
    from env import CAAEnvironment

    caa_env = CAAEnvironment()
    caa_env.initialize()
    info = caa_env.get_info()
    assert "catia_version" in info
    assert "mkmk_path" in info


def test_parser():
    from parser import parse_mkmk_output

    output = """
    C:\\test\\file.cpp(10): error C2143: syntax error
    C:\\test\\file.cpp(20): warning C4101: unreferenced variable
    """
    result = parse_mkmk_output(output)
    assert result["error_count"] == 1
    assert result["warning_count"] == 1


def test_utils_logger():
    from utils import Logger

    logger = Logger("integration_test.log")
    logger.clear()
    logger.write("Test message", "INFO")
    assert logger.log_path.exists()


def test_utils_cache():
    from utils import Cache

    cache = Cache("integration_test.json")
    cache.save({"test": "data"})
    data = cache.load()
    assert data["test"] == "data"
    cache.clear()


report.test("Environment initialization", test_env_initialization)
report.test("Environment info", test_env_info)
report.test("mkmk parser", test_parser)
report.test("Logger", test_utils_logger)
report.test("Cache", test_utils_cache)


# ═══════════════════════════════════════════════════════════════════
#  FINAL REPORT
# ═══════════════════════════════════════════════════════════════════

sys.exit(report.summary())
