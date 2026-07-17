#!/usr/bin/env python3
"""Focused regression tests for production safety contracts."""

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from actions import ActionContext, create_framework
from analyzer import WorkspaceAnalyzer
import build as build_module
import cade as cade_module
from build import verify_build
from changeset import ChangeSet, Patch, merge_changesets
from diagnostics import DiagnosticsEngine
from generator import TemplateGenerator
from parser import parse_mkmk_output
from repair import RepairLoop, RepairState
from utils import Cache

workspace = Path(tempfile.mkdtemp(prefix="cade_production_regressions_"))
total = passed = 0
failures = []


def check(label, ok, detail=""):
    global total, passed
    total += 1
    if ok:
        passed += 1
    else:
        failures.append(label)
    trailer = f" — {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{trailer}")


try:
    # Rejection must be side-effect free.
    rejected_parent = workspace / "must_not_exist"
    cs = ChangeSet(action="reject", description="reject before writes")
    cs.add_create(rejected_parent / "new.txt", "new")
    cs.add_modify(workspace / "missing.txt", "bad")
    result = cs.apply(workspace_root=workspace)
    check("invalid changeset is rejected", result["status"] == "rejected", str(result.get("errors", [])))
    check("rejected changeset creates no parent", not rejected_parent.exists())

    # insert_after must terminate even when inserted content contains the target.
    target_file = workspace / "patch.txt"
    target_file.write_text("TARGET\n", encoding="utf-8")
    patch_cs = ChangeSet(action="patch", description="safe insert")
    patch_cs.add_patch(Patch(target_file, "insert_after", "TARGET", "TARGET child"))
    patch_result = patch_cs.apply(workspace_root=workspace)
    check("insert_after with recursive-looking content applies", patch_result["status"] == "applied", str(patch_result.get("errors", [])))
    check("insert_after inserts exactly once", target_file.read_text(encoding="utf-8").count("TARGET child") == 1)

    # A ChangeSet may create a file and patch that newly-created content atomically.
    created_file = workspace / "created_then_patched.txt"
    create_patch = ChangeSet(action="create_patch", description="create and patch")
    create_patch.add_create(created_file, "base\n")
    create_patch.add_patch(Patch(created_file, "append", "", "extra"))
    create_patch_result = create_patch.apply(workspace_root=workspace)
    check("create+patch same file applies", create_patch_result["status"] == "applied", str(create_patch_result.get("errors", [])))
    check("create+patch content retained", created_file.exists() and "extra" in created_file.read_text(encoding="utf-8"))

    # Framework + modules is advertised as one operation and must be applicable.
    ctx = ActionContext(workspace)
    framework_result = create_framework(ctx, "CombinedFramework", modules=["CoreModule"])
    check("framework with modules returns pending", framework_result.get("status") == "pending", framework_result.get("message", ""))
    framework_cs = ChangeSet.from_dict(framework_result.get("changeset", {}))
    framework_apply = framework_cs.apply(workspace_root=workspace)
    check("framework with modules applies", framework_apply["status"] == "applied", str(framework_apply.get("errors", [])))
    check("framework module exists", (workspace / "CombinedFramework.edu" / "CoreModule.m" / "Imakefile.mk").exists())

    # Generated tests must use APIs available in B28, not an invented test framework.
    generated_tests = workspace / "generated_tests"
    testcase_result = TemplateGenerator().generate("testcase", "GeneratedTest", generated_tests)
    generated_header = (generated_tests / "GeneratedTest.h").read_text(encoding="utf-8")
    generated_source = (generated_tests / "GeneratedTest.cpp").read_text(encoding="utf-8")
    check("testcase generation succeeds", testcase_result.get("status") == "success", str(testcase_result))
    check("testcase omits unavailable CATTestCase", '#include "CATTestCase.h"' not in generated_header and "public CATTestCase" not in generated_header and ": CATTestCase(" not in generated_source)
    check("testcase uses supported CATAssert", "CATAssert(" in generated_source)
    check("testcase omits unavailable suite macros", "CATBeginTestSuite" not in generated_source and "CATAddTest" not in generated_source)

    # Static diagnostics must reject the legacy patterns found by the real TTEST build.
    legacy_source = workspace / "CombinedFramework.edu" / "CoreModule.m" / "src" / "LegacyTest.h"
    legacy_source.write_text('#include "CATTestCase.h"\n', encoding="utf-8")
    legacy_addin = legacy_source.with_name("LegacyAddin.cpp")
    legacy_addin.write_text("CATImplementHeaderResources(LegacyHdr, CATCommandHeader, LegacyHdr);\n", encoding="utf-8")
    legacy_snapshot = WorkspaceAnalyzer(workspace).analyze()
    legacy_diagnostics = DiagnosticsEngine(legacy_snapshot)
    legacy_diagnostics.run_all()
    compile_problems = [d.problem for d in legacy_diagnostics.diagnostics if d.category == "compile_contract"]
    check("diagnostics detect unavailable CATTestCase", any("CATTestCase" in p for p in compile_problems), str(compile_problems))
    check("diagnostics detect invalid header macro", any("CommandHeader" in p for p in compile_problems), str(compile_problems))

    # The documented direct `build.py <workspace> -a` CLI form must remain valid.
    cli_calls = []
    with patch.object(sys, "argv", ["build.py", str(workspace), "-a"]), \
            patch.object(build_module, "build_workspace", side_effect=lambda ws, opts, timeout: cli_calls.append((ws, opts, timeout)) or {"status": "success"}), \
            patch.object(build_module, "output_json", return_value=None):
        build_module.main()
    check("build CLI accepts direct -a", bool(cli_calls) and cli_calls[0][1] == "-a", str(cli_calls))

    kernel_calls = []
    with patch.object(cade_module, "_kernel", side_effect=lambda mode, text, workspace=None: kernel_calls.append((mode, text, workspace)) or {"status": "ok", "message": "mock"}), \
            patch.object(cade_module, "_print_kernel", return_value=None):
        cade_module.cmd_diagnose([str(workspace)])
    check("diagnose CLI uses positional workspace", bool(kernel_calls) and kernel_calls[0][2] == str(workspace), str(kernel_calls))

    # Conflicting merge must not silently select the last writer.
    conflict_path = workspace / "conflict.txt"
    first = ChangeSet(action="first", description="first")
    second = ChangeSet(action="second", description="second")
    first.add_create(conflict_path, "first")
    second.add_create(conflict_path, "second")
    merged = merge_changesets(first, second)
    conflict_apply = merged.apply(workspace_root=workspace)
    check("merge conflict blocks apply", conflict_apply["status"] == "rejected", str(conflict_apply.get("errors", [])))
    check("merge conflict writes no file", not conflict_path.exists())

    # Wrapper/system errors must count even when mkmk returns zero. B28 uses
    # mkmk-ERROR; make-ERROR remains a compatibility variant.
    wrapper_output = (
        "   # mkmk-ERROR: C:\\Build Output\\Broken Module.m\n"
        "mkmk-ERROR: C:\\Build Output\\Second Module.m\n"
        "# make-ERROR: C:\\Build Output\\Legacy Module.m\n"
        "  # syst-ERROR: C:\\Program Files\\Dassault Systemes\\broken.obj: access denied\n"
    )
    parsed_wrapper = parse_mkmk_output(wrapper_output)
    check("mkmk/make/syst errors are parsed", parsed_wrapper["error_count"] == 4, str(parsed_wrapper))
    wrapper_codes = [e.get("code") for e in parsed_wrapper["errors"]]
    check("mkmk wrapper code is preserved", wrapper_codes.count("mkmk-ERROR") == 2, str(wrapper_codes))
    syst_errors = [e for e in parsed_wrapper["errors"] if e.get("message") == "access denied"]
    check("syst error preserves message", len(syst_errors) == 1 and syst_errors[0].get("code") == "syst-ERROR", str(parsed_wrapper["errors"]))
    check("wrapper Windows path with spaces is parsed", any(e.get("file") == "Broken Module.m" for e in parsed_wrapper["errors"]), str(parsed_wrapper["errors"]))

    prose_output = (
        "Documentation says mkmk-ERROR: this is only an example.\n"
        "prefix # syst-ERROR: C:\\Build\\broken.obj: not a real record\n"
        "mkmk completed successfully\n"
    )
    parsed_prose = parse_mkmk_output(prose_output)
    check("wrapper tokens in prose are ignored", parsed_prose["error_count"] == 0, str(parsed_prose))
    single_wrapper = parse_mkmk_output("# mkmk-ERROR: C:\\Build Output\\OnlyOnce.m")
    check("one wrapper line is counted once", single_wrapper["error_count"] == 1, str(single_wrapper))

    # Build verification must reject stale or implausible target DLLs.
    bin_dir = workspace / "win_b64" / "code" / "bin"
    bin_dir.mkdir(parents=True)
    target_dll = bin_dir / "TargetModule.dll"
    target_dll.write_bytes(b"x" * 2048)
    build_start = datetime.now()
    stale_time = (build_start - timedelta(minutes=5)).timestamp()
    os.utime(target_dll, (stale_time, stale_time))
    stale_verify = verify_build(
        workspace,
        expected_modules=["TargetModule"],
        build_start_time=build_start,
    )
    check("stale target DLL fails verification", not stale_verify["ok"], str(stale_verify["issues"]))
    check("stale DLL issue is explicit", any("stale" in issue.lower() for issue in stale_verify["issues"]), str(stale_verify["issues"]))

    fresh_time = (build_start + timedelta(seconds=1)).timestamp()
    os.utime(target_dll, (fresh_time, fresh_time))
    target_dll.write_bytes(b"tiny")
    tiny_verify = verify_build(
        workspace,
        expected_modules=["TargetModule"],
        build_start_time=build_start,
    )
    check("tiny target DLL fails verification", not tiny_verify["ok"], str(tiny_verify["issues"]))

    # Mixed module results must identify only stale/missing targets.
    fresh_dll = bin_dir / "FreshModule.dll"
    stale_dll = bin_dir / "StaleModule.dll"
    fresh_dll.write_bytes(b"f" * 2048)
    stale_dll.write_bytes(b"s" * 2048)
    os.utime(fresh_dll, (fresh_time, fresh_time))
    os.utime(stale_dll, (stale_time, stale_time))
    mixed_verify = verify_build(
        workspace,
        expected_modules=["FreshModule", "StaleModule", "MissingModule"],
        build_start_time=build_start,
    )
    mixed_issues = mixed_verify["issues"]
    check("mixed module verification fails", not mixed_verify["ok"], str(mixed_issues))
    check("mixed verification identifies stale module", any("StaleModule.dll" in issue and "stale" in issue for issue in mixed_issues), str(mixed_issues))
    check("mixed verification accepts fresh module", not any("FreshModule.dll" in issue for issue in mixed_issues), str(mixed_issues))
    check("mixed verification identifies missing module", any("missingmodule.dll" in issue.lower() and "not found" in issue.lower() for issue in mixed_issues), str(mixed_issues))

    # The final cache and log must reflect post-build verification, not pre-verification success.
    build_ws = workspace / "mock_build"
    build_fw = build_ws / "MockFramework.edu"
    build_mod = build_fw / "MockModule.m"
    (build_fw / "IdentityCard").mkdir(parents=True)
    (build_fw / "IdentityCard" / "IdentityCard.h").write_text("// identity", encoding="utf-8")
    (build_fw / "Imakefile.mk").write_text("", encoding="utf-8")
    build_mod.mkdir()
    (build_mod / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY", encoding="utf-8")

    class MemoryLogger:
        instances = []

        def __init__(self, *_args, **_kwargs):
            self.lines = []
            self.__class__.instances.append(self)

        def clear(self):
            self.lines.clear()

        def write(self, message):
            self.lines.append(str(message))

    class MemoryCache:
        instances = []

        def __init__(self, *_args, **_kwargs):
            self.data = {}
            self.__class__.instances.append(self)

        def load(self):
            return dict(self.data)

        def save(self, data):
            self.data = dict(data)

    class FakeEnvironment:
        _build_bat = None

        def load_config(self):
            return True

        def build_time_command(self, _workspace, _options):
            return ["fake-build"], "fake-build"

    fake_process = SimpleNamespace(returncode=0, stdout="build completed", stderr="")
    failed_verification = {"ok": False, "issues": ["MockModule.dll: stale DLL"]}
    with patch.object(build_module, "Logger", MemoryLogger), \
            patch.object(build_module, "Cache", MemoryCache), \
            patch.object(build_module, "CAAEnvironment", FakeEnvironment), \
            patch.object(build_module, "setup_prerequisite_path", return_value={"status": "success"}), \
            patch.object(build_module.subprocess, "run", return_value=fake_process), \
            patch.object(build_module, "verify_build", return_value=failed_verification), \
            patch.object(build_module, "sync_runtime_view", return_value={"synced": [], "errors": [], "ok": True}):
        mocked_build = build_module.build_workspace(build_ws)

    final_cache = MemoryCache.instances[-1].data
    final_log = MemoryLogger.instances[-1].lines
    check("verification failure changes returned build status", mocked_build["status"] == "failed_verification", str(mocked_build))
    check("final cache stores verification failure", final_cache.get("status") == "failed_verification", str(final_cache))
    check("final cache preserves prerequisite workspace", final_cache.get("prereq_workspace") == str(build_ws), str(final_cache))
    check("final build log stores verification failure", any("Status: failed_verification" in line for line in final_log), str(final_log))

    successful_verification = {"ok": True, "issues": [], "dll_count": 1, "dlls": [{"name": "MockModule.dll"}]}
    MemoryLogger.instances.clear()
    MemoryCache.instances.clear()
    with patch.object(build_module, "Logger", MemoryLogger), \
            patch.object(build_module, "Cache", MemoryCache), \
            patch.object(build_module, "CAAEnvironment", FakeEnvironment), \
            patch.object(build_module, "setup_prerequisite_path", return_value={"status": "success"}), \
            patch.object(build_module.subprocess, "run", return_value=fake_process), \
            patch.object(build_module, "verify_build", return_value=successful_verification), \
            patch.object(build_module, "sync_runtime_view", return_value={"synced": [], "errors": [], "ok": True}):
        successful_build = build_module.build_workspace(build_ws)
    check("successful build returns verification evidence", successful_build.get("verification") == successful_verification, str(successful_build))
    check("successful cache stores verification evidence", MemoryCache.instances[-1].data.get("verification") == successful_verification, str(MemoryCache.instances[-1].data))

    # Repair must diagnose the output returned by this build, not stale cache data.
    repair_ws = workspace / "repair"
    repair_ws.mkdir()
    Cache("build.json", workspace_root=repair_ws).save({
        "output": "old.cpp(1): error C2143: stale cached failure"
    })
    current_build = {
        "status": "failed",
        "output": "current.cpp(7): error C1083: Cannot open include file: 'Current.h'",
        "error_count": 1,
    }
    repair_loop = RepairLoop(repair_ws, with_build=True)
    with patch("build.build_workspace", return_value=current_build):
        build_diagnosis = repair_loop._diagnose_build()
    build_files = [d.get("file") for d in build_diagnosis["diagnostics"]]
    check("repair uses current build output", "current.cpp" in build_files, str(build_diagnosis))
    check("repair ignores stale cached output", "old.cpp" not in build_files, str(build_diagnosis))

    failed_without_details = {"status": "error", "message": "tool invocation failed", "output": ""}
    with patch("build.build_workspace", return_value=failed_without_details):
        failed_diagnosis = repair_loop._diagnose_build()
    check("unparsed build failure remains diagnostic", failed_diagnosis["total"] == 1, str(failed_diagnosis))

    # Static-only repair results must never imply that build verification ran.
    static_clean = RepairLoop(repair_ws, with_build=False)
    static_clean._diagnose_static = lambda: {"total": 0, "auto_fixable": 0, "diagnostics": []}
    clean_result = static_clean.run()
    check("static clean message discloses no build", "static analysis only" in clean_result.message.lower(), clean_result.message)

    static_fix = RepairLoop(repair_ws, with_build=False)
    static_fix._diagnose_static = lambda: {
        "total": 1,
        "auto_fixable": 1,
        "diagnostics": [{
            "severity": "error",
            "message": "missing generated file",
            "file": "generated.h",
            "auto_fixable": True,
            "fix_plan": {
                "action": "create_file",
                "file": "generated.h",
                "line": "// generated",
            },
        }],
    }
    static_fix._create_backup = lambda: "test-backup"
    fixed_result = static_fix.run()
    check("static fix succeeds", fixed_result.state == RepairState.FIXED, fixed_result.message)
    check("static fix discloses no build", "build verification was not run" in fixed_result.message.lower(), fixed_result.message)

    # Addins are neither interfaces nor generic components; workbench names are unique.
    analyzer_fw = workspace / "AnalyzerFramework.edu"
    (analyzer_fw / "IdentityCard").mkdir(parents=True)
    (analyzer_fw / "IdentityCard" / "IdentityCard.h").write_text("", encoding="utf-8")
    analyzer_mod = analyzer_fw / "AnalyzerModule.m"
    local_interfaces = analyzer_mod / "LocalInterfaces"
    src_dir = analyzer_mod / "src"
    local_interfaces.mkdir(parents=True)
    src_dir.mkdir()
    (analyzer_mod / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY", encoding="utf-8")
    (local_interfaces / "SampleWorkbenchAddin.h").write_text(
        "class SampleWorkbenchAddin : public CATBaseUnknown { CATDeclareClass; };",
        encoding="utf-8",
    )
    (src_dir / "SampleWorkbench.cpp").write_text(
        "CATCmdWorkbench SampleWorkbench;", encoding="utf-8"
    )
    (src_dir / "SampleWorkbenchAddin.cpp").write_text(
        "CATIAfrGeneralWksAddin CreateCommands CreateToolbars", encoding="utf-8"
    )
    analyzer_snapshot = WorkspaceAnalyzer(workspace).analyze()
    analyzed_fw = next(fw for fw in analyzer_snapshot.frameworks if fw.name == "AnalyzerFramework.edu")
    analyzed_mod = analyzed_fw.modules[0]
    check("addin is not classified as interface", "SampleWorkbenchAddin" not in [i.name for i in analyzed_mod.interfaces])
    check("addin is not classified as component", "SampleWorkbenchAddin" not in [c.name for c in analyzed_mod.components])
    workbench_names = [wb.name for wb in analyzed_fw.workbenches]
    check("workbench names are unique", len(workbench_names) == len(set(workbench_names)), str(workbench_names))
finally:
    shutil.rmtree(workspace, ignore_errors=True)

print(f"\nProduction regressions: {passed}/{total}")
if failures:
    print("Failures:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)
print("All production regression tests passed")
sys.exit(0)
