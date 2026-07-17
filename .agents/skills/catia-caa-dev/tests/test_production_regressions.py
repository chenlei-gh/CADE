#!/usr/bin/env python3
"""Focused regression tests for production safety contracts."""

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from actions import ActionContext, create_framework
from analyzer import WorkspaceAnalyzer
from build import verify_build
from changeset import ChangeSet, Patch, merge_changesets
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

    # Wrapper/system errors must count even when mkmk returns zero.
    wrapper_output = (
        "# make-ERROR: C:\\Build Output\\BrokenModule.m\n"
        "# syst-ERROR: C:\\Program Files\\Dassault Systemes\\broken.obj: access denied\n"
    )
    parsed_wrapper = parse_mkmk_output(wrapper_output)
    check("make/syst errors are parsed", parsed_wrapper["error_count"] == 2, str(parsed_wrapper))
    syst_errors = [e for e in parsed_wrapper["errors"] if e.get("message") == "access denied"]
    check("syst error preserves message", len(syst_errors) == 1, str(parsed_wrapper["errors"]))

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
