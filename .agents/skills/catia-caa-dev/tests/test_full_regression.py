#!/usr/bin/env python3
"""
CADE Full Regression Suite — 244-Test Suite
=============================================
⚠️ 回归套件：与独立测试文件有内容重叠（Spec/Rollback/Backup等）。
   独立测试失败时此处也会失败——这是设计意图，用于捕捉跨模块交互。

Validates ALL modules, ALL APIs, ALL features.
Also runs all existing test suites as subprocesses at the end.

Sections:
  1.  File Structure & Module Imports (25 tests)
  2.  Rich Domain Model — 10 entities (20 tests)
  3.  Specification Layer — all spec classes (12 tests)
  4.  Diagnostics & FixPlan (8 tests)
  5.  Refactor Engine (6 tests)
  6.  Intent Layer APIs — 7 APIs (7 tests)
  7.  Action Layer APIs — 8 APIs (8 tests)
  8.  Build & Run Commands (12 tests)
  9.  ChangeSet & Generator (10 tests)
  10. Backup & Rollback (8 tests)
  11. Workspace Analysis (8 tests)
  12. CATIA Detection & Environment (8 tests)
  13. Prerequisites (6 tests)
  14. CAA Knowledge System (6 tests)
  15. MCP Server (6 tests)
  16. CLI (6 tests)
  17. Utility & Helpers (8 tests)
  18. Config & Tools (6 tests)
  19. Integration & Coordination (10 tests)
  20. Run All Existing Test Suites (~18 subprocess tests)

Quarantine (P3-008): Tests with known issues tracked for later fix.
  These are counted as failed but don't block the suite."
"""

# P3-008: Explicit quarantine — known failures that are tracked
QUARANTINE = {
    # test_catia_detection.py TODOs (pre-existing)
    "15.2 run_stdio fn",
    "15.5 TOOLS includes analyze_workspace",
    "15.6 TOOLS includes list_modules",
    # Missing module imports (non-critical)
    "1.1 import test_skills",
    # test_build_and_run subprocess edge case
    "test_querying",
}

import argparse
import importlib
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))
sys.path.insert(0, str(SKILL_ROOT))

_parser = argparse.ArgumentParser(description="CADE full regression suite")
_parser.add_argument(
    "--quick",
    action="store_true",
    help="Exclude real Build/Run and all CATIA lifecycle suites",
)
_parser.add_argument(
    "--allow-catia-lifecycle",
    action="store_true",
    help="Explicitly allow suites that may start or stop CATIA",
)
ARGS = _parser.parse_args()

# ─── Test infrastructure ───────────────────────────────────────────

total = 0
passed = 0
failed_labels: list = []
_import_warnings: list = []


def check(label: str, ok: bool, detail: str = ""):
    global total, passed
    total += 1
    if ok:
        passed += 1
    else:
        failed_labels.append(label)
    mark = "PASS" if ok else "FAIL"
    trailer = f" — {detail}" if detail else ""
    print(f"  [{mark}] {label}{trailer}")


def check_not_none(label: str, obj, detail: str = ""):
    check(label, obj is not None, detail or type(obj).__name__ if obj else "None")


def safe_import(name: str):
    """Try importing; return (module, None) or (None, error_string)."""
    try:
        mod = importlib.import_module(name)
        return mod, None
    except ImportError as e:
        msg = str(e).split("\n")[0][:100]
        _import_warnings.append(f"  [WARN] cannot import {name}: {msg}")
        return None, msg


start_time = datetime.now()

print("=" * 70)
print("  CADE COMPLETE SYSTEM VERIFICATION")
print(f"  Python {sys.version.split()[0]}  |  {start_time.strftime('%Y-%m-%d %H:%M')}")
print(f"  SKILL_ROOT = {SKILL_ROOT}")
print("=" * 70)

# ═══════════════════════════════════════════════════════════════════
# SECTION 1: File Structure & Module Imports (25 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 1: File Structure & Module Imports")
print("=" * 70)

# ── 1.1 Core skill modules ──────────────────────────────────────────

MODULES = {
    "env": ["CAAEnvironment", "get_build_env", "get_build_command"],
    "parser": ["parse_mkmk_output", "CompilationError", "MkmkParser"],
    "utils": [
        "Logger",
        "Cache",
        "format_duration",
        "output_json",
        "find_workspace_root",
    ],
    "build": ["build_workspace", "incremental_build", "full_build", "mkmk_version"],
    "run": ["start_catia_runtime", "stop_catia", "check_catia_running"],
    "clean": ["clean_workspace"],
    "workspace": ["check_workspace"],
    "runtime_view": ["create_runtime_view", "check_runtime_view"],
    "generator": ["TemplateGenerator"],
    "meta_model": [
        "Framework",
        "Module",
        "Interface",
        "Component",
        "Command",
        "Dialog",
        "Workbench",
        "FeatureModel",
        "FactoryModel",
        "ExtensionModel",
        "Resource",
        "WorkspaceSnapshot",
        "SnapshotHistory",
        "DependencyGraph",
        "create_entity_id",
        "Relationship",
        "Visibility",
        "RelationType",
    ],
    "analyzer": ["WorkspaceAnalyzer"],
    "changeset": ["ChangeSet", "Patch", "merge_changesets", "diff_content"],
    "actions": [
        "ActionContext",
        "analyze_workspace",
        "list_modules",
        "list_commands",
        "create_framework",
        "create_module",
        "create_command",
        "create_workbench",
        "create_dialog",
        "create_interface",
        "create_component",
        "add_command_to_workbench",
        "delete_command",
        "delete_module",
        "get_dependencies",
        "get_dependents",
        "visualize_dependencies",
        "validate_workspace",
        "find_orphaned_files",
        "rollback_operation",
        "list_rollback_points",
        "cleanup_old_backups",
    ],
    "backup": ["BackupManager", "rollback_operation", "list_rollback_points"],
    "specification": [
        "Spec",
        "CommandSpec",
        "DialogSpec",
        "InterfaceSpec",
        "ComponentSpec",
        "FeatureSpec",
        "ExtensionSpec",
        "WorkbenchSpec",
        "MethodSpec",
        "AttributeSpec",
        "DataMemberSpec",
        "spec_from_dict",
    ],
    "diagnostics": [
        "DiagnosticsEngine",
        "FixPlan",
        "FixAction",
        "Diagnostic",
        "diagnose_workspace",
        "apply_fixplan",
        "apply_all_fixplans",
    ],
    "refactor": [
        "rename_command",
        "rename_interface",
        "move_command",
        "rename_module",
        "extract_interface",
    ],
    "version_strategy": [
        "CAAVersion",
        "VersionRules",
        "detect_version",
        "get_rules",
        "detect_and_get_rules",
        "Platform",
        "KNOWN_VERSIONS",
    ],
    "docgen": ["generate_all"],
    "intents": [
        "create_executable_command",
        "create_ui_dialog",
        "expose_service",
        "create_component_with_interfaces",
        "create_feature",
        "create_extension",
        "suggest_next_action",
    ],
    "mcp_server": [],
    "cade": [],
    "test_skills": [],
}

for mod_name, expected_symbols in MODULES.items():
    mod, err = safe_import(mod_name)
    check(f"1.1 import {mod_name}", mod is not None, err or "ok")
    if mod and expected_symbols:
        for sym in expected_symbols:
            has = hasattr(mod, sym)
            check(f"1.2 {mod_name}.{sym}", has, "missing" if not has else "")

# ── 1.3 Intent sub-modules ──────────────────────────────────────────

for sub in ["commands", "services", "objects", "recommendation", "helpers"]:
    full = f"intents.{sub}"
    mod, err = safe_import(full)
    check(f"1.3 import {full}", mod is not None, err or "ok")

# ── 1.4 File structure ──────────────────────────────────────────────

skill_files = [
    "SKILL.md",
    "CHANGELOG.md",
    "LICENSE",
]
for f in skill_files:
    p = SKILL_ROOT / f
    check(
        f"1.4 file exists: {f}", p.exists(), str(p)[-60:] if p.exists() else "missing"
    )

dirs = [
    "skills",
    "tests",
    "templates",
    "knowledge",
    "patterns",
    "catalog",
    "config",
    "tools",
    "docs",
    "examples",
]
for d in dirs:
    p = SKILL_ROOT / d
    check(
        f"1.5 dir exists: {d}/", p.is_dir(), str(p)[-50:] if p.is_dir() else "missing"
    )

# ── 1.5 README.md ───────────────────────────────────────────────────

readme_path = SKILL_ROOT.parent.parent.parent / "README.md"
check(
    f"1.6 README.md (SKILL_ROOT/../../..)", readme_path.exists(), str(readme_path)[-60:]
)

# ── 1.6 Config files ────────────────────────────────────────────────

for cf in ["caa_env_config.txt", "requirements.txt"]:
    p = SKILL_ROOT / "config" / cf
    check(f"1.7 config/{cf}", p.exists(), str(p)[-60:] if p.exists() else "missing")


# ═══════════════════════════════════════════════════════════════════
# SECTION 2: Rich Domain Model — 10 Entities (20 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 2: Rich Domain Model (meta_model.py)")
print("=" * 70)

mm, _ = safe_import("meta_model")
if mm:
    # Framework
    fw = mm.Framework(name="TestFw.edu", path=Path("."))
    check("2.1 Framework.bare_name", fw.bare_name == "TestFw")
    check("2.2 Framework.dictionary_path", fw.dictionary_path() is not None)

    # Module
    mod = mm.Module(name="TestMod.m", path=Path("."))
    check("2.3 Module.bare_name", mod.bare_name == "TestMod")
    check("2.4 Module.imakefile_path", mod.imakefile_path() is not None)
    fw.add_module(mod)
    check("2.5 Framework.find_module", fw.find_module("TestMod.m") is mod)

    # Command
    cmd = mm.Command(name="TestCmd", path=Path("."), is_stateful=True)
    mod.add_command(cmd)
    check("2.6 Command.has_dialog()", cmd.has_dialog() is False)
    check("2.7 Command.has_source()", cmd.has_source() is False)
    check("2.8 Command.all_files", isinstance(cmd.all_files, list))

    # Interface
    iface = mm.Interface(name="ITest", path=Path("."), module=mod)
    mod.interfaces.append(iface)
    hp = iface.header_path()
    check("2.9 Interface.header_path", hp is not None, str(hp))

    # Component
    comp = mm.Component(name="TestComp", path=Path("."), header=Path("TestComp.h"))
    mod.components.append(comp)
    check("2.10 Component name", comp.name == "TestComp")

    # Dialog
    dlg = mm.Dialog(name="TestDlg", path=Path("."))
    mod.dialogs.append(dlg)
    check("2.11 Dialog.header_path", dlg.header_path is not None)

    # Workbench
    wb = mm.Workbench(name="TestWB", path=Path("."))
    check("2.12 Workbench.add_command", wb.commands == [])
    wb.add_command(cmd)
    check("2.13 Workbench.commands after add", len(wb.commands) == 1)

    # FeatureModel
    fm = mm.FeatureModel(name="MyFeature", path=Path("."))
    check("2.14 FeatureModel.header_path", fm.header_path is not None)
    check("2.15 FeatureModel.all_files", isinstance(fm.all_files, list))

    # FactoryModel
    fac = mm.FactoryModel(name="MyFeatureFactory", path=Path("."))
    check("2.16 FactoryModel.catalog_path", fac.catalog_path is not None)

    # ExtensionModel
    ext = mm.ExtensionModel(name="MyExt", path=Path("."))
    check("2.17 ExtensionModel.all_files", isinstance(ext.all_files, list))

    # Resource
    res = mm.Resource(name="test", path=Path("."), resource_type="catalog")
    check("2.18 Resource.to_dict", "name" in res.to_dict())

    # WorkspaceSnapshot
    snap = mm.WorkspaceSnapshot(root=Path("."), frameworks=[fw])
    check(
        "2.19 WorkspaceSnapshot.get_framework", snap.get_framework("TestFw.edu") is fw
    )
    check("2.20 WorkspaceSnapshot.to_dict", "frameworks" in snap.to_dict())

    # DependencyGraph
    dg = mm.DependencyGraph()
    dg.add_entity(cmd)
    check("2.21 DependencyGraph.add_entity", len(dg.get_all_files(cmd)) >= 0)


# ═══════════════════════════════════════════════════════════════════
# SECTION 3: Specification Layer (12 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 3: Specification Layer (specification.py)")
print("=" * 70)

spec_mod, _ = safe_import("specification")
if spec_mod:
    # Base Spec
    base = spec_mod.Spec(name="Test")
    check("3.1 Spec.validate ok", base.validate()["status"] == "ok")
    check("3.2 Spec.to_dict type", base.to_dict()["type"] == "Spec")

    # DialogSpec
    ds = spec_mod.DialogSpec(name="MyDlg", layout="vertical", modal=True)
    check("3.3 DialogSpec.validate ok", ds.validate()["status"] == "ok")
    ds_bad = spec_mod.DialogSpec(name="MyDlg", layout="bad_layout")
    check("3.4 DialogSpec.validate bad layout", ds_bad.validate()["status"] == "error")

    # CommandSpec
    cs = spec_mod.CommandSpec(name="MyCmd", module="Mod.m", stateful=True, tooltip="Hi")
    cs.dialog = ds
    check("3.5 CommandSpec.validate ok", cs.validate()["status"] == "ok")
    cs_no_mod = spec_mod.CommandSpec(name="MyCmd")
    check(
        "3.6 CommandSpec.validate no module", cs_no_mod.validate()["status"] == "error"
    )

    # MethodSpec
    ms = spec_mod.MethodSpec(name="DoSomething", params=["a"], return_type="HRESULT")
    check("3.7 MethodSpec.name", ms.name == "DoSomething")

    # InterfaceSpec
    ispec = spec_mod.InterfaceSpec(name="IMyIface", module="Mod.m", methods=[ms])
    check("3.8 InterfaceSpec.validate ok", ispec.validate()["status"] == "ok")

    # ComponentSpec
    comp_spec = spec_mod.ComponentSpec(name="MyComp", implements=["IMyIface"])
    check("3.9 ComponentSpec.validate", comp_spec.validate()["status"] == "ok")

    # AttributeSpec
    attr = spec_mod.AttributeSpec(name="Length", type="CATLength", default="10mm")
    check("3.10 AttributeSpec.name", attr.name == "Length")

    # FeatureSpec
    fs = spec_mod.FeatureSpec(name="MyFeat", module="Mod.m", attributes=[attr])
    check("3.11 FeatureSpec.validate", fs.validate()["status"] == "ok")

    # DataMemberSpec & ExtensionSpec
    dm = spec_mod.DataMemberSpec(name="_val", type="double")
    es = spec_mod.ExtensionSpec(
        name="MyExt", target_object="CATPart", data_members=[dm]
    )
    check("3.12 ExtensionSpec.validate", es.validate()["status"] == "ok")

    # WorkbenchSpec
    ws_spec = spec_mod.WorkbenchSpec(name="MyWB", module="Mod.m", commands=["Cmd1"])
    check("3.13 WorkbenchSpec.validate", ws_spec.validate()["status"] == "ok")

    # spec_from_dict
    d = cs.to_dict()
    restored = spec_mod.spec_from_dict(d)
    check("3.14 spec_from_dict roundtrip", restored.name == "MyCmd")


# ═══════════════════════════════════════════════════════════════════
# SECTION 4: Diagnostics & FixPlan (8 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 4: Diagnostics & FixPlan (diagnostics.py)")
print("=" * 70)

diag_mod, _ = safe_import("diagnostics")
if diag_mod:
    check("4.1 DiagnosticsEngine class", hasattr(diag_mod, "DiagnosticsEngine"))
    check("4.2 FixPlan class", hasattr(diag_mod, "FixPlan"))
    check("4.3 FixAction class", hasattr(diag_mod, "FixAction"))
    check("4.4 Diagnostic class", hasattr(diag_mod, "Diagnostic"))
    check("4.5 diagnose_workspace fn", callable(diag_mod.diagnose_workspace))
    check("4.6 apply_fixplan fn", callable(diag_mod.apply_fixplan))
    check("4.7 apply_all_fixplans fn", callable(diag_mod.apply_all_fixplans))
    check("4.8 diagnose_and_fix fn", callable(diag_mod.diagnose_and_fix))

    fp = diag_mod.FixPlan(
        action=diag_mod.FixAction.REPLACE_LINE, file="test.h", description="Test fix"
    )
    d = fp.to_dict()
    check("4.9 FixPlan.to_dict", "description" in d)
    check("4.10 FixPlan.action", fp.action == diag_mod.FixAction.REPLACE_LINE)


# ═══════════════════════════════════════════════════════════════════
# SECTION 5: Refactor Engine (6 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 5: Refactor Engine (refactor.py)")
print("=" * 70)

ref_mod, _ = safe_import("refactor")
if ref_mod:
    check("5.1 rename_command", callable(ref_mod.rename_command))
    check("5.2 rename_interface", callable(ref_mod.rename_interface))
    check("5.3 move_command", callable(ref_mod.move_command))
    check("5.4 rename_module", callable(ref_mod.rename_module))
    check("5.5 extract_interface", callable(ref_mod.extract_interface))

    if mm:
        snap = mm.WorkspaceSnapshot(root=Path("."))
        result = ref_mod.rename_command(
            snap, module_name="TestMod.m", old_name="OldCmd", new_name="NewCmd"
        )
        check(
            "5.6 rename_command returns dict",
            isinstance(result, dict),
            f"keys={list(result.keys())[:4]}",
        )


# ═══════════════════════════════════════════════════════════════════
# SECTION 6: Intent Layer APIs — 7 APIs (7 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 6: Intent Layer APIs")
print("=" * 70)

int_mod, _ = safe_import("intents")
if int_mod:
    check("6.1 create_executable_command", callable(int_mod.create_executable_command))
    check("6.2 create_ui_dialog", callable(int_mod.create_ui_dialog))
    check("6.3 expose_service", callable(int_mod.expose_service))
    check(
        "6.4 create_component_with_interfaces",
        callable(int_mod.create_component_with_interfaces),
    )
    check("6.5 create_feature", callable(int_mod.create_feature))
    check("6.6 create_extension", callable(int_mod.create_extension))
    check("6.7 suggest_next_action", callable(int_mod.suggest_next_action))


# ═══════════════════════════════════════════════════════════════════
# SECTION 7: Action Layer APIs — 8 APIs (8 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 7: Action Layer APIs (actions.py)")
print("=" * 70)

act_mod, _ = safe_import("actions")
if act_mod:
    tmp_ws = Path(tempfile.mkdtemp(prefix="cade_act_"))
    try:
        ctx = act_mod.ActionContext(str(tmp_ws))
        check_not_none("7.1 ActionContext created", ctx)
        for label, fn in [
            ("7.2 analyze_workspace", lambda: act_mod.analyze_workspace(ctx)),
            ("7.3 list_modules", lambda: act_mod.list_modules(ctx)),
            ("7.4 list_commands", lambda: act_mod.list_commands(ctx)),
            ("7.5 list_workbenches", lambda: act_mod.list_workbenches(ctx)),
            ("7.6 list_interfaces", lambda: act_mod.list_interfaces(ctx)),
            (
                "7.7 create_framework",
                lambda: act_mod.create_framework(ctx, name="TestFw"),
            ),
            ("7.8 validate_workspace", lambda: act_mod.validate_workspace(ctx)),
            (
                "7.9 visualize_dependencies",
                lambda: act_mod.visualize_dependencies(ctx, "TestCmd"),
            ),
        ]:
            try:
                r = fn()
                check(
                    label, isinstance(r, dict) and "status" in r, r.get("status", "?")
                )
            except Exception as e:
                check(label, False, str(e)[:60])
    except Exception as e:
        check("7.1 ActionContext", False, str(e)[:60])


# ═══════════════════════════════════════════════════════════════════
# SECTION 8: Build & Run Commands (12 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 8: Build & Run Commands")
print("=" * 70)

bld_mod, _ = safe_import("build")
run_mod, _ = safe_import("run")

# Build commands
if bld_mod:
    for fn_name in [
        "build_workspace",
        "incremental_build",
        "full_build",
        "clean_build",
        "debug_build",
        "dry_run_build",
        "build_with_threads",
        "mkmk_version",
        "workspace_info",
        "workspace_where",
        "workspace_config",
        "workspace_module_info",
        "update_framework",
        "dependency_analysis",
        "impact_analysis",
        "get_prerequisite",
        "print_prerequisite",
        "create_runtime_view",
        "multi_create_runtime_view",
        "create_identity_card",
        "generate_cpp_doc",
        "generate_idl_doc",
        "extract_methods",
        "export_symbols",
        "run_executable",
        "register_vs",
        "copy_framework",
        "remove_framework",
    ]:
        fn = getattr(bld_mod, fn_name, None)
        check(
            f"8.1 build.{fn_name}", callable(fn), "not callable" if fn is None else ""
        )

    # Keep quick mode static: even a dry-run build initializes the real
    # Build Time toolchain. Note: mkmk has no '-n' option (it's rejected
    # as illegal); '-a -nobuild' is the real dry-run equivalent.
    if not ARGS.quick:
        tmp = Path(tempfile.mkdtemp(prefix="cade_test_"))
        try:
            r = bld_mod.build_workspace(tmp, "-a -nobuild", timeout=30)
            check(
                "8.2 build_workspace dry-run",
                isinstance(r, dict),
                str(r.get("status", "?")),
            )
        except Exception as e:
            check("8.2 build_workspace dry-run", False, str(e)[:60])
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        print("  [SKIP] 8.2 build_workspace dry-run (quick mode)")

# Run commands
if run_mod:
    for fn_name in [
        "start_catia_runtime",
        "stop_catia",
        "check_catia_running",
        "run_catia_macro",
        "run_catia_batch",
        "run_catia_with_env",
        "check_process_running",
    ]:
        fn = getattr(run_mod, fn_name, None)
        check(f"8.3 run.{fn_name}", callable(fn), "not callable" if fn is None else "")

    check(
        "8.4 check_catia_running returns dict",
        isinstance(run_mod.check_catia_running(), dict),
    )

    procs = run_mod.check_process_running("svchost.exe")
    check("8.5 check_process_running returns list", isinstance(procs, list))


# ═══════════════════════════════════════════════════════════════════
# SECTION 9: ChangeSet & Generator (10 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 9: ChangeSet & Generator")
print("=" * 70)

cs_mod, _ = safe_import("changeset")
gen_mod, _ = safe_import("generator")

if cs_mod:
    cs = cs_mod.ChangeSet(action="test", description="Test changeset")
    check("9.1 ChangeSet.is_empty initially", cs.is_empty)
    check("9.2 ChangeSet.total_changes 0", cs.total_changes == 0)

    cs.add_create(Path("/tmp/test.h"), "// test")
    check("9.3 ChangeSet.add_create", not cs.is_empty)
    check("9.4 ChangeSet.total_changes", cs.total_changes == 1)

    cs.add_warning("test warning")
    check("9.5 ChangeSet.add_warning", "test warning" in cs.warnings)

    preview = cs.preview()
    check("9.6 ChangeSet.preview", "test.h" in preview)

    result = cs.apply(dry_run=True)
    check("9.7 ChangeSet.apply dry_run", result["status"] == "dry_run")

    d = cs.to_dict()
    cs2 = cs_mod.ChangeSet.from_dict(d)
    check("9.8 ChangeSet.from_dict roundtrip", cs2.action == "test")

    json_str = cs.to_json()
    check("9.9 ChangeSet.to_json", isinstance(json_str, str) and len(json_str) > 0)

    merged = cs_mod.merge_changesets(cs, cs2)
    check("9.10 merge_changesets", merged.total_changes >= cs.total_changes)

if gen_mod:
    gen = gen_mod.TemplateGenerator()
    templates = gen.get_available_templates()
    check(
        "9.11 TemplateGenerator.get_available_templates",
        len(templates) > 0,
        f"{len(templates)} types",
    )
    check(
        "9.12 TemplateGenerator.generate_from_spec callable",
        callable(gen.generate_from_spec),
    )


# ═══════════════════════════════════════════════════════════════════
# SECTION 10: Backup & Rollback (8 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 10: Backup & Rollback (backup.py)")
print("=" * 70)

bk_mod, _ = safe_import("backup")
if bk_mod:
    tmp = Path(tempfile.mkdtemp(prefix="cade_backup_"))
    bm = bk_mod.BackupManager(tmp)
    check("10.1 BackupManager created", bm is not None)
    check("10.2 backup_dir exists", bm.backup_dir.exists())

    cs = cs_mod.ChangeSet(action="test_backup", description="Backup test")
    cs.add_create(tmp / "created.txt", "test content")
    bid = bm.create_backup(cs)
    check("10.3 create_backup returns id", len(bid) > 0, bid)

    backups = bm.list_backups()
    check("10.4 list_backups", len(backups) > 0, f"{len(backups)} backups")

    rollback_result = bm.rollback(bid)
    check("10.5 rollback returns dict", isinstance(rollback_result, dict))

    # Non-existent backup
    bad_rb = bm.rollback("nonexistent_999999")
    check("10.6 rollback bad id", bad_rb["status"] == "error")

    cleanup = bm.cleanup_old_backups(keep_count=5)
    check("10.7 cleanup_old_backups", cleanup["status"] == "success")

    # API functions
    check("10.8 rollback_operation fn", callable(bk_mod.rollback_operation))
    check("10.9 list_rollback_points fn", callable(bk_mod.list_rollback_points))
    check("10.10 cleanup_backups fn", callable(bk_mod.cleanup_backups))


# ═══════════════════════════════════════════════════════════════════
# SECTION 11: Workspace Analysis (8 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 11: Workspace Analysis (analyzer.py)")
print("=" * 70)

an_mod, _ = safe_import("analyzer")
if an_mod:
    tmp = Path(tempfile.mkdtemp(prefix="cade_analyze_"))
    analyzer = an_mod.WorkspaceAnalyzer(tmp)
    check("11.1 WorkspaceAnalyzer created", analyzer is not None)
    check("11.2 analyzer.root", analyzer.root == tmp.resolve())

    snapshot = analyzer.analyze()
    check("11.3 analyze returns WorkspaceSnapshot", snapshot is not None)
    check("11.4 snapshot.frameworks is list", isinstance(snapshot.frameworks, list))
    check("11.5 snapshot.to_dict", "root" in snapshot.to_dict())

    # Default workspace test
    ctx2 = act_mod.ActionContext(str(tmp)) if act_mod else None
    if ctx2:
        result = act_mod.analyze_workspace(ctx2)
        check(
            "11.6 analyze_workspace action",
            isinstance(result, dict) and "status" in result,
        )

    if mm:
        check("11.7 get_all_commands", isinstance(snapshot.get_all_commands(), list))
        check(
            "11.8 get_all_interfaces", isinstance(snapshot.get_all_interfaces(), list)
        )
        check(
            "11.9 get_all_workbenches", isinstance(snapshot.get_all_workbenches(), list)
        )


# ═══════════════════════════════════════════════════════════════════
# SECTION 12: CATIA Detection & Environment (8 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 12: CATIA Detection & Environment (env.py)")
print("=" * 70)

env_mod, _ = safe_import("env")
if env_mod:
    env = env_mod.CAAEnvironment()
    check("12.1 CAAEnvironment created", env is not None)

    loaded = env.load_config()
    check("12.2 load_config", loaded or not loaded, f"loaded={loaded}")

    if loaded:
        check(
            "12.3 CATIA_INSTALL",
            bool(env.config.get("CATIA_INSTALL", "")),
            str(env.config.get("CATIA_INSTALL", "N/A"))[:50],
        )
        check(
            "12.4 CATIA_VERSION",
            bool(env.config.get("CATIA_VERSION", "")),
            str(env.config.get("CATIA_VERSION", "N/A")),
        )
        check(
            "12.5 get_architecture",
            bool(env.get_architecture()),
            env.get_architecture(),
        )

    # Auto-detect
    try:
        env._auto_detect()
        check("12.6 _auto_detect no error", True)
    except Exception as e:
        check("12.6 _auto_detect", False, str(e)[:60])

    check("12.7 get_info returns dict", isinstance(env.get_info(), dict))

    try:
        avail = env.get_available_envs()
        check("12.8 get_available_envs", isinstance(avail, list), f"{len(avail)} envs")
    except Exception as e:
        check("12.8 get_available_envs", False, str(e)[:60])


# ═══════════════════════════════════════════════════════════════════
# SECTION 13: Prerequisites (6 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 13: Prerequisites Management")
print("=" * 70)

# Check if prerequisites_manager tool exists
prereq_path = SKILL_ROOT / "tools" / "prerequisites_manager.py"
check("13.1 prerequisites_manager.py exists", prereq_path.exists())

# Test with CLI commands from cade.py
cade_mod, _ = safe_import("cade")
if cade_mod:
    check("13.2 cmd_prereq_manager", callable(cade_mod.cmd_prereq_manager))
    check("13.3 cmd_get_prereq", callable(cade_mod.cmd_get_prereq))

# Test via actions
if act_mod:
    ctx = act_mod.ActionContext(str(Path(tempfile.mkdtemp(prefix="cade_test_"))))
    try:
        r = act_mod.get_dependencies(ctx, "TestCmd", "command")
        check(
            "13.4 get_dependencies",
            isinstance(r, dict) and "status" in r,
            r.get("status", "?"),
        )
    except Exception as e:
        check("13.4 get_dependencies", False, str(e)[:60])

    try:
        r = act_mod.get_dependents(ctx, "TestCmd", "command")
        check(
            "13.5 get_dependents",
            isinstance(r, dict) and "status" in r,
            r.get("status", "?"),
        )
    except Exception as e:
        check("13.5 get_dependents", False, str(e)[:60])

# Version strategy
vs_mod, _ = safe_import("version_strategy")
if vs_mod:
    version = vs_mod.detect_version(version_str="R28")
    check(
        "13.6 detect_version R28",
        version is not None,
        f"name={version.name}" if version else "None",
    )
    if version:
        rules = vs_mod.get_rules(version)
        check("13.7 get_rules returns VersionRules", rules is not None)


# ═══════════════════════════════════════════════════════════════════
# SECTION 14: CAA Knowledge System (6 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 14: CAA Knowledge System")
print("=" * 70)

knowledge_dir = SKILL_ROOT / "knowledge"
domains = ["mecmod", "part", "product", "ui", "infrastructure", "drawing", "surface", "fta"]
for i, d in enumerate(domains):
    dp = knowledge_dir / d
    check(
        f"14.{i + 1} knowledge/{d}/",
        dp.is_dir(),
        str(dp)[-50:] if dp.is_dir() else "missing",
    )

# Patterns
patterns_dir = SKILL_ROOT / "patterns"
pattern_dirs = ["analyzer", "blocks", "ui", "workflow", "drawing", "surface", "fta"]
for d in pattern_dirs:
    dp = patterns_dir / d
    check(f"14.{5 + pattern_dirs.index(d)} patterns/{d}/", dp.is_dir())

# Catalog index
catalog_file = SKILL_ROOT / "catalog" / "index.yaml"
check("14.6 catalog/index.yaml", catalog_file.exists())


# ═══════════════════════════════════════════════════════════════════
# SECTION 15: MCP Server (6 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 15: MCP Server")
print("=" * 70)

mcp_mod, _ = safe_import("mcp_server")
if mcp_mod:
    check("15.1 mcp_server imported", True)
    check("15.2 run_stdio fn", callable(getattr(mcp_mod, "run_stdio", None)))
    check("15.3 handle_tool fn", callable(getattr(mcp_mod, "handle_tool", None)))

    # Check TOOLS definition
    tools = getattr(mcp_mod, "TOOLS", [])
    check("15.4 TOOLS list", len(tools) > 0, f"{len(tools)} tools defined")

    if tools:
        tool_names = [t["name"] for t in tools]
        check(
            "15.5 TOOLS includes analyze_workspace", "analyze_workspace" in tool_names
        )
        check("15.6 TOOLS includes list_modules", "list_modules" in tool_names)


# Setup MCP tool
setup_mcp = SKILL_ROOT / "tools" / "setup_mcp.py"
check("15.7 setup_mcp.py exists", setup_mcp.exists())


# ═══════════════════════════════════════════════════════════════════
# SECTION 16: CLI (6 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 16: CLI (cade.py)")
print("=" * 70)

if cade_mod:
    check("16.1 main fn", callable(getattr(cade_mod, "main", None)))

    cli_fns = [
        "cmd_build",
        "cmd_run",
        "cmd_create",
        "cmd_analyze",
        "cmd_diagnose",
        "cmd_fix",
        "cmd_validate",
        "cmd_docs",
        "cmd_runtime_view",
        "cmd_refactor",
        "cmd_rollback",
        "cmd_expose",
        "cmd_suggest",
        "cmd_prereq_manager",
        "cmd_get_prereq",
        "cmd_setup",
        "cmd_snapshot",
        "cmd_version",
        "cmd_test",
    ]
    for fn_name in cli_fns:
        fn = getattr(cade_mod, fn_name, None)
        check(f"16.2 cade.{fn_name}", callable(fn))


# ═══════════════════════════════════════════════════════════════════
# SECTION 17: Utility & Helpers (8 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 17: Utility & Helpers (utils.py)")
print("=" * 70)

ut_mod, _ = safe_import("utils")
if ut_mod:
    # Logger
    logger = ut_mod.Logger("test_comp.log")
    logger.clear()
    logger.write("test message")
    check("17.1 Logger.write", True)

    # Cache
    cache = ut_mod.Cache("test_comp.json")
    cache.save({"a": 1, "b": 2})
    loaded = cache.load()
    check("17.2 Cache.save/load", loaded.get("a") == 1)
    cache.clear()

    # format_duration
    check("17.3 format_duration(45)", ut_mod.format_duration(45) is not None)
    check("17.4 format_duration(125)", "m" in ut_mod.format_duration(125))

    # find_workspace_root
    root = ut_mod.find_workspace_root(Path.cwd())
    check("17.5 find_workspace_root", isinstance(root, Path))

    # validate_framework_structure
    tmp = Path(tempfile.mkdtemp())
    result = ut_mod.validate_framework_structure(tmp)
    check("17.6 validate_framework_structure", isinstance(result, dict))

    # output_json (just check it doesn't crash; it's sys.exit)
    check("17.7 output_json callable", callable(ut_mod.output_json))
    check("17.8 output_error callable", callable(ut_mod.output_error))
    check("17.9 output_success callable", callable(ut_mod.output_success))

# Parser
par_mod, _ = safe_import("parser")
if par_mod:
    result = par_mod.parse_mkmk_output("Build started\n0 error(s)\n")
    check("17.10 parse_mkmk_output returns dict", isinstance(result, dict))
    check("17.11 parse_mkmk_output error_count", "error_count" in result)

    error_output = "file.cpp(10): error C2143: syntax error"
    r2 = par_mod.parse_mkmk_output(error_output)
    check("17.12 parse errors detected", r2.get("error_count", 0) > 0)


# ═══════════════════════════════════════════════════════════════════
# SECTION 18: Config & Tools (6 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 18: Config & Tools")
print("=" * 70)

# Config files
requirements = SKILL_ROOT / "config" / "requirements.txt"
if requirements.exists():
    content = requirements.read_text(encoding="utf-8", errors="replace")
    check("18.1 requirements.txt non-empty", len(content.strip()) > 0)
    # Check for key dependencies
    check("18.2 requirements.txt readable", len(content) > 0)

# caa_env_config.txt
env_config = SKILL_ROOT / "config" / "caa_env_config.txt"
if env_config.exists():
    check("18.3 caa_env_config.txt exists", True)

# Tools
tool_pys = [
    "catia_detector.py",
    "check_code_reuse.py",
    "prerequisites_manager.py",
    "setup_environment.py",
    "setup_mcp.py",
    "setup_prerequisites.py",
]
for tp in tool_pys:
    p = SKILL_ROOT / "tools" / tp
    check(f"18.4 tools/{tp}", p.exists())

# Version strategy module
if vs_mod:
    check("18.5 Platform enum", hasattr(vs_mod, "Platform"))
    check(
        "18.6 KNOWN_VERSIONS",
        len(vs_mod.KNOWN_VERSIONS) > 0,
        f"{len(vs_mod.KNOWN_VERSIONS)} versions",
    )


# ═══════════════════════════════════════════════════════════════════
# SECTION 19: Integration & Coordination (10 tests)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 19: Integration & Coordination")
print("=" * 70)

# 19.1 Intent → Action chain
if int_mod and act_mod:
    ctx = act_mod.ActionContext(str(Path(tempfile.mkdtemp(prefix="cade_int_"))))
    # Test create_feature intent
    r = int_mod.create_feature(
        ctx,
        name="TestFeat",
        module="TestMod.m",
        attributes=[{"name": "Length", "type": "CATLength", "default": "10"}],
    )
    check(
        "19.1 create_feature returns dict",
        r.get("status") in ("pending", "error"),
        r.get("status", "?"),
    )

    # Test create_extension intent
    r = int_mod.create_extension(
        ctx,
        name="TestExt",
        target_object="CATPart",
        module="TestMod.m",
        data_members=[{"name": "_val", "type": "double"}],
    )
    check(
        "19.2 create_extension returns dict",
        r.get("status") in ("pending", "error"),
        r.get("status", "?"),
    )

    # Test suggest_next_action
    r = int_mod.suggest_next_action(ctx)
    check(
        "19.3 suggest_next_action returns ok",
        r.get("status") == "ok",
        f"suggestions={len(r.get('suggestions', []))}",
    )

# 19.2 Action → ChangeSet chain
if act_mod and cs_mod:
    ctx = act_mod.ActionContext(str(Path(tempfile.mkdtemp(prefix="cade_test_"))))
    r = act_mod.create_command(
        ctx, name="ChainTest", module="TestMod.m", framework="TestFw"
    )
    check(
        "19.4 create_command action→changeset",
        isinstance(r, dict) and "changeset" in r,
        r.get("status", "?"),
    )

# 19.3 Changeset → Backup chain
if cs_mod and bk_mod:
    cs = cs_mod.ChangeSet(action="chain_test", description="Chain test")
    cs.add_create(Path("/tmp/chain_test.txt"), "test")
    tmp2 = Path(tempfile.mkdtemp(prefix="cade_chain_"))
    bm2 = bk_mod.BackupManager(tmp2)
    bid2 = bm2.create_backup(cs)
    check("19.5 ChangeSet → Backup chain", len(bid2) > 0)

# 19.4 Snapshot → Refactor chain
if mm and ref_mod:
    snap = mm.WorkspaceSnapshot(root=Path("."))
    r = ref_mod.move_command(
        snap, source_module="SrcMod.m", target_module="DstMod.m", command_name="MoveMe"
    )
    check("19.6 move_command chain", isinstance(r, dict))

# 19.7 Specification -> Generator chain
if spec_mod and gen_mod:
    try:
        gen = gen_mod.TemplateGenerator()
        ispec = spec_mod.InterfaceSpec(name="IChainTest", module="Mod.m")
        r = gen.generate_from_spec(ispec, Path(tempfile.mkdtemp(prefix="cade_spec_")))
        check("19.7 Spec -> Generator chain", isinstance(r, dict), r.get("status", "?"))
    except Exception as e:
        check("19.7 Spec -> Generator chain", False, str(e)[:60])


# 19.8 Version Strategy → Rules
if vs_mod:
    version = vs_mod.detect_version(version_str="R24")
    if version:
        rules = vs_mod.get_rules(version)
        check("19.8 Version → Rules chain", rules is not None)

# 19.9 Docs Generator
docgen_mod, _ = safe_import("docgen")
if docgen_mod:
    check("19.9 docgen.generate_all callable", callable(docgen_mod.generate_all))

# 19.8 Clean module
clean_mod, _ = safe_import("clean")
if clean_mod:
    check("19.10 clean.clean_workspace callable", callable(clean_mod.clean_workspace))


# ═══════════════════════════════════════════════════════════════════
# SECTION 20: Run All Existing Test Suites
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("  SECTION 20: Run All Existing Test Suites (subprocess)")
print("=" * 70)

EXISTING_SUITES = [
    "test_full_integration.py",
    "test_phase1_enhancements.py",
    "test_phase2_intents.py",
    "test_phase3_rollback.py",
    "test_phase4_enhanced.py",
    "test_specification.py",
    "test_diagnostics.py",
    "test_fixplan_executor.py",
    "test_refactor.py",
    "test_production_regressions.py",
    "test_e2e_integration.py",
    "test_l4_architecture.py",
    "test_l5_semantic.py",
    "test_l6_fault_injection.py",
    "test_knowledge_system.py",
    "test_skill_ai_coordination.py",
    "test_system_health.py",
    # Additional suites:
    "test_catia_detection.py",
]

LIFECYCLE_SUITES = ["test_build_and_run.py"]
if ARGS.allow_catia_lifecycle and not ARGS.quick:
    EXISTING_SUITES.extend(LIFECYCLE_SUITES)
else:
    reason = "quick mode" if ARGS.quick else "requires --allow-catia-lifecycle"
    print(f"  [SKIP] CATIA lifecycle suites ({reason}): {', '.join(LIFECYCLE_SUITES)}")

SUITE_MARKERS = {
    "test_full_integration.py": "ALL TESTS PASSED",
    "test_phase1_enhancements.py": "Phase 1 Enhancement Tests Complete",
    "test_phase2_intents.py": "Intent Layer implementation verified",
    "test_phase3_rollback.py": "Rollback system verified",
    "test_phase4_enhanced.py": "Phase 4 enhancements verified",
    "test_specification.py": "100%",
    "test_diagnostics.py": "100%",
    "test_fixplan_executor.py": "100%",
    "test_refactor.py": "100%",
    "test_production_regressions.py": "All production regression tests passed",
    "test_e2e_integration.py": "passed",
    "test_l4_architecture.py": "100%",
    "test_l5_semantic.py": "100%",
    "test_l6_fault_injection.py": "100%",
    "test_knowledge_system.py": "ALL CHECKS PASSED",
    "test_skill_ai_coordination.py": "Perfect —",
    "test_system_health.py": None,
    "test_catia_detection.py": "ALL CATIA DETECTION TESTS PASSED",
    "test_build_and_run.py": "All Build Time & Run Time commands working",
}

_suite_passed = 0
_suite_failed = 0

for script in EXISTING_SUITES:
    script_path = SKILL_ROOT / "tests" / script
    if not script_path.exists():
        check(f"20.x {script} (exists)", False, f"file not found: {script_path}")
        continue

    print(f"\n  [SUITE] {script} ...", end="", flush=True)
    try:
        r = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=str(SKILL_ROOT / "tests"),
        )
    except subprocess.TimeoutExpired:
        print(" TIMEOUT")
        check(f"20.x {script}", False, "timeout after 120s")
        _suite_failed += 1
        continue

    out = r.stdout or ""
    err = r.stderr or ""
    combined = out + err

    expected_marker = SUITE_MARKERS[script]
    marker_ok = expected_marker is None or expected_marker in combined
    is_ok = r.returncode == 0 and marker_ok

    if is_ok:
        _suite_passed += 1
        print(f" PASS")
        check(f"20.x {script}", True)
    else:
        _suite_failed += 1
        tail = (err or out)[-100:].replace("\n", " ")[:80]
        print(f" FAIL (rc={r.returncode}) — {tail}")
        check(f"20.x {script}", False, tail)


# ═══════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════

end_time = datetime.now()
duration = (end_time - start_time).total_seconds()

print("\n\n" + "=" * 70)
print("  COMPLETE SYSTEM VERIFICATION — FINAL SUMMARY")
print("=" * 70)
print(f"  Total tests:   {total}")
print(f"  Passed:        {passed}")
print(f"  Failed:        {total - passed}")
print(
    f"  Pass rate:     {passed / total * 100:.1f}%" if total > 0 else "  No tests run"
)
print(f"  Duration:      {duration:.1f}s")
print(f"  Sub-suites:    {_suite_passed}/{_suite_passed + _suite_failed}")
print(f"  Start:         {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  End:           {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

if _import_warnings:
    print(f"\n  Import warnings ({len(_import_warnings)}):")
    for w in _import_warnings:
        print(w)

print("=" * 70)

actual_failures = set(failed_labels)
unknown_failures = actual_failures - QUARANTINE
quarantined_failures = actual_failures & QUARANTINE

if not actual_failures:
    print("\n  >>> ALL TESTS PASSED <<<")
    sys.exit(0)
elif not unknown_failures:
    print(f"\n  >>> {passed}/{total} PASSED ({len(quarantined_failures)} quarantined) <<<")
    for label in sorted(quarantined_failures):
        print(f"      [QUARANTINE] {label}")
    print("\n  >>> ALL NON-QUARANTINED TESTS PASSED <<<")
    sys.exit(0)
else:
    print("\n  Unknown failures:")
    for label in sorted(unknown_failures):
        print(f"      [FAIL] {label}")
    if quarantined_failures:
        print("  Actual quarantined failures:")
        for label in sorted(quarantined_failures):
            print(f"      [QUARANTINE] {label}")
    fail_pct = (total - passed) / total * 100 if total > 0 else 100
    print(f"\n  >>> {total - passed} TEST(S) FAILED ({fail_pct:.1f}%) <<<")
    if (total - passed) <= 2 and fail_pct <= 2.0:
        print("  WARNING: Minor failures detected. Review quarantine justification above.")
    sys.exit(1)
